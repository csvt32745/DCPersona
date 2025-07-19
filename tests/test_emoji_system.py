"""
Emoji 系統測試

測試 EmojiConfig、EmojiHandler 和整體 emoji 功能的單元測試和整合測試。
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

from output_media.emoji_types import EmojiConfig
from output_media.emoji_registry import EmojiRegistry
from discord_bot.progress_adapter import DiscordProgressAdapter


class TestEmojiConfig:
    """測試 EmojiConfig 資料結構"""
    
    def test_emoji_config_creation(self):
        """測試 EmojiConfig 基本創建"""
        config = EmojiConfig(
            application={123456789: "test emoji"},
            guilds={999888777: {987654321: "guild emoji"}}
        )
        
        assert config.application == {123456789: "test emoji"}
        assert config.guilds == {999888777: {987654321: "guild emoji"}}
    
    def test_emoji_config_from_yaml_valid(self):
        """測試從有效 YAML 載入配置"""
        yaml_content = """
application:
  123456789: "test emoji"
  987654321: "another emoji"

999888777:
  111222333: "guild emoji 1"
  444555666: "guild emoji 2"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(yaml_content)
            f.flush()
            
            try:
                config = EmojiConfig.from_yaml(f.name)
                
                assert len(config.application) == 2
                assert config.application[123456789] == "test emoji"
                assert config.application[987654321] == "another emoji"
                
                assert len(config.guilds) == 1
                assert 999888777 in config.guilds
                assert len(config.guilds[999888777]) == 2
                assert config.guilds[999888777][111222333] == "guild emoji 1"
                assert config.guilds[999888777][444555666] == "guild emoji 2"
                
            finally:
                try:
                    os.unlink(f.name)
                except PermissionError:
                    pass  # Skip cleanup on Windows if file is locked
    
    def test_emoji_config_from_yaml_empty_file(self):
        """測試從空 YAML 檔案載入"""
        yaml_content = ""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(yaml_content)
            f.flush()
            
            try:
                config = EmojiConfig.from_yaml(f.name)
                assert config.application == {}
                assert config.guilds == {}
            finally:
                try:
                    os.unlink(f.name)
                except PermissionError:
                    pass  # Skip cleanup on Windows if file is locked
    
    def test_emoji_config_from_yaml_nonexistent_file(self):
        """測試載入不存在的檔案"""
        config = EmojiConfig.from_yaml("nonexistent_file.yaml")
        assert config.application == {}
        assert config.guilds == {}
    
    def test_emoji_config_from_yaml_invalid_emoji_id(self):
        """測試無效的 emoji ID 會被跳過"""
        yaml_content = """
application:
  123456789: "valid emoji"
  invalid_id: "invalid emoji"
  987654321: "another valid emoji"

999888777:
  111222333: "valid guild emoji"
  another_invalid: "invalid guild emoji"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(yaml_content)
            f.flush()
            
            try:
                config = EmojiConfig.from_yaml(f.name)
                
                # 只有有效的 emoji ID 應該被載入
                assert len(config.application) == 2
                assert 123456789 in config.application
                assert 987654321 in config.application
                
                assert len(config.guilds[999888777]) == 1
                assert 111222333 in config.guilds[999888777]
                
            finally:
                try:
                    os.unlink(f.name)
                except PermissionError:
                    pass  # Skip cleanup on Windows if file is locked
    
    def test_emoji_config_from_yaml_invalid_guild_id(self):
        """測試無效的 guild ID 會被跳過"""
        yaml_content = """
application:
  123456789: "app emoji"

999888777:
  111222333: "valid guild emoji"

invalid_guild:
  444555666: "invalid guild emoji"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(yaml_content)
            f.flush()
            
            try:
                config = EmojiConfig.from_yaml(f.name)
                
                assert len(config.application) == 1
                assert len(config.guilds) == 1
                assert 999888777 in config.guilds
                
            finally:
                try:
                    os.unlink(f.name)
                except PermissionError:
                    pass  # Skip cleanup on Windows if file is locked


