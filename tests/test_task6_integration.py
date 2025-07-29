"""
Task 6 整合測試

測試 EventScheduler 與 Discord Bot 的整合功能
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import discord

from event_scheduler.scheduler import EventScheduler
from discord_bot.message_handler import DiscordMessageHandler
from schemas.agent_types import ReminderDetails
from schemas.config_types import AppConfig


@pytest.fixture
async def event_scheduler():
    """創建測試用的 EventScheduler"""
    scheduler = EventScheduler(data_dir="test_data")
    await scheduler.start()
    yield scheduler
    await scheduler.shutdown()


@pytest.fixture
def mock_config():
    """創建測試用的配置"""
    config = Mock(spec=AppConfig)
    config.discord = Mock()
    config.discord.enable_conversation_history = True
    config.discord.limits = Mock()
    config.discord.limits.max_text = 1000
    config.discord.limits.max_images = 5
    config.discord.limits.max_messages = 10
    config.discord.permissions = Mock()
    config.discord.permissions.allow_dms = True
    config.discord.permissions.users = {"allowed_ids": [], "blocked_ids": []}
    config.discord.permissions.roles = {"allowed_ids": [], "blocked_ids": []}
    config.discord.permissions.channels = {"allowed_ids": [], "blocked_ids": []}
    config.discord.maintenance = Mock()
    config.discord.maintenance.enabled = False
    config.agent = Mock()
    config.agent.behavior = Mock()
    config.reject_resp = "拒絕回應"
    
    # 添加 LLM 配置
    config.llm = Mock()
    config.llm.models = {}
    config.llm.default_model = "test_model"
    
    # 添加工具配置
    config.tools = Mock()
    config.tools.enabled = []
    
    # 添加 get_enabled_tools 方法
    config.get_enabled_tools = Mock(return_value=[])
    
    return config


@pytest.fixture
def message_handler(mock_config, event_scheduler):
    """創建測試用的 DiscordMessageHandler"""
    # 使用 patch 來避免創建真實的 Agent
    with patch('agent_core.graph.UnifiedAgent') as mock_unified_agent:
        mock_agent = Mock()
        mock_unified_agent.return_value = mock_agent
        
        handler = DiscordMessageHandler(mock_config, event_scheduler)
        
        # 模擬 Discord 客戶端
        mock_client = Mock(spec=discord.Client)
        mock_client.user = Mock()
        mock_client.user.id = 12345
        mock_client.user.name = "TestBot"
        mock_client.user.display_name = "TestBot"
        mock_client._connection = Mock()
        mock_client.unified_agent = mock_agent  # 添加 unified_agent
        mock_client.emoji_handler = Mock()  # 添加 emoji_handler
        
        handler.set_discord_client(mock_client)
        return handler


class TestTask6Integration:
    """Task 6 整合測試"""
    
    def test_message_handler_initialization(self, mock_config, event_scheduler):
        """測試 DiscordMessageHandler 初始化"""
        with patch('agent_core.graph.UnifiedAgent') as mock_unified_agent:
            mock_agent = Mock()
            mock_unified_agent.return_value = mock_agent
            
            handler = DiscordMessageHandler(mock_config, event_scheduler)
            
            assert handler.event_scheduler is event_scheduler
            assert "reminder" in event_scheduler.callbacks
        
    def test_event_scheduler_callback_registration(self, event_scheduler):
        """測試 EventScheduler 回調函數註冊"""
        with patch('agent_core.graph.UnifiedAgent') as mock_unified_agent:
            mock_agent = Mock()
            mock_unified_agent.return_value = mock_agent
            
            handler = DiscordMessageHandler(event_scheduler=event_scheduler)
            
            # 檢查回調函數是否已註冊
            assert "reminder" in event_scheduler.callbacks
            assert event_scheduler.callbacks["reminder"] == handler._on_reminder_triggered
        
    @pytest.mark.asyncio
    async def test_reminder_scheduling(self, message_handler, event_scheduler):
        """測試提醒排程功能"""
        # 創建測試用的提醒詳細資料
        reminder_details = ReminderDetails(
            message="測試提醒",
            target_timestamp=(datetime.now() + timedelta(seconds=1)).isoformat(),
            channel_id="123456789",
            user_id="987654321",
            reminder_id="test_reminder_1",
            msg_id="555555555"
        )
        
        # 模擬 Agent 結果
        agent_result = {
            "reminder_requests": [reminder_details],
            "final_answer": "已設定提醒"
        }
        
        # 創建模擬的進度適配器
        mock_progress_adapter = Mock()
        mock_progress_adapter.original_message = Mock()
        mock_progress_adapter.original_message.id = 555555555
        mock_progress_adapter.original_message.channel = Mock()
        mock_progress_adapter.original_message.channel.id = 123456789
        mock_progress_adapter.original_message.author = Mock()
        mock_progress_adapter.original_message.author.id = 987654321
        mock_progress_adapter._streaming_message = None
        mock_progress_adapter.on_completion = AsyncMock()
        
        # 處理 Agent 結果
        await message_handler._handle_agent_result(agent_result, mock_progress_adapter)
        
        # 檢查提醒是否已排程
        scheduled_events = await event_scheduler.get_scheduled_events()
        assert len(scheduled_events) > 0
        
        # 檢查提醒詳細資料是否正確填入
        assert reminder_details.channel_id == "123456789"
        assert reminder_details.user_id == "987654321"
        
    @pytest.mark.asyncio
    async def test_reminder_trigger_flow(self, message_handler):
        """測試提醒觸發流程"""
        reminder_details = ReminderDetails(
            message="測試提醒訊息",
            target_timestamp=datetime.now().isoformat(),
            channel_id="123456789",
            user_id="987654321",
            msg_id="555555555"
        )
        
        # 模擬頻道和原始訊息
        mock_channel = Mock(spec=discord.TextChannel)
        mock_channel.id = 123456789
        
        mock_original_message = Mock(spec=discord.Message)
        mock_original_message.id = 555555555
        mock_original_message.content = "原始訊息內容"
        mock_original_message.channel = mock_channel
        mock_original_message.author = Mock()
        mock_original_message.author.id = 987654321
        
        mock_channel.fetch_message = AsyncMock(return_value=mock_original_message)
        message_handler.discord_client.get_channel.return_value = mock_channel
        
        # 模擬 handle_message 方法
        message_handler.handle_message = AsyncMock()
        
        # 觸發提醒回調
        await message_handler._on_reminder_triggered(
            "reminder", 
            reminder_details.__dict__, 
            "test_event_id"
        )
        
        # 檢查是否正確設定了提醒標記到 reminder_triggers 字典中
        message_id = str(mock_original_message.id)
        assert message_id in message_handler.reminder_triggers
        assert message_handler.reminder_triggers[message_id]['is_trigger'] is True
        assert message_handler.reminder_triggers[message_id]['content'] == "測試提醒訊息"
        
        # 檢查是否調用了 handle_message
        message_handler.handle_message.assert_called_once_with(mock_original_message)
        
    def test_should_process_reminder_message(self, message_handler):
        """測試是否處理提醒訊息"""
        # 創建模擬的提醒訊息
        mock_message = Mock(spec=discord.Message)
        mock_message.author = Mock()
        mock_message.author.bot = True  # 來自 Bot
        mock_message.content = "提醒：時間到了，請注意：測試"
        
        # 應該允許處理提醒訊息
        should_process = message_handler._should_process_message(mock_message)
        assert should_process is True
        
        # 創建普通 Bot 訊息
        mock_message.content = "普通 Bot 訊息"
        should_process = message_handler._should_process_message(mock_message)
        assert should_process is False


if __name__ == "__main__":
    pytest.main([__file__]) 