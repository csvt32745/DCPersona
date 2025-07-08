"""
YouTube 影片摘要工具

此模組提供一個工具，用於從 YouTube URL 生成影片摘要。
"""

import asyncio
import logging
from typing import Any, ClassVar
import time
from utils.youtube_utils import extract_first_youtube_url, get_video_id

from langchain_core.tools import BaseTool
from pydantic import Field
from google.genai import Client, types

from schemas.agent_types import ToolExecutionResult
from schemas.config_types import AppConfig


class YouTubeSummaryTool(BaseTool):
    """YouTube 影片摘要工具
    
    支援單一 YouTube URL，使用 Gemini API 生成影片摘要。
    """
    
    name: str = "youtube_summary"
    description: str = (
        "為給定的 YouTube 影片 URL 生成摘要。此工具僅接受一個 URL。"
    )
    
    # 定義工具的輸入 schema，只接受一個 url 字串
    args_schema: dict = {
        "url": {
            "type": "string",
            "description": "要生成摘要的 YouTube 影片 URL。"
        }
    }
    
    # Pydantic 模型欄位
    google_client: Any = Field(default=None, exclude=True)
    config: AppConfig = Field(default=None, exclude=True)
    logger: logging.Logger = Field(default=None, exclude=True)

    # 類別層級快取: video_id -> (timestamp, ToolExecutionResult)
    _cache: ClassVar[dict] = {}
    _DEFAULT_TTL = 60 * 60 * 24  # 24h

    def __init__(self, google_client: Client, config: AppConfig, logger: logging.Logger = None, **kwargs):
        super().__init__(**kwargs)
        self.google_client = google_client
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

    def _run(self, url: str) -> ToolExecutionResult:
        """同步執行摘要"""
        self.logger.info(f"執行 YouTube 摘要，URL: {url}")
        # 在同步方法中執行異步的 _arun
        return asyncio.run(self._arun(url=url))

    async def _arun(self, url: str) -> ToolExecutionResult:
        """非同步執行摘要"""
        self.logger.info(f"執行非同步 YouTube 摘要，URL: {url}")

        video_id = get_video_id(url)
        if not video_id:
            return ToolExecutionResult(success=False, message="無效的 YouTube URL", data={"url": url})

        now = time.time()
        # 清理過期
        expired = [vid for vid, (ts, _) in self._cache.items() if now - ts > self._DEFAULT_TTL]
        for vid in expired:
            self._cache.pop(vid, None)

        # 快取命中
        print(self._cache)
        cached = self._cache.get(video_id)
        if cached:
            self.logger.info(f"Cache hit for {video_id}")
            return cached[1]

        if not self.google_client:
            self.logger.error("Google 客戶端未配置，無法執行摘要。")
            return ToolExecutionResult(
                success=False,
                message="Google 客戶端未配置，無法執行摘要。",
                data={"url": url}
            )

        try:
            result = await self._call_gemini(url)
            # 寫入快取
            if result.success:
                self._cache[video_id] = (now, result)
            return result
        except Exception as e:
            self.logger.error(f"為 URL {url} 執行 YouTube 摘要時發生錯誤: {e}", exc_info=True)
            return ToolExecutionResult(success=False, message=f"摘要執行失敗: {str(e)}", data={"url": url, "error": str(e)})

    async def _call_gemini(self, url: str) -> ToolExecutionResult:
        """實際呼叫 Gemini 生成摘要"""
        youtube_video_part = types.Part.from_uri(file_uri=url, mime_type="video/*")
        prompt_part = types.Part.from_text(text="""
                                           請幫我總結這部影片，並詳細描述整段影片的內容。
                                           """)
        contents = [youtube_video_part, prompt_part]

        model_config = self.config.llm.models.get("tool_analysis")
        if not model_config:
            return ToolExecutionResult(success=False, message="YouTube 摘要模型未找到配置。", data={"url": url})

        gen_config = types.GenerateContentConfig(
            temperature=getattr(model_config, "temperature", 0.7),
            max_output_tokens=getattr(model_config, "max_output_tokens", 32768),
            response_modalities=["TEXT"],
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW,
        )

        response = self.google_client.models.generate_content(
            model=model_config.model,
            contents=contents,
            config=gen_config,
        )

        if response.text:
            return ToolExecutionResult(success=True, message=response.text, data={"url": url, "summary": response.text})
        else:
            return ToolExecutionResult(success=False, message="API 回應為空。", data={"url": url}) 