class TestEmojiHandler:
    """測試 EmojiHandler 類別"""
    
    @pytest.fixture
    def sample_config(self):
        """提供測試用的 EmojiConfig"""
        return EmojiConfig(
            application={
                123456789: "test emoji",
                987654321: "another emoji"
            },
            guilds={
                999888777: {
                    111222333: "guild emoji 1",
                    444555666: "guild emoji 2"
                }
            }
        )
    
    @pytest.fixture
    def emoji_handler(self, sample_config):
        """提供測試用的 EmojiRegistry"""
        with patch('output_media.emoji_types.EmojiConfig.from_yaml', return_value=sample_config):
            handler = EmojiRegistry("test_config.yaml")
            return handler
    
    def test_emoji_handler_initialization(self, emoji_handler):
        """測試 EmojiHandler 初始化"""
        assert emoji_handler.available_emojis == {}
        assert emoji_handler.emoji_lookup == {}
        assert emoji_handler.config is not None
    
    @pytest.mark.asyncio
    async def test_load_application_emojis(self, emoji_handler):
        """測試載入應用程式 emoji"""
        # 模擬 Discord 客戶端和 emoji
        mock_client = Mock()
        mock_emoji1 = Mock()
        mock_emoji1.id = 123456789
        mock_emoji1.name = "test_emoji"
        
        mock_emoji2 = Mock()
        mock_emoji2.id = 987654321
        mock_emoji2.name = "another_emoji"
        
        # 模擬未配置的 emoji（應該被跳過）
        mock_emoji3 = Mock()
        mock_emoji3.id = 555555555
        mock_emoji3.name = "unconfigured_emoji"
        
        mock_client.fetch_application_emojis = AsyncMock(
            return_value=[mock_emoji1, mock_emoji2, mock_emoji3]
        )
        mock_client.guilds = []  # Add empty guilds list
        
        await emoji_handler.load_emojis(mock_client)
        
        # 檢查只有配置中的 emoji 被載入
        assert len(emoji_handler.available_emojis[-1]) == 2
        assert 123456789 in emoji_handler.available_emojis[-1]
        assert 987654321 in emoji_handler.available_emojis[-1]
        assert 555555555 not in emoji_handler.available_emojis[-1]
        
        # 檢查 emoji_lookup
        assert len(emoji_handler.emoji_lookup[-1]) == 2
        assert 123456789 in emoji_handler.emoji_lookup[-1]
        assert 987654321 in emoji_handler.emoji_lookup[-1]
    
    @pytest.mark.asyncio
    async def test_load_guild_emojis(self, emoji_handler):
        """測試載入伺服器 emoji"""
        # 模擬 Discord 客戶端
        mock_client = Mock()
        mock_client.fetch_application_emojis = AsyncMock(return_value=[])
        
        # 模擬伺服器
        mock_guild = Mock()
        mock_guild.id = 999888777
        mock_guild.name = "Test Guild"
        
        # 模擬伺服器 emoji
        mock_emoji1 = Mock()
        mock_emoji1.id = 111222333
        mock_emoji1.name = "guild_emoji1"
        
        mock_emoji2 = Mock()
        mock_emoji2.id = 444555666
        mock_emoji2.name = "guild_emoji2"
        
        mock_guild.fetch_emojis = AsyncMock(return_value=[mock_emoji1, mock_emoji2])
        mock_client.guilds = [mock_guild]
        
        await emoji_handler.load_emojis(mock_client)
        
        # 檢查伺服器 emoji 被載入
        assert 999888777 in emoji_handler.available_emojis
        assert len(emoji_handler.available_emojis[999888777]) == 2
        assert 111222333 in emoji_handler.available_emojis[999888777]
        assert 444555666 in emoji_handler.available_emojis[999888777]
    
    def test_build_prompt_context_empty_config(self):
        """測試空配置的提示上下文生成"""
        empty_config = EmojiConfig(application={}, guilds={})
        with patch('output_media.emoji_types.EmojiConfig.from_yaml', return_value=empty_config):
            handler = EmojiRegistry("test_config.yaml")
            context = handler.build_prompt_context()
            assert context == ""
    
    def test_build_prompt_context_with_emojis(self, emoji_handler):
        """測試有 emoji 的提示上下文生成"""
        # 模擬已載入的 emoji
        mock_emoji1 = Mock()
        mock_emoji1.name = "test_emoji"
        mock_emoji1.id = 123456789
        mock_emoji1.__str__ = Mock(return_value="<:test_emoji:123456789>")
        
        mock_emoji2 = Mock()
        mock_emoji2.name = "guild_emoji"
        mock_emoji2.id = 111222333
        mock_emoji2.__str__ = Mock(return_value="<:guild_emoji:111222333>")
        
        emoji_handler.available_emojis[-1] = {123456789: mock_emoji1}
        emoji_handler.available_emojis[999888777] = {111222333: mock_emoji2}
        
        # 測試只有應用程式 emoji
        context = emoji_handler.build_prompt_context()
        assert "可用的應用程式 Emoji" in context
        assert "<:test_emoji:123456789>" in context
        assert "test emoji" in context
        
        # 測試包含伺服器 emoji
        context_with_guild = emoji_handler.build_prompt_context(999888777)
        assert "可用的應用程式 Emoji" in context_with_guild
        assert "當前伺服器可用的 Emoji" in context_with_guild
        assert "<:guild_emoji:111222333>" in context_with_guild
        assert "guild emoji 1" in context_with_guild
    
    def test_format_emoji_output_no_emojis(self, emoji_handler):
        """測試沒有 emoji 標記的文字格式化 - 現在此方法已移除"""
        # 此測試已不再需要，因為 format_emoji_output 方法已移除
        pass
    
    def test_format_emoji_output_with_valid_emojis(self, emoji_handler):
        """測試有效 emoji 標記的格式化 - 現在此方法已移除"""
        # 此測試已不再需要，因為 format_emoji_output 方法已移除
        pass
    
    def test_format_emoji_output_invalid_emoji_id(self, emoji_handler):
        """測試無效 emoji ID 的處理 - 現在此方法已移除"""
        # 此測試已不再需要，因為 format_emoji_output 方法已移除
        pass
    
    def test_format_emoji_output_mixed_valid_invalid(self, emoji_handler):
        """測試混合有效和無效 emoji 的處理 - 現在此方法已移除"""
        # 此測試已不再需要，因為 format_emoji_output 方法已移除
        pass
    
    def test_get_stats(self, emoji_handler):
        """測試統計資訊獲取"""
        # 設置測試數據
        emoji_handler.available_emojis[-1] = {123: "app1", 456: "app2"}
        emoji_handler.available_emojis[999] = {789: "guild1"}
        emoji_handler.available_emojis[888] = {111: "guild2", 222: "guild3"}
        
        stats = emoji_handler.get_stats()
        
        assert stats["application_emojis"] == 2
        assert stats["guild_emojis"] == 3
        assert stats["total_emojis"] == 5
        assert stats["configured_guilds"] == 2


