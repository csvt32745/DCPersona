"""
Emoji 處理器

統一的 EmojiHandler 類別，負責載入、驗證和格式化 Discord Bot 的 emoji 功能。
實現配置驅動、非同步預先驗證和快速同步處理的設計模式。
"""

import discord
import logging
import re
from typing import Dict, Optional, List, Tuple
from pathlib import Path

from schemas.emoji_types import EmojiConfig


class EmojiHandler:
    """
    統一的 Emoji 處理器
    
    負責載入配置、驗證 emoji 可用性、生成提示上下文和格式化輸出。
    """
    
    def __init__(self, config_path: str = "emoji_config.yaml"):
        """
        初始化 EmojiHandler
        
        Args:
            config_path: emoji 配置檔案路徑
        """
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path
        
        # 載入靜態配置
        try:
            self.config = EmojiConfig.from_yaml(config_path)
        except Exception as e:
            self.logger.error(f"載入 emoji 配置失敗: {e}")
            self.config = EmojiConfig(application={}, guilds={})
        
        # 快取字典：儲存驗證後的 emoji 物件和格式化字串
        # 使用 -1 作為 application emoji 的 key
        self.available_emojis: Dict[int, Dict[int, discord.Emoji]] = {}
        self.emoji_lookup: Dict[int, Dict[int, str]] = {}  # {guild_id: {emoji_id: formatted_string}}
        
        self.logger.info(f"EmojiHandler 已初始化，配置路徑: {config_path}")
    
    async def load_emojis(self, client: discord.Client) -> None:
        """
        載入和驗證所有 emoji（僅在 Bot 啟動時呼叫一次）
        
        Args:
            client: Discord 客戶端實例
        """
        self.logger.info("開始載入和驗證 emoji...")
        
        # 清空快取
        self.available_emojis.clear()
        self.emoji_lookup.clear()
        
        # 載入應用程式 emoji
        await self._load_application_emojis(client)
        
        # 載入伺服器 emoji
        await self._load_guild_emojis(client)
        
        self.logger.info("Emoji 載入和驗證完成")
    
    async def _load_application_emojis(self, client: discord.Client) -> None:
        """載入應用程式 emoji"""
        try:
            app_emojis = await client.fetch_application_emojis()
            self.available_emojis[-1] = {}
            self.emoji_lookup[-1] = {}
            
            valid_count = 0
            for emoji in app_emojis:
                if emoji.id in self.config.application:
                    self.available_emojis[-1][emoji.id] = emoji
                    self.emoji_lookup[-1][emoji.id] = str(emoji)
                    valid_count += 1
            
            self.logger.info(f"已載入 {valid_count} 個應用程式 emoji")
            
        except Exception as e:
            self.logger.error(f"載入應用程式 emoji 失敗: {e}")
            self.available_emojis[-1] = {}
            self.emoji_lookup[-1] = {}
    
    async def _load_guild_emojis(self, client: discord.Client) -> None:
        """載入伺服器 emoji"""
        for guild in client.guilds:
            guild_id = guild.id
            
            # 檢查配置中是否有此伺服器的 emoji 設定
            if guild_id not in self.config.guilds:
                continue
            
            try:
                guild_emojis = await guild.fetch_emojis()
                self.available_emojis[guild_id] = {}
                self.emoji_lookup[guild_id] = {}
                
                guild_config = self.config.guilds.get(guild_id, {})
                valid_count = 0
                
                for emoji in guild_emojis:
                    if emoji.id in guild_config:
                        self.available_emojis[guild_id][emoji.id] = emoji
                        self.emoji_lookup[guild_id][emoji.id] = str(emoji)
                        valid_count += 1
                
                self.logger.info(f"已載入伺服器 {guild.name} ({guild_id}) 的 {valid_count} 個 emoji")
                
            except Exception as e:
                self.logger.warning(f"載入伺服器 {guild.name} ({guild_id}) 的 emoji 失敗: {e}")
                self.available_emojis[guild_id] = {}
                self.emoji_lookup[guild_id] = {}
    
    def build_prompt_context(self, guild_id: Optional[int] = None) -> str:
        """
        生成提供給 LLM 的 emoji 提示上下文
        
        Args:
            guild_id: 可選的伺服器 ID
            
        Returns:
            str: 格式化的提示上下文
        """
        if not self.config.application and not self.config.guilds:
            return ""
        
        context_parts = []
        
        # 應用程式 emoji
        app_emojis = self.available_emojis.get(-1, {})
        if app_emojis:
            context_parts.append("**可用的應用程式 Emoji:**")
            for emoji_id, emoji in app_emojis.items():
                description = self.config.application.get(emoji_id, "")
                context_parts.append(f"- {str(emoji)} - {description}")
        
        # 伺服器 emoji
        if guild_id is not None:
            guild_emojis = self.available_emojis.get(guild_id, {})
            if guild_emojis:
                context_parts.append(f"**當前伺服器可用的 Emoji:**")
                for emoji_id, emoji in guild_emojis.items():
                    guild_config = self.config.guilds.get(guild_id, {})
                    description = guild_config.get(emoji_id, "")
                    context_parts.append(f"- {str(emoji)} - {description}")
        
        if not context_parts:
            return ""
        
        context = "\n".join(context_parts)
        return f"""
Emoji 使用說明：
{context}

請在回應中適當使用這些 emoji 來增加表達的生動性。直接使用 emoji 格式即可。
例如：<:thinking:123456789012345678> 讓我想想... <:happy:123456789012345679>
"""
    
    
    
    
    def get_stats(self) -> Dict[str, int]:
        """
        獲取 emoji 載入統計資訊
        
        Returns:
            Dict[str, int]: 統計資訊
        """
        app_count = len(self.available_emojis.get(-1, {}))
        guild_count = sum(
            len(emojis) for key, emojis in self.available_emojis.items() 
            if key != -1
        )
        
        return {
            "application_emojis": app_count,
            "guild_emojis": guild_count,
            "total_emojis": app_count + guild_count,
            "configured_guilds": len([k for k in self.available_emojis.keys() if k != -1])
        }