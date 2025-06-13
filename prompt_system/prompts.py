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
import os

from utils.config_loader import load_typed_config
from schemas.config_types import AppConfig

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
    
    def get_system_instructions(
        self,
        cfg: Dict[str, Any],
        available_tools: List[str],
        discord_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        獲取完整的系統指令，包括 persona、工具說明、時間戳等
        
        Args:
            cfg: 配置資料
            available_tools: 可用的工具列表
            discord_context: Discord 上下文資訊（可選）
        
        Returns:
            str: 完整的系統指令
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

        # 6. 工具描述
        tool_descriptions = self.generate_tool_descriptions(available_tools)
        if tool_descriptions:
            prompt_parts.append(tool_descriptions)

        return "\n\n".join(prompt_parts)

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
        # 直接呼叫 get_system_instructions，但在此函數中沒有 available_tools
        # 為了保持原函數簽名，傳遞空列表或根據需求調整
        # 注意：如果此函數仍然被 LangGraph 以外的部分調用且需要工具，需要修改調用方
        return self.get_system_instructions(cfg, [], discord_context)
    
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
            "google_search": "我可以提供網路搜尋結果",
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

def get_current_date(timezone_str: str = DEFAULT_TIMEZONE) -> str:
    """獲取當前日期字串"""
    try:
        tz = pytz.timezone(timezone_str)
        current_time = datetime.now(tz)
        return current_time.strftime('%Y-%m-%d')
    except Exception as e:
        logging.getLogger(__name__).warning(f"獲取當前日期時出錯: {e}")
        return datetime.now().strftime('%Y-%m-%d')


def load_persona_files(persona_dir: str = "persona") -> Dict[str, str]:
    """載入所有 persona 檔案
    
    Args:
        persona_dir: persona 檔案目錄
        
    Returns:
        Dict[str, str]: 檔案名稱到內容的映射
    """
    personas = {}
    persona_path = Path(persona_dir)
    
    if not persona_path.exists():
        logging.warning(f"Persona 目錄不存在: {persona_dir}")
        return personas
    
    try:
        for file_path in persona_path.glob("*.txt"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        personas[file_path.name] = content
                        logging.debug(f"載入 persona: {file_path.name}")
            except Exception as e:
                logging.warning(f"載入 persona 檔案失敗 {file_path}: {e}")
    except Exception as e:
        logging.error(f"掃描 persona 目錄失敗: {e}")
    
    return personas


def get_system_prompt(config: Optional[AppConfig] = None) -> str:
    """獲取系統提示詞
    
    Args:
        config: 型別安全的配置實例
        
    Returns:
        str: 系統提示詞
    """
    if config is None:
        config = load_typed_config()
    
    try:
        # 使用型別安全的配置存取
        prompt_config = config.prompt_system
        system_prompt_config = prompt_config.system_prompt
        
        # 檢查是否使用檔案
        if system_prompt_config.use_file and system_prompt_config.file:
            persona_file = system_prompt_config.file
            
            # 如果啟用隨機選擇
            if prompt_config.persona.random_selection:
                personas = load_persona_files()
                if personas:
                    # 隨機選擇一個 persona
                    selected_file = random.choice(list(personas.keys()))
                    selected_content = personas[selected_file]
                    logging.info(f"隨機選擇 persona: {selected_file}")
                    return selected_content
                else:
                    logging.warning("沒有找到 persona 檔案，使用預設檔案")
            
            # 載入指定檔案
            persona_path = Path("persona") / persona_file
            if persona_path.exists():
                try:
                    with open(persona_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            logging.info(f"載入系統提示詞檔案: {persona_file}")
                            return content
                except Exception as e:
                    logging.error(f"載入系統提示詞檔案失敗 {persona_file}: {e}")
        
        # 使用回退提示詞
        fallback_prompt = system_prompt_config.fallback
        logging.info("使用回退系統提示詞")
        return fallback_prompt
        
    except Exception as e:
        logging.error(f"獲取系統提示詞失敗: {e}")
        return "你是一個有用的 AI 助手。"


def format_discord_context(
    discord_context: Dict[str, Any], 
    config: Optional[AppConfig] = None
) -> str:
    """格式化 Discord 上下文資訊
    
    Args:
        discord_context: Discord 上下文字典
        config: 型別安全的配置實例
        
    Returns:
        str: 格式化的上下文字串
    """
    if config is None:
        config = load_typed_config()
    
    try:
        context_parts = []
        
        # 使用型別安全的配置存取
        discord_integration = config.prompt_system.discord_integration
        
        # 添加時間戳
        if discord_integration.include_timestamp:
            current_time = get_current_date(config.system.timezone)
            context_parts.append(f"當前時間: {current_time}")
        
        # 添加 Bot 資訊
        bot_id = discord_context.get("bot_id")
        if bot_id:
            context_parts.append(f"你的 Discord ID: <@{bot_id}>")
        
        # 添加頻道資訊
        channel_id = discord_context.get("channel_id")
        if channel_id:
            context_parts.append(f"當前頻道: <#{channel_id}>")
        
        # 添加伺服器資訊
        guild_name = discord_context.get("guild_name")
        if guild_name:
            context_parts.append(f"伺服器: {guild_name}")
        
        # 添加提及資訊
        if discord_integration.include_mentions:
            mentions = discord_context.get("mentions", [])
            if mentions:
                mention_strs = [f"<@{user_id}>" for user_id in mentions]
                context_parts.append(f"提及的用戶: {', '.join(mention_strs)}")
        
        return "\n".join(context_parts) if context_parts else ""
        
    except Exception as e:
        logging.error(f"格式化 Discord 上下文失敗: {e}")
        return ""


# 工具相關的提示詞模板
web_searcher_instructions = """作為一個網路搜尋專家，你的目標是：

1. 分析用戶的問題，決定是否需要最新的資訊
2. 如果需要搜尋，創建精確的搜尋關鍵詞
3. 合并搜尋結果，提供準確且有用的回應

研究主題: {research_topic}
當前日期: {current_date}

搜尋策略：
- 使用明確、相關的關鍵詞
- 避免太廣泛的搜尋詞
- 考慮時間效應和地區效應
- 優先選擇權威來源

回應要求：
- 根據搜尋結果提供準確的資訊
- 標明資訊來源
- 承認不確定性
- 提供有用的後續建議
""" 

# This function was incorrectly added and should be removed.
# def _get_system_message_for_planning_agent(self, current_date: str) -> str:
#     # ... existing code ...
#     return "" 