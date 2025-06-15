"""
提醒功能整合測試
展示提醒配置和資料結構的完整使用流程
"""

import pytest
from datetime import datetime, timedelta
from schemas.config_types import AppConfig, ReminderConfig
from schemas.agent_types import ReminderDetails, ToolExecutionResult, OverallState


class TestReminderIntegration:
    """提醒功能整合測試"""
    
    def test_complete_reminder_workflow(self):
        """測試完整的提醒工作流程"""
        # 1. 載入配置
        config = AppConfig()
        assert config.reminder.enabled is True
        
        # 2. 創建提醒詳細資料
        reminder = ReminderDetails(
            message="記得喝水",
            target_timestamp="2024-12-25T10:00:00Z",
            channel_id="123456789",
            user_id="987654321",
            msg_id="555555555",
            reminder_id="reminder_001"
        )
        
        # 3. 創建工具執行結果
        tool_result = ToolExecutionResult(
            success=True,
            message="提醒設定成功",
            data={"reminder_id": reminder.reminder_id}
        )
        
        # 4. 更新 Agent 狀態
        state = OverallState()
        state.reminder_requests.append(reminder)
        
        # 5. 驗證狀態
        assert len(state.reminder_requests) == 1
        assert state.reminder_requests[0].message == "記得喝水"
        assert state.reminder_requests[0].reminder_id == "reminder_001"
        
        # 6. 驗證工具結果
        assert tool_result.success is True
        assert tool_result.data["reminder_id"] == "reminder_001"
    
    def test_reminder_config_validation(self):
        """測試提醒配置驗證"""
        # 測試自定義配置
        custom_config = ReminderConfig(
            enabled=True,
            persistence_file="custom/reminders.json",
            max_reminders_per_user=5,
            cleanup_expired_events=False
        )
        
        # 驗證配置值
        assert custom_config.enabled is True
        assert custom_config.persistence_file == "custom/reminders.json"
        assert custom_config.max_reminders_per_user == 5
        assert custom_config.cleanup_expired_events is False
    
    def test_multiple_reminders_in_state(self):
        """測試在狀態中管理多個提醒"""
        state = OverallState()
        
        # 添加多個提醒
        reminders = [
            ReminderDetails(
                message="提醒 1",
                target_timestamp="2024-12-25T10:00:00Z",
                channel_id="123",
                user_id="456",
                msg_id="111111111",
                reminder_id="r1"
            ),
            ReminderDetails(
                message="提醒 2",
                target_timestamp="2024-12-25T11:00:00Z",
                channel_id="123",
                user_id="456",
                msg_id="222222222",
                reminder_id="r2"
            ),
            ReminderDetails(
                message="提醒 3",
                target_timestamp="2024-12-25T12:00:00Z",
                channel_id="789",
                user_id="456",
                msg_id="333333333",
                reminder_id="r3"
            )
        ]
        
        for reminder in reminders:
            state.reminder_requests.append(reminder)
        
        # 驗證所有提醒都已添加
        assert len(state.reminder_requests) == 3
        
        # 驗證可以按用戶過濾
        user_reminders = [r for r in state.reminder_requests if r.user_id == "456"]
        assert len(user_reminders) == 3
        
        # 驗證可以按頻道過濾
        channel_reminders = [r for r in state.reminder_requests if r.channel_id == "123"]
        assert len(channel_reminders) == 2
    
    def test_reminder_data_serialization(self):
        """測試提醒資料的序列化（為持久化做準備）"""
        reminder = ReminderDetails(
            message="測試提醒",
            target_timestamp="2024-12-25T10:00:00Z",
            channel_id="123456789",
            user_id="987654321",
            msg_id="555555555",
            reminder_id="test_001",
            metadata={"priority": "high", "category": "work"}
        )
        
        # 驗證所有欄位都可以訪問（為 JSON 序列化做準備）
        reminder_dict = {
            "message": reminder.message,
            "target_timestamp": reminder.target_timestamp,
            "channel_id": reminder.channel_id,
            "user_id": reminder.user_id,
            "reminder_id": reminder.reminder_id,
            "metadata": reminder.metadata
        }
        
        # 驗證字典包含所有必要資訊
        assert reminder_dict["message"] == "測試提醒"
        assert reminder_dict["target_timestamp"] == "2024-12-25T10:00:00Z"
        assert reminder_dict["channel_id"] == "123456789"
        assert reminder_dict["user_id"] == "987654321"
        assert reminder_dict["reminder_id"] == "test_001"
        assert reminder_dict["metadata"]["priority"] == "high"
        assert reminder_dict["metadata"]["category"] == "work"


if __name__ == "__main__":
    pytest.main([__file__]) 