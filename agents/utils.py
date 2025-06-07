"""
Agent 工具函式

基於 gemini-fullstack-langgraph-quickstart 的工具函式，
適配到 Discord 環境並添加中文和會話管理支援。
"""

import hashlib
import uuid
from typing import Any, Dict, List, Optional
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage
from datetime import datetime
import discord
import re


def get_research_topic(messages: List[AnyMessage]) -> str:
    """
    從訊息列表中提取研究主題
    
    Args:
        messages: LangChain 訊息列表
        
    Returns:
        str: 研究主題字串
    """
    # 檢查是否有歷史對話，將訊息合併為單一字串
    if len(messages) == 1:
        research_topic = messages[-1].content
    else:
        research_topic = ""
        for message in messages:
            if isinstance(message, HumanMessage):
                research_topic += f"使用者: {message.content}\n"
            elif isinstance(message, AIMessage):
                research_topic += f"初華: {message.content}\n"
    
    return research_topic


def resolve_urls(urls_to_resolve: List[Any], id: int) -> Dict[str, str]:
    """
    將長 URL 對應到短 URL，確保每個原始 URL 獲得一致的短網址形式，同時保持唯一性
    
    Args:
        urls_to_resolve: 需要解析的 URL 列表
        id: 唯一 ID
        
    Returns:
        Dict[str, str]: URL 對應字典
    """
    prefix = f"https://research.hatsuhana.moe/ref/"
    
    # 處理不同的 URL 結構
    if hasattr(urls_to_resolve[0], 'web'):
        urls = [site.web.uri for site in urls_to_resolve]
    else:
        urls = [str(url) for url in urls_to_resolve]

    # 創建字典，將每個唯一 URL 對應到其第一次出現的索引
    resolved_map = {}
    for idx, url in enumerate(urls):
        if url not in resolved_map:
            resolved_map[url] = f"{prefix}{id}-{idx}"

    return resolved_map


def insert_citation_markers(text: str, citations_list: List[Dict[str, Any]]) -> str:
    """
    根據開始和結束索引在文字字串中插入引用標記
    
    Args:
        text: 原始文字字串
        citations_list: 引用資訊列表，每個字典包含 'start_index', 'end_index' 和 'segments'
        
    Returns:
        str: 插入引用標記後的文字
    """
    # 按 end_index 降序排序，如果 end_index 相同則按 start_index 降序排序
    # 這確保在字串末尾的插入不會影響仍需處理的字串早期部分的索引
    sorted_citations = sorted(
        citations_list, key=lambda c: (c["end_index"], c["start_index"]), reverse=True
    )

    modified_text = text
    for citation_info in sorted_citations:
        # 這些索引指向原始文字中的位置，但由於我們從末尾開始迭代，
        # 它們對於相對於已處理字串部分的插入仍然有效
        end_idx = citation_info["end_index"]
        marker_to_insert = ""
        for segment in citation_info["segments"]:
            marker_to_insert += f" [{segment['label']}]({segment['short_url']})"
        
        # 在原始 end_idx 位置插入引用標記
        modified_text = (
            modified_text[:end_idx] + marker_to_insert + modified_text[end_idx:]
        )

    return modified_text


