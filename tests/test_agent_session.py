"""
測試 agent_session.py 模組（現在是 Discord 訊息管理器）
"""

import pytest
import asyncio
from unittest.mock import Mock
from datetime import datetime, timedelta

from discord_bot.message_manager import MessageManager, MessageCache, get_manager_instance


class TestDiscordMessageCache:
    """測試 DiscordMessageCache 類別"""
    
    def test_cache_creation(self):
        """測試快取創建"""
        cache = MessageCache(
            messages={},
            last_updated=datetime.now()
        )
        
        assert len(cache.messages) == 0
        assert cache.max_size == 1000
    
    def test_add_message(self):
        """測試添加訊息"""
        cache = MessageCache(
            messages={},
            last_updated=datetime.now()
        )
        
        # 創建模擬的 Discord 訊息
        mock_message = Mock()
        mock_message.id = 123456789
        mock_message.content = "測試訊息"
        mock_message.created_at = datetime.now()
        
        cache.add_message(mock_message)
        
        assert len(cache.messages) == 1
        assert cache.messages[123456789] == mock_message
    
    def test_max_size_limit(self):
        """測試最大大小限制"""
        cache = MessageCache(
            messages={},
            last_updated=datetime.now(),
            max_size=3
        )
        
        # 添加超過最大大小的訊息
        for i in range(5):
            mock_message = Mock()
            mock_message.id = i
            mock_message.content = f"訊息 {i}"
            mock_message.created_at = datetime.now() + timedelta(seconds=i)
            cache.add_message(mock_message)
        
        assert len(cache.messages) == 3
        # 應該保留最新的 3 條訊息 (2, 3, 4)
        assert 2 in cache.messages
        assert 3 in cache.messages
        assert 4 in cache.messages
        assert 0 not in cache.messages
        assert 1 not in cache.messages
    
    def test_get_message_by_id(self):
        """測試根據 ID 獲取訊息"""
        cache = MessageCache(
            messages={},
            last_updated=datetime.now()
        )
        
        mock_message = Mock()
        mock_message.id = 123456789
        mock_message.content = "測試訊息"
        mock_message.created_at = datetime.now()
        
        cache.add_message(mock_message)
        
        found_message = cache.get_message_by_id(123456789)
        assert found_message == mock_message
        
        not_found = cache.get_message_by_id(999999999)
        assert not_found is None
    
    def test_get_recent_messages(self):
        """測試獲取最近訊息"""
        cache = MessageCache(
            messages={},
            last_updated=datetime.now()
        )
        
        # 添加多條訊息
        for i in range(10):
            mock_message = Mock()
            mock_message.id = i
            mock_message.content = f"訊息 {i}"
            mock_message.created_at = datetime.now() + timedelta(seconds=i)
            cache.add_message(mock_message)
        
        recent = cache.get_recent_messages(3)
        assert len(recent) == 3
        # 應該按時間倒序排列，最新的在前
        assert recent[0].id == 9
        assert recent[1].id == 8
        assert recent[2].id == 7
    
    def test_get_messages_by_channel(self):
        """測試獲取特定頻道的訊息"""
        cache = MessageCache(
            messages={},
            last_updated=datetime.now()
        )
        
        # 添加不同頻道的訊息
        for i in range(5):
            mock_message = Mock()
            mock_message.id = i
            mock_message.content = f"訊息 {i}"
            mock_message.created_at = datetime.now() + timedelta(seconds=i)
            mock_message.channel.id = 111 if i < 3 else 222
            cache.add_message(mock_message)
        
        channel_111_messages = cache.get_messages_by_channel(111, 10)
        assert len(channel_111_messages) == 3
        
        channel_222_messages = cache.get_messages_by_channel(222, 10)
        assert len(channel_222_messages) == 2
    
    def test_cleanup_old_messages(self):
        """測試清理舊訊息"""
        cache = MessageCache(
            messages={},
            last_updated=datetime.now()
        )
        
        # 添加新舊訊息
        old_time = datetime.now() - timedelta(hours=25)
        new_time = datetime.now()
        
        # 舊訊息
        old_message = Mock()
        old_message.id = 1
        old_message.created_at = old_time
        cache.add_message(old_message)
        
        # 新訊息
        new_message = Mock()
        new_message.id = 2
        new_message.created_at = new_time
        cache.add_message(new_message)
        
        # 清理 24 小時前的訊息
        cache.cleanup_old_messages(24)
        
        assert 1 not in cache.messages  # 舊訊息被清理
        assert 2 in cache.messages      # 新訊息保留


