"""
Discord 進度消息管理模組

管理 Discord 進度消息的發送、更新和清理。
支援進度條、embed 格式和最終答案整合。
"""

import discord
import time
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from schemas.agent_types import DiscordProgressUpdate, ResearchSource
from agent_core.progress_types import ProgressStage
from utils.config_loader import load_typed_config

# 常數
EMBED_COLOR_COMPLETE = discord.Color.dark_green()
EMBED_COLOR_INCOMPLETE = discord.Color.orange()
EMBED_COLOR_ERROR = discord.Color.red()


class ProgressManager:
    """Discord 進度消息管理器 (簡化版)"""
    
    def __init__(self):
        # 追蹤每個原始訊息的進度消息 {original_message_id: progress_message}
        # 改用 message_id 作為主鍵，避免同頻道多訊息的 race condition
        self._progress_messages: Dict[int, discord.Message] = {}
        
        # 追蹤原始消息到進度消息的映射 {original_message_id: progress_message}
        # 保持此欄位以維持向後相容性
        self._message_to_progress: Dict[int, discord.Message] = {}
        
        # 記錄消息創建時間
        self._message_timestamps: Dict[int, float] = {}
        
        # 異步鎖，保護共享資料結構的並發存取
        self._lock = asyncio.Lock()
        
        self.logger = logging.getLogger(__name__)
        
        # 載入配置
        self.config = load_typed_config()
    
    async def send_or_update_progress(
        self,
        original_message: discord.Message,
        progress: DiscordProgressUpdate,
        final_answer: Optional[str] = None,
        sources: Optional[List[ResearchSource]] = None
    ) -> Optional[discord.Message]:
        """
        發送新的進度消息或更新現有消息
        
        Args:
            original_message: 原始 Discord 訊息
            progress: 進度更新資料
            final_answer: 最終答案（可選）
            sources: 研究來源列表（可選）
        
        Returns:
            Optional[discord.Message]: 進度消息或 None
        """
        async with self._lock:  # 使用鎖保護所有共享資料的操作
            try:
                message_id = original_message.id
                
                # 檢查是否已有該訊息的進度消息
                existing_progress_msg = self._progress_messages.get(message_id)
                
                # 創建 embed 內容
                embed_content = self._create_progress_embed(progress, final_answer, sources)
                
                if existing_progress_msg:
                    try:
                        # 嘗試編輯現有進度消息
                        if embed_content:
                            await existing_progress_msg.edit(content=None, embed=embed_content)
                        else:
                            # 回退到純文字格式
                            content = self._format_progress_content(progress, final_answer)
                            await existing_progress_msg.edit(content=content, embed=None)
                        return existing_progress_msg
                    except (discord.NotFound, discord.HTTPException, discord.Forbidden):
                        # 如果編輯失敗，移除記錄並發送新消息
                        self._progress_messages.pop(message_id, None)
                        self._message_to_progress.pop(message_id, None)
                        self._message_timestamps.pop(message_id, None)
                
                # 發送新的進度消息
                if embed_content:
                    progress_msg = await original_message.reply(
                        embed=embed_content,
                        silent=True
                    )
                else:
                    # 回退到純文字格式
                    content = self._format_progress_content(progress, final_answer)
                    progress_msg = await original_message.reply(
                        content=content,
                        silent=True
                    )
                
                # 記錄新的進度消息（使用 message_id 作為主鍵）
                self._progress_messages[message_id] = progress_msg
                self._message_to_progress[message_id] = progress_msg
                self._message_timestamps[message_id] = time.time()
                
                return progress_msg
                
            except discord.HTTPException as e:
                self.logger.error(f"發送進度更新失敗: {e}")
                return None
    
    def _create_progress_embed(
        self,
        progress: DiscordProgressUpdate,
        final_answer: Optional[str] = None,
        sources: Optional[List[ResearchSource]] = None
    ) -> Optional[discord.Embed]:
        """創建進度 embed"""
        try:
            # 決定顏色
            if progress.stage == ProgressStage.COMPLETED:
                color = EMBED_COLOR_COMPLETE
            elif progress.stage in [ProgressStage.ERROR, ProgressStage.TIMEOUT]:
                color = EMBED_COLOR_ERROR
            else:
                color = EMBED_COLOR_INCOMPLETE
            
            embed = discord.Embed(color=color)
            
            if progress.stage == ProgressStage.COMPLETED and final_answer:
                # 完成狀態：顯示最終答案
                embed.description = final_answer[:4096]  # Discord embed 描述限制
                
                # 添加來源資訊
                if sources:
                    sources_text = self._format_sources_for_embed(sources)
                    if sources_text:
                        embed.add_field(
                            name="📚 參考來源",
                            value=sources_text,
                            inline=False
                        )
            elif progress.stage == ProgressStage.STREAMING and final_answer:
                # 串流狀態：顯示串流內容
                embed.description = final_answer[:4096]  # Discord embed 描述限制
                embed.set_footer(text="🔄 正在回答...")
            else:
                # 進度狀態：顯示進度訊息，優先使用 progress.message，否則從配置載入
                message = progress.message
                if not message:
                    message = self.config.progress.discord.messages.get(progress.stage.value, progress.stage.value)
                embed.description = message
                
                # 添加進度條
                if progress.progress_percentage is not None:
                    progress_bar = self._create_progress_bar(progress.progress_percentage)
                    embed.description += f"\n{progress_bar} {progress.progress_percentage}%"
                
                # 添加詳細資訊（如工具清單）
                if progress.details:
                    embed.description += f"\n\n{progress.details}"
                
                # 添加預估時間
                if progress.eta_seconds is not None and progress.eta_seconds > 0:
                    eta_text = self._format_eta(progress.eta_seconds)
                    embed.add_field(
                        name="⏱️ 預估剩餘時間",
                        value=eta_text,
                        inline=True
                    )
            
            return embed
            
        except Exception as e:
            self.logger.error(f"創建進度 embed 失敗: {e}")
            return None
    
    def _format_sources_for_embed(self, sources: List[ResearchSource], max_sources: int = 3) -> str:
        """格式化來源資訊為 embed field 格式"""
        if not sources:
            return ""
        
        formatted_sources = []
        for i, source in enumerate(sources[:max_sources], 1):
            title = source.title
            url = source.url
            # 限制標題長度
            if len(title) > 50:
                title = title[:47] + "..."
            formatted_sources.append(f"{i}. [{title}]({url})")
        
        if len(sources) > max_sources:
            formatted_sources.append(f"... 還有 {len(sources) - max_sources} 個來源")
        
        return "\n".join(formatted_sources)
    
    def _format_progress_content(
        self, 
        progress: DiscordProgressUpdate, 
        final_answer: Optional[str] = None
    ) -> str:
        """格式化純文字進度內容"""
        if progress.stage == ProgressStage.COMPLETED and final_answer:
            return f"✅ **完成**\n\n{final_answer}"
        
        # 優先使用 progress.message，如果為空則從配置載入
        message = progress.message
        if not message:
            message = self.config.progress.discord.messages.get(progress.stage.value, progress.stage.value)
        
        content = f"**{message}**"
        
        if progress.progress_percentage is not None:
            progress_bar = self._create_progress_bar(progress.progress_percentage)
            content += f"\n{progress_bar} {progress.progress_percentage}%"
        
        return content
    
    def _create_progress_bar(self, percentage: int, length: int = 10) -> str:
        """創建進度條"""
        filled = int(percentage / 100 * length)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}]"
    
    def _format_eta(self, seconds: int) -> str:
        """格式化預估時間"""
        if seconds < 60:
            return f"{seconds} 秒"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} 分鐘"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours} 小時 {minutes} 分鐘"
    
    def cleanup_by_message_id(self, message_id: int):
        """根據訊息 ID 清理進度消息記錄（新的主要清理方法）"""
        self._progress_messages.pop(message_id, None)
        self._message_to_progress.pop(message_id, None)
        self._message_timestamps.pop(message_id, None)
        self.logger.debug(f"清理訊息 {message_id} 的所有進度記錄")

    def cleanup_progress_message(self, channel_id: int):
        """清理特定頻道的進度消息記錄（保留以維持向後相容性）"""
        # 改為清理該頻道所有相關的訊息
        to_remove = []
        for msg_id, progress_msg in self._progress_messages.items():
            if progress_msg and hasattr(progress_msg, 'channel') and progress_msg.channel.id == channel_id:
                to_remove.append(msg_id)
        
        for msg_id in to_remove:
            self.cleanup_by_message_id(msg_id)
        
        self.logger.debug(f"清理頻道 {channel_id} 的 {len(to_remove)} 個進度消息記錄")
    
    def cleanup_message_tracking(self, message_id: int):
        """清理指定消息的追蹤記錄（保留以維持向後相容性）"""
        # 現在直接調用新的清理方法
        self.cleanup_by_message_id(message_id)
    
    def cleanup_old_messages(self, max_age_seconds: int = 3600):
        """清理舊的消息記錄"""
        current_time = time.time()
        expired_messages = [
            msg_id for msg_id, timestamp in self._message_timestamps.items()
            if current_time - timestamp > max_age_seconds
        ]
        
        for msg_id in expired_messages:
            self.cleanup_by_message_id(msg_id)
        
        if expired_messages:
            self.logger.info(f"清理了 {len(expired_messages)} 個過期的進度消息記錄")
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取統計資訊"""
        return {
            'active_progress_count': len(self._progress_messages),
            'tracked_messages_count': len(self._message_to_progress),
            'timestamps_count': len(self._message_timestamps)
        }


# 全域進度管理器實例
_progress_manager = None

def get_progress_manager() -> ProgressManager:
    """獲取全域進度管理器實例"""
    global _progress_manager
    if _progress_manager is None:
        _progress_manager = ProgressManager()
    return _progress_manager


# 便利函數
async def send_progress_update(
    message: discord.Message,
    progress: DiscordProgressUpdate,
    final_answer: Optional[str] = None,
    sources: Optional[List[ResearchSource]] = None
) -> Optional[discord.Message]:
    """發送進度更新的便利函數"""
    manager = get_progress_manager()
    return await manager.send_or_update_progress(message, progress, final_answer, sources)


def cleanup_progress_messages(channel_id: Optional[int] = None):
    """清理進度消息的便利函數"""
    manager = get_progress_manager()
    if channel_id:
        manager.cleanup_progress_message(channel_id)
    else:
        # 清理所有記錄
        manager._progress_messages.clear()
        manager._message_to_progress.clear()
        manager._message_timestamps.clear() 