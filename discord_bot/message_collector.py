"""
Discord 訊息收集與預處理模組

收集並處理 Discord 訊息內容，建立對話歷史鏈，
並整合 Discord 訊息快取功能。
"""

import discord
import logging
import asyncio
from base64 import b64encode
from typing import Dict, Any, Set, List, Optional, Union, Iterator, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import OrderedDict

from schemas.agent_types import MsgNode
from schemas.config_types import EmojiStickerConfig
from discord_bot.message_manager import get_manager_instance
from utils.image_processor import (
    parse_emoji_from_message,
    load_from_discord_emoji_sticker,
    process_attachment_image,
    resize_image,
    convert_images_to_base64_dict,
    ImageProcessingError,
    VirtualAttachment,
    is_video_url,
    # 保留舊的導入以維持相容性，但會產生 deprecation warning
    is_discord_gif_url,
)


@dataclass
class ProcessedMessage:
    """處理後的訊息結構
    
    表示經過預處理的單一 Discord 訊息，包含清理後的內容和元數據
    """
    content: Union[str, List[Dict[str, Any]]]
    """訊息內容，可以是純文字或包含圖片的結構化列表"""
    
    role: str
    """訊息角色，通常是 'user' 或 'assistant'"""
    
    user_id: Optional[int] = None
    """發送者的 Discord 用戶 ID"""
    
    message_id: Optional[int] = None
    """Discord 訊息的 ID"""
    
    created_at: Optional[datetime] = None
    """訊息創建時間，用於排序"""


