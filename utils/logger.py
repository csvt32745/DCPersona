import logging
from typing import Dict, Any
from schemas.config_types import AppConfig


def setup_logger(cfg: AppConfig) -> None:
    """根據給定設定初始化 logging 系統。"""
    log_level = getattr(logging, cfg.system.log_level.upper(), logging.INFO)
    log_format = "%(asctime)s %(levelname)s: %(message)s"

    # 移除既有 handler，避免其他套件 (如 discord.py) 影響
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(level=log_level, format=log_format, force=True)

    # 調整 discord logger 水位，減少雜訊
    logging.getLogger("discord").setLevel(logging.WARNING)

    logging.info("Logger initialized → level: %s", logging.getLevelName(log_level)) 