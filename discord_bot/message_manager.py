"""
Discord 訊息快取系統

統一管理 Discord 訊息快取，支援訊息存儲、查找和自動清理。
不再使用 session 概念，直接以 Discord message ID 為索引。
"""

import asyncio
import logging
import discord
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class MessageCache:
    """訊息快取結構"""
    messages: Dict[int, discord.Message]  # message_id -> discord.Message
    """訊息字典，以 Discord message ID 為鍵，discord.Message 物件為值"""
    
    last_updated: datetime
    """最後更新時間"""
    
    max_size: int = 1000
    """最大快取大小"""
    
    def add_message(self, message: discord.Message):
        """添加訊息到快取
        
        Args:
            message: Discord 訊息物件
        """
        self.messages[message.id] = message
        
        # 如果超過最大大小，移除最舊的訊息
        if len(self.messages) > self.max_size:
            # 按創建時間排序，移除最舊的訊息
            sorted_messages = sorted(
                self.messages.items(), 
                key=lambda x: x[1].created_at
            )
            # 保留最新的 max_size 條訊息
            messages_to_keep = dict(sorted_messages[-self.max_size:])
            self.messages = messages_to_keep
        
        self.last_updated = datetime.now()
    
    def get_message_by_id(self, message_id: int) -> Optional[discord.Message]:
        """根據 ID 獲取訊息
        
        Args:
            message_id: Discord 訊息 ID
            
        Returns:
            Optional[discord.Message]: 找到的訊息或 None
        """
        return self.messages.get(message_id)
    
    def get_recent_messages(self, count: int = 10) -> List[discord.Message]:
        """獲取最近的訊息
        
        Args:
            count: 返回的訊息數量
            
        Returns:
            List[discord.Message]: 最近的訊息列表
        """
        sorted_messages = sorted(
            self.messages.values(), 
            key=lambda x: x.created_at, 
            reverse=True
        )
        return sorted_messages[:count]
    
    def get_messages_by_channel(self, channel_id: int, count: int = 10) -> List[discord.Message]:
        """獲取特定頻道的訊息
        
        Args:
            channel_id: 頻道 ID
            count: 返回的訊息數量
            
        Returns:
            List[discord.Message]: 該頻道的訊息列表
        """
        channel_messages = [
            msg for msg in self.messages.values() 
            if msg.channel.id == channel_id
        ]
        # 按時間排序，最新的在前
        channel_messages.sort(key=lambda x: x.created_at, reverse=True)
        return channel_messages[:count]
    
    def cleanup_old_messages(self, hours: int = 24):
        """清理舊訊息
        
        Args:
            hours: 保留訊息的小時數
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # 找出需要清理的訊息
        messages_to_remove = [
            msg_id for msg_id, msg in self.messages.items()
            if msg.created_at.replace(tzinfo=None) < cutoff_time
        ]
        
        # 移除舊訊息
        for msg_id in messages_to_remove:
            self.messages.pop(msg_id, None)
        
        if messages_to_remove:
            logging.info(f"清理了 {len(messages_to_remove)} 條舊訊息")


class MessageManager:
    """Discord 訊息管理器"""
    
    def __init__(self, cleanup_interval: int = 3600, message_retention_hours: int = 24):
        """
        初始化訊息管理器
        
        Args:
            cleanup_interval: 清理間隔（秒）
            message_retention_hours: 訊息保留時間（小時）
        """
        self.cache = MessageCache(
            messages={},
            last_updated=datetime.now()
        )
        
        self.cleanup_interval = cleanup_interval
        self.message_retention_hours = message_retention_hours
        self.logger = logging.getLogger(__name__)
        
        # 啟動定期清理任務
        self._cleanup_task = None
        # 只在有運行的事件循環時才啟動清理任務
        try:
            asyncio.get_running_loop()
            self._start_cleanup_task()
        except RuntimeError:
            # 沒有運行的事件循環，稍後再啟動
            pass
    
    def _start_cleanup_task(self):
        """啟動清理任務"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """定期清理過期訊息"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                self.cleanup_old_messages()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"清理任務出錯: {e}")
    
    def cache_message(self, message: discord.Message):
        """快取單一訊息
        
        Args:
            message: Discord 訊息物件
        """
        self.cache.add_message(message)
        self.logger.debug(f"快取訊息: {message.id}")
    
    def cache_messages(self, messages: List[discord.Message]):
        """快取多條訊息
        
        Args:
            messages: Discord 訊息物件列表
        """
        for message in messages:
            self.cache.add_message(message)
        self.logger.debug(f"快取 {len(messages)} 條訊息")
    
    def find_message_by_id(self, message_id: int) -> Optional[discord.Message]:
        """根據訊息 ID 查找快取中的訊息
        
        Args:
            message_id: Discord 訊息 ID
            
        Returns:
            Optional[discord.Message]: 找到的訊息或 None
        """
        return self.cache.get_message_by_id(message_id)
    
    def get_recent_messages(self, count: int = 10) -> List[discord.Message]:
        """獲取最近的訊息
        
        Args:
            count: 返回的訊息數量
            
        Returns:
            List[discord.Message]: 最近的訊息列表
        """
        return self.cache.get_recent_messages(count)
    
    def get_messages_by_channel(self, channel_id: int, count: int = 10) -> List[discord.Message]:
        """獲取特定頻道的訊息
        
        Args:
            channel_id: 頻道 ID
            count: 返回的訊息數量
            
        Returns:
            List[discord.Message]: 該頻道的訊息列表
        """
        return self.cache.get_messages_by_channel(channel_id, count)
    
    def cleanup_old_messages(self):
        """清理舊訊息"""
        self.cache.cleanup_old_messages(self.message_retention_hours)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """獲取快取統計資訊
        
        Returns:
            Dict: 統計資訊
        """
        return {
            'total_messages': len(self.cache.messages),
            'last_updated': self.cache.last_updated.isoformat(),
            'max_size': self.cache.max_size
        }
    
    async def shutdown(self):
        """關閉訊息管理器"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Discord 訊息管理器已關閉")


# 全域訊息管理器實例
_message_manager = None

def get_manager_instance() -> MessageManager:
    """獲取全域 Discord 訊息管理器實例"""
    global _message_manager
    if _message_manager is None:
        _message_manager = MessageManager()
    return _message_manager 