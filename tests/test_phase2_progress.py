"""
Phase 2 進度更新功能測試

測試進度觀察者模式、Discord 適配器和配置系統的整合
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

# 測試進度觀察者介面
def test_progress_event_creation():
    """測試進度事件建立"""
    from agent_core.progress_observer import ProgressEvent
    
    event = ProgressEvent(
        stage="test_stage",
        message="測試訊息",
        progress_percentage=50,
        eta_seconds=30,
        metadata={"key": "value"}
    )
    
    assert event.stage == "test_stage"
    assert event.message == "測試訊息"
    assert event.progress_percentage == 50
    assert event.eta_seconds == 30
    assert event.metadata["key"] == "value"


def test_progress_mixin():
    """測試進度混入功能"""
    from agent_core.progress_mixin import ProgressMixin
    from agent_core.progress_observer import ProgressObserver, ProgressEvent
    
    # 創建測試觀察者
    class TestObserver(ProgressObserver):
        def __init__(self):
            self.events = []
            self.completions = []
            self.errors = []
        
        async def on_progress_update(self, event: ProgressEvent) -> None:
            self.events.append(event)
        
        async def on_completion(self, final_result: str, sources: Optional[List[Dict]] = None) -> None:
            self.completions.append((final_result, sources))
        
        async def on_error(self, error: Exception) -> None:
            self.errors.append(error)
    
    # 創建使用 ProgressMixin 的類別
    class TestAgent(ProgressMixin):
        def __init__(self):
            super().__init__()
    
    # 測試觀察者管理
    agent = TestAgent()
    observer = TestObserver()
    
    agent.add_progress_observer(observer)
    assert len(agent._progress_observers) == 1
    
    agent.remove_progress_observer(observer)
    assert len(agent._progress_observers) == 0
    
    # 測試清除所有觀察者
    agent.add_progress_observer(observer)
    agent.clear_progress_observers()
    assert len(agent._progress_observers) == 0


@pytest.mark.asyncio
async def test_progress_notification():
    """測試進度通知功能"""
    from agent_core.progress_mixin import ProgressMixin
    from agent_core.progress_observer import ProgressObserver, ProgressEvent
    
    # 創建測試觀察者
    class TestObserver(ProgressObserver):
        def __init__(self):
            self.events = []
            self.completions = []
            self.errors = []
        
        async def on_progress_update(self, event: ProgressEvent) -> None:
            self.events.append(event)
        
        async def on_completion(self, final_result: str, sources: Optional[List[Dict]] = None) -> None:
            self.completions.append((final_result, sources))
        
        async def on_error(self, error: Exception) -> None:
            self.errors.append(error)
    
    class TestAgent(ProgressMixin):
        def __init__(self):
            super().__init__()
    
    agent = TestAgent()
    observer = TestObserver()
    agent.add_progress_observer(observer)
    
    # 測試進度通知
    await agent._notify_progress("test", "測試進度", 50)
    assert len(observer.events) == 1
    assert observer.events[0].stage == "test"
    assert observer.events[0].message == "測試進度"
    assert observer.events[0].progress_percentage == 50
    
    # 測試完成通知
    await agent._notify_completion("測試完成", [{"title": "來源1"}])
    assert len(observer.completions) == 1
    assert observer.completions[0][0] == "測試完成"
    assert observer.completions[0][1][0]["title"] == "來源1"
    
    # 測試錯誤通知
    test_error = Exception("測試錯誤")
    await agent._notify_error(test_error)
    assert len(observer.errors) == 1
    assert observer.errors[0] == test_error


def test_discord_progress_adapter():
    """測試 Discord 進度適配器"""
    from discord_bot.progress_adapter import DiscordProgressAdapter
    from agent_core.progress_observer import ProgressEvent
    
    # 創建模擬 Discord 訊息
    mock_message = Mock()
    mock_message.reply = AsyncMock()
    
    # 創建適配器
    with patch('discord_bot.progress_adapter.get_progress_manager') as mock_get_manager:
        mock_manager = Mock()
        mock_manager.send_or_update_progress = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        adapter = DiscordProgressAdapter(mock_message)
        assert adapter.original_message == mock_message
        assert adapter.progress_manager == mock_manager


@pytest.mark.asyncio
async def test_discord_progress_adapter_events():
    """測試 Discord 進度適配器事件處理"""
    from discord_bot.progress_adapter import DiscordProgressAdapter
    from agent_core.progress_observer import ProgressEvent
    
    mock_message = Mock()
    mock_message.reply = AsyncMock()
    
    with patch('discord_bot.progress_adapter.get_progress_manager') as mock_get_manager:
        mock_manager = Mock()
        mock_manager.send_or_update_progress = AsyncMock()
        mock_manager.cleanup_progress_message = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        adapter = DiscordProgressAdapter(mock_message)
        
        # 測試進度更新
        event = ProgressEvent("test", "測試訊息", 50)
        await adapter.on_progress_update(event)
        mock_manager.send_or_update_progress.assert_called_once()
        
        # 測試完成事件
        await adapter.on_completion("測試完成", [{"title": "來源1"}])
        assert mock_manager.send_or_update_progress.call_count == 2
        
        # 測試錯誤事件
        test_error = Exception("測試錯誤")
        await adapter.on_error(test_error)
        assert mock_manager.send_or_update_progress.call_count == 3


def test_config_types():
    """測試配置類型"""
    from schemas.config_types import AppConfig, ToolConfig, AgentConfig
    
    # 測試工具配置
    tool_config = ToolConfig(enabled=True, priority=1)
    assert tool_config.enabled is True
    assert tool_config.priority == 1
    
    # 測試 Agent 配置
    agent_config = AgentConfig()
    agent_config.tools["google_search"] = tool_config
    
    # 測試應用配置
    app_config = AppConfig()
    app_config.agent = agent_config
    
    # 測試便利方法
    assert app_config.is_tool_enabled("google_search") is True
    assert app_config.get_tool_priority("google_search") == 1
    assert "google_search" in app_config.get_enabled_tools()


def test_config_loading():
    """測試配置載入功能"""
    from utils.config_loader import load_config, load_typed_config
    
    # 測試字典格式載入（向後相容）
    config_dict = load_config("config.yaml")
    assert isinstance(config_dict, dict)
    
    # 測試型別安全配置載入
    typed_config = load_typed_config("config.yaml")
    # 注意：如果配置文件不存在，會返回預設配置
    if typed_config:
        assert hasattr(typed_config, 'agent')
        assert hasattr(typed_config, 'discord')


def test_unified_agent_with_progress():
    """測試統一 Agent 支援進度更新"""
    from agent_core.graph import UnifiedAgent
    from agent_core.progress_observer import ProgressObserver, ProgressEvent
    
    # 創建測試觀察者
    class TestObserver(ProgressObserver):
        def __init__(self):
            self.events = []
        
        async def on_progress_update(self, event: ProgressEvent) -> None:
            self.events.append(event)
        
        async def on_completion(self, final_result: str, sources=None) -> None:
            pass
        
        async def on_error(self, error: Exception) -> None:
            pass
    
    # 創建 Agent（使用空配置避免依賴外部文件）
    config = {
        "gemini_api_key": "test_key",
        "llm_models": {
            "tool_analysis": {"model": "gemini-2.0-flash-exp", "temperature": 0.1},
            "final_answer": {"model": "gemini-2.0-flash-exp", "temperature": 0.7}
        },
        "agent": {
            "tools": {},
            "behavior": {"max_tool_rounds": 0}
        }
    }
    
    with patch('agent_core.graph.ChatGoogleGenerativeAI'):
        agent = UnifiedAgent(config)
        observer = TestObserver()
        
        # 測試觀察者註冊
        agent.add_progress_observer(observer)
        assert len(agent._progress_observers) == 1
        
        # 測試 ProgressMixin 方法可用
        assert hasattr(agent, '_notify_progress')
        assert hasattr(agent, '_notify_completion')
        assert hasattr(agent, '_notify_error')


if __name__ == "__main__":
    # 運行基本測試
    test_progress_event_creation()
    test_progress_mixin()
    test_discord_progress_adapter()
    test_config_types()
    test_config_loading()
    test_unified_agent_with_progress()
    print("✅ Phase 2 進度更新功能基本測試通過") 