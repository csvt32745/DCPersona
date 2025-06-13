"""
統一提示詞管理系統

合併所有提示詞管理功能，包括 Random persona 選擇、
系統提示詞組裝、Discord 特定處理等。
"""

import random
import logging
from pathlib import Path
from typing import Union, Dict, Any, Optional, List
from datetime import datetime
import pytz

# 常數
ROOT_PROMPT_DIR = "persona"
DEFAULT_TIMEZONE = "Asia/Taipei"


class PromptSystem:
    """統一的提示詞管理系統"""
    
    def __init__(self, persona_cache_enabled: bool = True):
        """
        初始化提示詞系統
        
        Args:
            persona_cache_enabled: 是否啟用 persona 快取
        """
        self.persona_cache_enabled = persona_cache_enabled
        self._persona_cache: Dict[str, str] = {}
        self.logger = logging.getLogger(__name__)
    
    def get_prompt(self, filename: Union[str, Path]) -> str:
        """讀取並回傳指定檔案內容"""
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"載入提示詞檔案失敗 {filename}: {e}")
            return ""
    
    def random_system_prompt(self, root: Union[str, Path] = ROOT_PROMPT_DIR) -> str:
        """隨機選取 persona 目錄下的提示詞"""
        try:
            prompt_files = list(Path(root).glob("*.txt"))
            if not prompt_files:
                self.logger.warning(f"在 {root} 中找不到提示詞檔案")
                return ""
            
            filename = random.choice(prompt_files)
            persona_name = filename.stem
            
            # 檢查快取
            if self.persona_cache_enabled and persona_name in self._persona_cache:
                self.logger.info(f"從快取載入 {persona_name} persona")
                return self._persona_cache[persona_name]
            
            # 載入並快取
            content = self.get_prompt(filename)
            if self.persona_cache_enabled and content:
                self._persona_cache[persona_name] = content
            
            self.logger.info(f"隨機選擇 {persona_name} persona")
            return content
            
        except Exception as e:
            self.logger.error(f"選擇隨機提示詞時出錯: {e}")
            return ""
    
    def get_specific_persona(self, persona_name: str, root: Union[str, Path] = ROOT_PROMPT_DIR) -> str:
        """獲取特定的 persona"""
        try:
            # 檢查快取
            if self.persona_cache_enabled and persona_name in self._persona_cache:
                return self._persona_cache[persona_name]
            
            # 嘗試載入檔案
            persona_path = Path(root) / f"{persona_name}.txt"
            if not persona_path.exists():
                self.logger.warning(f"找不到 persona 檔案: {persona_path}")
                return ""
            
            content = self.get_prompt(persona_path)
            if self.persona_cache_enabled and content:
                self._persona_cache[persona_name] = content
            
            return content
            
        except Exception as e:
            self.logger.error(f"載入特定 persona {persona_name} 時出錯: {e}")
            return ""
    
    def build_system_prompt(
        self,
        cfg: Dict[str, Any],
        discord_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        組裝系統提示詞，包含 persona、時間戳、Discord 特定資訊等
        
        Args:
            cfg: 配置資料
            discord_context: Discord 上下文資訊（可選）
        
        Returns:
            str: 完整的系統提示詞
        """
        prompt_parts = []
        
        # 1. 基礎系統提示詞
        base_prompt = cfg.get("system_prompt", "")
        if base_prompt:
            prompt_parts.append(base_prompt.strip())
        
        # 2. Random persona（如果啟用）
        if cfg.get("is_random_system_prompt", False):
            persona_prompt = self.random_system_prompt()
            if persona_prompt:
                prompt_parts.append(persona_prompt.strip())
        
        # 3. 特定 persona 檔案（如果指定）
        system_prompt_file = cfg.get("system_prompt_file")
        if system_prompt_file:
            specific_persona = self.get_specific_persona(
                Path(system_prompt_file).stem
            )
            if specific_persona:
                prompt_parts.append(specific_persona.strip())
        
        # 4. Discord 特定資訊
        discord_info = self._build_discord_context(cfg, discord_context)
        if discord_info:
            prompt_parts.append(discord_info)
        
        # 5. 時間戳資訊
        timestamp_info = self._build_timestamp_info(cfg)
        if timestamp_info:
            prompt_parts.append(timestamp_info)
        
        return "\n\n".join(prompt_parts)
    
    def _build_discord_context(
        self,
        cfg: Dict[str, Any],
        discord_context: Optional[Dict[str, Any]]
    ) -> str:
        """建立 Discord 特定上下文"""
        if not discord_context:
            return ""
        
        context_parts = []
        
        # Bot ID 資訊
        bot_id = discord_context.get("bot_id")
        if bot_id:
            context_parts.append(f"我的 Discord Bot ID 是 {bot_id}")
        
        # 頻道資訊
        channel_id = discord_context.get("channel_id")
        if channel_id:
            context_parts.append(f"當前頻道 ID: {channel_id}")
        
        # 伺服器資訊
        guild_name = discord_context.get("guild_name")
        if guild_name:
            context_parts.append(f"當前伺服器: {guild_name}")
        
        # 用戶提及資訊
        mentions = discord_context.get("mentions", [])
        if mentions:
            mention_info = f"此訊息提及了: {', '.join(mentions)}"
            context_parts.append(mention_info)
        
        if context_parts:
            return "Discord 環境資訊:\n" + "\n".join(context_parts)
        
        return ""
    
    def _build_timestamp_info(self, cfg: Dict[str, Any]) -> str:
        """建立時間戳資訊"""
        prompt_config = cfg.get("prompt_system", {})
        discord_config = prompt_config.get("discord_integration", {})
        
        if not discord_config.get("include_timestamp", True):
            return ""
        
        try:
            timezone = discord_config.get("timezone", DEFAULT_TIMEZONE)
            tz = pytz.timezone(timezone)
            current_time = datetime.now(tz)
            
            time_info = f"當前時間: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            return f"時間資訊:\n{time_info}"
            
        except Exception as e:
            self.logger.warning(f"生成時間戳資訊時出錯: {e}")
            return ""
    
    def generate_tool_descriptions(self, available_tools: List[str]) -> str:
        """動態生成工具說明"""
        if not available_tools:
            return ""
        
        tool_descriptions = {
            "google_search": "我可以進行網路搜索來獲取最新資訊",
            "citation": "我可以提供來源引用和參考資料",
            "web_research": "我可以進行深度網路研究和分析"
        }
        
        descriptions = []
        for tool in available_tools:
            if tool in tool_descriptions:
                descriptions.append(f"- {tool_descriptions[tool]}")
        
        if descriptions:
            return f"我的能力包括:\n" + "\n".join(descriptions)
        
        return ""
    
    def clear_persona_cache(self):
        """清理 persona 快取"""
        self._persona_cache.clear()
        self.logger.info("已清理 persona 快取")
    
    def get_available_personas(self, root: Union[str, Path] = ROOT_PROMPT_DIR) -> List[str]:
        """獲取可用的 persona 列表"""
        try:
            prompt_files = list(Path(root).glob("*.txt"))
            return [f.stem for f in prompt_files]
        except Exception as e:
            self.logger.error(f"獲取可用 persona 時出錯: {e}")
            return []
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """獲取快取統計資訊"""
        return {
            "cache_enabled": self.persona_cache_enabled,
            "cached_personas": list(self._persona_cache.keys()),
            "cache_size": len(self._persona_cache)
        }


# 全域提示詞系統實例
_prompt_system = None

def get_prompt_system() -> PromptSystem:
    """獲取全域提示詞系統實例"""
    global _prompt_system
    if _prompt_system is None:
        _prompt_system = PromptSystem()
    return _prompt_system


# 便利函數（向後兼容）
def random_system_prompt(root: Union[str, Path] = ROOT_PROMPT_DIR) -> str:
    """隨機選取 persona 的便利函數"""
    system = get_prompt_system()
    return system.random_system_prompt(root)


def build_system_prompt(
    cfg: Dict[str, Any],
    discord_context: Optional[Dict[str, Any]] = None
) -> str:
    """快速建立系統提示詞的便利函數"""
    prompt_system = get_prompt_system()
    return prompt_system.build_system_prompt(cfg, discord_context)


# ===== Agent 搜尋相關提示詞 =====

def get_current_date(timezone_str: str = "Asia/Taipei"):
    """取得當前日期的可讀格式，考慮傳入的時區設定"""
    now = datetime.now(pytz.timezone(timezone_str))
    return now.strftime("%B %d, %Y")


web_searcher_instructions = """Conduct targeted Google Searches to gather the most recent, credible information on "{research_topic}" and synthesize it into a verifiable text artifact.

Instructions:
- Query should ensure that the most current information is gathered. The current date is {current_date}.
- Conduct multiple, diverse searches to gather comprehensive information.
- Consolidate key findings while meticulously tracking the source(s) for each specific piece of information.
- The output should be a well-written summary or report based on your search findings. 
- Only include the information found in the search results, don't make up any information.

Research Topic:
{research_topic}
""" 