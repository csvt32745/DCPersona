from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class MsgNode:
    """結構化訊息節點。"""
    role: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OverallState:
    """統一代理狀態 (簡化版)。"""
    messages: List[MsgNode] = field(default_factory=list)
    tool_round: int = 0
    finished: bool = False
    
    # LangGraph 狀態欄位
    needs_tools: bool = False
    search_queries: List[str] = field(default_factory=list)
    research_topic: str = ""
    available_tools: List[str] = field(default_factory=list)
    selected_tool: Optional[str] = None
    tool_results: List[str] = field(default_factory=list)
    is_sufficient: bool = False
    reflection_complete: bool = False
    final_answer: str = ""


@dataclass
class DiscordProgressUpdate:
    """Discord 進度更新結構"""
    stage: str  # 當前階段
    message: str  # 進度訊息
    progress_percentage: Optional[int] = None  # 進度百分比 (0-100)
    eta_seconds: Optional[int] = None  # 預估剩餘時間（秒）


@dataclass
class ResearchSource:
    """研究來源結構"""
    title: str
    url: str
    snippet: str
    relevance_score: Optional[float] = None 