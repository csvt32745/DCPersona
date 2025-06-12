"""
測試 agent_session.py 模組
"""

import pytest
import asyncio
from datetime import datetime, timedelta

from agent_core.agent_session import AgentSession, SessionData, DiscordMessageCache, get_agent_session


class TestSessionData:
    """測試 SessionData 類別"""
    
    def test_session_data_creation(self):
        """測試會話資料創建"""
        session_data = SessionData(
            session_id="test_session",
            channel_id="123456",
            created_at=datetime.now(),
            last_activity=datetime.now(),
            message_count=0,
            is_active=True
        )
        
        assert session_data.session_id == "test_session"
        assert session_data.channel_id == "123456"
        assert session_data.is_active is True
        assert session_data.message_count == 0
    
    def test_session_data_to_dict(self):
        """測試會話資料序列化"""
        now = datetime.now()
        session_data = SessionData(
            session_id="test_session",
            channel_id="123456",
            created_at=now,
            last_activity=now,
            message_count=5,
            is_active=True
        )
        
        data_dict = session_data.to_dict()
        assert data_dict["session_id"] == "test_session"
        assert data_dict["message_count"] == 5
        assert isinstance(data_dict["created_at"], str)
    
    def test_session_data_from_dict(self):
        """測試會話資料反序列化"""
        now = datetime.now()
        original_data = {
            "session_id": "test_session",
            "channel_id": "123456",
            "created_at": now.isoformat(),
            "last_activity": now.isoformat(),
            "message_count": 3,
            "is_active": True,
            "langgraph_state": None,
            "cached_messages": None
        }
        
        session_data = SessionData.from_dict(original_data)
        assert session_data.session_id == "test_session"
        assert session_data.message_count == 3
        assert isinstance(session_data.created_at, datetime)
    
    def test_update_activity(self):
        """測試活動更新"""
        session_data = SessionData(
            session_id="test_session",
            channel_id="123456",
            created_at=datetime.now(),
            last_activity=datetime.now(),
            message_count=0,
            is_active=True
        )
        
        original_count = session_data.message_count
        original_time = session_data.last_activity
        
        # 等待一小段時間確保時間差異
        import time
        time.sleep(0.01)
        
        session_data.update_activity()
        
        assert session_data.message_count == original_count + 1
        assert session_data.last_activity > original_time
    
    def test_is_expired(self):
        """測試過期檢查"""
        # 創建過期的會話
        old_time = datetime.now() - timedelta(hours=25)
        session_data = SessionData(
            session_id="test_session",
            channel_id="123456",
            created_at=old_time,
            last_activity=old_time,
            message_count=0,
            is_active=True
        )
        
        assert session_data.is_expired(24) is True
        assert session_data.is_expired(26) is False


class TestDiscordMessageCache:
    """測試 DiscordMessageCache 類別"""
    
    def test_cache_creation(self):
        """測試快取創建"""
        cache = DiscordMessageCache(
            messages=[],
            last_updated=datetime.now()
        )
        
        assert len(cache.messages) == 0
        assert cache.max_size == 100
    
    def test_add_message(self):
        """測試添加訊息"""
        cache = DiscordMessageCache(
            messages=[],
            last_updated=datetime.now()
        )
        
        test_message = {"id": 123, "content": "測試訊息"}
        cache.add_message(test_message)
        
        assert len(cache.messages) == 1
        assert cache.messages[0] == test_message
    
    def test_max_size_limit(self):
        """測試最大大小限制"""
        cache = DiscordMessageCache(
            messages=[],
            last_updated=datetime.now(),
            max_size=3
        )
        
        # 添加超過最大大小的訊息
        for i in range(5):
            cache.add_message({"id": i, "content": f"訊息 {i}"})
        
        assert len(cache.messages) == 3
        # 應該保留最新的 3 條訊息 (2, 3, 4)
        assert cache.messages[0]["id"] == 2
        assert cache.messages[-1]["id"] == 4
    
    def test_get_recent_messages(self):
        """測試獲取最近訊息"""
        cache = DiscordMessageCache(
            messages=[],
            last_updated=datetime.now()
        )
        
        # 添加多條訊息
        for i in range(10):
            cache.add_message({"id": i, "content": f"訊息 {i}"})
        
        recent = cache.get_recent_messages(3)
        assert len(recent) == 3
        assert recent[0]["id"] == 7  # 最近 3 條: 7, 8, 9
        assert recent[-1]["id"] == 9


