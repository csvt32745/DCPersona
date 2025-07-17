"""
Emoji Cache 單元測試

測試 emoji 圖片快取功能的正確性和效能。
"""

import pytest
from typing import Dict, Any, List
from unittest.mock import Mock, patch
from utils.emoji_cache import (
    EmojiImageCache,
    generate_cache_key,
    get_global_cache,
    get_cache_stats,
    clear_cache
)


class TestEmojiImageCache:
    """測試 EmojiImageCache 類別"""
    
    def setup_method(self):
        """每個測試方法前的設定"""
        self.cache = EmojiImageCache(max_size=3)
        self.test_data = [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,test1"}}
        ]
    
    def test_cache_initialization(self):
        """測試快取初始化"""
        assert self.cache.max_size == 3
        assert len(self.cache.cache) == 0
        assert self.cache.stats == {"hits": 0, "misses": 0}
    
    def test_cache_miss(self):
        """測試快取未命中"""
        result = self.cache.get("nonexistent_key")
        assert result is None
        assert self.cache.stats["misses"] == 1
        assert self.cache.stats["hits"] == 0
    
    def test_cache_hit(self):
        """測試快取命中"""
        key = "test_key"
        value = (self.test_data, False)
        
        # 先儲存
        self.cache.put(key, value)
        
        # 再讀取
        result = self.cache.get(key)
        assert result == value
        assert self.cache.stats["hits"] == 1
        assert self.cache.stats["misses"] == 0
    
    def test_cache_put_and_get(self):
        """測試快取儲存和讀取"""
        key = "test_key"
        value = (self.test_data, True)
        
        self.cache.put(key, value)
        result = self.cache.get(key)
        
        assert result == value
        assert len(self.cache.cache) == 1
    
    def test_cache_lru_eviction(self):
        """測試 LRU 清理機制"""
        # 填滿快取
        for i in range(3):
            self.cache.put(f"key_{i}", (self.test_data, False))
        
        assert len(self.cache.cache) == 3
        
        # 加入第 4 個項目應該移除最舊的
        self.cache.put("key_3", (self.test_data, True))
        
        assert len(self.cache.cache) == 3
        assert self.cache.get("key_0") is None  # 最舊的應該被移除
        assert self.cache.get("key_3") is not None  # 新的應該存在
    
    def test_cache_lru_access_order(self):
        """測試 LRU 存取順序"""
        # 填滿快取
        for i in range(3):
            self.cache.put(f"key_{i}", (self.test_data, False))
        
        # 存取 key_0，使其成為最近使用的
        self.cache.get("key_0")
        
        # 加入新項目
        self.cache.put("key_3", (self.test_data, True))
        
        # key_0 應該還在（因為被存取過），key_1 應該被移除
        assert self.cache.get("key_0") is not None
        assert self.cache.get("key_1") is None
        assert self.cache.get("key_3") is not None
    
    def test_cache_update_existing(self):
        """測試更新現有項目"""
        key = "test_key"
        value1 = (self.test_data, False)
        value2 = ([{"type": "image_url", "image_url": {"url": "data:image/png;base64,test2"}}], True)
        
        self.cache.put(key, value1)
        self.cache.put(key, value2)
        
        result = self.cache.get(key)
        assert result == value2
        assert len(self.cache.cache) == 1
    
    def test_get_stats(self):
        """測試統計資訊"""
        # 初始統計
        stats = self.cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == "0.0%"
        assert stats["cache_size"] == 0
        assert stats["max_size"] == 3
        
        # 加入一些操作
        self.cache.put("key1", (self.test_data, False))
        self.cache.get("key1")  # hit
        self.cache.get("key2")  # miss
        
        stats = self.cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == "50.0%"
        assert stats["cache_size"] == 1
    
    def test_clear_cache(self):
        """測試清空快取"""
        self.cache.put("key1", (self.test_data, False))
        self.cache.put("key2", (self.test_data, True))
        
        assert len(self.cache.cache) == 2
        
        self.cache.clear()
        
        assert len(self.cache.cache) == 0
        assert self.cache.stats == {"hits": 0, "misses": 0}


