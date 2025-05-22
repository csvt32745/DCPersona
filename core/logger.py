import logging
from typing import Dict, Any

def setup_logger(cfg: Dict[str, Any]) -> None:
    """
    Sets up the logger based on configuration.
    
    Args:
        cfg (dict): Configuration data containing logger settings.
    """
    log_level = getattr(logging, cfg.get("log_level", "INFO"))
    log_format = cfg.get("log_format", "%(asctime)s %(levelname)s: %(message)s")
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
    )
    
    logging.info("Logger initialized with level: %s", log_level)
