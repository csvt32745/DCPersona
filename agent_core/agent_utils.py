"""
Agent 核心邏輯相關的輔助函數

包含與 Agent 核心流程強相關的輔助函式，如引用處理、研究主題獲取等。
"""

from typing import Any, Dict, List, Union
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage


def _extract_text_content(content: Union[str, List[Dict[str, Any]]]) -> str:
    """
    安全地從多模態內容中提取文字部分
    
    Args:
        content: 可能是字串或多模態列表的內容
        
    Returns:
        str: 提取的文字內容
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        # 從多模態列表中提取文字部分
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif item.get("type") == "image_url":
                    # 對於圖片，添加描述性文字
                    text_parts.append("[圖片]")
        return " ".join(text_parts)
    else:
        return str(content)


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