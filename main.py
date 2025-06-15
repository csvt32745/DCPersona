"""
DCPersona 主程式

Discord Bot 的主要入口點，負責初始化和啟動 Bot。
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

from dotenv import load_dotenv
from discord_bot.client import create_discord_client
from utils.config_loader import load_typed_config
from utils.logger import setup_logger
from schemas.config_types import AppConfig, ConfigurationError
from event_scheduler.scheduler import EventScheduler

load_dotenv()

async def main():
    """
    DCPersona 應用程式主要入口點
    
    Args:
        config: 型別安全的配置實例
    """
    config = load_typed_config()
    
    # 設置日誌
    setup_logger(config)
    logging.info("🚀 DCPersona 應用程式啟動中...")

    # 獲取 Bot Token
    bot_token = config.discord.bot_token
    if not bot_token:
        logging.error("❌ Bot token 未在配置檔案中找到。請在 config.yaml 中新增 'bot_token'。")
        return
    
    # 獲取 Bot Token
    bot_token = config.discord.bot_token
    if not bot_token:
        logging.error("❌ Bot token 未在配置檔案中找到。請在 config.yaml 中新增 'bot_token'。")
        return
    
    # 初始化 EventScheduler
    event_scheduler = EventScheduler(data_dir="data")
    await event_scheduler.start()
    logging.info("✅ EventScheduler 已啟動")
    
    discord_client = create_discord_client(config, event_scheduler)
    
    # 啟動 Discord Bot
    logging.info("🔗 正在連接到 Discord...")
    try:
        await discord_client.start(bot_token)
    except Exception as e:
        logging.exception(f"❌ 啟動 Discord bot 失敗: {e}")
    finally:
        # 清理資源
        logging.info("🧹 正在清理連線...")
        await event_scheduler.shutdown()
        logging.info("✅ EventScheduler 已關閉")
        
    if hasattr(discord_client, 'get_handler_stats'):
        stats = discord_client.get_handler_stats()
        logging.info(f"📊 處理統計: 處理訊息 {stats.get('messages_processed', 0)} 條，"
                    f"錯誤 {stats.get('errors_occurred', 0)} 次")
        
    logging.info("✅ DCPersona 已成功關閉")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("👋 用戶中斷，正在退出...")
    except Exception as e:
        logging.error(f"❌ 程式異常退出: {e}", exc_info=True)
        sys.exit(1)