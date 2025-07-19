"""
Discord 進度適配器

將通用的進度事件轉換為 Discord 特定的進度更新，實現與現有進度管理系統的整合。
"""

import logging
import time
from typing import Optional, List, Dict, Any
import asyncio
import discord

from agent_core.progress_observer import ProgressObserver, ProgressEvent
from agent_core.progress_types import ProgressStage, ToolStatus, TOOL_STATUS_SYMBOLS
from schemas.agent_types import DiscordProgressUpdate, ResearchSource
from .progress_manager import get_progress_manager
from utils.config_loader import load_typed_config
from output_media.emoji_registry import EmojiRegistry


class DiscordProgressAdapter(ProgressObserver):
    """Discord 進度適配器
    
    實現 ProgressObserver 介面，將通用進度事件轉換為 Discord 特定的進度更新。
    與現有的 progress_manager 系統整合。
    """
    
    def __init__(self, original_message: discord.Message, emoji_handler: Optional[EmojiRegistry] = None):
        """
        初始化 Discord 進度適配器
        
        Args:
            original_message: 觸發 Agent 處理的原始 Discord 訊息
            emoji_handler: 可選的 emoji 處理器實例
        """
        self.original_message = original_message
        self.emoji_handler = emoji_handler
        self.progress_manager = get_progress_manager()
        self.logger = logging.getLogger(__name__)
        self.config = load_typed_config()
        
        # 追蹤最後發送的進度訊息
        self._last_progress_message: Optional[discord.Message] = None
        
        # 串流相關狀態
        self._streaming_content = ""
        self._last_update = 0
        self._streaming_message: Optional[discord.Message] = None
        self._update_lock = asyncio.Lock()
        self._tool_state_lock = asyncio.Lock()   # <--- 新增

        # Phase3: 工具清單進度追蹤
        # tool_name -> status (使用 ToolStatus enum)
        self.tool_states: Dict[str, ToolStatus] = {}
        self._last_tool_update = 0.0  # 最後一次工具進度渲染時間
        
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
            
            # 特殊處理 Phase3 工具進度事件
            if event.stage == ProgressStage.TOOL_LIST:
                async with self._tool_state_lock:
                    todo_tools = event.metadata.get("todo", []) if event.metadata else []
                    self.tool_states = {tool: ToolStatus.PENDING for tool in todo_tools}

            if event.stage == ProgressStage.TOOL_STATUS:
                tool_name = event.metadata.get("tool") if event.metadata else None
                status = event.metadata.get("status") if event.metadata else None
                if tool_name and status:
                    async with self._tool_state_lock:
                        # 直接使用 ToolStatus enum
                        self.tool_states[tool_name] = status

            # 如果正在串流，則不顯示一般進度更新
            if self._streaming_message:
                return

            # 組合工具清單（如果有的話）
            tool_list_str = ""
            async with self._tool_state_lock:
                tool_list_str = self._compose_tool_list_str()

            # 檢查是否有自訂訊息，如果沒有則從配置載入
            message = event.message
            if not message:
                # 從配置載入訊息
                stage_str = event.stage.value if hasattr(event.stage, 'value') else event.stage
                message = self.config.progress.discord.messages.get(stage_str, stage_str)
            
            # emoji 處理已不需要，因為 LLM 直接生成正確格式

            # 轉換為 Discord 進度更新格式
            discord_progress = DiscordProgressUpdate(
                stage=event.stage,
                message=message,
                progress_percentage=event.progress_percentage,
                eta_seconds=event.eta_seconds,
                details=tool_list_str if tool_list_str else None
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

    def _compose_tool_list_str(self) -> str:
        """組合工具進度清單字串，只回傳字串不發送訊息"""
        if not self.tool_states:
            return ""

        # 直接以 dict 插入順序產生無序列表，使用 TOOL_STATUS_SYMBOLS 映射
        lines = [f"• {TOOL_STATUS_SYMBOLS.get(status, '⚪')} {tool}" for tool, status in self.tool_states.items()]
        content = "\n".join(lines)
        return f"🛠️ 工具進度\n{content}"
    
    async def on_streaming_chunk(self, content: str, is_final: bool = False) -> None:
        """處理串流內容塊
        
        Args:
            content: 串流內容
            is_final: 是否為最終塊
        """
        async with self._update_lock:
            self._streaming_content += content
            
            current_time = time.time()
            update_interval = self.config.progress.discord.update_interval
            
            # 根據配置的更新間隔決定是否更新
            should_update = (
                (current_time - self._last_update >= update_interval) or 
                is_final or  # 直接使用 is_final
                len(self._streaming_content) > 1500  # Discord 字符限制考量
            )
            
            if should_update:
                await self._update_streaming_message()
                self._last_update = current_time
    
    async def on_streaming_complete(self) -> None:
        """處理串流完成"""
        async with self._update_lock:
            if self._streaming_content:
                try:
                    # 使用 progress_manager 發送最終的串流內容
                    completion_progress = DiscordProgressUpdate(
                        stage="completed",
                        message="✅ 回答完成",
                        progress_percentage=100
                    )
                    
                    # 格式化 emoji 輸出
                    formatted_content = self._streaming_content
                    # emoji 處理已不需要，因為 LLM 直接生成正確格式
                    
                    await self.progress_manager.send_or_update_progress(
                        original_message=self.original_message,
                        progress=completion_progress,
                        final_answer=formatted_content
                    )
                except Exception as e:
                    self.logger.error(f"串流完成事件處理失敗: {e}")
                finally:
                    # 無論成功或失敗都清理串流狀態
                    self._streaming_message = None
    
    async def _update_streaming_message(self):
        """更新串流訊息"""
        try:
            # 截斷過長的內容
            display_content = self._streaming_content
            if len(display_content) > 1800:
                display_content = display_content[:1800] + "..."
            
            # emoji 處理已不需要，因為 LLM 直接生成正確格式
            
            # 使用 progress_manager 更新串流進度
            streaming_progress = DiscordProgressUpdate(
                stage="streaming",
                message="🔄 正在回答...",
                progress_percentage=None  # 串流模式不顯示百分比
            )
            
            # 將串流內容作為 final_answer 傳遞，但標記為進行中
            result_message = await self.progress_manager.send_or_update_progress(
                original_message=self.original_message,
                progress=streaming_progress,
                final_answer=display_content + " ⚪"  # 串流指示器
            )
            
            # 記錄串流訊息以便後續更新
            if result_message and not self._streaming_message:
                self._streaming_message = result_message
                
        except Exception as e:
            self.logger.error(f"串流訊息處理失敗: {e}")
    
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
            
            # 如果正在串流，則不使用傳統的完成事件處理
            if self._streaming_message:
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
            
            # emoji 處理已不需要，因為 LLM 直接生成正確格式
            formatted_result = final_result
            
            # 發送完成更新
            await self.progress_manager.send_or_update_progress(
                original_message=self.original_message,
                progress=completion_progress,
                final_answer=formatted_result,
                sources=research_sources
            )
            
            self.logger.info("Discord 完成事件已處理")
            
        except Exception as e:
            self.logger.error(f"Discord 完成事件處理失敗: {e}")
    
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
                # 使用 progress_manager 作為備用方案
                fallback_progress = DiscordProgressUpdate(
                    stage="error",
                    message="❌ 處理時發生錯誤（備用模式）",
                    progress_percentage=0
                )
                await self.progress_manager.send_or_update_progress(
                    original_message=self.original_message,
                    progress=fallback_progress,
                    final_answer="抱歉，處理您的請求時發生錯誤。請稍後再試。"
                )
            except Exception as e:
                self.logger.error(f"Discord 錯誤事件處理失敗: {e}")
    
    def get_last_progress_message(self) -> Optional[discord.Message]:
        """獲取最後發送的進度訊息
        
        Returns:
            Optional[discord.Message]: 最後的進度訊息，如果沒有則返回 None
        """
        return self._last_progress_message
    
    async def cleanup(self):
        """清理資源"""
        try:
            # 使用新的 cleanup_by_message_id 方法清理進度管理器中的訊息
            if hasattr(self, 'progress_manager') and self.progress_manager:
                message_id = self.original_message.id
                self.progress_manager.cleanup_by_message_id(message_id)
        except Exception as e:
            self.logger.warning(f"清理進度訊息失敗: {e}")
        
        # 清理串流相關狀態
        self._streaming_content = ""
        self._streaming_message = None
        self._last_progress_message = None 