import yaml
import logging
import os
from typing import Dict, Any
from copy import deepcopy

def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    深度合併兩個字典，override 中的值會覆蓋 base 中的值。
    
    Args:
        base (dict): 基礎配置字典
        override (dict): 覆蓋配置字典
        
    Returns:
        dict: 合併後的配置字典
    """
    result = deepcopy(base)
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # 遞歸合併嵌套字典
            result[key] = _deep_merge(result[key], value)
        else:
            # 直接覆蓋值
            result[key] = deepcopy(value)
    
    return result

def load_config(filename: str = "config.yaml") -> Dict[str, Any]:
    """
    智能融合配置文件，優先載入 config-example.yaml 作為預設，
    然後用 config.yaml 覆蓋相應的配置項。
    
    Args:
        filename (str): 主配置文件路徑 (config.yaml)
        
    Returns:
        dict: 融合後的配置數據
    """
    try:
        # 獲取配置文件目錄
        config_dir = os.path.dirname(os.path.abspath(filename))
        example_config_path = os.path.join(config_dir, "config-example.yaml")
        
        # 載入預設配置 (config-example.yaml)
        default_config = {}
        if os.path.exists(example_config_path):
            try:
                with open(example_config_path, "r", encoding="utf-8") as file:
                    default_config = yaml.safe_load(file) or {}
                logging.info(f"Loaded default config from {example_config_path}")
            except Exception as e:
                logging.warning(f"Failed to load default config from {example_config_path}: {e}")
        else:
            logging.warning(f"Default config file not found: {example_config_path}")
        
        # 載入覆蓋配置 (config.yaml)
        override_config = {}
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as file:
                    override_config = yaml.safe_load(file) or {}
                logging.info(f"Loaded override config from {filename}")
            except Exception as e:
                logging.error(f"Failed to load override config from {filename}: {e}")
                # 如果覆蓋配置載入失敗，至少返回預設配置
                if default_config:
                    logging.info("Using default config only due to override config failure")
                    return default_config
                raise
        else:
            logging.warning(f"Override config file not found: {filename}, using default config only")
        
        # 智能融合配置
        if not default_config and not override_config:
            raise FileNotFoundError(f"Neither default config nor override config found")
        elif not default_config:
            logging.info("Using override config only (no default config)")
            return override_config
        elif not override_config:
            logging.info("Using default config only (no override config)")
            return default_config
        else:
            # 深度合併配置
            merged_config = _deep_merge(default_config, override_config)
            logging.info("Successfully merged default and override configurations")
            return merged_config
            
    except Exception as e:
        logging.error(f"Failed to load and merge configurations: {e}")
        raise

def reload_config(filename: str = "config.yaml") -> Dict[str, Any]:
    """
    重新載入融合後的配置。
    
    Args:
        filename (str): 主配置文件路徑
        
    Returns:
        dict: 刷新後的融合配置數據
    """
    return load_config(filename)
