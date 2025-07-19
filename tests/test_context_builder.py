"""
Output Media Context Builder 測試

測試 OutputMediaContextBuilder 的功能，包括整合 emoji 和 sticker 註冊器。
"""

import pytest
from unittest.mock import Mock, patch

from output_media.context_builder import OutputMediaContextBuilder
from output_media.emoji_registry import EmojiRegistry
from output_media.sticker_registry import OutputStickerRegistry
from output_media.emoji_types import EmojiConfig


class TestOutputMediaContextBuilder:
    """測試 OutputMediaContextBuilder 基本功能"""
    
    def test_init_no_registries(self):
        """測試不提供任何註冊器的初始化"""
        builder = OutputMediaContextBuilder()
        
        assert builder.emoji_registry is None
        assert builder.sticker_registry is None
    
    def test_init_with_registries(self):
        """測試提供註冊器的初始化"""
        emoji_registry = Mock(spec=EmojiRegistry)
        sticker_registry = Mock(spec=OutputStickerRegistry)
        
        builder = OutputMediaContextBuilder(
            emoji_registry=emoji_registry,
            sticker_registry=sticker_registry
        )
        
        assert builder.emoji_registry is emoji_registry
        assert builder.sticker_registry is sticker_registry
    
    def test_build_full_context_empty(self):
        """測試空的上下文建構"""
        builder = OutputMediaContextBuilder()
        
        context = builder.build_full_context()
        
        assert context == ""
    
    def test_build_emoji_context_no_registry(self):
        """測試沒有 emoji 註冊器時的上下文建構"""
        builder = OutputMediaContextBuilder()
        
        context = builder.build_emoji_context()
        
        assert context == ""
    
    def test_build_sticker_context_no_registry(self):
        """測試沒有 sticker 註冊器時的上下文建構"""
        builder = OutputMediaContextBuilder()
        
        context = builder.build_sticker_context()
        
        assert context == ""
    
    def test_has_media_available_false(self):
        """測試沒有媒體可用時的檢查"""
        builder = OutputMediaContextBuilder()
        
        assert builder.has_media_available() is False


class TestOutputMediaContextBuilderWithEmojiRegistry:
    """測試有 emoji 註冊器的 OutputMediaContextBuilder"""
    
    @pytest.fixture
    def mock_emoji_registry(self):
        """建立 mock emoji 註冊器"""
        registry = Mock(spec=EmojiRegistry)
        return registry
    
    @pytest.fixture
    def builder_with_emoji(self, mock_emoji_registry):
        """建立有 emoji 註冊器的 context builder"""
        return OutputMediaContextBuilder(emoji_registry=mock_emoji_registry)
    
    def test_build_emoji_context_with_registry(self, builder_with_emoji, mock_emoji_registry):
        """測試有 emoji 註冊器時的上下文建構"""
        expected_context = "Test emoji context"
        mock_emoji_registry.build_prompt_context.return_value = expected_context
        
        context = builder_with_emoji.build_emoji_context(guild_id=123)
        
        mock_emoji_registry.build_prompt_context.assert_called_once_with(123)
        assert context == expected_context
    
    def test_build_full_context_emoji_only(self, builder_with_emoji, mock_emoji_registry):
        """測試僅有 emoji 時的完整上下文建構"""
        emoji_context = "Test emoji context"
        mock_emoji_registry.build_prompt_context.return_value = emoji_context
        
        context = builder_with_emoji.build_full_context(guild_id=456)
        
        mock_emoji_registry.build_prompt_context.assert_called_once_with(456)
        assert "Test emoji context" in context
        assert "Emoji 格式：" in context
        assert "媒體使用規則" in context
    
    def test_has_media_available_with_emoji(self, builder_with_emoji, mock_emoji_registry):
        """測試有 emoji 可用時的檢查"""
        mock_emoji_registry.build_prompt_context.return_value = "Some emoji context"
        
        assert builder_with_emoji.has_media_available() is True
        
        mock_emoji_registry.build_prompt_context.assert_called_once_with(None)
    
    def test_get_media_stats_with_emoji(self, builder_with_emoji, mock_emoji_registry):
        """測試獲取 emoji 統計資訊"""
        expected_stats = {"application_emojis": 5, "guild_emojis": 10}
        mock_emoji_registry.get_stats.return_value = expected_stats
        
        stats = builder_with_emoji.get_media_stats()
        
        assert stats["emoji"] == expected_stats
        assert stats["total_media_types"] == 1
        assert stats["sticker"] == {}


