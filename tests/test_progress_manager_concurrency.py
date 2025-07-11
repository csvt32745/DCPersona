"""
ProgressManager 並行處理測試

測試重構後的 ProgressManager 是否能正確處理並行請求，
避免 Race Condition 並確保不同訊息的進度追蹤是獨立的。
"""

import pytest
import asyncio
import discord
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any

from discord_bot.progress_manager import ProgressManager, get_progress_manager
from schemas.agent_types import DiscordProgressUpdate, ResearchSource


class TestProgressManagerConcurrency:
    """測試 ProgressManager 的並行處理能力"""
    
    @pytest.fixture
    def progress_manager(self):
        """建立測試用的 ProgressManager 實例"""
        return ProgressManager()
    
    @pytest.fixture
    def mock_message_1(self):
        """建立第一個模擬 Discord 訊息"""
        message = Mock(spec=discord.Message)
        message.id = 12345
        message.channel = Mock()
        message.channel.id = 67890
        message.reply = AsyncMock()
        return message
    
    @pytest.fixture
    def mock_message_2(self):
        """建立第二個模擬 Discord 訊息（同頻道，不同 ID）"""
        message = Mock(spec=discord.Message)
        message.id = 54321  # 不同的 message_id
        message.channel = Mock()
        message.channel.id = 67890  # 相同的 channel_id
        message.reply = AsyncMock()
        return message
    
    @pytest.fixture
    def mock_message_3(self):
        """建立第三個模擬 Discord 訊息（不同頻道）"""
        message = Mock(spec=discord.Message)
        message.id = 11111
        message.channel = Mock()
        message.channel.id = 99999  # 不同的 channel_id
        message.reply = AsyncMock()
        return message
    
    @pytest.fixture
    def sample_progress_update(self):
        """建立樣本進度更新"""
        return DiscordProgressUpdate(
            stage="searching",
            message="正在搜尋資料...",
            progress_percentage=50,
            eta_seconds=30
        )
    
    @pytest.mark.asyncio
    async def test_concurrent_different_messages_same_channel(
        self, 
        progress_manager, 
        mock_message_1, 
        mock_message_2, 
        sample_progress_update
    ):
        """測試同一頻道中不同訊息的並行處理"""
        
        # 模擬回覆訊息
        mock_progress_msg_1 = Mock(spec=discord.Message)
        mock_progress_msg_1.id = 1001
        mock_progress_msg_1.edit = AsyncMock()
        
        mock_progress_msg_2 = Mock(spec=discord.Message)
        mock_progress_msg_2.id = 1002
        mock_progress_msg_2.edit = AsyncMock()
        
        mock_message_1.reply.return_value = mock_progress_msg_1
        mock_message_2.reply.return_value = mock_progress_msg_2
        
        # 建立兩個不同的進度更新
        progress_1 = DiscordProgressUpdate(
            stage="searching", 
            message="訊息1正在搜尋...", 
            progress_percentage=25
        )
        progress_2 = DiscordProgressUpdate(
            stage="analyzing", 
            message="訊息2正在分析...", 
            progress_percentage=75
        )
        
        # 並行執行兩個進度更新
        results = await asyncio.gather(
            progress_manager.send_or_update_progress(mock_message_1, progress_1),
            progress_manager.send_or_update_progress(mock_message_2, progress_2),
            return_exceptions=True
        )
        
        # 驗證兩個操作都成功
        assert len(results) == 2
        assert results[0] == mock_progress_msg_1
        assert results[1] == mock_progress_msg_2
        
        # 驗證兩個訊息都被正確記錄，且使用不同的鍵
        assert mock_message_1.id in progress_manager._progress_messages
        assert mock_message_2.id in progress_manager._progress_messages
        assert progress_manager._progress_messages[mock_message_1.id] == mock_progress_msg_1
        assert progress_manager._progress_messages[mock_message_2.id] == mock_progress_msg_2
        
        # 驗證兩個原始訊息都有對應的回覆被觸發
        mock_message_1.reply.assert_called_once()
        mock_message_2.reply.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_concurrent_updates_same_message(
        self, 
        progress_manager, 
        mock_message_1
    ):
        """測試同一訊息的並行更新（應該使用編輯而非建立新訊息）"""
        
        # 模擬第一次回覆建立的進度訊息
        mock_progress_msg = Mock(spec=discord.Message)
        mock_progress_msg.id = 2001
        mock_progress_msg.edit = AsyncMock()
        mock_progress_msg.channel = mock_message_1.channel
        
        mock_message_1.reply.return_value = mock_progress_msg
        
        # 第一次進度更新
        progress_1 = DiscordProgressUpdate(
            stage="starting", 
            message="開始處理...", 
            progress_percentage=10
        )
        
        # 先發送第一個進度更新，建立進度訊息
        result_1 = await progress_manager.send_or_update_progress(mock_message_1, progress_1)
        assert result_1 == mock_progress_msg
        
        # 建立後續的進度更新
        progress_2 = DiscordProgressUpdate(
            stage="processing", 
            message="處理中...", 
            progress_percentage=50
        )
        progress_3 = DiscordProgressUpdate(
            stage="finishing", 
            message="即將完成...", 
            progress_percentage=90
        )
        
        # 並行執行兩個後續更新
        results = await asyncio.gather(
            progress_manager.send_or_update_progress(mock_message_1, progress_2),
            progress_manager.send_or_update_progress(mock_message_1, progress_3),
            return_exceptions=True
        )
        
        # 驗證兩個更新都成功並返回相同的進度訊息
        assert len(results) == 2
        assert results[0] == mock_progress_msg
        assert results[1] == mock_progress_msg
        
        # 驗證只有一個進度訊息被記錄
        assert len(progress_manager._progress_messages) == 1
        assert mock_message_1.id in progress_manager._progress_messages
        
        # 驗證 reply 只被呼叫一次（第一次），後續都是 edit
        mock_message_1.reply.assert_called_once()
        
        # 驗證 edit 被呼叫了兩次（對應兩個後續更新）
        assert mock_progress_msg.edit.call_count == 2
    
    @pytest.mark.asyncio
    async def test_high_concurrency_stress_test(
        self, 
        progress_manager
    ):
        """高並行壓力測試 - 模擬多個使用者同時發送訊息"""
        
        num_messages = 20
        mock_messages = []
        
        # 建立多個模擬訊息
        for i in range(num_messages):
            message = Mock(spec=discord.Message)
            message.id = 10000 + i
            message.channel = Mock()
            message.channel.id = 50000 + (i % 5)  # 5個不同頻道
            
            # 模擬進度訊息
            progress_msg = Mock(spec=discord.Message)
            progress_msg.id = 20000 + i
            progress_msg.edit = AsyncMock()
            progress_msg.channel = message.channel
            
            message.reply = AsyncMock(return_value=progress_msg)
            mock_messages.append(message)
        
        # 建立進度更新任務
        async def create_progress_task(msg_index):
            message = mock_messages[msg_index]
            progress = DiscordProgressUpdate(
                stage="processing",
                message=f"處理訊息 {msg_index}...",
                progress_percentage=min(100, msg_index * 5)
            )
            return await progress_manager.send_or_update_progress(message, progress)
        
        # 並行執行所有任務
        tasks = [create_progress_task(i) for i in range(num_messages)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 驗證所有任務都成功完成
        assert len(results) == num_messages
        for i, result in enumerate(results):
            assert not isinstance(result, Exception), f"任務 {i} 失敗: {result}"
            assert result is not None
        
        # 驗證所有訊息都被正確記錄
        assert len(progress_manager._progress_messages) == num_messages
        for i in range(num_messages):
            message_id = mock_messages[i].id
            assert message_id in progress_manager._progress_messages
            assert message_id in progress_manager._message_to_progress
            assert message_id in progress_manager._message_timestamps
        
        # 驗證每個原始訊息都有一次 reply 調用
        for message in mock_messages:
            message.reply.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_by_message_id(
        self, 
        progress_manager, 
        mock_message_1, 
        mock_message_2, 
        sample_progress_update
    ):
        """測試基於 message_id 的清理功能"""
        
        # 模擬進度訊息
        mock_progress_msg_1 = Mock(spec=discord.Message)
        mock_progress_msg_2 = Mock(spec=discord.Message)
        mock_message_1.reply.return_value = mock_progress_msg_1
        mock_message_2.reply.return_value = mock_progress_msg_2
        
        # 建立兩個進度記錄
        await progress_manager.send_or_update_progress(mock_message_1, sample_progress_update)
        await progress_manager.send_or_update_progress(mock_message_2, sample_progress_update)
        
        # 驗證兩個記錄都存在
        assert len(progress_manager._progress_messages) == 2
        assert len(progress_manager._message_to_progress) == 2
        assert len(progress_manager._message_timestamps) == 2
        
        # 清理第一個訊息
        progress_manager.cleanup_by_message_id(mock_message_1.id)
        
        # 驗證只有第一個訊息的記錄被清理
        assert mock_message_1.id not in progress_manager._progress_messages
        assert mock_message_1.id not in progress_manager._message_to_progress
        assert mock_message_1.id not in progress_manager._message_timestamps
        
        # 驗證第二個訊息的記錄仍然存在
        assert mock_message_2.id in progress_manager._progress_messages
        assert mock_message_2.id in progress_manager._message_to_progress
        assert mock_message_2.id in progress_manager._message_timestamps
    
    @pytest.mark.asyncio
    async def test_backward_compatibility_cleanup_progress_message(
        self, 
        progress_manager, 
        mock_message_1, 
        mock_message_2, 
        mock_message_3, 
        sample_progress_update
    ):
        """測試向後相容的 cleanup_progress_message 方法"""
        
        # 模擬進度訊息
        mock_progress_msg_1 = Mock(spec=discord.Message)
        mock_progress_msg_1.channel = mock_message_1.channel
        mock_progress_msg_2 = Mock(spec=discord.Message)
        mock_progress_msg_2.channel = mock_message_2.channel
        mock_progress_msg_3 = Mock(spec=discord.Message)
        mock_progress_msg_3.channel = mock_message_3.channel
        
        mock_message_1.reply.return_value = mock_progress_msg_1
        mock_message_2.reply.return_value = mock_progress_msg_2
        mock_message_3.reply.return_value = mock_progress_msg_3
        
        # 建立三個進度記錄（message_1 和 message_2 在同一頻道）
        await progress_manager.send_or_update_progress(mock_message_1, sample_progress_update)
        await progress_manager.send_or_update_progress(mock_message_2, sample_progress_update)
        await progress_manager.send_or_update_progress(mock_message_3, sample_progress_update)
        
        # 驗證三個記錄都存在
        assert len(progress_manager._progress_messages) == 3
        
        # 使用舊的 cleanup_progress_message 方法清理 message_1 和 message_2 的頻道
        channel_id = mock_message_1.channel.id
        progress_manager.cleanup_progress_message(channel_id)
        
        # 驗證同一頻道的兩個訊息都被清理
        assert mock_message_1.id not in progress_manager._progress_messages
        assert mock_message_2.id not in progress_manager._progress_messages
        
        # 驗證不同頻道的訊息仍然存在
        assert mock_message_3.id in progress_manager._progress_messages
    
    def test_global_progress_manager_instance(self):
        """測試全域 ProgressManager 實例的一致性"""
        
        # 獲取兩次全域實例
        manager_1 = get_progress_manager()
        manager_2 = get_progress_manager()
        
        # 驗證是同一個實例
        assert manager_1 is manager_2
        
        # 驗證實例有必要的屬性
        assert hasattr(manager_1, '_progress_messages')
        assert hasattr(manager_1, '_message_to_progress')
        assert hasattr(manager_1, '_message_timestamps')
        assert hasattr(manager_1, '_lock')
        
        # 驗證鎖是 asyncio.Lock 類型
        assert isinstance(manager_1._lock, asyncio.Lock)
    
    @pytest.mark.asyncio
    async def test_concurrent_cleanup_operations(
        self, 
        progress_manager, 
        mock_message_1, 
        mock_message_2, 
        sample_progress_update
    ):
        """測試並行清理操作的安全性"""
        
        # 模擬進度訊息
        mock_progress_msg_1 = Mock(spec=discord.Message)
        mock_progress_msg_2 = Mock(spec=discord.Message)
        mock_message_1.reply.return_value = mock_progress_msg_1
        mock_message_2.reply.return_value = mock_progress_msg_2
        
        # 建立進度記錄
        await progress_manager.send_or_update_progress(mock_message_1, sample_progress_update)
        await progress_manager.send_or_update_progress(mock_message_2, sample_progress_update)
        
        # 並行執行清理操作
        await asyncio.gather(
            asyncio.create_task(asyncio.to_thread(
                progress_manager.cleanup_by_message_id, mock_message_1.id
            )),
            asyncio.create_task(asyncio.to_thread(
                progress_manager.cleanup_by_message_id, mock_message_2.id
            )),
            return_exceptions=True
        )
        
        # 驗證所有記錄都被正確清理
        assert len(progress_manager._progress_messages) == 0
        assert len(progress_manager._message_to_progress) == 0
        assert len(progress_manager._message_timestamps) == 0 