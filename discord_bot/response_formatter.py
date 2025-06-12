"""
Discord 回覆格式化與發送模組

格式化 LLM 回覆並發送到 Discord，支援長訊息分割、
embed 格式和警告顯示。
"""

import discord
import asyncio
import logging
from typing import Dict, Any, Set, List, Optional

# 常數
EMBED_COLOR_COMPLETE = discord.Color.dark_green()
EMBED_COLOR_INCOMPLETE = discord.Color.orange()
STREAMING_INDICATOR = " ⚪"
EDIT_DELAY_SECONDS = 1


async def format_llm_output_and_reply(
    llm_response_content: str,
    finish_reason: str,
    new_msg: discord.Message,
    user_warnings: Set[str],
    cfg: Dict[str, Any],
    sources: Optional[List[Dict[str, Any]]] = None
) -> List[discord.Message]:
    """
    格式化 LLM 回覆並發送到 Discord
    
    Args:
        llm_response_content: LLM 回覆內容
        finish_reason: LLM 完成原因
        new_msg: 原始 Discord 訊息
        user_warnings: 用戶警告集合
        cfg: 配置資料
        sources: 來源資訊（可選）
    
    Returns:
        List[discord.Message]: 發送的回覆訊息列表
    """
    use_plain_responses = cfg.get("use_plain_responses", False)
    max_message_length = 2000 if use_plain_responses else (4096 - len(STREAMING_INDICATOR))
    
    # 準備回覆內容塊
    response_contents = _split_content(llm_response_content or "", max_message_length)
    
    # 準備警告 embed
    warning_embed = _create_warning_embed(user_warnings, finish_reason)
    
    # 準備來源 embed
    sources_embed = _create_sources_embed(sources) if sources else None
    
    response_msgs: List[discord.Message] = []
    
    try:
        async with new_msg.channel.typing():
            # 發送第一條回覆
            first_msg = await _send_first_response(
                new_msg, 
                response_contents[0] if response_contents else "...",
                use_plain_responses,
                finish_reason,
                len(response_contents) > 1
            )
            response_msgs.append(first_msg)
            
            # 發送後續訊息
            for i, content in enumerate(response_contents[1:], 1):
                is_last = i == len(response_contents) - 1
                
                next_msg = await _send_follow_up_response(
                    new_msg.channel,
                    content,
                    use_plain_responses,
                    finish_reason,
                    not is_last
                )
                response_msgs.append(next_msg)
                
                # 添加延遲避免速率限制
                if not is_last:
                    await asyncio.sleep(0.5)
            
            # 添加警告和來源資訊
            await _add_supplementary_info(
                response_msgs[-1] if response_msgs else None,
                warning_embed,
                sources_embed,
                use_plain_responses
            )
    
    except Exception as e:
        logging.exception("發送回覆時出錯")
        try:
            error_msg = await new_msg.reply(f"發送回覆時出錯: {str(e)}")
            response_msgs.append(error_msg)
        except:
            pass
    
    return response_msgs


def _split_content(content: str, max_length: int) -> List[str]:
    """分割內容以符合 Discord 訊息長度限制"""
    if not content:
        return [""]
    
    chunks = []
    remaining = content
    
    while remaining:
        # 找到合適的分割點
        break_point = min(max_length, len(remaining))
        
        # 如果還有更多內容，嘗試在換行符處分割
        if break_point < len(remaining) and break_point > max_length // 2:
            last_newline = remaining[:break_point].rfind('\n')
            if last_newline > max_length // 2:
                break_point = last_newline
        
        chunk = remaining[:break_point]
        chunks.append(chunk)
        remaining = remaining[break_point:].lstrip()
    
    return chunks


def _create_warning_embed(user_warnings: Set[str], finish_reason: str) -> Optional[discord.Embed]:
    """建立警告 embed"""
    if not user_warnings:
        return None
    
    embed = discord.Embed(
        color=EMBED_COLOR_COMPLETE if finish_reason == "stop" else EMBED_COLOR_INCOMPLETE
    )
    
    for warning in sorted(user_warnings):
        embed.add_field(name=warning, value="", inline=False)
    
    return embed


