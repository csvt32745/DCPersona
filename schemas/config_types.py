"""
型別安全的配置結構定義

使用 dataclass 定義各種配置類型，提供型別安全的配置載入和存取功能。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import yaml
import logging
import os
from dotenv import load_dotenv


def _default_progress_messages() -> Dict[str, str]:
    """預設進度訊息映射
    
    返回預設的進度階段到訊息的映射
    """
    # 延遲導入避免循環依賴
    from agent_core.progress_types import ProgressStage
    return {
        ProgressStage.STARTING.value: "🔄 正在處理您的訊息...",
        ProgressStage.GENERATE_QUERY.value: "🤔 正在分析您的問題...",
        ProgressStage.SEARCHING.value: "🔍 正在搜尋資料...",
        ProgressStage.ANALYZING.value: "🧠 正在分析資訊...",
        ProgressStage.COMPLETING.value: "⏳ 正在整理答案...",
        ProgressStage.STREAMING.value: "🔄 正在回答...",
        ProgressStage.COMPLETED.value: "✅ 研究完成！正在準備回答...",
        ProgressStage.ERROR.value: "❌ 處理時發生錯誤",
        ProgressStage.TIMEOUT.value: "⏰ 處理逾時",
        ProgressStage.TOOL_EXECUTION.value: "🛠️ 正在執行工具...",
        ProgressStage.TOOL_STATUS.value: "🔧 正在平行執行工具...",  # 新增工具狀態預設訊息
        ProgressStage.REFLECTION.value: "🤔 正在反思結果...",
        ProgressStage.FINALIZE_ANSWER.value: "✍️ 正在整理答案...",
    }


@dataclass
class ToolConfig:
    """工具配置"""
    enabled: bool = False
    priority: int = 999
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamingConfig:
    """串流配置"""
    enabled: bool = True
    min_content_length: int = 100  # 最小內容長度才啟用串流


@dataclass 
class ToolDescriptionConfig:
    """工具描述配置"""
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 999


@dataclass
class AgentBehaviorConfig:
    """Agent 行為配置"""
    max_tool_rounds: int = 1
    timeout_per_round: int = 30
    enable_reflection: bool = True
    enable_progress: bool = True


@dataclass
class AgentThresholdsConfig:
    """Agent 決策閾值配置"""
    tool_usage: float = 0.3
    completion: float = 0.8
    confidence: float = 0.7


@dataclass
class AgentConfig:
    """Agent 核心配置"""
    tools: Dict[str, ToolConfig] = field(default_factory=dict)
    behavior: AgentBehaviorConfig = field(default_factory=AgentBehaviorConfig)
    thresholds: AgentThresholdsConfig = field(default_factory=AgentThresholdsConfig)


@dataclass
class DiscordContextData:
    """Discord 上下文資料結構"""
    bot_id: str = ""
    bot_name: str = ""
    channel_id: str = ""
    channel_name: str = ""
    guild_name: Optional[str] = None
    user_id: str = ""
    user_name: str = ""
    mentions: List[str] = field(default_factory=list)


@dataclass
class DiscordPermissionsConfig:
    """Discord 權限配置"""
    allow_dms: bool = False
    users: Dict[str, List[int]] = field(default_factory=lambda: {"allowed_ids": [], "blocked_ids": []})
    roles: Dict[str, List[int]] = field(default_factory=lambda: {"allowed_ids": [], "blocked_ids": []})
    channels: Dict[str, List[int]] = field(default_factory=lambda: {"allowed_ids": [], "blocked_ids": []})


@dataclass
class EmojiStickerConfig:
    """Emoji 和 Sticker 處理配置"""
    max_emoji_per_message: int = 3
    max_sticker_per_message: int = 2
    max_animated_frames: int = 4
    emoji_sticker_max_size: int = 256
    enable_emoji_processing: bool = True
    enable_sticker_processing: bool = True
    enable_animated_processing: bool = True


@dataclass
class DiscordLimitsConfig:
    """Discord 限制配置"""
    max_text: int = 100000
    max_images: int = 3
    max_messages: int = 25


@dataclass
class DiscordMaintenanceConfig:
    """Discord 維護配置"""
    enabled: bool = False
    message: str = "維護中..."


@dataclass
class DiscordConfig:
    """Discord Bot 配置"""
    bot_token: str = ""
    client_id: str = ""
    status_message: str = "AI Assistant"
    enable_conversation_history: bool = True
    limits: DiscordLimitsConfig = field(default_factory=DiscordLimitsConfig)
    permissions: DiscordPermissionsConfig = field(default_factory=DiscordPermissionsConfig)
    maintenance: DiscordMaintenanceConfig = field(default_factory=DiscordMaintenanceConfig)
    emoji_sticker: EmojiStickerConfig = field(default_factory=EmojiStickerConfig)


@dataclass
class LLMModelConfig:
    """LLM 模型配置"""
    model: str = "gemini-2.0-flash-exp"
    temperature: float = 0.7


@dataclass
class LLMProviderConfig:
    """LLM 提供商配置"""
    base_url: Optional[str] = None
    api_key: str = ""


@dataclass
class LLMConfig:
    """LLM 配置"""
    default_model: str = "openai/gemini-2.0-flash-exp"
    providers: Dict[str, LLMProviderConfig] = field(default_factory=dict)
    models: Dict[str, LLMModelConfig] = field(default_factory=dict)


@dataclass
class PromptPersonaConfig:
    """提示詞 Persona 配置（統一的系統提示詞管理）"""
    enabled: bool = True
    random_selection: bool = True
    cache_personas: bool = True
    default_persona: str = "default"
    persona_directory: str = "persona"
    fallback: str = "你是一個有用的 AI 助手。"


@dataclass
class PromptDiscordIntegrationConfig:
    """提示詞 Discord 整合配置"""
    include_timestamp: bool = True
    include_mentions: bool = True
    include_user_context: bool = True


@dataclass
class PromptSystemConfig:
    """提示詞系統配置"""
    persona: PromptPersonaConfig = field(default_factory=PromptPersonaConfig)
    discord_integration: PromptDiscordIntegrationConfig = field(default_factory=PromptDiscordIntegrationConfig)


@dataclass
class ProgressDiscordConfig:
    """Discord 進度更新配置"""
    enabled: bool = True
    use_embeds: bool = True
    update_interval: int = 2  # 秒
    cleanup_delay: int = 30   # 完成後清理延遲
    show_percentage: bool = True
    show_eta: bool = False
    messages: Dict[str, str] = field(default_factory=lambda: _default_progress_messages())


@dataclass
class ProgressCLIConfig:
    """CLI 進度更新配置"""
    enabled: bool = True
    show_percentage: bool = True
    show_eta: bool = True


@dataclass
class ProgressConfig:
    """進度更新配置"""
    discord: ProgressDiscordConfig = field(default_factory=ProgressDiscordConfig)
    cli: ProgressCLIConfig = field(default_factory=ProgressCLIConfig)


@dataclass
class SystemConfig:
    """系統配置"""
    timezone: str = "Asia/Taipei"
    debug_mode: bool = False
    log_level: str = "INFO"


@dataclass
class ReminderConfig:
    """提醒功能配置"""
    enabled: bool = True
    persistence_file: str = "data/events.json"
    max_reminders_per_user: int = 10
    cleanup_expired_events: bool = True


@dataclass
class DevelopmentConfig:
    """開發與測試配置"""
    debug_mode: bool = False
    save_sessions: bool = True
    session_file: str = "sessions.json"
    langgraph_test_mode: bool = False
    mock_research_responses: bool = False
    enable_mock_tools: bool = False
    test_mode: bool = False


class ConfigurationError(Exception):
    """配置錯誤異常"""
    pass


@dataclass
class AppConfig:
    """應用程式總配置"""
    system: SystemConfig = field(default_factory=SystemConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    prompt_system: PromptSystemConfig = field(default_factory=PromptSystemConfig)
    progress: ProgressConfig = field(default_factory=ProgressConfig)
    development: DevelopmentConfig = field(default_factory=DevelopmentConfig)
    streaming: StreamingConfig = field(default_factory=StreamingConfig)
    reminder: ReminderConfig = field(default_factory=ReminderConfig)
    
    def __post_init__(self):
        """初始化後處理，載入環境變數"""
        # 載入 .env 文件
        load_dotenv()
        
        # 從環境變數讀取 Gemini API Key
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if gemini_api_key:
            # 設置到 LLM 提供商配置中
            if 'google' not in self.llm.providers:
                from schemas.config_types import LLMProviderConfig
                self.llm.providers['google'] = LLMProviderConfig()
            self.llm.providers['google'].api_key = gemini_api_key
    
    @classmethod
    def from_yaml(cls, config_path: str) -> 'AppConfig':
        """從 YAML 文件載入配置
        
        Args:
            config_path: 配置文件路徑
            
        Returns:
            AppConfig: 配置實例
            
        Raises:
            ConfigurationError: 配置載入失敗時拋出
        """
        try:
            config_file = Path(config_path)
            
            if not config_file.exists():
                logging.warning(f"配置檔案不存在: {config_path}，使用預設配置")
                return cls()
            
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            # 載入預設配置（如果存在）
            config_dir = config_file.parent
            example_path = config_dir / "config-example.yaml"
            
            default_data = {}
            if example_path.exists():
                try:
                    with open(example_path, 'r', encoding='utf-8') as f:
                        default_data = yaml.safe_load(f) or {}
                    logging.debug(f"載入預設配置: {example_path}")
                except Exception as e:
                    logging.warning(f"載入預設配置失敗: {e}")
            
            # 合併配置
            if default_data:
                merged_data = cls._deep_merge(default_data, data)
            else:
                merged_data = data
            
            # 驗證配置
            cls._validate_config(merged_data)
            
            return cls._dict_to_dataclass(merged_data, cls)
            
        except Exception as e:
            logging.error(f"配置載入失敗: {e}")
            raise ConfigurationError(f"無法載入配置 {config_path}: {e}")
    
    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """深度合併兩個字典"""
        from copy import deepcopy
        
        result = deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = AppConfig._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result
    
    @staticmethod
    def _validate_config(data: Dict[str, Any]) -> None:
        """驗證配置數據"""
        if not isinstance(data, dict):
            raise ConfigurationError("配置必須是字典格式")
        
        # 驗證必要的 API 金鑰（現在從環境變數讀取）
        if not os.getenv('GEMINI_API_KEY'):
            raise ConfigurationError("未設置 GEMINI_API_KEY 環境變數")
        
        # 驗證 Discord 配置
        discord_config = data.get("discord", {})
        if isinstance(discord_config, dict):
            if not discord_config.get("bot_token"):
                logging.warning("未設置 Discord bot_token，Discord 功能將無法使用")
        
        # 驗證進度訊息配置的 key
        progress_config = data.get("progress", {})
        if isinstance(progress_config, dict):
            discord_progress = progress_config.get("discord", {})
            if isinstance(discord_progress, dict):
                messages_config = discord_progress.get("messages", {})
                if isinstance(messages_config, dict):
                    AppConfig._validate_progress_message_keys(messages_config)
    
    @staticmethod
    def _validate_progress_message_keys(messages_config: Dict[str, str]) -> None:
        """驗證進度訊息配置的 key 是否有效
        
        Args:
            messages_config: 進度訊息配置字典
        """
        try:
            from agent_core.progress_types import ProgressStage
            
            # 獲取所有有效的 ProgressStage 值
            valid_keys = {stage.value for stage in ProgressStage}
            
            # 檢查配置中的 key
            invalid_keys = []
            for key in messages_config.keys():
                if key not in valid_keys:
                    invalid_keys.append(key)
            
            # 如果有無效的 key，記錄警告
            if invalid_keys:
                logging.warning(f"進度訊息配置中發現無效的 key: {invalid_keys}")
                logging.warning(f"有效的 ProgressStage key: {sorted(valid_keys)}")
                # 不拋出異常，只記錄警告，讓配置可以繼續載入
        
        except ImportError:
            # 如果無法導入 ProgressStage，記錄警告但不驗證
            logging.warning("無法導入 ProgressStage 進行 key 驗證")
    
    @classmethod
    def _dict_to_dataclass(cls, data: Dict[str, Any], dataclass_type):
        """將字典轉換為 dataclass
        
        Args:
            data: 配置字典
            dataclass_type: 目標 dataclass 類型
            
        Returns:
            dataclass 實例
        """
        if not isinstance(data, dict):
            return data
        
        # 獲取字段定義
        field_types = {}
        if hasattr(dataclass_type, '__dataclass_fields__'):
            field_types = {f.name: f.type for f in dataclass_type.__dataclass_fields__.values()}
        
        # 轉換數據
        converted_data = {}
        # 定義已移除的向後兼容字段
        deprecated_fields = {
            'llm_models', 'model', 'bot_token', 
            'extra_api_parameters', 'use_plain_responses', 'is_maintainance',
            'reject_resp', 'maintainance_resp', 'is_random_system_prompt',
            'system_prompt_file', 'system_prompt', 'langgraph'
        }
        
        # 定義字段映射（舊字段名 -> 新字段名）
        field_mappings = {
            'default_file': 'default_persona'  # persona 配置中的舊字段
        }
        
        for key, value in data.items():
            # 檢查是否需要字段映射
            actual_key = field_mappings.get(key, key)
            
            if actual_key in field_types:
                field_type = field_types[actual_key]
                
                # 處理嵌套 dataclass
                if hasattr(field_type, '__dataclass_fields__'):
                    converted_data[actual_key] = cls._dict_to_dataclass(value, field_type)
                # 處理 Dict[str, dataclass] 類型
                elif hasattr(field_type, '__origin__') and field_type.__origin__ is dict:
                    args = getattr(field_type, '__args__', ())
                    if len(args) == 2 and hasattr(args[1], '__dataclass_fields__'):
                        # Dict[str, SomeDataclass] 類型
                        converted_dict = {}
                        for k, v in value.items():
                            converted_dict[k] = cls._dict_to_dataclass(v, args[1])
                        converted_data[actual_key] = converted_dict
                    else:
                        converted_data[actual_key] = value
                else:
                    converted_data[actual_key] = value
            elif key not in deprecated_fields and key not in field_mappings:
                # 未知字段但不是已棄用的字段或映射字段，直接保留（向後相容性）
                converted_data[key] = value
            # 已棄用的字段和映射字段會被忽略或轉換
        
        return dataclass_type(**converted_data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """從字典載入配置
        
        Args:
            data: 配置字典
            
        Returns:
            AppConfig: 配置實例
        """
        # 驗證配置
        cls._validate_config(data)
        
        return cls._dict_to_dataclass(data, cls)
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        return self._dataclass_to_dict(self)
    
    @staticmethod
    def _dataclass_to_dict(obj) -> Any:
        """將 dataclass 轉換為字典
        
        Args:
            obj: dataclass 實例
            
        Returns:
            Any: 轉換後的數據
        """
        if hasattr(obj, '__dataclass_fields__'):
            result = {}
            for field_name in obj.__dataclass_fields__:
                value = getattr(obj, field_name)
                result[field_name] = AppConfig._dataclass_to_dict(value)
            return result
        elif isinstance(obj, dict):
            return {k: AppConfig._dataclass_to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [AppConfig._dataclass_to_dict(item) for item in obj]
        else:
            return obj
    
    def get_tool_config(self, tool_name: str) -> Optional[ToolConfig]:
        """獲取特定工具的配置
        
        Args:
            tool_name: 工具名稱
            
        Returns:
            Optional[ToolConfig]: 工具配置，如果不存在則返回 None
        """
        return self.agent.tools.get(tool_name)
    
    def is_tool_enabled(self, tool_name: str) -> bool:
        """檢查工具是否啟用
        
        Args:
            tool_name: 工具名稱
            
        Returns:
            bool: 是否啟用
        """
        # 特殊處理 reminder 工具（根據 reminder.enabled）
        if tool_name == "reminder":
            return self.reminder.enabled

        # youtube_summary 預設啟用（若未在 config.tools 中明確設置）
        if tool_name == "youtube_summary":
            tool_config = self.get_tool_config(tool_name)
            return tool_config.enabled if tool_config else True

        tool_config = self.get_tool_config(tool_name)
        return tool_config.enabled if tool_config else False
    
    def get_tool_priority(self, tool_name: str) -> int:
        """獲取工具優先級
        
        Args:
            tool_name: 工具名稱
            
        Returns:
            int: 工具優先級，數字越小優先級越高
        """
        tool_config = self.get_tool_config(tool_name)
        return tool_config.priority if tool_config else 999
    
    def get_enabled_tools(self) -> List[str]:
        """獲取所有啟用的工具列表
        
        Returns:
            List[str]: 啟用的工具名稱列表，按優先級排序
        """
        enabled_tools = []
        for tool_name, tool_config in self.agent.tools.items():
            if tool_config.enabled:
                enabled_tools.append((tool_name, tool_config.priority))
        
        # 特殊處理 reminder 工具
        if self.reminder.enabled:
            enabled_tools.append(("reminder", 2))  # 給 reminder 一個中等優先級
        
        # 按優先級排序
        enabled_tools.sort(key=lambda x: x[1])
        return [tool_name for tool_name, _ in enabled_tools]
    
    @property
    def gemini_api_key(self) -> str:
        """獲取 Gemini API Key（向後兼容性屬性）
        
        Returns:
            str: Gemini API Key
        """
        # 優先從環境變數讀取
        env_key = os.getenv('GEMINI_API_KEY')
        if env_key:
            return env_key
        
        # 從 LLM 提供商配置讀取
        google_provider = self.llm.providers.get('google')
        if google_provider and google_provider.api_key:
            return google_provider.api_key
        
        return "" 