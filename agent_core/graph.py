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

from schemas.agent_types import OverallState, MsgNode
from utils.config_loader import load_typed_config
from prompt_system.prompts import web_searcher_instructions, get_current_date
from .agent_utils import resolve_urls, get_citations, insert_citation_markers
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
        """建立並編譯 LangGraph"""
        builder = StateGraph(OverallState)
        
        # 添加所有節點
        builder.add_node("generate_query_or_plan", self.generate_query_or_plan)
        builder.add_node("tool_selection", self.tool_selection)
        builder.add_node("execute_tool", self.execute_tool)
        builder.add_node("reflection", self.reflection)
        builder.add_node("evaluate_research", self.evaluate_research)
        builder.add_node("finalize_answer", self.finalize_answer)
        
        # 設置流程邊緣
        builder.add_edge(START, "generate_query_or_plan")
        
        # 根據配置決定流程 - 使用型別安全存取
        max_tool_rounds = self.behavior_config.max_tool_rounds
        
        if max_tool_rounds == 0:
            # 純對話模式：直接到最終答案
            builder.add_edge("generate_query_or_plan", "finalize_answer")
        else:
            # 工具模式：完整流程
            builder.add_edge("generate_query_or_plan", "tool_selection")
            builder.add_edge("tool_selection", "execute_tool")
            builder.add_edge("execute_tool", "reflection")
            
            builder.add_conditional_edges(
                "reflection",
                self.decide_next_step,
                {
                    "continue": "tool_selection",
                    "finish": "finalize_answer"
                }
            )
        
        builder.add_edge("finalize_answer", END)
        
        return builder.compile()
    
    async def generate_query_or_plan(self, state: OverallState) -> Dict[str, Any]:
        """
        LangGraph 節點：生成查詢或初步規劃
        
        分析用戶請求並決定是否需要使用工具，生成初步的行動計劃。
        """
        try:
            self.logger.info("generate_query_or_plan: 開始分析用戶請求")
            
            # 通知開始階段
            await self._notify_progress(
                stage="generate_query", 
                message="🤔 正在分析您的問題..."
            )
            
            user_content = state.messages[-1].content
            max_tool_rounds = self.behavior_config.max_tool_rounds
            
            # 決定是否需要工具
            needs_tools = False
            if max_tool_rounds > 0:
                needs_tools = self._analyze_tool_necessity(state.messages)
            
            # 生成查詢或計劃
            queries = []
            if needs_tools and self.google_client:
                queries = self._generate_search_queries(state.messages)
            
            self.logger.info(f"generate_query_or_plan: 需要工具={needs_tools}, 查詢數量={len(queries)}")
            
            return {
                "tool_round": 0,
                "needs_tools": needs_tools,
                "search_queries": queries,
                "research_topic": user_content[:200],  # 截取前200字符作為研究主題
            }
            
        except Exception as e:
            self.logger.error(f"generate_query_or_plan 失敗: {e}")
            await self._notify_progress(
                stage="error",
                message="❌ 分析問題時發生錯誤",
                progress_percentage=0
            )
            return {"finished": True}
    
    def tool_selection(self, state: OverallState) -> Dict[str, Any]:
        """
        LangGraph 節點：工具選擇
        
        根據當前狀態和配置決定使用哪些工具。
        """
        try:
            self.logger.info("tool_selection: 選擇適當的工具")
            
            available_tools = []
            
            # 根據優先級排序工具 - 使用型別安全存取
            tools_by_priority = sorted(
                self.tools_config.items(),
                key=lambda x: x[1].priority
            )
            
            for tool_name, tool_config in tools_by_priority:
                if tool_config.enabled:
                    # 檢查工具是否真的可用
                    if tool_name == "google_search" and self.google_client:
                        available_tools.append(tool_name)
                    elif tool_name != "google_search":
                        available_tools.append(tool_name)
            
            # 決定使用的工具
            selected_tool = None
            if state.needs_tools and available_tools:
                # 簡單策略：選擇第一個可用的工具
                selected_tool = available_tools[0]
            
            self.logger.info(f"tool_selection: 可用工具={available_tools}, 選擇工具={selected_tool}")
            
            return {
                "available_tools": available_tools,
                "selected_tool": selected_tool
            }
            
        except Exception as e:
            self.logger.error(f"tool_selection 失敗: {e}")
            return {"selected_tool": None}
    
    async def execute_tool(self, state: OverallState) -> Dict[str, Any]:
        """
        LangGraph 節點：執行工具
        
        執行選定的工具，內嵌工具邏輯如 Google Search。
        """
        try:
            selected_tool = state.selected_tool
            
            if not selected_tool:
                self.logger.info("execute_tool: 沒有選擇工具，跳過")
                return {
                    "tool_results": [], 
                    "tool_round": state.tool_round + 1
                }
            
            self.logger.info(f"execute_tool: 執行工具 {selected_tool}")
            
            # 計算進度百分比
            current_round = state.tool_round + 1
            max_rounds = self.behavior_config.max_tool_rounds
            progress_percentage = int((current_round / max_rounds) * 50)  # 工具執行佔總進度的50%
            
            # 通知工具執行進度
            tool_names = {
                "google_search": "Google 搜尋",
                "citation": "引用處理"
            }
            tool_display_name = tool_names.get(selected_tool, selected_tool)
            
            await self._notify_progress(
                stage="execute_tool",
                message=f"🔍 正在使用 {tool_display_name} 搜尋資料... (第 {current_round}/{max_rounds} 輪)",
                progress_percentage=progress_percentage,
                current_round=current_round,
                max_rounds=max_rounds,
                tool_name=selected_tool
            )
            
            tool_results = []
            
            if selected_tool == "google_search":
                # 內嵌 Google Search 邏輯
                tool_results = self._execute_google_search(state)
            elif selected_tool == "citation":
                # 內嵌引用處理邏輯
                tool_results = self._execute_citation_tool(state)
            
            # 更新工具使用輪次
            current_round = state.tool_round + 1
            
            self.logger.info(f"execute_tool: 完成，結果數量={len(tool_results)}, 輪次={current_round}")
            # self.logger.info(f"execute_tool: 結果={tool_results}")
            
            
            return {
                "tool_results": tool_results,
                "tool_round": current_round
            }
            
        except Exception as e:
            self.logger.error(f"execute_tool 失敗: {e}")
            return {"tool_results": [], "tool_round": state.tool_round + 1}
    
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
            
            tool_results = state.tool_results
            research_topic = state.research_topic
            
            # 使用專用的反思 LLM 或簡化邏輯
            is_sufficient = self._evaluate_results_sufficiency(tool_results, research_topic)
            
            self.logger.info(f"reflection: 結果充分度={is_sufficient}")
            
            return {
                "is_sufficient": is_sufficient,
                "reflection_complete": True
            }
            
        except Exception as e:
            self.logger.error(f"reflection 失敗: {e}")
            return {"is_sufficient": True}  # 失敗時假設充分
    
    def evaluate_research(self, state: OverallState) -> str:
        """
        LangGraph 路由節點：評估研究進度
        
        決定是否繼續研究或進入最終答案生成。
        """
        try:
            current_round = state.tool_round
            max_rounds = self.behavior_config.max_tool_rounds
            is_sufficient = state.is_sufficient
            
            # 決策邏輯
            if is_sufficient or current_round >= max_rounds:
                self.logger.info(f"evaluate_research: 完成研究 (輪次={current_round}, 充分={is_sufficient})")
                return "finish"
            else:
                self.logger.info(f"evaluate_research: 繼續研究 (輪次={current_round}/{max_rounds})")
                return "continue"
                
        except Exception as e:
            self.logger.error(f"evaluate_research 失敗: {e}")
            return "finish"
    
    def decide_next_step(self, state: OverallState) -> Literal["continue", "finish"]:
        """決定下一步的路由函數"""
        return self.evaluate_research(state)
    
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
            tool_results = state.tool_results or []
            
            # 構建上下文
            context = ""
            if tool_results:
                context = "\n".join([f"搜尋結果: {result}" for result in tool_results])
            
            # 生成最終答案
            try:
                final_answer = self._generate_final_answer(messages, context)
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
    
    # 內部輔助方法
    
    def _analyze_tool_necessity(self, messages: List[MsgNode]) -> bool:
        """分析是否需要使用工具（使用專用 LLM 智能判斷）"""
        if not self.tool_analysis_llm:
            return self._analyze_tool_necessity_fallback(messages)
        
        try:
            # 構建包含所有歷史對話的提示
            messages_for_llm = [SystemMessage(content="""
請分析以下對話歷史，判斷最新一條用戶請求是否需要使用搜尋工具來獲取最新資訊：

判斷標準：
- 最新用戶請求需要最新資訊、即時數據、新聞事件
- 最新用戶請求需要查找特定事實、數據、統計
- 最新用戶請求涉及當前狀況、最新發展
- 最新用戶請求需要驗證或引用外部資源
- 最新用戶請求是之前問題的延伸或補充，且需要搜尋來回答。

請只回答「是」或「否」，不需要解釋。
""")]
            
            for msg in messages:
                if msg.role == "user":
                    messages_for_llm.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages_for_llm.append(AIMessage(content=msg.content))

            response = self.tool_analysis_llm.invoke(messages_for_llm)
            result = response.content.strip().lower()
            
            needs_tools = "是" in result or "yes" in result or "需要" in result
            
            self.logger.info(f"LLM 工具需求判斷 (基於歷史對話): '{messages[-1].content[:50]}...' -> {needs_tools}")
            return needs_tools
            
        except Exception as e:
            self.logger.warning(f"LLM 工具需求判斷失敗，回退到關鍵字檢測: {e}")
            return self._analyze_tool_necessity_fallback(messages)

    def _analyze_tool_necessity_fallback(self, messages: List[MsgNode]) -> bool:
        """關鍵字檢測回退方案 (仍基於最新訊息)"""
        tool_keywords = [
            "搜尋", "查詢", "最新", "現在", "今天", "今年", "查找",
            "資訊", "資料", "新聞", "消息", "更新", "狀況", "search",
            "find", "latest", "current", "recent", "what is", "告訴我"
        ]
        
        content_lower = messages[-1].content.lower()
        return any(keyword in content_lower for keyword in tool_keywords)
    
    def _generate_search_queries(self, messages: List[MsgNode]) -> List[str]:
        """生成搜尋查詢（基於完整對話歷史）"""
        try:
            self.logger.info("生成搜尋查詢（基於完整對話歷史）")
            
            # System instruction for the LLM
            system_instruction = f"""
            今日是 {get_current_date(self.config.system.timezone)}
                你是一個網路搜尋查詢生成器。
                你的任務是根據提供的對話歷史和最新一條用戶請求，生成 1-2 個精確的網路搜尋查詢。
                請確保查詢能涵蓋用戶請求的最新資訊需求。

                輸出格式：
                請直接提供 JSON 格式的搜尋查詢列表。如果沒有需要搜尋的查詢，請回傳一個空的 JSON 列表 `[]`。

                範例：
                [ "查詢一", "查詢二" ]
                或者，如果不需要查詢：
                []
                """
            
            messages_for_llm = [SystemMessage(content=system_instruction)]

            # Add conversation history as individual messages
            # Iterate in chronological order as LLM expects messages in order
            for msg in messages:
                print(msg.role, msg.content[:100])
                if msg.role == "user":
                    messages_for_llm.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages_for_llm.append(AIMessage(content=msg.content))
            
            response = self.tool_analysis_llm.invoke(messages_for_llm)
            raw_content = response.content.strip()
            
            parsed_json = None
            if "```json" in raw_content:
                # Try to extract JSON from markdown code block
                start_marker = "```json"
                end_marker = "```"
                start_index = raw_content.find(start_marker)
                end_index = raw_content.rfind(end_marker)

                if start_index != -1 and end_index != -1 and end_index > start_index:
                    json_str = raw_content[start_index + len(start_marker):end_index].strip()
                    try:
                        if json_str:
                            parsed_json = json.loads(json_str)
                        else:
                            parsed_json = []
                    except json.JSONDecodeError:
                        self.logger.warning(f"無法解析 Markdown 中的 JSON。回應: {raw_content}")
            
            if parsed_json is None and raw_content.startswith("["):
                # Try to parse as direct JSON array
                try:
                    parsed_json = json.loads(raw_content)
                except json.JSONDecodeError:
                    self.logger.warning(f"無法解析為 JSON 列表。回應: {raw_content}")

            if parsed_json is None or not isinstance(parsed_json, list):
                self.logger.warning(f"LLM 生成的搜尋查詢內容為空或格式不正確，回退到簡化模式。回應: {raw_content}")
                return [messages[-1].content[:100]]
            
            queries = parsed_json

            self.logger.info(f"LLM 生成搜尋查詢: {queries}")
            return queries
            
        except Exception as e:
            self.logger.warning(f"LLM 生成搜尋查詢失敗，回退到簡化模式: {e}")
            return [messages[-1].content[:100]]
    
    def _execute_google_search(self, state: OverallState) -> List[str]:
        """執行 Google 搜尋（內嵌實作）"""
        if not self.google_client:
            raise ValueError("Google 客戶端未配置，無法執行 Google 搜尋。")
        
        search_queries = state.search_queries
        self.logger.debug(f"DEBUG: _execute_google_search: search_queries type: {type(search_queries)}, value: {search_queries}")
        results = []
        
        try:
            for query in search_queries[:2]:  # 限制最多2個查詢
                current_date = get_current_date(timezone_str=self.config.system.timezone)
                
                # 準備傳遞給 Gemini 模型的提示
                formatted_prompt = web_searcher_instructions.format(
                    research_topic=query,
                    current_date=current_date
                )
                
                try:
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
                        # 生成一個唯一的 ID 給每個查詢結果，用於 resolve_urls
                        query_id = state.tool_round * 100 + search_queries.index(query) # 確保唯一性
                        
                        # 初始化安全預設值
                        grounding_chunks = []
                        resolved_urls = {} # 確保初始化為空字典
                        citations = []
                        modified_text = response.text

                        # 嘗試提取 grounding_chunks
                        if response.candidates and len(response.candidates) > 0:
                            candidate_0 = response.candidates[0]
                            if candidate_0 and hasattr(candidate_0, 'grounding_metadata') and candidate_0.grounding_metadata:
                                if hasattr(candidate_0.grounding_metadata, 'grounding_chunks') and candidate_0.grounding_metadata.grounding_chunks:
                                    grounding_chunks = candidate_0.grounding_metadata.grounding_chunks

                        # 處理 URL 解析和引用
                        try:
                            resolved_urls = resolve_urls(grounding_chunks, query_id)
                            # 確認這裡沒有對列表類型的檢查，因為 resolved_urls 應為字典
                        except Exception as url_e:
                            self.logger.warning(f"解析 URL 失敗: {url_e}")
                            resolved_urls = {} # 確保重設為空字典

                        try:
                            citations = get_citations(response, resolved_urls)
                            # 確認這裡不再有對列表類型的檢查，因為 get_citations 內部會處理
                        except Exception as cite_e:
                            self.logger.warning(f"獲取引用失敗: {cite_e}")
                            import traceback
                            print(traceback.format_exc())
                            citations = []

                        # 插入引用標記
                        modified_text = insert_citation_markers(response.text, citations)
                        
                        results.append(modified_text)
                    else:
                        results.append(f"針對查詢「{query}」沒有找到內容。")
                except Exception as llm_e:
                    self.logger.error(f"LLM 執行 Google 搜尋失敗: {llm_e}")
                    results.append(f"執行搜尋時發生內部錯誤: {llm_e}")
                
        except Exception as e:
            self.logger.error(f"Google 搜尋失敗: {e}")
        
        return results
    
    def _execute_citation_tool(self, state: OverallState) -> List[str]:
        """執行引用工具（內嵌實作）"""
        tool_results = state.tool_results
        
        # 簡化的引用生成
        citations = []
        for i, result in enumerate(tool_results, 1):
            citation = f"[{i}] {result[:50]}..."
            citations.append(citation)
        
        return citations
    
    def _evaluate_results_sufficiency(self, tool_results: List[str], research_topic: str) -> bool:
        """評估結果是否充分"""
        # 如果沒有工具結果，表示可能沒有合適的工具，認為應該結束
        if not tool_results:
            return True  # 修改：沒有結果時認為充分，避免無限循環
        
        # 如果有結果且長度合理，認為充分
        total_length = sum(len(result) for result in tool_results)
        return total_length > 20  # 至少20字符的結果
    
    def _generate_final_answer(self, messages: List[MsgNode], context: str) -> str:
        """生成最終答案（使用專用 LLM）"""
        if not messages:
            return "嗯...好像沒有收到你的訊息耶，可以再試一次嗎？😅"
        
        latest_message = messages[-1]
        user_question = latest_message.content
        
        # 不管有沒有context，都用LLM生成更自然的回應
        try:
            # 構建所有歷史對話的訊息列表，除了當前用戶問題

            if context:
                messages_for_final_answer = [SystemMessage(
                    content=f"""
                    你是一個友善、聰明的聊天助手。請用自然、人性化的方式回答用戶的問題。
                    以下是你使用工具得到的相關資訊，請用於回答用戶的問題：
                    {context}
                    """
                )]
            else:
                messages_for_final_answer = [SystemMessage(content="你是一個友善、聰明的聊天助手。請用自然、人性化的方式回答用戶的問題。")]
                
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