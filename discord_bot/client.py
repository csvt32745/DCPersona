"""
Discord 客戶端

創建和配置 Discord 客戶端實例，支援新的統一 Agent 架構和 Slash Commands。
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Dict, Any, Optional
from datetime import datetime, date
import pytz
import re
from pathlib import Path

from utils.config_loader import load_typed_config
from .message_handler import get_message_handler
from schemas.config_types import AppConfig
from event_scheduler.scheduler import EventScheduler

# 導入 Wordle 相關功能
from utils.wordle_service import get_wordle_service, WordleNotFound, WordleAPITimeout, WordleServiceError, safe_wordle_output
from prompt_system.prompts import PromptSystem
from output_media.emoji_registry import EmojiRegistry
from langchain_google_genai import ChatGoogleGenerativeAI
from discord_bot.commands import register_commands
from discord_bot.trend_following import TrendFollowingHandler

class DCPersonaBot(commands.Bot):
    """自定義 Bot 類，支援 Slash Commands"""
    
    def __init__(self, config: AppConfig, event_scheduler: Optional[EventScheduler] = None):
        # 設定 Discord 意圖
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        intents.reactions = True  # 啟用 reaction 相關事件
        
        # 檢查是否支援 direct_messages 屬性
        if hasattr(intents, 'direct_messages'):
            intents.direct_messages = True
        elif hasattr(intents, 'dm_messages'):
            intents.dm_messages = True
            
        super().__init__(command_prefix='!', intents=intents)
        
        self.config = config
        self.event_scheduler = event_scheduler
        self.logger = logging.getLogger(__name__)
        
        # 初始化服務
        self.wordle_service = get_wordle_service()
        self.prompt_system = PromptSystem()
        self.emoji_handler = EmojiRegistry()
        
        # 初始化 LLM 實例（smart_llm 和 fast_llm）
        self._init_llm_instances()
        
        # 初始化跟風功能處理器
        self.trend_following_handler = None  # 將在 on_ready 中初始化
        
        # 創建訊息處理器
        self.message_handler = get_message_handler(config, event_scheduler)
        
        # 統計數據
        self._handler_stats = {
            "messages_processed": 0,
            "errors_occurred": 0,
            "start_time": None
        }
    
    def _init_llm_instances(self):
        """初始化 smart_llm 和 fast_llm 實例"""
        api_key = self.config.gemini_api_key
        if not api_key:
            self.logger.error("缺少 GEMINI_API_KEY，LLM 功能將無法使用")
            self.smart_llm = None
            self.fast_llm = None
            self.wordle_llm = None
            return
        
        try:
            # 初始化 smart_llm (基於 final_answer 配置)
            final_answer_config = self.config.llm.models.get("final_answer")
            if final_answer_config:
                self.smart_llm = ChatGoogleGenerativeAI(
                    model=final_answer_config.model,
                    temperature=final_answer_config.temperature,
                    api_key=api_key
                )
                self.logger.info(f"Smart LLM 初始化成功: {final_answer_config.model}")
            else:
                self.logger.warning("找不到 final_answer LLM 配置，smart_llm 使用預設配置")
                self.smart_llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash-exp",
                    temperature=0.7,
                    api_key=api_key
                )
            
            # 初始化 fast_llm (基於 tool_analysis 配置)
            tool_analysis_config = self.config.llm.models.get("tool_analysis")
            if tool_analysis_config:
                self.fast_llm = ChatGoogleGenerativeAI(
                    model=tool_analysis_config.model,
                    temperature=tool_analysis_config.temperature,
                    api_key=api_key
                )
                self.logger.info(f"Fast LLM 初始化成功: {tool_analysis_config.model}")
            else:
                self.logger.warning("找不到 tool_analysis LLM 配置，fast_llm 使用預設配置")
                self.fast_llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash-exp",
                    temperature=0.3,
                    api_key=api_key
                )
            
            # 保持 wordle_llm 向後相容性
            self.wordle_llm = self.smart_llm
            
        except Exception as e:
            self.logger.error(f"初始化 LLM 實例失敗: {e}")
            self.smart_llm = None
            self.fast_llm = None
            self.wordle_llm = None
    
    async def setup_hook(self):
        """Bot 初始化鉤子"""
        # 同步 Slash Commands
        try:
            synced = await self.tree.sync()
            self.logger.info(f"✅ 同步了 {len(synced)} 個 Slash Commands")
        except Exception as e:
            self.logger.error(f"同步 Slash Commands 失敗: {e}")
    
    async def on_ready(self):
        """Discord 客戶端就緒事件"""
        import time
        self._handler_stats["start_time"] = time.time()
        
        self.logger.info(f"🤖 Discord Bot 已連線: {self.user}")
        self.logger.info(f"📊 伺服器數量: {len(self.guilds)}")
        
        # 設定 discord_client 到 message_handler
        self.message_handler.set_discord_client(self)
        
        # 載入 emoji 配置
        try:
            await self.emoji_handler.load_emojis(self)
            stats = self.emoji_handler.get_stats()
            self.logger.info(f"✅ Emoji 系統已載入: {stats['total_emojis']} 個 emoji "
                           f"(應用程式: {stats['application_emojis']}, 伺服器: {stats['guild_emojis']})")
        except Exception as e:
            self.logger.error(f"❌ 載入 emoji 配置失敗: {e}")
        
        # 初始化跟風功能處理器
        try:
            self.trend_following_handler = TrendFollowingHandler(
                config=self.config.trend_following,
                llm=self.fast_llm,
                emoji_registry=self.emoji_handler
            )
            if self.config.trend_following.enabled:
                self.logger.info("✅ 跟風功能已啟用")
            else:
                self.logger.info("ℹ️ 跟風功能已停用")
        except Exception as e:
            self.logger.error(f"❌ 初始化跟風功能失敗: {e}")
            self.trend_following_handler = None
        
        # 記錄配置資訊
        if self.config and self.config.agent:
            enabled_tools = self.config.get_enabled_tools()
            if enabled_tools:
                self.logger.info(f"🔧 已啟用的工具: {', '.join(enabled_tools)}")
            else:
                self.logger.info("💬 純對話模式（無工具啟用）")
        
        # 設置 Bot 狀態
        activity = discord.Game(name=self.config.discord.status_message)
        await self.change_presence(activity=activity)
        
        self.logger.info("✅ Discord Bot 已準備就緒！")
    
    async def on_message(self, message: discord.Message):
        """Discord 訊息事件處理器"""
        try:
            self._handler_stats["messages_processed"] += 1
            
            # 處理跟風功能（在主要訊息處理前）
            if self.trend_following_handler:
                try:
                    if await self.trend_following_handler.handle_message_following(message, self):
                        return
                except Exception as e:
                    self.logger.error(f"跟風功能處理失敗: {e}")
            
            # 使用新的統一訊息處理器
            success = await self.message_handler.handle_message(message)
            
            if not success:
                self._handler_stats["errors_occurred"] += 1
                
        except Exception as e:
            self._handler_stats["errors_occurred"] += 1
            self.logger.error(f"訊息處理器發生未捕獲的錯誤: {e}", exc_info=True)
            
            # 發送錯誤回覆（如果可能）
            try:
                if not message.author.bot:
                    await message.reply("抱歉，處理您的訊息時發生了內部錯誤。請稍後再試。")
            except Exception as reply_error:
                self.logger.error(f"發送錯誤回覆失敗: {reply_error}")

    async def on_reaction_add(self, reaction: discord.Reaction, user):
        """當使用者在訊息上新增 Reaction 時觸發 (受訊息快取限制)"""
        try:
            if user.bot:
                return  # 避免機器人循環觸發
            
            # self.logger.info(
            #     f"🆕 Reaction Add | guild={getattr(reaction.message.guild, 'name', 'DM')} "
            #     f"channel={reaction.message.channel} user={user} emoji={reaction.emoji} "
            #     f"message_id={reaction.message.id}"
            # )
        except Exception as e:
            self.logger.error(f"記錄 on_reaction_add 時發生錯誤: {e}", exc_info=True)

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """當有 Reaction 新增（不受訊息快取限制）"""
        try:
            # 避免機器人自己觸發
            if payload.user_id == self.user.id:
                return
            
            # 處理 reaction 跟風功能
            if self.trend_following_handler:
                try:
                    await self.trend_following_handler.handle_raw_reaction_following(payload, self)
                except Exception as e:
                    self.logger.error(f"Raw Reaction 跟風功能處理失敗: {e}")
            
            # self.logger.info(
            #     f"🆕 RAW Reaction Add | guild_id={payload.guild_id} channel_id={payload.channel_id} "
            #     f"message_id={payload.message_id} user_id={payload.user_id} emoji={payload.emoji}"
            # )
        except Exception as e:
            self.logger.error(f"記錄 on_raw_reaction_add 時發生錯誤: {e}", exc_info=True)
    
    async def on_error(self, event: str, *args, **kwargs):
        """Discord 客戶端錯誤事件處理器"""
        self._handler_stats["errors_occurred"] += 1
        self.logger.error(f"Discord 客戶端錯誤: {event}", exc_info=True)
    
    def get_handler_stats(self) -> Dict[str, Any]:
        """獲取處理器統計資訊"""
        stats = self._handler_stats.copy()
        if stats["start_time"]:
            import time
            stats["uptime_seconds"] = time.time() - stats["start_time"]
        return stats


# Slash Command 實作
def create_discord_client(config: Optional[AppConfig] = None, event_scheduler: Optional[EventScheduler] = None) -> DCPersonaBot:
    """
    創建和配置 Discord 客戶端實例
    
    Args:
        config: 型別安全的配置實例
        event_scheduler: 事件排程器實例
        
    Returns:
        DCPersonaBot: 配置好的 Discord Bot 實例
    """
    if config is None:
        config = load_typed_config()
    
    # 創建 Bot 實例
    bot = DCPersonaBot(config, event_scheduler)
    
    # 集中註冊 Slash Commands
    register_commands(bot)
    
    # 記錄客戶端 ID 以供邀請 URL
    client_id = config.discord.client_id
    
    if client_id:
        invite_url = f"https://discord.com/api/oauth2/authorize?client_id={client_id}&permissions=2048&scope=bot%20applications.commands"
        logging.info(f"\n\n🔗 BOT 邀請連結（包含 Slash Commands）:\n{invite_url}\n")
    
    logging.info("🎯 Discord Bot 和 Slash Commands 已註冊")
    
    return bot