class TestDiscordMessageManager:
    """測試 DiscordMessageManager 類別"""
    
    def test_manager_creation(self):
        """測試訊息管理器創建"""
        manager = MessageManager()
        
        assert len(manager.cache.messages) == 0
        assert manager.cleanup_interval == 3600
        assert manager.message_retention_hours == 24
    
    def test_cache_message(self):
        """測試快取單一訊息"""
        manager = MessageManager()
        
        mock_message = Mock()
        mock_message.id = 123456789
        mock_message.content = "測試訊息"
        mock_message.created_at = datetime.now()
        
        manager.cache_message(mock_message)
        
        assert len(manager.cache.messages) == 1
        assert manager.cache.messages[123456789] == mock_message
    
    def test_cache_messages(self):
        """測試快取多條訊息"""
        manager = MessageManager()
        
        messages = []
        for i in range(3):
            mock_message = Mock()
            mock_message.id = i
            mock_message.content = f"訊息 {i}"
            mock_message.created_at = datetime.now()
            messages.append(mock_message)
        
        manager.cache_messages(messages)
        
        assert len(manager.cache.messages) == 3
    
    def test_find_message_by_id(self):
        """測試根據訊息 ID 查找訊息"""
        manager = MessageManager()
        
        mock_message = Mock()
        mock_message.id = 123456789
        mock_message.content = "測試訊息"
        mock_message.created_at = datetime.now()
        
        manager.cache_message(mock_message)
        
        found_message = manager.find_message_by_id(123456789)
        assert found_message == mock_message
        
        not_found = manager.find_message_by_id(999999999)
        assert not_found is None
    
    def test_get_recent_messages(self):
        """測試獲取最近訊息"""
        manager = MessageManager()
        
        # 添加多條訊息
        for i in range(5):
            mock_message = Mock()
            mock_message.id = i
            mock_message.content = f"訊息 {i}"
            mock_message.created_at = datetime.now() + timedelta(seconds=i)
            manager.cache_message(mock_message)
        
        recent = manager.get_recent_messages(3)
        assert len(recent) == 3
        assert recent[0].id == 4  # 最新的在前
    
    def test_get_messages_by_channel(self):
        """測試獲取特定頻道的訊息"""
        manager = MessageManager()
        
        # 添加不同頻道的訊息
        for i in range(5):
            mock_message = Mock()
            mock_message.id = i
            mock_message.content = f"訊息 {i}"
            mock_message.created_at = datetime.now()
            mock_message.channel.id = 111 if i < 3 else 222
            manager.cache_message(mock_message)
        
        channel_messages = manager.get_messages_by_channel(111, 10)
        assert len(channel_messages) == 3
    
    def test_get_cache_stats(self):
        """測試獲取快取統計"""
        manager = MessageManager()
        
        # 添加一些訊息
        for i in range(3):
            mock_message = Mock()
            mock_message.id = i
            mock_message.created_at = datetime.now()
            manager.cache_message(mock_message)
        
        stats = manager.get_cache_stats()
        assert stats["total_messages"] == 3
        assert stats["max_size"] == 1000
        assert "last_updated" in stats
    
    def test_cleanup_old_messages(self):
        """測試清理舊訊息"""
        manager = MessageManager(message_retention_hours=1)
        
        # 添加新舊訊息
        old_time = datetime.now() - timedelta(hours=2)
        new_time = datetime.now()
        
        old_message = Mock()
        old_message.id = 1
        old_message.created_at = old_time
        manager.cache_message(old_message)
        
        new_message = Mock()
        new_message.id = 2
        new_message.created_at = new_time
        manager.cache_message(new_message)
        
        manager.cleanup_old_messages()
        
        assert 1 not in manager.cache.messages
        assert 2 in manager.cache.messages


def test_get_manager_instance():
    """測試全域 Discord 訊息管理器獲取"""
    manager1 = get_manager_instance()
    manager2 = get_manager_instance()
    
    # 應該是同一個實例
    assert manager1 is manager2


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 