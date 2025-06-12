"""
Discord 訊息收集與預處理模組

收集並處理 Discord 訊息內容，建立對話歷史鏈，
並整合會話管理功能。
"""

import discord
import logging
import asyncio
from base64 import b64encode
from typing import Dict, Any, Set, List, Optional
from dataclasses import dataclass, field

from schemas.agent_types import MsgNode
from agent_core.agent_session import get_agent_session


@dataclass
class ProcessedMessage:
    """處理後的訊息結構"""
    content: Any  # 可以是字串或包含圖片的列表
    role: str
    user_id: Optional[int] = None


async def collect_message(
    new_msg: discord.Message,
    cfg: dict,
    discord_client_user: discord.User,
    max_text: int = 4000,
    max_images: int = 4,
    max_messages: int = 10,
    httpx_client = None
) -> Dict[str, Any]:
    """
    收集並處理訊息內容，建立對話歷史鏈
    
    Args:
        new_msg: Discord 訊息
        cfg: 配置資料
        discord_client_user: Bot 的 Discord 用戶物件
        max_text: 每條訊息的最大文字長度
        max_images: 每條訊息的最大圖片數量
        max_messages: 歷史訊息的最大數量
        httpx_client: HTTP 客戶端（用於下載附件）
    
    Returns:
        Dict: 包含處理後訊息和用戶警告的字典
    """
    messages = []
    user_warnings = set()
    curr_msg = new_msg
    
    # 取得會話管理器
    session_manager = get_agent_session()
    
    # 獲取或創建會話
    session_id = session_manager.create_session(str(new_msg.channel.id))
    session = session_manager.get_session(session_id)
    
    # 記錄收到的訊息
    logging.info(f"處理訊息 (用戶ID: {new_msg.author.id}, 附件: {len(new_msg.attachments)}, 會話: {session_id})")
    
    # 獲取訊息歷史
    history_msgs = []
    if cfg.get("enable_conversation_history", True):
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
    for processed_msg in processed_messages:
        msg_node = MsgNode(
            role=processed_msg.role,
            content=processed_msg.content if isinstance(processed_msg.content, str) else str(processed_msg.content),
            metadata={"user_id": processed_msg.user_id} if processed_msg.user_id else {}
        )
        messages.append(msg_node)
    
    # 快取處理後的訊息到會話
    if session:
        discord_messages = [
            {
                "id": new_msg.id,
                "content": new_msg.content,
                "author_id": new_msg.author.id,
                "timestamp": new_msg.created_at.isoformat()
            }
        ]
        session_manager.cache_discord_messages(session_id, discord_messages)
    
    return {
        "messages": messages,
        "user_warnings": user_warnings,
        "session_id": session_id
    }


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
    """獲取父訊息（回覆的原始訊息）"""
    try:
        if msg.reference and msg.reference.message_id:
            return await msg.channel.fetch_message(msg.reference.message_id)
    except (discord.NotFound, discord.HTTPException):
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