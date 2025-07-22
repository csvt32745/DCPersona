"""
記憶體監控測試模組

測試 DCPersona 各個元件的記憶體使用情況，識別潛在的記憶體洩漏問題
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import psutil
import gc
import asyncio
import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from unittest.mock import MagicMock, AsyncMock

# 測試元件導入
from discord_bot.progress_manager import ProgressManager, get_progress_manager
from utils.input_emoji_cache import EmojiImageCache, get_global_cache, clear_cache
from agent_core.graph import UnifiedAgent, create_unified_agent
from utils.config_loader import load_typed_config


@dataclass
class MemorySnapshot:
    """記憶體快照資料結構"""
    timestamp: float
    rss_mb: float  # 實體記憶體使用 (MB)
    vms_mb: float  # 虛擬記憶體使用 (MB)
    percent: float  # 記憶體使用百分比
    objects_count: int  # Python 物件數量
    context: str  # 測試情境描述


class MemoryMonitor:
    """記憶體監控工具"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.snapshots: List[MemorySnapshot] = []
        self.logger = logging.getLogger(__name__)
    
    def take_snapshot(self, context: str = "") -> MemorySnapshot:
        """拍攝記憶體快照"""
        memory_info = self.process.memory_info()
        memory_percent = self.process.memory_percent()
        objects_count = len(gc.get_objects())
        
        snapshot = MemorySnapshot(
            timestamp=time.time(),
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            percent=memory_percent,
            objects_count=objects_count,
            context=context
        )
        
        self.snapshots.append(snapshot)
        self.logger.info(f"記憶體快照 [{context}]: RSS={snapshot.rss_mb:.2f}MB, 物件數={snapshot.objects_count}")
        return snapshot
    
    def get_memory_growth(self, start_index: int = 0) -> Dict[str, float]:
        """計算記憶體增長量"""
        if len(self.snapshots) < 2:
            return {"rss_growth": 0.0, "objects_growth": 0}
        
        start_snapshot = self.snapshots[start_index]
        end_snapshot = self.snapshots[-1]
        
        return {
            "rss_growth": end_snapshot.rss_mb - start_snapshot.rss_mb,
            "objects_growth": end_snapshot.objects_count - start_snapshot.objects_count,
            "time_elapsed": end_snapshot.timestamp - start_snapshot.timestamp
        }
    
    def clear_snapshots(self):
        """清空快照記錄"""
        self.snapshots.clear()


