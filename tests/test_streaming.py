"""
測試串流功能

測試 Progress 系統的串流支援，包括：
- ProgressObserver 的串流方法
- DiscordProgressAdapter 的串流處理
- Agent 的串流生成
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import List

from agent_core.progress_observer import ProgressObserver, ProgressEvent
from agent_core.progress_mixin import ProgressMixin
from discord_bot.progress_adapter import DiscordProgressAdapter
from schemas.config_types import AppConfig, StreamingConfig, ProgressConfig, ProgressDiscordConfig
from schemas.agent_types import OverallState, MsgNode


class MockProgressObserver(ProgressObserver):
    """測試用的 ProgressObserver 實作"""
    
    def __init__(self):
        self.progress_events = []
        self.streaming_chunks = []
        self.completion_calls = []
        self.error_calls = []
        self.streaming_complete_calls = []
    
    async def on_progress_update(self, event: ProgressEvent) -> None:
        self.progress_events.append(event)
    
    async def on_completion(self, final_result: str, sources=None) -> None:
        self.completion_calls.append((final_result, sources))
    
    async def on_error(self, error: Exception) -> None:
        self.error_calls.append(error)
    
    async def on_streaming_chunk(self, content: str, is_final: bool = False) -> None:
        self.streaming_chunks.append((content, is_final))
    
    async def on_streaming_complete(self) -> None:
        self.streaming_complete_calls.append(True)


class MockProgressMixin(ProgressMixin):
    """測試用的 ProgressMixin 實作"""
    
    def __init__(self):
        super().__init__()


@pytest.mark.asyncio
async def test_progress_observer_streaming_methods():
    """測試 ProgressObserver 的串流方法"""
    observer = MockProgressObserver()
    
    # 測試串流塊
    await observer.on_streaming_chunk("Hello", False)
    await observer.on_streaming_chunk(" World", False)
    await observer.on_streaming_chunk("!", True)
    
    assert len(observer.streaming_chunks) == 3
    assert observer.streaming_chunks[0] == ("Hello", False)
    assert observer.streaming_chunks[1] == (" World", False)
    assert observer.streaming_chunks[2] == ("!", True)
    
    # 測試串流完成
    await observer.on_streaming_complete()
    assert len(observer.streaming_complete_calls) == 1


@pytest.mark.asyncio
async def test_progress_mixin_streaming_notifications():
    """測試 ProgressMixin 的串流通知功能"""
    mixin = MockProgressMixin()
    observer = MockProgressObserver()
    
    # 添加觀察者
    mixin.add_progress_observer(observer)
    
    # 測試串流通知
    await mixin._notify_streaming_chunk("Test content", False)
    await mixin._notify_streaming_chunk("Final content", True)
    await mixin._notify_streaming_complete()
    
    # 驗證觀察者收到通知
    assert len(observer.streaming_chunks) == 2
    assert observer.streaming_chunks[0] == ("Test content", False)
    assert observer.streaming_chunks[1] == ("Final content", True)
    assert len(observer.streaming_complete_calls) == 1


@pytest.mark.asyncio
async def test_discord_progress_adapter_streaming():
    """測試 DiscordProgressAdapter 的串流處理"""
    # 創建 mock Discord 訊息
    mock_message = Mock()
    mock_message.reply = AsyncMock()
    mock_message.channel = Mock()
    mock_message.channel.id = 12345
    
    # 創建測試配置
    config = AppConfig(
        streaming=StreamingConfig(enabled=True, min_content_length=10),
        progress=ProgressConfig(
            discord=ProgressDiscordConfig(update_interval=0.1)
        )
    )
    
    with patch('discord_bot.progress_adapter.load_typed_config', return_value=config):
        adapter = DiscordProgressAdapter(mock_message)
        
        # 測試串流塊處理
        await adapter.on_streaming_chunk("Hello", False)
        await adapter.on_streaming_chunk(" World", False)
        await adapter.on_streaming_chunk("!", True)
        
        # 驗證內容累積
        assert adapter._streaming_content == "Hello World!"
        
        # 測試串流完成
        await adapter.on_streaming_complete()
        
        # 驗證 Discord 訊息被調用
        assert mock_message.reply.called


@pytest.mark.asyncio
async def test_streaming_with_time_based_updates():
    """測試基於時間的串流更新"""
    mock_message = Mock()
    mock_message.reply = AsyncMock()
    mock_message.channel = Mock()
    mock_message.channel.id = 12345
    
    # 創建配置，設置較短的更新間隔
    config = AppConfig(
        streaming=StreamingConfig(enabled=True, min_content_length=10),
        progress=ProgressConfig(
            discord=ProgressDiscordConfig(update_interval=0.01)  # 10ms 間隔
        )
    )
    
    with patch('discord_bot.progress_adapter.load_typed_config', return_value=config):
        adapter = DiscordProgressAdapter(mock_message)
        
        # 發送多個串流塊，間隔時間
        await adapter.on_streaming_chunk("First", False)
        await asyncio.sleep(0.02)  # 等待超過更新間隔
        await adapter.on_streaming_chunk(" Second", False)
        await asyncio.sleep(0.02)
        await adapter.on_streaming_chunk(" Third", True)
        
        # 驗證內容
        assert adapter._streaming_content == "First Second Third"


@pytest.mark.asyncio
async def test_streaming_with_length_based_updates():
    """測試基於長度的串流更新"""
    mock_message = Mock()
    mock_message.reply = AsyncMock()
    mock_message.channel = Mock()
    mock_message.channel.id = 12345
    
    config = AppConfig(
        streaming=StreamingConfig(enabled=True, min_content_length=10),
        progress=ProgressConfig(
            discord=ProgressDiscordConfig(update_interval=1.0)  # 長間隔
        )
    )
    
    with patch('discord_bot.progress_adapter.load_typed_config', return_value=config):
        adapter = DiscordProgressAdapter(mock_message)
        
        # 發送長內容觸發長度更新
        long_content = "A" * 1600  # 超過 1500 字符限制
        await adapter.on_streaming_chunk(long_content, False)
        
        # 驗證內容被截斷
        assert len(adapter._streaming_content) == 1600


@pytest.mark.asyncio
async def test_streaming_error_handling():
    """測試串流錯誤處理"""
    mock_message = Mock()
    mock_message.reply = AsyncMock(side_effect=Exception("Discord API Error"))
    mock_message.channel = Mock()
    mock_message.channel.id = 12345
    
    config = AppConfig(
        streaming=StreamingConfig(enabled=True, min_content_length=10),
        progress=ProgressConfig(
            discord=ProgressDiscordConfig(update_interval=0.1)
        )
    )
    
    with patch('discord_bot.progress_adapter.load_typed_config', return_value=config):
        adapter = DiscordProgressAdapter(mock_message)
        
        # 測試在 Discord API 錯誤時不會崩潰
        await adapter.on_streaming_chunk("Test content", False)
        await adapter.on_streaming_complete()
        
        # 驗證內容仍然被保存
        assert adapter._streaming_content == "Test content"


@pytest.mark.asyncio
async def test_streaming_disabled():
    """測試串流功能被禁用時的行為"""
    mock_message = Mock()
    mock_message.reply = AsyncMock()
    mock_message.channel = Mock()
    mock_message.channel.id = 12345
    
    config = AppConfig(
        streaming=StreamingConfig(enabled=False, min_content_length=10),
        progress=ProgressConfig(
            discord=ProgressDiscordConfig(update_interval=0.1)
        )
    )
    
    with patch('discord_bot.progress_adapter.load_typed_config', return_value=config):
        adapter = DiscordProgressAdapter(mock_message)
        
        # 即使串流被禁用，適配器仍應正常處理串流事件
        await adapter.on_streaming_chunk("Test content", False)
        await adapter.on_streaming_complete()
        
        # 驗證內容被處理
        assert adapter._streaming_content == "Test content"


if __name__ == "__main__":
    pytest.main([__file__]) 