class TestOutputMediaContextBuilderWithStickerRegistry:
    """測試有 sticker 註冊器的 OutputMediaContextBuilder"""
    
    @pytest.fixture
    def mock_sticker_registry(self):
        """建立 mock sticker 註冊器"""
        registry = Mock(spec=OutputStickerRegistry)
        return registry
    
    @pytest.fixture
    def builder_with_sticker(self, mock_sticker_registry):
        """建立有 sticker 註冊器的 context builder"""
        return OutputMediaContextBuilder(sticker_registry=mock_sticker_registry)
    
    def test_build_sticker_context_with_registry(self, builder_with_sticker, mock_sticker_registry):
        """測試有 sticker 註冊器時的上下文建構"""
        expected_context = "Test sticker context"
        mock_sticker_registry.build_prompt_context.return_value = expected_context
        
        context = builder_with_sticker.build_sticker_context(guild_id=789)
        
        mock_sticker_registry.build_prompt_context.assert_called_once_with(789)
        assert context == expected_context
    
    def test_get_media_stats_with_sticker(self, builder_with_sticker, mock_sticker_registry):
        """測試獲取 sticker 統計資訊"""
        expected_stats = {"available_stickers": 3, "status": "not_implemented"}
        mock_sticker_registry.get_stats.return_value = expected_stats
        
        stats = builder_with_sticker.get_media_stats()
        
        assert stats["sticker"] == expected_stats
        assert stats["total_media_types"] == 0  # 因為 status 是 not_implemented
        assert stats["emoji"] == {}


class TestOutputMediaContextBuilderComplete:
    """測試完整的 OutputMediaContextBuilder（包含 emoji 和 sticker）"""
    
    @pytest.fixture
    def mock_emoji_registry(self):
        """建立 mock emoji 註冊器"""
        registry = Mock(spec=EmojiRegistry)
        return registry
    
    @pytest.fixture
    def mock_sticker_registry(self):
        """建立 mock sticker 註冊器"""
        registry = Mock(spec=OutputStickerRegistry)
        return registry
    
    @pytest.fixture
    def complete_builder(self, mock_emoji_registry, mock_sticker_registry):
        """建立完整的 context builder"""
        return OutputMediaContextBuilder(
            emoji_registry=mock_emoji_registry,
            sticker_registry=mock_sticker_registry
        )
    
    def test_build_full_context_both_types(
        self, 
        complete_builder, 
        mock_emoji_registry, 
        mock_sticker_registry
    ):
        """測試同時有 emoji 和 sticker 的完整上下文建構"""
        emoji_context = "Emoji context"
        sticker_context = "Sticker context"
        
        mock_emoji_registry.build_prompt_context.return_value = emoji_context
        mock_sticker_registry.build_prompt_context.return_value = sticker_context
        
        context = complete_builder.build_full_context(guild_id=999)
        
        mock_emoji_registry.build_prompt_context.assert_called_once_with(999)
        mock_sticker_registry.build_prompt_context.assert_called_once_with(999)
        
        assert "Emoji context" in context
        assert "Sticker context" in context
        assert "Emoji 格式：" in context
        assert "Sticker 格式：" in context
    
    def test_build_full_context_empty_contexts(
        self, 
        complete_builder, 
        mock_emoji_registry, 
        mock_sticker_registry
    ):
        """測試當兩個註冊器都返回空上下文時"""
        mock_emoji_registry.build_prompt_context.return_value = ""
        mock_sticker_registry.build_prompt_context.return_value = ""
        
        context = complete_builder.build_full_context()
        
        assert context == ""
    
    def test_has_media_available_both_empty(
        self, 
        complete_builder, 
        mock_emoji_registry, 
        mock_sticker_registry
    ):
        """測試當兩個註冊器都沒有可用媒體時"""
        mock_emoji_registry.build_prompt_context.return_value = ""
        mock_sticker_registry.build_prompt_context.return_value = ""
        
        assert complete_builder.has_media_available() is False
    
    def test_has_media_available_emoji_only(
        self, 
        complete_builder, 
        mock_emoji_registry, 
        mock_sticker_registry
    ):
        """測試當只有 emoji 可用時"""
        mock_emoji_registry.build_prompt_context.return_value = "Some emoji"
        mock_sticker_registry.build_prompt_context.return_value = ""
        
        assert complete_builder.has_media_available() is True
    
    def test_get_media_stats_complete(
        self, 
        complete_builder, 
        mock_emoji_registry, 
        mock_sticker_registry
    ):
        """測試獲取完整統計資訊"""
        emoji_stats = {"application_emojis": 2, "guild_emojis": 5}
        sticker_stats = {"available_stickers": 3, "status": "active"}
        
        mock_emoji_registry.get_stats.return_value = emoji_stats
        mock_sticker_registry.get_stats.return_value = sticker_stats
        
        stats = complete_builder.get_media_stats()
        
        assert stats["emoji"] == emoji_stats
        assert stats["sticker"] == sticker_stats
        assert stats["total_media_types"] == 2  # 兩種都可用


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 