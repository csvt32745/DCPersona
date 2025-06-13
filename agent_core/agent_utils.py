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


def resolve_urls(urls_to_resolve: List[Any], id: int) -> Dict[str, str]:
    """
    將 Vertex AI 搜尋的長 URL 轉換為短 URL，並為每個 URL 分配唯一 ID
    確保每個原始 URL 都能獲得一致的縮短形式，同時保持唯一性
    
    Args:
        urls_to_resolve: 需要解析的 URL 列表
        id: 唯一識別符
        
    Returns:
        Dict[str, str]: 原始 URL 到短 URL 的對應字典
    """
    prefix = f"https://vertexaisearch.cloud.google.com/id/"
    urls = [site.web.uri for site in urls_to_resolve]

    # 創建字典，將每個唯一 URL 對應到其第一次出現的索引
    resolved_map = {}
    for idx, url in enumerate(urls):
        if url not in resolved_map:
            resolved_map[url] = f"{prefix}{id}-{idx}"

    return resolved_map


def insert_citation_markers(text, citations_list):
    """
    根據開始和結束索引在文本字串中插入引用標記
    
    Args:
        text (str): 原始文本字串
        citations_list (list): 引用字典列表，每個字典包含
                               'start_index', 'end_index', 和
                               'segment_string' (要插入的標記)
                               索引假設為原始文本的索引
                               
    Returns:
        str: 插入引用標記後的文本
    """
    # 按 end_index 降序排序引用
    # 如果 end_index 相同，則按 start_index 降序進行二次排序
    # 這確保在字串末尾的插入不會影響仍需處理的字串早期部分的索引
    sorted_citations = sorted(
        citations_list, key=lambda c: (c["end_index"], c["start_index"]), reverse=True
    )

    modified_text = text
    for citation_info in sorted_citations:
        # 這些索引指向*原始*文本中的位置，
        # 但由於我們從末尾開始迭代，它們對於相對於已處理的字串部分的插入仍然有效
        end_idx = citation_info["end_index"]
        marker_to_insert = ""
        for segment in citation_info["segments"]:
            marker_to_insert += f" [{segment['label']}]({segment['short_url']})"
        # 在原始 end_idx 位置插入引用標記
        modified_text = (
            modified_text[:end_idx] + marker_to_insert + modified_text[end_idx:]
        )

    return modified_text


def get_citations(response, resolved_urls_map):
    """
    從 Gemini 模型的回應中提取並格式化引用資訊
    
    此函數處理回應中提供的 grounding metadata 來構建引用對象列表。
    每個引用對象包含它所指向的文本段的開始和結束索引，
    以及包含格式化的 markdown 連結到支持網頁塊的字串。
    
    Args:
        response: Gemini 模型的回應對象，預期具有包含
                  `candidates[0].grounding_metadata` 的結構。
                  它還依賴於其作用域中可用的 `resolved_map` 
                  來將塊 URI 對應到解析的 URL。
                  
    Returns:
        list: 字典列表，其中每個字典代表一個引用，具有以下鍵：
              - "start_index" (int): 引用段在原始文本中的起始字符索引。
                                     如果未指定，則預設為 0。
              - "end_index" (int): 緊接引用段結束後的字符索引（不包含）。
              - "segments" (list[str]): 每個 grounding 塊的個別 markdown 格式連結列表。
              - "segment_string" (str): 引用的所有 markdown 格式連結的連接字串。
              如果沒有找到有效的候選者或 grounding supports，
              或者缺少重要資料，則返回空列表。
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
        or not candidate.grounding_metadata.grounding_supports
    ):
        return citations

    for support in candidate.grounding_metadata.grounding_supports:
        citation = {}

        # 確保段資訊存在
        if not hasattr(support, "segment") or support.segment is None:
            continue  # 如果缺少段資訊，跳過此支持

        start_index = (
            support.segment.start_index
            if support.segment.start_index is not None
            else 0
        )

        # 確保 end_index 存在以形成有效段
        if support.segment.end_index is None:
            continue  # 如果缺少 end_index，跳過，因為它是關鍵的

        # 將 1 加到 end_index 以使其成為切片/範圍目的的不包含結束
        # （假設 API 提供包含的 end_index）
        citation["start_index"] = start_index
        citation["end_index"] = support.segment.end_index

        citation["segments"] = []
        if (
            hasattr(support, "grounding_chunk_indices")
            and support.grounding_chunk_indices
            and hasattr(candidate.grounding_metadata, "grounding_chunks")
            and candidate.grounding_metadata.grounding_chunks
        ):
            for ind in support.grounding_chunk_indices:
                try:
                    chunk = candidate.grounding_metadata.grounding_chunks[ind]
                    resolved_url = resolved_urls_map.get(chunk.web.uri, None)
                    citation["segments"].append(
                        {
                            "label": chunk.web.title.split(".")[:-1][0],
                            "short_url": resolved_url,
                            "value": chunk.web.uri,
                        }
                    )
                except (IndexError, AttributeError, NameError):
                    # 處理 chunk、web、uri 或 resolved_map 可能有問題的情況
                    # 為了簡單起見，我們只會跳過添加這個特定的段連結
                    # 在生產系統中，您可能想要記錄這個。
                    pass
        citations.append(citation)
    return citations 