@dataclass
class CollectedMessages:
    """收集到的訊息集合結構
    
    提供類型安全的訊息收集結果，包含處理後的訊息和用戶警告。
    這個類別封裝了 Discord 訊息收集的完整結果，提供便利的存取方法。
    """
    messages: List[MsgNode] = field(default_factory=list)
    """處理後的訊息列表，已轉換為 MsgNode 格式，按時間順序排列"""
    
    user_warnings: Set[str] = field(default_factory=set)
    """用戶警告集合，包含處理過程中的提示訊息（如附件過大、內容截斷等）"""
    
    collection_timestamp: datetime = field(default_factory=datetime.now)
    """訊息收集的時間戳，用於追蹤和除錯"""
    
    # 便利方法
    def has_warnings(self) -> bool:
        """檢查是否有用戶警告
        
        Returns:
            bool: 如果存在警告則返回 True
        """
        return len(self.user_warnings) > 0
    

    def message_count(self) -> int:
        """獲取訊息數量
        
        Returns:
            int: 收集到的訊息總數
        """
        return len(self.messages)

    def get_latest_message(self) -> Optional[MsgNode]:
        """獲取最新的訊息
        
        Returns:
            Optional[MsgNode]: 最新的訊息，如果沒有訊息則返回 None
        """
        return self.messages[-1] if self.messages else None
    
    def get_messages_by_user_id(self, user_id: int) -> List[MsgNode]:
        """根據用戶 ID 獲取訊息
        
        Args:
            user_id: Discord 用戶 ID
            
        Returns:
            List[MsgNode]: 該用戶發送的所有訊息
        """
        return [
            msg for msg in self.messages 
            if msg.metadata and msg.metadata.get("user_id") == user_id
        ]
    
    def iter_messages(self) -> Iterator[MsgNode]:
        """迭代所有訊息
        
        Yields:
            MsgNode: 按順序產生每個訊息
        """
        yield from self.messages
    
    def add_warning(self, warning: str) -> None:
        """添加用戶警告
        
        Args:
            warning: 警告訊息
        """
        self.user_warnings.add(warning)
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式，便於序列化
        
        Returns:
            Dict[str, Any]: 包含所有資料的字典
        """
        return {
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "metadata": msg.metadata
                }
                for msg in self.messages
            ],
            "user_warnings": list(self.user_warnings),
            "collection_timestamp": self.collection_timestamp.isoformat(),
            "message_count": self.message_count(),
            "has_warnings": self.has_warnings()
        }
    
    def __str__(self) -> str:
        """字串表示
        
        Returns:
            str: 人類可讀的訊息集合描述
        """
        return (
            f"CollectedMessages(messages={self.message_count()}, "
            f"warnings={len(self.user_warnings)})"
        )
    
    def __repr__(self) -> str:
        """詳細字串表示
        
        Returns:
            str: 詳細的物件表示
        """
        return (
            f"CollectedMessages("
            f"messages={self.messages}, "
            f"user_warnings={self.user_warnings}, "
            f"collection_timestamp={self.collection_timestamp}"
            f")"
        )


async def collect_message(
    new_msg: discord.Message,
    discord_client_user: discord.User,
    enable_conversation_history: bool = True,
    max_text: int = 4000,
    max_images: int = 4,
    max_messages: int = 10,
    httpx_client = None,
    emoji_sticker_config: Optional[EmojiStickerConfig] = None
) -> CollectedMessages:
    """
    收集並處理訊息內容，建立對話歷史鏈
    
    Args:
        new_msg: Discord 訊息
        discord_client_user: Bot 的 Discord 用戶物件
        enable_conversation_history: 是否啟用對話歷史
        max_text: 每條訊息的最大文字長度
        max_images: 每條訊息的最大圖片數量
        max_messages: 歷史訊息的最大數量
        httpx_client: HTTP 客戶端（用於下載附件）
        emoji_sticker_config: Emoji 和 Sticker 處理配置
    
    Returns:
        CollectedMessages: 包含處理後訊息和用戶警告的結構化資料
    """
    messages = []
    user_warnings = set()
    curr_msg = new_msg
    
    # 設定預設 emoji_sticker_config
    if emoji_sticker_config is None:
        emoji_sticker_config = EmojiStickerConfig()
    
    # 取得 Discord 訊息管理器
    message_manager = get_manager_instance()
    
    # 記錄收到的訊息
    logging.info(f"處理訊息 (用戶: {new_msg.author.display_name}, 附件: {len(new_msg.attachments)}, stickers: {len(new_msg.stickers)})")
    
    # 獲取訊息歷史
    history_msgs = []
    if enable_conversation_history:
        try:
            history_msgs = [m async for m in curr_msg.channel.history(before=curr_msg, limit=max_messages)][::-1]
        except discord.HTTPException:
            logging.warning("無法獲取頻道歷史，將只處理當前訊息")
    
    remaining_imgs_count = max_images
    processed_messages = []
    
    # 處理訊息鏈
    msg_count = 0
    all_processed_messages_map: OrderedDict[int, ProcessedMessage] = OrderedDict() # 用於去重複
    
    # 這裡的邏輯需要調整，因為我們現在要從 history_msgs 和 curr_msg 中收集所有相關訊息
    # 並在之後統一處理去重複和排序
    
    # 首先處理 new_msg 和其父訊息鏈
    current_msg_to_process = new_msg
    while current_msg_to_process and msg_count < max_messages:
        try:
            processed_msg = await _process_single_message(
                current_msg_to_process, 
                discord_client_user, 
                max_text, 
                remaining_imgs_count, # 這裡的 remaining_imgs_count 在這個迴圈中不再是累計的，因為我們是獨立處理每個訊息的圖片限制
                httpx_client,
                emoji_sticker_config
            )
            
            if processed_msg and processed_msg.message_id not in all_processed_messages_map:
                all_processed_messages_map[processed_msg.message_id] = processed_msg
                
                # 檢查限制並添加警告
                _check_limits_and_add_warnings(current_msg_to_process, max_text, max_images, user_warnings)
            
            msg_count += 1
            
            # 嘗試獲取父訊息（回覆）
            current_msg_to_process = await _get_parent_message(current_msg_to_process)
            
        except Exception as e:
            logging.error(f"處理訊息時出錯: {e}")
            break
            
    # 將歷史訊息也加入待處理的集合中
    for hist_msg in history_msgs[::-1]:
        if hist_msg.id not in all_processed_messages_map:
            try:
                processed_msg = await _process_single_message(
                    hist_msg, 
                    discord_client_user, 
                    max_text, 
                    max_images, # 歷史訊息的圖片限制獨立計算
                    httpx_client,
                    emoji_sticker_config
                )
                if processed_msg and processed_msg.message_id not in all_processed_messages_map:
                    all_processed_messages_map[processed_msg.message_id] = processed_msg
                    _check_limits_and_add_warnings(hist_msg, max_text, max_images, user_warnings)
            except Exception as e:
                logging.error(f"處理歷史訊息時出錯: {e}")

    # 對所有處理過的訊息進行去重複和排序
    # 去重複已經在 all_processed_messages_map 中完成
    processed_messages = list(all_processed_messages_map.values())[::-1]
    # processed_messages = sorted(
    #     all_processed_messages_map.values(), 
    #     key=lambda p_msg: p_msg.created_at or datetime.min # 使用 created_at 排序，如果為 None 則排在最前面
    # )
    
    # 重新計算實際使用的圖片數量
    actual_img_count = 0
    for p_msg in processed_messages:
        if isinstance(p_msg.content, list):
            actual_img_count += sum(1 for item in p_msg.content if item.get("type") == "image_url")
    
    if actual_img_count > max_images:
        user_warnings.add(f"⚠️ 實際處理的圖片數量超過 {max_images} 張")

    # 轉換為 MsgNode 格式
    logging.debug(
        "處理訊息: %r", 
        [
            processed_msg.content[:100] 
            if isinstance(processed_msg.content, str) 
            else (processed_msg.content[0]['text'] + " (with Image)")
            for processed_msg in processed_messages
        ]
    )
    for processed_msg in processed_messages: # 這裡不再需要 [::-1] 反轉，因為已經排序過了
        msg_node = MsgNode(
            role=processed_msg.role,
            content=processed_msg.content,
            metadata={"user_id": processed_msg.user_id, "message_id": processed_msg.message_id} if processed_msg.user_id else {"message_id": processed_msg.message_id}
        )
        messages.append(msg_node)
    
    # 快取處理後的訊息
    # 這裡的 messages_to_cache 應該是原始的 discord.Message 物件，用於快取
    # 我們需要從 all_processed_messages_map 中獲取原始訊息的 ID，然後嘗試從 message_manager 中獲取原始訊息
    # 但考慮到 history_msgs 已經包含了歷史訊息，我們可以簡單地將 new_msg 和 history_msgs 加入快取
    # 這裡的邏輯保持不變，因為 cache_messages 預期的是 discord.Message 物件列表
    message_manager.cache_messages([new_msg] + history_msgs)
    
    return CollectedMessages(
        messages=messages,
        user_warnings=user_warnings
    )


def _extract_media_urls_from_embeds(msg: discord.Message) -> List[str]:
    """從 embed 中提取媒體 URLs（支援 thumbnail 和 image，簡化處理邏輯）
    
    Args:
        msg: Discord 訊息物件
        
    Returns:
        List[str]: 提取到的 URLs 列表（跳過明顯的影片格式）
    """
    media_urls = []
    
    for embed in msg.embeds:
        # 處理 embed thumbnail
        if hasattr(embed, '_thumbnail') and embed._thumbnail:
            thumbnail_url = embed._thumbnail.get('url', '')
            if thumbnail_url:
                if is_video_url(thumbnail_url):
                    # TODO: 未來可考慮支援影片處理
                    logging.info(f"跳過 embed thumbnail 中的影片 URL（待未來實現）: {thumbnail_url}")
                else:
                    # 簡化邏輯：只要不是明顯的影片格式就嘗試處理
                    media_urls.append(thumbnail_url)
                    logging.debug(f"從 embed thumbnail 提取 URL: {thumbnail_url}")
        
        # 處理 embed image (EmbedProxy)
        if hasattr(embed, 'image') and embed.image:
            image_url = getattr(embed.image, 'url', '') or getattr(embed.image, 'proxy_url', '')
            if image_url:
                if is_video_url(image_url):
                    # TODO: 未來可考慮支援影片處理
                    logging.info(f"跳過 embed image 中的影片 URL（待未來實現）: {image_url}")
                else:
                    # 簡化邏輯：只要不是明顯的影片格式就嘗試處理
                    media_urls.append(image_url)
                    logging.debug(f"從 embed image 提取 URL: {image_url}")
    
    return media_urls


async def _process_single_message(
    msg: discord.Message,
    discord_client_user: discord.User,
    max_text: int,
    remaining_imgs_count: int,
    httpx_client,
    emoji_sticker_config: EmojiStickerConfig
) -> Optional[ProcessedMessage]:
    """處理單一訊息"""
    try:
        # 初始化多媒體內容計數器
        media_stats = {
            "emoji": 0,
            "sticker": 0,
            "animated": 0,
            "static": 0
        }

        # 清理內容（移除 bot 提及）
        cleaned_content = msg.content
        if msg.content.startswith(discord_client_user.mention):
            cleaned_content = msg.content.removeprefix(discord_client_user.mention).lstrip()
        if msg.author.id != discord_client_user.id:
            cleaned_content = f"{msg.author.mention} {msg.author.display_name}: {cleaned_content}"
        
        # 處理 Discord Stickers
        sticker_images, sticker_stats = await _process_discord_stickers(msg, emoji_sticker_config)
        media_stats["sticker"] = sticker_stats["total"]
        media_stats["animated"] += sticker_stats["animated"]
        media_stats["static"] += sticker_stats["static"]
        
        # 處理訊息中的 Emoji
        emoji_images, emoji_stats = await _process_emoji_from_message(msg, emoji_sticker_config)
        media_stats["emoji"] = emoji_stats["total"]
        media_stats["animated"] += emoji_stats["animated"]
        media_stats["static"] += emoji_stats["static"]
        
        # 處理附件
        good_attachments = [
            att for att in msg.attachments 
            if att.content_type and any(att.content_type.startswith(x) for x in ("text", "image"))
        ]
        
        # 從 embed 中提取媒體 URLs 並創建虛擬附件（支援 thumbnail 和 image，無域名限制）
        embed_media_urls = _extract_media_urls_from_embeds(msg)
        virtual_attachments = []
        
        for url in embed_media_urls:
            if len(good_attachments) + len(virtual_attachments) < remaining_imgs_count:
                virtual_att = VirtualAttachment(url=url)
                virtual_attachments.append(virtual_att)
                logging.debug(f"從 embed 創建虛擬附件: {url}")
            else:
                logging.warning(f"達到圖片數量限制，跳過 embed 媒體 URL: {url}")
                break
        
        # 合併真實附件和虛擬附件
        good_attachments.extend(virtual_attachments)
        
        # 組合文字內容
        text_parts = []
        if cleaned_content:
            text_parts.append(cleaned_content)
        
        # 添加 embed 內容
        for embed in msg.embeds:
            embed_text = "\n".join(filter(None, [
                embed.title,
                embed.description,
                getattr(embed.footer, "text", None)
            ]))
            if embed_text:
                text_parts.append(embed_text)
        
        # 添加文字附件內容
        if httpx_client and good_attachments:
            try:
                logging.debug(f"下載文字附件: {[att.url for att in good_attachments if att.content_type.startswith('text')]}")
                text_attachment_responses = await asyncio.gather(
                    *[httpx_client.get(att.url) for att in good_attachments if att.content_type.startswith("text")],
                    return_exceptions=True
                )
                
                text_attachments = [att for att in good_attachments if att.content_type.startswith("text")]
                for att, resp in zip(text_attachments, text_attachment_responses):
                    if hasattr(resp, 'text') and not isinstance(resp, Exception):
                        try:
                            text_parts.append(resp.text)
                        except Exception:
                            logging.warning(f"無法讀取文字附件: {att.filename}")
            except Exception as e:
                logging.warning(f"下載文字附件失敗: {e}")
        
        text_content = "\n".join(text_parts)[:max_text]
        
        # 處理圖片附件（包含虛擬附件，即 embed 中的圖片 URLs，支援多種來源和格式）
        attachment_images = []
        attachment_count = 0
        for att in good_attachments:
            # ⚠️ 注意：att 可能是 VirtualAttachment（來自 embed thumbnail/image）或真實的 discord.Attachment
            # 在對 attachment 進行更深入的屬性操作時，請檢查 hasattr(att, '_is_virtual')
            if att.content_type.startswith("image") and len(attachment_images) < remaining_imgs_count:
                try:
                    # 使用新的圖片處理函數支援動畫
                    processed_frames, is_animated = await process_attachment_image(
                        att, 
                        emoji_sticker_config.max_animated_frames if emoji_sticker_config.enable_animated_processing else 1,
                        httpx_client
                    )
                    
                    # 更新統計
                    if is_animated:
                        media_stats["animated"] += 1
                    else:
                        media_stats["static"] += 1
                    attachment_count += 1
                    
                    # 調整圖片大小（使用現有的限制邏輯，不使用 emoji_sticker_max_size）
                    # 這裡保持現有的大小限制邏輯不變
                    
                    # 轉換為 Base64 格式
                    frame_data = convert_images_to_base64_dict(processed_frames)
                    attachment_images.extend(frame_data)
                    
                    logging.debug(f"成功處理圖片附件: {att.filename}, 幀數: {len(processed_frames)}")
                    
                except ImageProcessingError as e:
                    logging.warning(f"處理圖片附件失敗: {att.filename} - {e}")
                    continue
                except Exception as e:
                    logging.warning(f"處理圖片附件時發生未預期錯誤: {att.filename} - {e}")
                    continue
        
        # 產生多媒體內容摘要
        media_summary = _generate_media_summary(
            emoji_count=media_stats["emoji"],
            sticker_count=media_stats["sticker"],
            gif_count=media_stats["animated"],
            static_count=media_stats["static"] + attachment_count - media_stats["animated"]
        )

        # 將摘要附加到文字內容
        if media_summary:
            text_content = f"{text_content}\n{media_summary}".strip()
            
        # 整合所有圖片內容
        all_images = sticker_images + emoji_images + attachment_images
        
        # 決定內容格式
        if all_images and text_content:
            content = [{"type": "text", "text": text_content}] + all_images
        elif all_images:
            content = all_images
        else:
            content = text_content
        
        # 確定角色
        role = "assistant" if msg.author == discord_client_user else "user"
        user_id = msg.author.id if role == "user" else None
        
        return ProcessedMessage(
            content=content,
            role=role,
            user_id=user_id,
            message_id=msg.id,
            created_at=msg.created_at
        )
        
    except Exception as e:
        logging.error(f"處理訊息 {msg.id} 時出錯: {e}")
        return None


async def _get_parent_message(msg: discord.Message) -> Optional[discord.Message]:
    """獲取父訊息（回覆的原始訊息）
    
    優先從 Discord 訊息快取中查找，如果找不到再從 Discord API 獲取
    """
    if not msg.reference or not msg.reference.message_id:
        return None
    
    try:
        # 先從 Discord 訊息快取中查找
        message_manager = get_manager_instance()
        cached_message = message_manager.find_message_by_id(msg.reference.message_id)
        
        if cached_message:
            logging.debug(f"從快取中找到父訊息: {msg.reference.message_id}")
            return cached_message
        
        # 如果快取中沒有，再從 Discord API 獲取
        parent_message = await msg.channel.fetch_message(msg.reference.message_id)
        
        # 將獲取到的父訊息也加入快取
        message_manager.cache_message(parent_message)
        
        return parent_message
        
    except (discord.NotFound, discord.HTTPException):
        logging.debug(f"無法獲取父訊息: {msg.reference.message_id}")
        pass
    return None


def _check_limits_and_add_warnings(
    msg: discord.Message,
    max_text: int,
    max_images: int,
    user_warnings: Set[str]
):
    """檢查限制並添加警告"""
    if len(msg.content) > max_text:
        user_warnings.add(f"⚠️ 每條訊息最多 {max_text:,} 個字元")
    
    image_attachments = [att for att in msg.attachments if att.content_type and att.content_type.startswith("image")]
    if len(image_attachments) > max_images:
        user_warnings.add(f"⚠️ 每條訊息最多 {max_images} 張圖片" if max_images > 0 else "⚠️ 無法處理圖片")
    
    unsupported_attachments = [
        att for att in msg.attachments 
        if not att.content_type or not any(att.content_type.startswith(x) for x in ("text", "image"))
    ]
    if unsupported_attachments:
        user_warnings.add("⚠️ 不支援的附件類型")


async def _process_discord_stickers(
    msg: discord.Message,
    config: EmojiStickerConfig
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    處理 Discord Sticker
    
    Args:
        msg: Discord 訊息物件
        config: Emoji 和 Sticker 配置
        
    Returns:
        Tuple[List[Dict[str, Any]], Dict[str, int]]: 
            處理後的 sticker 圖片列表和統計數據
            (e.g., {"total": 1, "animated": 1, "static": 0})
    """
    if not config.enable_sticker_processing or not msg.stickers:
        return [], {"total": 0, "animated": 0, "static": 0}
    
    sticker_images = []
    stats = {"total": 0, "animated": 0, "static": 0}
    
    for sticker in msg.stickers:
        if stats["total"] >= config.max_sticker_per_message:
            logging.warning(f"Sticker 數量超過限制 {config.max_sticker_per_message}，跳過剩餘 sticker")
            break
        
        try:
            # 檢查 sticker 格式
            if hasattr(sticker, 'format') and sticker.format:
                format_name = str(sticker.format).lower()
                
                # TODO: Lottie 格式暫不支援，直接跳過
                if 'lottie' in format_name:
                    logging.info(f"跳過 Lottie 格式的 sticker: {sticker.name}")
                    continue
                
                # 支援的格式：PNG, APNG, GIF, WebP
                supported_formats = ['png', 'apng', 'gif', 'webp']
                if not any(fmt in format_name for fmt in supported_formats):
                    logging.warning(f"不支援的 sticker 格式: {format_name}")
                    continue
            
            # 載入 sticker 圖片
            frames, is_animated = await load_from_discord_emoji_sticker(
                sticker, 
                config.max_animated_frames if config.enable_animated_processing else 1
            )
            
            # 更新統計
            stats["total"] += 1
            if is_animated:
                stats["animated"] += 1
            else:
                stats["static"] += 1

            # 調整圖片大小
            resized_frames = []
            for frame in frames:
                resized_frame = resize_image(frame, config.emoji_sticker_max_size)
                resized_frames.append(resized_frame)
            
            # 轉換為 Base64 格式
            frame_data = convert_images_to_base64_dict(resized_frames)
            sticker_images.extend(frame_data)
            
            logging.debug(f"成功處理 sticker: {sticker.name}, 幀數: {len(frames)}")
            
        except ImageProcessingError as e:
            logging.warning(f"處理 sticker 失敗: {sticker.name} - {e}")
            continue
        except Exception as e:
            logging.warning(f"處理 sticker 時發生未預期錯誤: {sticker.name} - {e}")
            continue
    
    return sticker_images, stats


