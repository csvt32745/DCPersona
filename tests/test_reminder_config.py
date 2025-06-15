"""
測試提醒相關的配置和資料結構
"""

import pytest
from datetime import datetime
from schemas.config_types import AppConfig, ReminderConfig
from schemas.agent_types import ReminderDetails, ToolExecutionResult, OverallState


class TestReminderConfig:
    """測試提醒配置"""
    
    def test_reminder_config_defaults(self):
        """測試提醒配置的預設值"""
        config = ReminderConfig()
        
        assert config.enabled is True
        assert config.persistence_file == "data/events.json"
        assert config.max_reminders_per_user == 10
        assert config.cleanup_expired_events is True
    
    def test_reminder_config_custom_values(self):
        """測試提醒配置的自定義值"""
        config = ReminderConfig(
            enabled=False,
            persistence_file="custom/path.json",
            max_reminders_per_user=5,
            cleanup_expired_events=False
        )
        
        assert config.enabled is False
        assert config.persistence_file == "custom/path.json"
        assert config.max_reminders_per_user == 5
        assert config.cleanup_expired_events is False


class TestAppConfigWithReminder:
    """測試包含提醒配置的應用程式配置"""
    
    def test_app_config_includes_reminder(self):
        """測試應用程式配置包含提醒配置"""
        config = AppConfig()
        
        assert hasattr(config, 'reminder')
        assert isinstance(config.reminder, ReminderConfig)
        assert config.reminder.enabled is True
    
    def test_app_config_from_dict_with_reminder(self):
        """測試從字典載入包含提醒配置的應用程式配置"""
        config_dict = {
            "reminder": {
                "enabled": False,
                "persistence_file": "test/events.json",
                "max_reminders_per_user": 3
            }
        }
        
        config = AppConfig.from_dict(config_dict)
        
        assert config.reminder.enabled is False
        assert config.reminder.persistence_file == "test/events.json"
        assert config.reminder.max_reminders_per_user == 3
        assert config.reminder.cleanup_expired_events is True  # 預設值


class TestReminderDetails:
    """測試提醒詳細資料結構"""
    
    def test_reminder_details_creation(self):
        """測試提醒詳細資料的創建"""
        reminder = ReminderDetails(
            message="測試提醒",
            target_timestamp="2024-01-01T10:00:00Z",
            channel_id="123456789",
            user_id="987654321",
            msg_id="555555555"
        )
        
        assert reminder.message == "測試提醒"
        assert reminder.target_timestamp == "2024-01-01T10:00:00Z"
        assert reminder.channel_id == "123456789"
        assert reminder.user_id == "987654321"
        assert reminder.reminder_id is None
        assert reminder.metadata == {}
    
    def test_reminder_details_with_optional_fields(self):
        """測試包含可選欄位的提醒詳細資料"""
        reminder = ReminderDetails(
            message="測試提醒",
            target_timestamp="2024-01-01T10:00:00Z",
            channel_id="123456789",
            user_id="987654321",
            msg_id="555555555",
            reminder_id="reminder_123",
            metadata={"source": "test"}
        )
        
        assert reminder.reminder_id == "reminder_123"
        assert reminder.metadata == {"source": "test"}


class TestToolExecutionResult:
    """測試工具執行結果結構"""
    
    def test_tool_execution_result_success(self):
        """測試成功的工具執行結果"""
        result = ToolExecutionResult(
            success=True,
            message="提醒設定成功",
            data={"reminder_id": "123"}
        )
        
        assert result.success is True
        assert result.message == "提醒設定成功"
        assert result.data == {"reminder_id": "123"}
    
    def test_tool_execution_result_failure(self):
        """測試失敗的工具執行結果"""
        result = ToolExecutionResult(
            success=False,
            message="時間格式錯誤"
        )
        
        assert result.success is False
        assert result.message == "時間格式錯誤"
        assert result.data is None


class TestOverallStateWithReminders:
    """測試包含提醒的整體狀態"""
    
    def test_overall_state_reminder_requests(self):
        """測試整體狀態的提醒請求欄位"""
        state = OverallState()
        
        assert hasattr(state, 'reminder_requests')
        assert isinstance(state.reminder_requests, list)
        assert len(state.reminder_requests) == 0
    
    def test_overall_state_add_reminder_request(self):
        """測試向整體狀態添加提醒請求"""
        state = OverallState()
        
        reminder = ReminderDetails(
            message="測試提醒",
            target_timestamp="2024-01-01T10:00:00Z",
            channel_id="123456789",
            user_id="987654321",
            msg_id="555555555"
        )
        
        state.reminder_requests.append(reminder)
        
        assert len(state.reminder_requests) == 1
        assert state.reminder_requests[0] == reminder


if __name__ == "__main__":
    pytest.main([__file__]) 