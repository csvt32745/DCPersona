import yaml
import logging
from typing import Dict, Any

def load_config(filename: str = "config.yaml") -> Dict[str, Any]:
    """
    Reads the configuration file and returns its contents.
    
    Args:
        filename (str): Path to the configuration file.
        
    Returns:
        dict: Configuration data.
    """
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except Exception as e:
        logging.error(f"Failed to load config from {filename}: {e}")
        raise

def reload_config(filename: str = "config.yaml") -> Dict[str, Any]:
    """
    Reloads configuration from the file.
    
    Args:
        filename (str): Path to the configuration file.
        
    Returns:
        dict: Refreshed configuration data.
    """
    return load_config(filename)