class TestAgentSession:
    """測試 AgentSession 類別"""
    
    def test_session_creation(self):
        """測試會話管理器創建"""
        session_manager = AgentSession()
        
        assert len(session_manager.sessions) == 0
        assert len(session_manager.cache) == 0
        assert session_manager.cleanup_interval == 3600
        assert session_manager.session_timeout_hours == 24
    
    def test_create_session(self):
        """測試創建會話"""
        session_manager = AgentSession()
        
        channel_id = "123456789"
        session_id = session_manager.create_session(channel_id)
        
        assert session_id.startswith("session_")
        assert session_id in session_manager.sessions
        assert session_id in session_manager.cache
        
        session = session_manager.get_session(session_id)
        assert session is not None
        assert session.channel_id == channel_id
        assert session.is_active is True
    
    def test_get_active_session_for_channel(self):
        """測試獲取頻道活躍會話"""
        session_manager = AgentSession()
        
        channel_id = "123456789"
        session_id = session_manager.create_session(channel_id)
        
        active_session = session_manager.get_active_session_for_channel(channel_id)
        assert active_session is not None
        assert active_session.session_id == session_id
        
        # 測試不存在的頻道
        no_session = session_manager.get_active_session_for_channel("999999")
        assert no_session is None
    
    def test_langgraph_state_management(self):
        """測試 LangGraph 狀態管理"""
        session_manager = AgentSession()
        
        session_id = session_manager.create_session("123456")
        
        # 測試獲取初始狀態
        initial_state = session_manager.get_langgraph_state(session_id)
        assert initial_state is not None
        assert "messages" in initial_state
        
        # 測試更新狀態
        new_state = {
            "messages": ["test_message"],
            "tool_calls": ["test_tool"],
            "current_round": 1
        }
        session_manager.update_langgraph_state(session_id, new_state)
        
        updated_state = session_manager.get_langgraph_state(session_id)
        assert updated_state == new_state
    
    def test_cache_discord_messages(self):
        """測試 Discord 訊息快取"""
        session_manager = AgentSession()
        
        session_id = session_manager.create_session("123456")
        
        test_messages = [
            {"id": 1, "content": "訊息 1"},
            {"id": 2, "content": "訊息 2"}
        ]
        
        session_manager.cache_discord_messages(session_id, test_messages)
        
        cached = session_manager.get_cached_messages(session_id, 10)
        assert len(cached) == 2
    
    def test_session_stats(self):
        """測試會話統計"""
        session_manager = AgentSession()
        
        # 創建幾個會話
        session_manager.create_session("123")
        session_manager.create_session("456")
        
        stats = session_manager.get_session_stats()
        assert stats["total_sessions"] == 2
        assert stats["active_sessions"] == 2
        assert stats["cache_size"] == 2
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self):
        """測試清理過期會話"""
        session_manager = AgentSession(session_timeout_hours=1)
        
        # 創建會話並手動設置為過期
        session_id = session_manager.create_session("123456")
        session = session_manager.get_session(session_id)
        session.last_activity = datetime.now() - timedelta(hours=2)
        
        await session_manager.cleanup_expired_sessions()
        
        # 檢查會話是否被清理
        assert session_id not in session_manager.sessions
        assert session_id not in session_manager.cache


def test_get_agent_session():
    """測試全域會話管理器獲取"""
    session1 = get_agent_session()
    session2 = get_agent_session()
    
    # 應該是同一個實例
    assert session1 is session2


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 