def get_citations(response: Any, resolved_urls_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    從 Gemini 模型回應中提取和格式化引用資訊
    
    Args:
        response: Gemini 模型的回應物件
        resolved_urls_map: URL 解析對應字典
        
    Returns:
        List[Dict]: 引用資訊列表
    """
    citations = []

    # 確保回應和必要的嵌套結構存在
    if not response or not response.candidates:
        return citations

    candidate = response.candidates[0]
    if (
        not hasattr(candidate, "grounding_metadata")
        or not candidate.grounding_metadata
        or not hasattr(candidate.grounding_metadata, "grounding_supports")
    ):
        return citations

    for support in candidate.grounding_metadata.grounding_supports:
        citation = {}

        # 確保段落資訊存在
        if not hasattr(support, "segment") or support.segment is None:
            continue  # 如果段落資訊缺失則跳過此支持

        start_index = (
            support.segment.start_index
            if support.segment.start_index is not None
            else 0
        )

        # 確保 end_index 存在以形成有效段落
        if support.segment.end_index is None:
            continue  # 如果 end_index 缺失則跳過，因為它是關鍵的

        citation["start_index"] = start_index
        citation["end_index"] = support.segment.end_index

        citation["segments"] = []
        if (
            hasattr(support, "grounding_chunk_indices")
            and support.grounding_chunk_indices
        ):
            for ind in support.grounding_chunk_indices:
                try:
                    chunk = candidate.grounding_metadata.grounding_chunks[ind]
                    resolved_url = resolved_urls_map.get(chunk.web.uri, None)
                    citation["segments"].append(
                        {
                            "label": chunk.web.title.split(".")[:-1][0] if chunk.web.title else "來源",
                            "short_url": resolved_url,
                            "value": chunk.web.uri,
                        }
                    )
                except (IndexError, AttributeError, NameError):
                    # 處理 chunk、web、uri 或 resolved_map 可能有問題的情況
                    # 為了簡單起見，我們只是跳過添加這個特定的段落連結
                    pass
        citations.append(citation)
    return citations


# Discord 特定工具函式
def generate_session_id(user_id: int, channel_id: int) -> str:
    """
    生成唯一的會話 ID
    
    Args:
        user_id: Discord 使用者 ID
        channel_id: Discord 頻道 ID
        
    Returns:
        str: 會話 ID
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")  # 包含微秒
    random_uuid = str(uuid.uuid4())[:8]  # 添加隨機UUID以確保唯一性
    unique_str = f"{user_id}_{channel_id}_{timestamp}_{random_uuid}"
    hash_obj = hashlib.md5(unique_str.encode())
    return f"session_{hash_obj.hexdigest()[:8]}"


def extract_discord_context(message: discord.Message) -> Dict[str, Any]:
    """
    從 Discord 訊息中提取上下文資訊
    
    Args:
        message: Discord 訊息物件
        
    Returns:
        Dict: 上下文資訊
    """
    return {
        "user_id": message.author.id,
        "user_name": message.author.display_name,
        "channel_id": message.channel.id,
        "channel_name": getattr(message.channel, 'name', 'DM'),
        "guild_id": message.guild.id if message.guild else None,
        "guild_name": message.guild.name if message.guild else None,
        "is_dm": message.guild is None,
        "message_id": message.id,
        "timestamp": message.created_at.isoformat(),
        "content": message.content,
    }


def analyze_message_complexity(content: str) -> Dict[str, Any]:
    """
    分析訊息複雜度以決定是否使用研究模式
    
    Args:
        content: 訊息內容
        
    Returns:
        Dict: 複雜度分析結果
    """
    content_lower = content.lower()
    
    # 複雜度指標
    indicators = {
        "length": len(content.split()) > 15,  # 長文本
        "multiple_questions": content.count("?") > 1 or content.count("？") > 1,  # 多個問題
        "comparison_words": any(word in content_lower for word in 
                               ["比較", "對比", "差異", "優缺點", "vs", "versus"]),
        "research_keywords": any(word in content_lower for word in 
                                ["研究", "調查", "分析", "詳細", "深入", "為什麼", "如何"]),
        "current_info": any(word in content_lower for word in 
                           ["最新", "2024", "2025", "現在", "目前", "今年"]),
        "technical_terms": len(re.findall(r'[A-Z]{2,}|[a-z]+[A-Z][a-z]*', content)) > 2,
    }
    
    # 計算複雜度評分
    complexity_score = sum(indicators.values()) / len(indicators)
    
    # 檢測到的關鍵字
    detected_keywords = []
    if indicators["comparison_words"]:
        detected_keywords.append("比較分析")
    if indicators["research_keywords"]:
        detected_keywords.append("研究關鍵字")
    if indicators["current_info"]:
        detected_keywords.append("時效性資訊")
    
    return {
        "complexity_score": complexity_score,
        "indicators": indicators,
        "detected_keywords": detected_keywords,
        "use_research": complexity_score >= 0.4,  # 閾值可調整
    }


def format_time_elapsed(start_time: datetime) -> str:
    """
    格式化經過的時間
    
    Args:
        start_time: 開始時間
        
    Returns:
        str: 格式化的時間字串
    """
    elapsed = datetime.now() - start_time
    
    if elapsed.total_seconds() < 60:
        return f"{int(elapsed.total_seconds())}秒"
    elif elapsed.total_seconds() < 3600:
        return f"{int(elapsed.total_seconds() // 60)}分鐘"
    else:
        hours = int(elapsed.total_seconds() // 3600)
        minutes = int((elapsed.total_seconds() % 3600) // 60)
        return f"{hours}小時{minutes}分鐘"


def clean_and_truncate_text(text: str, max_length: int = 1900) -> str:
    """
    清理和截斷文字以適應 Discord 限制
    
    Args:
        text: 原始文字
        max_length: 最大長度
        
    Returns:
        str: 清理後的文字
    """
    # 移除多餘的空白和換行
    cleaned = re.sub(r'\n\s*\n', '\n\n', text.strip())
    cleaned = re.sub(r' +', ' ', cleaned)
    
    # 如果超過長度限制，智能截斷
    if len(cleaned) <= max_length:
        return cleaned
    
    # 嘗試在句號處截斷
    sentences = cleaned.split('。')
    result = ""
    for sentence in sentences:
        if len(result + sentence + "。") <= max_length - 3:  # 預留 "..." 空間
            result += sentence + "。"
        else:
            break
    
    if result:
        return result + "..."
    else:
        # 如果沒有找到合適的句號截斷點，直接截斷
        return cleaned[:max_length - 3] + "..."


def extract_mentions_and_channels(content: str) -> Dict[str, List[str]]:
    """
    從內容中提取提及和頻道
    
    Args:
        content: 訊息內容
        
    Returns:
        Dict: 提取的提及和頻道資訊
    """
    # Discord 提及格式：<@user_id>, <#channel_id>, <@&role_id>
    user_mentions = re.findall(r'<@!?(\d+)>', content)
    channel_mentions = re.findall(r'<#(\d+)>', content)
    role_mentions = re.findall(r'<@&(\d+)>', content)
    
    return {
        "user_mentions": user_mentions,
        "channel_mentions": channel_mentions,
        "role_mentions": role_mentions,
    }


def create_safe_filename(text: str, max_length: int = 50) -> str:
    """
    創建安全的檔案名稱
    
    Args:
        text: 原始文字
        max_length: 最大長度
        
    Returns:
        str: 安全的檔案名稱
    """
    # 移除不安全的字符
    safe_text = re.sub(r'[<>:"/\\|?*]', '', text)
    safe_text = re.sub(r'[^\w\s-]', '', safe_text).strip()
    safe_text = re.sub(r'[-\s]+', '_', safe_text)
    
    # 截斷到最大長度
    if len(safe_text) > max_length:
        safe_text = safe_text[:max_length]
    
    return safe_text


def validate_research_query(query: str) -> tuple[bool, str]:
    """
    驗證研究查詢的有效性
    
    Args:
        query: 查詢字串
        
    Returns:
        tuple: (是否有效, 錯誤訊息)
    """
    if not query or len(query.strip()) == 0:
        return False, "查詢不能為空"
    
    if len(query) > 500:
        return False, "查詢過長，請縮短問題"
    
    # 檢查是否包含不當內容
    inappropriate_terms = [
        "illegal", "harmful", "dangerous", "violence",
        "非法", "有害", "危險", "暴力"
    ]
    
    query_lower = query.lower()
    if any(term in query_lower for term in inappropriate_terms):
        return False, "查詢包含不當內容"
    
    # 檢查是否是有意義的查詢
    if len(query.split()) < 2:
        return False, "請提供更詳細的問題"
    
    return True, "查詢有效"


def get_language_from_content(content: str) -> str:
    """
    從內容中檢測語言
    
    Args:
        content: 文字內容
        
    Returns:
        str: 語言代碼 ('zh', 'en', 'ja', etc.)
    """
    # 簡單的語言檢測
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
    japanese_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff]', content))
    english_chars = len(re.findall(r'[a-zA-Z]', content))
    
    total_chars = len(content)
    
    if total_chars == 0:
        return 'zh'  # 預設中文
    
    if chinese_chars / total_chars > 0.3:
        return 'zh'
    elif japanese_chars / total_chars > 0.3:
        return 'ja'
    elif english_chars / total_chars > 0.5:
        return 'en'
    else:
        return 'zh'  # 預設中文