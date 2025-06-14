"""
進度觀察者模式實作

提供通用的進度事件和觀察者介面，實現 Agent 核心與外部 UI 系統的解耦。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class ProgressEvent:
    """通用進度事件
    
    用於在 Agent 執行過程中傳遞進度資訊給外部系統
    """
    stage: str  # 進度階段 (generate_query, execute_tool, reflection, etc.)
    message: str  # 進度描述訊息
    progress_percentage: Optional[int] = None  # 進度百分比 (0-100)
    eta_seconds: Optional[int] = None  # 預估剩餘時間（秒）
    metadata: Dict[str, Any] = field(default_factory=dict)  # 額外的元數據


class ProgressObserver(ABC):
    """進度觀察者介面
    
    外部系統（如 Discord, CLI, Web）需要實作此介面來接收進度更新
    """
    
    @abstractmethod
    async def on_progress_update(self, event: ProgressEvent) -> None:
        """處理進度更新事件
        
        Args:
            event: 進度事件，包含階段、訊息、百分比等資訊
        """
        pass
    
    @abstractmethod
    async def on_completion(self, final_result: str, sources: Optional[List[Dict]] = None) -> None:
        """處理完成事件
        
        Args:
            final_result: 最終生成的回答
            sources: 研究來源清單（可選）
        """
        pass
    
    @abstractmethod
    async def on_error(self, error: Exception) -> None:
        """處理錯誤事件
        
        Args:
            error: 發生的異常
        """
        pass
    
    @abstractmethod
    async def on_streaming_chunk(self, content: str, is_final: bool = False) -> None:
        """處理串流塊
        
        Args:
            content: 串流內容
            is_final: 是否為最終塊
        """
        pass
    
    @abstractmethod
    async def on_streaming_complete(self) -> None:
        """處理串流完成"""
        pass 