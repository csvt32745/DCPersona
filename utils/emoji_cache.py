"""
Emoji 圖片快取模組

提供 emoji 和 sticker 圖片的記憶體快取功能，使用 LRU 策略管理快取項目。
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from collections import OrderedDict


class EmojiImageCache:
    """
    Emoji 圖片記憶體快取機制
    
    使用 LRU 策略管理已處理的 emoji 圖片資料，避免重複下載和處理。
    """
    
    def __init__(self, max_size: int = 100):
        """
        初始化 emoji 圖片快取
        
        Args:
            max_size: 最大快取項目數量，預設 100
        """
        self.max_size = max_size
        self.cache: OrderedDict[str, Tuple[List[Dict[str, Any]], bool]] = OrderedDict()
        self.stats = {"hits": 0, "misses": 0}
        self.logger = logging.getLogger(__name__)
    
    def get(self, cache_key: str) -> Optional[Tuple[List[Dict[str, Any]], bool]]:
        """
        從快取中獲取處理後的 emoji 圖片資料
        
        Args:
            cache_key: 快取鍵值
            
        Returns:
            Optional[Tuple[List[Dict[str, Any]], bool]]: (base64_images, is_animated) 或 None
        """
        if cache_key in self.cache:
            # 移動到最後（最近使用）
            value = self.cache.pop(cache_key)
            self.cache[cache_key] = value
            self.stats["hits"] += 1
            self.logger.debug(f"快取命中: {cache_key}")
            return value
        
        self.stats["misses"] += 1
        self.logger.debug(f"快取未命中: {cache_key}")
        return None
    
    def put(self, cache_key: str, value: Tuple[List[Dict[str, Any]], bool]) -> None:
        """
        將處理後的 emoji 圖片資料存入快取
        
        Args:
            cache_key: 快取鍵值
            value: (base64_images, is_animated) 元組
        """
        # 如果已存在，先移除再重新加入
        if cache_key in self.cache:
            del self.cache[cache_key]
        
        # 加入新項目
        self.cache[cache_key] = value
        
        # 檢查快取大小限制
        while len(self.cache) > self.max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            self.logger.debug(f"移除最舊快取項目: {oldest_key}")
        
        self.logger.debug(f"快取儲存: {cache_key}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        獲取快取統計資訊
        
        Returns:
            Dict[str, Any]: 快取統計資訊
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": f"{hit_rate:.1f}%",
            "cache_size": len(self.cache),
            "max_size": self.max_size
        }
    
    def clear(self) -> None:
        """清空快取"""
        self.cache.clear()
        self.stats = {"hits": 0, "misses": 0}
        self.logger.info("快取已清空")


def generate_cache_key(media_id: int, max_size: int, frame_limit: int, media_type: str = "emoji") -> str:
    """
    生成快取鍵值
    
    Args:
        media_id: emoji 或 sticker 的 ID
        max_size: 圖片最大尺寸
        frame_limit: 動畫幀數限制
        media_type: 媒體類型 ("emoji" 或 "sticker")
        
    Returns:
        str: 快取鍵值
    """
    return f"{media_type}_{media_id}_{max_size}_{frame_limit}"


# 全域快取實例
_global_emoji_cache = EmojiImageCache(max_size=100)


def get_global_cache() -> EmojiImageCache:
    """
    獲取全域快取實例
    
    Returns:
        EmojiImageCache: 全域快取實例
    """
    return _global_emoji_cache


def get_cache_stats() -> Dict[str, Any]:
    """
    獲取全域快取統計資訊
    
    Returns:
        Dict[str, Any]: 快取統計資訊
    """
    return _global_emoji_cache.get_stats()


def clear_cache() -> None:
    """
    清空全域快取
    """
    _global_emoji_cache.clear()