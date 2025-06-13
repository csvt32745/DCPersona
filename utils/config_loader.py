"""
配置載入器

負責載入和管理系統配置，支援多種配置來源、型別安全和快取機制。
向下相容原有的字典格式配置，同時支援新的型別安全 dataclass 配置。
"""

import yaml
import logging
import os
from typing import Dict, Any, Optional, Union
from pathlib import Path
from copy import deepcopy

# 延遲導入以避免循環依賴
_AppConfig = None
_AgentConfig = None
_DiscordConfig = None


def _get_config_types():
    """延遲導入配置類型以避免循環依賴"""
    global _AppConfig, _AgentConfig, _DiscordConfig
    
    if _AppConfig is None:
        try:
            from schemas.config_types import AppConfig, AgentConfig, DiscordConfig
            _AppConfig = AppConfig
            _AgentConfig = AgentConfig
            _DiscordConfig = DiscordConfig
        except ImportError:
            logging.warning("無法導入新的配置類型，僅支援舊格式")
    
    return _AppConfig, _AgentConfig, _DiscordConfig


# 全域配置快取
_config_cache: Optional[Any] = None
_legacy_config_cache: Optional[Dict[str, Any]] = None
_config_path_cache: Optional[str] = None


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """深度合併兩個字典，override 中的值會覆蓋 base 中的值。"""
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_config(filename: str = "config.yaml") -> Dict[str, Any]:
    """載入配置檔案（向後相容版本）
    
    為了保持向後相容性，仍返回字典格式。
    如需型別安全配置，請使用 load_typed_config()。
    
    Args:
        filename: 配置檔案路徑
        
    Returns:
        Dict[str, Any]: 配置字典
    """
    global _legacy_config_cache, _config_path_cache
    
    # 檢查快取
    if (_legacy_config_cache is not None and 
        _config_path_cache == filename):
        return _legacy_config_cache
    
    try:
        # 取得配置資料夾
        config_dir = os.path.dirname(os.path.abspath(filename)) or "."
        example_path = os.path.join(config_dir, "config-example.yaml")

        default_cfg: Dict[str, Any] = {}
        if os.path.exists(example_path):
            try:
                with open(example_path, "r", encoding="utf-8") as f:
                    default_cfg = yaml.safe_load(f) or {}
                logging.debug("Loaded default config from %s", example_path)
            except Exception as e:
                logging.warning("Failed to load default config: %s", e)

        override_cfg: Dict[str, Any] = {}
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    override_cfg = yaml.safe_load(f) or {}
                logging.debug("Loaded override config from %s", filename)
            except Exception as e:
                logging.error("Failed to load override config: %s", e)
                if default_cfg:
                    return default_cfg
                raise
        else:
            logging.info("Override config not found, use default only if present")

        if not default_cfg and not override_cfg:
            raise FileNotFoundError("No configuration files found")
        if not default_cfg:
            config = override_cfg
        elif not override_cfg:
            config = default_cfg
        else:
            config = _deep_merge(default_cfg, override_cfg)
        
        # 快取配置
        _legacy_config_cache = config
        _config_path_cache = filename
        
        logging.info(f"配置載入成功: {filename}")
        return config
        
    except Exception as e:
        logging.error(f"載入配置失敗: {e}")
        return {}


def load_typed_config(config_path: str = "config.yaml", force_reload: bool = False):
    """載入型別安全的配置
    
    Args:
        config_path: 配置檔案路徑
        force_reload: 是否強制重新載入
        
    Returns:
        AppConfig: 型別安全的配置實例，如果無法載入新格式則返回 None
    """
    global _config_cache, _config_path_cache
    
    AppConfig, _, _ = _get_config_types()
    if AppConfig is None:
        logging.warning("新配置類型不可用，請使用 load_config() 獲取字典格式配置")
        return None
    
    # 檢查快取
    if (not force_reload and 
        _config_cache is not None and 
        _config_path_cache == config_path):
        return _config_cache
    
    try:
        config_file = Path(config_path)
        
        if not config_file.exists():
            logging.warning(f"配置檔案不存在: {config_path}，使用預設配置")
            _config_cache = AppConfig()
            _config_path_cache = config_path
            return _config_cache
        
        # 先載入原始字典格式
        config_dict = load_config(config_path)
        
        # 轉換為型別安全格式
        config = AppConfig.from_dict(config_dict)
        
        # 快取配置
        _config_cache = config
        _config_path_cache = config_path
        
        logging.info(f"型別安全配置載入成功: {config_path}")
        return config
        
    except Exception as e:
        logging.error(f"載入型別安全配置失敗: {e}，使用預設配置")
        _config_cache = AppConfig()
        _config_path_cache = config_path
        return _config_cache


def get_agent_config(config_path: str = "config.yaml"):
    """快速獲取 Agent 配置
    
    Args:
        config_path: 配置檔案路徑
        
    Returns:
        AgentConfig: Agent 配置，如果無法載入則返回 None
    """
    app_config = load_typed_config(config_path)
    return app_config.agent if app_config else None


def get_discord_config(config_path: str = "config.yaml"):
    """快速獲取 Discord 配置
    
    Args:
        config_path: 配置檔案路徑
        
    Returns:
        DiscordConfig: Discord 配置，如果無法載入則返回 None
    """
    app_config = load_typed_config(config_path)
    return app_config.discord if app_config else None


def is_tool_enabled(tool_name: str, config_path: str = "config.yaml") -> bool:
    """快速檢查工具是否啟用
    
    Args:
        tool_name: 工具名稱
        config_path: 配置檔案路徑
        
    Returns:
        bool: 是否啟用
    """
    app_config = load_typed_config(config_path)
    if app_config:
        return app_config.is_tool_enabled(tool_name)
    
    # 回退到字典格式
    config = load_config(config_path)
    return config.get("agent", {}).get("tools", {}).get(tool_name, {}).get("enabled", False)


def get_enabled_tools(config_path: str = "config.yaml") -> list[str]:
    """獲取啟用的工具列表
    
    Args:
        config_path: 配置檔案路徑
        
    Returns:
        List[str]: 啟用的工具列表，按優先級排序
    """
    app_config = load_typed_config(config_path)
    if app_config:
        return app_config.get_enabled_tools()
    
    # 回退到字典格式
    config = load_config(config_path)
    tools = config.get("agent", {}).get("tools", {})
    enabled_tools = []
    
    for tool_name, tool_config in tools.items():
        if tool_config.get("enabled", False):
            priority = tool_config.get("priority", 999)
            enabled_tools.append((tool_name, priority))
    
    # 按優先級排序
    enabled_tools.sort(key=lambda x: x[1])
    return [tool_name for tool_name, _ in enabled_tools]


def reload_config(filename: str = "config.yaml") -> Dict[str, Any]:
    """重新載入配置（向後相容）"""
    clear_config_cache()
    return load_config(filename)


def clear_config_cache():
    """清除配置快取"""
    global _config_cache, _legacy_config_cache, _config_path_cache
    _config_cache = None
    _legacy_config_cache = None
    _config_path_cache = None


# 向後相容性別名
def get_config_value(key_path: str, default: Any = None, config_path: str = "config.yaml") -> Any:
    """獲取配置值，支援點記法路徑（向後相容）
    
    Args:
        key_path: 配置鍵路徑，如 "agent.behavior.max_tool_rounds"
        default: 預設值
        config_path: 配置檔案路徑
        
    Returns:
        Any: 配置值
    """
    config = load_config(config_path)
    
    keys = key_path.split('.')
    value = config
    
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    
    return value 