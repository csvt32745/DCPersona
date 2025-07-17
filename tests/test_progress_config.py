"""
進度配置測試

測試進度訊息配置化功能，確保自訂配置正確載入和使用。
"""

import pytest
import logging
from unittest.mock import patch
from schemas.config_types import AppConfig, ProgressDiscordConfig
from schemas.agent_types import DiscordProgressUpdate
from agent_core.progress_types import ProgressStage, ToolStatus, TOOL_STATUS_SYMBOLS
from discord_bot.progress_adapter import DiscordProgressAdapter
from agent_core.progress_observer import ProgressEvent


def test_progress_stage_enum():
    """測試 ProgressStage enum 定義"""
    # 測試所有必要的階段都存在
    assert ProgressStage.STARTING == "starting"
    assert ProgressStage.GENERATE_QUERY == "generate_query"
    assert ProgressStage.SEARCHING == "searching"
    assert ProgressStage.ANALYZING == "analyzing"
    assert ProgressStage.COMPLETING == "completing"
    assert ProgressStage.STREAMING == "streaming"
    assert ProgressStage.COMPLETED == "completed"
    assert ProgressStage.ERROR == "error"
    assert ProgressStage.TIMEOUT == "timeout"
    assert ProgressStage.TOOL_LIST == "tool_list"
    assert ProgressStage.TOOL_STATUS == "tool_status"
    assert ProgressStage.TOOL_EXECUTION == "tool_execution"
    assert ProgressStage.REFLECTION == "reflection"
    assert ProgressStage.FINALIZE_ANSWER == "finalize_answer"


def test_tool_status_enum():
    """測試 ToolStatus enum 定義"""
    assert ToolStatus.PENDING == "pending"
    assert ToolStatus.RUNNING == "running"
    assert ToolStatus.COMPLETED == "completed"
    assert ToolStatus.ERROR == "error"


def test_tool_status_symbols():
    """測試工具狀態符號映射"""
    assert TOOL_STATUS_SYMBOLS[ToolStatus.PENDING] == "⚪"
    assert TOOL_STATUS_SYMBOLS[ToolStatus.RUNNING] == "🔄"
    assert TOOL_STATUS_SYMBOLS[ToolStatus.COMPLETED] == "✅"
    assert TOOL_STATUS_SYMBOLS[ToolStatus.ERROR] == "❌"


def test_default_progress_messages():
    """測試預設進度訊息載入"""
    config = AppConfig()
    
    # 檢查預設配置中包含所有必要的進度訊息
    messages = config.progress.discord.messages
    
    assert ProgressStage.STARTING.value in messages
    assert ProgressStage.GENERATE_QUERY.value in messages
    assert ProgressStage.COMPLETED.value in messages
    assert ProgressStage.ERROR.value in messages
    assert ProgressStage.TOOL_STATUS.value in messages
    
    # 檢查訊息內容不為空
    assert messages[ProgressStage.STARTING.value] != ""
    assert messages[ProgressStage.COMPLETED.value] != ""


def test_custom_progress_messages():
    """測試自訂進度訊息配置"""
    # 建立自訂配置
    custom_messages = {
        ProgressStage.STARTING.value: "🚀 自訂開始訊息",
        ProgressStage.COMPLETED.value: "🎉 自訂完成訊息",
        ProgressStage.ERROR.value: "💥 自訂錯誤訊息"
    }
    
    config_dict = {
        "progress": {
            "discord": {
                "messages": custom_messages
            }
        }
    }
    
    config = AppConfig.from_dict(config_dict)
    
    # 驗證自訂訊息正確載入
    messages = config.progress.discord.messages
    assert messages[ProgressStage.STARTING.value] == "🚀 自訂開始訊息"
    assert messages[ProgressStage.COMPLETED.value] == "🎉 自訂完成訊息"
    assert messages[ProgressStage.ERROR.value] == "💥 自訂錯誤訊息"


def test_progress_event_with_enum():
    """測試 ProgressEvent 使用 enum"""
    event = ProgressEvent(
        stage=ProgressStage.SEARCHING,
        message="測試訊息",
        progress_percentage=50,
        metadata={"test": "data"}
    )
    
    assert event.stage == ProgressStage.SEARCHING
    assert event.stage.value == "searching"
    assert event.message == "測試訊息"
    assert event.progress_percentage == 50


def test_discord_progress_update_with_enum():
    """測試 DiscordProgressUpdate 使用 enum"""
    update = DiscordProgressUpdate(
        stage=ProgressStage.ANALYZING,
        message="正在分析...",
        progress_percentage=75
    )
    
    assert update.stage == ProgressStage.ANALYZING
    assert update.stage.value == "analyzing"
    assert update.message == "正在分析..."
    assert update.progress_percentage == 75


