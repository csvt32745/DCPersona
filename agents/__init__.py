"""
LangGraph agents 模組 - 提供智能研究代理功能

這個模組整合了 LangGraph 的多步驟研究能力到 llmcord Discord bot 中。
支援智能模式切換和即時進度回饋。
"""

from .research_agent import ResearchAgent
from .state import OverallState, ResearchConfig
from .configuration import AgentConfiguration

__all__ = [
    "ResearchAgent",
    "OverallState", 
    "ResearchConfig",
    "AgentConfiguration",
]