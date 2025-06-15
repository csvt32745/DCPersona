"""
測試 event_scheduler 模組
"""

import pytest
import asyncio
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from event_scheduler import EventScheduler


class TestEventScheduler:
    """測試 EventScheduler 類別"""
    
    @pytest.fixture
    async def temp_scheduler(self):
        """創建臨時的 EventScheduler 實例"""
        temp_dir = tempfile.mkdtemp()
        scheduler = EventScheduler(data_dir=temp_dir)
        await scheduler.start()
        
        yield scheduler
        
        await scheduler.shutdown()
        shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_scheduler_initialization(self, temp_scheduler):
        """測試排程器初始化"""
        scheduler = temp_scheduler
        
        assert scheduler.scheduler.running
        assert scheduler.data_dir.exists()
        assert scheduler.events_file.parent.exists()
    
    @pytest.mark.asyncio
    async def test_register_callback(self, temp_scheduler):
        """測試註冊回調函數"""
        scheduler = temp_scheduler
        
        async def test_callback(event_type, event_details, event_id):
            pass
        
        scheduler.register_callback("test_event", test_callback)
        
        assert "test_event" in scheduler.callbacks
        assert scheduler.callbacks["test_event"] == test_callback
    
    @pytest.mark.asyncio
    async def test_schedule_event(self, temp_scheduler):
        """測試排程事件"""
        scheduler = temp_scheduler
        
        # 設定測試資料
        event_type = "test_reminder"
        event_details = {"message": "測試提醒", "user_id": "123"}
        target_time = datetime.now() + timedelta(seconds=1)
        
        # 排程事件
        event_id = await scheduler.schedule_event(event_type, event_details, target_time)
        
        assert event_id is not None
        assert len(event_id) > 0
        
        # 檢查事件是否被添加到排程器
        jobs = scheduler.scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == event_id
    
    @pytest.mark.asyncio
    async def test_schedule_event_with_custom_id(self, temp_scheduler):
        """測試使用自定義 ID 排程事件"""
        scheduler = temp_scheduler
        
        custom_id = "custom_event_123"
        event_type = "test_reminder"
        event_details = {"message": "測試提醒"}
        target_time = datetime.now() + timedelta(seconds=1)
        
        event_id = await scheduler.schedule_event(
            event_type, event_details, target_time, event_id=custom_id
        )
        
        assert event_id == custom_id
        
        jobs = scheduler.scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == custom_id
    
    @pytest.mark.asyncio
    async def test_cancel_event(self, temp_scheduler):
        """測試取消事件"""
        scheduler = temp_scheduler
        
        # 先排程一個事件
        event_type = "test_reminder"
        event_details = {"message": "測試提醒"}
        target_time = datetime.now() + timedelta(hours=1)
        
        event_id = await scheduler.schedule_event(event_type, event_details, target_time)
        
        # 確認事件已排程
        jobs = scheduler.scheduler.get_jobs()
        assert len(jobs) == 1
        
        # 取消事件
        success = await scheduler.cancel_event(event_id)
        
        assert success is True
        
        # 確認事件已被移除
        jobs = scheduler.scheduler.get_jobs()
        assert len(jobs) == 0
    
    @pytest.mark.asyncio
    async def test_get_scheduled_events(self, temp_scheduler):
        """測試取得已排程事件"""
        scheduler = temp_scheduler
        
        # 排程多個事件
        event1_id = await scheduler.schedule_event(
            "reminder", {"msg": "事件1"}, datetime.now() + timedelta(hours=1)
        )
        event2_id = await scheduler.schedule_event(
            "reminder", {"msg": "事件2"}, datetime.now() + timedelta(hours=2)
        )
        
        events = await scheduler.get_scheduled_events()
        
        assert len(events) == 2
        event_ids = [e['event_id'] for e in events]
        assert event1_id in event_ids
        assert event2_id in event_ids
    
    @pytest.mark.asyncio
    async def test_event_persistence(self, temp_scheduler):
        """測試事件持久化"""
        scheduler = temp_scheduler
        
        # 排程事件
        event_type = "test_reminder"
        event_details = {"message": "持久化測試"}
        target_time = datetime.now() + timedelta(hours=1)
        
        event_id = await scheduler.schedule_event(event_type, event_details, target_time)
        
        # 檢查檔案是否存在且包含事件資料
        assert scheduler.events_file.exists()
        
        with open(scheduler.events_file, 'r', encoding='utf-8') as f:
            events_data = json.load(f)
        
        assert len(events_data) == 1
        assert events_data[0]['event_id'] == event_id
        assert events_data[0]['event_type'] == event_type
        assert events_data[0]['event_details'] == event_details
    
    @pytest.mark.asyncio
    async def test_callback_execution(self, temp_scheduler):
        """測試回調函數執行"""
        scheduler = temp_scheduler
        
        # 創建模擬回調函數
        callback_executed = asyncio.Event()
        received_data = {}
        
        async def test_callback(event_type, event_details, event_id):
            received_data['event_type'] = event_type
            received_data['event_details'] = event_details
            received_data['event_id'] = event_id
            callback_executed.set()
        
        # 註冊回調函數
        scheduler.register_callback("test_reminder", test_callback)
        
        # 排程一個很快就會觸發的事件
        event_type = "test_reminder"
        event_details = {"message": "回調測試"}
        target_time = datetime.now() + timedelta(milliseconds=100)
        
        event_id = await scheduler.schedule_event(event_type, event_details, target_time)
        
        # 等待回調函數執行
        await asyncio.wait_for(callback_executed.wait(), timeout=2.0)
        
        # 驗證回調函數接收到正確的資料
        assert received_data['event_type'] == event_type
        assert received_data['event_details'] == event_details
        assert received_data['event_id'] == event_id
    
    @pytest.mark.asyncio
    async def test_load_events_on_startup(self):
        """測試啟動時載入事件"""
        temp_dir = tempfile.mkdtemp()
        
        try:
            # 手動創建事件檔案
            events_file = Path(temp_dir) / "events.json"
            future_time = datetime.now() + timedelta(hours=1)
            past_time = datetime.now() - timedelta(hours=1)
            
            events_data = [
                {
                    'event_id': 'future_event',
                    'event_type': 'reminder',
                    'event_details': {'message': '未來事件'},
                    'target_time': future_time.isoformat(),
                    'created_at': datetime.now().isoformat()
                },
                {
                    'event_id': 'past_event',
                    'event_type': 'reminder',
                    'event_details': {'message': '過去事件'},
                    'target_time': past_time.isoformat(),
                    'created_at': datetime.now().isoformat()
                }
            ]
            
            with open(events_file, 'w', encoding='utf-8') as f:
                json.dump(events_data, f, ensure_ascii=False, indent=2)
            
            # 創建新的排程器實例
            scheduler = EventScheduler(data_dir=temp_dir)
            await scheduler.start()
            
            # 檢查只有未來的事件被載入
            jobs = scheduler.scheduler.get_jobs()
            assert len(jobs) == 1
            assert jobs[0].id == 'future_event'
            
            # 檢查過期事件已從檔案中移除
            with open(events_file, 'r', encoding='utf-8') as f:
                updated_events = json.load(f)
            
            assert len(updated_events) == 1
            assert updated_events[0]['event_id'] == 'future_event'
            
            await scheduler.shutdown()
            
        finally:
            shutil.rmtree(temp_dir)
    
    @pytest.mark.asyncio
    async def test_sync_callback_execution(self, temp_scheduler):
        """測試同步回調函數執行"""
        scheduler = temp_scheduler
        
        # 創建同步回調函數
        callback_executed = asyncio.Event()
        received_data = {}
        
        def sync_callback(event_type, event_details, event_id):
            received_data['event_type'] = event_type
            received_data['event_details'] = event_details
            received_data['event_id'] = event_id
            # 在同步函數中設置異步事件需要特殊處理
            asyncio.create_task(set_event())
        
        async def set_event():
            callback_executed.set()
        
        # 註冊同步回調函數
        scheduler.register_callback("sync_test", sync_callback)
        
        # 排程事件
        event_type = "sync_test"
        event_details = {"message": "同步回調測試"}
        target_time = datetime.now() + timedelta(milliseconds=100)
        
        event_id = await scheduler.schedule_event(event_type, event_details, target_time)
        
        # 等待回調函數執行
        await asyncio.wait_for(callback_executed.wait(), timeout=2.0)
        
        # 驗證回調函數接收到正確的資料
        assert received_data['event_type'] == event_type
        assert received_data['event_details'] == event_details
        assert received_data['event_id'] == event_id


if __name__ == "__main__":
    pytest.main([__file__]) 