async def _process_emoji_from_message(
    msg: discord.Message,
    config: EmojiStickerConfig
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    處理訊息中的自定義 Emoji
    
    Args:
        msg: Discord 訊息物件
        config: Emoji 和 Sticker 配置
        
    Returns:
        Tuple[List[Dict[str, Any]], Dict[str, int]]: 
            處理後的 emoji 圖片列表和統計數據
            (e.g., {"total": 1, "animated": 0, "static": 1})
    """
    if not config.enable_emoji_processing or not msg.content:
        return [], {"total": 0, "animated": 0, "static": 0}
    
    emoji_images = []
    stats = {"total": 0, "animated": 0, "static": 0}
    
    try:
        # 解析訊息中的 emoji
        emojis = await parse_emoji_from_message(msg, config.max_emoji_per_message)
        
        if not emojis:
            return [], {"total": 0, "animated": 0, "static": 0}
        
        if len(emojis) > config.max_emoji_per_message:
            logging.warning(f"Emoji 數量超過限制 {config.max_emoji_per_message}，僅處理前 {config.max_emoji_per_message} 個")
            emojis = emojis[:config.max_emoji_per_message]
        
        for emoji in emojis:
            try:
                # 載入 emoji 圖片
                frames, is_animated = await load_from_discord_emoji_sticker(
                    emoji,
                    config.max_animated_frames if config.enable_animated_processing else 1
                )
                
                # 更新統計
                stats["total"] += 1
                if is_animated:
                    stats["animated"] += 1
                else:
                    stats["static"] += 1

                # 調整圖片大小
                resized_frames = []
                for frame in frames:
                    resized_frame = resize_image(frame, config.emoji_sticker_max_size)
                    resized_frames.append(resized_frame)
                
                # 轉換為 Base64 格式
                frame_data = convert_images_to_base64_dict(resized_frames)
                emoji_images.extend(frame_data)
                
                logging.debug(f"成功處理 emoji: {emoji.name if hasattr(emoji, 'name') else 'unknown'}, 幀數: {len(frames)}")
                
            except ImageProcessingError as e:
                logging.warning(f"處理 emoji 失敗: {emoji.name if hasattr(emoji, 'name') else 'unknown'} - {e}")
                continue
            except Exception as e:
                logging.warning(f"處理 emoji 時發生未預期錯誤: {emoji.name if hasattr(emoji, 'name') else 'unknown'} - {e}")
                continue
        
    except Exception as e:
        logging.error(f"解析訊息 emoji 時發生錯誤: {e}")
    
    return emoji_images, stats

def _generate_media_summary(
    emoji_count: int,
    sticker_count: int,
    gif_count: int,
    static_count: int
) -> str:
    """生成簡潔的媒體內容摘要"""
    parts = []
    if emoji_count > 0:
        parts.append(f"{emoji_count}個emoji")
    if sticker_count > 0:
        parts.append(f"{sticker_count}個sticker")
    if gif_count > 0:
        parts.append(f"{gif_count}個動畫")
    
    # 靜態圖片的統計比較複雜，暫時不加入摘要，避免混淆
    # if static_count > 0:
    #     parts.append(f"{static_count}張靜態圖片")

    if parts:
        return f"[包含: {', '.join(parts)}]"
    return ""


 