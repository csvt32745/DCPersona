"""
Discord 客戶端

創建和配置 Discord 客戶端實例，支援新的統一 Agent 架構。
"""

import discord
import logging
from typing import Dict, Any, Optional

from utils.config_loader import load_config, load_typed_config
from .message_handler import get_message_handler


def create_discord_client(cfg: Optional[Dict[str, Any]] = None) -> discord.Client:
    """
    創建和配置 Discord 客戶端實例
    
    Args:
        cfg: 配置字典，如果為 None 則載入預設配置
        
    Returns:
        discord.Client: 配置好的 Discord 客戶端實例
    """
    if cfg is None:
        cfg = load_config()
    
    # 設定 Discord 意圖
    intents = discord.Intents.default()
    intents.message_content = True
    
    # 設定狀態訊息
    status_message = cfg.get("status_message", "AI Assistant")
    if isinstance(cfg.get("discord"), dict):
        status_message = cfg["discord"].get("status_message", status_message)
    
    activity = discord.CustomActivity(name=status_message[:128])
    
    # 創建 Discord 客戶端
    discord_client = discord.Client(intents=intents, activity=activity)
    
    # 記錄客戶端 ID 以供邀請 URL
    client_id = cfg.get("client_id")
    if isinstance(cfg.get("discord"), dict):
        client_id = cfg["discord"].get("client_id", client_id)
    
    if client_id:
        invite_url = f"https://discord.com/api/oauth2/authorize?client_id={client_id}&permissions=412317273088&scope=bot"
        logging.info(f"\n\n🔗 BOT 邀請連結:\n{invite_url}\n")
    
    return discord_client


def register_handlers(discord_client: discord.Client, cfg: Optional[Dict[str, Any]] = None):
    """
    註冊 Discord 事件處理器
    
    Args:
        discord_client: Discord 客戶端實例
        cfg: 配置字典，如果為 None 則載入預設配置
    """
    if cfg is None:
        cfg = load_config()
    
    # 獲取訊息處理器
    message_handler = get_message_handler(cfg)
    
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
        
        # 記錄配置資訊
        typed_config = load_typed_config()
        if typed_config and typed_config.agent:
            enabled_tools = typed_config.get_enabled_tools()
            if enabled_tools:
                logging.info(f"🔧 已啟用的工具: {', '.join(enabled_tools)}")
            else:
                logging.info("💬 純對話模式（無工具啟用）")
        
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
    
    logging.info("🎯 Discord 事件處理器已註冊")


# 便利函數，提供與 main.py 一致的介面
def create_and_register_discord_bot(cfg: Optional[Dict[str, Any]] = None) -> discord.Client:
    """
    創建並註冊 Discord Bot 的便利函數
    
    Args:
        cfg: 配置字典，如果為 None 則載入預設配置
        
    Returns:
        discord.Client: 已註冊處理器的 Discord 客戶端
    """
    if cfg is None:
        cfg = load_config()
    
    # 創建客戶端
    client = create_discord_client(cfg)
    
    # 註冊處理器
    register_handlers(client, cfg)
    
    return client 