class TestMemoryMonitoring:
    """記憶體監控測試類別"""
    
    def setup_method(self):
        """測試前設置"""
        self.monitor = MemoryMonitor()
        # 強制垃圾回收
        gc.collect()
        self.monitor.take_snapshot("test_start")
    
    def teardown_method(self):
        """測試後清理"""
        gc.collect()
        self.monitor.take_snapshot("test_end")
        
        # 輸出記憶體變化報告
        growth = self.monitor.get_memory_growth()
        if growth["rss_growth"] > 10:  # 超過 10MB 增長則警告
            logging.warning(f"測試後記憶體增長: {growth['rss_growth']:.2f}MB")
    
    def test_progress_manager_memory_accumulation(self):
        """測試進度管理器記憶體累積問題"""
        self.monitor.take_snapshot("progress_manager_start")
        
        # 獲取進度管理器實例
        progress_manager = get_progress_manager()
        
        # 模擬大量訊息處理
        mock_messages = []
        for i in range(1000):
            # 創建模擬 Discord 訊息
            mock_msg = MagicMock()
            mock_msg.id = i
            mock_msg.channel.id = 12345
            mock_messages.append(mock_msg)
            
            # 模擬進度訊息記錄
            progress_manager._progress_messages[i] = mock_msg
            progress_manager._message_to_progress[i] = mock_msg
            progress_manager._message_timestamps[i] = time.time()
        
        self.monitor.take_snapshot("progress_manager_after_accumulation")
        
        # 檢查記憶體增長
        growth = self.monitor.get_memory_growth(1)  # 從 progress_manager_start 開始
        
        assert len(progress_manager._progress_messages) == 1000
        assert len(progress_manager._message_to_progress) == 1000
        assert len(progress_manager._message_timestamps) == 1000
        
        logging.info(f"進度管理器累積1000項記錄後記憶體增長: {growth['rss_growth']:.2f}MB")
        
        # 測試清理功能
        for i in range(1000):
            progress_manager.cleanup_by_message_id(i)
        
        self.monitor.take_snapshot("progress_manager_after_cleanup")
        
        assert len(progress_manager._progress_messages) == 0
        assert len(progress_manager._message_to_progress) == 0
        assert len(progress_manager._message_timestamps) == 0
    
    def test_emoji_cache_memory_limits(self):
        """測試 Emoji 快取記憶體限制"""
        self.monitor.take_snapshot("emoji_cache_start")
        
        # 清空快取開始測試
        clear_cache()
        emoji_cache = get_global_cache()
        
        # 模擬大量 emoji 快取項目
        test_data = []
        for i in range(200):  # 超過預設限制 100
            cache_key = f"emoji_{i}_256_4"
            mock_image_data = [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,test{i}"}}]
            test_data.append((cache_key, (mock_image_data, False)))
            emoji_cache.put(cache_key, (mock_image_data, False))
        
        self.monitor.take_snapshot("emoji_cache_after_200_items")
        
        # 檢查快取大小限制
        stats = emoji_cache.get_stats()
        assert stats["cache_size"] == 100  # 應該被限制在 100
        assert stats["max_size"] == 100
        
        # 檢查記憶體使用
        growth = self.monitor.get_memory_growth(1)
        logging.info(f"Emoji 快取200項後記憶體增長: {growth['rss_growth']:.2f}MB")
        
        # 清空快取
        emoji_cache.clear()
        self.monitor.take_snapshot("emoji_cache_after_clear")
    
    def test_agent_instance_creation_memory(self):
        """測試 Agent 實例創建的記憶體影響"""
        self.monitor.take_snapshot("agent_creation_start")
        
        config = load_typed_config()
        agents = []
        
        # 創建多個 Agent 實例模擬重複處理
        for i in range(10):
            try:
                agent = create_unified_agent(config)
                agents.append(agent)
                
                if i % 3 == 0:  # 每 3 個拍一次快照
                    self.monitor.take_snapshot(f"agent_creation_after_{i+1}")
            except Exception as e:
                # API key 可能未設置，跳過實際 LLM 初始化
                logging.warning(f"Agent 創建失敗 (可能是 API key 未設置): {e}")
                break
        
        # 檢查記憶體增長
        if len(self.monitor.snapshots) > 2:
            growth = self.monitor.get_memory_growth(1)
            logging.info(f"創建 {len(agents)} 個 Agent 實例後記憶體增長: {growth['rss_growth']:.2f}MB")
        
        # 清理 agents
        agents.clear()
        gc.collect()
        self.monitor.take_snapshot("agent_creation_after_cleanup")
    
    async def test_async_memory_monitoring(self):
        """異步記憶體監控測試"""
        self.monitor.take_snapshot("async_test_start")
        
        # 模擬異步工作負載
        tasks = []
        for i in range(50):
            task = asyncio.create_task(self._simulate_async_work(i))
            tasks.append(task)
        
        # 等待所有任務完成
        await asyncio.gather(*tasks, return_exceptions=True)
        
        self.monitor.take_snapshot("async_test_complete")
        
        growth = self.monitor.get_memory_growth(1)
        logging.info(f"異步任務完成後記憶體增長: {growth['rss_growth']:.2f}MB")
    
    async def _simulate_async_work(self, task_id: int):
        """模擬異步工作"""
        # 模擬一些記憶體分配和釋放
        data = [f"task_{task_id}_data_{i}" for i in range(100)]
        await asyncio.sleep(0.01)  # 模擬 I/O 等待
        return len(data)
    
    def test_memory_growth_threshold(self):
        """測試記憶體增長閾值"""
        initial_snapshot = self.monitor.snapshots[0]  # test_start 快照
        
        # 執行一些記憶體密集操作
        large_data = []
        for i in range(1000):
            large_data.append("x" * 1000)  # 每個字串 1KB
        
        self.monitor.take_snapshot("after_large_allocation")
        
        # 釋放記憶體
        large_data.clear()
        gc.collect()
        
        self.monitor.take_snapshot("after_cleanup")
        
        # 檢查是否有記憶體洩漏
        final_growth = self.monitor.get_memory_growth()
        
        # 設置警告閾值：記憶體增長超過 5MB
        if final_growth["rss_growth"] > 5.0:
            logging.warning(f"記憶體增長超過閾值: {final_growth['rss_growth']:.2f}MB")
        
        # 記錄詳細快照資訊
        for i, snapshot in enumerate(self.monitor.snapshots):
            logging.info(f"快照 {i}: {snapshot.context} - RSS={snapshot.rss_mb:.2f}MB, 物件數={snapshot.objects_count}")


def run_memory_tests():
    """執行記憶體測試的便利函數"""
    logging.basicConfig(level=logging.INFO)
    test_instance = TestMemoryMonitoring()
    
    print("=== DCPersona 記憶體監控測試 ===")
    
    # 執行各項測試
    tests = [
        ("進度管理器記憶體累積測試", test_instance.test_progress_manager_memory_accumulation),
        ("Emoji 快取記憶體限制測試", test_instance.test_emoji_cache_memory_limits),
        ("Agent 實例創建記憶體測試", test_instance.test_agent_instance_creation_memory),
        ("記憶體增長閾值測試", test_instance.test_memory_growth_threshold),
    ]
    
    for test_name, test_method in tests:
        print(f"\n執行: {test_name}")
        test_instance.setup_method()
        try:
            test_method()
            print(f"[PASS] {test_name} 完成")
        except Exception as e:
            print(f"[FAIL] {test_name} 失敗: {e}")
        finally:
            test_instance.teardown_method()
    
    # 執行異步測試
    print(f"\n執行: 異步記憶體監控測試")
    test_instance.setup_method()
    try:
        asyncio.run(test_instance.test_async_memory_monitoring())
        print(f"[PASS] 異步記憶體監控測試 完成")
    except Exception as e:
        print(f"[FAIL] 異步記憶體監控測試 失敗: {e}")
    finally:
        test_instance.teardown_method()
    
    print("\n=== 記憶體監控測試完成 ===")


if __name__ == "__main__":
    run_memory_tests()