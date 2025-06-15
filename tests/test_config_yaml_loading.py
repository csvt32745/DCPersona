"""
測試從 YAML 檔案載入提醒配置
"""

import pytest
import tempfile
import os
from pathlib import Path
from schemas.config_types import AppConfig


class TestYAMLConfigLoading:
    """測試 YAML 配置載入"""
    
    def test_load_config_with_reminder_from_yaml(self):
        """測試從 YAML 檔案載入包含提醒配置的應用程式配置"""
        yaml_content = """
reminder:
  enabled: false
  persistence_file: "custom/events.json"
  max_reminders_per_user: 5
  cleanup_expired_events: false

system:
  timezone: "UTC"
  debug_mode: true
"""
        
        # 創建臨時 YAML 檔案
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            # 載入配置
            config = AppConfig.from_yaml(temp_path)
            
            # 驗證提醒配置
            assert config.reminder.enabled is False
            assert config.reminder.persistence_file == "custom/events.json"
            assert config.reminder.max_reminders_per_user == 5
            assert config.reminder.cleanup_expired_events is False
            
            # 驗證其他配置也正常載入
            assert config.system.timezone == "UTC"
            assert config.system.debug_mode is True
            
        finally:
            # 清理臨時檔案
            os.unlink(temp_path)
    
    def test_load_config_example_yaml(self):
        """測試載入 config-example.yaml 檔案"""
        config_path = "config-example.yaml"
        
        if not Path(config_path).exists():
            pytest.skip(f"配置檔案 {config_path} 不存在")
        
        # 載入配置
        config = AppConfig.from_yaml(config_path)
        
        # 驗證提醒配置存在且有預設值
        assert hasattr(config, 'reminder')
        assert config.reminder.enabled is True
        assert config.reminder.persistence_file == "data/events.json"
        assert config.reminder.max_reminders_per_user == 10
        assert config.reminder.cleanup_expired_events is True
    
    def test_load_config_without_reminder_section(self):
        """測試載入沒有提醒區塊的 YAML 配置（應該使用預設值）"""
        yaml_content = """
system:
  timezone: "Asia/Tokyo"
  debug_mode: false

discord:
  bot_token: "test_token"
"""
        
        # 創建臨時 YAML 檔案
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            # 載入配置
            config = AppConfig.from_yaml(temp_path)
            
            # 驗證提醒配置使用預設值
            assert config.reminder.enabled is True
            assert config.reminder.persistence_file == "data/events.json"
            assert config.reminder.max_reminders_per_user == 10
            assert config.reminder.cleanup_expired_events is True
            
            # 驗證其他配置正常載入
            assert config.system.timezone == "Asia/Tokyo"
            assert config.discord.bot_token == "test_token"
            
        finally:
            # 清理臨時檔案
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__]) 