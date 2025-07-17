"""
進度相關配置驗證測試
"""

import pytest
from schemas.config_types import AppConfig, ConfigurationError, LLMConfig, LLMModelConfig


class TestProgressConfigValidation:
    """進度相關配置驗證測試類別"""
    
    def test_llm_model_config_max_output_tokens_default(self):
        """測試 LLMModelConfig 的 max_output_tokens 預設值"""
        config = LLMModelConfig()
        assert config.max_output_tokens == 32
    
    def test_llm_model_config_max_output_tokens_custom(self):
        """測試 LLMModelConfig 的 max_output_tokens 自訂值"""
        config = LLMModelConfig(max_output_tokens=20)
        assert config.max_output_tokens == 20
    
    def test_progress_discord_config_auto_generate_default(self):
        """測試 ProgressDiscordConfig 的 auto_generate_messages 預設值"""
        config = AppConfig()
        assert config.progress.discord.auto_generate_messages is False
    
    def test_validate_llm_models_config_valid(self):
        """測試有效的 LLM 模型配置驗證"""
        models_config = {
            "progress_msg": {
                "model": "gemini-2.0-flash-lite",
                "temperature": 0.4,
                "max_output_tokens": 20
            },
            "tool_analysis": {
                "model": "gemini-2.0-flash-exp",
                "temperature": 0.1,
                "max_output_tokens": 100
            }
        }
        
        # 應該不拋出異常
        AppConfig._validate_llm_models_config(models_config)
    
    def test_validate_llm_models_config_invalid_max_tokens(self):
        """測試無效的 max_output_tokens 配置"""
        models_config = {
            "progress_msg": {
                "model": "gemini-2.0-flash-lite",
                "temperature": 0.4,
                "max_output_tokens": 0  # 無效值
            }
        }
        
        with pytest.raises(ConfigurationError, match="max_output_tokens 必須大於 0"):
            AppConfig._validate_llm_models_config(models_config)
    
    def test_validate_llm_models_config_negative_max_tokens(self):
        """測試負數的 max_output_tokens 配置"""
        models_config = {
            "progress_msg": {
                "model": "gemini-2.0-flash-lite",
                "temperature": 0.4,
                "max_output_tokens": -5  # 負值
            }
        }
        
        with pytest.raises(ConfigurationError, match="max_output_tokens 必須大於 0"):
            AppConfig._validate_llm_models_config(models_config)
    
    def test_validate_llm_models_config_missing_max_tokens(self):
        """測試缺少 max_output_tokens 配置（應該正常）"""
        models_config = {
            "progress_msg": {
                "model": "gemini-2.0-flash-lite",
                "temperature": 0.4
                # 沒有 max_output_tokens
            }
        }
        
        # 應該不拋出異常
        AppConfig._validate_llm_models_config(models_config)
    
    def test_validate_llm_models_config_none_max_tokens(self):
        """測試 None 的 max_output_tokens 配置（應該正常）"""
        models_config = {
            "progress_msg": {
                "model": "gemini-2.0-flash-lite",
                "temperature": 0.4,
                "max_output_tokens": None
            }
        }
        
        # 應該不拋出異常
        AppConfig._validate_llm_models_config(models_config)
    
    def test_validate_llm_models_config_non_dict_model(self):
        """測試非字典的模型配置（應該被跳過）"""
        models_config = {
            "progress_msg": "not_a_dict",
            "tool_analysis": {
                "model": "gemini-2.0-flash-exp",
                "temperature": 0.1,
                "max_output_tokens": 100
            }
        }
        
        # 應該不拋出異常
        AppConfig._validate_llm_models_config(models_config)
    
    def test_full_config_validation_integration(self):
        """測試完整配置驗證整合"""
        config_data = {
            "llm": {
                "models": {
                    "progress_msg": {
                        "model": "gemini-2.0-flash-lite",
                        "temperature": 0.4,
                        "max_output_tokens": 20
                    },
                    "tool_analysis": {
                        "model": "gemini-2.0-flash-exp",
                        "temperature": 0.1,
                        "max_output_tokens": 100
                    }
                }
            },
            "progress": {
                "discord": {
                    "auto_generate_messages": True
                }
            }
        }
        
        # 應該不拋出異常
        AppConfig._validate_config(config_data)
    
    def test_full_config_validation_with_invalid_max_tokens(self):
        """測試包含無效 max_output_tokens 的完整配置驗證"""
        config_data = {
            "llm": {
                "models": {
                    "progress_msg": {
                        "model": "gemini-2.0-flash-lite",
                        "temperature": 0.4,
                        "max_output_tokens": -1  # 無效值
                    }
                }
            }
        }
        
        with pytest.raises(ConfigurationError, match="max_output_tokens 必須大於 0"):
            AppConfig._validate_config(config_data)
    
    def test_config_from_dict_with_progress_msg(self):
        """測試從字典創建包含 progress_msg 的配置"""
        config_data = {
            "llm": {
                "models": {
                    "progress_msg": {
                        "model": "gemini-2.0-flash-lite",
                        "temperature": 0.4,
                        "max_output_tokens": 20
                    }
                }
            },
            "progress": {
                "discord": {
                    "auto_generate_messages": True
                }
            }
        }
        
        config = AppConfig.from_dict(config_data)
        
        # 驗證 progress_msg 配置
        assert "progress_msg" in config.llm.models
        progress_model = config.llm.models["progress_msg"]
        assert progress_model.model == "gemini-2.0-flash-lite"
        assert progress_model.temperature == 0.4
        assert progress_model.max_output_tokens == 20
        
        # 驗證 auto_generate_messages 配置
        assert config.progress.discord.auto_generate_messages is True