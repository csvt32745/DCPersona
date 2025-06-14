"""
進度更新混入類別

提供進度通知功能，讓 Agent 類別可以通知註冊的觀察者
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from .progress_observer import ProgressObserver, ProgressEvent


class ProgressMixin:
    """進度更新 Mixin
    
    提供進度觀察者管理和通知功能，讓 Agent 類別可以繼承此功能
    """
    
    def __init__(self):
        """初始化進度混入"""
        self._progress_observers: List[ProgressObserver] = []
        # 確保有 logger 屬性
        if not hasattr(self, 'logger'):
            self.logger = logging.getLogger(self.__class__.__name__)
    
    def add_progress_observer(self, observer: ProgressObserver):
        """添加進度觀察者
        
        Args:
            observer: 進度觀察者實例
        """
        if observer not in self._progress_observers:
            self._progress_observers.append(observer)
    
    def remove_progress_observer(self, observer: ProgressObserver):
        """移除進度觀察者
        
        Args:
            observer: 要移除的進度觀察者實例
        """
        if observer in self._progress_observers:
            self._progress_observers.remove(observer)
    
    def clear_progress_observers(self):
        """清除所有進度觀察者"""
        self._progress_observers.clear()
    
    async def _notify_progress(self, stage: str, message: str, 
                              progress_percentage: Optional[int] = None,
                              eta_seconds: Optional[int] = None,
                              **metadata):
        """通知所有觀察者進度更新
        
        Args:
            stage: 進度階段
            message: 進度訊息
            progress_percentage: 進度百分比 (0-100)
            eta_seconds: 預估剩餘時間（秒）
            **metadata: 額外的元數據
        """
        if not self._progress_observers:
            return
        
        event = ProgressEvent(
            stage=stage,
            message=message,
            progress_percentage=progress_percentage,
            eta_seconds=eta_seconds,
            metadata=metadata
        )
        
        # 並行通知所有觀察者
        tasks = []
        for observer in self._progress_observers:
            task = self._safe_notify_observer(observer.on_progress_update, event)
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _notify_completion(self, final_result: str, sources: Optional[List[Dict]] = None):
        """通知完成事件
        
        Args:
            final_result: 最終結果
            sources: 研究來源清單
        """
        if not self._progress_observers:
            return
        
        # 並行通知所有觀察者
        tasks = []
        for observer in self._progress_observers:
            task = self._safe_notify_observer(observer.on_completion, final_result, sources)
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _notify_error(self, error: Exception):
        """通知錯誤事件
        
        Args:
            error: 發生的異常
        """
        if not self._progress_observers:
            return
        
        # 並行通知所有觀察者
        tasks = []
        for observer in self._progress_observers:
            task = self._safe_notify_observer(observer.on_error, error)
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _notify_streaming_chunk(self, content: str, is_final: bool = False, **metadata):
        """通知串流塊 (直接傳遞內容和is_final)
        
        Args:
            content: 串流內容
            is_final: 是否為最終塊
            **metadata: 額外的元數據（目前未使用，保留以備將來擴展）
        """
        if not self._progress_observers:
            return
        
        # 並行通知所有觀察者
        tasks = []
        for observer in self._progress_observers:
            task = self._safe_notify_observer(observer.on_streaming_chunk, content, is_final)
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _notify_streaming_complete(self):
        """通知串流完成"""
        if not self._progress_observers:
            return
        
        # 並行通知所有觀察者
        tasks = []
        for observer in self._progress_observers:
            task = self._safe_notify_observer(observer.on_streaming_complete)
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _safe_notify_observer(self, method, *args, **kwargs):
        """安全地通知觀察者，避免單一觀察者的錯誤影響其他觀察者
        
        Args:
            method: 要調用的觀察者方法
            *args: 位置參數
            **kwargs: 關鍵字參數
        """
        try:
            await method(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"進度觀察者通知失敗: {e}", exc_info=True)
    
    def _sync_notify_progress(self, stage: str, message: str, 
                             progress_percentage: Optional[int] = None,
                             eta_seconds: Optional[int] = None,
                             **metadata):
        """同步版本的進度通知（在無法使用 async 的情況下）
        
        Args:
            stage: 進度階段
            message: 進度訊息
            progress_percentage: 進度百分比 (0-100)
            eta_seconds: 預估剩餘時間（秒）
            **metadata: 額外的元數據
        """
        if not self._progress_observers:
            return
        
        try:
            # 嘗試獲取當前事件循環
            try:
                loop = asyncio.get_running_loop()
                # 如果有正在運行的事件循環，創建任務
                loop.create_task(self._notify_progress(
                    stage, message, progress_percentage, eta_seconds, **metadata
                ))
                return
            except RuntimeError:
                # 沒有正在運行的事件循環，嘗試其他方法
                pass
            
            # 嘗試獲取事件循環（即使沒有運行）
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    # 事件循環存在但沒有運行，直接運行
                    loop.run_until_complete(self._notify_progress(
                        stage, message, progress_percentage, eta_seconds, **metadata
                    ))
                    return
            except RuntimeError:
                # 沒有事件循環，嘗試創建一個新的
                pass
            
            # 最後的嘗試：創建新的事件循環
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    new_loop.run_until_complete(self._notify_progress(
                        stage, message, progress_percentage, eta_seconds, **metadata
                    ))
                finally:
                    new_loop.close()
                    # 清理事件循環設置
                    try:
                        asyncio.set_event_loop(None)
                    except RuntimeError:
                        pass
                return
            except Exception as e:
                # 如果所有嘗試都失敗，記錄詳細警告但不拋出異常
                self.logger.warning(
                    f"無法發送進度更新 (所有方法都失敗): {stage} - {message} - {e}"
                )
                return
                
        except Exception as e:
            # 捕獲任何其他異常，避免中斷主要流程
            self.logger.warning(f"進度通知過程中發生意外錯誤: {stage} - {message} - {e}") 