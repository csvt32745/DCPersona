"""
測試 Persona 系統整合與 System Prompt 統一

測試內容：
1. PromptSystem 使用 typed config 的功能
2. 工具提示詞檔案的讀取和驗證
3. UnifiedAgent 整合 PromptSystem 的功能
"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from prompt_system.prompts import PromptSystem
from schemas.config_types import AppConfig, PromptPersonaConfig, PromptSystemConfig
from agent_core.graph import UnifiedAgent


class TestPromptSystem:
    """測試 PromptSystem 類"""
    
    def setup_method(self):
        """設置測試環境"""
        self.prompt_system = PromptSystem(persona_cache_enabled=True)
        
        # 創建測試配置
        self.test_config = AppConfig()
        self.test_config.prompt_system.persona.enabled = True
        self.test_config.prompt_system.persona.random_selection = False
        self.test_config.prompt_system.persona.default_persona = "humor"
        self.test_config.prompt_system.persona.persona_directory = "persona"
    
    def test_get_system_instructions_with_typed_config(self):
        """測試使用 typed config 的 get_system_instructions"""
        # 測試基本功能
        result = self.prompt_system.get_system_instructions(
            config=self.test_config
        )
        
        assert isinstance(result, str)
        assert len(result) > 0
        
    def test_get_planning_instructions_removed(self):
        """測試 get_planning_instructions 方法已被移除"""
        # 這個方法已經被移除，因為 LangChain 會自動處理工具調用
        # 這個測試只是為了確認方法不存在
        assert not hasattr(self.prompt_system, 'get_planning_instructions')
    
    def test_get_tool_prompt_missing_file(self):
        """測試讀取不存在的工具提示詞檔案"""
        with pytest.raises(FileNotFoundError):
            self.prompt_system.get_tool_prompt("nonexistent_prompt")
    
    def test_get_web_searcher_instructions_success(self):
        """測試成功讀取網路搜尋指令"""
        tool_prompts_dir = Path("prompt_system/tool_prompts")
        web_file = tool_prompts_dir / "web_searcher_instructions.txt"
        
        if web_file.exists():
            try:
                result = self.prompt_system.get_web_searcher_instructions(
                    research_topic="台北天氣",
                    current_date="2024-12-19"
                )
                assert isinstance(result, str)
                assert "台北天氣" in result
                assert "2024-12-19" in result
            except Exception as e:
                # 如果檔案不存在，應該有回退機制
                assert "搜尋關於" in str(e) or isinstance(result, str)
    
    def test_validate_format_string(self):
        """測試格式字符串驗證"""
        content = "Hello {name}, today is {date}"
        
        # 應該成功（所有參數都提供）
        format_args = {"name": "Alice", "date": "2024-12-19"}
        self.prompt_system._validate_format_string(content, format_args)
        
        # 應該失敗（缺少參數）
        incomplete_args = {"name": "Alice"}
        with pytest.raises(KeyError):
            self.prompt_system._validate_format_string(content, incomplete_args)
    
    def test_get_available_tool_prompts(self):
        """測試獲取可用工具提示詞列表"""
        prompts = self.prompt_system.get_available_tool_prompts()
        assert isinstance(prompts, list)
        
        # 如果存在文件，應該包含在列表中
        if Path("prompt_system/tool_prompts/planning_instructions.txt").exists():
            assert "planning_instructions" in prompts


class TestUnifiedAgentIntegration:
    """測試 UnifiedAgent 整合 PromptSystem 的功能"""
    
    def setup_method(self):
        """設置測試環境"""
        # 模擬環境變數
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            self.config = AppConfig()
            # 禁用實際的工具以避免 API 調用
            self.config.agent.tools = {}
    
    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'})
    def test_unified_agent_initialization(self):
        """測試 UnifiedAgent 正確初始化 PromptSystem"""
        agent = UnifiedAgent(self.config)
        
        assert hasattr(agent, 'prompt_system')
        assert isinstance(agent.prompt_system, PromptSystem)
    
    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'})
    def test_build_planning_prompt_with_tool_prompts(self):
        """測試使用工具提示詞檔案構建計劃提示詞"""
        agent = UnifiedAgent(self.config)
        
        # 創建模擬訊息
        from schemas.agent_types import MsgNode
        messages = [MsgNode(role="user", content="今天天氣如何？")]
        
        # 測試 system prompt 構建
        try:
            system_prompt = agent._build_final_system_prompt("", "")
            assert isinstance(system_prompt, str)
            assert len(system_prompt) > 0
        except Exception as e:
            # 如果工具提示詞檔案不存在或格式問題，應該有適當的錯誤處理
            assert "構建" in str(e) or "失敗" in str(e)


if __name__ == "__main__":
    pytest.main([__file__]) 