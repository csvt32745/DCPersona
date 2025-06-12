import yaml
import logging
import os
from typing import Dict, Any
from copy import deepcopy


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
    """載入並融合 default(config-example.yaml) 與 override(config.yaml) 設定。"""
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
        return override_cfg
    if not override_cfg:
        return default_cfg

    return _deep_merge(default_cfg, override_cfg)


def reload_config(filename: str = "config.yaml") -> Dict[str, Any]:
    """重新載入配置。"""
    return load_config(filename) 