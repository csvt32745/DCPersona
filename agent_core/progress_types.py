"""
進度類型定義

定義進度階段和工具狀態的枚舉類型，提供型別安全的進度管理。
"""

from enum import Enum
from typing import Dict


class ProgressStage(str, Enum):
    """進度階段枚舉
    
    定義 Agent 執行過程中的各個階段，使用字串枚舉確保向後相容性
    """
    STARTING = "starting"
    GENERATE_QUERY = "generate_query"
    SEARCHING = "searching"
    ANALYZING = "analyzing"
    COMPLETING = "completing"
    STREAMING = "streaming"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"
    TOOL_LIST = "tool_list"
    TOOL_STATUS = "tool_status"
    TOOL_EXECUTION = "tool_execution"
    REFLECTION = "reflection"
    FINALIZE_ANSWER = "finalize_answer"


class ToolStatus(str, Enum):
    """工具狀態枚舉
    
    定義工具執行過程中的各種狀態
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


# 工具狀態符號映射 - 保留在程式碼中，不放入配置
TOOL_STATUS_SYMBOLS: Dict[ToolStatus, str] = {
    ToolStatus.PENDING: "⚪",
    ToolStatus.RUNNING: "🔄",
    ToolStatus.COMPLETED: "✅",
    ToolStatus.ERROR: "❌",
} 