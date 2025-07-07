"""
Wordle 服務模組

負責從外部 API 獲取 Wordle 答案的核心邏輯。
支援按日期查詢，並提供錯誤處理機制。
"""

import logging
import asyncio
import aiohttp
from datetime import datetime, date
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class WordleServiceError(Exception):
    """Wordle 服務基礎例外"""
    pass


class WordleNotFound(WordleServiceError):
    """指定日期的 Wordle 答案不存在"""
    pass


class WordleAPITimeout(WordleServiceError):
    """Wordle API 請求超時"""
    pass


@dataclass
class WordleResult:
    """Wordle 查詢結果"""
    solution: str
    date_str: str
    game_id: Optional[int] = None
    
    def __post_init__(self):
        """確保答案是大寫"""
        self.solution = self.solution.upper()


class WordleService:
    """Wordle 服務類"""
    
    # NYT 官方 Wordle API 端點
    API_BASE_URL = "https://www.nytimes.com/svc/wordle/v2"
    
    def __init__(self, timeout: int = 10):
        """
        初始化 Wordle 服務
        
        Args:
            timeout: API 請求超時時間（秒）
        """
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
    
    async def fetch_solution(self, target_date: date) -> WordleResult:
        """
        獲取指定日期的 Wordle 答案
        
        Args:
            target_date: 目標日期
            
        Returns:
            WordleResult: 包含答案和相關資訊的結果對象
            
        Raises:
            WordleNotFound: 指定日期的答案不存在（404）
            WordleAPITimeout: API 請求超時
            WordleServiceError: 其他 API 錯誤
        """
        date_str = target_date.strftime("%Y-%m-%d")
        url = f"{self.API_BASE_URL}/{date_str}.json"
        
        self.logger.info(f"正在獲取 {date_str} 的 Wordle 答案...")
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(url) as response:
                    if response.status == 404:
                        self.logger.warning(f"找不到 {date_str} 的 Wordle 答案")
                        raise WordleNotFound(f"該日期（{date_str}）查無 Wordle 資料")
                    
                    if response.status != 200:
                        self.logger.error(f"Wordle API 回應錯誤: {response.status}")
                        raise WordleServiceError(f"API 請求失敗（狀態碼：{response.status}）")
                    
                    data = await response.json()
                    
                    # 驗證回應格式
                    if "solution" not in data:
                        self.logger.error(f"API 回應格式錯誤: {data}")
                        raise WordleServiceError("API 回應格式不正確，缺少 solution 字段")
                    
                    solution = data["solution"]
                    game_id = data.get("id")  # 可能包含遊戲 ID
                    
                    self.logger.info(f"成功獲取 {date_str} 的 Wordle 答案")
                    
                    return WordleResult(
                        solution=solution,
                        date_str=date_str,
                        game_id=game_id
                    )
                    
        except asyncio.TimeoutError:
            self.logger.error(f"獲取 {date_str} Wordle 答案時請求超時")
            raise WordleAPITimeout("API 請求超時，請稍後再試")
        except aiohttp.ClientError as e:
            self.logger.error(f"網路請求錯誤: {e}")
            raise WordleServiceError(f"網路連接錯誤: {str(e)}")
        except Exception as e:
            # 若已是 WordleServiceError 子類，直接重新拋出
            if isinstance(e, WordleServiceError):
                raise
            self.logger.error(f"獲取 Wordle 答案時發生未知錯誤: {e}")
            raise WordleServiceError(f"服務暫時不可用: {str(e)}")


import re

def safe_wordle_output(text: str, solution: str) -> str:
    """
    安全後處理函式，確保包含 Discord spoiler tag 格式（使用正則優化，並用正則偵測 spoiler tag）

    Args:
        text: 原始提示文字
        solution: Wordle 答案

    Returns:
        str: 包含 spoiler tag 的安全文字
    """
    if not text or not solution:
        return text

    solution_upper = solution.upper()
    spoiler_tag = f"|| {solution_upper} ||"

    logger.debug(f"檢查 spoiler tag 格式，答案: {solution_upper}")

    # 用正則偵測是否已經有任何形式的 spoiler tag（允許空格）
    spoiler_pattern = re.compile(r"\|\|\s*{}[\s]*\|\|".format(re.escape(solution_upper)), re.IGNORECASE)
    if spoiler_pattern.search(text):
        logger.debug("文字已包含正確的 spoiler tag 格式")
        return text

    logger.info(f"補充 spoiler tag: {spoiler_tag}")

    # 使用正則，將所有不區分大小寫的 solution 字串替換為 spoiler tag
    solution_pattern = re.compile(re.escape(solution), re.IGNORECASE)
    safe_text = solution_pattern.sub(spoiler_tag, text)

    return f"{spoiler_tag}\n\n{safe_text}"


# 全域服務實例
_wordle_service: Optional[WordleService] = None


def get_wordle_service() -> WordleService:
    """獲取全域 Wordle 服務實例"""
    global _wordle_service
    if _wordle_service is None:
        _wordle_service = WordleService()
    return _wordle_service 