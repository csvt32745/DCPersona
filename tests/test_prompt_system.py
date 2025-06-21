"""
測試 prompt_system/prompts.py 模組
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from prompt_system.prompts import (
    PromptSystem, 
    get_prompt_system,
    MULTIMODAL_GUIDANCE
)
from utils.config_loader import load_typed_config


class TestPromptSystem:
    """測試 PromptSystem 類別"""
    
    def test_prompt_system_creation(self):
        """測試提示詞系統創建"""
        system = PromptSystem()
        
        assert system.persona_cache_enabled is True
        assert len(system._persona_cache) == 0
    
    def test_get_prompt_file_exists(self):
        """測試讀取存在的提示詞檔案"""
        system = PromptSystem()
        
        # 創建臨時檔案
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            test_content = "這是測試提示詞內容"
            f.write(test_content)
            temp_path = f.name
        
        try:
            content = system.get_prompt(temp_path)
            assert content == test_content
        finally:
            os.unlink(temp_path)
    
    def test_get_prompt_file_not_exists(self):
        """測試讀取不存在的提示詞檔案"""
        system = PromptSystem()
        
        content = system.get_prompt("不存在的檔案.txt")
        assert content == ""
    
    def test_random_system_prompt_with_files(self):
        """測試有檔案時的隨機提示詞選擇"""
        system = PromptSystem()
        
        # 創建臨時目錄和檔案
        with tempfile.TemporaryDirectory() as temp_dir:
            # 創建測試檔案
            test_files = [
                ("persona1.txt", "這是 persona 1"),
                ("persona2.txt", "這是 persona 2"),
            ]
            
            for filename, content in test_files:
                with open(Path(temp_dir) / filename, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            # 測試隨機選擇
            content = system.random_system_prompt(temp_dir)
            assert content in ["這是 persona 1", "這是 persona 2"]
    
    def test_random_system_prompt_no_files(self):
        """測試無檔案時的隨機提示詞選擇"""
        system = PromptSystem()
        
        # 使用空目錄
        with tempfile.TemporaryDirectory() as temp_dir:
            content = system.random_system_prompt(temp_dir)
            assert content == ""
    
    def test_get_specific_persona(self):
        """測試獲取特定 persona"""
        system = PromptSystem()
        
        # 創建臨時目錄和檔案
        with tempfile.TemporaryDirectory() as temp_dir:
            test_content = "這是特定的 persona"
            with open(Path(temp_dir) / "test_persona.txt", 'w', encoding='utf-8') as f:
                f.write(test_content)
            
            content = system.get_specific_persona("test_persona", temp_dir)
            assert content == test_content
    
    def test_get_specific_persona_not_exists(self):
        """測試獲取不存在的 persona"""
        system = PromptSystem()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            content = system.get_specific_persona("不存在的persona", temp_dir)
            assert content == ""
    
    def test_persona_cache(self):
        """測試 persona 快取功能"""
        system = PromptSystem(persona_cache_enabled=True)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_content = "這是快取測試"
            with open(Path(temp_dir) / "cache_test.txt", 'w', encoding='utf-8') as f:
                f.write(test_content)
            
            # 第一次載入
            content1 = system.get_specific_persona("cache_test", temp_dir)
            assert content1 == test_content
            assert "cache_test" in system._persona_cache
            
            # 第二次載入（應該從快取）
            content2 = system.get_specific_persona("cache_test", temp_dir)
            assert content2 == test_content
    

    
    @patch('prompt_system.prompts.pytz')
    @patch('prompt_system.prompts.datetime')
    def test_build_timestamp_info(self, mock_datetime, mock_pytz):
        """測試時間戳資訊建立"""
        from schemas.config_types import AppConfig
        system = PromptSystem()
        
        # Mock datetime
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2024-01-01 12:00:00 CST"
        mock_datetime.now.return_value = mock_now
        
        # Mock timezone
        mock_tz = MagicMock()
        mock_pytz.timezone.return_value = mock_tz
        
        # 使用 typed config
        config = AppConfig()
        config.prompt_system.discord_integration.include_timestamp = True
        config.system.timezone = "Asia/Taipei"
        
        timestamp_info = system._build_timestamp_info(config)
        assert "當前時間" in timestamp_info
        assert "2024-01-01 12:00:00 CST" in timestamp_info
    




    def test_clear_persona_cache(self):
        """測試清理 persona 快取"""
        system = PromptSystem()
        system._persona_cache["test"] = "測試內容"
        
        assert len(system._persona_cache) == 1
        system.clear_persona_cache()
        assert len(system._persona_cache) == 0
    
    def test_get_available_personas(self):
        """測試獲取可用 persona 列表"""
        system = PromptSystem()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # 創建測試檔案
            test_files = ["persona1.txt", "persona2.txt", "not_txt.md"]
            for filename in test_files:
                with open(Path(temp_dir) / filename, 'w') as f:
                    f.write("測試")
            
            personas = system.get_available_personas(temp_dir)
            assert "persona1" in personas
            assert "persona2" in personas
            assert "not_txt" not in personas  # 應該過濾非 .txt 檔案
    
    def test_get_cache_stats(self):
        """測試快取統計資訊"""
        system = PromptSystem()
        system._persona_cache["test1"] = "內容1"
        system._persona_cache["test2"] = "內容2"
        
        stats = system.get_cache_stats()
        assert stats["cache_enabled"] is True
        assert stats["cache_size"] == 2
        assert "test1" in stats["cached_personas"]
        assert "test2" in stats["cached_personas"]


def test_get_prompt_system():
    """測試全域提示詞系統獲取"""
    system1 = get_prompt_system()
    system2 = get_prompt_system()
    
    # 應該是同一個實例
    assert system1 is system2


class TestPromptSystemLangChainAdaptation:
    """測試 PromptSystem 對 LangChain 工具綁定的適配"""
    
    def setup_method(self):
        """設置測試環境"""
        self.prompt_system = PromptSystem()
        self.config = load_typed_config()
    
    def test_get_system_instructions_without_tools(self):
        """測試不使用工具時的系統指令生成"""
        result = self.prompt_system.get_system_instructions(
            config=self.config,
            messages_global_metadata="測試 metadata"
        )
        
        # 應該包含基本的系統指令
        assert isinstance(result, str)
        assert len(result) > 0

    def test_system_instructions_include_multimodal_guidance(self):
        """測試系統指令是否包含多媒體處理指導"""
        result = self.prompt_system.get_system_instructions(
            config=self.config,
            messages_global_metadata="測試 metadata"
        )
        
        assert MULTIMODAL_GUIDANCE in result


if __name__ == "__main__":
    # 運行基本測試
    test_instance = TestPromptSystemLangChainAdaptation()
    test_instance.setup_method()
    
    test_instance.test_get_system_instructions_without_tools()
    test_instance.test_get_system_instructions_with_deprecated_tools_param()
    test_instance.test_backward_compatibility()
    test_instance.test_system_instructions_include_multimodal_guidance()
    
    print("PromptSystem LangChain 適配測試通過！") 