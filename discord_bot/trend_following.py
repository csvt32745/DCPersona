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
from enum import Enum
from typing import Optional, List, Dict, Any, Set, Tuple
from langchain_google_genai import ChatGoogleGenerativeAI

from schemas.config_types import TrendFollowingConfig
from output_media.emoji_registry import EmojiRegistry


class TrendActivityType(Enum):
    """跟風活動類型"""
    REACTION = "reaction"
    CONTENT = "content"
    EMOJI = "emoji"
    
    @property
    def is_message_based(self) -> bool:
        """是否為訊息類活動 (需要發送訊息)"""
        return self in (TrendActivityType.CONTENT, TrendActivityType.EMOJI)
    


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
        # 分離的鎖機制 - reaction 和 message 可以並行處理
        self.reaction_locks: Dict[int, asyncio.Lock] = {}
        self.message_locks: Dict[int, asyncio.Lock] = {}
        
        # 分離的狀態管理：防止延遲期間重複發送
        self.pending_message_activities: Dict[int, Set[TrendActivityType]] = {}  # CONTENT/EMOJI
        self.pending_reaction_activities: Dict[int, bool] = {}  # REACTION
        
        # emoji 格式正則表達式：匹配 <:name:id> 或 <a:name:id>
        self.emoji_pattern = re.compile(r'<a?:[^:]+:\d+>')
        
        # Unicode emoji 正則表達式：匹配所有 Unicode emoji
        self.unicode_emoji_pattern = re.compile(
            "["
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F700-\U0001F77F"  # alchemical symbols
            "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
            "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA00-\U0001FA6F"  # Chess Symbols
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "\U00002702-\U000027B0"  # Dingbats
            "\U00002190-\U000021FF"  # Arrows
            "\U00002600-\U000026FF"  # Miscellaneous Symbols
            "\U00002700-\U000027BF"  # Dingbats
            "]+"
        )
        
        # 統一的 fallback emoji 列表（支援更多 Unicode emoji）
        self.fallback_emojis = [
            "😄", "👍", "❤️", "😊", "🎉", "😂", "🔥", "💯", 
            "👌", "😍", "🤔", "😅", "🙌", "💪", "🚀", "✨"
        ]
        
        self.logger.info("跟風功能處理器已初始化")
    
    def should_follow_probabilistically(self, count: int, threshold: int) -> bool:
        """機率性跟風決策
        
        Args:
            count: 當前數量（reaction 數、重複次數等）
            threshold: 最低閾值
            
        Returns:
            bool: 是否跟風
        """
        # 如果沒有啟用機率性跟風，使用舊邏輯（硬閾值）
        if not self.config.enable_probabilistic:
            return count >= threshold
        
        # 未達最低閾值時不跟風
        if count < threshold:
            return False
        
        # 計算超出閾值的數量
        excess_count = count - threshold
        
        # 計算機率：基礎機率 + 超出量 * 提升係數
        probability = min(
            self.config.max_probability,
            self.config.base_probability + excess_count * self.config.probability_boost_factor
        )
        
        # 機率決策
        result = random.random() < probability
        
        self.logger.debug(
            f"機率性跟風決策: count={count}, threshold={threshold}, "
            f"excess={excess_count}, probability={probability:.2f}, result={result}"
        )
        
        return result
    
    def get_reaction_lock(self, channel_id: int) -> asyncio.Lock:
        """獲取指定頻道的 reaction 鎖
        
        Args:
            channel_id: 頻道 ID
            
        Returns:
            asyncio.Lock: 頻道 reaction 專用的異步鎖
        """
        if channel_id not in self.reaction_locks:
            self.reaction_locks[channel_id] = asyncio.Lock()
        return self.reaction_locks[channel_id]
    
    def get_message_lock(self, channel_id: int) -> asyncio.Lock:
        """獲取指定頻道的 message 鎖
        
        Args:
            channel_id: 頻道 ID
            
        Returns:
            asyncio.Lock: 頻道 message 專用的異步鎖
        """
        if channel_id not in self.message_locks:
            self.message_locks[channel_id] = asyncio.Lock()
        return self.message_locks[channel_id]
    
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
    
    def _has_pending_message_activity(self, channel_id: int) -> bool:
        """檢查是否有待處理的訊息活動"""
        return channel_id in self.pending_message_activities and bool(self.pending_message_activities[channel_id])
    
    def _has_pending_reaction_activity(self, channel_id: int) -> bool:
        """檢查是否有待處理的 reaction 活動"""
        return channel_id in self.pending_reaction_activities
    
    def _mark_pending_message_activity(self, channel_id: int, activity_type: TrendActivityType) -> None:
        """標記訊息活動為待處理"""
        if not activity_type.is_message_based:
            raise ValueError(f"活動類型 {activity_type} 不是訊息類活動")
        
        if channel_id not in self.pending_message_activities:
            self.pending_message_activities[channel_id] = set()
        self.pending_message_activities[channel_id].add(activity_type)
    
    def _mark_pending_reaction_activity(self, channel_id: int) -> None:
        """標記 reaction 活動為待處理"""
        self.pending_reaction_activities[channel_id] = True
    
    def _clear_pending_message_activity(self, channel_id: int, activity_type: TrendActivityType) -> None:
        """清除待處理的訊息活動"""
        if channel_id in self.pending_message_activities:
            self.pending_message_activities[channel_id].discard(activity_type)
            if not self.pending_message_activities[channel_id]:
                del self.pending_message_activities[channel_id]
    
    def _clear_pending_reaction_activity(self, channel_id: int) -> None:
        """清除待處理的 reaction 活動"""
        if channel_id in self.pending_reaction_activities:
            del self.pending_reaction_activities[channel_id]
    
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
        
        # 使用 reaction 專用鎖防止併發處理
        lock = self.get_reaction_lock(channel_id)
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
        channel_id = payload.channel_id
        
        try:
            # 檢查是否有待處理的 reaction 活動
            if self._has_pending_reaction_activity(channel_id):
                self.logger.debug(f"跳過 reaction 跟風: 頻道 {channel_id} 有待處理的 reaction")
                return False
            
            # 獲取頻道和訊息
            channel = bot.get_channel(channel_id)
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
            
            # 使用機率性決策檢查是否跟風
            if not self.should_follow_probabilistically(target_reaction.count, self.config.reaction_threshold):
                return False
            
            # 檢查機器人是否已經添加過這個 reaction
            async for reaction_user in target_reaction.users():
                if reaction_user.id == bot.user.id:
                    return False  # 機器人已經添加過了
            
            # 標記 reaction 活動為待處理
            self._mark_pending_reaction_activity(channel_id)
            
            try:
                # 可選的隨機延遲（reaction 延遲較短）
                if self.config.enable_random_delay:
                    delay = random.uniform(0.2, min(1.0, self.config.max_delay_seconds))
                    await asyncio.sleep(delay)
                
                # 添加相同的 reaction
                await message.add_reaction(payload.emoji)
                self.update_cooldown(channel_id)
                
                self.logger.info(f"執行 reaction 跟風: {payload.emoji} 在頻道 {channel_id}")
                return True
                
            finally:
                # 清除待處理標記
                self._clear_pending_reaction_activity(channel_id)
            
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
        
        # 使用 message 專用鎖防止併發處理
        lock = self.get_message_lock(channel_id)
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
        channel_id = message.channel.id
        
        try:
            # 檢查是否有待處理的訊息活動
            if self._has_pending_message_activity(channel_id):
                self.logger.debug(f"跳過訊息跟風: 頻道 {channel_id} 有待處理的訊息活動")
                return False
            
            # 獲取訊息歷史（包含機器人訊息用於分析）
            history = await self._get_recent_messages(message.channel, bot.user.id)
            if len(history) < 1:  # 至少需要 1 條歷史訊息才能判斷
                return False
            
            # 決定要執行的活動類型和發送函數
            selected_activity = None
            send_func = None
            send_args = None
            
            # 優先級 1：內容跟風
            content_result = await self._check_content_following(message, history, bot.user.id)
            if content_result:
                activity_type, func, args = content_result
                selected_activity, send_func, send_args = activity_type, func, args
            else:
                # 優先級 2：emoji 跟風
                emoji_result = await self._check_emoji_following(message, history, bot.user.id)
                if emoji_result:
                    activity_type, func, args = emoji_result
                    selected_activity, send_func, send_args = activity_type, func, args
            
            if not selected_activity:
                return False
            
            # 標記活動為進行中
            self._mark_pending_message_activity(channel_id, selected_activity)
            
            try:
                # 如果是emoji跟風，先預生成回應（避免延遲期間的LLM等待）
                if selected_activity == TrendActivityType.EMOJI:
                    # 提前生成emoji回應，傳入bot_user_id
                    response_emoji = await self._generate_emoji_response(send_args[0], bot.user.id)
                    if not response_emoji:
                        return False
                    # 更新發送參數為預生成的emoji
                    send_args = (send_args[0].channel, response_emoji)
                
                    send_func = self._send_pregenerated_emoji
                # 延遲在鎖內執行（確保原子性）
                if self.config.enable_random_delay:
                    delay = random.uniform(self.config.min_delay_seconds, self.config.max_delay_seconds)
                    await asyncio.sleep(delay)
                
                # 發送
                await send_func(*send_args)
                self.update_cooldown(channel_id)
                
                self.logger.info(f"執行 {selected_activity.value} 跟風在頻道 {channel_id}")
                return True
                
            finally:
                # 清理進行中標記
                self._clear_pending_message_activity(channel_id, selected_activity)
            
        except Exception as e:
            self.logger.error(f"跟風邏輯執行失敗: {e}", exc_info=True)
            return False
    
    def _process_message_text_for_context(self, msg: discord.Message, bot_user_id: int) -> Optional[str]:
        """輕量化處理訊息文字內容用於上下文生成
        
        Args:
            msg: Discord 訊息物件
            bot_user_id: 機器人用戶 ID
            
        Returns:
            Optional[str]: 處理後的文字內容，None 表示無有效文字
        """
        try:
            # 獲取基本文字內容
            text_parts = []
            
            # 處理訊息文字內容
            if msg.content:
                cleaned_content = msg.content
                # 移除 bot 提及
                if cleaned_content.startswith(f'<@{bot_user_id}>'):
                    cleaned_content = cleaned_content.replace(f'<@{bot_user_id}>', '').strip()
                if cleaned_content.startswith(f'<@!{bot_user_id}>'):
                    cleaned_content = cleaned_content.replace(f'<@!{bot_user_id}>', '').strip()
                
                # 只有非 bot 訊息才加上用戶名稱
                if not (msg.author.bot or msg.author.id == bot_user_id):
                    cleaned_content = f"{msg.author.display_name}: {cleaned_content}"
                
                if cleaned_content:
                    text_parts.append(cleaned_content)
            
            # 處理 embed 文字內容
            for embed in msg.embeds:
                embed_text = "\n".join(filter(None, [
                    embed.title,
                    embed.description,
                    getattr(embed.footer, "text", None)
                ]))
                if embed_text:
                    text_parts.append(embed_text)
            
            # 合併文字內容
            full_text = "\n".join(text_parts).strip()
            return full_text if full_text else None
            
        except Exception as e:
            self.logger.error(f"處理訊息文字時出錯: {e}")
            return None

    async def _get_recent_messages(self, channel: discord.TextChannel, bot_user_id: int, include_text_content: bool = False) -> List[dict]:
        """獲取最近的訊息內容和元數據
        
        Args:
            channel: Discord 頻道
            bot_user_id: 機器人的用戶 ID
            include_text_content: 是否包含處理後的文字內容用於上下文
            
        Returns:
            List[dict]: 最近的訊息列表，包含內容、sticker 和是否為機器人訊息的資訊
        """
        try:
            messages = []
            async for msg in channel.history(limit=self.config.message_history_limit + 1):
                # 獲取訊息的實際內容（文字或 sticker）
                content_type, content_value = self._get_message_content(msg)
                
                if content_type:  # 只要有內容（文字或 sticker）就保留
                    message_data = {
                        'content_type': content_type,
                        'content_value': content_value,
                        'is_bot': msg.author.bot or msg.author.id == bot_user_id,
                        'author_id': msg.author.id
                    }
                    
                    # 如果需要文字上下文，額外處理文字內容
                    if include_text_content:
                        text_content = self._process_message_text_for_context(msg, bot_user_id)
                        message_data['text_content'] = text_content
                    
                    messages.append(message_data)
            
            # 移除第一條（當前訊息）並反轉順序（最舊的在前）
            return messages[1:][::-1] if len(messages) > 1 else []
            
        except Exception as e:
            self.logger.error(f"獲取訊息歷史失敗: {e}")
            return []
    
    async def _check_content_following(self, message: discord.Message, history: List[dict], bot_user_id: int) -> Optional[tuple]:
        """檢查是否應該執行內容跟風
        
        Args:
            message: 當前訊息
            history: 訊息歷史（包含元數據）
            bot_user_id: 機器人用戶 ID
            
        Returns:
            Optional[tuple]: (活動類型, 發送函數, 發送參數) 或 None
        """
        try:
            # 獲取當前訊息的實際內容（可能是文字或 sticker）
            content_type, content_value = self._get_message_content(message)
            if not content_type:
                return None
            
            # 提取有效的內容片段
            valid_segment, has_bot_in_segment = self._extract_valid_content_segment(history, content_type, content_value)
            
            # 如果機器人已經參與了這個片段，不要跟風
            if has_bot_in_segment:
                content_desc = f"{content_type}:{content_value.id if content_type == 'sticker' else content_value}"
                self.logger.debug(f"內容跟風被阻止：機器人已在片段中參與，內容: '{content_desc}'")
                return None
            
            # 加上當前訊息的計數
            total_count = len(valid_segment) + 1
            
            # 使用機率性決策檢查是否跟風
            if self.should_follow_probabilistically(total_count, self.config.content_threshold):
                return (
                    TrendActivityType.CONTENT,
                    self._send_content_response,
                    (content_type, content_value, message.channel)
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"內容跟風檢查失敗: {e}")
            return None
    
    async def _check_emoji_following(self, message: discord.Message, history: List[dict], bot_user_id: int) -> Optional[tuple]:
        """檢查是否應該執行 emoji 跟風
        
        Args:
            message: 當前訊息
            history: 訊息歷史（包含元數據）
            bot_user_id: 機器人用戶 ID
            
        Returns:
            Optional[tuple]: (活動類型, 發送函數, 發送參數) 或 None
        """
        try:
            # 檢查當前訊息是否只包含 emoji（只處理文字類型）
            content_type, content_value = self._get_message_content(message)
            if content_type != "text" or not self._is_emoji_only_message(content_value):
                return None
            
            # 提取有效的 emoji 片段
            valid_segment, has_bot_in_segment = self._extract_valid_emoji_segment(history)
            
            # 如果機器人已經參與了這個片段，不要跟風
            if has_bot_in_segment:
                self.logger.debug(f"Emoji 跟風被阻止：機器人已在片段中參與")
                return None
            
            # 加上當前訊息的計數
            total_count = len(valid_segment) + 1
            
            # 使用機率性決策檢查是否跟風
            if self.should_follow_probabilistically(total_count, self.config.emoji_threshold):
                return (
                    TrendActivityType.EMOJI,
                    self._send_pregenerated_emoji,
                    (message,)
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Emoji 跟風檢查失敗: {e}")
            return None
    
    async def _send_pregenerated_emoji(self, channel, emoji: str) -> None:
        """發送預生成的 emoji 回應"""
        await channel.send(emoji)
    
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
    
    
    def _is_emoji_only_message(self, content: str) -> bool:
        """檢查訊息是否只包含 emoji (支援 Discord 格式和 Unicode emoji)
        
        Args:
            content: 訊息內容
            
        Returns:
            bool: 是否只包含 emoji
        """
        if not content:
            return False
        
        # 移除所有 Discord 格式 emoji
        content_without_discord_emojis = self.emoji_pattern.sub('', content).strip()
        
        # 移除所有 Unicode emoji
        content_without_unicode_emojis = self.unicode_emoji_pattern.sub('', content_without_discord_emojis).strip()
        
        # 檢查是否有找到任何 emoji
        discord_emojis = self.emoji_pattern.findall(content)
        unicode_emojis = self.unicode_emoji_pattern.findall(content)
        
        # 如果移除所有 emoji 後沒有內容，且至少有一個 emoji，則是純 emoji 訊息
        return (len(content_without_unicode_emojis) == 0 and 
                (len(discord_emojis) > 0 or len(unicode_emojis) > 0))
    
    async def _generate_emoji_response(self, message: discord.Message, bot_user_id: int) -> Optional[str]:
        """使用 LLM 生成 emoji 回應（整合對話上下文）
        
        Args:
            message: Discord 訊息
            bot_user_id: 機器人用戶 ID
            
        Returns:
            Optional[str]: 生成的 emoji 回應
        """
        try:
            if not self.llm or not self.emoji_registry:
                return random.choice(self.fallback_emojis)
            
            # 建立 emoji 上下文
            guild_id = message.guild.id if message.guild else None
            emoji_context = self.emoji_registry.build_prompt_context(guild_id)
            
            history = await self._get_recent_messages(message.channel, bot_user_id, include_text_content=True)
            
            # 建立對話上下文
            conversation_context = ""
            if history:
                text_messages = []
                for msg_data in history[-5:]:  # 最近5條有文字的訊息
                    if msg_data.get('text_content'):
                        text_messages.append(msg_data['text_content'])
                
                if text_messages:
                    conversation_context = f"""
最近的對話內容：
{chr(10).join(text_messages)}
"""
            
            # 如果既沒有 emoji 上下文也沒有對話上下文，使用 fallback
            if not emoji_context and not conversation_context:
                return random.choice(self.fallback_emojis)
            
            # 建立完整的 LLM 提示
            prompt = f"""你正在參與一個 Discord 頻道的 emoji 跟風活動。最近有多條訊息都只包含 emoji，現在需要你根據對話上下文選擇一個適合的 emoji 來回應。
對話上下文:
{conversation_context}

請根據對話內容和氣氛選擇一個最適合的 emoji 回應。你可以使用：
1. Discord 自定義 emoji（格式：<:emoji_name:emoji_id> 或 <a:animated_emoji:emoji_id>）
{emoji_context}

2. Unicode emoji（如：😄👍❤️😊🎉😂🔥💯等等）

只需要回傳一個 emoji，不要其他文字。
範例回應: <:thinking:123456789012345678> 或 😄
"""
            
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()
            self.logger.info(f"Emoji 回應: {content}")
            
            # 驗證回應是否包含有效的 emoji 格式
            # 優先檢查 Discord 格式 emoji
            discord_emoji_matches = self.emoji_pattern.findall(content)
            if discord_emoji_matches:
                return discord_emoji_matches[0]  # 返回第一個找到的 Discord emoji
            
            # 檢查 Unicode emoji
            unicode_emoji_matches = self.unicode_emoji_pattern.findall(content)
            if unicode_emoji_matches:
                return unicode_emoji_matches[0]  # 返回第一個找到的 Unicode emoji
            
            # 如果 LLM 回應無效，使用 fallback
            return random.choice(self.fallback_emojis)
            
        except Exception as e:
            self.logger.error(f"生成 emoji 回應失敗: {e}")
            # 異常時使用 fallback
            return random.choice(self.fallback_emojis)