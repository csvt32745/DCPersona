import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, AsyncGenerator
from openai import AsyncOpenAI
import pytz

# Google Search tool definition
google_search_tool: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "perform_Google_Search",
            "description": "當需要查詢最新資訊、事件、人物或不確定的事實時，執行 Google 搜尋",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要執行的 Google 搜尋查詢字詞",
                    },
                },
                "required": ["query"],
            },
        }
    }
]

def build_llm_input(collected_messages: List[Dict[str, str]], 
                   system_prompt_parts: List[str], 
                   cfg: Dict[str, Any], 
                   discord_client_user_id: int,
                   accept_usernames: bool = False, 
                   datetime_now: Optional[datetime] = None) -> List[Dict[str, str]]:
    """
    Builds the final input for the LLM by combining system prompt and messages.
    
    Args:
        collected_messages (list): List of collected conversation messages
        system_prompt_parts (list): List of system prompt components
        cfg (dict): Configuration data
        discord_client_user_id (int): ID of the bot
        accept_usernames (bool): Whether the LLM supports usernames
        datetime_now (datetime): Current datetime (defaults to now)
        
    Returns:
        list: Final messages list ready for LLM input
    """
    if datetime_now is None:
        tz = pytz.timezone("Asia/Taipei")
        datetime_now = datetime.now(tz)
    else:
        # If datetime_now is naive, localize it to Asia/Taipei
        if datetime_now.tzinfo is None:
            tz = pytz.timezone("Asia/Taipei")
            datetime_now = tz.localize(datetime_now)
        else:
            datetime_now = datetime_now.astimezone(pytz.timezone("Asia/Taipei"))
        
    # Add additional information to system prompt
    detailed_time: str = datetime_now.strftime("%Y-%m-%d %A %H:%M")
    system_prompt_extras: List[str] = [f"Today's date and time: {detailed_time}."]
    if accept_usernames:
        system_prompt_extras.append(f"{discord_client_user_id} 是你的 ID，如果有人提到 {discord_client_user_id} 就是在說你")
        system_prompt_extras.append("User's names are their Discord IDs and should be typed as '<@ID>'.")
    
    # Create final system prompt
    full_system_prompt: str = "\n".join(system_prompt_parts + system_prompt_extras)
    
    # Add system message to the beginning of the messages list
    final_messages: List[Dict[str, str]] = collected_messages.copy()
    final_messages.append(dict(role="system", content=full_system_prompt))
    
    # Reverse message order (older messages first)
    final_messages = final_messages[::-1]
    
    return final_messages

async def call_llm_api(
    openai_client: AsyncOpenAI,
    model_name: str,
    messages: List[Dict[str, str]],
    tools: Optional[List[Dict[str, Any]]] = None,
    cfg: Optional[Dict[str, Any]] = None
) -> Dict[str, Union[str, None]]:
    """
    Calls the LLM API with the prepared messages and handles the response.

    Args:
        openai_client (AsyncOpenAI): OpenAI client instance
        model_name (str): Name of the model to use
        messages (List[Dict[str, str]]): Messages to send to the LLM
        tools (Optional[List[Dict[str, Any]]]): List of tools available to the LLM
        cfg (Optional[Dict[str, Any]]): Configuration data

    Returns:
        Dict[str, Union[str, None]]: Response content and finish reason
    """
    if cfg is None:
        cfg = {}

    extra_api_parameters: Dict[str, Any] = cfg.get("extra_api_parameters", {})

    # Prepare the API call kwargs
    kwargs: Dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "stream": True,
        "extra_body": extra_api_parameters
    }

    # Add tools if available
    if tools:
        kwargs["tools"] = tools

    try:
        content: str = ""
        finish_reason: Optional[str] = None

        # Make the API call
        async for chunk in await openai_client.chat.completions.create(**kwargs):
            delta = chunk.choices[0].delta

            # Check for function calls
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                for tool_call in delta.tool_calls:
                    if tool_call.type == "function" and tool_call.function.name == "perform_Google_Search":
                        # This is a placeholder - in Phase 2 we'll implement the actual Google Search
                        query: str = tool_call.function.arguments.get("query", "")
                        logging.info(f"LLM requested Google Search for: {query}")
                        # In Phase 1, just add a note that this would trigger a search
                        content += f"\n[Note: Would search Google for: '{query}' in Phase 2]\n"

            # Add text content
            if delta.content:
                content += delta.content

            # Check if generation is complete
            if chunk.choices[0].finish_reason:
                finish_reason = chunk.choices[0].finish_reason

    except Exception as e:
        logging.exception("Error calling LLM API")
        content = f"Error generating response: {str(e)}"
        finish_reason = "error"

    return {
        "content": content,
        "finish_reason": finish_reason
    }
