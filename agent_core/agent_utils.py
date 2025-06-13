"""
Agent 核心邏輯相關的輔助函數

包含與 Agent 核心流程強相關的輔助函式，如引用處理、研究主題獲取等。
"""

from typing import Any, Dict, List
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage


def get_research_topic(messages: List[AnyMessage]) -> str:
    """
    從訊息中獲取研究主題
    
    Args:
        messages: 訊息列表
        
    Returns:
        str: 研究主題字串
    """
    # 檢查是否有歷史訊息，將訊息組合成單一字串
    if len(messages) == 1:
        research_topic = messages[-1].content
    else:
        research_topic = ""
        for message in messages:
            if isinstance(message, HumanMessage):
                research_topic += f"用戶: {message.content}\n"
            elif isinstance(message, AIMessage):
                research_topic += f"助手: {message.content}\n"
    return research_topic


def resolve_urls(grounding_chunks: List[Any], task_id: str) -> Dict[str, str]:
    """
    根據 grounding_chunks 解析和映射 URL，生成短 URL 或標記。
    
    Args:
        grounding_chunks: 包含來源資訊的 grounding 塊列表。
        task_id: 任務 ID，用於生成唯一標記。
        
    Returns:
        Dict[str, str]: 原始 URL 到短 URL 或標記的映射。
    """
    resolved_urls = {}
    if not grounding_chunks:
        return resolved_urls
    
    for idx, chunk in enumerate(grounding_chunks):
        if hasattr(chunk, 'web_archive_url') and chunk.web_archive_url:
            original_url = chunk.web_archive_url
            # 使用一個簡單的遞增數字作為短 URL 標記
            resolved_urls[original_url] = f"url{task_id}_{idx+1}"
        elif hasattr(chunk, 'uri') and chunk.uri:
            original_url = chunk.uri
            resolved_urls[original_url] = f"url{task_id}_{idx+1}"
    return resolved_urls 