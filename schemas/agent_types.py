from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Annotated
import operator


@dataclass
class MsgNode:
    """結構化訊息節點。"""
    role: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolPlan:
    """工具使用計劃"""
    tool_name: str
    queries: List[str]  # 該工具的查詢列表
    priority: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class AgentPlan:
    """Agent 執行計劃"""
    needs_tools: bool
    tool_plans: List[ToolPlan] = field(default_factory=list)
    reasoning: str = ""  # 決策推理過程


@dataclass
class OverallState:
    """統一代理狀態（重構版）"""
    messages: List[MsgNode] = field(default_factory=list)
    tool_round: int = 0
    finished: bool = False
    
    # 新的計劃驅動欄位
    agent_plan: Optional[AgentPlan] = None
    research_topic: str = ""
    
    # 工具執行結果
    tool_results: Annotated[List[str], operator.add] = field(default_factory=list)
    aggregated_tool_results: List[str] = field(default_factory=list)
    
    # 反思和評估
    is_sufficient: bool = False
    reflection_reasoning: str = ""
    
    # 最終結果
    final_answer: str = ""
    sources: List[Dict[str, str]] = field(default_factory=list)
    
    # 向後相容性欄位（保留舊的欄位以避免破壞現有代碼）
    needs_tools: bool = False
    search_queries: Annotated[List[str], operator.add] = field(default_factory=list)
    available_tools: List[str] = field(default_factory=list)
    selected_tool: Optional[str] = None
    reflection_complete: bool = False


@dataclass
class ToolExecutionState:
    """單個工具執行狀態"""
    tool_name: str
    query: str
    task_id: str
    priority: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


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