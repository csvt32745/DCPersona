"""
Discord 進度適配器

將通用的進度事件轉換為 Discord 特定的進度更新，實現與現有進度管理系統的整合。
"""

import logging
from typing import Optional, List, Dict, Any
import asyncio
import discord

from agent_core.progress_observer import ProgressObserver, ProgressEvent
from schemas.agent_types import DiscordProgressUpdate, ResearchSource
from .progress_manager import get_progress_manager


class DiscordProgressAdapter(ProgressObserver):
    """Discord 進度適配器
    
    實現 ProgressObserver 介面，將通用進度事件轉換為 Discord 特定的進度更新。
    與現有的 progress_manager 系統整合。
    """
    
    def __init__(self, original_message: discord.Message):
        """
        初始化 Discord 進度適配器
        
        Args:
            original_message: 觸發 Agent 處理的原始 Discord 訊息
        """
        self.original_message = original_message
        self.progress_manager = get_progress_manager()
        self.logger = logging.getLogger(__name__)
        
        # 追蹤最後發送的進度訊息
        self._last_progress_message: Optional[discord.Message] = None
        
    async def on_progress_update(self, event: ProgressEvent) -> None:
        """處理進度更新事件
        
        將通用 ProgressEvent 轉換為 Discord 特定格式並發送
        
        Args:
            event: 進度事件
        """
        try:
            # 檢查是否在合適的異步上下文中
            try:
                # 嘗試獲取當前運行的事件循環
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                # 沒有運行的事件循環，記錄但不嘗試發送 Discord 更新
                self.logger.warning(f"跳過 Discord 進度更新（無事件循環）: {event.stage} - {event.message}")
                return
            
            # 轉換為 Discord 進度更新格式
            discord_progress = DiscordProgressUpdate(
                stage=event.stage,
                message=event.message,
                progress_percentage=event.progress_percentage,
                eta_seconds=event.eta_seconds
            )
            
            # 使用現有的進度管理器發送更新
            self._last_progress_message = await self.progress_manager.send_or_update_progress(
                original_message=self.original_message,
                progress=discord_progress
            )
            
            self.logger.debug(f"Discord 進度更新已發送: {event.stage} - {event.message}")
            
        except RuntimeError as e:
            if "Timeout context manager should be used inside a task" in str(e):
                self.logger.warning(f"跳過 Discord 進度更新（事件循環上下文問題）: {event.stage} - {event.message}")
            else:
                self.logger.error(f"Discord 進度更新失敗: {e}")
        except Exception as e:
            self.logger.error(f"Discord 進度更新失敗: {e}", exc_info=True)
    
    async def on_completion(self, final_result: str, sources: Optional[List[Dict]] = None) -> None:
        """處理完成事件
        
        發送完成狀態並準備最終回答的發送
        
        Args:
            final_result: 最終生成的回答
            sources: 研究來源清單（可選）
        """
        try:
            # 檢查是否在合適的異步上下文中
            import asyncio
            try:
                # 嘗試獲取當前運行的事件循環
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                # 沒有運行的事件循環，記錄但不嘗試發送 Discord 更新
                self.logger.warning("跳過 Discord 完成事件（無事件循環）")
                return
            
            # 創建完成進度更新
            completion_progress = DiscordProgressUpdate(
                stage="completed",
                message="✅ 研究完成！正在準備回答...",
                progress_percentage=100
            )
            
            # 轉換來源格式
            research_sources = []
            if sources:
                research_sources = [
                    ResearchSource(
                        title=source.get("title", "未知來源"),
                        url=source.get("url", ""),
                        snippet=source.get("snippet", "")
                    )
                    for source in sources[:5]  # 限制最多5個來源
                ]
            
            # 發送完成更新
            await self.progress_manager.send_or_update_progress(
                original_message=self.original_message,
                progress=completion_progress,
                final_answer=final_result,
                sources=research_sources
            )
            
            self.logger.info("Discord 完成事件已處理")
            
        except RuntimeError as e:
            if "Timeout context manager should be used inside a task" in str(e):
                self.logger.warning("跳過 Discord 完成事件（事件循環上下文問題）")
            else:
                self.logger.error(f"Discord 完成事件處理失敗: {e}")
        except Exception as e:
            self.logger.error(f"Discord 完成事件處理失敗: {e}", exc_info=True)
            
            # 備用方案：直接回覆原訊息（但只在有合適事件循環時）
            try:
                import asyncio
                asyncio.get_running_loop()  # 檢查事件循環
                await self.original_message.reply(final_result[:2000])  # Discord 訊息長度限制
            except RuntimeError:
                self.logger.warning("跳過備用回覆方案（無事件循環）")
            except Exception as backup_error:
                self.logger.error(f"備用回覆方案也失敗: {backup_error}")
    
    async def on_error(self, error: Exception) -> None:
        """處理錯誤事件
        
        發送錯誤狀態並通知用戶
        
        Args:
            error: 發生的異常
        """
        try:
            # 檢查是否在合適的異步上下文中
            import asyncio
            try:
                # 嘗試獲取當前運行的事件循環
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                # 沒有運行的事件循環，記錄但不嘗試發送 Discord 更新
                self.logger.warning("跳過 Discord 錯誤事件（無事件循環）")
                return
            
            # 創建錯誤進度更新
            error_progress = DiscordProgressUpdate(
                stage="error",
                message="❌ 處理時發生錯誤",
                progress_percentage=0
            )
            
            # 發送錯誤更新
            await self.progress_manager.send_or_update_progress(
                original_message=self.original_message,
                progress=error_progress,
                final_answer="抱歉，處理您的請求時發生錯誤。請稍後再試。"
            )
            
            self.logger.error(f"Discord 錯誤事件已處理: {error}")
            
        except RuntimeError as e:
            if "Timeout context manager should be used inside a task" in str(e):
                self.logger.warning("跳過 Discord 錯誤事件（事件循環上下文問題）")
            else:
                self.logger.error(f"Discord 錯誤事件處理失敗: {e}")
        except Exception as e:
            self.logger.error(f"Discord 錯誤事件處理失敗: {e}", exc_info=True)
            
            # 備用方案：直接回覆原訊息（但只在有合適事件循環時）
            try:
                import asyncio
                asyncio.get_running_loop()  # 檢查事件循環
                await self.original_message.reply("抱歉，處理您的請求時發生錯誤。請稍後再試。")
            except RuntimeError:
                self.logger.warning("跳過備用錯誤回覆方案（無事件循環）")
            except Exception as backup_error:
                self.logger.error(f"備用錯誤回覆方案也失敗: {backup_error}")
    
    def get_last_progress_message(self) -> Optional[discord.Message]:
        """獲取最後發送的進度訊息
        
        Returns:
            最後發送的進度訊息，如果沒有則返回 None
        """
        return self._last_progress_message
    
    async def cleanup(self):
        """清理進度適配器資源
        
        移除進度訊息等清理工作
        """
        try:
            # 檢查是否在合適的異步上下文中
            import asyncio
            try:
                # 嘗試獲取當前運行的事件循環
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                # 沒有運行的事件循環，記錄但不嘗試 Discord 操作
                self.logger.warning("跳過 Discord 進度適配器清理（無事件循環）")
                return
            
            if self._last_progress_message:
                # 使用進度管理器的清理功能
                # cleanup_progress_message 是同步方法，不需要 await
                # 並且需要傳遞 channel_id 而不是 message 對象
                self.progress_manager.cleanup_progress_message(self._last_progress_message.channel.id)
                self._last_progress_message = None
                
            self.logger.debug("Discord 進度適配器清理完成")
            
        except RuntimeError as e:
            if "Timeout context manager should be used inside a task" in str(e):
                self.logger.warning("跳過 Discord 進度適配器清理（事件循環上下文問題）")
            else:
                self.logger.error(f"Discord 進度適配器清理失敗: {e}")
        except Exception as e:
            self.logger.error(f"Discord 進度適配器清理失敗: {e}", exc_info=True) 