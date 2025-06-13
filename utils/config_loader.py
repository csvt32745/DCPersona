"""
配置載入器

負責載入和管理系統配置，提供型別安全的配置載入功能。
完全移除字典格式支援，強制使用型別安全的 dataclass 配置。
"""

import logging
from typing import Optional
from pathlib import Path

# 導入配置類型
from schemas.config_types import AppConfig, AgentConfig, DiscordConfig, ConfigurationError


# 全域配置快取
_config_cache: Optional[AppConfig] = None
_config_path_cache: Optional[str] = None


def load_typed_config(config_path: str = "config.yaml", force_reload: bool = False) -> AppConfig:
    """載入型別安全配置（唯一入口）
    
    Args:
        config_path: 配置檔案路徑
        force_reload: 是否強制重新載入
        
    Returns:
        AppConfig: 型別安全的配置實例
        
    Raises:
        ConfigurationError: 配置載入失敗時拋出
    """
    global _config_cache, _config_path_cache
    
    # 檢查快取
    if (not force_reload and 
        _config_cache is not None and 
        _config_path_cache == config_path):
        return _config_cache
    
    try:
        # 使用 AppConfig.from_yaml 載入配置
        config = AppConfig.from_yaml(config_path)
        
        # 快取配置
        _config_cache = config
        _config_path_cache = config_path
        
        logging.info(f"型別安全配置載入成功: {config_path}")
        return config
        
    except Exception as e:
        logging.error(f"載入型別安全配置失敗: {e}")
        raise ConfigurationError(f"無法載入配置: {e}")


def get_agent_config(config_path: str = "config.yaml") -> AgentConfig:
    """快速獲取 Agent 配置
    
    Args:
        config_path: 配置檔案路徑
        
    Returns:
        AgentConfig: Agent 配置
    """
    app_config = load_typed_config(config_path)
    return app_config.agent


def get_discord_config(config_path: str = "config.yaml") -> DiscordConfig:
    """快速獲取 Discord 配置
    
    Args:
        config_path: 配置檔案路徑
        
    Returns:
        DiscordConfig: Discord 配置
    """
    app_config = load_typed_config(config_path)
    return app_config.discord


def is_tool_enabled(tool_name: str, config_path: str = "config.yaml") -> bool:
    """快速檢查工具是否啟用
    
    Args:
        tool_name: 工具名稱
        config_path: 配置檔案路徑
        
    Returns:
        bool: 是否啟用
    """
    app_config = load_typed_config(config_path)
    return app_config.is_tool_enabled(tool_name)


def get_enabled_tools(config_path: str = "config.yaml") -> list[str]:
    """獲取啟用的工具列表
    
    Args:
        config_path: 配置檔案路徑
        
    Returns:
        List[str]: 啟用的工具列表，按優先級排序
    """
    app_config = load_typed_config(config_path)
    return app_config.get_enabled_tools()


# 向後相容性別名 - 重定向到型別安全版本
def load_config(filename: str = "config.yaml") -> AppConfig:
    """載入配置（向後相容性別名）
    
    注意：此函數現在返回 AppConfig 實例而非字典。
    請更新代碼使用型別安全的屬性存取方式。
    
    Args:
        filename: 配置檔案路徑
        
    Returns:
        AppConfig: 型別安全的配置實例
    """
    logging.warning("load_config() 已棄用，請使用 load_typed_config() 並更新代碼使用型別安全存取")
    return load_typed_config(filename) 