class TestEmojiIntegration:
    """測試 emoji 系統整合"""
    
    @pytest.mark.asyncio
    async def test_progress_adapter_emoji_formatting(self):
        """測試 DiscordProgressAdapter 中的 emoji 格式化 - 現在不再需要格式化"""
        # 模擬 Discord 訊息
        mock_message = Mock()
        mock_message.guild.id = 999888777
        
        # 模擬 EmojiHandler
        mock_emoji_handler = Mock()
        
        # 創建 DiscordProgressAdapter
        adapter = DiscordProgressAdapter(mock_message, mock_emoji_handler)
        
        # 模擬 progress_manager
        adapter.progress_manager = Mock()
        adapter.progress_manager.send_or_update_progress = AsyncMock()
        
        # 測試 on_completion 中的 emoji 格式化
        await adapter.on_completion("測試文字 <:test:123456789>", [])
        
        # 驗證 emoji 直接傳遞，沒有呼叫 format_emoji_output
        adapter.progress_manager.send_or_update_progress.assert_called_once()
        call_args = adapter.progress_manager.send_or_update_progress.call_args
        assert call_args[1]["final_answer"] == "測試文字 <:test:123456789>"
    
    @pytest.mark.asyncio 
    async def test_progress_adapter_no_emoji_handler(self):
        """測試沒有 emoji_handler 時的處理"""
        mock_message = Mock()
        
        # 創建沒有 emoji_handler 的 DiscordProgressAdapter
        adapter = DiscordProgressAdapter(mock_message, None)
        adapter.progress_manager = Mock()
        adapter.progress_manager.send_or_update_progress = AsyncMock()
        
        # 測試 on_completion
        await adapter.on_completion("測試文字 [emoji:123456789]", [])
        
        # 驗證原始文字被發送（沒有格式化）
        call_args = adapter.progress_manager.send_or_update_progress.call_args
        assert call_args[1]["final_answer"] == "測試文字 [emoji:123456789]"
    
    @pytest.mark.asyncio
    async def test_streaming_emoji_formatting(self):
        """測試串流模式的 emoji 格式化 - 現在不再需要格式化"""
        mock_message = Mock()
        mock_message.guild.id = 999888777
        
        mock_emoji_handler = Mock()
        
        adapter = DiscordProgressAdapter(mock_message, mock_emoji_handler)
        adapter.progress_manager = Mock()
        adapter.progress_manager.send_or_update_progress = AsyncMock(return_value=Mock())
        
        # 模擬串流內容
        adapter._streaming_content = "串流文字 <:emoji:123456789>"
        
        # 測試 _update_streaming_message
        await adapter._update_streaming_message()
        
        # 驗證 emoji 直接傳遞，沒有呼叫 format_emoji_output
        adapter.progress_manager.send_or_update_progress.assert_called_once()


