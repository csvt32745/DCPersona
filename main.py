"""
llmcord 主要入口點

使用新的統一 Agent 架構和進度更新系統的 Discord bot 啟動腳本。
"""

import asyncio
import logging
import httpx
from typing import Optional

from utils.config_loader import load_config, load_typed_config
from utils.logger import setup_logger
from discord_bot.client import create_discord_client, register_handlers


async def main(config_path: Optional[str] = None):
    """
    llmcord 應用程式主要入口點
    
    Args:
        config_path: 配置文件路徑，如果為 None 則使用預設配置
    """
    # 載入配置
    if config_path:
        cfg = load_config(config_path)
    else:
        cfg = load_config()
    
    # 設置日誌
    setup_logger(cfg)
    logging.info("🚀 llmcord 應用程式啟動中...")
    
    # 顯示配置資訊
    typed_config = load_typed_config(config_path) if config_path else load_typed_config()
    if typed_config:
        logging.info("📋 配置載入成功")
        
        # 顯示啟用的工具
        enabled_tools = typed_config.get_enabled_tools()
        if enabled_tools:
            logging.info(f"🔧 已啟用工具: {', '.join(enabled_tools)}")
        else:
            logging.info("💬 純對話模式（無工具啟用）")
        
        # 顯示進度設定
        if typed_config.progress and typed_config.progress.discord.enabled:
            logging.info("📈 Discord 進度更新已啟用")
        else:
            logging.info("📈 Discord 進度更新已停用")
    
    # 創建 Discord 客戶端
    discord_client = create_discord_client(cfg)
    logging.info("📱 Discord 客戶端已建立")
    
    # 註冊訊息處理器
    register_handlers(discord_client, cfg)
    logging.info("🎯 訊息處理程序已註冊")
    
    # 獲取 Bot Token（支援新舊配置格式）
    bot_token = cfg.get("bot_token")
    if isinstance(cfg.get("discord"), dict):
        bot_token = cfg["discord"].get("bot_token", bot_token)
    
    if not bot_token:
        logging.error("❌ Bot token 未在配置檔案中找到。請在 config.yaml 中新增 'bot_token'。")
        return
    
    # 啟動 Discord Bot
    logging.info("🔗 正在連接到 Discord...")
    try:
        await discord_client.start(bot_token)
    except Exception as e:
        logging.exception(f"❌ 啟動 Discord bot 失敗: {e}")
    finally:
        # 清理資源
        logging.info("🧹 正在清理連線...")
        
        # 關閉 HTTP 客戶端
        try:
            await httpx.AsyncClient().aclose()
        except:
            pass
        
        # 顯示統計資訊
        if hasattr(discord_client, 'get_handler_stats'):
            stats = discord_client.get_handler_stats()
            logging.info(f"📊 處理統計: 處理訊息 {stats.get('messages_processed', 0)} 條，"
                       f"錯誤 {stats.get('errors_occurred', 0)} 次")
        
        logging.info("✅ 應用程式已安全關閉")


def run_llmcord(config_path: Optional[str] = None):
    """
    運行 llmcord 的便利函數
    
    Args:
        config_path: 配置文件路徑，如果為 None 則使用預設配置
    """
    try:
        asyncio.run(main(config_path))
    except KeyboardInterrupt:
        logging.info("👋 收到中斷信號，正在關閉...")
    except Exception as e:
        logging.exception(f"❌ llmcord 運行失敗: {e}")


if __name__ == "__main__":
    import sys
    
    # 支援命令行指定配置文件
    config_path = None
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        print(f"使用配置文件: {config_path}")
    
    run_llmcord(config_path)