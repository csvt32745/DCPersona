"""
進度更新混入類別

提供進度通知功能，讓 Agent 類別可以通知註冊的觀察者
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from .progress_observer import ProgressObserver, ProgressEvent
from .progress_types import ProgressStage

# TYPE_CHECKING 引入已移除，因為不再需要 ProgressMessageFactory


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
    
    # 已移除 set_progress_message_factory 方法，因為不再需要 ProgressMessageFactory
    
    async def _notify_progress(self, stage, message: str = "", 
                              progress_percentage: Optional[int] = None,
                              eta_seconds: Optional[int] = None,
                              auto_msg: Optional[bool] = None,
                              current_state: Optional = None,
                              **metadata):
        """通知所有觀察者進度更新
        
        Args:
            stage: 進度階段
            message: 進度訊息，如果為空且 auto_msg 為 True，則自動產生
            progress_percentage: 進度百分比 (0-100)
            eta_seconds: 預估剩餘時間（秒）
            auto_msg: 是否自動產生訊息，None 則根據配置決定
            current_state: 當前狀態（用於自動產生訊息）
            **metadata: 額外的元數據
        """
        if not self._progress_observers:
            return
        
        # 決定是否需要自動產生訊息  
        stage_str = stage.value if hasattr(stage, 'value') else stage
        should_auto_generate = self._should_auto_generate_message(stage_str, message, auto_msg)
        
        # 如果需要自動產生訊息
        if should_auto_generate:
            message = await self._generate_progress_message(stage_str, current_state)
        
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
    
    def _sync_notify_progress(self, stage, message: str = "", 
                             progress_percentage: Optional[int] = None,
                             eta_seconds: Optional[int] = None,
                             auto_msg: Optional[bool] = None,
                             current_state: Optional = None,
                             **metadata):
        """同步版本的進度通知（在無法使用 async 的情況下）
        
        Args:
            stage: 進度階段
            message: 進度訊息，如果為空且 auto_msg 為 True，則自動產生
            progress_percentage: 進度百分比 (0-100)
            eta_seconds: 預估剩餘時間（秒）
            auto_msg: 是否自動產生訊息，None 則根據配置決定
            current_state: 當前狀態（用於自動產生訊息）
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
                    stage, message, progress_percentage, eta_seconds, auto_msg, current_state, **metadata
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
                        stage, message, progress_percentage, eta_seconds, auto_msg, current_state, **metadata
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
                        stage, message, progress_percentage, eta_seconds, auto_msg, current_state, **metadata
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
    
    def _should_auto_generate_message(self, stage: str, message: str, auto_msg: Optional[bool]) -> bool:
        """判斷是否需要自動產生訊息
        
        Args:
            stage: 進度階段
            message: 當前訊息
            auto_msg: 明確的自動產生標誌
            
        Returns:
            bool: 是否需要自動產生訊息
        """
        # 如果已經有訊息，不需要自動產生
        if message:
            return False
        
        # 檢查是否有 progress LLM 或配置支援自動產生
        has_progress_llm = hasattr(self, '_progress_llm') and self._progress_llm
        has_config_support = hasattr(self, 'config') and hasattr(self.config, 'progress')
        
        if not has_progress_llm and not has_config_support:
            return False
        
        # 如果明確設置了 auto_msg，使用該設置
        if auto_msg is not None:
            return auto_msg
        
        # 高頻事件（如 TOOL_STATUS、STREAMING）不自動產生，維持既有模板
        high_frequency_stages = {
            ProgressStage.TOOL_STATUS.value,
            ProgressStage.STREAMING.value,
        }
        if stage in high_frequency_stages:
            return False
        
        # 從配置中獲取是否啟用自動產生
        config = getattr(self, 'config', None)
        if config and hasattr(config, 'progress'):
            return config.progress.discord.auto_generate_messages
        
        return False
    
    async def _generate_progress_message(self, stage: str, current_state) -> str:
        """基礎方法：處理 progress 相關資訊
        
        Args:
            stage: 進度階段
            current_state: 當前狀態
            
        Returns:
            str: 產生的進度訊息
        """
        if not current_state:
            return ""
            
        try:
            # 1. 獲取 Agent 準備好的 messages
            agent_messages = await self._build_agent_messages_for_progress(stage, current_state)
            
            # 2. 加入 progress 指令（ProgressMixin 的責任）
            messages = self._add_progress_instruction(agent_messages, stage)
            
            # 3. 調用 LLM 生成
            return await self._generate_with_llm(messages, stage)
            
        except Exception as e:
            self.logger.error(f"自動產生進度訊息失敗: {e}")
            # 返回備用訊息
            return f"🔄 {stage}..."
    
    async def _build_agent_messages_for_progress(self, stage: str, current_state) -> List[BaseMessage]:
        """讓 Agent 構建 messages（子類重寫）
        
        Args:
            stage: 進度階段
            current_state: 當前狀態
            
        Returns:
            List[BaseMessage]: Agent 構建的 messages
        """
        return []
    
    def _add_progress_instruction(self, messages: List[BaseMessage], stage: str) -> List[BaseMessage]:
        """加入 progress 指令
        
        Args:
            messages: Agent 構建的 messages
            stage: 進度階段
            
        Returns:
            List[BaseMessage]: 加入指令後的 messages
        """
        if not messages:
            return messages
            
        template_message = self.config.progress.discord.messages.get(stage, "") if hasattr(self, 'config') else ""
        
        progress_instruction = f'''
你現在需要為進度階段 "{stage}:" 生成簡短的進度訊息。

參考: {template_message}

要求:
- 嚴格限制在16字左右
- 保持簡潔
- 根據你的人格和當前對話發揮創意
- 內容主軸要圍繞在當前進度
- 使用適當的 emoji
'''
        
        # 在現有 SystemMessage 基礎上 chain
        new_messages = messages.copy()
        if len(new_messages) > 0 and hasattr(new_messages[0], 'content'):
            original_system = new_messages[0].content
            new_messages[0] = SystemMessage(content=f"{original_system}\n\n{progress_instruction}")
        
        # 添加生成指令
        new_messages.append(HumanMessage(content=f"請為 {stage} 階段生成約16字的個性進度訊息: {template_message}"))
        
        return new_messages
    
    async def _generate_with_llm(self, messages: List[BaseMessage], stage: str) -> str:
        """純粹的 LLM 調用
        
        Args:
            messages: 要發送給 LLM 的訊息
            stage: 進度階段
            
        Returns:
            str: 生成的進度訊息
        """
        if not hasattr(self, '_progress_llm') or not self._progress_llm:
            config = getattr(self, 'config', None)
            if config and hasattr(config, 'progress'):
                return config.progress.discord.messages.get(stage, "🔄 處理中...")
            return "🔄 處理中..."
        
        try:
            response = await self._progress_llm.ainvoke(messages)
            content = response.content.strip()
            
            # 長度控制
            if len(content) > 64:
                content = content[:64] + "..."
            
            return content
            
        except Exception as e:
            self.logger.error(f"進度訊息生成失敗: {e}")
            config = getattr(self, 'config', None)
            if config and hasattr(config, 'progress'):
                return config.progress.discord.messages.get(stage, "🔄 處理中...")
            return "🔄 處理中..."
    
    def _collect_context_for_progress(self, stage: ProgressStage, **metadata) -> dict:
        """收集進度訊息生成所需的上下文
        
        Args:
            stage: 進度階段
            **metadata: 額外的元數據
            
        Returns:
            dict: 包含上下文信息的字典
        """
        context = metadata.copy()
        
        # 嘗試獲取當前的對話歷史（如果有的話）
        if hasattr(self, '_current_messages') and self._current_messages:
            context['conversation_history'] = self._extract_conversation_context(self._current_messages)
        
        # 獲取原本的模板訊息作為參考
        template_message = self._get_template_message(stage)
        if template_message:
            context['template_message'] = template_message
        
        return context
    
    def _extract_conversation_context(self, messages) -> str:
        """從對話歷史中提取上下文摘要
        
        Args:
            messages: 對話訊息列表
            
        Returns:
            str: 上下文摘要
        """
        try:
            # 如果 messages 是 list，嘗試提取最近的用戶訊息
            if isinstance(messages, list) and messages:
                # 尋找最近的用戶訊息
                for msg in reversed(messages):
                    if hasattr(msg, 'content') and msg.content:
                        # 限制長度避免過長
                        content = str(msg.content)
                        if len(content) > 100:
                            content = content[:100] + "..."
                        return content
            
            # 如果是字符串，直接返回
            if isinstance(messages, str):
                return messages[:100] + "..." if len(messages) > 100 else messages
                
            return ""
            
        except Exception as e:
            self.logger.debug(f"提取對話上下文失敗: {e}")
            return ""
    
    def _get_template_message(self, stage: ProgressStage) -> str:
        """獲取階段的模板訊息
        
        Args:
            stage: 進度階段
            
        Returns:
            str: 模板訊息
        """
        try:
            # 從配置中獲取模板訊息
            config = getattr(self, 'config', None)
            if config and hasattr(config, 'progress'):
                template_messages = config.progress.discord.messages
                return template_messages.get(stage.value, "")
            
            # 如果沒有配置，返回預設模板
            from schemas.config_types import _default_progress_messages
            default_messages = _default_progress_messages()
            return default_messages.get(stage.value, "")
            
        except Exception as e:
            self.logger.debug(f"獲取模板訊息失敗: {e}")
            return "" 