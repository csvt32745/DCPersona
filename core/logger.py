import logging
from typing import Dict, Any

def setup_logger(cfg: Dict[str, Any]) -> None:
    """
    Sets up the logger based on configuration.
    Enhanced to prevent discord.py from overriding logging configuration.
    
    Args:
        cfg (dict): Configuration data containing logger settings.
    """
    log_level = getattr(logging, cfg.get("log_level", "INFO"))
    log_format = cfg.get("log_format", "%(asctime)s %(levelname)s: %(message)s")
    
    # 清除現有的 handlers 以確保完全重新設置
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        force=True,  # 強制覆蓋已有的 handler，防止 discord.py 重設
    )
    
    # 確保 discord.py 的 logger 也使用我們的配置
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.WARNING)  # 減少 discord.py 的冗余日誌
    
    logging.info("🔧 Logger initialized with level: %s", logging.getLevelName(log_level))
    logging.info("📝 Log format: %s", log_format)
    logging.debug("🐛 Debug logging is enabled")
