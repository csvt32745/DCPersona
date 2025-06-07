import asyncio
import logging
import httpx

from core.config import load_config
from core.logger import setup_logger
from discordbot.client import create_discord_client
from discordbot.message_handler import register_handlers

async def main():
    """
    Main entry point for the llmcord application.
    Initializes components and starts the Discord bot.
    """
    # Load configuration
    cfg = load_config()
    
    # Setup logger
    setup_logger(cfg)
    logging.info("🚀 llmcord 應用程式啟動中...")
    
    # Create Discord client
    discord_client = create_discord_client(cfg)
    logging.info("📱 Discord 客戶端已建立")
    
    # Register message handlers
    register_handlers(discord_client, cfg)
    logging.info("🎯 訊息處理程序已註冊")
    
    # Start the Discord bot
    logging.info("🔗 正在連接到 Discord...")
    try:
        await discord_client.start(cfg["bot_token"])
    except KeyError:
        logging.error("❌ Bot token 未在配置檔案中找到。請在 config.yaml 中新增 'bot_token'。")
    except Exception as e:
        logging.exception(f"❌ 啟動 Discord bot 失敗: {e}")
    finally:
        # Close any open connections
        logging.info("🧹 正在清理連線...")
        await httpx.AsyncClient().aclose()
        logging.info("✅ 應用程式已安全關閉")

if __name__ == "__main__":
    asyncio.run(main())