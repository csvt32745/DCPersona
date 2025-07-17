"""
進度混入整合測試
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from agent_core.progress_mixin import ProgressMixin
from agent_core.progress_types import ProgressStage
from schemas.config_types import AppConfig, ProgressConfig, ProgressDiscordConfig
from schemas.agent_types import OverallState


class TestProgressMixinIntegration:
    """ProgressMixin 整合測試類別"""
    
    def setup_method(self):
        """設置測試環境"""
        # 創建測試用的配置
        self.config = AppConfig()
        self.config.progress = ProgressConfig()
        self.config.progress.discord = ProgressDiscordConfig()
        
        # 創建測試用的 ProgressMixin 實例
        self.progress_mixin = ProgressMixin()
        self.progress_mixin.config = self.config
        
        # 創建 mock 觀察者
        self.observer = AsyncMock()
        self.progress_mixin.add_progress_observer(self.observer)
    
    @pytest.mark.asyncio
    async def test_notify_progress_with_message(self):
        """測試有訊息時的進度通知"""
        # 測試提供明確訊息
        await self.progress_mixin._notify_progress(
            stage=ProgressStage.SEARCHING,
            message="正在搜尋資料...",
            progress_percentage=50
        )
        
        # 驗證觀察者被調用
        self.observer.on_progress_update.assert_called_once()
        
        # 驗證事件內容
        event = self.observer.on_progress_update.call_args[0][0]
        assert event.stage == ProgressStage.SEARCHING
        assert event.message == "正在搜尋資料..."
        assert event.progress_percentage == 50
    
    @pytest.mark.asyncio
    async def test_notify_progress_auto_generate_disabled(self):
        """測試自動產生功能關閉時的行為"""
        # 設置配置為關閉自動產生
        self.config.progress.discord.auto_generate_messages = False
        
        # 測試空訊息
        await self.progress_mixin._notify_progress(
            stage=ProgressStage.SEARCHING,
            message="",
            progress_percentage=50
        )
        
        # 驗證觀察者被調用但訊息為空
        self.observer.on_progress_update.assert_called_once()
        event = self.observer.on_progress_update.call_args[0][0]
        assert event.message == ""
    
    @pytest.mark.asyncio
    async def test_notify_progress_auto_generate_enabled(self):
        """測試自動產生功能開啟時的行為"""
        # 設置配置為開啟自動產生
        self.config.progress.discord.auto_generate_messages = True
        
        # 創建 mock progress LLM
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "🔍 正在搜尋..."
        mock_llm.ainvoke.return_value = mock_response
        self.progress_mixin._progress_llm = mock_llm
        
        # 創建測試狀態
        test_state = OverallState()
        test_state.current_persona = "default"
        
        # 測試空訊息 - 需要重寫 _build_agent_messages_for_progress 方法
        async def mock_build_agent_messages(stage, current_state):
            return []
        
        self.progress_mixin._build_agent_messages_for_progress = mock_build_agent_messages
        
        # 測試空訊息
        await self.progress_mixin._notify_progress(
            stage=ProgressStage.SEARCHING,
            message="",
            progress_percentage=50,
            current_state=test_state
        )
        
        # 驗證觀察者被調用且訊息被生成
        self.observer.on_progress_update.assert_called_once()
        event = self.observer.on_progress_update.call_args[0][0]
        assert event.message == "🔍 正在搜尋..."
    
    @pytest.mark.asyncio
    async def test_notify_progress_explicit_auto_msg_true(self):
        """測試明確設置 auto_msg=True 的行為"""
        # 設置配置為關閉自動產生
        self.config.progress.discord.auto_generate_messages = False
        
        # 創建 mock progress LLM
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "🔍 正在搜尋..."
        mock_llm.ainvoke.return_value = mock_response
        self.progress_mixin._progress_llm = mock_llm
        
        # 創建測試狀態
        test_state = OverallState()
        test_state.current_persona = "default"
        
        # 測試空訊息 - 需要重寫 _build_agent_messages_for_progress 方法
        async def mock_build_agent_messages(stage, current_state):
            return []
        
        self.progress_mixin._build_agent_messages_for_progress = mock_build_agent_messages
        
        # 測試明確設置 auto_msg=True
        await self.progress_mixin._notify_progress(
            stage=ProgressStage.SEARCHING,
            message="",
            auto_msg=True,
            progress_percentage=50,
            current_state=test_state
        )
        
        # 驗證觀察者被調用且訊息被生成
        self.observer.on_progress_update.assert_called_once()
        event = self.observer.on_progress_update.call_args[0][0]
        assert event.message == "🔍 正在搜尋..."
    
    @pytest.mark.asyncio
    async def test_notify_progress_explicit_auto_msg_false(self):
        """測試明確設置 auto_msg=False 的行為"""
        # 設置配置為開啟自動產生
        self.config.progress.discord.auto_generate_messages = True
        
        # 創建 mock progress LLM
        mock_llm = AsyncMock()
        self.progress_mixin._progress_llm = mock_llm
        
        # 測試明確設置 auto_msg=False
        await self.progress_mixin._notify_progress(
            stage=ProgressStage.SEARCHING,
            message="",
            auto_msg=False,
            progress_percentage=50
        )
        
        # 驗證 LLM 未被調用（即使配置開啟）
        mock_llm.ainvoke.assert_not_called()
        
        # 驗證觀察者被調用但訊息為空
        self.observer.on_progress_update.assert_called_once()
        event = self.observer.on_progress_update.call_args[0][0]
        assert event.message == ""
    
    @pytest.mark.asyncio
    async def test_notify_progress_tool_status_no_auto_generate(self):
        """測試 TOOL_STATUS 階段不自動產生訊息"""
        # 設置配置為開啟自動產生
        self.config.progress.discord.auto_generate_messages = True
        
        # 創建 mock progress LLM
        mock_llm = AsyncMock()
        self.progress_mixin._progress_llm = mock_llm
        
        # 測試 TOOL_STATUS 階段
        await self.progress_mixin._notify_progress(
            stage=ProgressStage.TOOL_STATUS,
            message="",
            progress_percentage=50
        )
        
        # 驗證 LLM 未被調用（高頻事件不自動產生）
        mock_llm.ainvoke.assert_not_called()
        
        # 驗證觀察者被調用但訊息為空
        self.observer.on_progress_update.assert_called_once()
        event = self.observer.on_progress_update.call_args[0][0]
        assert event.message == ""
    
    @pytest.mark.asyncio
    async def test_notify_progress_without_llm(self):
        """測試沒有 LLM 時的行為"""
        # 設置配置為開啟自動產生
        self.config.progress.discord.auto_generate_messages = True
        
        # 不設置 LLM
        self.progress_mixin._progress_llm = None
        
        # 測試空訊息
        await self.progress_mixin._notify_progress(
            stage=ProgressStage.SEARCHING,
            message="",
            progress_percentage=50
        )
        
        # 驗證觀察者被調用但訊息為空
        self.observer.on_progress_update.assert_called_once()
        event = self.observer.on_progress_update.call_args[0][0]
        assert event.message == ""
    
    @pytest.mark.asyncio
    async def test_notify_progress_llm_error(self):
        """測試 LLM 錯誤時的處理"""
        # 設置配置為開啟自動產生
        self.config.progress.discord.auto_generate_messages = True
        
        # 創建會拋出異常的 mock LLM
        mock_llm = AsyncMock()
        mock_llm.ainvoke.side_effect = Exception("LLM 錯誤")
        self.progress_mixin._progress_llm = mock_llm
        
        # 創建測試狀態
        test_state = OverallState()
        test_state.current_persona = "default"
        
        # 測試空訊息 - 需要重寫 _build_agent_messages_for_progress 方法
        async def mock_build_agent_messages(stage, current_state):
            return []
        
        self.progress_mixin._build_agent_messages_for_progress = mock_build_agent_messages
        
        # 測試空訊息
        await self.progress_mixin._notify_progress(
            stage=ProgressStage.SEARCHING,
            message="",
            progress_percentage=50,
            current_state=test_state
        )
        
        # 驗證觀察者被調用且收到備用訊息
        self.observer.on_progress_update.assert_called_once()
        event = self.observer.on_progress_update.call_args[0][0]
        # 錯誤時應該返回配置中的訊息或預設訊息
        assert "🔍 正在搜尋資料" in event.message or "🔄 處理中" in event.message
    
    @pytest.mark.asyncio
    async def test_progress_multiple_notifications(self):
        """測試多個進度通知"""
        # 發送多個進度更新
        await self.progress_mixin._notify_progress(
            stage=ProgressStage.STARTING,
            message="開始處理"
        )
        await self.progress_mixin._notify_progress(
            stage=ProgressStage.SEARCHING,
            message="正在搜尋"
        )
        
        # 驗證觀察者被調用兩次
        assert self.observer.on_progress_update.call_count == 2
    
    def test_should_auto_generate_message_logic(self):
        """測試自動產生訊息的判斷邏輯"""
        # 創建 mock LLM
        mock_llm = MagicMock()
        self.progress_mixin._progress_llm = mock_llm
        
        # 測試有訊息時不自動產生
        assert not self.progress_mixin._should_auto_generate_message(
            "searching", "已有訊息", None
        )
        
        # 測試沒有 LLM 時不自動產生
        self.progress_mixin._progress_llm = None
        assert not self.progress_mixin._should_auto_generate_message(
            "searching", "", None
        )
        
        # 恢復 LLM
        self.progress_mixin._progress_llm = mock_llm
        
        # 測試高頻事件不自動產生
        assert not self.progress_mixin._should_auto_generate_message(
            ProgressStage.TOOL_STATUS.value, "", None
        )
        
        # 測試明確設置 auto_msg
        assert self.progress_mixin._should_auto_generate_message(
            "searching", "", True
        )
        assert not self.progress_mixin._should_auto_generate_message(
            "searching", "", False
        )
        
        # 測試根據配置決定
        self.config.progress.discord.auto_generate_messages = True
        assert self.progress_mixin._should_auto_generate_message(
            "searching", "", None
        )
        
        self.config.progress.discord.auto_generate_messages = False
        assert not self.progress_mixin._should_auto_generate_message(
            "searching", "", None
        )