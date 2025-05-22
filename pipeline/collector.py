import discord
import logging
import asyncio
from base64 import b64encode
from discordbot.msg_node import MsgNode, msg_nodes

async def collect_message(new_msg, cfg, discord_client_user, msg_nodes, 
                         max_text=4000, max_images=4, max_messages=10, 
                         is_casual_chat=False, httpx_client=None):
    """
    Collects and processes message content and builds the conversation history chain.
    
    Args:
        new_msg (discord.Message): The new message to process
        cfg (dict): Configuration data
        discord_client_user (discord.User): The bot's Discord user object
        msg_nodes (dict): Dictionary of message nodes for caching
        max_text (int): Maximum text length per message
        max_images (int): Maximum number of images per message
        max_messages (int): Maximum number of messages in history
        is_casual_chat (bool): Whether this is a casual conversation
        httpx_client (httpx.AsyncClient): HTTP client for fetching attachments
        
    Returns:
        dict: Dictionary containing processed messages and user warnings
    """
    messages = []
    user_warnings = set()
    curr_msg = new_msg
    
    # Log the incoming message
    logging.info(f"Message received (user ID: {new_msg.author.id}, attachments: {len(new_msg.attachments)}, conversation length: {len(messages)})")
    
    # For casual chat, get message history
    history_msgs = []
    if is_casual_chat:
        history_msgs += [m async for m in curr_msg.channel.history(before=curr_msg, limit=max_messages)][::-1]
    
    is_history_msg = False
    remaining_imgs_count = max_images
    
    # Process message chain
    while curr_msg != None and len(messages) < max_messages:
        curr_node = msg_nodes.setdefault(curr_msg.id, MsgNode())
        
        async with curr_node.lock:
            if curr_node.text == None:
                # Clean content by removing the bot's mention
                cleaned_content = curr_msg.content
                if curr_msg.content.startswith(f"<@{discord_client_user.id}>"):
                    cleaned_content = curr_msg.content.removeprefix(f"<@{discord_client_user.id}>").lstrip()
                
                # Process attachments
                good_attachments = [att for att in curr_msg.attachments 
                                   if att.content_type and any(att.content_type.startswith(x) 
                                                            for x in ("text", "image"))]
                
                attachment_responses = []
                if httpx_client and good_attachments:
                    attachment_responses = await asyncio.gather(
                        *[httpx_client.get(att.url) for att in good_attachments]
                    )
                
                # Combine text from content, embeds, and text attachments
                curr_node.text = "\n".join(
                    ([cleaned_content] if cleaned_content else [])
                    + ["\n".join(filter(None, (embed.title, embed.description, 
                                              getattr(embed.footer, "text", None))))
                       for embed in curr_msg.embeds]
                    + [resp.text for att, resp in zip(good_attachments, attachment_responses) 
                       if att.content_type.startswith("text")]
                )
                
                # Process image attachments
                curr_node.images = [
                    dict(type="image_url", image_url=dict(
                        url=f"data:{att.content_type};base64,{b64encode(resp.content).decode('utf-8')}"
                    ))
                    for att, resp in zip(good_attachments, attachment_responses)
                    if att.content_type.startswith("image")
                ]
                
                # Set role and user ID
                curr_node.role = "assistant" if curr_msg.author == discord_client_user else "user"
                curr_node.user_id = curr_msg.author.id if curr_node.role == "user" else None
                
                # Flag if there were unsupported attachments
                curr_node.has_bad_attachments = len(curr_msg.attachments) > len(good_attachments)
                
                # Try to get parent message if this is a reply
                try:
                    if curr_msg.reference and curr_msg.reference.message_id:
                        # Get from cache or fetch from Discord
                        parent_id = curr_msg.reference.message_id
                        if parent_id in msg_nodes:
                            curr_node.parent_msg = await curr_msg.channel.fetch_message(parent_id)
                        else:
                            try:
                                curr_node.parent_msg = await curr_msg.channel.fetch_message(parent_id)
                            except (discord.NotFound, discord.HTTPException):
                                curr_node.fetch_parent_failed = True
                except (discord.NotFound, discord.HTTPException):
                    curr_node.fetch_parent_failed = True
            
            # Add message content to messages list
            content = ((f'<@{curr_node.user_id}>: ' if curr_node.user_id else "" ) + curr_node.text)[:max_text]
            if imgs := curr_node.images[:remaining_imgs_count]:
                remaining_imgs_count -= len(imgs)
                content = ([dict(type="text", text=content)] if content else []) + imgs
            
            if content:
                message = dict(content=content, role=curr_node.role)
                messages.append(message)
            
            # Set next message in chain
            curr_msg = curr_node.parent_msg
            if curr_msg is None and len(history_msgs) > 0:
                curr_msg = history_msgs.pop(-1)
                is_history_msg = True
            
            # Add warnings if limits are exceeded
            if len(curr_node.text) > max_text:
                user_warnings.add(f"⚠️ Max {max_text:,} characters per message")
            if len(curr_node.images) > max_images:
                user_warnings.add(f"⚠️ Max {max_images} image{'' if max_images == 1 else 's'} per message" 
                                if max_images > 0 else "⚠️ Can't see images")
            if curr_node.has_bad_attachments:
                user_warnings.add("⚠️ Unsupported attachments")
            if curr_node.fetch_parent_failed or (curr_msg != None and len(messages) == max_messages):
                user_warnings.add(f"⚠️ Only using last {len(messages)} message{'' if len(messages) == 1 else 's'}")
    
    return {
        "messages": messages,
        "user_warnings": user_warnings
    }
