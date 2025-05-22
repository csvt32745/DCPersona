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
    
    # Create Discord client
    discord_client = create_discord_client(cfg)
    
    # Register message handlers
    register_handlers(discord_client, cfg)
    
    # Start the Discord bot
    logging.info("Starting Discord bot...")
    try:
        await discord_client.start(cfg["bot_token"])
    except KeyError:
        logging.error("Bot token not found in config file. Please add 'bot_token' to config.yaml.")
    except Exception as e:
        logging.exception(f"Failed to start Discord bot: {e}")
    finally:
        # Close any open connections
        await httpx.AsyncClient().aclose()

if __name__ == "__main__":
    asyncio.run(main())