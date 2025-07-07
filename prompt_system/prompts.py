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
from schemas.config_types import AppConfig, DiscordContextData

# 常數
ROOT_PROMPT_DIR = "persona"
DEFAULT_TIMEZONE = "Asia/Taipei"
MULTIMODAL_GUIDANCE = """
多媒體內容處理指導：
- 用戶訊息可能包含 Discord 自定義 emoji（格式：<:emoji_name:emoji_id>）、sticker 和圖片附件。
- 所有圖片內容都已轉換為 base64 格式供你分析和理解。
- 如果訊息末尾有 [包含: ...] 標記，這是多媒體內容的統計摘要。
- 請在回應時適當參考和回應這些視覺內容，讓對話更生動自然。
- 回應時可以用文字描述看到的圖片內容，或對 emoji/sticker 表達的情感作出回應。
"""


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
        config: AppConfig,
        messages_global_metadata: str = ""
    ) -> str:
        """
        獲取完整的系統指令，包括 persona、時間戳等
        
        注意：由於 LangChain 工具綁定會自動處理工具描述，
        此方法不再需要手動生成工具說明。
        
        Args:
            config: 型別化配置實例
            messages_global_metadata: 全域訊息 metadata
        
        Returns:
            str: 完整的系統指令
        """
        prompt_parts = []

        # 使用型別化配置
        persona_cfg = config.prompt_system.persona
        
        # 1. 基礎系統提示詞（從統一的 persona 配置）
        if persona_cfg.enabled:
            if persona_cfg.random_selection:
                # 隨機選擇 persona
                persona_prompt = self.random_system_prompt(persona_cfg.persona_directory)
                if persona_prompt:
                    prompt_parts.append(persona_prompt.strip())
                elif persona_cfg.fallback:
                    prompt_parts.append(persona_cfg.fallback.strip())
            else:
                # 使用預設 persona
                if persona_cfg.default_persona:
                    specific_persona = self.get_specific_persona(
                        persona_cfg.default_persona, 
                        persona_cfg.persona_directory
                    )
                    if specific_persona:
                        prompt_parts.append(specific_persona.strip())
                    elif persona_cfg.fallback:
                        prompt_parts.append(persona_cfg.fallback.strip())
        else:
            # Persona 被禁用，使用回退提示詞
            if persona_cfg.fallback:
                prompt_parts.append(persona_cfg.fallback.strip())


        # 3. 工具描述 - 已移除，由 LangChain 自動處理
        # LangChain 的 bind_tools 會自動將工具描述注入到模型中
        
        # 4. 時間戳資訊
        timestamp_info = self._build_timestamp_info(config)
        if timestamp_info:
            prompt_parts.append(timestamp_info)

        # 5. 全域 metadata（倒數第二位）
        if messages_global_metadata:
            prompt_parts.append(messages_global_metadata)

        
        # 6. 多媒體內容處理指導
        prompt_parts.append(MULTIMODAL_GUIDANCE)
        
        # 7. 最後加入任何其他系統指令（如 tool result 相關）
        # （這裡是倒數第一位，為未來的 tool result 指令預留）
        
        result = "\n\n".join(prompt_parts)
        self.logger.debug(f"系統指令: {result}")
        return result
    
    def _build_discord_context(
        self,
        config: AppConfig,
        discord_context: DiscordContextData = None,
        is_reminder_trigger: bool = False,
        reminder_content: str = ""
    ) -> str:
        """建立 Discord 特定上下文"""
        if discord_context is None:
            return ""
        
        discord_integration_cfg = config.prompt_system.discord_integration
        context_parts = []
        
        # Bot ID 和名稱資訊
        if discord_context.bot_id:
            if discord_context.bot_name:
                context_parts.append(f"<@{discord_context.bot_id}> ({discord_context.bot_name}) 是你的 ID，如果有人提到 <@{discord_context.bot_id}> 就是在說你")
            else:
                context_parts.append(f"<@{discord_context.bot_id}> 是你的 ID，如果有人提到 <@{discord_context.bot_id}> 就是在說你")
            context_parts.append("User's names are their Discord IDs and should be typed as '<@ID>'.")
        
        context_parts.append("注意：若對話中有 || 內容 || 的對話內容，請記得跟著一起用 || 內容 || 包起來，防止意外暴雷，例如: ||答案||")
        
        # 頻道資訊
        if discord_context.channel_id:
            if discord_context.channel_name:
                context_parts.append(f"當前頻道: <#{discord_context.channel_id}> ({discord_context.channel_name})")
            else:
                context_parts.append(f"當前頻道 ID: {discord_context.channel_id}")
        
        # 伺服器資訊
        if discord_context.guild_name:
            context_parts.append(f"當前伺服器: {discord_context.guild_name}")
        
        # 用戶提及資訊（如果啟用）
        if discord_integration_cfg.include_mentions and discord_context.mentions:
            mention_info = f"此訊息提及了: {', '.join(discord_context.mentions)}"
            context_parts.append(mention_info)
            
        context_parts.append(f"回覆時禁止使用 <@{discord_context.bot_id}> {discord_context.bot_name}: 這種格式，自然講話就好!")
        
        # 用戶上下文資訊（包括用戶 ID，如果啟用）
        if discord_integration_cfg.include_user_context and discord_context.user_name and discord_context.user_id:
            context_parts.append(f"最新訊息用戶: <@{discord_context.user_id}> {discord_context.user_name}")
            
        # 檢查是否為提醒觸發情況
        if is_reminder_trigger:
            context_parts.append(self.get_tool_prompt("on_reminder_triggered", reminder_content=reminder_content))
        
        if context_parts:
            return "Discord 環境資訊:\n" + "\n".join(context_parts)
        
        return ""
    
    def _build_timestamp_info(self, config: AppConfig) -> str:
        """建立時間戳資訊"""
        discord_integration_cfg = config.prompt_system.discord_integration
        
        if not discord_integration_cfg.include_timestamp:
            return ""
        
        try:
            timezone = config.system.timezone
            tz = pytz.timezone(timezone)
            current_time = datetime.now(tz)
            
            time_info = f"當前時間: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            return f"時間資訊:\n{time_info}"
            
        except Exception as e:
            self.logger.warning(f"生成時間戳資訊時出錯: {e}")
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
    
    def get_tool_prompt(self, prompt_name: str, **format_args) -> str:
        """
        獲取工具提示詞並進行格式化
        
        Args:
            prompt_name: 提示詞名稱（不包含 .txt 擴展名）
            **format_args: 格式化參數
            
        Returns:
            str: 格式化後的提示詞
            
        Raises:
            FileNotFoundError: 如果提示詞檔案不存在
            KeyError: 如果缺少必要的格式化參數
        """
        tool_prompts_dir = Path("prompt_system/tool_prompts")
        prompt_file = tool_prompts_dir / f"{prompt_name}.txt"
        
        if not prompt_file.exists():
            raise FileNotFoundError(f"工具提示詞檔案不存在: {prompt_file}")
        
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # 檢查格式字符串
            self._validate_format_string(content, format_args)
            
            # 格式化內容
            return content.format(**format_args)
            
        except Exception as e:
            self.logger.error(f"讀取或格式化工具提示詞失敗 {prompt_file}: {e}")
            raise
    
    
    def get_final_answer_context(self, **format_args) -> str:
        """獲取最終答案上下文提示詞"""
        try:
            result = self.get_tool_prompt("final_answer_context", **format_args)
            self.logger.debug(f"載入最終答案上下文: {result}")
            return result
        except Exception as e:
            self.logger.error(f"獲取最終答案上下文失敗: {e}")
            return "請根據以下資訊提供完整的回答。"
    
    def get_web_searcher_instructions(self, research_topic: str, current_date: str) -> str:
        """獲取網路搜尋指令"""
        try:
            result = self.get_tool_prompt(
                "web_searcher_instructions",
                research_topic=research_topic,
                current_date=current_date
            )
            self.logger.debug(f"載入網路搜尋指令: {result}")
            return result
        except Exception as e:
            self.logger.error(f"獲取網路搜尋指令失敗: {e}")
            return f"搜尋關於「{research_topic}」的最新資訊。當前日期：{current_date}"
    
    def _load_json_template(self, template_name: str) -> str:
        """載入 JSON 模板檔案"""
        try:
            tool_prompts_dir = Path("prompt_system/tool_prompts")
            template_file = tool_prompts_dir / f"{template_name}.txt"
            
            if template_file.exists():
                with open(template_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            else:
                self.logger.warning(f"JSON 模板檔案不存在: {template_file}")
                return ""
                
        except Exception as e:
            self.logger.error(f"載入 JSON 模板失敗: {e}")
            return ""
    
    def _validate_format_string(self, content: str, format_args: Dict[str, Any]) -> None:
        """
        驗證格式字符串，確保所有必需的參數都存在
        
        Args:
            content: 提示詞內容
            format_args: 格式化參數
            
        Raises:
            KeyError: 如果缺少必要的格式化參數
        """
        import re
        
        # 移除 JSON 示例區塊，避免誤判
        # 查找 {{ 和 }} 之間的內容（JSON 示例）
        json_pattern = r'\{\{.*?\}\}'
        content_without_json = re.sub(json_pattern, '', content, flags=re.DOTALL)
        
        # 查找所有格式字符串 {parameter_name}
        format_pattern = r'\{([^}]+)\}'
        required_params = set(re.findall(format_pattern, content_without_json))
        
        # 檢查所有必需參數是否存在
        missing_params = required_params - set(format_args.keys())
        if missing_params:
            raise KeyError(f"缺少必要的格式化參數: {missing_params}")
    
    def get_available_tool_prompts(self) -> List[str]:
        """獲取可用的工具提示詞列表"""
        tool_prompts_dir = Path("prompt_system/tool_prompts")
        if not tool_prompts_dir.exists():
            return []
        
        try:
            prompt_files = list(tool_prompts_dir.glob("*.txt"))
            return [f.stem for f in prompt_files]
        except Exception as e:
            self.logger.error(f"獲取工具提示詞列表時出錯: {e}")
            return []


# 全域提示詞系統實例
_prompt_system = None

def get_prompt_system() -> PromptSystem:
    """獲取全域提示詞系統實例"""
    global _prompt_system
    if _prompt_system is None:
        _prompt_system = PromptSystem()
    return _prompt_system

def get_current_date(timezone_str: str = DEFAULT_TIMEZONE) -> str:
    """獲取當前日期字串"""
    try:
        tz = pytz.timezone(timezone_str)
        current_time = datetime.now(tz)
        return current_time.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logging.getLogger(__name__).warning(f"獲取當前日期時出錯: {e}")
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
