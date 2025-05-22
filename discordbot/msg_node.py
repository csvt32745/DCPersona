import asyncio
import discord
from dataclasses import dataclass, field
from typing import Literal, Optional, List, Dict, Any

# Maximum number of message nodes to keep in memory
MAX_MESSAGE_NODES = 100

@dataclass
class MsgNode:
    """
    Class representing a message node in the conversation.
    Used for caching message content and maintaining conversation history.
    """
    text: Optional[str] = None
    images: List[Dict[str, Any]] = field(default_factory=list)

    role: Literal["user", "assistant"] = "assistant"
    user_id: Optional[int] = None

    has_bad_attachments: bool = False
    fetch_parent_failed: bool = False

    parent_msg: Optional[discord.Message] = None

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

# Global dictionary to store message nodes
msg_nodes: Dict[str, MsgNode] = {}
