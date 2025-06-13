"""
LLMCord 主程式

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

load_dotenv()

async def main():
    """
    llmcord 應用程式主要入口點
    
    Args:
        config: 型別安全的配置實例
    """
    config = load_typed_config()
    
    # 設置日誌
    setup_logger(config)
    logging.info("🚀 llmcord 應用程式啟動中...")

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
    
    discord_client = create_discord_client(config)
    
    # 啟動 Discord Bot
    logging.info("🔗 正在連接到 Discord...")
    try:
        await discord_client.start(bot_token)
    except Exception as e:
        logging.exception(f"❌ 啟動 Discord bot 失敗: {e}")
    finally:
        # 清理資源
        logging.info("🧹 正在清理連線...")
        
    if hasattr(discord_client, 'get_handler_stats'):
        stats = discord_client.get_handler_stats()
        logging.info(f"📊 處理統計: 處理訊息 {stats.get('messages_processed', 0)} 條，"
                    f"錯誤 {stats.get('errors_occurred', 0)} 次")
        
    logging.info("✅ LLMCord 已成功關閉")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("👋 用戶中斷，正在退出...")
    except Exception as e:
        logging.error(f"❌ 程式異常退出: {e}", exc_info=True)
        sys.exit(1)