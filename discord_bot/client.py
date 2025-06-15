"""
Discord 客戶端

創建和配置 Discord 客戶端實例，支援新的統一 Agent 架構。
"""

import discord
import logging
from typing import Dict, Any, Optional

from utils.config_loader import load_config, load_typed_config
from .message_handler import get_message_handler
from schemas.config_types import AppConfig
from event_scheduler.scheduler import EventScheduler


def create_discord_client(config: Optional[AppConfig] = None, event_scheduler: Optional[EventScheduler] = None) -> discord.Client:
    """
    創建和配置 Discord 客戶端實例
    
    Args:
        config: 型別安全的配置實例
        event_scheduler: 事件排程器實例
        
    Returns:
        discord.Client: 配置好的 Discord 客戶端實例
    """
    if config is None:
        config = load_typed_config()
    
    # 設定 Discord 意圖
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.guild_messages = True
    # 檢查是否支援 direct_messages 屬性
    if hasattr(intents, 'direct_messages'):
        intents.direct_messages = True
    elif hasattr(intents, 'dm_messages'):
        intents.dm_messages = True
    
    # 設定狀態訊息
    status_message = config.discord.status_message
    
    # 創建 Discord 客戶端
    discord_client = discord.Client(intents=intents)
    
    # 記錄客戶端 ID 以供邀請 URL
    client_id = config.discord.client_id
    
    if client_id:
        invite_url = f"https://discord.com/api/oauth2/authorize?client_id={client_id}&permissions=2048&scope=bot"
        logging.info(f"\n\n🔗 BOT 邀請連結:\n{invite_url}\n")
    
    # 創建訊息處理器，並將 event_scheduler 傳遞給它
    message_handler = get_message_handler(config, event_scheduler)
    
    # 統計數據
    _handler_stats = {
        "messages_processed": 0,
        "errors_occurred": 0,
        "start_time": None
    }
    
    @discord_client.event
    async def on_ready():
        """Discord 客戶端就緒事件"""
        import time
        _handler_stats["start_time"] = time.time()
        
        logging.info(f"🤖 Discord Bot 已連線: {discord_client.user}")
        logging.info(f"📊 伺服器數量: {len(discord_client.guilds)}")
        
        # 設定 discord_client 到 message_handler
        message_handler.set_discord_client(discord_client)
        
        # 記錄配置資訊
        typed_config = load_typed_config()
        if typed_config and typed_config.agent:
            enabled_tools = typed_config.get_enabled_tools()
            if enabled_tools:
                logging.info(f"🔧 已啟用的工具: {', '.join(enabled_tools)}")
            else:
                logging.info("💬 純對話模式（無工具啟用）")
        
        # 設置 Bot 狀態
        activity = discord.Game(name=status_message)
        await discord_client.change_presence(activity=activity)
        
        logging.info("✅ Discord Bot 已準備就緒！")
    
    @discord_client.event
    async def on_message(message: discord.Message):
        """Discord 訊息事件處理器"""
        try:
            _handler_stats["messages_processed"] += 1
            
            # 使用新的統一訊息處理器
            success = await message_handler.handle_message(message)
            
            if not success:
                _handler_stats["errors_occurred"] += 1
                
        except Exception as e:
            _handler_stats["errors_occurred"] += 1
            logging.error(f"訊息處理器發生未捕獲的錯誤: {e}", exc_info=True)
            
            # 發送錯誤回覆（如果可能）
            try:
                if not message.author.bot:
                    await message.reply("抱歉，處理您的訊息時發生了內部錯誤。請稍後再試。")
            except Exception as reply_error:
                logging.error(f"發送錯誤回覆失敗: {reply_error}")
    
    @discord_client.event
    async def on_error(event: str, *args, **kwargs):
        """Discord 客戶端錯誤事件處理器"""
        _handler_stats["errors_occurred"] += 1
        logging.error(f"Discord 客戶端錯誤: {event}", exc_info=True)
    
    # 添加統計訊息存取函數
    def get_handler_stats() -> Dict[str, Any]:
        """獲取處理器統計資訊"""
        stats = _handler_stats.copy()
        if stats["start_time"]:
            import time
            stats["uptime_seconds"] = time.time() - stats["start_time"]
        return stats
    
    # 將統計函數附加到客戶端，方便存取
    discord_client.get_handler_stats = get_handler_stats
    
    # 將訊息處理器附加到客戶端以便外部存取
    discord_client.message_handler = message_handler
    
    logging.info("🎯 Discord 事件處理器已註冊")
    
    return discord_client
