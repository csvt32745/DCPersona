"""
LangGraph 研究代理

基於 gemini-fullstack-langgraph-quickstart 的圖結構，
適配到 Discord 環境並添加即時進度回饋和錯誤處理。
"""

import os
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

import discord
from langchain_core.messages import AIMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.types import Send
from langgraph.graph import StateGraph, START, END
from langgraph.graph import add_messages
from langchain_core.runnables import RunnableConfig
from google.genai import Client

from .state import (
    OverallState, 
    ReflectionState, 
    QueryGenerationState, 
    WebSearchState,
    DiscordContext,
    ResearchProgress,
    create_initial_state
)
from .configuration import AgentConfiguration
from .prompts import (
    get_current_date,
    query_writer_instructions,
    web_searcher_instructions,
    reflection_instructions,
    answer_instructions,
    get_progress_message
)
from .tools_and_schemas import (
    SearchQueryList, 
    Reflection,
    DiscordTools,
    ErrorHandler,
    DataValidator
)
from .utils import (
    get_citations,
    get_research_topic,
    insert_citation_markers,
    resolve_urls,
    clean_and_truncate_text,
    format_time_elapsed
)


class ResearchAgent:
    """LangGraph 研究代理主類別"""
    
    def __init__(self, config: AgentConfiguration):
        """
        初始化研究代理
        
        Args:
            config: Agent 配置
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 驗證必要的 API 金鑰
        is_valid, message = config.validate_api_keys()
        if not is_valid:
            self.logger.warning(f"API 金鑰驗證失敗: {message}")
        
        # 初始化 Gemini 客戶端
        if config.gemini_api_key:
            os.environ["GEMINI_API_KEY"] = config.gemini_api_key
            self.genai_client = Client(api_key=config.gemini_api_key)
        else:
            self.genai_client = None
            self.logger.warning("Gemini API 金鑰未設置，無法使用網路搜尋功能")
        
        # 建立 LangGraph
        self.graph = self._build_graph()
        
        # 進度追蹤
        self.current_progress = {}
    
    def _build_graph(self) -> StateGraph:
        """建立 LangGraph 圖結構"""
        builder = StateGraph(OverallState, config_schema=AgentConfiguration)
        
        # 定義節點
        builder.add_node("generate_query", self._generate_query)
        builder.add_node("web_research", self._web_research)
        builder.add_node("reflection", self._reflection)
        builder.add_node("finalize_answer", self._finalize_answer)
        
        # 設置入口點
        builder.add_edge(START, "generate_query")
        
        # 添加條件邊緣
        builder.add_conditional_edges(
            "generate_query", 
            self._continue_to_web_research, 
            ["web_research"]
        )
        
        builder.add_edge("web_research", "reflection")
        
        builder.add_conditional_edges(
            "reflection", 
            self._evaluate_research, 
            ["web_research", "finalize_answer"]
        )
        
        builder.add_edge("finalize_answer", END)
        
        return builder.compile(name="discord-research-agent")
    
    async def process_research_request(
        self,
        discord_ctx: DiscordContext,
        user_message: str,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        處理研究請求
        
        Args:
            discord_ctx: Discord 上下文
            user_message: 使用者訊息
            progress_callback: 進度回調函式
            
        Returns:
            Dict: 研究結果
        """
        start_time = datetime.now()
        session_id = discord_ctx.session_id
        
        try:
            # 驗證查詢
            is_valid, error_msg = DataValidator.validate_search_query(user_message)
            if not is_valid:
                return self._create_error_result("invalid_query", error_msg)
            
            # 創建初始狀態
            initial_state = create_initial_state(discord_ctx, user_message, self.config)
            
            # 初始化進度追蹤
            progress = ResearchProgress(stage="generate_query")
            self.current_progress[session_id] = progress
            
            # 發送初始進度訊息
            if progress_callback:
                await progress_callback(progress)
            
            # 創建配置
            config = RunnableConfig(
                configurable=self.config.model_dump(exclude_none=True)
            )
            
            # 執行研究流程（帶超時）
            result = await asyncio.wait_for(
                self._run_research_graph(initial_state, config, session_id, progress_callback),
                timeout=self.config.timeout_seconds
            )
            
            # 計算執行時間
            execution_time = format_time_elapsed(start_time)
            
            # 完成進度
            progress.stage = "completed"
            self.current_progress[session_id] = progress
            if progress_callback:
                await progress_callback(progress)
            
            return {
                "success": True,
                "result": result,
                "execution_time": execution_time,
                "session_id": session_id,
                "sources_count": len(result.get("sources_gathered", [])),
            }
            
        except asyncio.TimeoutError:
            self.logger.warning(f"研究請求超時: {session_id}")
            progress.stage = "timeout"
            if progress_callback:
                await progress_callback(progress)
            
            return self._create_error_result("timeout", "研究請求超時")
            
        except Exception as e:
            self.logger.error(f"研究過程發生錯誤: {str(e)}", exc_info=True)
            progress.stage = "error"
            if progress_callback:
                await progress_callback(progress)
            
            return self._create_error_result("unknown", str(e))
        
        finally:
            # 清理進度追蹤
            self.current_progress.pop(session_id, None)
            
            # 清理頻道的進度消息記錄（如果有的話）
            if discord_ctx and hasattr(discord_ctx, 'channel_id'):
                DiscordTools.cleanup_progress_messages(discord_ctx.channel_id)
    
    async def _run_research_graph(
        self,
        initial_state: OverallState,
        config: RunnableConfig,
        session_id: str,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """執行研究圖流程"""
        # 這裡需要實際執行 LangGraph
        # 由於 LangGraph 的 invoke 方法通常是同步的，我們需要在執行器中運行它
        loop = asyncio.get_event_loop()
        
        def run_sync():
            return self.graph.invoke(initial_state, config)
        
        # 在線程池中執行同步的圖調用
        result = await loop.run_in_executor(None, run_sync)
        return result
    
    def _generate_query(self, state: OverallState, config: RunnableConfig) -> QueryGenerationState:
        """LangGraph 節點：生成搜尋查詢"""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            # 檢查自定義初始搜尋查詢數量
            if state.get("initial_search_query_count") is None:
                state["initial_search_query_count"] = configurable.number_of_initial_queries
            
            # 初始化 Gemini 模型
            llm = ChatGoogleGenerativeAI(
                model=configurable.query_generator_model,
                temperature=1.0,
                max_retries=2,
                api_key=self.config.gemini_api_key,
            )
            structured_llm = llm.with_structured_output(SearchQueryList)
            
            # 格式化提示
            current_date = get_current_date()
            formatted_prompt = query_writer_instructions.format(
                current_date=current_date,
                research_topic=get_research_topic(state["messages"]),
                number_queries=state["initial_search_query_count"],
            )
            
            # 生成搜尋查詢
            result = structured_llm.invoke(formatted_prompt)
            
            # 更新進度
            session_id = state.get("session_id")
            if session_id and session_id in self.current_progress:
                progress = self.current_progress[session_id]
                progress.stage = "web_research"
                progress.total_queries = len(result.query)
            
            return {"query_list": [{"query": q, "rationale": result.rationale} for q in result.query]}
            
        except Exception as e:
            self.logger.error(f"查詢生成失敗: {str(e)}")
            raise
    
    def _continue_to_web_research(self, state: QueryGenerationState):
        """LangGraph 節點：將搜尋查詢發送到網路研究節點"""
        return [
            Send("web_research", {"search_query": query_info["query"], "id": int(idx)})
            for idx, query_info in enumerate(state["query_list"])
        ]
    
    def _web_research(self, state: WebSearchState, config: RunnableConfig) -> OverallState:
        """LangGraph 節點：執行網路研究"""
        try:
            if not self.genai_client:
                raise ValueError("Gemini 客戶端未初始化")
            
            configurable = AgentConfiguration.from_runnable_config(config)
            formatted_prompt = web_searcher_instructions.format(
                current_date=get_current_date(),
                research_topic=state["search_query"],
            )
            
            # 使用 Google genai 客戶端（因為 langchain 客戶端不返回 grounding metadata）
            response = self.genai_client.models.generate_content(
                model=configurable.query_generator_model,
                contents=formatted_prompt,
                config={
                    "tools": [{"google_search": {}}],
                    "temperature": 0,
                },
            )
            
            # 解析 URL 為短 URL 以節省 token 和時間
            resolved_urls = resolve_urls(
                response.candidates[0].grounding_metadata.grounding_chunks, state["id"]
            )
            
            # 獲取引用並添加到生成的文字中
            citations = get_citations(response, resolved_urls)
            modified_text = insert_citation_markers(response.text, citations)
            sources_gathered = [item for citation in citations for item in citation["segments"]]
            
            # 更新進度
            session_id = state.get("session_id")
            if session_id and session_id in self.current_progress:
                progress = self.current_progress[session_id]
                progress.completed_queries += 1
                progress.sources_found += len(sources_gathered)
            
            return {
                "sources_gathered": sources_gathered,
                "search_query": [state["search_query"]],
                "web_research_result": [modified_text],
            }
            
        except Exception as e:
            self.logger.error(f"網路研究失敗: {str(e)}")
            # 返回空結果而不是拋出異常，讓流程繼續
            return {
                "sources_gathered": [],
                "search_query": [state["search_query"]],
                "web_research_result": [f"搜尋 '{state['search_query']}' 時發生錯誤"],
            }
    
    def _reflection(self, state: OverallState, config: RunnableConfig) -> ReflectionState:
        """LangGraph 節點：反思和評估"""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            
            # 增加研究循環計數並獲取推理模型
            state["research_loop_count"] = state.get("research_loop_count", 0) + 1
            reasoning_model = state.get("reasoning_model") or configurable.reflection_model
            
            # 格式化提示
            current_date = get_current_date()
            formatted_prompt = reflection_instructions.format(
                current_date=current_date,
                research_topic=get_research_topic(state["messages"]),
                summaries="\n\n---\n\n".join(state["web_research_result"]),
            )
            
            # 初始化推理模型
            llm = ChatGoogleGenerativeAI(
                model=reasoning_model,
                temperature=1.0,
                max_retries=2,
                api_key=self.config.gemini_api_key,
            )
            result = llm.with_structured_output(Reflection).invoke(formatted_prompt)
            
            # 更新進度
            session_id = state.get("session_id")
            if session_id and session_id in self.current_progress:
                progress = self.current_progress[session_id]
                progress.stage = "reflection" if not result.is_sufficient else "finalize_answer"
                progress.loop_count = state["research_loop_count"]
            
            return {
                "is_sufficient": result.is_sufficient,
                "knowledge_gap": result.knowledge_gap,
                "follow_up_queries": result.follow_up_queries,
                "research_loop_count": state["research_loop_count"],
                "number_of_ran_queries": len(state["search_query"]),
            }
            
        except Exception as e:
            self.logger.error(f"反思過程失敗: {str(e)}")
            # 如果反思失敗，假設資訊充分以繼續流程
            return {
                "is_sufficient": True,
                "knowledge_gap": "",
                "follow_up_queries": [],
                "research_loop_count": state.get("research_loop_count", 0) + 1,
                "number_of_ran_queries": len(state.get("search_query", [])),
            }
    
    def _evaluate_research(self, state: ReflectionState, config: RunnableConfig):
        """LangGraph 路由函式：決定下一步"""
        configurable = AgentConfiguration.from_runnable_config(config)
        max_research_loops = (
            state.get("max_research_loops")
            if state.get("max_research_loops") is not None
            else configurable.max_research_loops
        )
        
        if state["is_sufficient"] or state["research_loop_count"] >= max_research_loops:
            return "finalize_answer"
        else:
            return [
                Send(
                    "web_research",
                    {
                        "search_query": follow_up_query,
                        "id": state["number_of_ran_queries"] + int(idx),
                    },
                )
                for idx, follow_up_query in enumerate(state["follow_up_queries"])
            ]
    
    def _finalize_answer(self, state: OverallState, config: RunnableConfig):
        """LangGraph 節點：最終化答案"""
        try:
            configurable = AgentConfiguration.from_runnable_config(config)
            reasoning_model = state.get("reasoning_model") or configurable.answer_model
            
            # 格式化提示
            current_date = get_current_date()
            formatted_prompt = answer_instructions.format(
                current_date=current_date,
                research_topic=get_research_topic(state["messages"]),
                summaries="\n---\n\n".join(state["web_research_result"]),
            )
            
            # 初始化推理模型
            llm = ChatGoogleGenerativeAI(
                model=reasoning_model,
                temperature=0,
                max_retries=2,
                api_key=self.config.gemini_api_key,
            )
            result = llm.invoke(formatted_prompt)
            
            # 替換短 URL 為原始 URL 並添加所有使用的 URL 到 sources_gathered
            unique_sources = []
            for source in state["sources_gathered"]:
                if source["short_url"] in result.content:
                    result.content = result.content.replace(
                        source["short_url"], source["value"]
                    )
                    unique_sources.append(source)
            
            # 清理和截斷文字以適應 Discord
            final_content = clean_and_truncate_text(result.content)
            
            # 添加來源資訊到最終答案
            if unique_sources:
                sources_text = "\n\n**📚 參考來源：**\n"
                for i, source in enumerate(unique_sources[:3], 1):
                    source_title = source.get('label', source.get('title', '來源'))
                    source_url = source.get('value', source.get('url', '#'))
                    sources_text += f"{i}. [{source_title}]({source_url})\n"
                
                # 確保最終內容不會超過 Discord 限制
                if len(final_content + sources_text) <= 1900:
                    final_content += sources_text
            
            # 更新進度 - 將最終答案標記為完成
            session_id = state.get("session_id")
            if session_id and session_id in self.current_progress:
                progress = self.current_progress[session_id]
                progress.stage = "completed"
                progress.final_answer = final_content  # 保存最終答案到進度對象
            
            return {
                "messages": [AIMessage(content=final_content)],
                "sources_gathered": unique_sources,
                "final_answer": final_content,  # 添加最終答案到返回結果
            }
            
        except Exception as e:
            self.logger.error(f"最終化答案失敗: {str(e)}")
            # 提供降級回應
            fallback_response = "抱歉，在整理最終答案時遇到了問題 😅 不過根據我的研究，我找到了一些相關資訊..."
            
            # 更新進度為錯誤狀態
            session_id = state.get("session_id")
            if session_id and session_id in self.current_progress:
                progress = self.current_progress[session_id]
                progress.stage = "error"
                progress.final_answer = fallback_response
            
            return {
                "messages": [AIMessage(content=fallback_response)],
                "sources_gathered": state.get("sources_gathered", []),
                "final_answer": fallback_response,
            }
    
    def _create_error_result(self, error_type: str, message: str) -> Dict[str, Any]:
        """創建錯誤結果"""
        error = ErrorHandler.create_user_friendly_error(error_type, message)
        
        return {
            "success": False,
            "error": error,
            "fallback_available": error.fallback_available,
        }
    
    def get_progress(self, session_id: str) -> Optional[ResearchProgress]:
        """獲取會話的進度"""
        return self.current_progress.get(session_id)
    
    async def create_progress_callback(self, message: discord.Message):
        """創建進度回調函式"""
        channel_id = message.channel.id
        
        # 設置當前處理的原始消息ID
        DiscordTools.set_current_original_message_id(message.id)
        
        async def progress_callback(progress: ResearchProgress):
            try:
                # 確保所有必要欄位都存在且型別正確
                stage = progress.stage if progress.stage else "processing"
                progress_message = progress.get_progress_message()
                
                # 驗證進度訊息不為空
                if not progress_message:
                    progress_message = f"🔄 處理中... ({stage})"
                
                # 建構進度更新資料
                progress_update = {
                    "stage": stage,
                    "message": progress_message,
                    "progress_percentage": None,
                    "eta_seconds": None,
                }
                
                # 計算進度百分比
                if progress.total_queries > 0 and progress.completed_queries <= progress.total_queries:
                    progress_percentage = int(
                        (progress.completed_queries / progress.total_queries) * 100
                    )
                    # 確保百分比在有效範圍內
                    progress_update["progress_percentage"] = max(0, min(100, progress_percentage))
                
                # 估計剩餘時間（簡單實現）
                if (progress.total_queries > 0 and
                    progress.completed_queries > 0 and
                    progress.completed_queries < progress.total_queries):
                    
                    # 假設每個查詢平均需要 3-5 秒
                    remaining_queries = progress.total_queries - progress.completed_queries
                    estimated_seconds = remaining_queries * 4  # 平均 4 秒每查詢
                    progress_update["eta_seconds"] = estimated_seconds
                
                # 添加調試日誌
                self.logger.debug(f"創建 DiscordProgressUpdate: {progress_update}")
                
                from .tools_and_schemas import DiscordProgressUpdate
                discord_progress = DiscordProgressUpdate(**progress_update)
                
                # 檢查是否有最終答案需要整合
                final_answer = getattr(progress, 'final_answer', None)
                
                # 發送或更新進度消息
                if stage == "completed" and final_answer:
                    # 如果是完成狀態且有最終答案，使用整合功能
                    progress_msg = await DiscordTools.send_progress_update(
                        message, discord_progress, edit_previous=True, final_answer=final_answer
                    )
                else:
                    # 正常的進度更新
                    progress_msg = await DiscordTools.send_progress_update(
                        message, discord_progress, edit_previous=True
                    )
                
                # 如果研究完成或出錯，安排清理任務
                if stage in ["completed", "error", "timeout"]:
                    # 延遲清理，給用戶時間看到最終狀態
                    asyncio.create_task(self._delayed_cleanup(channel_id, delay=30))  # 增加延遲時間
                
            except Exception as e:
                self.logger.error(f"發送進度更新失敗: {str(e)}", exc_info=True)
                # 嘗試發送簡化的進度訊息
                try:
                    simple_message = f"🔄 {stage}" if stage != "processing" else "🔄 處理中..."
                    await message.channel.send(simple_message)
                except Exception as fallback_error:
                    self.logger.error(f"降級進度訊息也失敗: {str(fallback_error)}")
        
        return progress_callback
    
    async def _delayed_cleanup(self, channel_id: int, delay: int = 10):
        """延遲清理進度消息記錄"""
        try:
            await asyncio.sleep(delay)
            DiscordTools.cleanup_progress_messages(channel_id)
            self.logger.debug(f"已清理頻道 {channel_id} 的進度消息記錄")
        except Exception as e:
            self.logger.error(f"清理進度消息記錄失敗: {str(e)}")


# 便利函式
async def create_research_agent_from_config(llmcord_config: Dict[str, Any]) -> ResearchAgent:
    """從 llmcord 配置創建研究代理"""
    agent_config = AgentConfiguration.from_llmcord_config(llmcord_config)
    return ResearchAgent(agent_config)


def should_use_research_mode(message_content: str, config: AgentConfiguration) -> bool:
    """判斷是否應該使用研究模式"""
    return config.should_use_research_mode(message_content)