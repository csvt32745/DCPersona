"""
RAG 流程 - 整合 LangGraph 智能研究

更新後的 RAG 流程支援智能模式切換：
- 簡單問答使用傳統流程
- 複雜研究自動啟動 LangGraph
- 支援用戶強制指定模式
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import discord
from openai import AsyncOpenAI

from agents.research_agent import ResearchAgent, create_research_agent_from_config, should_use_research_mode
from agents.state import DiscordContext, ResearchConfig
from agents.configuration import AgentConfiguration
from agents.utils import analyze_message_complexity, assess_message_complexity_with_llm, generate_session_id
from agents.tools_and_schemas import ErrorHandler, DiscordTools
from core.session_manager import get_session_manager


class SmartRAGPipeline:
    """智能 RAG 流程管理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._research_agent: Optional[ResearchAgent] = None
        self._agent_config: Optional[AgentConfiguration] = None
        self._llm_client: Optional[AsyncOpenAI] = None
        self._cfg: Optional[Dict[str, Any]] = None
    
    async def initialize(self, llmcord_config: Dict[str, Any]):
        """
        初始化 RAG 流程
        
        Args:
            llmcord_config: llmcord 配置
        """
        try:
            # 儲存配置
            self._cfg = llmcord_config
            
            # 創建 LLM 客戶端（用於複雜度評估）
            self._create_llm_client(llmcord_config)
            
            # 創建 agent 配置
            self._agent_config = AgentConfiguration.from_llmcord_config(llmcord_config)
            
            # 驗證 API 金鑰
            is_valid, message = self._agent_config.validate_api_keys()
            if not is_valid:
                self.logger.warning(f"LangGraph 功能可能受限: {message}")
            
            # 創建研究代理
            self._research_agent = ResearchAgent(self._agent_config)
            
            self.logger.info("智能 RAG 流程已初始化")
            
        except Exception as e:
            self.logger.error(f"初始化 RAG 流程失敗: {str(e)}")
            self._research_agent = None
    
    def _create_llm_client(self, cfg: Dict[str, Any]):
        """
        創建 LLM 客戶端用於複雜度評估
        
        Args:
            cfg: llmcord 配置
        """
        try:
            provider_slash_model = cfg.get("model", "openai/gpt-3.5-turbo")
            provider, model = provider_slash_model.split("/", 1)
            base_url = cfg.get("providers", {}).get(provider, {}).get("base_url", "https://api.openai.com/v1")
            api_key = cfg.get("providers", {}).get(provider, {}).get("api_key", "sk-no-key-required")
            
            self._llm_client = AsyncOpenAI(base_url=base_url, api_key=api_key)
            self._model_name = model  # 儲存模型名稱用於複雜度評估
            self.logger.info(f"LLM 客戶端已創建: {provider}/{model}")
            
        except Exception as e:
            self.logger.warning(f"創建 LLM 客戶端失敗: {str(e)}，將回退到規則型複雜度評估")
            self._llm_client = None
            self._model_name = None
    
    async def process_message(
        self,
        message: discord.Message,
        message_data: Dict[str, Any],
        cfg: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        處理訊息並決定使用哪種流程
        
        Args:
            message: Discord 訊息
            message_data: 訊息資料
            cfg: 配置
            
        Returns:
            Dict: 處理結果
        """
        try:
            # 提取使用者訊息內容
            user_content = self._extract_user_message(message_data)
            if not user_content:
                return await self._fallback_response(message, "無法識別使用者訊息")
            
            # 檢查是否強制使用研究模式
            force_research = self._check_force_research_mode(user_content)
            
            # 使用新的 LLM 複雜度評估（優先），回退到規則評估
            try:
                if self._llm_client:
                    # 使用 LLM 進行複雜度評估
                    complexity_analysis = await assess_message_complexity_with_llm(
                        message_content=user_content,
                        llm_client=self._llm_client,
                        fallback_to_rules=True,
                        model_name=getattr(self, '_model_name', 'gpt-3.5-turbo')
                    )
                    
                    self.logger.info(f"LLM 複雜度評估完成 - 決定: {complexity_analysis['final_decision']}, "
                                   f"方法: {complexity_analysis['method']}, "
                                   f"信心: {complexity_analysis['confidence']:.2f}")
                else:
                    # 回退到規則型評估
                    rule_result = analyze_message_complexity(user_content)
                    complexity_analysis = {
                        "final_decision": "RESEARCH" if rule_result["use_research"] else "SIMPLE",
                        "use_research": rule_result["use_research"],
                        "confidence": rule_result["complexity_score"],
                        "method": "rule_based_fallback"
                    }
                    
                    self.logger.info(f"規則複雜度評估 - 複雜度: {rule_result['complexity_score']:.2f}, "
                                   f"使用研究: {rule_result['use_research']}")
                    
            except Exception as e:
                self.logger.warning(f"複雜度評估失敗，使用規則型評估: {str(e)}")
                rule_result = analyze_message_complexity(user_content)
                complexity_analysis = {
                    "final_decision": "RESEARCH" if rule_result["use_research"] else "SIMPLE",
                    "use_research": rule_result["use_research"],
                    "confidence": rule_result["complexity_score"],
                    "method": "rule_based_error_fallback"
                }
            
            # 決定使用哪種模式
            use_research_mode = (
                force_research or
                (self._research_agent is not None and
                 (complexity_analysis["use_research"] or
                  (self._agent_config and self._agent_config.should_use_research_mode(user_content))))
            )
            
            self.logger.info(f"最終決定 - 使用研究模式: {use_research_mode} "
                           f"(強制: {force_research}, 複雜度建議: {complexity_analysis['use_research']})")
            
            if use_research_mode and self._research_agent:
                return await self._process_with_langgraph(message, user_content, message_data)
            else:
                return await self._process_with_traditional_rag(message, user_content, message_data)
                
        except Exception as e:
            self.logger.error(f"處理訊息時發生錯誤: {str(e)}", exc_info=True)
            return await self._fallback_response(message, str(e))
    
    async def _process_with_langgraph(
        self,
        message: discord.Message,
        user_content: str,
        message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用 LangGraph 進行深度研究"""
        try:
            # 創建 Discord 上下文
            discord_ctx = DiscordContext(
                message=message,
                user_id=message.author.id,
                channel_id=message.channel.id,
                guild_id=message.guild.id if message.guild else None,
                session_id=generate_session_id(message.author.id, message.channel.id),
                is_dm=message.guild is None
            )
            
            # 獲取會話管理器
            session_manager = get_session_manager()
            session_data = session_manager.get_or_create_session(message)
            
            # 創建進度回調
            progress_callback = await self._research_agent.create_progress_callback(message)
            
            # 執行研究流程
            research_result = await self._research_agent.process_research_request(
                discord_ctx=discord_ctx,
                user_message=user_content,
                progress_callback=progress_callback
            )
            
            if research_result["success"]:
                # 更新會話狀態
                session_manager.update_session_state(
                    discord_ctx.session_id,
                    research_result["result"]
                )
                
                # 提取最終回應
                final_message = research_result["result"]["messages"][-1].content
                sources = research_result["result"].get("sources_gathered", [])
                
                return {
                    "augmented_content": final_message,
                    "sources": sources,
                    "research_mode": True,
                    "execution_time": research_result.get("execution_time"),
                    "session_id": discord_ctx.session_id,
                }
            else:
                # 研究失敗，使用降級機制
                error_obj = research_result.get("error", {})
                error_message = "Unknown error"
                user_friendly_message = "研究過程發生錯誤"
                try:
                    if hasattr(error_obj, "error_message"):
                        error_message = getattr(error_obj, "error_message", "Unknown error")
                    elif isinstance(error_obj, dict):
                        error_message = error_obj.get("error_message", "Unknown error")
                    else:
                        error_message = str(error_obj)
                    if hasattr(error_obj, "user_friendly_message"):
                        user_friendly_message = getattr(error_obj, "user_friendly_message", user_friendly_message)
                    elif isinstance(error_obj, dict):
                        user_friendly_message = error_obj.get("user_friendly_message", user_friendly_message)
                except Exception as e:
                    self.logger.warning(f"處理 error 結構時發生例外: {e}")
                self.logger.warning(f"LangGraph 研究失敗: {error_message}")
                return await self._fallback_response(
                    message,
                    user_friendly_message
                )
                
        except Exception as e:
            self.logger.error(f"LangGraph 處理失敗: {str(e)}", exc_info=True)
            return await self._fallback_response(message, "深度研究功能暫時無法使用")
    
    async def _process_with_traditional_rag(
        self,
        message: discord.Message,
        user_content: str,
        message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用傳統 RAG 流程"""
        self.logger.info("使用傳統 RAG 流程處理訊息")
        
        # 這裡保持原有的簡單 RAG 邏輯
        # 未來可以整合向量資料庫、知識圖譜等
        return {
            "augmented_content": None,
            "sources": [],
            "research_mode": False,
            "note": "使用傳統流程處理"
        }
    
    async def _fallback_response(self, message: discord.Message, error_msg: str) -> Dict[str, Any]:
        """降級回應機制"""
        try:
            # 使用三角初華的降級回應
            fallback_messages = [
                "抱歉，我在處理妳的問題時遇到了一些困難 😅",
                "技術上出了點小狀況... 不過我會盡力回答妳的 💭",
                "系統有點不穩定呢... 讓我用其他方式來回答妳 ✨",
                "網路搜尋功能暫時有問題，但我還是想幫助妳 🌟"
            ]
            
            import random
            fallback_content = random.choice(fallback_messages)
            
            return {
                "augmented_content": fallback_content,
                "sources": [],
                "research_mode": False,
                "is_fallback": True,
                "error": error_msg
            }
            
        except Exception as e:
            self.logger.error(f"降級回應也失敗了: {str(e)}")
            return {
                "augmented_content": "抱歉，目前遇到技術問題，請稍後再試 😔",
                "sources": [],
                "research_mode": False,
                "is_fallback": True,
                "error": str(e)
            }
    
    def _extract_user_message(self, message_data: Dict[str, Any]) -> Optional[str]:
        """從訊息資料中提取使用者內容"""
        # 這裡需要根據實際的 message_data 結構來提取
        # 假設結構類似於 {"content": "...", "messages": [...]}
        if "content" in message_data:
            return message_data["content"]
        
        if "messages" in message_data and message_data["messages"]:
            # 取最後一條使用者訊息
            for msg in reversed(message_data["messages"]):
                if msg.get("role") == "user":
                    return msg.get("content", "")
        
        return None
    
    def _check_force_research_mode(self, content: str) -> bool:
        """檢查是否強制使用研究模式"""
        force_keywords = ["!research", "!研究", "!調查", "!深入"]
        content_lower = content.lower()
        
        return any(keyword in content_lower for keyword in force_keywords)
    
    def is_research_available(self) -> bool:
        """檢查研究功能是否可用"""
        return self._research_agent is not None and self._agent_config is not None
    
    def get_research_stats(self) -> Dict[str, Any]:
        """獲取研究功能統計"""
        session_manager = get_session_manager()
        session_stats = session_manager.get_session_stats()
        
        return {
            "research_available": self.is_research_available(),
            "agent_config": self._agent_config.model_dump() if self._agent_config else None,
            "session_stats": session_stats,
        }


# 全域 RAG 流程實例
_rag_pipeline: Optional[SmartRAGPipeline] = None


async def get_rag_pipeline() -> SmartRAGPipeline:
    """獲取全域 RAG 流程實例"""
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = SmartRAGPipeline()
    return _rag_pipeline


async def init_rag_pipeline(llmcord_config: Dict[str, Any]) -> SmartRAGPipeline:
    """
    初始化全域 RAG 流程
    
    Args:
        llmcord_config: llmcord 配置
        
    Returns:
        SmartRAGPipeline: RAG 流程實例
    """
    global _rag_pipeline
    _rag_pipeline = SmartRAGPipeline()
    await _rag_pipeline.initialize(llmcord_config)
    return _rag_pipeline


# 向後相容的函式（保持原有 API）
async def retrieve_augmented_context(message_data: Dict[str, Any], message: discord.Message = None, cfg: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    向後相容的 RAG 上下文檢索函式
    
    Args:
        message_data: 訊息資料
        message: Discord 訊息（新增參數）
        cfg: 配置（新增參數）
        
    Returns:
        Dict: 增強的上下文資訊
    """
    try:
        # 如果沒有提供必要參數，返回空結果
        if not message or not cfg:
            logging.info("向後相容模式：缺少必要參數，返回空結果")
            return {
                "augmented_content": None,
                "sources": []
            }
        
        # 獲取 RAG 流程實例
        rag_pipeline = await get_rag_pipeline()
        
        # 如果未初始化，先初始化
        if not rag_pipeline.is_research_available():
            await rag_pipeline.initialize(cfg)
        
        # 處理訊息
        result = await rag_pipeline.process_message(message, message_data, cfg)
        
        # 轉換為向後相容的格式
        return {
            "augmented_content": result.get("augmented_content"),
            "sources": result.get("sources", []),
            "research_mode_used": result.get("research_mode", False),
            "execution_time": result.get("execution_time"),
        }
        
    except Exception as e:
        logging.error(f"RAG 上下文檢索失敗: {str(e)}")
        return {
            "augmented_content": None,
            "sources": [],
            "error": str(e)
        }


# 新的主要入口函式
async def process_smart_rag(
    message: discord.Message,
    message_data: Dict[str, Any],
    cfg: Dict[str, Any]
) -> Dict[str, Any]:
    """
    智能 RAG 處理主入口
    
    Args:
        message: Discord 訊息
        message_data: 訊息資料
        cfg: 配置
        
    Returns:
        Dict: 處理結果
    """
    rag_pipeline = await get_rag_pipeline()
    
    # 如果未初始化，先初始化
    if not rag_pipeline.is_research_available():
        await rag_pipeline.initialize(cfg)
    
    return await rag_pipeline.process_message(message, message_data, cfg)
