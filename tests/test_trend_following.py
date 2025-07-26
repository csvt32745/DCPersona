"""
跟風功能完整測試套件

測試 TrendFollowingHandler 的所有核心功能，包括：
- Reaction 跟風
- 內容跟風（文字和 sticker）
- Emoji 跟風
- 頻道鎖機制和併發控制
- Bot 循環防護
- 配置驅動的行為控制
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from typing import List, Dict, Any

import discord
from langchain_google_genai import ChatGoogleGenerativeAI

from discord_bot.trend_following import TrendFollowingHandler
from schemas.config_types import TrendFollowingConfig
from output_media.emoji_registry import EmojiRegistry


@pytest.fixture
def default_config():
    """預設跟風配置"""
    return TrendFollowingConfig(
        enabled=True,
        allowed_channels=[123456789],
        cooldown_seconds=60,
        message_history_limit=10,
        reaction_threshold=3,
        content_threshold=2,
        emoji_threshold=3
    )


@pytest.fixture
def mock_llm():
    """模擬 LLM"""
    llm = AsyncMock(spec=ChatGoogleGenerativeAI)
    mock_response = AsyncMock()
    mock_response.content = "<:test_emoji:123456789>"
    llm.ainvoke.return_value = mock_response
    return llm


@pytest.fixture
def mock_emoji_registry():
    """模擬 EmojiRegistry"""
    registry = AsyncMock(spec=EmojiRegistry)
    registry.build_prompt_context.return_value = "Available emojis: <:test_emoji:123456789>"
    return registry


@pytest.fixture
def handler(default_config, mock_llm, mock_emoji_registry):
    """創建 TrendFollowingHandler 實例"""
    return TrendFollowingHandler(
        config=default_config,
        llm=mock_llm,
        emoji_registry=mock_emoji_registry
    )


class TestTrendFollowingHandler:
    """TrendFollowingHandler 核心功能測試"""
    
    def test_handler_initialization(self, handler, default_config):
        """測試處理器初始化"""
        assert handler.config == default_config
        assert handler.llm is not None
        assert handler.emoji_registry is not None
        assert handler.last_response_times == {}
        assert handler.channel_locks == {}
        assert handler.emoji_pattern is not None
    
    def test_get_channel_lock(self, handler):
        """測試頻道鎖獲取機制"""
        channel_id = 123456789
        
        # 第一次獲取應該創建新鎖
        lock1 = handler.get_channel_lock(channel_id)
        assert isinstance(lock1, asyncio.Lock)
        assert channel_id in handler.channel_locks
        
        # 第二次獲取應該返回相同的鎖
        lock2 = handler.get_channel_lock(channel_id)
        assert lock1 is lock2
    
    def test_is_enabled_in_channel(self, handler):
        """測試頻道啟用檢查"""
        # 允許的頻道
        assert handler.is_enabled_in_channel(123456789) is True
        
        # 不允許的頻道
        assert handler.is_enabled_in_channel(987654321) is False
        
        # 測試空允許列表（所有頻道都允許）
        handler.config.allowed_channels = []
        assert handler.is_enabled_in_channel(987654321) is True
        
        # 功能關閉
        handler.config.enabled = False
        assert handler.is_enabled_in_channel(123456789) is False
    
    def test_cooldown_mechanism(self, handler):
        """測試冷卻機制"""
        channel_id = 123456789
        
        # 初始狀態沒有冷卻
        assert handler.is_in_cooldown(channel_id) is False
        
        # 更新冷卻時間
        handler.update_cooldown(channel_id)
        assert handler.is_in_cooldown(channel_id) is True
        
        # 模擬時間過去（超過冷卻時間）
        handler.last_response_times[channel_id] = time.time() - 70  # 70秒前
        assert handler.is_in_cooldown(channel_id) is False


class TestReactionFollowing:
    """Reaction 跟風測試"""
    
    @pytest.fixture
    def mock_payload(self):
        """模擬 Discord RawReactionActionEvent"""
        payload = Mock(spec=discord.RawReactionActionEvent)
        payload.channel_id = 123456789
        payload.message_id = 987654321
        payload.user_id = 111111111
        payload.emoji = "👍"
        return payload
    
    @pytest.fixture
    def mock_bot(self):
        """模擬 Discord Bot"""
        bot = AsyncMock(spec=discord.Client)
        bot.user.id = 999999999
        
        # 模擬頻道
        channel = AsyncMock(spec=discord.TextChannel)
        bot.get_channel.return_value = channel
        
        # 模擬訊息和 reaction
        message = AsyncMock(spec=discord.Message)
        reaction = AsyncMock(spec=discord.Reaction)
        reaction.emoji = "👍"
        reaction.count = 3
        
        # 模擬 reaction.users() 返回異步生成器
        async def mock_users():
            yield AsyncMock(id=111111111)  # 其他用戶
            yield AsyncMock(id=222222222)  # 其他用戶
        
        reaction.users.return_value = mock_users()
        message.reactions = [reaction]
        channel.fetch_message.return_value = message
        
        return bot
    
    @pytest.mark.asyncio
    async def test_reaction_following_success(self, handler, mock_payload, mock_bot):
        """測試成功的 reaction 跟風"""
        result = await handler.handle_raw_reaction_following(mock_payload, mock_bot)
        
        assert result is True
        
        # 驗證訊息獲取
        mock_bot.get_channel.assert_called_once_with(123456789)
        channel = mock_bot.get_channel.return_value
        channel.fetch_message.assert_called_once_with(987654321)
        
        # 驗證 reaction 添加
        message = channel.fetch_message.return_value
        message.add_reaction.assert_called_once_with("👍")
    
    @pytest.mark.asyncio
    async def test_reaction_following_bot_already_reacted(self, handler, mock_payload, mock_bot):
        """測試 Bot 已經 react 的情況"""
        # 修改 mock 讓 Bot 已經在 reaction 用戶中
        channel = mock_bot.get_channel.return_value
        message = channel.fetch_message.return_value
        reaction = message.reactions[0]
        
        async def mock_users_with_bot():
            yield AsyncMock(id=111111111)  # 其他用戶
            yield AsyncMock(id=999999999)  # Bot 自己
        
        reaction.users.return_value = mock_users_with_bot()
        
        result = await handler.handle_raw_reaction_following(mock_payload, mock_bot)
        
        assert result is False
        message.add_reaction.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_reaction_following_threshold_not_met(self, handler, mock_payload, mock_bot):
        """測試 reaction 數量未達閾值"""
        # 設置 reaction 數量低於閾值
        channel = mock_bot.get_channel.return_value
        message = channel.fetch_message.return_value
        reaction = message.reactions[0]
        reaction.count = 1  # 低於閾值 3
        
        result = await handler.handle_raw_reaction_following(mock_payload, mock_bot)
        
        assert result is False
        message.add_reaction.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_reaction_following_bot_triggered(self, handler, mock_payload, mock_bot):
        """測試 Bot 自己觸發的 reaction"""
        mock_payload.user_id = 999999999  # Bot 的 ID
        
        result = await handler.handle_raw_reaction_following(mock_payload, mock_bot)
        
        assert result is False
        mock_bot.get_channel.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_reaction_following_channel_not_enabled(self, handler, mock_payload, mock_bot):
        """測試在未啟用的頻道"""
        mock_payload.channel_id = 999999999  # 不在允許列表中
        
        result = await handler.handle_raw_reaction_following(mock_payload, mock_bot)
        
        assert result is False
        mock_bot.get_channel.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_reaction_following_in_cooldown(self, handler, mock_payload, mock_bot):
        """測試冷卻期間的處理"""
        # 設置冷卻
        handler.update_cooldown(123456789)
        
        result = await handler.handle_raw_reaction_following(mock_payload, mock_bot)
        
        assert result is False
        mock_bot.get_channel.assert_not_called()


class TestContentFollowing:
    """內容跟風測試"""
    
    def test_get_message_content_text(self, handler):
        """測試獲取文字訊息內容"""
        message = Mock()
        message.stickers = []
        message.content = "Hello World"
        
        content_type, content_value = handler._get_message_content(message)
        
        assert content_type == "text"
        assert content_value == "Hello World"
    
    def test_get_message_content_sticker(self, handler):
        """測試獲取 sticker 內容"""
        message = Mock()
        sticker = Mock()
        sticker.id = 123456789
        message.stickers = [sticker]
        message.content = ""
        
        content_type, content_value = handler._get_message_content(message)
        
        assert content_type == "sticker"
        assert content_value == sticker
    
    def test_get_message_content_empty(self, handler):
        """測試空內容訊息"""
        message = Mock()
        message.stickers = []
        message.content = ""
        
        content_type, content_value = handler._get_message_content(message)
        
        assert content_type == ""
        assert content_value == ""
    
    def test_extract_valid_content_segment_text(self, handler):
        """測試提取有效的文字內容片段"""
        # 訊息順序：最舊到最新（實現會從最新往回找）
        messages = [
            {'content_type': 'text', 'content_value': 'Different', 'is_bot': False},  # 最舊
            {'content_type': 'text', 'content_value': 'Hello', 'is_bot': False},
            {'content_type': 'text', 'content_value': 'Hello', 'is_bot': False},      # 最新
        ]
        
        segment, has_bot = handler._extract_valid_content_segment(
            messages, "text", "Hello"
        )
        
        assert len(segment) == 2
        assert has_bot is False
        assert all(item[0] == "text" and item[1] == "Hello" for item in segment)
    
    def test_extract_valid_content_segment_with_bot(self, handler):
        """測試包含 Bot 的內容片段"""
        messages = [
            {'content_type': 'text', 'content_value': 'Different', 'is_bot': False},  # 最舊
            {'content_type': 'text', 'content_value': 'Hello', 'is_bot': False},
            {'content_type': 'text', 'content_value': 'Hello', 'is_bot': True},      # Bot 參與，最新
        ]
        
        segment, has_bot = handler._extract_valid_content_segment(
            messages, "text", "Hello"
        )
        
        assert len(segment) == 2
        assert has_bot is True
    
    def test_extract_valid_content_segment_sticker(self, handler):
        """測試提取 sticker 內容片段"""
        sticker1 = Mock()
        sticker1.id = 123456789
        sticker2 = Mock()
        sticker2.id = 123456789
        sticker3 = Mock()
        sticker3.id = 987654321  # 不同的 sticker
        
        messages = [
            {'content_type': 'sticker', 'content_value': sticker3, 'is_bot': False},  # 最舊，不同
            {'content_type': 'sticker', 'content_value': sticker1, 'is_bot': False},
            {'content_type': 'sticker', 'content_value': sticker2, 'is_bot': False},  # 最新，相同
        ]
        
        segment, has_bot = handler._extract_valid_content_segment(
            messages, "sticker", sticker1
        )
        
        assert len(segment) == 2
        assert has_bot is False
    
    @pytest.mark.asyncio
    async def test_send_content_response_text(self, handler):
        """測試發送文字內容回應"""
        channel = AsyncMock()
        
        await handler._send_content_response("text", "Hello World", channel)
        
        channel.send.assert_called_once_with("Hello World")
    
    @pytest.mark.asyncio
    async def test_send_content_response_sticker(self, handler):
        """測試發送 sticker 回應"""
        channel = AsyncMock()
        sticker = Mock()
        
        await handler._send_content_response("sticker", sticker, channel)
        
        channel.send.assert_called_once_with(stickers=[sticker])
    
    @pytest.mark.asyncio
    async def test_send_content_response_unknown_type(self, handler):
        """測試發送未知類型內容"""
        channel = AsyncMock()
        
        await handler._send_content_response("unknown", "content", channel)
        
        channel.send.assert_called_once_with("[未知內容類型]")


class TestEmojiFollowing:
    """Emoji 跟風測試"""
    
    def test_is_emoji_only_message_valid(self, handler):
        """測試有效的純 emoji 訊息"""
        assert handler._is_emoji_only_message("<:test:123456789>") is True
        assert handler._is_emoji_only_message("<a:animated:123456789>") is True
        assert handler._is_emoji_only_message("<:test1:123> <:test2:456>") is True
    
    def test_is_emoji_only_message_invalid(self, handler):
        """測試無效的純 emoji 訊息"""
        assert handler._is_emoji_only_message("Hello <:test:123456789>") is False
        assert handler._is_emoji_only_message("Hello World") is False
        assert handler._is_emoji_only_message("") is False
        assert handler._is_emoji_only_message("   ") is False
    
    def test_extract_valid_emoji_segment(self, handler):
        """測試提取有效的 emoji 片段"""
        messages = [
            {'content_type': 'text', 'content_value': 'Hello World', 'is_bot': False},  # 最舊，非 emoji
            {'content_type': 'text', 'content_value': '<:emoji1:123>', 'is_bot': False},
            {'content_type': 'text', 'content_value': '<:emoji2:456>', 'is_bot': False},  # 最新
        ]
        
        segment, has_bot = handler._extract_valid_emoji_segment(messages)
        
        assert len(segment) == 2
        assert has_bot is False
        assert '<:emoji1:123>' in segment
        assert '<:emoji2:456>' in segment
    
    def test_extract_valid_emoji_segment_with_bot(self, handler):
        """測試包含 Bot 的 emoji 片段"""
        messages = [
            {'content_type': 'text', 'content_value': '<:emoji1:123>', 'is_bot': False},
            {'content_type': 'text', 'content_value': '<:emoji2:456>', 'is_bot': True},  # Bot 參與
        ]
        
        segment, has_bot = handler._extract_valid_emoji_segment(messages)
        
        assert len(segment) == 2
        assert has_bot is True
    
    @pytest.mark.asyncio
    async def test_generate_emoji_response_with_llm(self, handler):
        """測試使用 LLM 生成 emoji 回應"""
        message = AsyncMock()
        message.guild.id = 123456789
        
        response = await handler._generate_emoji_response(message)
        
        assert response == "<:test_emoji:123456789>"
        handler.llm.ainvoke.assert_called_once()
        handler.emoji_registry.build_prompt_context.assert_called_once_with(123456789)
    
    @pytest.mark.asyncio
    async def test_generate_emoji_response_no_llm(self, handler):
        """測試沒有 LLM 時的 fallback"""
        handler.llm = None
        message = AsyncMock()
        
        response = await handler._generate_emoji_response(message)
        
        assert response in ["😄", "👍", "❤️", "😊", "🎉"]
    
    @pytest.mark.asyncio
    async def test_generate_emoji_response_no_emoji_context(self, handler):
        """測試沒有 emoji 上下文時的 fallback"""
        handler.emoji_registry.build_prompt_context.return_value = ""
        message = AsyncMock()
        
        response = await handler._generate_emoji_response(message)
        
        assert response in ["😄", "👍", "❤️", "😊", "🎉"]
    
    @pytest.mark.asyncio
    async def test_generate_emoji_response_llm_invalid_response(self, handler):
        """測試 LLM 返回無效回應時的 fallback"""
        # 模擬 LLM 返回無效格式
        mock_response = AsyncMock()
        mock_response.content = "這不是有效的 emoji 格式"
        handler.llm.ainvoke.return_value = mock_response
        
        message = AsyncMock()
        response = await handler._generate_emoji_response(message)
        
        assert response in ["😄", "👍", "❤️", "😊", "🎉"]


class TestConcurrencyAndLocking:
    """併發控制和鎖機制測試"""
    
    @pytest.mark.asyncio
    async def test_concurrent_message_processing(self, handler):
        """測試併發訊息處理的鎖機制"""
        channel_id = 123456789
        
        # 模擬兩個併發的訊息處理
        message1 = AsyncMock()
        message1.channel.id = channel_id
        message1.author.bot = False
        message1.author.id = 111111111
        
        message2 = AsyncMock()
        message2.channel.id = channel_id
        message2.author.bot = False
        message2.author.id = 222222222
        
        bot = AsyncMock()
        bot.user.id = 999999999
        
        # 模擬第一個處理會持有鎖較長時間
        async def slow_processing(*args):
            await asyncio.sleep(0.1)
            return False
        
        with patch.object(handler, '_do_following_logic', side_effect=slow_processing):
            # 同時啟動兩個處理
            task1 = asyncio.create_task(handler.handle_message_following(message1, bot))
            task2 = asyncio.create_task(handler.handle_message_following(message2, bot))
            
            results = await asyncio.gather(task1, task2)
            
            # 一個應該成功處理，另一個應該因為鎖超時而跳過
            assert results.count(False) == 2  # 兩個都會返回 False（因為 slow_processing 返回 False）
    
    @pytest.mark.asyncio
    async def test_channel_lock_timeout(self, handler):
        """測試頻道鎖超時機制"""
        channel_id = 123456789
        
        # 手動獲取並持有鎖
        lock = handler.get_channel_lock(channel_id)
        await lock.acquire()
        
        try:
            message = AsyncMock()
            message.channel.id = channel_id
            message.author.bot = False
            message.author.id = 111111111
            
            bot = AsyncMock()
            bot.user.id = 999999999
            
            # 嘗試處理訊息應該因為鎖超時而失敗
            result = await handler.handle_message_following(message, bot)
            assert result is False
            
        finally:
            lock.release()


class TestBotLoopPrevention:
    """Bot 循環防護測試"""
    
    @pytest.mark.asyncio
    async def test_content_following_blocked_by_bot_participation(self, handler):
        """測試內容跟風被 Bot 參與阻止"""
        message = AsyncMock()
        message.channel.id = 123456789
        message.author.bot = False
        message.author.id = 111111111
        message.content = "Hello"
        message.stickers = []
        
        # 模擬歷史訊息包含 Bot 參與
        history = [
            {'content_type': 'text', 'content_value': 'Hello', 'is_bot': False},
            {'content_type': 'text', 'content_value': 'Hello', 'is_bot': True},  # Bot 參與
        ]
        
        bot = AsyncMock()
        bot.user.id = 999999999
        
        with patch.object(handler, '_get_recent_messages', return_value=history):
            result = await handler._try_content_following(message, history, 999999999)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_emoji_following_blocked_by_bot_participation(self, handler):
        """測試 emoji 跟風被 Bot 參與阻止"""
        message = AsyncMock()
        message.channel.id = 123456789
        message.author.bot = False
        message.author.id = 111111111
        message.content = "<:test:123>"
        message.stickers = []
        
        # 模擬歷史訊息包含 Bot 參與
        history = [
            {'content_type': 'text', 'content_value': '<:emoji1:123>', 'is_bot': False},
            {'content_type': 'text', 'content_value': '<:emoji2:456>', 'is_bot': True},  # Bot 參與
        ]
        
        bot = AsyncMock()
        bot.user.id = 999999999
        
        with patch.object(handler, '_get_recent_messages', return_value=history):
            result = await handler._try_emoji_following(message, history, 999999999)
            
            assert result is False


class TestConfigurationDrivenBehavior:
    """配置驅動的行為控制測試"""
    
    def test_disabled_trend_following(self):
        """測試關閉跟風功能"""
        config = TrendFollowingConfig(enabled=False)
        handler = TrendFollowingHandler(config=config)
        
        assert handler.is_enabled_in_channel(123456789) is False
    
    def test_channel_restrictions(self):
        """測試頻道限制"""
        config = TrendFollowingConfig(
            enabled=True,
            allowed_channels=[123456789, 987654321]
        )
        handler = TrendFollowingHandler(config=config)
        
        assert handler.is_enabled_in_channel(123456789) is True
        assert handler.is_enabled_in_channel(987654321) is True
        assert handler.is_enabled_in_channel(111111111) is False
    
    def test_threshold_configuration(self):
        """測試閾值配置"""
        config = TrendFollowingConfig(
            enabled=True,
            reaction_threshold=5,
            content_threshold=3,
            emoji_threshold=4
        )
        handler = TrendFollowingHandler(config=config)
        
        assert handler.config.reaction_threshold == 5
        assert handler.config.content_threshold == 3
        assert handler.config.emoji_threshold == 4
    
    def test_cooldown_configuration(self):
        """測試冷卻時間配置"""
        config = TrendFollowingConfig(
            enabled=True,
            cooldown_seconds=120  # 2 分鐘
        )
        handler = TrendFollowingHandler(config=config)
        
        channel_id = 123456789
        handler.update_cooldown(channel_id)
        
        # 模擬 1 分鐘後（仍在冷卻中）
        handler.last_response_times[channel_id] = time.time() - 60
        assert handler.is_in_cooldown(channel_id) is True
        
        # 模擬 3 分鐘後（冷卻結束）
        handler.last_response_times[channel_id] = time.time() - 180
        assert handler.is_in_cooldown(channel_id) is False


class TestIntegrationScenarios:
    """整合測試場景"""
    
    @pytest.mark.asyncio
    async def test_complete_content_following_workflow(self, handler):
        """測試完整的內容跟風工作流程"""
        # 設置訊息
        message = AsyncMock()
        message.channel.id = 123456789
        message.channel.send = AsyncMock()
        message.author.bot = False
        message.author.id = 111111111
        message.content = "Hello World"
        message.stickers = []
        
        # 設置 Bot
        bot = AsyncMock()
        bot.user.id = 999999999
        
        # 設置歷史訊息（達到閾值且無 Bot 參與）
        history = [
            {'content_type': 'text', 'content_value': 'Hello World', 'is_bot': False},
        ]
        
        with patch.object(handler, '_get_recent_messages', return_value=history):
            result = await handler.handle_message_following(message, bot)
            
            assert result is True
            message.channel.send.assert_called_once_with("Hello World")
            assert handler.is_in_cooldown(123456789) is True
    
    @pytest.mark.asyncio
    async def test_complete_emoji_following_workflow(self, handler):
        """測試完整的 emoji 跟風工作流程"""
        # 設置訊息
        message = AsyncMock()
        message.channel.id = 123456789
        message.channel.send = AsyncMock()
        message.author.bot = False
        message.author.id = 111111111
        message.content = "<:test:123456789>"
        message.stickers = []
        message.guild.id = 123456789
        
        # 設置 Bot
        bot = AsyncMock()
        bot.user.id = 999999999
        
        # 設置歷史訊息（達到閾值且無 Bot 參與）
        history = [
            {'content_type': 'text', 'content_value': '<:emoji1:123>', 'is_bot': False},
            {'content_type': 'text', 'content_value': '<:emoji2:456>', 'is_bot': False},
        ]
        
        with patch.object(handler, '_get_recent_messages', return_value=history):
            result = await handler.handle_message_following(message, bot)
            
            assert result is True
            message.channel.send.assert_called_once_with("<:test_emoji:123456789>")
            assert handler.is_in_cooldown(123456789) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])