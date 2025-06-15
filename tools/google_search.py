"""
Google 搜尋工具 - 使用 LangChain BaseTool 實作

此模組提供 Google 搜尋功能，支援單個查詢的執行。
"""

import asyncio
import logging
from typing import Any, Union, List, Optional
from datetime import datetime
import json

from langchain_core.tools import BaseTool
from pydantic import Field
from google.genai import Client

from prompt_system.prompts import get_current_date, PromptSystem
from schemas.config_types import AppConfig
from schemas.agent_types import ToolExecutionResult


class GoogleSearchTool(BaseTool):
    """Google 搜尋工具
    
    支援單個查詢，使用 Gemini API 進行搜尋。
    """
    
    name: str = "google_search"
    description: str = (
        "執行 Google 搜尋並返回結果。此工具可接受由 Agent 判斷後生成的 0 到 3 個搜尋查詢（單一字串或字串列表），"
        "這些查詢將被非同步執行。主要用於獲取最新資訊、即時數據或新聞事件，以輔助 Agent 回覆使用者需求。"
        "注意 變數皆為 query，請不要使用其他變數名稱。"
    )
    
    # 定義工具的輸入 schema，支援單一字串或字串列表
    args_schema: dict = {
        "query": {
            "type": ["string", "array"],
            "items": {"type": "string"},
            "description": "The search query (string example: query='latest news about AI') or a list of search query (array of strings example: query=['latest news about AI', 'latest news about stock market'])"
        }
    }
    
    # Pydantic 模型欄位
    google_client: Any = Field(default=None, exclude=True)
    prompt_system_instance: Any = Field(default=None, exclude=True)
    config: Any = Field(default=None, exclude=True)
    logger: Any = Field(default=None, exclude=True)

    def __init__(self, google_client: Any, prompt_system_instance: Any, config: AppConfig, logger: logging.Logger = None, **kwargs):
        super().__init__(**kwargs)
        self.google_client = google_client
        self.prompt_system_instance = prompt_system_instance
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

    def _run(self, query: Union[str, List[str]]) -> ToolExecutionResult:
        """同步執行搜尋"""
        self.logger.info(f"執行 Google 搜尋，查詢: {query}")
        return asyncio.run(self._process_queries(query))

    async def _arun(self, query: Union[str, List[str]]) -> ToolExecutionResult:
        """非同步執行搜尋"""
        self.logger.info(f"執行非同步 Google 搜尋，查詢: {query}")
        return await self._process_queries(query)

    async def _process_queries(self, query: Union[str, List[str]]) -> ToolExecutionResult:
        """處理單一或多個查詢的執行，並將結果合併為單一 ToolExecutionResult"""
        if isinstance(query, str):
            # 單一查詢
            self.logger.info(f"處理單一查詢: {query}")
            return self._execute_search(query)
        elif isinstance(query, list):
            # 多個查詢，並行執行
            self.logger.info(f"處理多個查詢: {query}")
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(None, self._execute_search, q)
                for q in query
            ]
            individual_results: List[ToolExecutionResult] = await asyncio.gather(*tasks)

            # 合併結果
            all_success = any(r.success for r in individual_results)
            combined_message_parts = []
            combined_data = []

            for i, res in enumerate(individual_results):
                query_str = query[i] if i < len(query) else "Unknown Query"
                status = "成功" if res.success else "失敗"
                combined_message_parts.append(f"查詢 '{query_str}' {status}: {res.message}")
                combined_data.append({"query": query_str, "result_data": res.data})

            combined_message = "\n ----- \n".join(combined_message_parts)

            return ToolExecutionResult(
                success=all_success,
                message=combined_message,
                data={"queries_results": combined_data}
            )
        else:
            return ToolExecutionResult(
                success=False,
                message=f"不支援的查詢格式: {type(query)}",
                data={"query": query}
            )

    def _execute_search(self, query: str) -> ToolExecutionResult:
        """執行單個搜尋"""
        if not self.google_client:
            return ToolExecutionResult(
                success=False,
                message=f"Google 客戶端未配置，無法執行搜尋: {query}",
                data={"query": query}
            )
        
        try:
            current_date = get_current_date(timezone_str=self.config.system.timezone)
            
            # 準備傳遞給 Gemini 模型的提示
            formatted_prompt = self.prompt_system_instance.get_web_searcher_instructions(
                research_topic=query,
                current_date=current_date
            )
            
            # 取得模型名稱
            tool_analysis_config = self.config.llm.models.get("tool_analysis")
            if not tool_analysis_config:
                return ToolExecutionResult(
                    success=False,
                    message="Google 搜尋模型未找到配置",
                    data={"query": query}
                )
            
            # 調用 Gemini API
            response = self.google_client.models.generate_content(
                model=tool_analysis_config.model,
                contents=formatted_prompt,
                config={
                    "tools": [{"google_search": {}}],
                    "temperature": 0
                }
            )
            print(response)
            
            if response.text:
                return ToolExecutionResult(
                    success=True,
                    message=response.text,
                    data={"query": query}
                )
            else:
                return ToolExecutionResult(
                    success=False,
                    message=f"針對查詢「{query}」沒有找到內容。",
                    data={"query": query}
                )
                
        except Exception as e:
            self.logger.error(f"Google 搜尋失敗: {e}")
            return ToolExecutionResult(
                success=False,
                message=f"搜尋執行失敗: {str(e)}",
                data={"query": query, "error": str(e)}
            ) 