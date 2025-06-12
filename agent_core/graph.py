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

from langchain_core.messages import AIMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langchain_core.runnables import RunnableConfig
from google.genai import Client

from schemas.agent_types import OverallState, MsgNode, DiscordProgressUpdate
from utils.config_loader import load_config
from agents.prompts import web_searcher_instructions, get_current_date
from agents.utils import resolve_urls, get_citations, insert_citation_markers


class UnifiedAgent:
    """統一的 Agent 實作，根據配置動態調整行為"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化統一 Agent
        
        Args:
            config: 配置字典，如果為 None 則載入預設配置
        """
        self.config = config or load_config()
        self.logger = logging.getLogger(__name__)
        
        # 從配置獲取 agent 設定
        self.agent_config = self.config.get("agent", {})
        self.tools_config = self.agent_config.get("tools", {})
        self.behavior_config = self.agent_config.get("behavior", {})
        
        # 初始化多個 LLM 實例
        self.llm_instances = self._initialize_llm_instances()
        
        # 初始化 Google 客戶端（如果工具啟用）
        self.google_client = None
        if self.tools_config.get("google_search", {}).get("enabled", False):
            api_key = self.config.get("gemini_api_key")
            if api_key:
                self.google_client = Client(api_key=api_key)
    
    def _initialize_llm_instances(self) -> Dict[str, Optional[ChatGoogleGenerativeAI]]:
        """初始化不同用途的 LLM 實例"""
        api_key = self.config.get("gemini_api_key")
        if not api_key:
            return {
                "tool_analysis": None,
                "final_answer": None,
                "reflection": None
            }
        
        # LLM 配置
        llm_configs = self.config.get("llm_models", {
            "tool_analysis": {
                "model": "gemini-2.0-flash-exp",
                "temperature": 0.1
            },
            "final_answer": {
                "model": "gemini-2.0-flash-exp", 
                "temperature": 0.7
            },
            "reflection": {
                "model": "gemini-2.0-flash-exp",
                "temperature": 0.3
            }
        })
        
        llm_instances = {}
        for purpose, config in llm_configs.items():
            try:
                llm_instances[purpose] = ChatGoogleGenerativeAI(
                    model=config.get("model", "gemini-2.0-flash-exp"),
                    temperature=config.get("temperature", 0.5),
                    api_key=api_key
                )
                self.logger.info(f"初始化 {purpose} LLM: {config.get('model')}")
            except Exception as e:
                self.logger.warning(f"初始化 {purpose} LLM 失敗: {e}")
                llm_instances[purpose] = None
        
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
        
        # 根據配置決定流程
        max_tool_rounds = self.behavior_config.get("max_tool_rounds", 0)
        
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
    
    def generate_query_or_plan(self, state: OverallState) -> Dict[str, Any]:
        """
        LangGraph 節點：生成查詢或初步規劃
        
        分析用戶請求並決定是否需要使用工具，生成初步的行動計劃。
        """
        try:
            self.logger.info("generate_query_or_plan: 開始分析用戶請求")
            
            # 獲取最新的用戶訊息
            if not state.messages:
                return {"finished": True}
            
            latest_message = state.messages[-1] if state.messages else None
            if not latest_message or latest_message.role != "user":
                return {"finished": True}
            
            user_content = latest_message.content
            max_tool_rounds = self.behavior_config.get("max_tool_rounds", 0)
            
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
            return {"finished": True}
    
    def tool_selection(self, state: OverallState) -> Dict[str, Any]:
        """
        LangGraph 節點：工具選擇
        
        根據當前狀態和配置決定使用哪些工具。
        """
        try:
            self.logger.info("tool_selection: 選擇適當的工具")
            
            available_tools = []
            
            # 根據優先級排序工具
            tools_by_priority = sorted(
                self.tools_config.items(),
                key=lambda x: x[1].get("priority", 999)
            )
            
            for tool_name, tool_config in tools_by_priority:
                if tool_config.get("enabled", False):
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
    
    def execute_tool(self, state: OverallState) -> Dict[str, Any]:
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
            self.logger.info(f"execute_tool: 結果={tool_results}")
            
            
            return {
                "tool_results": tool_results,
                "tool_round": current_round
            }
            
        except Exception as e:
            self.logger.error(f"execute_tool 失敗: {e}")
            return {"tool_results": [], "tool_round": state.tool_round + 1}
    
    def reflection(self, state: OverallState) -> Dict[str, Any]:
        """
        LangGraph 節點：反思
        
        評估工具結果的質量和完整性。
        """
        try:
            if not self.behavior_config.get("enable_reflection", True):
                # 如果禁用反思，直接認為結果充分
                return {"is_sufficient": True}
            
            self.logger.info("reflection: 開始反思工具結果")
            
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
            max_rounds = self.behavior_config.get("max_tool_rounds", 1)
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
    
    def finalize_answer(self, state: OverallState) -> Dict[str, Any]:
        """
        LangGraph 節點：生成最終答案
        
        整合所有信息並生成最終回覆。
        """
        try:
            self.logger.info("finalize_answer: 生成最終答案")
            
            # 獲取基礎信息
            messages = state.messages
            tool_results = state.tool_results
            research_topic = state.research_topic
            
            if not messages:
                return {"finished": True}
            
            # 準備答案生成的上下文
            context_parts = []
            
            # 添加工具結果作為上下文
            if tool_results:
                context_parts.append("研究結果:")
                for i, result in enumerate(tool_results[:5], 1):  # 限制最多5個結果
                    context_parts.append(f"{i}. {result}")
            
            context = "\n".join(context_parts) if context_parts else ""
            
            # 生成最終答案
            final_answer = self._generate_final_answer(messages, context)
            
            self.logger.info("finalize_answer: 答案生成完成")
            
            return {
                "final_answer": final_answer,
                "finished": True
            }
            
        except Exception as e:
            self.logger.error(f"finalize_answer 失敗: {e}")
            return {
                "final_answer": "抱歉，處理您的請求時發生錯誤。",
                "finished": True
            }
    
    # 內部輔助方法
    
    def _analyze_tool_necessity(self, messages: List[MsgNode]) -> bool:
        """分析是否需要使用工具（使用專用 LLM 智能判斷）"""
        tool_analysis_llm = self.llm_instances.get("tool_analysis")
        if not tool_analysis_llm:
            return self._analyze_tool_necessity_fallback(messages)
        
        try:
            # 構建包含所有歷史對話的提示
            conversation_history = ""
            for msg in messages:
                if msg.role == "user":
                    conversation_history += f"用戶: {msg.content}\n"
                elif msg.role == "assistant":
                    conversation_history += f"初華: {msg.content}\n"

            analysis_prompt = f"""
請分析以下對話歷史，判斷最新一條用戶請求是否需要使用搜尋工具來獲取最新資訊：

對話歷史：
{conversation_history}

判斷標準：
- 最新用戶請求需要最新資訊、即時數據、新聞事件
- 最新用戶請求需要查找特定事實、數據、統計
- 最新用戶請求涉及當前狀況、最新發展
- 最新用戶請求需要驗證或引用外部資源
- 最新用戶請求是之前問題的延伸或補充，且需要搜尋來回答。

請只回答「是」或「否」，不需要解釋。
"""
            
            response = tool_analysis_llm.invoke(analysis_prompt)
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
        tool_analysis_llm = self.llm_instances.get("tool_analysis") # 仍使用此 LLM
        if not tool_analysis_llm:
            # 回退到簡化實作：直接使用最新用戶輸入作為查詢
            return [messages[-1].content[:100]]
        
        try:
            # 構建包含所有歷史對話的提示
            conversation_history = ""
            for msg in messages:
                if msg.role == "user":
                    conversation_history += f"用戶: {msg.content}\n"
                elif msg.role == "assistant":
                    conversation_history += f"初華: {msg.content}\n"

            query_generation_prompt = f"""
根據以下對話歷史，為最新一條用戶請求生成 1-2 個精確的網路搜尋查詢。請確保查詢能涵蓋用戶請求的最新資訊需求。

對話歷史：
{conversation_history}

輸出格式：
請直接提供 JSON 格式的搜尋查詢列表。如果沒有需要搜尋的查詢，請回傳一個空的 JSON 列表 `[]`。

範例：
[ "查詢一", "查詢二" ]
或者，如果不需要查詢：
[]
"""
            
            response = tool_analysis_llm.invoke(query_generation_prompt)
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
            return ["Google 客戶端未配置，無法執行 Google 搜尋。"]
        
        search_queries = state.search_queries
        self.logger.debug(f"DEBUG: _execute_google_search: search_queries type: {type(search_queries)}, value: {search_queries}")
        results = []
        
        try:
            for query in search_queries[:2]:  # 限制最多2個查詢
                current_date = get_current_date()
                
                # 準備傳遞給 Gemini 模型的提示
                formatted_prompt = web_searcher_instructions.format(
                    research_topic=query,
                    current_date=current_date
                )
                
                # 使用專用的工具分析 LLM 進行搜尋
                tool_llm = self.llm_instances.get("tool_analysis")
                if not tool_llm:
                    results.append("搜尋 LLM 未配置，無法執行 Google 搜尋。")
                    continue

                try:
                    tool_llm_config = self.config.get("llm_models", {}).get("tool_analysis", {})
                    model_name = tool_llm_config.get("model", "gemini-2.0-flash-exp")
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
        
        # 嘗試使用專用的回答生成 LLM
        final_answer_llm = self.llm_instances.get("final_answer")
        
        # 不管有沒有context，都用LLM生成更自然的回應
        if final_answer_llm:
            try:
                if context:
                    # 有搜尋結果的情況
                    answer_prompt = f"""
你是一個友善、聰明的聊天助手。請用自然、人性化的方式回答用戶的問題。

用戶問題：{user_question}

相關資訊：
{context}

回答要求：
- 用輕鬆、友好的語調
- 像朋友間聊天一樣自然
- 可以適當使用表情符號
- 回答要實用且容易理解
- 表現出對用戶問題的關心和理解

請提供一個溫暖、有幫助的回答：
"""
                else:
                    # 一般聊天的情況
                    answer_prompt = f"""
                你是一個友善、聰明的聊天助手。請用自然、人性化的方式回答用戶的問題或與用戶對話。

                用戶說：{user_question}

                回答要求：
                - 用輕鬆、友好的語調，像朋友間聊天
                - 可以適當使用表情符號
                - 直接回答問題或回應用戶的話題
                - 表現出興趣和關心
                - 如果是問題，盡力回答；如果是閒聊，友善回應
                - 可以適當提出相關的後續問題來延續對話

                請提供一個溫暖、自然的回應：
                """
                
                response = final_answer_llm.invoke(answer_prompt)
                return response.content.strip()
                
            except Exception as e:
                self.logger.warning(f"使用 LLM 生成答案失敗: {e}")
        
        # 回退到簡化邏輯 - 也要人性化
        if context:
            return f"關於你問的「{user_question}」，我找到了一些有用的資訊呢！✨\n\n{context}\n\n希望這些對你有幫助！還有什麼想了解的嗎？😊"
        else:
            return f"嗨！關於「{user_question}」，我很樂意和你聊聊～雖然我現在沒有額外的搜尋資訊，但我會盡我所知來回答你！😊 有什麼特別想聊的嗎？"


# 便利函數

def create_unified_agent(config: Optional[Dict[str, Any]] = None) -> UnifiedAgent:
    """建立統一 Agent 實例"""
    return UnifiedAgent(config)


def create_agent_graph(config: Optional[Dict[str, Any]] = None) -> StateGraph:
    """建立並編譯 Agent 圖"""
    agent = create_unified_agent(config)
    return agent.build_graph() 