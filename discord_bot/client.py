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

from utils.config_loader import load_config, load_typed_config
from .message_handler import get_message_handler
from schemas.config_types import AppConfig
from event_scheduler.scheduler import EventScheduler

# 導入 Wordle 相關功能
from utils.wordle_service import get_wordle_service, WordleNotFound, WordleAPITimeout, WordleServiceError, safe_wordle_output
from prompt_system.prompts import PromptSystem
from langchain_google_genai import ChatGoogleGenerativeAI


class DCPersonaBot(commands.Bot):
    """自定義 Bot 類，支援 Slash Commands"""
    
    def __init__(self, config: AppConfig, event_scheduler: Optional[EventScheduler] = None):
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
            
        super().__init__(command_prefix='!', intents=intents)
        
        self.config = config
        self.event_scheduler = event_scheduler
        self.logger = logging.getLogger(__name__)
        
        # 初始化服務
        self.wordle_service = get_wordle_service()
        self.prompt_system = PromptSystem()
        
        # 初始化 LLM（用於生成 Wordle 提示）
        self._init_wordle_llm()
        
        # 創建訊息處理器
        self.message_handler = get_message_handler(config, event_scheduler)
        
        # 統計數據
        self._handler_stats = {
            "messages_processed": 0,
            "errors_occurred": 0,
            "start_time": None
        }
    
    def _init_wordle_llm(self):
        """初始化用於 Wordle 提示生成的 LLM"""
        try:
            api_key = self.config.gemini_api_key
            if not api_key:
                self.logger.error("缺少 GEMINI_API_KEY，Wordle 功能將無法使用")
                self.wordle_llm = None
                return
                
            # 使用 final_answer 配置來生成 Wordle 提示
            llm_config = self.config.llm.models.get("final_answer")
            if llm_config:
                self.wordle_llm = ChatGoogleGenerativeAI(
                    model=llm_config.model,
                    temperature=llm_config.temperature,
                    api_key=api_key
                )
                self.logger.info("Wordle LLM 初始化成功")
            else:
                self.logger.warning("找不到 final_answer LLM 配置，使用預設配置")
                self.wordle_llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash-exp",
                    temperature=0.7,
                    api_key=api_key
                )
        except Exception as e:
            self.logger.error(f"初始化 Wordle LLM 失敗: {e}")
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
@app_commands.command(name="wordle_hint", description="獲取 Wordle 遊戲提示")
@app_commands.describe(date="指定日期 (YYYY-MM-DD)，預設為今天")
async def wordle_hint_command(interaction: discord.Interaction, date: Optional[str] = None):
    """
    /wordle_hint Slash Command 處理器
    
    Args:
        interaction: Discord 互動對象
        date: 可選的日期字串，格式為 YYYY-MM-DD
    """
    bot: DCPersonaBot = interaction.client
    logger = logging.getLogger(__name__)
    
    # 延遲回應，因為可能需要時間獲取答案和生成提示
    try:
        if not interaction.response.is_done():
            await interaction.response.defer()
    except discord.errors.HTTPException as http_exc:
        # 忽略已回應 (40060) 或已失效 (10062) 的互動錯誤
        if getattr(http_exc, 'code', None) not in (40060, 10062):
            raise
    
    try:
        # 1. 解析日期
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                await interaction.followup.send("❌ 日期格式錯誤！請使用 YYYY-MM-DD 格式，例如：2024-01-15")
                return
        else:
            # 使用配置中的時區獲取今天的日期
            timezone = bot.config.system.timezone
            tz = pytz.timezone(timezone)
            target_date = datetime.now(tz).date()
        
        logger.info(f"用戶 {interaction.user} 請求 {target_date} 的 Wordle 提示")
        
        # 2. 獲取 Wordle 答案
        try:
            wordle_result = await bot.wordle_service.fetch_solution(target_date)
            solution = wordle_result.solution
            logger.info(f"成功獲取 {target_date} 的 Wordle 答案")
        except WordleNotFound:
            await interaction.followup.send(f"❌ 找不到 {target_date} 的 Wordle 資料，請檢查日期是否正確。")
            return
        except WordleAPITimeout:
            await interaction.followup.send("⏰ 請求超時，請稍後再試。")
            return
        except WordleServiceError as e:
            await interaction.followup.send(f"❌ 服務暫時不可用：{str(e)}")
            return
        
        # 3. 生成提示
        if not bot.wordle_llm:
            await interaction.followup.send("❌ LLM 服務不可用，無法生成提示。")
            return
        
        try:
            # 獲取當前 persona 風格
            persona_style = "友善且有趣"  # 預設風格
            try:
                # 嘗試獲取實際的 persona 內容
                if bot.config.prompt_system.persona.enabled:
                    if bot.config.prompt_system.persona.random_selection:
                        persona_style = bot.prompt_system.random_system_prompt(
                            bot.config.prompt_system.persona.persona_directory
                        )
                    else:
                        persona_style = bot.prompt_system.get_specific_persona(
                            bot.config.prompt_system.persona.default_persona,
                            bot.config.prompt_system.persona.persona_directory
                        )
                    
            except Exception as e:
                logger.warning(f"獲取 persona 風格失敗，使用預設風格: {e}")

            # 1. 取得隨機的提示風格描述
            hint_style_dir = Path("prompt_system/tool_prompts/wordle_hint_types")
            hint_style_description = bot.prompt_system.random_system_prompt(
                hint_style_dir, 
                use_cache=False
            )
            if not hint_style_description:
                logger.error("無法獲取隨機 Wordle 提示風格，流程中止。")
                await interaction.followup.send("❌ 內部錯誤：無法載入提示風格。")
                return

            # 2. 取得主提示詞模板並傳入風格描述
            prompt_template = bot.prompt_system.get_tool_prompt(
                "wordle_hint_instructions",
                solution=solution,
                persona_style=persona_style,
                hint_style_description=hint_style_description
            )
            
            logger.debug(f"Wordle 提示生成提示詞: {prompt_template}")
            
            # 調用 LLM 生成提示
            response = await bot.wordle_llm.ainvoke([{"role": "user", "content": prompt_template}])
            hint_content = response.content

            # 將 <think> 和 <check> 區塊轉為 Discord spoiler
            # <think>...</think> -> ||...||
            hint_content = re.sub(r'<think>(.*?)</think>', r'||\1||', hint_content, flags=re.DOTALL | re.IGNORECASE)

            # <check>...</check> -> 題解:\n|| ... ||
            def _replace_check(match):
                inner = match.group(1).strip()
                return f"題解:\n|| {inner} ||"

            hint_content = re.sub(r'<check>(.*?)</check>', _replace_check, hint_content, flags=re.DOTALL | re.IGNORECASE)
            
            # 4. 安全後處理
            safe_hint = safe_wordle_output(hint_content, solution)
            
            # 5. 發送回應
            await interaction.followup.send(safe_hint)
            
        except Exception as e:
            logger.error(f"生成 Wordle 提示時發生錯誤: {e}")
            await interaction.followup.send("❌ 生成提示時發生錯誤，請稍後再試。")
    
    except Exception as e:
        logger.error(f"Wordle hint 指令處理時發生未預期錯誤: {e}")
        try:
            await interaction.followup.send("❌ 處理指令時發生內部錯誤，請稍後再試。")
        except:
            pass  # 如果連錯誤訊息都發送不了，就忽略


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
    
    # 添加 Slash Commands 到 CommandTree
    bot.tree.add_command(wordle_hint_command)
    
    # 記錄客戶端 ID 以供邀請 URL
    client_id = config.discord.client_id
    
    if client_id:
        invite_url = f"https://discord.com/api/oauth2/authorize?client_id={client_id}&permissions=2048&scope=bot%20applications.commands"
        logging.info(f"\n\n🔗 BOT 邀請連結（包含 Slash Commands）:\n{invite_url}\n")
    
    logging.info("🎯 Discord Bot 和 Slash Commands 已註冊")
    
    return bot
