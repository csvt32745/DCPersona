import discord
import logging

def create_discord_client(cfg):
    """
    Creates and configures a Discord client instance.
    
    Args:
        cfg (dict): Configuration containing Discord client settings.
        
    Returns:
        discord.Client: Configured Discord client instance.
    """
    intents = discord.Intents.default()
    intents.message_content = True
    
    status_message = cfg.get("status_message", "github.com/jakobdylanc/llmcord")
    activity = discord.CustomActivity(name=status_message[:128])
    
    discord_client = discord.Client(intents=intents, activity=activity)
    
    # Log client ID for invite URL if available
    if client_id := cfg.get("client_id"):
        logging.info(f"\n\nBOT INVITE URL:\nhttps://discord.com/api/oauth2/authorize?client_id={client_id}&permissions=412317273088&scope=bot\n")
    
    return discord_client
