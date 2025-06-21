"""
測試 message_collector.py 模組
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from discord_bot.message_collector import (
    collect_message, 
    _get_parent_message,
    ProcessedMessage,
    CollectedMessages
)
from discord_bot.message_manager import get_manager_instance


class TestMessageCollector:
    """測試訊息收集器"""
    
    @pytest.fixture
    def mock_discord_message(self):
        """創建模擬的 Discord 訊息"""
        msg = Mock()
        msg.id = 123456789
        msg.content = "測試訊息內容"
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.embeds = []
        msg.stickers = []  # 添加 stickers 屬性
        msg.reference = None
        return msg
    
    @pytest.fixture
    def mock_discord_client_user(self):
        """創建模擬的 Discord 客戶端用戶"""
        user = Mock()
        user.id = 555666777
        user.mention = "<@555666777>"
        return user
    
    @pytest.fixture
    def mock_parent_message(self):
        """創建模擬的父訊息"""
        msg = Mock()
        msg.id = 111111111
        msg.content = "父訊息內容"
        msg.author.id = 888999000
        msg.author.display_name = "父訊息用戶"
        msg.created_at = datetime.now()
        return msg
    
    @pytest.mark.asyncio
    async def test_get_parent_message_from_cache(self, mock_discord_message, mock_parent_message):
        """測試從快取中獲取父訊息"""
        # 設置訊息引用
        mock_discord_message.reference = Mock()
        mock_discord_message.reference.message_id = 111111111
        
        # 獲取 Discord 訊息管理器並添加父訊息到快取
        message_manager = get_manager_instance()
        message_manager.cache_message(mock_parent_message)
        
        # 測試從快取中查找父訊息
        result = await _get_parent_message(mock_discord_message)
        
        # 驗證返回的是快取中的訊息
        assert result == mock_parent_message
    
    @pytest.mark.asyncio
    async def test_get_parent_message_fallback_to_api(self, mock_discord_message):
        """測試當快取中沒有父訊息時，回退到 Discord API"""
        # 設置訊息引用
        mock_discord_message.reference = Mock()
        mock_discord_message.reference.message_id = 999999999
        
        # 模擬 Discord API 調用
        mock_parent = Mock()
        mock_parent.id = 999999999
        mock_discord_message.channel.fetch_message = AsyncMock(return_value=mock_parent)
        
        # 測試從 API 獲取父訊息
        result = await _get_parent_message(mock_discord_message)
        
        # 驗證 API 被調用
        mock_discord_message.channel.fetch_message.assert_called_once_with(999999999)
        assert result == mock_parent
        
        # 驗證訊息被加入快取
        message_manager = get_manager_instance()
        cached_message = message_manager.find_message_by_id(999999999)
        assert cached_message == mock_parent
    
    @pytest.mark.asyncio
    async def test_get_parent_message_no_reference(self, mock_discord_message):
        """測試沒有引用的訊息"""
        # 沒有設置 reference
        mock_discord_message.reference = None
        
        result = await _get_parent_message(mock_discord_message)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_collect_message_caches_messages(self, mock_discord_message, mock_discord_client_user):
        """測試 collect_message 正確快取訊息"""
        # 創建一個異步迭代器類
        class AsyncIterator:
            def __init__(self, items):
                self.items = items
                self.index = 0
            
            def __aiter__(self):
                return self
            
            async def __anext__(self):
                if self.index >= len(self.items):
                    raise StopAsyncIteration
                item = self.items[self.index]
                self.index += 1
                return item
        
        # 模擬頻道歷史 - 返回空的異步迭代器
        mock_discord_message.channel.history = Mock(return_value=AsyncIterator([]))
        
        # 調用 collect_message
        result = await collect_message(
            mock_discord_message,
            mock_discord_client_user,
            enable_conversation_history=True,
            httpx_client=None
        )
        
        # 驗證結果
        assert isinstance(result, CollectedMessages)
        assert len(result.messages) > 0
        
        # 驗證訊息被快取
        message_manager = get_manager_instance()
        cached_message = message_manager.find_message_by_id(mock_discord_message.id)
        assert cached_message == mock_discord_message
    
    def test_processed_message_creation(self):
        """測試 ProcessedMessage 創建"""
        msg = ProcessedMessage(
            content="測試內容",
            role="user",
            user_id=123456
        )
        
        assert msg.content == "測試內容"
        assert msg.role == "user"
        assert msg.user_id == 123456
    
    def test_collected_messages_methods(self):
        """測試 CollectedMessages 的便利方法"""
        from schemas.agent_types import MsgNode
        
        messages = [
            MsgNode(role="user", content="訊息1", metadata={"user_id": 111}),
            MsgNode(role="assistant", content="訊息2", metadata={}),
            MsgNode(role="user", content="訊息3", metadata={"user_id": 222})
        ]
        
        collected = CollectedMessages(messages=messages)
        
        # 測試訊息數量
        assert collected.message_count() == 3
        
        # 測試獲取最新訊息
        latest = collected.get_latest_message()
        assert latest.content == "訊息3"
        
        # 測試根據用戶 ID 獲取訊息
        user_messages = collected.get_messages_by_user_id(111)
        assert len(user_messages) == 1
        assert user_messages[0].content == "訊息1"
        
        # 測試迭代器
        message_contents = [msg.content for msg in collected.iter_messages()]
        assert message_contents == ["訊息1", "訊息2", "訊息3"]
        
        # 測試警告功能
        assert not collected.has_warnings()
        collected.add_warning("測試警告")
        assert collected.has_warnings()
        assert "測試警告" in collected.user_warnings
    
    def test_collected_messages_to_dict(self):
        """測試 CollectedMessages 轉換為字典"""
        from schemas.agent_types import MsgNode
        
        messages = [
            MsgNode(role="user", content="測試訊息", metadata={"user_id": 123})
        ]
        
        collected = CollectedMessages(messages=messages)
        collected.add_warning("測試警告")
        
        result_dict = collected.to_dict()
        
        assert "messages" in result_dict
        assert "user_warnings" in result_dict
        assert "collection_timestamp" in result_dict
        assert "message_count" in result_dict
        assert "has_warnings" in result_dict
        
        assert result_dict["message_count"] == 1
        assert result_dict["has_warnings"] is True
        assert "測試警告" in result_dict["user_warnings"] 