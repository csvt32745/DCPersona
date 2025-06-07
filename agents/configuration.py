"""
Agent 配置管理

基於 gemini-fullstack-langgraph-quickstart 的配置系統，
適配到 Discord bot 環境並添加 Discord 特定配置。
"""

import os
from pydantic import BaseModel, Field
from typing import Any, Optional, Dict
from langchain_core.runnables import RunnableConfig


class AgentConfiguration(BaseModel):
    """LangGraph Agent 配置類別"""

    # LLM 模型配置
    query_generator_model: str = Field(
        default="gemini-2.0-flash-exp",
        metadata={
            "description": "用於查詢生成的語言模型名稱"
        },
    )

    reflection_model: str = Field(
        default="gemini-2.0-flash-exp",
        metadata={
            "description": "用於反思階段的語言模型名稱"
        },
    )

    answer_model: str = Field(
        default="gemini-2.0-flash-exp",
        metadata={
            "description": "用於最終答案生成的語言模型名稱"
        },
    )

    # 搜尋配置 - Discord 環境優化
    number_of_initial_queries: int = Field(
        default=2,  # 減少初始查詢數以適應 Discord 環境
        metadata={"description": "初始搜尋查詢的數量"},
    )

    max_research_loops: int = Field(
        default=1,  # 減少研究循環以控制回應時間
        metadata={"description": "最大研究循環次數"},
    )

    # Discord 特定配置
    progress_updates_enabled: bool = Field(
        default=True,
        metadata={"description": "是否啟用進度更新訊息"},
    )

    timeout_seconds: int = Field(
        default=30,
        metadata={"description": "研究超時時間（秒）"},
    )

    fallback_enabled: bool = Field(
        default=True,
        metadata={"description": "是否啟用降級機制"},
    )

    # API 金鑰配置
    gemini_api_key: Optional[str] = Field(
        default=None,
        metadata={"description": "Gemini API 金鑰"},
    )

    google_search_api_key: Optional[str] = Field(
        default=None,
        metadata={"description": "Google Search API 金鑰"},
    )

    google_search_engine_id: Optional[str] = Field(
        default=None,
        metadata={"description": "Google Search Engine ID"},
    )

    # 智能模式切換配置
    complexity_threshold: float = Field(
        default=0.7,
        metadata={"description": "複雜度閾值，超過此值啟動 LangGraph"},
    )

    force_research_keywords: list[str] = Field(
        default=["研究", "調查", "分析", "詳細", "深入", "比較", "!research", "!研究"],
        metadata={"description": "強制啟動研究模式的關鍵字"},
    )

    simple_response_max_tokens: int = Field(
        default=1000,
        metadata={"description": "簡單回應的最大 token 數"},
    )

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "AgentConfiguration":
        """從 RunnableConfig 創建配置實例"""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )

        # 從環境變數或配置中獲取原始值
        raw_values: dict[str, Any] = {
            name: os.environ.get(name.upper(), configurable.get(name))
            for name in cls.model_fields.keys()
        }

        # 過濾掉 None 值
        values = {k: v for k, v in raw_values.items() if v is not None}

        return cls(**values)

    @classmethod
    def from_llmcord_config(cls, llmcord_cfg: Dict[str, Any]) -> "AgentConfiguration":
        """從 llmcord 配置創建 Agent 配置"""
        # 提取相關配置
        model_config = llmcord_cfg.get("model", "openai/gemini-2.0-flash-exp")
        provider, model_name = model_config.split("/", 1) if "/" in model_config else ("openai", model_config)
        
        # 獲取 API 金鑰
        providers_config = llmcord_cfg.get("providers", {})
        api_key = None
        if provider in providers_config:
            api_key = providers_config[provider].get("api_key")

        # LangGraph 特定配置
        langgraph_config = llmcord_cfg.get("langgraph", {})
        models_config = langgraph_config.get("models", {})

        # 使用 langgraph.models 配置優先，否則 fallback 到主 model
        query_generator_model = models_config.get("query_generator", model_name)
        reflection_model = models_config.get("reflection", model_name)
        answer_model = models_config.get("answer", model_name)
        
        return cls(
            query_generator_model=query_generator_model,
            reflection_model=reflection_model,
            answer_model=answer_model,
            number_of_initial_queries=langgraph_config.get("initial_queries", 2),
            max_research_loops=langgraph_config.get("max_loops", 1),
            progress_updates_enabled=langgraph_config.get("progress_updates", True),
            timeout_seconds=langgraph_config.get("timeout", 30),
            fallback_enabled=langgraph_config.get("fallback", True),
            gemini_api_key=api_key if "gemini" in model_name.lower() else None,
            google_search_api_key=langgraph_config.get("google_search_api_key"),
            google_search_engine_id=langgraph_config.get("google_search_engine_id"),
            complexity_threshold=langgraph_config.get("complexity_threshold", 0.7),
            force_research_keywords=langgraph_config.get("force_research_keywords", 
                                                       ["研究", "調查", "分析", "詳細", "深入", "比較"]),
            simple_response_max_tokens=langgraph_config.get("simple_max_tokens", 1000),
        )

    def to_runnable_config(self) -> RunnableConfig:
        """轉換為 RunnableConfig 格式"""
        return RunnableConfig(
            configurable=self.model_dump(exclude_none=True)
        )

    def validate_api_keys(self) -> tuple[bool, str]:
        """驗證必要的 API 金鑰"""
        missing_keys = []
        
        if not self.gemini_api_key:
            missing_keys.append("Gemini API Key")
            
        if not self.google_search_api_key:
            missing_keys.append("Google Search API Key")
            
        if not self.google_search_engine_id:
            missing_keys.append("Google Search Engine ID")
        
        if missing_keys:
            return False, f"缺少必要的 API 金鑰: {', '.join(missing_keys)}"
        
        return True, "所有 API 金鑰已配置"

    def get_model_for_stage(self, stage: str) -> str:
        """根據階段獲取對應的模型"""
        stage_models = {
            "query_generation": self.query_generator_model,
            "reflection": self.reflection_model,
            "answer": self.answer_model,
        }
        return stage_models.get(stage, self.query_generator_model)

    def should_use_research_mode(self, message_content: str) -> bool:
        """判斷是否應該使用研究模式"""
        # 檢查強制研究關鍵字
        content_lower = message_content.lower()
        if any(keyword in content_lower for keyword in self.force_research_keywords):
            return True
        
        # 簡單的複雜度評估（可以後續改進為更精確的模型）
        complexity_indicators = [
            len(message_content.split()) > 20,  # 長文本
            "?" in message_content and len(message_content.split("?")) > 2,  # 多個問題
            any(word in content_lower for word in ["比較", "對比", "差異", "優缺點", "為什麼", "如何"]),
            any(word in content_lower for word in ["最新", "2024", "2025", "現在", "目前"]),  # 需要時效性資訊
        ]
        
        complexity_score = sum(complexity_indicators) / len(complexity_indicators)
        return complexity_score >= self.complexity_threshold


# 預設配置實例
DEFAULT_AGENT_CONFIG = AgentConfiguration()


def create_agent_config_from_env() -> AgentConfiguration:
    """從環境變數創建 Agent 配置"""
    return AgentConfiguration(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        google_search_api_key=os.getenv("GOOGLE_SEARCH_API_KEY"),
        google_search_engine_id=os.getenv("GOOGLE_SEARCH_ENGINE_ID"),
    )