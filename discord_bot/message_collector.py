"""
Discord 訊息收集與預處理模組

收集並處理 Discord 訊息內容，建立對話歷史鏈，
並整合 Discord 訊息快取功能。
"""

import discord
import logging
import asyncio
from base64 import b64encode
from typing import Dict, Any, Set, List, Optional, Union, Iterator
from dataclasses import dataclass, field
from datetime import datetime

from schemas.agent_types import MsgNode
from discord_bot.message_manager import get_manager_instance


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
    httpx_client = None
) -> CollectedMessages:
    """
    收集並處理訊息內容，建立對話歷史鏈
    
    Args:
        new_msg: Discord 訊息
        discord_client_user: Bot 的 Discord 用戶物件
        max_text: 每條訊息的最大文字長度
        max_images: 每條訊息的最大圖片數量
        max_messages: 歷史訊息的最大數量
        httpx_client: HTTP 客戶端（用於下載附件）
    
    Returns:
        CollectedMessages: 包含處理後訊息和用戶警告的結構化資料
    """
    messages = []
    user_warnings = set()
    curr_msg = new_msg
    
    # 取得 Discord 訊息管理器
    message_manager = get_manager_instance()
    
    # 記錄收到的訊息
    logging.info(f"處理訊息 (用戶: {new_msg.author.display_name}, 附件: {len(new_msg.attachments)})")
    
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
    while curr_msg and msg_count < max_messages:
        try:
            processed_msg = await _process_single_message(
                curr_msg, 
                discord_client_user, 
                max_text, 
                remaining_imgs_count,
                httpx_client
            )
            
            if processed_msg:
                processed_messages.append(processed_msg)
                
                # 更新剩餘圖片數量
                if isinstance(processed_msg.content, list):
                    img_count = sum(1 for item in processed_msg.content if item.get("type") == "image_url")
                    remaining_imgs_count -= img_count
                
                # 檢查限制並添加警告
                _check_limits_and_add_warnings(curr_msg, max_text, max_images, user_warnings)
            
            msg_count += 1
            
            # 嘗試獲取父訊息（回覆）
            curr_msg = await _get_parent_message(curr_msg)
            if curr_msg is None and history_msgs:
                curr_msg = history_msgs.pop(-1)
                
        except Exception as e:
            logging.error(f"處理訊息時出錯: {e}")
            break
    
    # 轉換為 MsgNode 格式
    logging.debug(f"處理訊息: {processed_messages[:3]}")
    for processed_msg in processed_messages[::-1]:
        msg_node = MsgNode(
            role=processed_msg.role,
            content=processed_msg.content if isinstance(processed_msg.content, str) else str(processed_msg.content),
            metadata={"user_id": processed_msg.user_id} if processed_msg.user_id else {}
        )
        messages.append(msg_node)
    
    # 快取處理後的訊息
    messages_to_cache = [new_msg] + history_msgs
    message_manager.cache_messages(messages_to_cache)
    
    return CollectedMessages(
        messages=messages,
        user_warnings=user_warnings
    )


async def _process_single_message(
    msg: discord.Message,
    discord_client_user: discord.User,
    max_text: int,
    remaining_imgs_count: int,
    httpx_client
) -> Optional[ProcessedMessage]:
    """處理單一訊息"""
    try:
        # 清理內容（移除 bot 提及）
        cleaned_content = msg.content
        if msg.content.startswith(f"<@{discord_client_user.id}>"):
            cleaned_content = msg.content.removeprefix(f"<@{discord_client_user.id}>").lstrip()
        if msg.author.id != discord_client_user.id:
            cleaned_content = f"<@{msg.author.id}> {msg.author.display_name}: {cleaned_content}"
        
        # 處理附件
        good_attachments = [
            att for att in msg.attachments 
            if att.content_type and any(att.content_type.startswith(x) for x in ("text", "image"))
        ]
        
        attachment_responses = []
        if httpx_client and good_attachments:
            try:
                attachment_responses = await asyncio.gather(
                    *[httpx_client.get(att.url) for att in good_attachments],
                    return_exceptions=True
                )
            except Exception as e:
                logging.warning(f"下載附件失敗: {e}")
        
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
        for att, resp in zip(good_attachments, attachment_responses):
            if (att.content_type.startswith("text") and 
                hasattr(resp, 'text') and not isinstance(resp, Exception)):
                try:
                    text_parts.append(resp.text)
                except Exception:
                    logging.warning(f"無法讀取文字附件: {att.filename}")
        
        text_content = "\n".join(text_parts)[:max_text]
        
        # 處理圖片附件
        images = []
        for att, resp in zip(good_attachments, attachment_responses):
            if (att.content_type.startswith("image") and 
                len(images) < remaining_imgs_count and
                hasattr(resp, 'content') and not isinstance(resp, Exception)):
                try:
                    image_data = {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{att.content_type};base64,{b64encode(resp.content).decode('utf-8')}"
                        }
                    }
                    images.append(image_data)
                except Exception:
                    logging.warning(f"無法處理圖片附件: {att.filename}")
        
        # 決定內容格式
        if images and text_content:
            content = [{"type": "text", "text": text_content}] + images
        elif images:
            content = images
        else:
            content = text_content
        
        # 確定角色
        role = "assistant" if msg.author == discord_client_user else "user"
        user_id = msg.author.id if role == "user" else None
        
        return ProcessedMessage(
            content=content,
            role=role,
            user_id=user_id
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