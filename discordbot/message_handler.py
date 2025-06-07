import discord
import logging
import asyncio
import httpx
from datetime import datetime
from openai import AsyncOpenAI

from core.config import reload_config
from core.utils import random_system_prompt
from core.session_manager import init_session_manager, get_session_manager, shutdown_session_manager
from discordbot.msg_node import msg_nodes, MAX_MESSAGE_NODES, MsgNode
from pipeline import collector, llm, postprocess
from pipeline.rag import init_rag_pipeline, get_rag_pipeline, process_smart_rag

# Constants
VISION_MODEL_TAGS = ("gpt-4", "o3", "o4", "claude-3", "gemini", "gemma", "llama", "pixtral", "mistral-small", "vision", "vl")
PROVIDERS_SUPPORTING_USERNAMES = ("openai", "x-ai")

# Global HTTP client for making requests
httpx_client = httpx.AsyncClient()

# 全域初始化標誌
_initialized = False

async def initialize_langgraph_systems(cfg: dict):
    """
    初始化 LangGraph 相關系統
    
    Args:
        cfg: 配置字典
    """
    global _initialized
    
    if _initialized:
        return
    
    try:
        # 檢查是否啟用 LangGraph
        langgraph_config = cfg.get("langgraph", {})
        if not langgraph_config.get("enabled", False):
            logging.info("LangGraph 功能未啟用")
            _initialized = True
            return
        
        # 初始化會話管理器
        session_file = cfg.get("development", {}).get("session_file")
        await init_session_manager(
            cleanup_interval=langgraph_config.get("cleanup_interval", 3600),
            session_timeout_hours=langgraph_config.get("session_timeout_hours", 24),
            load_from_file=session_file
        )
        
        # 初始化 RAG 流程
        await init_rag_pipeline(cfg)
        
        logging.info("✨ LangGraph 智能研究系統初始化完成")
        _initialized = True
        
    except Exception as e:
        logging.error(f"初始化 LangGraph 系統失敗: {str(e)}")
        _initialized = True  # 即使失敗也標記為已初始化，避免重複嘗試


async def on_message(new_msg: discord.Message):
    """
    Main message handler function that processes incoming Discord messages.
    Enhanced with LangGraph integration.
    
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
    
    # 初始化 LangGraph 系統（僅第一次）
    await initialize_langgraph_systems(cfg)

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
    
    # 檢查是否啟用智能研究功能
    langgraph_enabled = cfg.get("langgraph", {}).get("enabled", False)
    
    if langgraph_enabled and _initialized:
        try:
            # 使用智能 RAG 流程（可能包含 LangGraph）
            rag_result = await process_smart_rag(new_msg, collected_data, cfg)
            
            # 如果智能 RAG 產生了增強內容，整合到系統提示中
            if rag_result.get("augmented_content"):
                if rag_result.get("research_mode", False):
                    # 研究模式：LangGraph 已經通過進度訊息處理了最終答案
                    # 這裡不需要再發送額外的回覆，因為最終答案已經整合到進度訊息中
                    return
                else:
                    # 傳統模式：將增強內容加入系統提示
                    enhancement_note = f"\n\n[相關資訊補充]: {rag_result['augmented_content']}"
                    system_prompt += enhancement_note
            
        except Exception as e:
            logging.error(f"智能 RAG 處理失敗，回退到傳統流程: {str(e)}")
            # 繼續使用傳統流程
    
    # 傳統 LLM 流程
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
    
    # 定期清理舊的進度追蹤記錄（每50條消息清理一次）
    try:
        from agents.tools_and_schemas import DiscordTools
        import random
        if random.randint(1, 50) == 1:  # 2% 機率執行清理
            DiscordTools.cleanup_old_messages(max_age_seconds=3600)  # 清理超過1小時的記錄
    except Exception as e:
        logging.warning(f"定期清理進度追蹤記錄時出錯: {str(e)}")

def register_handlers(discord_client, cfg):
    """
    Registers event handlers with the Discord client.
    
    Args:
        discord_client (discord.Client): Discord client instance
        cfg (dict): Configuration data
    """
    @discord_client.event
    async def on_ready():
        """
        處理 Discord 客戶端準備就緒事件
        重新設置 logger 以防止 discord.py 覆蓋 logging 配置
        """
        from core.logger import setup_logger
        
        # 重新設置 logger，確保我們的配置不被 discord.py 覆蓋
        setup_logger(cfg)
        
        # 測試 logging 是否正常工作
        logging.info(f"🤖 Discord bot 已連接成功！登入為: {discord_client.user}")
        
        # 顯示一些連接資訊
        guild_count = len(discord_client.guilds)
        logging.info(f"📊 Bot 已連接到 {guild_count} 個伺服器")
        
        # 初始化 LangGraph 系統
        await initialize_langgraph_systems(cfg)
    
    @discord_client.event
    async def on_message(message):
        await handle_message(message)
        
    logging.info("Message handler registered")
    logging.info("Discord ready handler registered for logging fix")

async def handle_message(new_msg: discord.Message):
    """Wrapper function to avoid name conflicts with the event handler"""
    try:
        await on_message(new_msg)
    except Exception as e:
        logging.error(f"處理訊息時發生未捕獲的錯誤: {str(e)}", exc_info=True)
        try:
            await new_msg.reply(
                content="抱歉，處理妳的訊息時遇到了問題 😅 請稍後再試試看",
                suppress_embeds=True
            )
        except Exception:
            pass  # 如果連錯誤回覆都失敗，就靜默忽略


async def shutdown_handler():
    """關閉處理程序，清理資源"""
    try:
        # 清理所有進度消息記錄
        try:
            from agents.tools_and_schemas import DiscordTools
            DiscordTools.cleanup_progress_messages()
            logging.info("已清理所有進度消息記錄")
        except Exception as e:
            logging.warning(f"清理進度消息記錄時出錯: {str(e)}")
        
        # 保存會話資料
        session_manager = get_session_manager()
        if session_manager:
            await session_manager.save_to_file("sessions_backup.json")
        
        # 關閉會話管理器
        await shutdown_session_manager("sessions.json")
        
        # 關閉 HTTP 客戶端
        if httpx_client:
            await httpx_client.aclose()
        
        logging.info("訊息處理程序已安全關閉")
        
    except Exception as e:
        logging.error(f"關閉處理程序時發生錯誤: {str(e)}")


# 添加調試和統計函式
def get_handler_stats():
    """獲取處理程序統計資訊"""
    try:
        from pipeline.rag import get_rag_pipeline
        
        stats = {
            "initialized": _initialized,
            "message_nodes_count": len(msg_nodes),
            "langgraph_available": False,
            "session_stats": None,
        }
        
        # 獲取 RAG 統計
        if _initialized:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果在事件迴圈中，使用 create_task
                    # 這裡簡化處理，實際使用時可能需要更複雜的邏輯
                    pass
                else:
                    rag_pipeline = loop.run_until_complete(get_rag_pipeline())
                    if rag_pipeline:
                        rag_stats = rag_pipeline.get_research_stats()
                        stats.update(rag_stats)
            except Exception:
                pass
        
        return stats
        
    except Exception as e:
        logging.error(f"獲取處理程序統計失敗: {str(e)}")
        return {"error": str(e)}