class TestCacheKeyGeneration:
    """測試快取鍵值生成"""
    
    def test_generate_cache_key_emoji(self):
        """測試生成 emoji 快取鍵值"""
        key = generate_cache_key(123456, 256, 4, "emoji")
        assert key == "emoji_123456_256_4"
    
    def test_generate_cache_key_sticker(self):
        """測試生成 sticker 快取鍵值"""
        key = generate_cache_key(789012, 128, 1, "sticker")
        assert key == "sticker_789012_128_1"
    
    def test_generate_cache_key_default_type(self):
        """測試預設類型"""
        key = generate_cache_key(111111, 256, 4)
        assert key == "emoji_111111_256_4"
    
    def test_generate_cache_key_uniqueness(self):
        """測試不同參數產生不同鍵值"""
        key1 = generate_cache_key(123456, 256, 4, "emoji")
        key2 = generate_cache_key(123456, 128, 4, "emoji")
        key3 = generate_cache_key(123456, 256, 1, "emoji")
        key4 = generate_cache_key(123456, 256, 4, "sticker")
        
        keys = [key1, key2, key3, key4]
        assert len(set(keys)) == 4  # 所有鍵值都應該不同


class TestGlobalCache:
    """測試全域快取功能"""
    
    def test_get_global_cache(self):
        """測試獲取全域快取實例"""
        cache = get_global_cache()
        assert isinstance(cache, EmojiImageCache)
        assert cache.max_size == 100
    
    def test_global_cache_singleton(self):
        """測試全域快取是單例"""
        cache1 = get_global_cache()
        cache2 = get_global_cache()
        assert cache1 is cache2
    
    def test_get_cache_stats_global(self):
        """測試全域快取統計"""
        # 清空快取確保乾淨狀態
        clear_cache()
        
        stats = get_cache_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["cache_size"] == 0
        assert stats["max_size"] == 100
    
    def test_clear_cache_global(self):
        """測試清空全域快取"""
        cache = get_global_cache()
        
        # 加入一些資料
        test_data = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,test"}}]
        cache.put("test_key", (test_data, False))
        
        assert len(cache.cache) > 0
        
        # 清空
        clear_cache()
        
        assert len(cache.cache) == 0
        assert cache.stats == {"hits": 0, "misses": 0}


class TestCacheIntegration:
    """測試快取整合場景"""
    
    def setup_method(self):
        """每個測試方法前的設定"""
        clear_cache()
        self.cache = get_global_cache()
    
    def test_emoji_cache_workflow(self):
        """測試 emoji 快取工作流程"""
        emoji_id = 123456789
        max_size = 256
        frame_limit = 4
        
        # 生成快取鍵值
        cache_key = generate_cache_key(emoji_id, max_size, frame_limit, "emoji")
        
        # 模擬處理結果
        processed_data = [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,processed_emoji"}}
        ]
        is_animated = False
        
        # 第一次請求 - 應該未命中
        result = self.cache.get(cache_key)
        assert result is None
        
        # 儲存處理結果
        self.cache.put(cache_key, (processed_data, is_animated))
        
        # 第二次請求 - 應該命中
        result = self.cache.get(cache_key)
        assert result == (processed_data, is_animated)
        
        # 檢查統計
        stats = self.cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == "50.0%"
    
    def test_sticker_cache_workflow(self):
        """測試 sticker 快取工作流程"""
        sticker_id = 987654321
        max_size = 128
        frame_limit = 1
        
        # 生成快取鍵值
        cache_key = generate_cache_key(sticker_id, max_size, frame_limit, "sticker")
        
        # 模擬處理結果
        processed_data = [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,processed_sticker"}}
        ]
        is_animated = True
        
        # 快取操作
        self.cache.put(cache_key, (processed_data, is_animated))
        result = self.cache.get(cache_key)
        
        assert result == (processed_data, is_animated)
    
    def test_mixed_emoji_sticker_cache(self):
        """測試混合 emoji 和 sticker 快取"""
        # 準備測試資料
        emoji_key = generate_cache_key(111111, 256, 4, "emoji")
        sticker_key = generate_cache_key(222222, 128, 1, "sticker")
        
        emoji_data = ([{"type": "image_url", "image_url": {"url": "data:image/png;base64,emoji"}}], False)
        sticker_data = ([{"type": "image_url", "image_url": {"url": "data:image/png;base64,sticker"}}], True)
        
        # 儲存兩種類型
        self.cache.put(emoji_key, emoji_data)
        self.cache.put(sticker_key, sticker_data)
        
        # 讀取驗證
        assert self.cache.get(emoji_key) == emoji_data
        assert self.cache.get(sticker_key) == sticker_data
        
        # 確保鍵值不會衝突
        assert emoji_key != sticker_key
        assert len(self.cache.cache) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])