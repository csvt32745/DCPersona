import discord
import asyncio
import logging
from discordbot.msg_node import MsgNode
from typing import Dict, Any, Set, List

# Constants
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
    msg_nodes: Dict[int, MsgNode]
) -> None:
    """
    Formats the LLM response and sends it as a reply on Discord.
    
    Args:
        llm_response_content (str): Content from the LLM
        finish_reason (str): Reason why the LLM finished generating
        new_msg (discord.Message): Original message to reply to
        user_warnings (set): Set of warning messages to display to user
        cfg (dict): Configuration data
        msg_nodes (dict): Dictionary of message nodes
    """
    use_plain_responses = cfg.get("use_plain_responses", False)
    max_message_length = 2000 if use_plain_responses else (4096 - len(STREAMING_INDICATOR))
    
    # Prepare response chunks if content is too long
    response_contents = []
    remaining_content = llm_response_content or ""
    
    while remaining_content:
        # Find a good breaking point
        break_point = min(max_message_length, len(remaining_content))
        
        # If we have more content than fits in one message, try to break at a newline
        if break_point < len(remaining_content) and break_point > max_message_length // 2:
            last_newline = remaining_content[:break_point].rfind('\n')
            if last_newline > max_message_length // 2:
                break_point = last_newline
        
        chunk = remaining_content[:break_point]
        response_contents.append(chunk)
        remaining_content = remaining_content[break_point:].lstrip()
    
    # Prepare embed for warnings if any
    embed = None
    if user_warnings:
        embed = discord.Embed(color=EMBED_COLOR_COMPLETE if finish_reason == "stop" else EMBED_COLOR_INCOMPLETE)
        for warning in sorted(user_warnings):
            embed.add_field(name=warning, value="", inline=False)
    
    response_msgs: List[discord.Message] = []
    
    try:
        async with new_msg.channel.typing():
            # Send first message as a reply
            if use_plain_responses:
                response_msg = await new_msg.reply(content=response_contents[0] or "...", suppress_embeds=True)
            else:
                response_msg = await new_msg.reply(
                    embed=discord.Embed(
                        description=response_contents[0] + (STREAMING_INDICATOR if len(response_contents) > 1 or not finish_reason else ""),
                        color=EMBED_COLOR_COMPLETE if finish_reason == "stop" else EMBED_COLOR_INCOMPLETE
                    )
                )
            
            response_msgs.append(response_msg)
            
            # For multi-part responses
            for i, content in enumerate(response_contents[1:], 1):
                is_last = i == len(response_contents) - 1
                
                if use_plain_responses:
                    next_msg = await new_msg.channel.send(content=content or "...")
                else:
                    next_msg = await new_msg.channel.send(
                        embed=discord.Embed(
                            description=content + (STREAMING_INDICATOR if not is_last or not finish_reason else ""),
                            color=EMBED_COLOR_COMPLETE if finish_reason == "stop" else EMBED_COLOR_INCOMPLETE
                        )
                    )
                
                response_msgs.append(next_msg)
                
                # Add a delay between messages to avoid rate limits
                if not is_last:
                    await asyncio.sleep(0.5)
            
            # If we have warnings, edit the last message to include them
            if user_warnings and response_msgs:
                last_msg = response_msgs[-1]
                
                if use_plain_responses:
                    await last_msg.reply(embed=embed)
                else:
                    last_embed = last_msg.embeds[0] if last_msg.embeds else discord.Embed()
                    for field in embed.fields:
                        last_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                    await last_msg.edit(embed=last_embed)
    
    except Exception as e:
        logging.exception("Error sending response")
        try:
            await new_msg.reply(f"Error sending response: {str(e)}")
        except:
            pass
    
    # Store response in msg_nodes
    for response_msg in response_msgs:
        if response_msg.id in msg_nodes:
            msg_node = msg_nodes[response_msg.id]
            msg_node.text = "".join(response_contents)
            # Release lock if it's held
            try:
                msg_node.lock.release()
            except RuntimeError:
                pass
