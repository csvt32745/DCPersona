"""
Emoji Sticker 配置系統測試

測試 EmojiStickerConfig 的載入、驗證和預設值功能。
"""

import pytest
import tempfile
import yaml
from pathlib import Path

from schemas.config_types import (
    AppConfig, 
    DiscordConfig, 
    EmojiStickerConfig,
    ConfigurationError
)


class TestEmojiStickerConfig:
    """測試 EmojiStickerConfig 配置類別"""
    
    def test_default_values(self):
        """測試預設配置值"""
        config = EmojiStickerConfig()
        
        assert config.max_emoji_per_message == 3
        assert config.max_sticker_per_message == 2
        assert config.max_animated_frames == 4
        assert config.emoji_sticker_max_size == 256
        assert config.enable_emoji_processing is True
        assert config.enable_sticker_processing is True
        assert config.enable_animated_processing is True
    
    def test_custom_values(self):
        """測試自定義配置值"""
        config = EmojiStickerConfig(
            max_emoji_per_message=5,
            max_sticker_per_message=3,
            max_animated_frames=6,
            emoji_sticker_max_size=512,
            enable_emoji_processing=False,
            enable_sticker_processing=False,
            enable_animated_processing=False
        )
        
        assert config.max_emoji_per_message == 5
        assert config.max_sticker_per_message == 3
        assert config.max_animated_frames == 6
        assert config.emoji_sticker_max_size == 512
        assert config.enable_emoji_processing is False
        assert config.enable_sticker_processing is False
        assert config.enable_animated_processing is False


class TestDiscordConfigIntegration:
    """測試 DiscordConfig 中的 EmojiStickerConfig 整合"""
    
    def test_default_emoji_sticker_config(self):
        """測試 DiscordConfig 中的預設 emoji_sticker 配置"""
        discord_config = DiscordConfig()
        
        assert isinstance(discord_config.emoji_sticker, EmojiStickerConfig)
        assert discord_config.emoji_sticker.max_emoji_per_message == 3
        assert discord_config.emoji_sticker.enable_emoji_processing is True
    
    def test_custom_emoji_sticker_config(self):
        """測試 DiscordConfig 中的自定義 emoji_sticker 配置"""
        emoji_sticker_config = EmojiStickerConfig(
            max_emoji_per_message=10,
            enable_emoji_processing=False
        )
        
        discord_config = DiscordConfig(emoji_sticker=emoji_sticker_config)
        
        assert discord_config.emoji_sticker.max_emoji_per_message == 10
        assert discord_config.emoji_sticker.enable_emoji_processing is False


class TestAppConfigIntegration:
    """測試 AppConfig 中的完整配置整合"""
    
    def test_default_app_config(self):
        """測試 AppConfig 中的預設配置"""
        app_config = AppConfig()
        
        assert isinstance(app_config.discord.emoji_sticker, EmojiStickerConfig)
        assert app_config.discord.emoji_sticker.max_emoji_per_message == 3
    
    def test_yaml_config_loading(self):
        """測試從 YAML 載入配置"""
        yaml_content = """
discord:
  bot_token: "test_token"
  emoji_sticker:
    max_emoji_per_message: 5
    max_sticker_per_message: 3
    emoji_sticker_max_size: 512
    enable_emoji_processing: false
"""
        
        # 建立臨時 YAML 檔案
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_file = f.name
        
        try:
            # 載入配置
            app_config = AppConfig.from_yaml(temp_file)
            
            # 驗證配置
            assert app_config.discord.bot_token == "test_token"
            assert app_config.discord.emoji_sticker.max_emoji_per_message == 5
            assert app_config.discord.emoji_sticker.max_sticker_per_message == 3
            assert app_config.discord.emoji_sticker.emoji_sticker_max_size == 512
            assert app_config.discord.emoji_sticker.enable_emoji_processing is False
            
            # 驗證未設定的值使用預設值
            assert app_config.discord.emoji_sticker.max_animated_frames == 4
            assert app_config.discord.emoji_sticker.enable_sticker_processing is True
            
        finally:
            # 清理臨時檔案
            Path(temp_file).unlink()
    
    def test_partial_yaml_config_loading(self):
        """測試部分 YAML 配置載入"""
        yaml_content = """
discord:
  emoji_sticker:
    max_emoji_per_message: 8
    enable_animated_processing: false
"""
        
        # 建立臨時 YAML 檔案
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_file = f.name
        
        try:
            # 載入配置
            app_config = AppConfig.from_yaml(temp_file)
            
            # 驗證設定的值
            assert app_config.discord.emoji_sticker.max_emoji_per_message == 8
            assert app_config.discord.emoji_sticker.enable_animated_processing is False
            
            # 驗證未設定的值使用預設值
            assert app_config.discord.emoji_sticker.max_sticker_per_message == 2
            assert app_config.discord.emoji_sticker.emoji_sticker_max_size == 256
            assert app_config.discord.emoji_sticker.enable_emoji_processing is True
            assert app_config.discord.emoji_sticker.enable_sticker_processing is True
            
        finally:
            # 清理臨時檔案
            Path(temp_file).unlink()
    
    def test_config_to_dict(self):
        """測試配置轉換為字典"""
        app_config = AppConfig()
        app_config.discord.emoji_sticker.max_emoji_per_message = 10
        
        config_dict = app_config.to_dict()
        
        assert config_dict['discord']['emoji_sticker']['max_emoji_per_message'] == 10
        assert config_dict['discord']['emoji_sticker']['enable_emoji_processing'] is True
    
    def test_config_from_dict(self):
        """測試從字典建立配置"""
        config_dict = {
            'discord': {
                'emoji_sticker': {
                    'max_emoji_per_message': 7,
                    'enable_sticker_processing': False
                }
            }
        }
        
        app_config = AppConfig.from_dict(config_dict)
        
        assert app_config.discord.emoji_sticker.max_emoji_per_message == 7
        assert app_config.discord.emoji_sticker.enable_sticker_processing is False
        # 驗證預設值
        assert app_config.discord.emoji_sticker.max_sticker_per_message == 2


class TestConfigValidation:
    """測試配置驗證功能"""
    
    def test_valid_config_values(self):
        """測試有效的配置值"""
        # 這些值應該都是有效的
        config = EmojiStickerConfig(
            max_emoji_per_message=0,  # 0 表示禁用
            max_sticker_per_message=100,  # 大數值
            max_animated_frames=1,  # 最小值
            emoji_sticker_max_size=64  # 小尺寸
        )
        
        assert config.max_emoji_per_message == 0
        assert config.max_sticker_per_message == 100
        assert config.max_animated_frames == 1
        assert config.emoji_sticker_max_size == 64
    
    def test_type_safety(self):
        """測試型別安全"""
        # 測試型別註解是否正確
        config = EmojiStickerConfig()
        
        assert isinstance(config.max_emoji_per_message, int)
        assert isinstance(config.max_sticker_per_message, int)
        assert isinstance(config.max_animated_frames, int)
        assert isinstance(config.emoji_sticker_max_size, int)
        assert isinstance(config.enable_emoji_processing, bool)
        assert isinstance(config.enable_sticker_processing, bool)
        assert isinstance(config.enable_animated_processing, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 