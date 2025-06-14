"""
統一的 LangGraph 圖實作

根據配置動態構建 LangGraph 的 StateGraph，定義所有節點的實現，
包括工具邏輯的直接內嵌。嚴格參考 reference_arch.md 中定義的 Agent 核心流程。
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langchain_core.runnables import RunnableConfig
from google.genai import Client

from schemas.agent_types import OverallState, MsgNode, ToolPlan, AgentPlan, ToolExecutionState
from utils.config_loader import load_typed_config
from prompt_system.prompts import get_current_date, PromptSystem
from .progress_mixin import ProgressMixin
from schemas.config_types import AppConfig


class UnifiedAgent(ProgressMixin):
    """統一的 Agent 實作，根據配置動態調整行為"""
    
    def __init__(self, config: Optional[AppConfig] = None):
        """
        初始化統一 Agent
        
        Args:
            config: 型別安全的配置實例，如果為 None 則載入預設配置
        """
        # 首先初始化 ProgressMixin
        super().__init__()
        
        self.config = config or load_typed_config()
        self.logger = logging.getLogger(__name__)
        
        # 從配置獲取 agent 設定 - 使用型別安全存取
        self.agent_config = self.config.agent
        self.tools_config = self.config.agent.tools
        self.behavior_config = self.config.agent.behavior
        
        # 初始化多個 LLM 實例
        self.llm_instances = self._initialize_llm_instances()
        
        # 初始化 Google 客戶端（如果工具啟用）
        self.google_client = None
        if self.config.is_tool_enabled("google_search"):
            api_key = self.config.gemini_api_key
            if api_key:
                self.google_client = Client(api_key=api_key)
        
        # 初始化提示詞系統
        self.prompt_system = PromptSystem(
            persona_cache_enabled=self.config.prompt_system.persona.cache_personas
        )
    
    def _initialize_llm_instances(self) -> Dict[str, Optional[ChatGoogleGenerativeAI]]:
        """初始化不同用途的 LLM 實例"""
        api_key = self.config.gemini_api_key
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # 使用型別安全的配置存取
        llm_configs_source = self.config.llm.models
        
        llm_instances = {}
        for purpose, llm_config in llm_configs_source.items():
            try:
                # llm_config 現在總是 LLMModelConfig 實例
                model_name = llm_config.model
                temperature = llm_config.temperature
                
                llm_instances[purpose] = ChatGoogleGenerativeAI(
                    model=model_name,
                    temperature=temperature,
                    api_key=api_key
                )
                self.logger.info(f"初始化 {purpose} LLM: {model_name}")
            except Exception as e:
                self.logger.warning(f"初始化 {purpose} LLM 失敗: {e}")
                llm_instances[purpose] = None
        
        self.tool_analysis_llm: ChatGoogleGenerativeAI = llm_instances.get("tool_analysis")
        self.final_answer_llm: ChatGoogleGenerativeAI = llm_instances.get("final_answer")
        
        return llm_instances
    
    def build_graph(self) -> StateGraph:
        """建立簡化的 LangGraph"""
        builder = StateGraph(OverallState)
        
        # 核心節點
        builder.add_node("generate_query_or_plan", self.generate_query_or_plan)
        builder.add_node("execute_single_tool", self.execute_single_tool)
        builder.add_node("reflection", self.reflection)
        builder.add_node("finalize_answer", self.finalize_answer)
        
        # 流程設置
        builder.add_edge(START, "generate_query_or_plan")
        
        # 條件路由：根據計劃決定下一步
        builder.add_conditional_edges(
            "generate_query_or_plan",
            self.route_and_dispatch_tools,
            {
                "execute_tools": "execute_single_tool",
                "direct_answer": "finalize_answer"
            }
        )
        
        # Connect dispatch node to reflection
        builder.add_edge("execute_single_tool", "reflection")
        
        # 反思後的路由決策
        builder.add_conditional_edges(
            "reflection",
            self.decide_next_step,
            {
                "continue": "generate_query_or_plan",  # 重新規劃下一輪
                "finish": "finalize_answer"
            }
        )
        
        builder.add_edge("finalize_answer", END)
        return builder.compile()

    def route_after_planning(self, state: OverallState) -> str:
        """規劃後的路由決策"""
        agent_plan = state.agent_plan
        if agent_plan and agent_plan.needs_tools and agent_plan.tool_plans:
            return "use_tools"
        else:
            return "direct_answer"

    async def generate_query_or_plan(self, state: OverallState) -> Dict[str, Any]:
        """
        統一的計劃生成節點：同時決定工具使用和生成查詢
        
        參考 Gemini 實作，使用 structured output 一次性決定：
        1. 是否需要使用工具
        2. 需要使用哪些工具
        3. 每個工具的具體查詢參數
        """
        try:
            self.logger.info("generate_query_or_plan: 開始生成執行計劃")
            
            # 通知開始階段
            await self._notify_progress(
                stage="generate_query", 
                message="🤔 正在分析您的問題並制定搜尋計劃..."
            )
            
            user_content = state.messages[-1].content
            max_tool_rounds = self.behavior_config.max_tool_rounds
            
            if max_tool_rounds == 0:
                # 純對話模式
                return {
                    "agent_plan": AgentPlan(needs_tools=False),
                    "tool_round": 0
                }
            
            # 使用 structured LLM 生成完整計劃
            if not self.tool_analysis_llm:
                # 回退到簡單邏輯
                needs_tools = self._analyze_tool_necessity_fallback(state.messages)
                queries = [user_content] if needs_tools else []
                tool_plans = []
                if needs_tools and self.google_client:
                    tool_plans = [ToolPlan(tool_name="google_search", queries=queries)]
                
                agent_plan = AgentPlan(
                    needs_tools=needs_tools,
                    tool_plans=tool_plans,
                    reasoning="使用簡化邏輯決策"
                )
            else:
                # 使用 structured output 生成計劃
                agent_plan = await self._generate_structured_plan(state.messages, state.messages_global_metadata)
            
            self.logger.info(f"生成計劃: 需要工具={agent_plan.needs_tools}, 工具數量={len(agent_plan.tool_plans)}")
            
            return {
                "agent_plan": agent_plan,
                "tool_round": 0,
                "research_topic": user_content
            }
            
        except Exception as e:
            self.logger.error(f"generate_query_or_plan 失敗: {e}")
            return {
                "agent_plan": AgentPlan(needs_tools=False),
                "finished": True
            }

    async def _generate_structured_plan(self, messages: List[MsgNode], messages_global_metadata: str = "") -> AgentPlan:
        """使用 structured output 生成執行計劃"""
        try:
            # 構建計劃生成提示詞
            plan_prompt = self._build_planning_prompt(messages, messages_global_metadata)
            
            # 由於 LangChain 的 structured output 可能不支援複雜的嵌套結構，
            # 我們先用普通 LLM 生成 JSON，然後手動解析
            response = await asyncio.to_thread(self.tool_analysis_llm.invoke, plan_prompt)
            
            # 解析 JSON 回應
            plan_data = self._parse_plan_response(response.content)
            
            # 構建 AgentPlan
            tool_plans = []
            if plan_data.get("needs_tools", False):
                for tool_data in plan_data.get("tool_plans", []):
                    tool_plan = ToolPlan(
                        tool_name=tool_data.get("tool_name", "google_search"),
                        queries=tool_data.get("queries", []),
                        priority=tool_data.get("priority", 1)
                    )
                    tool_plans.append(tool_plan)
            
            return AgentPlan(
                needs_tools=plan_data.get("needs_tools", False),
                tool_plans=tool_plans,
                reasoning=plan_data.get("reasoning", "")
            )
            
        except Exception as e:
            self.logger.warning(f"structured plan 生成失敗，回退到簡化邏輯: {e}")
            # 回退邏輯
            needs_tools = self._analyze_tool_necessity_fallback(messages)
            queries = [messages[-1].content[:100]] if needs_tools else []
            tool_plans = []
            if needs_tools and self.google_client:
                tool_plans = [ToolPlan(tool_name="google_search", queries=queries)]
            
            return AgentPlan(
                needs_tools=needs_tools,
                tool_plans=tool_plans,
                reasoning="回退到簡化邏輯"
            )

    def _build_planning_prompt(self, messages: List[MsgNode], messages_global_metadata: str = "") -> List:
        """構建計劃生成提示詞（使用統一 PromptSystem 和工具提示詞檔案），整合全域 metadata"""
        try:
            # 使用 PromptSystem 構建基礎 system prompt
            base_system_prompt = self.prompt_system.get_system_instructions(
                config=self.config,  # 使用 typed config
                available_tools=self.config.get_enabled_tools(),
                messages_global_metadata=messages_global_metadata
            )
            
            # 從檔案讀取計劃生成特定的指令
            current_date = get_current_date(self.config.system.timezone)
            planning_instructions = self.prompt_system.get_planning_instructions(
                current_date=current_date
            )
            
            # 組合完整的 system prompt
            full_system_prompt = base_system_prompt + "\n\n" + planning_instructions
            messages_for_llm = [SystemMessage(content=full_system_prompt)]
            
            # 添加對話歷史
            for msg in messages:
                if msg.role == "user":
                    messages_for_llm.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages_for_llm.append(AIMessage(content=msg.content))
            
            return messages_for_llm
            
        except Exception as e:
            self.logger.error(f"構建計劃提示詞失敗: {e}")
            # 回退到簡化版本
            fallback_prompt = "你是一個智能助手。請分析用戶的問題並決定是否需要搜尋資訊。"
            return [SystemMessage(content=fallback_prompt)]

    def _parse_plan_response(self, response_content: str) -> Dict[str, Any]:
        """解析計劃回應的 JSON"""
        try:
            # 嘗試提取 JSON
            if "```json" in response_content:
                start_marker = "```json"
                end_marker = "```"
                start_index = response_content.find(start_marker)
                end_index = response_content.rfind(end_marker)
                
                if start_index != -1 and end_index != -1 and end_index > start_index:
                    json_str = response_content[start_index + len(start_marker):end_index].strip()
                    return json.loads(json_str)
            
            # 嘗試直接解析
            if response_content.strip().startswith("{"):
                return json.loads(response_content.strip())
            
            # 如果都失敗，返回預設值
            return {"needs_tools": False, "tool_plans": [], "reasoning": "JSON 解析失敗"}
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON 解析失敗: {e}")
            return {"needs_tools": False, "tool_plans": [], "reasoning": "JSON 解析失敗"}

    def route_and_dispatch_tools(self, state: OverallState) -> Any:
        """
        規劃後的路由決策：
        如果需要工具，則返回 Send 物件列表以進行並行執行；
        否則，返回 "direct_answer" 以直接跳到最終答案。
        """
        agent_plan = state.agent_plan
        
        if agent_plan and agent_plan.needs_tools and agent_plan.tool_plans:
            # 為每個工具計劃創建並行執行任務
            sends = []
            for idx, tool_plan in enumerate(agent_plan.tool_plans):
                for query_idx, query in enumerate(tool_plan.queries):
                    sends.append(Send(
                        "execute_single_tool", 
                        {
                            "tool_name": tool_plan.tool_name,
                            "query": query,
                            "task_id": f"{idx}_{query_idx}",
                            "priority": tool_plan.priority
                        }
                    ))
            self.logger.info(f"route_and_dispatch_tools: 正在調度 {len(sends)} 個並行工具執行任務")
            return sends # 返回 Send 物件列表以進行並行執行
        else:
            self.logger.info("route_and_dispatch_tools: 無需工具，直接回答")
            return "direct_answer" # 返回字符串以直接路由

    async def execute_single_tool(self, state: ToolExecutionState) -> Dict[str, Any]:
        """執行單個工具任務（並行節點）"""
        tool_name = state.get("tool_name")
        query = state.get("query")
        task_id = state.get("task_id")
        
        try:
            self.logger.info(f"執行單個工具: {tool_name}({query})")
            
            if tool_name == "google_search":
                await self._notify_progress(
                    stage="Tool Execution",
                    message=f"🤔 正在執行 {tool_name} 工具，查詢關鍵字: {query}",
                    progress_percentage=50
                )
                result = await self._execute_google_search_single(query, task_id)
            else:
                await self._notify_progress(
                    stage="Tool Execution",
                    message=f"🤔 正在執行 {tool_name} 工具...",
                    progress_percentage=50
                )
                
                result = f"未知工具: {tool_name}"
            
            return {
                "tool_results": [result]
                # "task_id": task_id,
                # "tool_name": tool_name
            }
            
        except Exception as e:
            self.logger.error(f"工具執行失敗 {tool_name}({query}): {e}")
            return {
                "tool_results": [],
                # "task_id": task_id,
                "error": str(e)
            }

    async def _execute_google_search_single(self, query: str, task_id: str) -> str:
        """執行單個 Google 搜尋"""
        if not self.google_client:
            return f"Google 客戶端未配置，無法執行搜尋: {query}"
        
        try:
            current_date = get_current_date(timezone_str=self.config.system.timezone)
            
            # 準備傳遞給 Gemini 模型的提示
            formatted_prompt = self.prompt_system.get_web_searcher_instructions(
                research_topic=query,
                current_date=current_date
            )
            
            model_name = self.tool_analysis_llm.model
            # 調用 Gemini API 並啟用 google_search 工具
            response = self.google_client.models.generate_content(
                model=model_name,
                contents=formatted_prompt,
                config={
                    "tools": [{"google_search": {}}],
                    "temperature": 0
                }
            )
            
            if response.text:
                # 處理 grounding 和引用
                # grounding_chunks = []
                # resolved_urls = {}
                
                # # 嘗試提取 grounding_chunks
                # if response.candidates and len(response.candidates) > 0:
                #     candidate_0 = response.candidates[0]
                #     if candidate_0 and hasattr(candidate_0, 'grounding_metadata') and candidate_0.grounding_metadata:
                #         if hasattr(candidate_0.grounding_metadata, 'grounding_chunks') and candidate_0.grounding_metadata.grounding_chunks:
                #             grounding_chunks = candidate_0.grounding_metadata.grounding_chunks

                # 處理 URL 解析和引用
                # try:
                #     resolved_urls = resolve_urls(grounding_chunks, task_id)
                #     return response.text
                # except Exception as e:
                #     self.logger.warning(f"處理引用失敗: {e}")
                return response.text
            else:
                return f"針對查詢「{query}」沒有找到內容。"
                
        except Exception as e:
            self.logger.error(f"Google 搜尋失敗: {e}")
            return f"搜尋執行失敗: {str(e)}"

    def _deduplicate_results(self, results: List[str]) -> List[str]:
        """去重和排序結果"""
        if not results:
            return []
        
        # 簡單去重
        seen = set()
        unique_results = []
        for result in results:
            if result and result not in seen:
                seen.add(result)
                unique_results.append(result)
        
        return unique_results

    async def reflection(self, state: OverallState) -> Dict[str, Any]:
        """
        LangGraph 節點：反思
        
        評估工具結果的質量和完整性。
        """
        try:
            if not self.behavior_config.enable_reflection:
                # 如果禁用反思，直接認為結果充分
                return {"is_sufficient": True}
            
            self.logger.info("reflection: 開始反思工具結果")
            
            # 通知反思階段
            await self._notify_progress(
                stage="reflection",
                message="🤔 正在評估搜尋結果的品質...",
                progress_percentage=75
            )
            
            # tool_results will be accumulated from parallel execute_single_tool calls
            raw_tool_results = state.tool_results or []
            unique_tool_results = self._deduplicate_results(raw_tool_results) # Deduplicate here
            research_topic = state.research_topic
            
            # 使用專用的反思 LLM 或簡化邏輯
            is_sufficient = self._evaluate_results_sufficiency(unique_tool_results, research_topic)
            
            self.logger.info(f"reflection: 結果充分度={is_sufficient}")
            
            return {
                "is_sufficient": is_sufficient,
                "reflection_complete": True,
                "reflection_reasoning": f"基於 {len(unique_tool_results)} 個結果的評估",
                "aggregated_tool_results": unique_tool_results # Update for next stages
            }
            
        except Exception as e:
            self.logger.error(f"reflection 失敗: {e}")
            return {"is_sufficient": True}  # 失敗時假設充分

    def decide_next_step(self, state: OverallState) -> Literal["continue", "finish"]:
        """決定下一步的路由函數"""
        try:
            current_round = state.tool_round
            max_rounds = self.behavior_config.max_tool_rounds
            is_sufficient = state.is_sufficient
            
            # 決策邏輯
            if is_sufficient or current_round >= max_rounds:
                self.logger.info(f"決定完成研究 (輪次={current_round}, 充分={is_sufficient})")
                return "finish"
            else:
                self.logger.info(f"決定繼續研究 (輪次={current_round}/{max_rounds})")
                return "continue"
                
        except Exception as e:
            self.logger.error(f"decide_next_step 失敗: {e}")
            return "finish"

    async def finalize_answer(self, state: OverallState) -> Dict[str, Any]:
        """
        LangGraph 節點：生成最終答案
        
        基於所有可用的信息生成最終回答。
        """
        try:
            self.logger.info("finalize_answer: 生成最終答案")
            
            # 通知答案生成階段
            await self._notify_progress(
                stage="finalize_answer",
                message="✍️ 正在整理答案...",
                progress_percentage=90
            )
            
            messages = state.messages
            tool_results = state.aggregated_tool_results or state.tool_results or []
            
            # 構建上下文
            context = ""
            if tool_results:
                context = "\n".join([f"搜尋結果: {result}" for result in tool_results])
            
            # 生成最終答案
            try:
                final_answer = self._generate_final_answer(messages, context, state.messages_global_metadata)
            except Exception as e:
                self.logger.warning(f"LLM 答案生成失敗，使用基本回覆: {e}")
                final_answer = self._generate_basic_fallback_answer(messages, context)
            
            self.logger.info("finalize_answer: 答案生成完成")
            
            # 通知完成
            await self._notify_progress(
                stage="completed",
                message="✅ 回答完成！",
                progress_percentage=100
            )
            
            return {
                "final_answer": final_answer,
                "finished": True,
                "sources": self._extract_sources_from_results(tool_results)
            }
            
        except Exception as e:
            self.logger.error(f"finalize_answer 失敗: {e}")
            
            # 通知錯誤
            await self._notify_error(e)
            
            return {
                "final_answer": "抱歉，生成回答時發生錯誤。", 
                "finished": True
            }

    # 保留原有的輔助方法以確保向後相容性
    def _analyze_tool_necessity_fallback(self, messages: List[MsgNode]) -> bool:
        """關鍵字檢測回退方案 (仍基於最新訊息)"""
        tool_keywords = [
            "搜尋", "查詢", "最新", "現在", "今天", "今年", "查找",
            "資訊", "資料", "新聞", "消息", "更新", "狀況", "search",
            "find", "latest", "current", "recent", "what is", "告訴我",
            "網路搜尋", "網路研究"
        ]
        
        content_lower = messages[-1].content.lower()
        return any(keyword in content_lower for keyword in tool_keywords)

    def _evaluate_results_sufficiency(self, tool_results: List[str], research_topic: str) -> bool:
        """評估結果是否充分"""
        # 重構後簡化邏輯：總是認為結果充分，避免無限循環
        # 實際的輪次控制由 max_tool_rounds 來處理
        return True

    def _generate_final_answer(self, messages: List[MsgNode], context: str, messages_global_metadata: str = "") -> str:
        """生成最終答案（使用統一 PromptSystem 和工具提示詞檔案），整合全域 metadata"""
        if not messages:
            return "嗯...好像沒有收到你的訊息耶，可以再試一次嗎？😅"
        
        latest_message = messages[-1]
        user_question = latest_message.content
        
        # 使用 PromptSystem 構建系統提示詞
        try:
            # 構建基礎系統提示詞
            base_system_prompt = self.prompt_system.get_system_instructions(
                config=self.config,  # 使用 typed config
                available_tools=[],  # 最終答案生成階段不需要工具描述
                messages_global_metadata=messages_global_metadata
            )
            
            # 添加上下文資訊（如果有的話）
            if context:
                try:
                    context_prompt = self.prompt_system.get_final_answer_context(
                        context=context
                    )
                    full_system_prompt = base_system_prompt + "\n\n" + context_prompt
                except Exception as e:
                    self.logger.warning(f"讀取最終答案上下文提示詞失敗: {e}")
                    # 回退到硬編碼版本
                    context_prompt = f"以下是相關資訊：\n{context}\n請基於以上資訊回答。"
                    full_system_prompt = base_system_prompt + "\n\n" + context_prompt
            else:
                full_system_prompt = base_system_prompt
            
            messages_for_final_answer = [SystemMessage(content=full_system_prompt)]
                
            for msg in messages[:-1]: # 除了最後一條消息（當前用戶問題）
                if msg.role == "user":
                    messages_for_final_answer.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages_for_final_answer.append(AIMessage(content=msg.content))

            # 將當前用戶問題作為 HumanMessage 加入
            messages_for_final_answer.append(HumanMessage(content=user_question))
            response = self.final_answer_llm.invoke(messages_for_final_answer)
            return response.content.strip()
            
        except Exception as e:
            self.logger.warning(f"使用 LLM 生成答案失敗: {e}")
        
        return self._generate_basic_fallback_answer(messages, context)

    def _generate_basic_fallback_answer(self, messages: List[MsgNode], context: str) -> str:
        return "出現錯誤，請再試一次 🔄"

    def _extract_sources_from_results(self, tool_results: List[str]) -> List[Dict[str, str]]:
        """從工具結果中提取來源信息"""
        sources = []
        if tool_results:
            for result in tool_results:
                if isinstance(result, str) and "http" in result:
                    # 簡化的來源提取邏輯
                    sources.append({
                        "title": result[:100] + "..." if len(result) > 100 else result,
                        "url": "",
                        "snippet": result
                    })
        return sources


def create_unified_agent(config: Optional[AppConfig] = None) -> UnifiedAgent:
    """建立統一 Agent 實例"""
    return UnifiedAgent(config)


def create_agent_graph(config: Optional[AppConfig] = None) -> StateGraph:
    """建立並編譯 Agent 圖"""
    agent = create_unified_agent(config)
    return agent.build_graph() 