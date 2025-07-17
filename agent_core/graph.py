"""
統一的 LangGraph 圖實作

根據配置動態構建 LangGraph 的 StateGraph，定義所有節點的實現，
包括工具邏輯的直接內嵌。嚴格參考 reference_arch.md 中定義的 Agent 核心流程。
"""

import asyncio
import logging
import json
import copy
import re
import uuid
from typing import Dict, Any, List, Optional, Literal, Union
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langchain_core.runnables import RunnableConfig
from google.genai import Client

from schemas.agent_types import OverallState, MsgNode, ToolPlan, AgentPlan, ToolExecutionState, ReminderDetails, ToolExecutionResult
from utils.config_loader import load_typed_config
from .progress_types import ProgressStage, ToolStatus
from prompt_system.prompts import get_current_date, PromptSystem
from schemas.config_types import AppConfig
from .progress_mixin import ProgressMixin
from .agent_utils import _extract_text_content

# 導入 LangChain 工具
from tools import GoogleSearchTool, set_reminder
from tools.youtube_summary import YouTubeSummaryTool
from utils.youtube_utils import extract_first_youtube_url
from langchain_core.messages import ToolMessage


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
        
        # 初始化進度 LLM
        self._progress_llm = self.llm_instances.get("progress_msg")
        
        # 初始化並綁定 LangChain 工具
        self._initialize_tools()
    
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
                max_output_tokens = llm_config.max_output_tokens
                
                # 準備 LLM 參數
                llm_params = {
                    "model": model_name,
                    "temperature": temperature,
                    "api_key": api_key
                }
                
                # 如果設置了 max_output_tokens 且為有效值，則添加到參數中
                if max_output_tokens is not None and max_output_tokens > 0:
                    llm_params["max_output_tokens"] = max_output_tokens
                
                llm_instances[purpose] = ChatGoogleGenerativeAI(**llm_params)
                self.logger.info(f"初始化 {purpose} LLM: {model_name} (max_tokens: {max_output_tokens})")
            except Exception as e:
                self.logger.warning(f"初始化 {purpose} LLM 失敗: {e}")
                llm_instances[purpose] = None
        
        self.tool_analysis_llm: ChatGoogleGenerativeAI = llm_instances.get("tool_analysis")
        self.final_answer_llm: ChatGoogleGenerativeAI = llm_instances.get("final_answer")
        
        return llm_instances
    
    def _initialize_tools(self):
        """初始化並綁定 LangChain 工具到 LLM"""
        self.available_tools = []
        self.tool_mapping = {}
        
        # 初始化 Google 搜尋工具（如果啟用）
        if self.config.is_tool_enabled("google_search") and self.google_client:
            self.google_search_tool = GoogleSearchTool(
                google_client=self.google_client,
                prompt_system_instance=self.prompt_system,
                config=self.config,
                logger=self.logger
            )
            self.available_tools.append(self.google_search_tool)
            self.tool_mapping[self.google_search_tool.name] = self.google_search_tool
            self.logger.info("已初始化 Google 搜尋工具")
        
        # 初始化提醒工具（如果啟用）
        if self.config.is_tool_enabled("reminder"):
            self.available_tools.append(set_reminder)
            self.tool_mapping[set_reminder.name] = set_reminder
            self.logger.info("已初始化提醒工具")

        # 初始化 YouTube 摘要工具（僅加入 mapping，不綁定給 LLM）
        if self.config.is_tool_enabled("youtube_summary") and self.google_client:
            self.youtube_summary_tool = YouTubeSummaryTool(
                google_client=self.google_client,
                config=self.config,
                logger=self.logger
            )
            # 不加入 self.available_tools 以避免暴露給 LLM
            self.tool_mapping[self.youtube_summary_tool.name] = self.youtube_summary_tool
            self.logger.info("已初始化 YouTube 摘要工具")
        
        # 綁定工具到 tool_analysis_llm
        if self.available_tools and self.tool_analysis_llm:
            self.tool_analysis_llm = self.tool_analysis_llm.bind_tools(self.available_tools)
            self.logger.info(f"已綁定 {len(self.available_tools)} 個工具到 LLM")
        else:
            if not self.tool_analysis_llm:
                self.logger.warning("tool_analysis_llm 未初始化，無法綁定工具")
            elif not self.available_tools:
                self.logger.warning("沒有可用的工具，使用未綁定工具的 LLM")
    
    async def _build_agent_messages_for_progress(self, stage: str, current_state) -> List:
        """Agent 只處理 Agent 特有資訊
        
        Args:
            stage: 進度階段
            current_state: 當前狀態
            
        Returns:
            List[BaseMessage]: Agent 構建的 messages
        """
        from langchain_core.messages import BaseMessage
        
        if not current_state:
            return []
        
        # 1. 獲取前10則消息
        recent_msg_nodes = current_state.messages[-10:] if current_state.messages else []
        
        # 2. 使用固定 persona 構建 system prompt
        system_prompt = self.prompt_system.get_system_instructions(
            self.config, persona=current_state.current_persona
        )
        
        # 3. 構建 messages
        messages = self._build_messages_for_llm(recent_msg_nodes, system_prompt)
        
        return messages
    
    def build_graph(self) -> StateGraph:
        """建立簡化的 LangGraph"""
        builder = StateGraph(OverallState)
        
        # 核心節點
        builder.add_node("generate_query_or_plan", self.generate_query_or_plan)
        builder.add_node("execute_tools", self.execute_tools_node)
        builder.add_node("reflection", self.reflection)
        builder.add_node("finalize_answer", self.finalize_answer)
        
        # 流程設置
        builder.add_edge(START, "generate_query_or_plan")
        
        # 條件路由：根據計劃決定下一步
        builder.add_conditional_edges(
            "generate_query_or_plan",
            self.route_and_dispatch_tools,
            {
                "execute_tools": "execute_tools",
                "direct_answer": "finalize_answer"
            }
        )
        
        # Connect dispatch node to reflection
        builder.add_edge("execute_tools", "reflection")
        
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

    async def generate_query_or_plan(self, state: OverallState) -> Dict[str, Any]:
        """
        統一的計劃生成節點：使用 LangChain 工具綁定的 LLM 進行分析
        
        LLM 會自動決定是否需要調用工具，並生成相應的 tool_calls
        """
        try:
            self.logger.info("generate_query_or_plan: 開始分析用戶請求")
            
            # ★ 新增：確定 current_persona（在第一個節點處理）
            if not state.current_persona:
                if self.config.prompt_system.persona.random_selection:
                    state.current_persona = self.prompt_system.get_random_persona_name()
                else:
                    state.current_persona = self.config.prompt_system.persona.default_persona
            
            # 通知開始階段
            await self._notify_progress(
                stage=ProgressStage.GENERATE_QUERY, 
                message="",
                progress_percentage=30,
                current_state=state
            )
            
            user_content = _extract_text_content(state.messages[-1].content)
            max_tool_rounds = self.behavior_config.max_tool_rounds
            
            if max_tool_rounds == 0:
                # 純對話模式
                return {
                    "agent_plan": AgentPlan(needs_tools=False),
                    "tool_round": 0
                }
            
            # 檢測 YouTube URL，若有則預備一個程式化工具調用 (稍後與 LLM 結果合併)
            youtube_tool_call = None

            # 在最近 10 則訊息內尋找第一個 YouTube URL（由近到遠）
            yt_url = None
            recent_msgs = state.messages[-10:]
            for m in reversed(recent_msgs):
                text_part = _extract_text_content(m.content)
                hit = extract_first_youtube_url(text_part)
                if hit:
                    yt_url = hit
                    break

            if yt_url and self.config.is_tool_enabled("youtube_summary"):
                self.logger.info(f"偵測到 YouTube URL: {yt_url}，將加入 youtube_summary 工具調用 (稍後合併)")

                youtube_tool_call = {
                    "id": str(uuid.uuid4()),
                    "name": self.youtube_summary_tool.name,
                    "args": {"url": yt_url}
                }
            
            # 使用綁定工具的 LLM 進行分析
            if not self.tool_analysis_llm:
                # 回退到簡單邏輯
                needs_tools = self._analyze_tool_necessity_fallback(state.messages)
                agent_plan = AgentPlan(
                    needs_tools=needs_tools,
                    reasoning="LLM 未可用，使用簡化邏輯決策"
                )
            else:
                # system_prompt = ""
                system_prompt = self._build_planning_system_prompt(state.messages_global_metadata)
                messages_for_llm = self._build_messages_for_llm(state.messages, system_prompt)
                self._log_messages(messages_for_llm, "messages_for_llm (planning)")
                ai_message = await self.tool_analysis_llm.ainvoke(messages_for_llm)
                
                # 檢查是否有工具調用
                if ai_message.tool_calls or youtube_tool_call:
                    # 有工具調用，需要執行工具
                    combined_tool_calls = list(ai_message.tool_calls) if ai_message.tool_calls else []
                    if youtube_tool_call:
                        # 將 YouTube 摘要工具放在最前面，避免與其它工具衝突
                        combined_tool_calls.insert(0, youtube_tool_call)

                    logging.debug(f"最終 tool_calls: {combined_tool_calls}")

                    agent_plan = AgentPlan(
                        needs_tools=True,
                        reasoning="LLM 決定調用工具" + ("，並加入 YouTube 摘要" if youtube_tool_call else "")
                    )

                    # 將 combined_tool_calls 存儲在 state 中供後續節點使用
                    state.metadata = state.metadata or {}
                    state.metadata["pending_tool_calls"] = combined_tool_calls
                    
                    # 保存 AI 訊息和工具調用到對話歷史
                    state.messages.append(MsgNode(
                        role="assistant",
                        content=ai_message.content or "",
                        metadata={"tool_calls": combined_tool_calls}
                    ))
                else:
                    # 沒有工具調用，直接回答
                    agent_plan = AgentPlan(
                        needs_tools=False,
                        reasoning="LLM 決定直接回答，無需工具"
                    )
            
            self.logger.info(f"生成計劃: 需要工具={agent_plan.needs_tools}")
            
            return {
                "agent_plan": agent_plan,
                "tool_round": state.tool_round + 1,
                "research_topic": user_content,
                "metadata": state.metadata,
                "messages": state.messages,
            }
            
        except Exception as e:
            self.logger.error(f"generate_query_or_plan 失敗: {e}")
            return {
                "agent_plan": AgentPlan(needs_tools=False),
                "finished": True
            }

    def route_and_dispatch_tools(self, state: OverallState) -> str:
        """
        規劃後的路由決策：
        檢查是否需要執行工具
        """
        agent_plan = state.agent_plan
        
        if agent_plan and agent_plan.needs_tools:
            # 檢查是否有待執行的工具調用
            pending_tool_calls = state.metadata.get("pending_tool_calls") if state.metadata else None
            if pending_tool_calls:
                self.logger.info(f"route_and_dispatch_tools: 需要執行 {len(pending_tool_calls)} 個工具")
                return "execute_tools"
            else:
                self.logger.error("route_and_dispatch_tools: 計劃需要工具但沒有待執行的工具調用")
                return "direct_answer"
        else:
            self.logger.info("route_and_dispatch_tools: 無需工具，直接回答")
            return "direct_answer"

    async def execute_tools_node(self, state: OverallState) -> Dict[str, Any]:
        """執行 LangChain 工具調用"""
        try:
            # 獲取待執行的工具調用
            pending_tool_calls = state.metadata.get("pending_tool_calls") if state.metadata else None
            if not pending_tool_calls:
                self.logger.warning("execute_tools_node: 沒有待執行的工具調用")
                return {"tool_results": []}
            
            self.logger.info(f"execute_tools_node: 平行執行 {len(pending_tool_calls)} 個工具調用")

            # Phase3: 先通知工具清單 (todo list)
            try:
                await self._notify_progress(
                    stage=ProgressStage.TOOL_LIST,
                    message="🛠️ 工具進度",
                    todo=[tc["name"] for tc in pending_tool_calls],
                    current_state=state
                )
            except Exception as e:
                self.logger.warning(f"發送工具清單進度失敗: {e}")

            # 通知工具執行階段
            await self._notify_progress(
                stage=ProgressStage.TOOL_EXECUTION,
                message="",  # 使用配置中的訊息
                progress_percentage=50,
                current_state=state
            )
            
            # 創建平行執行的任務
            tasks = []
            for tool_call in pending_tool_calls:
                task = self._execute_single_tool_call(tool_call)
                tasks.append(task)
            
            # 平行執行所有工具調用
            tool_results_with_messages = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 處理結果
            new_tool_messages: List[ToolMessage] = []
            tool_results: List[str] = []
            
            for i, result in enumerate(tool_results_with_messages):
                tool_call = pending_tool_calls[i]
                tool_call_id = tool_call["id"]
                tool_name = tool_call["name"]
                state_update_dict = {}
                if isinstance(result, Exception):
                    # 處理異常
                    self.logger.error(f"工具 {tool_name} 執行異常: {result}")
                    error_msg = f"工具執行異常: {str(result)}"
                    tool_message = ToolMessage(
                        content=error_msg,
                        tool_call_id=tool_call_id
                    )
                    new_tool_messages.append(tool_message)
                    tool_results.append(error_msg)
                else:
                    # 正常結果
                    tool_message, tool_execution_result = result
                    new_tool_messages.append(tool_message)
                    tool_results.append(tool_execution_result.message)
                    
                    # 特別處理 set_reminder 工具的成功結果
                    if tool_name == "set_reminder" and tool_execution_result.success:
                        state_update_dict.update(await self._process_reminder_result(state, tool_execution_result))
            
            # 將 ToolMessage 轉換為 MsgNode 並添加到對話歷史
            for tool_msg in new_tool_messages:
                state.messages.append(MsgNode(
                    role="tool",
                    content=tool_msg.content,
                    metadata={"tool_call_id": tool_msg.tool_call_id}
                ))
            
            # 清除已執行的工具調用
            if state.metadata:
                state.metadata.pop("pending_tool_calls", None)
            
            self.logger.info(f"平行執行完成，共處理 {len(tool_results)} 個工具結果")
            
            return {
                "tool_results": tool_results,
                "metadata": state.metadata,
                "messages": state.messages,
            } | state_update_dict # Merge state_update_dict into the return dict
            
        except Exception as e:
            self.logger.error(f"execute_tools_node 失敗: {e}")
            return {
                "tool_results": [],
                "error": str(e)
            }
    
    async def _execute_single_tool_call(self, tool_call: Dict[str, Any]) -> tuple[ToolMessage, ToolExecutionResult]:
        """執行單個工具調用 - 用於平行執行"""
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call["id"]
        
        self.logger.info(f"執行工具: {tool_name} with args: {tool_args}")

        # Phase3: 工具狀態 - running
        try:
            await self._notify_progress(
                stage=ProgressStage.TOOL_STATUS,
                message="",  # 使用配置訊息
                progress_percentage=50,  # 保持進度條
                tool=tool_name,
                status=ToolStatus.RUNNING
            )
        except Exception as e:
            self.logger.warning(f"通知工具 {tool_name} 執行中 狀態失敗: {e}")
        
        try:
            # 查找對應的工具
            selected_tool = self.tool_mapping.get(tool_name)
            if not selected_tool:
                error_result = ToolExecutionResult(
                    success=False,
                    message=f"錯誤：找不到工具 '{tool_name}'"
                )
                tool_message = ToolMessage(
                    content=error_result.message,
                    tool_call_id=tool_call_id
                )
                # Phase3: 工具狀態 - error
                try:
                    await self._notify_progress(
                        stage=ProgressStage.TOOL_STATUS,
                        message="",  # 使用配置訊息
                        progress_percentage=50,  # 保持進度條
                        tool=tool_name,
                        status=ToolStatus.ERROR
                    )
                except Exception as ne:
                    self.logger.warning(f"通知工具 {tool_name} error 狀態失敗: {ne}")
                return tool_message, error_result
            
            # 執行工具
            if hasattr(selected_tool, 'ainvoke'):
                raw_result = await selected_tool.ainvoke(tool_args)
            elif hasattr(selected_tool, 'invoke'):
                raw_result = selected_tool.invoke(tool_args)
            else:
                if asyncio.iscoroutinefunction(selected_tool):
                    raw_result = await selected_tool(**tool_args)
                else:
                    raw_result = selected_tool(**tool_args)
            
            # 處理工具結果
            if isinstance(raw_result, ToolExecutionResult):
                tool_execution_result = raw_result
            else:
                # 如果是字串，嘗試解析為 ToolExecutionResult
                try:
                    import json
                    result_data = json.loads(raw_result)
                    tool_execution_result = ToolExecutionResult(**result_data)
                except (json.JSONDecodeError, TypeError, ValueError):
                    # 如果解析失敗，創建一個簡單的成功結果
                    tool_execution_result = ToolExecutionResult(
                        success=True,
                        message=str(raw_result)
                    )
            print(tool_execution_result)
            # 創建 ToolMessage
            tool_message = ToolMessage(
                content=tool_execution_result.message,
                tool_call_id=tool_call_id
            )
            
            # Phase3: 工具狀態 - completed
            try:
                await self._notify_progress(
                    stage=ProgressStage.TOOL_STATUS,
                    message="",  # 使用配置訊息
                    progress_percentage=50,  # 保持進度條
                    tool=tool_name,
                    status=ToolStatus.COMPLETED
                )
            except Exception as ce:
                self.logger.warning(f"通知工具 {tool_name} completed 狀態失敗: {ce}")

            return tool_message, tool_execution_result
                
        except Exception as e:
            self.logger.error(f"執行工具 {tool_name} 時發生錯誤: {e}")
            error_result = ToolExecutionResult(
                success=False,
                message=f"工具執行錯誤: {str(e)}"
            )
            tool_message = ToolMessage(
                content=error_result.message,
                tool_call_id=tool_call_id
            )
            # Phase3: 工具狀態 - error
            try:
                await self._notify_progress(
                    stage=ProgressStage.TOOL_STATUS,
                    message="",  # 使用配置訊息
                    progress_percentage=50,  # 保持進度條
                    tool=tool_name,
                    status=ToolStatus.ERROR
                )
            except Exception as ne:
                self.logger.warning(f"通知工具 {tool_name} error 狀態失敗: {ne}")
            return tool_message, error_result

    async def _process_reminder_result(self, state: OverallState, tool_execution_result: ToolExecutionResult):
        """從 ToolExecutionResult 處理提醒工具的執行結果"""
        try:
            if tool_execution_result.success and tool_execution_result.data:
                # 提取 ReminderDetails
                reminder_data = tool_execution_result.data.get("reminder_details")
                if reminder_data:
                    # 確保包含 msg_id 欄位，如果沒有則設為空字串
                    logging.debug(f"reminder_data: {reminder_data}")
                    if "msg_id" not in reminder_data:
                        reminder_data["msg_id"] = ""
                    reminder_details = ReminderDetails(**reminder_data)
                    # 添加到 state 的 reminder_requests
                    if not hasattr(state, "reminder_requests") or state.reminder_requests is None:
                        state.reminder_requests = []
                    state.reminder_requests.append(reminder_details)
                    
                    self.logger.info(f"成功處理提醒請求: {reminder_details.message}")
            return {"reminder_requests": state.reminder_requests}
                    
        except (KeyError, TypeError) as e:
            self.logger.error(f"處理提醒結果時發生錯誤: {e}")
            return {}

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
                stage=ProgressStage.REFLECTION,
                message="",  # 使用配置中的訊息
                progress_percentage=75,
                current_state=state
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
                self.logger.info(f"決定完成研究 (輪次={current_round}/{max_rounds}, 充分={is_sufficient})")
                return "finish"
            else:
                self.logger.info(f"決定繼續研究 (輪次={current_round}/{max_rounds})")
                return "continue"
                
        except Exception as e:
            self.logger.error(f"decide_next_step 失敗: {e}")
            return "finish"

    def _build_planning_system_prompt(self, messages_global_metadata: str = "") -> str:
        """構建最終答案的系統提示詞
        
        Args:
            context: 工具結果上下文
            messages_global_metadata: 全域訊息元數據
            
        Returns:
            str: 完整的系統提示詞
        """
        # 使用 PromptSystem 構建基礎系統提示詞
        
        context_prompt = self.prompt_system.get_tool_prompt(
            "planning_instructions"
        )
        system_prompt = self.prompt_system.get_system_instructions(
            config=self.config,
            messages_global_metadata=context_prompt + "\n\n" + messages_global_metadata
        )
        return system_prompt
            

    def _build_final_system_prompt(self, context: str, messages_global_metadata: str) -> str:
        """構建最終答案的系統提示詞
        
        Args:
            context: 工具結果上下文
            messages_global_metadata: 全域訊息元數據
            
        Returns:
            str: 完整的系統提示詞
        """
        try:
            # 使用 PromptSystem 構建基礎系統提示詞
            base_system_prompt = self.prompt_system.get_system_instructions(
                config=self.config,
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
                    context_prompt = f"以下是相關資訊：\n{context}\n請基於以上資訊回答。"
                    full_system_prompt = base_system_prompt + "\n\n" + context_prompt
            else:
                full_system_prompt = base_system_prompt
            
            return full_system_prompt
            
        except Exception as e:
            self.logger.error(f"構建最終系統提示詞失敗: {e}")
            # 回退到簡單的系統提示詞
            fallback_prompt = f"你是一個有用的助手。請根據提供的資訊回答用戶的問題。由於流程出現錯誤，請提醒一下用戶 {e}。"
            if context:
                fallback_prompt += f"\n\n以下是相關資訊：\n{context}\n請基於以上資訊回答。"
            return fallback_prompt

    def _build_messages_for_llm(self, messages: List[MsgNode], system_prompt: str) -> List:
        """構建用於 LLM 的訊息列表
        
        Args:
            messages: 原始訊息列表
            system_prompt: 系統提示詞
            
        Returns:
            List: LangChain 格式的訊息列表
        """
        try:
            # 構建訊息列表
            messages_for_llm = [SystemMessage(content=system_prompt)]
            
            for msg in messages:
                if msg.role == "user":
                    messages_for_llm.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    # 檢查是否有 tool_calls
                    tool_calls = msg.metadata.get("tool_calls") if msg.metadata else None
                    if tool_calls:
                        ai_msg = AIMessage(content=msg.content, tool_calls=tool_calls)
                    else:
                        ai_msg = AIMessage(content=msg.content)
                    messages_for_llm.append(ai_msg)
                elif msg.role == "tool":
                    # 使用正確的 ToolMessage 格式
                    tool_call_id = msg.metadata.get("tool_call_id") if msg.metadata else None
                    if tool_call_id:
                        messages_for_llm.append(ToolMessage(
                            content=msg.content,
                            tool_call_id=str(tool_call_id)
                        ))
                    else:
                        # 如果沒有 tool_call_id，記錄錯誤但不中斷
                        self.logger.warning(f"Tool message without tool_call_id: {msg.content}")
                        messages_for_llm.append(HumanMessage(content="Tool Result: " + msg.content))
            
            return messages_for_llm
            
        except Exception as e:
            self.logger.error(f"構建 LLM 訊息列表失敗: {e}")
            # 回退到簡單的訊息格式
            fallback_content = _extract_text_content(messages[-1].content) if messages else "請回答用戶的問題。"
            return [
                SystemMessage(content=system_prompt),
                HumanMessage(content=fallback_content)
            ]

    async def finalize_answer(self, state: OverallState) -> Dict[str, Any]:
        """
        LangGraph 節點：生成最終答案（支援串流）
        
        基於所有可用的信息生成最終回答，特別處理提醒相關的回覆。
        """
        try:
            self.logger.info("finalize_answer: 生成最終答案")
            
            # 通知答案生成階段
            # 檢查是否有成功的提醒請求
            if state.reminder_requests:
                self.logger.info("finalize_answer: 確認提醒完成")
                
                # 通知完成
                await self._notify_progress(
                    stage=ProgressStage.COMPLETED,
                    message="✅ 提醒設定完成！",
                    progress_percentage=90,
                    current_state=state
                )
            
            await self._notify_progress(
                stage=ProgressStage.FINALIZE_ANSWER,
                message="",  # 使用配置中的訊息
                progress_percentage=90,
                current_state=state
            )
            
            messages = state.messages
            tool_results = state.aggregated_tool_results or state.tool_results or []
            
            # 構建上下文
            context = ""
            if tool_results:
                context = "\n".join([f"搜尋結果: {result}" for result in tool_results])
            
            # 構建系統提示詞和訊息列表
            system_prompt = self._build_final_system_prompt(context, state.messages_global_metadata)
            messages_for_llm = self._build_messages_for_llm(messages, system_prompt)
            
            self._log_messages(messages_for_llm, "messages_for_llm (finalize_answer)")
            
            # 檢查串流配置

            final_answer = ""
            
            if self.config.streaming.enabled:
                self.logger.info("finalize_answer: 啟用串流回應")
                
                try:
                    # 使用 LLM 串流生成答案
                    final_answer_chunks = []
                    async for chunk in self.final_answer_llm.astream(messages_for_llm):
                        content = chunk.content or ""
                        if content:  # 只處理有內容的 chunk
                            final_answer_chunks.append(content)
                            # 通知串流塊，最後一個 chunk 通常內容為空，用來標示結束
                            is_final = len(content) == 0
                            await self._notify_streaming_chunk(content, is_final=is_final)
                    
                    # 組合完整答案
                    final_answer = "".join(final_answer_chunks)
                    
                    # 通知串流完成
                    await self._notify_streaming_complete()
                    
                except Exception as e:
                    self.logger.warning(f"串流生成失敗，回退到同步模式: {e}")
                    # 回退到同步模式
                    final_answer = self.final_answer_llm.invoke(messages_for_llm).content
                    
            else:
                self.logger.info("finalize_answer: 未啟用串流或無觀察者，使用一般回應")
                # 生成完整答案（非串流）
                try:
                    # 直接使用 LLM invoke
                    response = self.final_answer_llm.invoke(messages_for_llm)
                    final_answer = response.content
                except Exception as e:
                    self.logger.warning(f"LLM 答案生成失敗，使用基本回覆: {e}")
                    final_answer = self._generate_basic_fallback_answer(messages, context)
                
                # 通知完成（非串流模式）
                await self._notify_progress(
                    stage=ProgressStage.COMPLETED,
                    message="✅ 回答完成！",
                    progress_percentage=100,
                    current_state=state
                )
            
            if state.reminder_requests:
                final_answer = final_answer + "\n" + "✅ 提醒設定完成！"
                
            if final_answer == "":
                final_answer = "✅ 回答完成！ (Agent 無言了)"
                
            self.logger.info("finalize_answer: 答案生成完成")
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

    def _analyze_tool_necessity_fallback(self, messages: List[MsgNode]) -> bool:
        """關鍵字檢測回退方案 (仍基於最新訊息)"""
        tool_keywords = [
            "搜尋", "查詢", "最新", "現在", "今天", "今年", "查找",
            "資訊", "資料", "新聞", "消息", "更新", "狀況", "search",
            "find", "latest", "current", "recent", "what is", "告訴我",
            "網路搜尋", "網路研究"
        ]
        
        # 安全地提取文字內容
        user_text = _extract_text_content(messages[-1].content)
        content_lower = user_text.lower()
        return any(keyword in content_lower for keyword in tool_keywords)

    def _evaluate_results_sufficiency(self, tool_results: List[str], research_topic: str) -> bool:
        """評估結果是否充分"""
        # 重構後簡化邏輯：總是認為結果充分，避免無限循環
        # 實際的輪次控制由 max_tool_rounds 來處理
        return True

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

    def _log_messages(self, messages_for_llm: List[Any], context_message: str = "messages_for_llm"):
        """Helper function to log messages, truncating image data."""
        if not messages_for_llm or len(messages_for_llm) < 2:
            logging.debug(f"{context_message} (raw): {messages_for_llm}")
            return
        try:
            # The first message is always SystemMessage, which we don't usually need to log repeatedly.
            loggable_messages = copy.deepcopy(messages_for_llm)
            for msg in loggable_messages:
                # HumanMessage content can be a list of parts
                if isinstance(msg.content, list):
                    for part in msg.content:
                        if isinstance(part, dict) and part.get("type") == "image_url":
                            image_url_content = part.get("image_url")
                            if isinstance(image_url_content, dict):
                                url = image_url_content.get("url", "")
                                if isinstance(url, str) and url.startswith("data:image"):
                                    image_url_content["url"] = f"{url[:50]}...[TRUNCATED]"
                            elif isinstance(image_url_content, str) and image_url_content.startswith("data:image"):
                                part["image_url"] = f"{image_url_content[:50]}...[TRUNCATED]"

            # Log all messages starting from the second one (skip system prompt)
            logging.debug(f"{context_message}: {loggable_messages[1:]}")
        except Exception as e:
            logging.warning(f"Could not format messages for logging: {e}")
            # Log raw messages if formatting fails, also skipping system prompt
            logging.debug(f"{context_message} (raw): {messages_for_llm[1:]}")


def create_unified_agent(config: Optional[AppConfig] = None) -> UnifiedAgent:
    """建立統一 Agent 實例"""
    return UnifiedAgent(config)


def create_agent_graph(config: Optional[AppConfig] = None) -> StateGraph:
    """建立並編譯 Agent 圖"""
    agent = create_unified_agent(config)
    return agent.build_graph() 