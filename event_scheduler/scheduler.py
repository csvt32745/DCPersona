"""
通用事件排程器

負責事件的排程、持久化和觸發時的回調機制。
"""

import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Callable, Optional, List
from pathlib import Path
import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

logger = logging.getLogger(__name__)


class EventScheduler:
    """通用事件排程器"""
    
    def __init__(self, data_dir: str = "data"):
        """
        初始化事件排程器
        
        Args:
            data_dir: 資料目錄路徑
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.events_file = self.data_dir / "events.json"
        
        # 初始化 APScheduler
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': AsyncIOExecutor()
        }
        job_defaults = {
            'coalesce': False,
            'max_instances': 3
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults
        )
        
        # 註冊的回調函數
        self.callbacks: Dict[str, Callable] = {}
        
        # 事件監聽器
        self.scheduler.add_listener(self._job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._job_error, EVENT_JOB_ERROR)
        
        # 載入持久化的事件
        self._load_events()
    
    def register_callback(self, event_type: str, callback: Callable):
        """
        註冊事件類型的回調函數
        
        Args:
            event_type: 事件類型
            callback: 回調函數
        """
        self.callbacks[event_type] = callback
        logger.info(f"已註冊回調函數：{event_type}")
    
    async def schedule_event(
        self, 
        event_type: str, 
        event_details: Dict[str, Any], 
        target_time: datetime,
        event_id: Optional[str] = None
    ) -> str:
        """
        排程事件
        
        Args:
            event_type: 事件類型
            event_details: 事件詳細資料
            target_time: 目標時間
            event_id: 事件 ID（可選，如果不提供會自動生成）
            
        Returns:
            事件 ID
        """
        if event_id is None:
            event_id = str(uuid.uuid4())
        
        # 檢查是否有註冊的回調函數
        if event_type not in self.callbacks:
            logger.warning(f"事件類型 {event_type} 沒有註冊回調函數")
        
        # 添加到排程器
        job = self.scheduler.add_job(
            func=self._trigger_callback,
            trigger='date',
            run_date=target_time,
            args=[event_type, event_details, event_id],
            id=event_id,
            replace_existing=True
        )
        
        # 持久化事件
        await self._save_event(event_id, event_type, event_details, target_time)
        
        logger.info(f"已排程事件：{event_id} ({event_type}) 於 {target_time}")
        return event_id
    
    async def cancel_event(self, event_id: str) -> bool:
        """
        取消事件
        
        Args:
            event_id: 事件 ID
            
        Returns:
            是否成功取消
        """
        try:
            # 從排程器移除
            self.scheduler.remove_job(event_id)
            
            # 從持久化檔案移除
            await self._remove_event(event_id)
            
            logger.info(f"已取消事件：{event_id}")
            return True
        except Exception as e:
            logger.error(f"取消事件失敗：{event_id}, 錯誤：{e}")
            return False
    
    async def get_scheduled_events(self) -> List[Dict[str, Any]]:
        """
        取得所有已排程的事件
        
        Returns:
            事件列表
        """
        events = []
        jobs = self.scheduler.get_jobs()
        
        for job in jobs:
            events.append({
                'event_id': job.id,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'args': job.args if len(job.args) >= 2 else []
            })
        
        return events
    
    async def start(self):
        """啟動排程器"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("事件排程器已啟動")
    
    async def shutdown(self):
        """關閉排程器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("事件排程器已關閉")
    
    async def _trigger_callback(self, event_type: str, event_details: Dict[str, Any], event_id: str):
        """
        觸發回調函數
        
        Args:
            event_type: 事件類型
            event_details: 事件詳細資料
            event_id: 事件 ID
        """
        try:
            if event_type in self.callbacks:
                callback = self.callbacks[event_type]
                
                # 檢查回調函數是否為異步
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, event_details, event_id)
                else:
                    callback(event_type, event_details, event_id)
                
                logger.info(f"已觸發回調：{event_type} ({event_id})")
            else:
                logger.warning(f"沒有找到事件類型 {event_type} 的回調函數")
            
            # 事件執行完成後從持久化檔案移除
            await self._remove_event(event_id)
            
        except Exception as e:
            logger.error(f"執行回調函數時發生錯誤：{e}")
    
    def _load_events(self):
        """載入持久化的事件"""
        if not self.events_file.exists():
            return
        
        try:
            with open(self.events_file, 'r', encoding='utf-8') as f:
                events_data = json.load(f)
            
            current_time = datetime.now()
            valid_events = []
            
            for event in events_data:
                target_time = datetime.fromisoformat(event['target_time'])
                
                # 只載入未來的事件
                if target_time > current_time:
                    self.scheduler.add_job(
                        func=self._trigger_callback,
                        trigger='date',
                        run_date=target_time,
                        args=[event['event_type'], event['event_details'], event['event_id']],
                        id=event['event_id'],
                        replace_existing=True
                    )
                    valid_events.append(event)
                    logger.info(f"已載入事件：{event['event_id']} ({event['event_type']})")
            
            # 更新檔案，移除過期事件
            if len(valid_events) != len(events_data):
                with open(self.events_file, 'w', encoding='utf-8') as f:
                    json.dump(valid_events, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"載入事件時發生錯誤：{e}")
    
    async def _save_event(self, event_id: str, event_type: str, event_details: Dict[str, Any], target_time: datetime):
        """
        保存事件到持久化檔案
        
        Args:
            event_id: 事件 ID
            event_type: 事件類型
            event_details: 事件詳細資料
            target_time: 目標時間
        """
        try:
            # 讀取現有事件
            events_data = []
            if self.events_file.exists():
                with open(self.events_file, 'r', encoding='utf-8') as f:
                    events_data = json.load(f)
            
            # 添加新事件
            new_event = {
                'event_id': event_id,
                'event_type': event_type,
                'event_details': event_details,
                'target_time': target_time.isoformat(),
                'created_at': datetime.now().isoformat()
            }
            
            # 移除相同 ID 的舊事件（如果存在）
            events_data = [e for e in events_data if e['event_id'] != event_id]
            events_data.append(new_event)
            
            # 寫入檔案
            with open(self.events_file, 'w', encoding='utf-8') as f:
                json.dump(events_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存事件時發生錯誤：{e}")
    
    async def _remove_event(self, event_id: str):
        """
        從持久化檔案移除事件
        
        Args:
            event_id: 事件 ID
        """
        try:
            if not self.events_file.exists():
                return
            
            with open(self.events_file, 'r', encoding='utf-8') as f:
                events_data = json.load(f)
            
            # 移除指定事件
            events_data = [e for e in events_data if e['event_id'] != event_id]
            
            # 寫回檔案
            with open(self.events_file, 'w', encoding='utf-8') as f:
                json.dump(events_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"移除事件時發生錯誤：{e}")
    
    def _job_executed(self, event):
        """工作執行完成事件監聽器"""
        logger.debug(f"工作執行完成：{event.job_id}")
    
    def _job_error(self, event):
        """工作執行錯誤事件監聽器"""
        logger.error(f"工作執行錯誤：{event.job_id}, 錯誤：{event.exception}") 