"""
LangGraph 狀態結構定義

定義了研究代理的各種狀態類型，適配 Discord 環境使用。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import add_messages
from typing_extensions import Annotated
import operator
import discord


class OverallState(TypedDict):
    """主要狀態類別 - 包含整個研究流程的狀態"""
    messages: Annotated[list, add_messages]  # LangGraph 訊息鏈
    search_query: Annotated[list, operator.add]  # 搜尋查詢列表
    web_research_result: Annotated[list, operator.add]  # 網路研究結果
    sources_gathered: Annotated[list, operator.add]  # 收集的來源資料
    initial_search_query_count: int  # 初始搜尋查詢數量
    max_research_loops: int  # 最大研究循環次數
    research_loop_count: int  # 當前研究循環計數
    reasoning_model: str  # 推理模型名稱
    
    # Discord 特定欄位
    discord_message: Optional[discord.Message]  # 原始 Discord 訊息
    progress_message: Optional[discord.Message]  # 進度更新訊息
    user_id: int  # 使用者 ID
    channel_id: int  # 頻道 ID
    session_id: str  # 會話 ID


class ReflectionState(TypedDict):
    """反思狀態 - 用於評估研究是否充分"""
    is_sufficient: bool  # 資訊是否充分
    knowledge_gap: str  # 知識缺口描述
    follow_up_queries: Annotated[list, operator.add]  # 後續查詢
    research_loop_count: int  # 研究循環計數
    number_of_ran_queries: int  # 已執行查詢數量


class Query(TypedDict):
    """查詢結構"""
    query: str  # 查詢字串
    rationale: str  # 查詢理由


class QueryGenerationState(TypedDict):
    """查詢生成狀態"""
    query_list: list[Query]  # 查詢列表


class WebSearchState(TypedDict):
    """網路搜尋狀態"""
    search_query: str  # 搜尋查詢
    id: str  # 搜尋 ID


@dataclass(kw_only=True)
class ResearchConfig:
    """研究配置類別"""
    # 模型配置
    query_generator_model: str = "gemini-2.0-flash-exp"
    reflection_model: str = "gemini-2.0-flash-exp" 
    answer_model: str = "gemini-2.0-flash-exp"
    
    # 搜尋配置
    number_of_initial_queries: int = 2  # Discord 環境下減少初始查詢數
    max_research_loops: int = 1  # Discord 環境下減少循環次數
    
    # Discord 特定配置
    progress_updates: bool = True  # 是否發送進度更新
    timeout_seconds: int = 30  # 超時時間（秒）
    fallback_enabled: bool = True  # 是否啟用降級機制
    
    # API 配置
    gemini_api_key: Optional[str] = None
    google_search_api_key: Optional[str] = None
    google_search_engine_id: Optional[str] = None


@dataclass
class DiscordContext:
    """Discord 環境上下文"""
    message: discord.Message
    user_id: int
    channel_id: int
    guild_id: Optional[int]
    session_id: str
    is_dm: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "guild_id": self.guild_id,
            "session_id": self.session_id,
            "is_dm": self.is_dm,
        }


@dataclass
class ResearchProgress:
    """研究進度追蹤"""
    stage: str  # 當前階段
    completed_queries: int = 0  # 已完成查詢數
    total_queries: int = 0  # 總查詢數
    loop_count: int = 0  # 循環計數
    sources_found: int = 0  # 找到的來源數
    
    def get_progress_message(self) -> str:
        """獲取進度訊息"""
        # 確保 stage 不為 None 或空字串
        safe_stage = self.stage if self.stage else "processing"
        
        stage_messages = {
            "generate_query": "🤔 正在分析問題並生成搜尋策略...",
            "web_research": f"🔍 正在進行網路研究 ({self.completed_queries}/{self.total_queries})",
            "reflection": f"💭 正在分析結果並評估資訊完整性... (循環 {self.loop_count})",
            "finalize_answer": f"📝 正在整理最終答案... (已收集 {self.sources_found} 個來源)",
            "completed": "✅ 研究完成！",
            "error": "❌ 研究過程中發生錯誤",
            "timeout": "⏰ 研究超時，正在提供可用結果...",
            "processing": "🔄 正在處理..."
        }
        
        # 獲取訊息，如果沒有對應的訊息則使用預設訊息
        message = stage_messages.get(safe_stage, f"🔄 處理中... ({safe_stage})")
        
        # 確保訊息不為空
        return message if message else "🔄 正在處理..."


# 狀態更新輔助函數
def create_initial_state(
    discord_ctx: DiscordContext,
    user_message: str,
    config: ResearchConfig
) -> OverallState:
    """創建初始狀態"""
    from langchain_core.messages import HumanMessage
    
    return OverallState(
        messages=[HumanMessage(content=user_message)],
        search_query=[],
        web_research_result=[],
        sources_gathered=[],
        initial_search_query_count=config.number_of_initial_queries,
        max_research_loops=config.max_research_loops,
        research_loop_count=0,
        reasoning_model=config.answer_model,
        discord_message=discord_ctx.message,
        progress_message=None,
        user_id=discord_ctx.user_id,
        channel_id=discord_ctx.channel_id,
        session_id=discord_ctx.session_id,
    )


def update_progress_in_state(
    state: OverallState,
    progress: ResearchProgress
) -> Dict[str, Any]:
    """更新狀態中的進度資訊"""
    # 這裡可以添加進度相關的狀態更新邏輯
    return {}