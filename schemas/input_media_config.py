"""
輸入媒體配置

定義處理用戶輸入媒體（Emoji、Sticker、圖片）的配置參數。
"""

from dataclasses import dataclass


@dataclass
class InputMediaConfig:
    """輸入媒體處理配置
    
    管理從 Discord 訊息中解析和處理媒體內容的配置選項：
    - Emoji 解析與驗證
    - Sticker 下載與處理
    - 圖片處理限制
    """
    max_emoji_per_message: int = 3
    max_sticker_per_message: int = 2
    max_animated_frames: int = 4
    emoji_sticker_max_size: int = 256
    enable_emoji_processing: bool = True
    enable_sticker_processing: bool = True
    enable_animated_processing: bool = True 