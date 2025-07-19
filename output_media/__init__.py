"""
Output Media 輸出媒體處理模組

負責處理 Bot 回覆中的媒體內容：
- Emoji 格式化與註冊
- Sticker 管理（預留接口）
- 多媒體內容上下文建構
"""

from .emoji_registry import EmojiRegistry
from .emoji_types import EmojiConfig
from .sticker_registry import OutputStickerRegistry
from .context_builder import OutputMediaContextBuilder

__all__ = ["EmojiRegistry", "EmojiConfig", "OutputStickerRegistry", "OutputMediaContextBuilder"] 