def _create_sources_embed(sources: List[Dict[str, Any]]) -> Optional[discord.Embed]:
    """建立來源資訊 embed"""
    if not sources:
        return None
    
    embed = discord.Embed(
        title="📚 參考來源",
        color=discord.Color.blue()
    )
    
    for i, source in enumerate(sources[:5], 1):  # 限制最多 5 個來源
        title = source.get('title', f'來源 {i}')
        url = source.get('url', '')
        snippet = source.get('snippet', '')
        
        if len(title) > 256:
            title = title[:253] + "..."
        
        if len(snippet) > 1024:
            snippet = snippet[:1021] + "..."
        
        embed.add_field(
            name=f"{i}. {title}",
            value=f"[連結]({url})\n{snippet}" if url else snippet,
            inline=False
        )
    
    return embed


async def _send_first_response(
    original_msg: discord.Message,
    content: str,
    use_plain_responses: bool,
    finish_reason: str,
    has_more_parts: bool
) -> discord.Message:
    """發送第一條回覆訊息"""
    if use_plain_responses:
        return await original_msg.reply(content=content or "...", suppress_embeds=True)
    else:
        embed = discord.Embed(
            description=content + (STREAMING_INDICATOR if has_more_parts or not finish_reason else ""),
            color=EMBED_COLOR_COMPLETE if finish_reason == "stop" else EMBED_COLOR_INCOMPLETE
        )
        return await original_msg.reply(embed=embed)


async def _send_follow_up_response(
    channel: discord.TextChannel,
    content: str,
    use_plain_responses: bool,
    finish_reason: str,
    has_more_parts: bool
) -> discord.Message:
    """發送後續回覆訊息"""
    if use_plain_responses:
        return await channel.send(content=content or "...")
    else:
        embed = discord.Embed(
            description=content + (STREAMING_INDICATOR if has_more_parts or not finish_reason else ""),
            color=EMBED_COLOR_COMPLETE if finish_reason == "stop" else EMBED_COLOR_INCOMPLETE
        )
        return await channel.send(embed=embed)


async def _add_supplementary_info(
    last_msg: Optional[discord.Message],
    warning_embed: Optional[discord.Embed],
    sources_embed: Optional[discord.Embed],
    use_plain_responses: bool
):
    """添加補充資訊（警告和來源）"""
    if not last_msg:
        return
    
    try:
        # 添加警告
        if warning_embed:
            if use_plain_responses:
                await last_msg.reply(embed=warning_embed)
            else:
                # 將警告添加到最後一條訊息的 embed
                if last_msg.embeds:
                    last_embed = last_msg.embeds[0]
                    for field in warning_embed.fields:
                        last_embed.add_field(
                            name=field.name, 
                            value=field.value, 
                            inline=field.inline
                        )
                    await last_msg.edit(embed=last_embed)
                else:
                    await last_msg.reply(embed=warning_embed)
        
        # 添加來源資訊
        if sources_embed:
            await last_msg.reply(embed=sources_embed)
    
    except discord.HTTPException as e:
        logging.warning(f"添加補充資訊時出錯: {e}")


async def send_simple_reply(
    message: discord.Message,
    content: str,
    embed: Optional[discord.Embed] = None
) -> Optional[discord.Message]:
    """發送簡單回覆"""
    try:
        if embed:
            return await message.reply(content=content, embed=embed)
        else:
            return await message.reply(content=content)
    except discord.HTTPException as e:
        logging.error(f"發送簡單回覆失敗: {e}")
        return None


async def send_error_reply(message: discord.Message, error_msg: str) -> Optional[discord.Message]:
    """發送錯誤回覆"""
    embed = discord.Embed(
        title="❌ 發生錯誤",
        description=error_msg,
        color=discord.Color.red()
    )
    return await send_simple_reply(message, "", embed) 