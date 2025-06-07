"""
結構化資料模式和工具定義

基於 gemini-fullstack-langgraph-quickstart 的工具系統，
適配到 Discord 環境並添加中文支援。
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import discord
import time


class SearchQueryList(BaseModel):
    """搜尋查詢列表結構"""
    query: List[str] = Field(
        description="用於網路研究的搜尋查詢列表"
    )
    rationale: str = Field(
        description="解釋為什麼這些查詢與研究主題相關的簡要說明"
    )


class Reflection(BaseModel):
    """反思結果結構"""
    is_sufficient: bool = Field(
        description="提供的摘要是否足以回答使用者的問題"
    )
    knowledge_gap: str = Field(
        description="缺失或需要澄清的資訊描述"
    )
    follow_up_queries: List[str] = Field(
        description="解決知識缺口的後續查詢列表"
    )


class ResearchSource(BaseModel):
    """研究來源結構"""
    title: str = Field(description="來源標題")
    url: str = Field(description="來源 URL")
    short_url: str = Field(description="短 URL 用於引用")
    snippet: str = Field(description="來源摘要")
    relevance_score: Optional[float] = Field(description="相關性評分")


class WebSearchResult(BaseModel):
    """網路搜尋結果結構"""
    query: str = Field(description="搜尋查詢")
    summary: str = Field(description="搜尋結果摘要")
    sources: List[ResearchSource] = Field(description="來源列表")
    search_id: str = Field(description="搜尋 ID")


class ResearchSummary(BaseModel):
    """研究摘要結構"""
    topic: str = Field(description="研究主題")
    summary: str = Field(description="研究摘要")
    sources: List[ResearchSource] = Field(description="所有來源")
    confidence_score: Optional[float] = Field(description="信心評分")
    created_at: str = Field(description="創建時間")


class DiscordProgressUpdate(BaseModel):
    """Discord 進度更新結構"""
    stage: str = Field(description="當前階段", min_length=1)
    message: str = Field(description="進度訊息", min_length=1)
    progress_percentage: Optional[int] = Field(default=None, description="進度百分比", ge=0, le=100)
    eta_seconds: Optional[int] = Field(default=None, description="預估剩餘時間（秒）", ge=0)


class ErrorResponse(BaseModel):
    """錯誤回應結構"""
    error_type: str = Field(description="錯誤類型")
    error_message: str = Field(description="錯誤訊息")
    fallback_available: bool = Field(description="是否有降級方案")
    user_friendly_message: str = Field(description="使用者友好的錯誤訊息")


class ComplexityAssessment(BaseModel):
    """複雜度評估結構"""
    use_research: bool = Field(description="是否使用研究模式")
    complexity_score: float = Field(description="複雜度評分 (0-1)")
    reasoning: str = Field(description="評估理由")
    detected_keywords: List[str] = Field(description="檢測到的關鍵字")


class SessionInfo(BaseModel):
    """會話資訊結構"""
    session_id: str = Field(description="會話 ID")
    user_id: int = Field(description="使用者 ID")
    channel_id: int = Field(description="頻道 ID")
    guild_id: Optional[int] = Field(description="伺服器 ID")
    start_time: str = Field(description="開始時間")
    message_count: int = Field(description="訊息數量")
    is_active: bool = Field(description="是否活躍")


# 進度消息管理器
class ProgressMessageManager:
    """管理 Discord 進度消息的全域管理器"""
    
    def __init__(self):
        # 使用字典追蹤 {channel_id: progress_message}
        # 每個頻道只保持一個活躍的進度消息
        self._progress_messages: Dict[int, discord.Message] = {}
        
        # 使用普通字典追蹤原始消息ID到進度消息的映射
        # 鍵為 message.id (int)，值為進度消息物件
        self._message_to_progress: Dict[int, discord.Message] = {}
        
        # 記錄消息創建時間，用於清理機制
        self._message_timestamps: Dict[int, float] = {}
        
        # 追蹤訊息的最終答案狀態
        self._final_answers: Dict[int, str] = {}
    
    async def send_or_update_progress(
        self,
        original_message: discord.Message,
        progress: DiscordProgressUpdate,
        final_answer: Optional[str] = None
    ) -> Optional[discord.Message]:
        """發送新的進度消息或更新現有消息，支援最終答案整合"""
        try:
            # 建構進度內容
            progress_content = self._format_progress_content(progress, final_answer)
            channel_id = original_message.channel.id
            
            # 如果提供了最終答案，記錄它
            if final_answer:
                self._final_answers[original_message.id] = final_answer
            
            # 檢查是否已有進度消息存在
            existing_progress_msg = self._progress_messages.get(channel_id)
            
            if existing_progress_msg:
                try:
                    # 嘗試編輯現有進度消息
                    await existing_progress_msg.edit(content=progress_content)
                    return existing_progress_msg
                except (discord.NotFound, discord.HTTPException, discord.Forbidden):
                    # 如果編輯失敗（消息被刪除、無權限等），移除記錄並發送新消息
                    self._progress_messages.pop(channel_id, None)
            
            # 發送新的進度消息
            progress_msg = await original_message.reply(
                content=progress_content,
                mention_author=False
            )
            
            # 記錄新的進度消息
            self._progress_messages[channel_id] = progress_msg
            self._message_to_progress[original_message.id] = progress_msg
            self._message_timestamps[original_message.id] = time.time()
            
            return progress_msg
            
        except discord.HTTPException as e:
            print(f"發送進度更新失敗: {e}")
            return None
    
    def _format_progress_content(self, progress: DiscordProgressUpdate, final_answer: Optional[str] = None) -> str:
        """格式化進度內容，支援最終答案整合"""
        # 基本進度內容
        if progress.stage == "completed" and final_answer:
            # 如果是完成狀態且有最終答案，使用整合格式
            content = f"{final_answer}"
        else:
            # 正常進度格式
            content = f"{progress.message}"
            
            if progress.progress_percentage is not None:
                # 創建進度條視覺效果
                progress_bar = self._create_progress_bar(progress.progress_percentage)
                content += f"\n{progress_bar} {progress.progress_percentage}%"
            
            if progress.eta_seconds is not None and progress.eta_seconds > 0:
                eta_text = self._format_eta(progress.eta_seconds)
                content += f"\n⏱️ 預估剩餘時間: {eta_text}"
        
        # 如果有保存的最終答案且當前不是完成狀態，也要顯示它
        if not (progress.stage == "completed" and final_answer) and hasattr(self, '_current_original_msg_id'):
            stored_answer = self._final_answers.get(self._current_original_msg_id)
            if stored_answer:
                content += f"\n\n**🎯 研究結果：**\n{stored_answer}"
        
        return content
    
    def _create_progress_bar(self, percentage: int, length: int = 10) -> str:
        """創建進度條視覺效果"""
        filled = int(length * percentage / 100)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}]"
    
    def _format_eta(self, seconds: int) -> str:
        """格式化預估時間"""
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            return f"{minutes}分{remaining_seconds}秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}小時{minutes}分"
    
    def cleanup_progress_message(self, channel_id: int):
        """清理指定頻道的進度消息記錄"""
        self._progress_messages.pop(channel_id, None)
    
    def cleanup_message_tracking(self, message_id: int):
        """清理指定消息的追蹤記錄"""
        self._message_to_progress.pop(message_id, None)
        self._message_timestamps.pop(message_id, None)
        self._final_answers.pop(message_id, None)
    
    def cleanup_all_progress_messages(self):
        """清理所有進度消息記錄"""
        self._progress_messages.clear()
        self._message_to_progress.clear()
        self._message_timestamps.clear()
        self._final_answers.clear()
    
    def cleanup_old_messages(self, max_age_seconds: int = 3600):
        """清理超過指定時間的消息追蹤記錄（預設1小時）"""
        current_time = time.time()
        expired_message_ids = [
            msg_id for msg_id, timestamp in self._message_timestamps.items()
            if current_time - timestamp > max_age_seconds
        ]
        
        for msg_id in expired_message_ids:
            self.cleanup_message_tracking(msg_id)
    
    def get_active_progress_count(self) -> int:
        """獲取活躍進度消息數量"""
        return len(self._progress_messages)
    
    def get_tracked_messages_count(self) -> int:
        """獲取追蹤的消息數量"""
        return len(self._message_to_progress)
    
    def get_progress_message_by_original_id(self, original_message_id: int) -> Optional[discord.Message]:
        """根據原始消息ID獲取進度消息"""
        return self._message_to_progress.get(original_message_id)
    
    async def update_with_final_answer(
        self,
        original_message: discord.Message,
        final_answer: str
    ) -> Optional[discord.Message]:
        """將最終答案更新到現有的進度消息"""
        try:
            # 保存最終答案
            self._final_answers[original_message.id] = final_answer
            
            # 獲取現有的進度消息
            progress_msg = self._message_to_progress.get(original_message.id)
            if progress_msg:
                # 創建完成狀態的進度更新
                completed_progress = DiscordProgressUpdate(
                    stage="completed",
                    message="研究已完成",
                    progress_percentage=100
                )
                
                # 格式化內容（包含最終答案）
                final_content = self._format_progress_content(completed_progress, final_answer)
                
                # 更新消息
                await progress_msg.edit(content=final_content)
                return progress_msg
            
            return None
            
        except Exception as e:
            print(f"更新最終答案失敗: {e}")
            return None
    
    def set_current_original_message_id(self, message_id: int):
        """設置當前處理的原始消息ID（用於格式化時獲取最終答案）"""
        self._current_original_msg_id = message_id


# 全域進度消息管理器實例
_progress_manager = ProgressMessageManager()


# Discord 工具函數
class DiscordTools:
    """Discord 特定工具集合"""
    
    @staticmethod
    async def send_progress_update(
        message: discord.Message,
        progress: DiscordProgressUpdate,
        edit_previous: bool = True,
        final_answer: Optional[str] = None
    ) -> Optional[discord.Message]:
        """發送或更新進度訊息，支援最終答案整合"""
        if edit_previous:
            return await _progress_manager.send_or_update_progress(message, progress, final_answer)
        else:
            # 如果不需要編輯，直接發送新消息
            try:
                progress_content = _progress_manager._format_progress_content(progress, final_answer)
                return await message.reply(content=progress_content, mention_author=False)
            except discord.HTTPException as e:
                print(f"發送進度更新失敗: {e}")
                return None
    
    @staticmethod
    def cleanup_progress_messages(channel_id: Optional[int] = None):
        """清理進度消息記錄"""
        if channel_id:
            _progress_manager.cleanup_progress_message(channel_id)
        else:
            _progress_manager.cleanup_all_progress_messages()
    
    @staticmethod
    def cleanup_message_tracking(message_id: int):
        """清理指定消息的追蹤記錄"""
        _progress_manager.cleanup_message_tracking(message_id)
    
    @staticmethod
    def cleanup_old_messages(max_age_seconds: int = 3600):
        """清理舊的消息追蹤記錄"""
        _progress_manager.cleanup_old_messages(max_age_seconds)
    
    @staticmethod
    def get_progress_message_by_original_id(original_message_id: int) -> Optional[discord.Message]:
        """根據原始消息ID獲取進度消息"""
        return _progress_manager.get_progress_message_by_original_id(original_message_id)
    
    @staticmethod
    async def update_progress_with_final_answer(
        original_message: discord.Message,
        final_answer: str
    ) -> Optional[discord.Message]:
        """將最終答案更新到現有的進度消息"""
        return await _progress_manager.update_with_final_answer(original_message, final_answer)
    
    @staticmethod
    def set_current_original_message_id(message_id: int):
        """設置當前處理的原始消息ID"""
        _progress_manager.set_current_original_message_id(message_id)
    
    @staticmethod
    def get_progress_manager_stats() -> Dict[str, Any]:
        """獲取進度管理器統計資訊"""
        return {
            "active_progress_messages": _progress_manager.get_active_progress_count(),
            "tracked_messages": _progress_manager.get_tracked_messages_count(),
            "manager_initialized": True
        }
    
    @staticmethod
    async def send_error_message(
        message: discord.Message,
        error: ErrorResponse
    ) -> Optional[discord.Message]:
        """發送錯誤訊息"""
        try:
            return await message.reply(
                content=error.user_friendly_message,
                mention_author=False
            )
        except discord.HTTPException as e:
            print(f"發送錯誤訊息失敗: {e}")
            return None
    
    @staticmethod
    def format_sources_for_discord(sources: List[ResearchSource], max_sources: int = 5) -> str:
        """格式化來源資訊為 Discord 訊息"""
        if not sources:
            return ""
        
        formatted_sources = []
        for i, source in enumerate(sources[:max_sources], 1):
            formatted_sources.append(f"{i}. [{source.title}]({source.url})")
        
        if len(sources) > max_sources:
            formatted_sources.append(f"... 還有 {len(sources) - max_sources} 個來源")
        
        return "\n".join(formatted_sources)
    
    @staticmethod
    def format_research_response(
        summary: str,
        sources: List[ResearchSource],
        max_length: int = 1900  # Discord 訊息限制
    ) -> str:
        """格式化研究回應為 Discord 訊息格式"""
        # 主要回應內容
        response = summary
        
        # 添加來源（如果有空間）
        if sources:
            sources_text = f"\n\n**參考來源：**\n{DiscordTools.format_sources_for_discord(sources)}"
            
            if len(response + sources_text) <= max_length:
                response += sources_text
            else:
                # 如果超過長度限制，縮短摘要
                available_length = max_length - len(sources_text) - 20  # 預留空間
                if available_length > 100:
                    response = response[:available_length] + "..."
                    response += sources_text
        
        return response
    
    @staticmethod
    def create_embed_response(
        summary: ResearchSummary,
        color: int = 0x7B68EE  # 淡紫色，符合初華的色調
    ) -> discord.Embed:
        """創建嵌入式回應"""
        embed = discord.Embed(
            title="🔍 研究結果",
            description=summary.summary[:4096],  # Discord embed 描述限制
            color=color
        )
        
        # 添加來源欄位
        if summary.sources:
            sources_text = DiscordTools.format_sources_for_discord(summary.sources, 3)
            embed.add_field(
                name="📚 參考來源",
                value=sources_text[:1024],  # Discord field 值限制
                inline=False
            )
        
        # 添加信心評分
        if summary.confidence_score is not None:
            confidence_emoji = "🌟" if summary.confidence_score > 0.8 else "⭐" if summary.confidence_score > 0.6 else "💫"
            embed.add_field(
                name="🎯 信心評分",
                value=f"{confidence_emoji} {summary.confidence_score:.1%}",
                inline=True
            )
        
        # 添加時間戳
        embed.add_field(
            name="⏰ 研究時間",
            value=summary.created_at,
            inline=True
        )
        
        # 設置縮圖（可選）
        embed.set_thumbnail(url="https://i.imgur.com/your_hatsuhana_avatar.png")  # 需要實際的圖片 URL
        
        return embed


# 資料驗證工具
class DataValidator:
    """資料驗證工具"""
    
    @staticmethod
    def validate_search_query(query: str) -> tuple[bool, str]:
        """驗證搜尋查詢"""
        if not query or len(query.strip()) == 0:
            return False, "搜尋查詢不能為空"
        
        if len(query) > 200:
            return False, "搜尋查詢過長"
        
        # 檢查是否包含不當內容的基本檢查
        banned_terms = ["illegal", "harmful"]  # 可擴展
        if any(term in query.lower() for term in banned_terms):
            return False, "搜尋查詢包含不當內容"
        
        return True, "查詢有效"
    
    @staticmethod
    def validate_discord_message_length(content: str) -> tuple[bool, str]:
        """驗證 Discord 訊息長度"""
        if len(content) > 2000:
            return False, f"訊息過長 ({len(content)}/2000 字元)"
        
        return True, "訊息長度有效"
    
    @staticmethod
    def sanitize_url(url: str) -> str:
        """清理 URL"""
        # 基本的 URL 清理
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        return url


# 錯誤處理工具
class ErrorHandler:
    """錯誤處理工具"""
    
    @staticmethod
    def create_user_friendly_error(
        error_type: str,
        technical_message: str
    ) -> ErrorResponse:
        """創建使用者友好的錯誤訊息"""
        friendly_messages = {
            "api_error": "抱歉，目前無法連接到搜尋服務 😅 讓我試試用其他方式回答妳",
            "timeout": "研究時間有點長呢... ⏰ 讓我先提供目前的結果",
            "invalid_query": "妳的問題我還不太理解 🤔 能再詳細一點嗎？",
            "rate_limit": "請求太頻繁了 😊 稍等一下再試試吧",
            "unknown": "遇到了一些技術問題 😅 不過我會盡力回答妳的"
        }
        
        user_message = friendly_messages.get(error_type, friendly_messages["unknown"])
        
        return ErrorResponse(
            error_type=error_type,
            error_message=technical_message,
            fallback_available=True,
            user_friendly_message=user_message
        )