@pytest.mark.asyncio
async def test_progress_adapter_config_loading():
    """測試進度適配器配置載入
    
    注意：此測試模擬配置載入，但不實際發送 Discord 訊息
    """
    # 建立自訂配置
    custom_messages = {
        ProgressStage.STARTING.value: "🔥 測試專用開始訊息",
        ProgressStage.COMPLETED.value: "🎯 測試專用完成訊息"
    }
    
    config_dict = {
        "progress": {
            "discord": {
                "messages": custom_messages
            }
        }
    }
    
    config = AppConfig.from_dict(config_dict)
    
    # 驗證配置正確載入
    assert config.progress.discord.messages[ProgressStage.STARTING.value] == "🔥 測試專用開始訊息"
    assert config.progress.discord.messages[ProgressStage.COMPLETED.value] == "🎯 測試專用完成訊息"


def test_config_yaml_compatibility():
    """測試配置檔案格式相容性"""
    # 模擬從 YAML 載入的配置結構
    yaml_config = {
        "progress": {
            "discord": {
                "enabled": True,
                "use_embeds": True,
                "update_interval": 2,
                "messages": {
                    "starting": "🔄 YAML 開始訊息",
                    "completed": "✅ YAML 完成訊息",
                    "error": "❌ YAML 錯誤訊息"
                }
            }
        }
    }
    
    config = AppConfig.from_dict(yaml_config)
    
    # 驗證配置正確載入
    assert config.progress.discord.enabled is True
    assert config.progress.discord.use_embeds is True
    assert config.progress.discord.update_interval == 2
    assert config.progress.discord.messages["starting"] == "🔄 YAML 開始訊息"
    assert config.progress.discord.messages["completed"] == "✅ YAML 完成訊息"
    assert config.progress.discord.messages["error"] == "❌ YAML 錯誤訊息"


def test_valid_progress_message_keys():
    """測試有效的進度訊息配置 key 不會產生警告"""
    with patch('schemas.config_types.logging') as mock_logging:
        # 使用有效的 key，並提供完整配置避免其他警告
        config_dict = {
            "discord": {
                "bot_token": "test_token"  # 避免 Discord 配置警告
            },
            "progress": {
                "discord": {
                    "messages": {
                        "starting": "開始訊息",
                        "completed": "完成訊息",
                        "error": "錯誤訊息"
                    }
                }
            }
        }
        
        # 設置環境變數避免 API key 警告
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            config = AppConfig.from_dict(config_dict)
        
        # 檢查是否有進度訊息相關的警告
        warning_calls = [call.args[0] for call in mock_logging.warning.call_args_list]
        progress_warnings = [msg for msg in warning_calls if "無效的 key" in msg]
        assert len(progress_warnings) == 0
        
        # 驗證配置正確載入
        messages = config.progress.discord.messages
        assert messages["starting"] == "開始訊息"
        assert messages["completed"] == "完成訊息"
        assert messages["error"] == "錯誤訊息"


def test_invalid_progress_message_keys():
    """測試無效的進度訊息配置 key 會產生警告"""
    with patch('schemas.config_types.logging') as mock_logging:
        # 使用無效的 key，並提供完整配置避免其他警告
        config_dict = {
            "discord": {
                "bot_token": "test_token"  # 避免 Discord 配置警告
            },
            "progress": {
                "discord": {
                    "messages": {
                        "starting": "開始訊息",
                        "invalid_key1": "無效訊息1",
                        "invalid_key2": "無效訊息2",
                        "completed": "完成訊息"
                    }
                }
            }
        }
        
        # 設置環境變數避免 API key 警告
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            config = AppConfig.from_dict(config_dict)
        
        # 檢查警告訊息內容
        warning_calls = [call.args[0] for call in mock_logging.warning.call_args_list]
        invalid_key_warning = next((msg for msg in warning_calls if "無效的 key" in msg), None)
        assert invalid_key_warning is not None
        assert "invalid_key1" in invalid_key_warning
        assert "invalid_key2" in invalid_key_warning
        
        # 驗證配置仍然正確載入（包括無效的 key）
        messages = config.progress.discord.messages
        assert messages["starting"] == "開始訊息"
        assert messages["completed"] == "完成訊息"
        assert messages["invalid_key1"] == "無效訊息1"
        assert messages["invalid_key2"] == "無效訊息2"


def test_mixed_valid_invalid_keys():
    """測試混合有效和無效 key 的情況"""
    with patch('schemas.config_types.logging') as mock_logging:
        config_dict = {
            "discord": {
                "bot_token": "test_token"  # 避免 Discord 配置警告
            },
            "progress": {
                "discord": {
                    "messages": {
                        "starting": "有效開始訊息",
                        "bad_key": "無效訊息",
                        "completed": "有效完成訊息",
                        "another_bad_key": "另一個無效訊息"
                    }
                }
            }
        }
        
        # 設置環境變數避免 API key 警告
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            config = AppConfig.from_dict(config_dict)
        
        # 檢查是否有進度訊息相關的警告
        warning_calls = [call.args[0] for call in mock_logging.warning.call_args_list]
        progress_warnings = [msg for msg in warning_calls if "無效的 key" in msg]
        assert len(progress_warnings) > 0
        
        # 驗證有效的 key 正常載入
        messages = config.progress.discord.messages
        assert messages["starting"] == "有效開始訊息"
        assert messages["completed"] == "有效完成訊息"


if __name__ == "__main__":
    pytest.main([__file__]) 