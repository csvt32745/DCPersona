"""
型別安全的配置結構定義

使用 dataclass 定義各種配置類型，提供型別安全的配置載入和存取功能。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import yaml


@dataclass
class ToolConfig:
    """工具配置"""
    enabled: bool = False
    priority: int = 999
    config: Dict[str, Any] = field(default_factory=dict)


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
class DiscordPermissionsConfig:
    """Discord 權限配置"""
    allow_dms: bool = False
    users: Dict[str, List[int]] = field(default_factory=lambda: {"allowed_ids": [], "blocked_ids": []})
    roles: Dict[str, List[int]] = field(default_factory=lambda: {"allowed_ids": [], "blocked_ids": []})
    channels: Dict[str, List[int]] = field(default_factory=lambda: {"allowed_ids": [], "blocked_ids": []})


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
    limits: DiscordLimitsConfig = field(default_factory=DiscordLimitsConfig)
    permissions: DiscordPermissionsConfig = field(default_factory=DiscordPermissionsConfig)
    maintenance: DiscordMaintenanceConfig = field(default_factory=DiscordMaintenanceConfig)


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
    """提示詞 Persona 配置"""
    enabled: bool = True
    random_selection: bool = True
    cache_personas: bool = True
    default_file: str = "default.txt"


@dataclass
class PromptDiscordIntegrationConfig:
    """提示詞 Discord 整合配置"""
    include_timestamp: bool = True
    include_mentions: bool = True
    include_user_context: bool = True


@dataclass
class PromptSystemPromptConfig:
    """系統提示詞配置"""
    use_file: bool = True
    file: str = "trump.txt"
    fallback: str = "你是一個有用的 AI 助手。"


@dataclass
class PromptSystemConfig:
    """提示詞系統配置"""
    persona: PromptPersonaConfig = field(default_factory=PromptPersonaConfig)
    discord_integration: PromptDiscordIntegrationConfig = field(default_factory=PromptDiscordIntegrationConfig)
    system_prompt: PromptSystemPromptConfig = field(default_factory=PromptSystemPromptConfig)


@dataclass
class ProgressDiscordConfig:
    """Discord 進度更新配置"""
    enabled: bool = True
    use_embeds: bool = True
    update_interval: int = 2  # 秒
    cleanup_delay: int = 30   # 完成後清理延遲


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
class DevelopmentConfig:
    """開發與測試配置"""
    debug_mode: bool = False
    log_level: str = "INFO"
    save_sessions: bool = True
    session_file: str = "sessions.json"
    langgraph_test_mode: bool = False
    mock_research_responses: bool = False
    enable_mock_tools: bool = False
    test_mode: bool = False


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
    
    # 向後相容性：保留舊的配置欄位
    gemini_api_key: str = ""
    llm_models: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    model: str = ""  # 舊格式的預設模型
    bot_token: str = ""  # 舊格式的 bot_token
    extra_api_parameters: Dict[str, Any] = field(default_factory=dict)
    use_plain_responses: bool = False
    is_maintainance: bool = False
    reject_resp: str = ""
    maintainance_resp: str = ""
    is_random_system_prompt: bool = True
    system_prompt_file: str = ""
    system_prompt: str = ""
    langgraph: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_yaml(cls, config_path: str) -> 'AppConfig':
        """從 YAML 文件載入配置
        
        Args:
            config_path: 配置文件路徑
            
        Returns:
            AppConfig: 配置實例
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return cls._dict_to_dataclass(data, cls)
    
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
        for key, value in data.items():
            if key in field_types:
                field_type = field_types[key]
                
                # 處理嵌套 dataclass
                if hasattr(field_type, '__dataclass_fields__'):
                    converted_data[key] = cls._dict_to_dataclass(value, field_type)
                # 處理 Dict[str, dataclass] 類型
                elif hasattr(field_type, '__origin__') and field_type.__origin__ is dict:
                    args = getattr(field_type, '__args__', ())
                    if len(args) == 2 and hasattr(args[1], '__dataclass_fields__'):
                        # Dict[str, SomeDataclass] 類型
                        converted_dict = {}
                        for k, v in value.items():
                            converted_dict[k] = cls._dict_to_dataclass(v, args[1])
                        converted_data[key] = converted_dict
                    else:
                        converted_data[key] = value
                else:
                    converted_data[key] = value
            else:
                # 未知字段，直接保留
                converted_data[key] = value
        
        return dataclass_type(**converted_data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """從字典載入配置
        
        Args:
            data: 配置字典
            
        Returns:
            AppConfig: 配置實例
        """
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
        
        # 按優先級排序
        enabled_tools.sort(key=lambda x: x[1])
        return [tool_name for tool_name, _ in enabled_tools] 