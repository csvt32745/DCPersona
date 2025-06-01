import discord
import logging
import asyncio
import httpx
from datetime import datetime
from openai import AsyncOpenAI

from core.config import reload_config
from core.utils import random_system_prompt
from discordbot.msg_node import msg_nodes, MAX_MESSAGE_NODES, MsgNode
from pipeline import collector, llm, postprocess

# Constants
VISION_MODEL_TAGS = ("gpt-4", "o3", "o4", "claude-3", "gemini", "gemma", "llama", "pixtral", "mistral-small", "vision", "vl")
PROVIDERS_SUPPORTING_USERNAMES = ("openai", "x-ai")

# Global HTTP client for making requests
httpx_client = httpx.AsyncClient()

async def on_message(new_msg: discord.Message):
    """
    Main message handler function that processes incoming Discord messages.
    
    Args:
        new_msg (discord.Message): The incoming Discord message
    """
    # Check if message is a DM or a mention
    is_dm = new_msg.channel.type == discord.ChannelType.private
    if (not is_dm and new_msg.guild.me not in new_msg.mentions) or new_msg.author.bot:
        return

    # Extract role and channel IDs for permission checking
    role_ids = set(role.id for role in getattr(new_msg.author, "roles", ()))
    channel_ids = set(filter(None, (new_msg.channel.id, getattr(new_msg.channel, "parent_id", None), getattr(new_msg.channel, "category_id", None))))

    # Reload config to get fresh settings
    cfg = reload_config()

    # Check maintenance mode
    is_maintainance = cfg.get("is_maintainance", False)
    if is_maintainance:
        await new_msg.reply(content=cfg.get('maintainance_resp', "Bot is currently in maintenance mode."), suppress_embeds=True)
        return

    # Check permissions
    allow_dms = cfg.get("allow_dms", True)
    permissions = cfg.get("permissions", {"users": {}, "roles": {}, "channels": {}})
    
    (allowed_user_ids, blocked_user_ids) = (permissions.get("users", {}).get("allowed_ids", []), 
                                          permissions.get("users", {}).get("blocked_ids", []))
    (allowed_role_ids, blocked_role_ids) = (permissions.get("roles", {}).get("allowed_ids", []), 
                                          permissions.get("roles", {}).get("blocked_ids", []))
    (allowed_channel_ids, blocked_channel_ids) = (permissions.get("channels", {}).get("allowed_ids", []), 
                                                permissions.get("channels", {}).get("blocked_ids", []))

    allow_all_users = not allowed_user_ids if is_dm else not allowed_user_ids and not allowed_role_ids
    is_good_user = allow_all_users or new_msg.author.id in allowed_user_ids or any(id in allowed_role_ids for id in role_ids)
    is_bad_user = not is_good_user or new_msg.author.id in blocked_user_ids or any(id in blocked_role_ids for id in role_ids)

    allow_all_channels = not allowed_channel_ids
    is_good_channel = allow_dms if is_dm else allow_all_channels or any(id in allowed_channel_ids for id in channel_ids)
    is_bad_channel = not is_good_channel or any(id in blocked_channel_ids for id in channel_ids)

    if is_bad_user or is_bad_channel:
        if is_bad_channel:
            await new_msg.reply(content=cfg.get('reject_resp', "I'm not allowed to respond in this channel."), suppress_embeds=True)
        return
    
    # Initialize OpenAI client
    provider_slash_model = cfg.get("model", "openai/gpt-3.5-turbo")
    provider, model = provider_slash_model.split("/", 1)
    base_url = cfg.get("providers", {}).get(provider, {}).get("base_url", "https://api.openai.com/v1")
    api_key = cfg.get("providers", {}).get(provider, {}).get("api_key", "sk-no-key-required")
    openai_client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    # Determine model capabilities
    accept_images = any(x in model.lower() for x in VISION_MODEL_TAGS)
    accept_usernames = provider.lower() in PROVIDERS_SUPPORTING_USERNAMES

    # Get configuration limits
    max_text = cfg.get("max_text", 4000)
    max_images = cfg.get("max_images", 4) if accept_images else 0
    max_messages = cfg.get("max_messages", 10)
    
    # Set system prompt
    is_casual_chat = any([text in new_msg.content for text in ["你怎麼想", "你認為呢", "你覺得呢", "如何"]])
    system_prompt = random_system_prompt() if cfg.get("is_random_system_prompt", False) else cfg.get('system_prompt', "You are a helpful AI assistant.")
    
    # Process and collect messages
    collected_data = await collector.collect_message(
        new_msg=new_msg,
        cfg=cfg,
        discord_client_user=new_msg.guild.me if not is_dm else new_msg.channel.me,
        msg_nodes=msg_nodes,
        max_text=max_text,
        max_images=max_images,
        max_messages=max_messages,
        is_casual_chat=is_casual_chat,
        httpx_client=httpx_client
    )
    
    messages = collected_data["messages"]
    user_warnings = collected_data["user_warnings"]
    
    # Build LLM input
    system_prompt_parts = [system_prompt]
    messages = llm.build_llm_input(
        collected_messages=messages, 
        system_prompt_parts=system_prompt_parts,
        cfg=cfg, 
        discord_client_user_id=new_msg.guild.me.id if not is_dm else new_msg.channel.me.id,
        accept_usernames=accept_usernames
    )
    
    # Call LLM API
    tools = []
    if cfg.get("allow_google_search", False):
        tools = llm.google_search_tool
        
    llm_response = await llm.call_llm_api(
        openai_client=openai_client, 
        model_name=model, 
        messages=messages, 
        tools=tools, 
        cfg=cfg
    )
    
    # Process and send response
    await postprocess.format_llm_output_and_reply(
        llm_response_content=llm_response["content"],
        finish_reason=llm_response["finish_reason"],
        new_msg=new_msg,
        user_warnings=user_warnings,
        cfg=cfg,
        msg_nodes=msg_nodes
    )
    
    # Clean up old message nodes to prevent memory leaks
    if (num_nodes := len(msg_nodes)) > MAX_MESSAGE_NODES:
        for msg_id in sorted(msg_nodes.keys())[: num_nodes - MAX_MESSAGE_NODES]:
            async with msg_nodes.get(msg_id, MsgNode()).lock:
                msg_nodes.pop(msg_id, None)

def register_handlers(discord_client, cfg):
    """
    Registers event handlers with the Discord client.
    
    Args:
        discord_client (discord.Client): Discord client instance
        cfg (dict): Configuration data
    """
    @discord_client.event
    async def on_message(message):
        await handle_message(message)
        
    logging.info("Message handler registered")

async def handle_message(new_msg: discord.Message):
    """Wrapper function to avoid name conflicts with the event handler"""
    await on_message(new_msg)
