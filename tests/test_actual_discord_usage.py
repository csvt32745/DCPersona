"""
實際 Discord 使用情境測試

模擬真實的 Discord 訊息處理流程，測試新架構的實際可用性
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List
import os

import discord

from schemas.agent_types import MsgNode
from schemas.config_types import AppConfig, AgentConfig, AgentBehaviorConfig, LLMConfig, DiscordConfig, ToolConfig


def get_test_discord_config():
    """創建測試用的 Discord 配置"""
    with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key_12345'}):
        return AppConfig(
            agent=AgentConfig(
                tools={"google_search": ToolConfig(enabled=True, priority=1)},
                behavior=AgentBehaviorConfig(max_tool_rounds=1, enable_reflection=True)
            ),
            discord=DiscordConfig(
                bot_token="test_token",
                enable_conversation_history=True,
                status_message="測試 AI 助手",
                client_id="123456789"
            )
        )


@pytest.mark.asyncio
async def test_actual_message_processing_flow():
    """測試實際的訊息處理流程"""
    
    # 模擬 Discord 訊息
    mock_message = Mock(spec=discord.Message)
    mock_message.content = "你好，請幫我搜尋 Python 程式設計的最新趨勢"
    mock_message.author = Mock()
    mock_message.author.bot = False
    mock_message.author.id = 12345
    mock_message.channel = Mock()
    mock_message.channel.id = 67890
    mock_message.channel.type = discord.ChannelType.text
    mock_message.guild = Mock()
    mock_message.guild.me = Mock()
    mock_message.guild.me.id = 99999
    mock_message.mentions = [mock_message.guild.me]  # 確保 bot 被提及
    mock_message.attachments = []
    mock_message.embeds = []
    mock_message.reply = AsyncMock()
    
    # 使用型別安全的配置
    test_config = get_test_discord_config()
    
    # 使用真實的訊息處理器（但模擬依賴）
    with patch('discord_bot.message_handler.load_typed_config', return_value=test_config), \
         patch('discord_bot.message_handler.collect_message') as mock_collect, \
         patch('discord_bot.message_handler.create_unified_agent') as mock_create_agent, \
         patch('discord_bot.message_handler.DiscordProgressAdapter') as mock_adapter:
        
        from discord_bot.message_handler import DiscordMessageHandler
        from discord_bot.message_collector import CollectedMessages
        
        # 設置 collect_message 模擬 - 現在返回 CollectedMessages 實例
        test_message = MsgNode(
            role="user",
            content="你好，請幫我搜尋 Python 程式設計的最新趨勢",
            metadata={"user_id": 12345}
        )
        
        mock_collect.return_value = CollectedMessages(
            messages=[test_message],
            user_warnings=set(),
            session_id="test_session_123"
        )
        
        # 設置 Agent 模擬
        mock_agent = Mock()
        mock_agent.add_progress_observer = Mock()
        mock_agent.build_graph = Mock()
        
        mock_graph = Mock()
        mock_graph.ainvoke = AsyncMock(return_value={
            "final_answer": "Python 程式設計目前的趨勢包括機器學習、Web 開發和自動化腳本...",
            "sources": [
                {"title": "Python 2024 趨勢", "url": "https://example.com/python-trends"}
            ],
            "finished": True
        })
        mock_agent.build_graph.return_value = mock_graph
        mock_create_agent.return_value = mock_agent
        
        # 設置進度適配器模擬
        mock_adapter_instance = Mock()
        mock_adapter_instance.on_completion = AsyncMock()
        mock_adapter_instance.cleanup = AsyncMock()
        mock_adapter_instance.on_error = AsyncMock()  # 添加 on_error 方法
        mock_adapter.return_value = mock_adapter_instance
        
        # 執行測試
        handler = DiscordMessageHandler()
        success = await handler.handle_message(mock_message)
        
        # 驗證結果
        assert success is True
        mock_collect.assert_called_once()
        # Agent 可能被調用多次（例如在初始化和處理時），這是正常的
        assert mock_create_agent.call_count >= 1
        mock_agent.add_progress_observer.assert_called_once()
        mock_agent.build_graph.assert_called_once()
        mock_graph.ainvoke.assert_called_once()
        mock_adapter_instance.on_completion.assert_called_once()
        mock_adapter_instance.cleanup.assert_called_once()


@pytest.mark.asyncio 
async def test_simple_message_collection():
    """測試簡化的訊息收集功能"""
    
    # 模擬 Discord 訊息
    mock_message = Mock(spec=discord.Message)
    mock_message.content = "測試訊息"
    mock_message.author = Mock()
    mock_message.author.id = 12345
    mock_message.channel = Mock()
    mock_message.channel.id = 67890
    # 創建可異步迭代的模擬歷史
    async def mock_async_iter():
        return
        yield  # 讓它成為異步生成器但不產生任何項目
    
    mock_message.channel.history = Mock(return_value=mock_async_iter())
    mock_message.attachments = []
    mock_message.embeds = []
    mock_message.reference = None
    
    mock_discord_user = Mock()
    mock_discord_user.id = 99999
    
    test_config = get_test_discord_config()
    
    # 使用真實的 collect_message 函數
    from discord_bot.message_collector import collect_message
    
    with patch('discord_bot.message_collector.get_agent_session') as mock_session:
        mock_session_manager = Mock()
        mock_session_manager.create_session.return_value = "test_session_123"
        mock_session_manager.get_session.return_value = Mock()
        mock_session_manager.cache_discord_messages = Mock()
        mock_session.return_value = mock_session_manager
        
        result = await collect_message(
            new_msg=mock_message,
            discord_client_user=mock_discord_user,
            enable_conversation_history=test_config.discord.enable_conversation_history,
            max_text=4000,
            max_images=4,
            max_messages=10
        )
        
        # 驗證結果 - 現在使用 CollectedMessages dataclass
        assert hasattr(result, 'messages')
        assert hasattr(result, 'user_warnings')
        assert hasattr(result, 'session_id')
        assert result.message_count() >= 1
        assert result.messages[0].content == "測試訊息"
        assert result.messages[0].role == "user"
        assert result.session_id == "test_session_123"


def test_discord_client_creation():
    """測試 Discord 客戶端建立"""
    
    from discord_bot.client import create_discord_client
    
    test_config = get_test_discord_config()
    
    with patch('discord.Client') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        client = create_discord_client(test_config)
        
        # 驗證客戶端建立
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs['intents'].message_content is True


def test_simplified_config_usage():
    """測試簡化的配置使用"""
    
    test_config = get_test_discord_config()
    
    # 測試型別安全的配置存取
    assert test_config.discord.bot_token == "test_token"
    assert test_config.discord.enable_conversation_history is True
    assert test_config.agent.behavior.max_tool_rounds == 1
    assert test_config.gemini_api_key == "test_key_12345"


@pytest.mark.asyncio
async def test_progress_adapter_integration():
    """測試進度適配器與進度管理器的整合"""
    
    from discord_bot.progress_adapter import DiscordProgressAdapter
    from agent_core.progress_observer import ProgressEvent
    
    # 模擬 Discord 訊息
    mock_message = Mock(spec=discord.Message)
    mock_message.reply = AsyncMock()
    
    # 模擬進度管理器
    with patch('discord_bot.progress_adapter.get_progress_manager') as mock_get_manager:
        mock_manager = Mock()
        mock_manager.send_or_update_progress = AsyncMock()
        mock_manager.cleanup_progress_message = AsyncMock()
        mock_get_manager.return_value = mock_manager
        
        # 創建適配器
        adapter = DiscordProgressAdapter(mock_message)
        
        # 測試進度更新
        event = ProgressEvent(
            stage="testing",
            message="測試進度更新",
            progress_percentage=50,
            eta_seconds=30
        )
        
        await adapter.on_progress_update(event)
        mock_manager.send_or_update_progress.assert_called_once()
        
        # 測試完成事件
        await adapter.on_completion("測試完成", [{"title": "測試來源"}])
        assert mock_manager.send_or_update_progress.call_count == 2
        
        # 測試清理
        await adapter.cleanup()
        mock_manager.cleanup_progress_message.assert_called_once()


def test_message_handler_should_process():
    """測試訊息處理器的基本過濾邏輯"""
    
    from discord_bot.message_handler import DiscordMessageHandler
    
    handler = DiscordMessageHandler({})
    
    # 測試 bot 訊息應該被忽略
    bot_message = Mock()
    bot_message.author.bot = True
    bot_message.content = "我是 bot"
    assert handler._should_process_message(bot_message) is False
    
    # 測試空訊息應該被忽略
    empty_message = Mock()
    empty_message.author.bot = False
    empty_message.content = "   "
    assert handler._should_process_message(empty_message) is False
    
    # 測試正常訊息應該被處理 - 添加必要的屬性
    normal_message = Mock()
    normal_message.author.bot = False
    normal_message.content = "你好"
    normal_message.channel = Mock()
    normal_message.channel.type = discord.ChannelType.private  # DM 訊息
    normal_message.guild = None  # DM 中沒有 guild
    normal_message.mentions = []
    assert handler._should_process_message(normal_message) is True


if __name__ == "__main__":
    # 運行基本測試
    test_discord_client_creation()
    test_simplified_config_usage()
    test_message_handler_should_process()
    print("✅ 實際使用情境測試通過") 