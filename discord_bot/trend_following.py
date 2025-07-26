"""
跟風功能處理器

實現 Discord 機器人的跟風功能，包括 reaction 跟風、內容跟風和 emoji 跟風。
使用輕量級的方式讀取訊息歷史，避免複雜的 agent 架構。
"""

import discord
import logging
import re
import time
import random
import asyncio
from typing import Optional, List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI

from schemas.config_types import TrendFollowingConfig
from output_media.emoji_registry import EmojiRegistry


class TrendFollowingHandler:
    """跟風功能處理器
    
    負責處理三種跟風模式：
    1. Reaction 跟風：當某個 reaction 達到閾值時自動添加相同 reaction
    2. Content 跟風：檢測連續相同內容並複製（優先級較高）
    3. Emoji 跟風：檢測連續 emoji 訊息並用 LLM 生成適合回應
    """
    
    def __init__(self, config: TrendFollowingConfig, llm: Optional[ChatGoogleGenerativeAI] = None, 
                 emoji_registry: Optional[EmojiRegistry] = None):
        """初始化跟風處理器
        
        Args:
            config: 跟風功能配置
            llm: LLM 實例，用於 emoji 跟風
            emoji_registry: emoji 註冊器
        """
        self.config = config
        self.llm = llm
        self.emoji_registry = emoji_registry
        self.logger = logging.getLogger(__name__)
        
        # 冷卻時間追蹤：{channel_id: last_response_time}
        self.last_response_times: Dict[int, float] = {}
        
        # 頻道鎖機制：防止併發處理導致重複發送
        self.channel_locks: Dict[int, asyncio.Lock] = {}
        
        # emoji 格式正則表達式：匹配 <:name:id> 或 <a:name:id>
        self.emoji_pattern = re.compile(r'<a?:[^:]+:\d+>')
        
        self.logger.info("跟風功能處理器已初始化")
    
    def get_channel_lock(self, channel_id: int) -> asyncio.Lock:
        """獲取指定頻道的鎖
        
        Args:
            channel_id: 頻道 ID
            
        Returns:
            asyncio.Lock: 頻道專用的異步鎖
        """
        if channel_id not in self.channel_locks:
            self.channel_locks[channel_id] = asyncio.Lock()
        return self.channel_locks[channel_id]
    
    def is_enabled_in_channel(self, channel_id: int) -> bool:
        """檢查跟風功能是否在指定頻道啟用
        
        Args:
            channel_id: 頻道 ID
            
        Returns:
            bool: 是否啟用
        """
        if not self.config.enabled:
            return False
        
        # 如果允許頻道列表為空，表示所有頻道都允許
        if not self.config.allowed_channels:
            return True
        
        return channel_id in self.config.allowed_channels
    
    def is_in_cooldown(self, channel_id: int) -> bool:
        """檢查頻道是否在冷卻時間內
        
        Args:
            channel_id: 頻道 ID
            
        Returns:
            bool: 是否在冷卻中
        """
        if channel_id not in self.last_response_times:
            return False
        
        time_passed = time.time() - self.last_response_times[channel_id]
        return time_passed < self.config.cooldown_seconds
    
    def update_cooldown(self, channel_id: int) -> None:
        """更新頻道的冷卻時間
        
        Args:
            channel_id: 頻道 ID
        """
        self.last_response_times[channel_id] = time.time()
    
    async def handle_raw_reaction_following(self, payload: discord.RawReactionActionEvent, bot: discord.Client) -> bool:
        """處理 raw reaction 跟風
        
        Args:
            payload: Discord raw reaction event payload
            bot: Discord bot 實例
            
        Returns:
            bool: 是否執行了跟風動作
        """
        channel_id = payload.channel_id
        
        # 檢查是否啟用和在冷卻中
        if not self.is_enabled_in_channel(channel_id) or self.is_in_cooldown(channel_id):
            return False
        
        # 避免機器人自己觸發
        if payload.user_id == bot.user.id:
            return False
        
        # 使用頻道鎖防止併發處理
        lock = self.get_channel_lock(channel_id)
        try:
            # 嘗試立即獲取鎖，如果無法獲取則跳過（避免阻塞）
            await asyncio.wait_for(lock.acquire(), timeout=0.1)
            try:
                return await self._do_reaction_following_logic(payload, bot)
            finally:
                lock.release()
                    
        except asyncio.TimeoutError:
            # 如果無法立即獲得鎖，說明有其他操作在進行，直接跳過
            self.logger.debug(f"Reaction 跟風處理跳過：頻道 {channel_id} 正在處理中")
            return False
        except Exception as e:
            self.logger.error(f"Reaction 跟風處理失敗: {e}", exc_info=True)
            return False
    
    async def _do_reaction_following_logic(self, payload: discord.RawReactionActionEvent, bot: discord.Client) -> bool:
        """執行實際的 reaction 跟風邏輯（在鎖保護下）
        
        Args:
            payload: Discord raw reaction event payload
            bot: Discord bot 實例
            
        Returns:
            bool: 是否執行了跟風動作
        """
        try:
            # 獲取頻道和訊息
            channel = bot.get_channel(payload.channel_id)
            if not channel:
                return False
            
            try:
                message = await channel.fetch_message(payload.message_id)
            except discord.NotFound:
                return False
            
            # 找到對應的 reaction
            target_reaction = None
            for reaction in message.reactions:
                if str(reaction.emoji) == str(payload.emoji):
                    target_reaction = reaction
                    break
            
            if not target_reaction:
                return False
            
            # 檢查 reaction 數量是否達到閾值
            if target_reaction.count < self.config.reaction_threshold:
                return False
            
            # 檢查機器人是否已經添加過這個 reaction
            async for reaction_user in target_reaction.users():
                if reaction_user.id == bot.user.id:
                    return False  # 機器人已經添加過了
            
            # 添加相同的 reaction
            await message.add_reaction(payload.emoji)
            self.update_cooldown(payload.channel_id)
            
            self.logger.info(f"執行 reaction 跟風: {payload.emoji} 在頻道 {payload.channel_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Reaction 跟風邏輯執行失敗: {e}", exc_info=True)
            return False
    
    async def handle_message_following(self, message: discord.Message, bot: discord.Client) -> bool:
        """處理訊息跟風（包括內容跟風和 emoji 跟風）
        
        Args:
            message: Discord 訊息物件
            bot: Discord bot 實例
            
        Returns:
            bool: 是否執行了跟風動作
        """
        channel_id = message.channel.id
        
        # 檢查是否啟用和在冷卻中
        if not self.is_enabled_in_channel(channel_id) or self.is_in_cooldown(channel_id):
            return False
        
        # 避免機器人自己觸發
        if message.author.bot or message.author.id == bot.user.id:
            return False
        
        # 使用頻道鎖防止併發處理
        lock = self.get_channel_lock(channel_id)
        try:
            # 嘗試立即獲取鎖，如果無法獲取則跳過（避免阻塞）
            await asyncio.wait_for(lock.acquire(), timeout=0.1)
            try:
                return await self._do_following_logic(message, bot)
            finally:
                lock.release()
                    
        except asyncio.TimeoutError:
            # 如果無法立即獲得鎖，說明有其他操作在進行，直接跳過
            self.logger.debug(f"跟風處理跳過：頻道 {channel_id} 正在處理中")
            return False
        except Exception as e:
            self.logger.error(f"訊息跟風處理失敗: {e}", exc_info=True)
            return False
    
    async def _do_following_logic(self, message: discord.Message, bot: discord.Client) -> bool:
        """執行實際的跟風邏輯（在鎖保護下）
        
        Args:
            message: Discord 訊息物件
            bot: Discord bot 實例
            
        Returns:
            bool: 是否執行了跟風動作
        """
        try:
            # 獲取訊息歷史（包含機器人訊息用於分析）
            history = await self._get_recent_messages(message.channel, bot.user.id)
            if len(history) < 1:  # 至少需要 1 條歷史訊息才能判斷
                return False
            
            # 優先級 1：內容跟風
            if await self._try_content_following(message, history, bot.user.id):
                return True
            
            # 優先級 2：emoji 跟風
            if await self._try_emoji_following(message, history, bot.user.id):
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"跟風邏輯執行失敗: {e}", exc_info=True)
            return False
    
    async def _get_recent_messages(self, channel: discord.TextChannel, bot_user_id: int) -> List[dict]:
        """獲取最近的訊息內容和元數據
        
        Args:
            channel: Discord 頻道
            bot_user_id: 機器人的用戶 ID
            
        Returns:
            List[dict]: 最近的訊息列表，包含內容、sticker 和是否為機器人訊息的資訊
        """
        try:
            messages = []
            async for msg in channel.history(limit=self.config.message_history_limit + 1):
                # 獲取訊息的實際內容（文字或 sticker）
                content_type, content_value = self._get_message_content(msg)
                
                if content_type:  # 只要有內容（文字或 sticker）就保留
                    messages.append({
                        'content_type': content_type,
                        'content_value': content_value,
                        'is_bot': msg.author.bot or msg.author.id == bot_user_id,
                        'author_id': msg.author.id
                    })
            
            # 移除第一條（當前訊息）並反轉順序（最舊的在前）
            return messages[1:][::-1] if len(messages) > 1 else []
            
        except Exception as e:
            self.logger.error(f"獲取訊息歷史失敗: {e}")
            return []
    
    def _get_message_content(self, message: discord.Message) -> tuple:
        """獲取訊息的實際內容（優先 sticker，其次文字）
        
        Args:
            message: Discord 訊息物件
            
        Returns:
            tuple: (content_type, content_value) 其中：
                   - content_type: "sticker" 或 "text"
                   - content_value: sticker 物件或文字字串
        """
        # 優先處理 sticker
        if message.stickers:
            return ("sticker", message.stickers[0])
        
        # 其次處理文字內容
        text_content = message.content.strip()
        if text_content:
            return ("text", text_content)
        
        return ("", "")
    
    def _extract_valid_content_segment(self, messages: List[dict], target_type: str, target_value) -> tuple:
        """提取有效的內容片段，排除機器人參與
        
        Args:
            messages: 訊息列表（包含元數據）
            target_type: 目標內容類型 ("text" 或 "sticker")
            target_value: 目標內容值（文字字串或 sticker 物件）
            
        Returns:
            tuple: (合法的內容片段, 是否有機器人參與該片段)
        """
        # 從最新訊息開始往回找連續相同內容
        valid_segment = []
        has_bot_in_segment = False
        
        for msg in reversed(messages):  # 從最新開始
            msg_type = msg['content_type']
            msg_value = msg['content_value']
            
            # 比較內容是否相同
            is_same_content = False
            if target_type == "text" and msg_type == "text":
                is_same_content = (msg_value == target_value)
            elif target_type == "sticker" and msg_type == "sticker":
                is_same_content = (msg_value.id == target_value.id)
            
            if is_same_content:
                valid_segment.append((msg_type, msg_value))
                if msg['is_bot']:
                    has_bot_in_segment = True
            else:
                break  # 遇到不同內容就停止
        
        return valid_segment, has_bot_in_segment
    
    def _extract_valid_emoji_segment(self, messages: List[dict]) -> tuple:
        """提取有效的 emoji 片段，排除機器人參與
        
        Args:
            messages: 訊息列表（包含元數據）
            
        Returns:
            tuple: (合法的 emoji 訊息片段, 是否有機器人參與該片段)
        """
        # 從最新訊息開始往回找連續 emoji 訊息
        valid_segment = []
        has_bot_in_segment = False
        
        for msg in reversed(messages):  # 從最新開始
            # 只處理文字類型的訊息，檢查是否只包含 emoji
            if msg['content_type'] == 'text' and self._is_emoji_only_message(msg['content_value']):
                valid_segment.append(msg['content_value'])
                if msg['is_bot']:
                    has_bot_in_segment = True
            else:
                break  # 遇到非 emoji 訊息就停止
        
        return valid_segment, has_bot_in_segment
    
    async def _try_content_following(self, message: discord.Message, history: List[dict], bot_user_id: int) -> bool:
        """嘗試內容跟風
        
        Args:
            message: 當前訊息
            history: 訊息歷史（包含元數據）
            bot_user_id: 機器人用戶 ID
            
        Returns:
            bool: 是否執行了內容跟風
        """
        try:
            # 獲取當前訊息的實際內容（可能是文字或 sticker）
            content_type, content_value = self._get_message_content(message)
            if not content_type:
                return False
            
            # 提取有效的內容片段
            valid_segment, has_bot_in_segment = self._extract_valid_content_segment(history, content_type, content_value)
            
            # 如果機器人已經參與了這個片段，不要跟風
            if has_bot_in_segment:
                content_desc = f"{content_type}:{content_value.id if content_type == 'sticker' else content_value}"
                self.logger.debug(f"內容跟風被阻止：機器人已在片段中參與，內容: '{content_desc}'")
                return False
            
            # 加上當前訊息的計數
            total_count = len(valid_segment) + 1
            
            if total_count >= self.config.content_threshold:
                # 執行內容跟風
                await self._send_content_response(content_type, content_value, message.channel)
                self.update_cooldown(message.channel.id)
                
                content_desc = f"{content_type}:{content_value.id if content_type == 'sticker' else content_value}"
                self.logger.info(f"執行內容跟風: '{content_desc}' 在頻道 {message.channel.id} (片段長度: {total_count})")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"內容跟風處理失敗: {e}")
            return False
    
    async def _send_content_response(self, content_type: str, content_value, channel) -> None:
        """發送內容回應（處理文字或 sticker）
        
        Args:
            content_type: 內容類型 ("text" 或 "sticker")
            content_value: 內容值（文字字串或 sticker 物件）
            channel: 要發送到的頻道
        """
        try:
            if content_type == "sticker":
                # 直接發送 sticker 物件
                await channel.send(stickers=[content_value])
            elif content_type == "text":
                # 發送文字內容
                await channel.send(content_value)
            else:
                # 未知類型
                await channel.send("[未知內容類型]")
                
        except Exception as e:
            self.logger.error(f"發送內容回應失敗: {e}")
            # 備用方案：發送文字說明
            try:
                await channel.send("[內容跟風失敗]")
            except:
                pass  # 如果連備用方案都失敗，就靜默忽略
    
    async def _try_emoji_following(self, message: discord.Message, history: List[dict], bot_user_id: int) -> bool:
        """嘗試 emoji 跟風
        
        Args:
            message: 當前訊息
            history: 訊息歷史（包含元數據）
            bot_user_id: 機器人用戶 ID
            
        Returns:
            bool: 是否執行了 emoji 跟風
        """
        try:
            # 檢查當前訊息是否只包含 emoji（只處理文字類型）
            content_type, content_value = self._get_message_content(message)
            if content_type != "text" or not self._is_emoji_only_message(content_value):
                return False
            
            # 提取有效的 emoji 片段
            valid_segment, has_bot_in_segment = self._extract_valid_emoji_segment(history)
            
            # 如果機器人已經參與了這個片段，不要跟風
            if has_bot_in_segment:
                self.logger.debug(f"Emoji 跟風被阻止：機器人已在片段中參與")
                return False
            
            # 加上當前訊息的計數
            total_count = len(valid_segment) + 1
            
            if total_count >= self.config.emoji_threshold:
                # 執行 emoji 跟風
                response_emoji = await self._generate_emoji_response(message)
                if response_emoji:
                    await message.channel.send(response_emoji)
                    self.update_cooldown(message.channel.id)
                    
                    self.logger.info(f"執行 emoji 跟風: '{response_emoji}' 在頻道 {message.channel.id} (片段長度: {total_count})")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Emoji 跟風處理失敗: {e}")
            return False
    
    def _is_emoji_only_message(self, content: str) -> bool:
        """檢查訊息是否只包含 emoji
        
        Args:
            content: 訊息內容
            
        Returns:
            bool: 是否只包含 emoji
        """
        if not content:
            return False
        
        # 移除所有 emoji 格式，檢查是否還有其他內容
        content_without_emojis = self.emoji_pattern.sub('', content).strip()
        
        # 如果移除 emoji 後還有內容，則不是純 emoji 訊息
        return len(content_without_emojis) == 0 and len(self.emoji_pattern.findall(content)) > 0
    
    async def _generate_emoji_response(self, message: discord.Message) -> Optional[str]:
        """使用 LLM 生成 emoji 回應
        
        Args:
            message: Discord 訊息
            
        Returns:
            Optional[str]: 生成的 emoji 回應
        """
        try:
            if not self.llm or not self.emoji_registry:
                # 如果沒有 LLM 或 emoji 註冊器，隨機選擇一個常見的 emoji
                fallback_emojis = ["😄", "👍", "❤️", "😊", "🎉"]
                return random.choice(fallback_emojis)
            
            # 建立 emoji 上下文
            guild_id = message.guild.id if message.guild else None
            emoji_context = self.emoji_registry.build_prompt_context(guild_id)
            
            if not emoji_context:
                # 如果沒有可用的 emoji 上下文，使用 fallback
                fallback_emojis = ["😄", "👍", "❤️", "😊", "🎉"]
                return random.choice(fallback_emojis)
            
            # 建立 LLM 提示
            prompt = f"""你正在參與一個 Discord 頻道的 emoji 跟風活動。最近有多條訊息都只包含 emoji，現在需要你選擇一個適合的 emoji 來回應。

{emoji_context}

請選擇一個適合的 emoji 回應。只需要回傳 emoji 格式，不要其他文字。
範例回應: <:thinking:123456789012345678>
"""
            
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()
            logging.info(f"Emoji 回應: {content}")
            
            # 驗證回應是否包含有效的 emoji 格式
            emoji_matches = self.emoji_pattern.findall(content)
            if emoji_matches:
                return emoji_matches[0]  # 返回第一個找到的 emoji
            
            # 如果 LLM 回應無效，使用 fallback
            fallback_emojis = ["😄", "👍", "❤️", "😊", "🎉"]
            return random.choice(fallback_emojis)
            
        except Exception as e:
            self.logger.error(f"生成 emoji 回應失敗: {e}")
            # 異常時使用 fallback
            fallback_emojis = ["😄", "👍", "❤️", "😊", "🎉"]
            return random.choice(fallback_emojis)