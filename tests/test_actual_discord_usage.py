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
from schemas.config_types import AppConfig, AgentConfig, AgentBehaviorConfig, LLMConfig, DiscordConfig, ToolConfig, LLMProviderConfig
from discord_bot.message_manager import get_manager_instance
from discord_bot.message_collector import collect_message, CollectedMessages, ProcessedMessage


def get_test_discord_config():
    """創建測試用的 Discord 配置"""
    # 移除環境變數補丁，直接在 AppConfig 中設定 LLM Provider 的 API Key
    # with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key_12345'}):
    
    # 創建一個模擬的 LLMProviderConfig
    mock_google_provider_config = LLMProviderConfig(api_key="test_key_12345")
    
    # 創建一個 LLMConfig 並包含模擬的 Provider
    mock_llm_config = LLMConfig(
        providers={"google": mock_google_provider_config}
    )

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
        ),
        llm=mock_llm_config # 將模擬的 LLMConfig 傳入
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
    mock_message.stickers = []  # 添加 stickers 屬性
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
            user_warnings=set()
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
        mock_adapter_instance._streaming_message = None  # 模擬非串流模式
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
        
        # 在非串流模式下，on_completion 應該被調用
        mock_adapter_instance.on_completion.assert_called_once()
        # cleanup 應該在 finally 塊中被調用
        mock_adapter_instance.cleanup.assert_called_once()


@pytest.mark.asyncio 
async def test_simple_message_collection():
    """測試簡化的訊息收集功能"""
    
    # 模擬 Discord 訊息
    mock_message = Mock(spec=discord.Message)
    mock_message.content = "測試訊息"
    mock_message.author = Mock()
    mock_message.author.id = 12345
    mock_message.author.display_name = "TestUser"
    mock_message.channel = Mock()
    mock_message.channel.id = 67890
    # 創建可異步迭代的模擬歷史
    async def mock_async_iter():
        return
        yield  # 讓它成為異步生成器但不產生任何項目
    
    mock_message.channel.history = Mock(return_value=mock_async_iter())
    mock_message.attachments = []
    mock_message.embeds = []
    mock_message.stickers = []  # 添加 stickers 屬性
    mock_message.reference = None
    
    mock_discord_user = Mock()
    mock_discord_user.id = 99999
    
    test_config = get_test_discord_config()
    
    with patch('discord_bot.message_collector._process_single_message', new_callable=AsyncMock) as mock_process_single_message, \
         patch('discord_bot.message_collector._get_parent_message', new_callable=AsyncMock) as mock_get_parent_message, \
         patch('discord_bot.message_collector.get_manager_instance') as mock_get_manager_instance:
        # 為了讓 collect_message 能夠使用模擬的 get_manager_instance，我們需要在 patch 塊內導入它
        from discord_bot.message_collector import collect_message
        
        # 設置 _process_single_message 的模擬返回值
        mock_processed_message = ProcessedMessage(
            content=f"<@{mock_message.author.id}> {mock_message.author.display_name}: {mock_message.content}",
            role="user",
            user_id=mock_message.author.id
        )
        mock_process_single_message.return_value = mock_processed_message
        
        # 設置 _get_parent_message 的模擬返回值，使其不返回父訊息以簡化流程
        mock_get_parent_message.return_value = None
        
        mock_message_manager = Mock()
        mock_message_manager.cache_messages = Mock()
        mock_get_manager_instance.return_value = mock_message_manager
        
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
        assert result.message_count() >= 1
        assert "<@12345> TestUser: 測試訊息" in result.messages[0].content
        assert result.messages[0].role == "user"
        
        # 驗證訊息管理器被呼叫
        mock_get_manager_instance.assert_called_once()
        mock_message_manager.cache_messages.assert_called_once_with([mock_message])


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
    
    # 使用 patch.dict 來確保 os.getenv 返回測試值
    with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key_12345'}):
        # 由於 AppConfig 在初始化時會讀取環境變數，
        # 我們需要確保在測試這個屬性時，環境變數是被正確設置的。
        # AppConfig 的 gemini_api_key 屬性會優先從環境變數讀取。
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
        mock_manager.cleanup_progress_message = Mock()  # 改為同步 Mock
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
    empty_message.stickers = []  # 沒有 sticker
    empty_message.attachments = []  # 沒有附件
    assert handler._should_process_message(empty_message) is False
    
    # 測試正常訊息應該被處理 - 添加必要的屬性
    normal_message = Mock()
    normal_message.author.bot = False
    normal_message.content = "你好"
    normal_message.channel = Mock()
    normal_message.channel.type = discord.ChannelType.private  # DM 訊息
    normal_message.guild = None  # DM 中沒有 guild
    normal_message.mentions = []
    normal_message.stickers = []  # 沒有 sticker
    normal_message.attachments = []  # 沒有附件
    assert handler._should_process_message(normal_message) is True


if __name__ == "__main__":
    # 運行基本測試
    test_discord_client_creation()
    test_simplified_config_usage()
    test_message_handler_should_process()
    print("✅ 實際使用情境測試通過") 