"""
Sticker 註冊器

統一的 OutputStickerRegistry 類別，負載 Discord Bot 的 sticker 輸出功能。
目前僅提供介面定義，實際功能待後續實作。
"""

import logging
from typing import Dict, Optional, List


class OutputStickerRegistry:
    """
    輸出 Sticker 註冊器
    
    負責管理 Bot 回覆中的 sticker 內容（預留介面）。
    未來將支援：
    - Sticker 驗證與快取
    - Sticker placeholder 生成
    - 動態 sticker 下載與傳送
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 OutputStickerRegistry
        
        Args:
            config_path: sticker 配置檔案路徑（預留）
        """
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path
        
        # TODO: 載入 sticker 配置
        self.available_stickers: Dict[int, str] = {}  # {sticker_id: placeholder}
        
        self.logger.info("OutputStickerRegistry 已初始化（預留介面）")
    
    async def load_stickers(self) -> None:
        """
        載入和驗證可用的 sticker（預留）
        
        TODO: 實作以下功能：
        - 從配置文件載入 sticker ID 列表
        - 驗證 sticker 可用性
        - 建立 placeholder 映射
        """
        self.logger.info("Sticker 載入功能尚未實作")
        pass
    
    def build_prompt_context(self, guild_id: Optional[int] = None) -> str:
        """
        生成提供給 LLM 的 sticker 提示上下文（預留）
        
        Args:
            guild_id: 可選的伺服器 ID
            
        Returns:
            str: 格式化的提示上下文
            
        TODO: 實作 sticker 提示上下文生成
        """
        # 暫時返回空字串，避免影響現有功能
        return ""
    
    def format_sticker_placeholder(self, sticker_id: int) -> str:
        """
        格式化 sticker placeholder（預留）
        
        Args:
            sticker_id: Sticker ID
            
        Returns:
            str: 格式化的 placeholder 字串
            
        TODO: 實作 sticker placeholder 格式化
        預計格式：<sticker:sticker_id>
        """
        # 預定義格式
        return f"<sticker:{sticker_id}>"
    
    async def process_sticker_placeholders(self, content: str) -> str:
        """
        處理訊息中的 sticker placeholder（預留）
        
        Args:
            content: 包含 placeholder 的訊息內容
            
        Returns:
            str: 處理後的訊息內容
            
        TODO: 實作以下功能：
        - 解析 <sticker:id> placeholder
        - 驗證 sticker 可用性
        - 準備實際 sticker 傳送
        """
        # 暫時直接返回原內容
        return content
    
    def get_stats(self) -> Dict[str, int]:
        """
        獲取 sticker 統計資訊（預留）
        
        Returns:
            Dict[str, int]: 統計資訊
        """
        return {
            "available_stickers": len(self.available_stickers),
            "total_stickers": 0,  # TODO: 實作總計統計
            "status": "not_implemented"
        } 