class TestEmojiRealWorldScenarios:
    """測試真實世界情境"""
    
    def test_real_emoji_config_structure(self):
        """測試真實的 emoji 配置結構"""
        # 基於用戶提供的配置結構
        real_config_content = """
application:
  1362820638489972937: cute signature expression

730024186852147240:
  959699262587928586: smug turtle
  791232834697953330: funny frog
  1234032272123101214: thinking frog weird
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(real_config_content)
            f.flush()
            
            try:
                config = EmojiConfig.from_yaml(f.name)
                
                # 驗證應用程式 emoji
                assert len(config.application) == 1
                assert 1362820638489972937 in config.application
                assert config.application[1362820638489972937] == "cute signature expression"
                
                # 驗證伺服器 emoji
                assert len(config.guilds) == 1
                assert 730024186852147240 in config.guilds
                guild_emojis = config.guilds[730024186852147240]
                assert len(guild_emojis) == 3
                assert guild_emojis[959699262587928586] == "smug turtle"
                assert guild_emojis[791232834697953330] == "funny frog"
                
            finally:
                try:
                    os.unlink(f.name)
                except PermissionError:
                    pass  # Skip cleanup on Windows if file is locked
    
    def test_emoji_handler_with_real_data(self):
        """測試使用真實數據的 EmojiHandler"""
        config = EmojiConfig(
            application={1362820638489972937: "cute signature expression"},
            guilds={
                730024186852147240: {
                    959699262587928586: "smug turtle",
                    791232834697953330: "funny frog"
                }
            }
        )
        
        with patch('output_media.emoji_types.EmojiConfig.from_yaml', return_value=config):
            handler = EmojiRegistry("test_config.yaml")
            
            # 模擬已載入的 emoji
            mock_app_emoji = Mock()
            mock_app_emoji.__str__ = Mock(return_value="<:kawaii:1362820638489972937>")
            
            mock_guild_emoji1 = Mock()
            mock_guild_emoji1.__str__ = Mock(return_value="<:turtle_smug:959699262587928586>")
            
            mock_guild_emoji2 = Mock()
            mock_guild_emoji2.__str__ = Mock(return_value="<:frog_funny:791232834697953330>")
            
            handler.available_emojis[-1] = {1362820638489972937: mock_app_emoji}
            handler.available_emojis[730024186852147240] = {
                959699262587928586: mock_guild_emoji1,
                791232834697953330: mock_guild_emoji2
            }
            
            # 測試 build_prompt_context
            context = handler.build_prompt_context(730024186852147240)
            assert "<:kawaii:1362820638489972937>" in context
            assert "<:turtle_smug:959699262587928586>" in context
            assert "<:frog_funny:791232834697953330>" in context
            assert "cute signature expression" in context
            assert "smug turtle" in context
            assert "funny frog" in context