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
    random_system_prompt, 
    build_system_prompt
)


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
    
    def test_build_system_prompt_basic(self):
        """測試基本系統提示詞建立"""
        system = PromptSystem()
        
        cfg = {
            "system_prompt": "基礎系統提示詞",
            "is_random_system_prompt": False
        }
        
        prompt = system.build_system_prompt(cfg)
        assert "基礎系統提示詞" in prompt
    
    def test_build_system_prompt_with_discord_context(self):
        """測試包含 Discord 上下文的系統提示詞建立"""
        system = PromptSystem()
        
        cfg = {
            "system_prompt": "基礎提示詞",
            "prompt_system": {
                "discord_integration": {
                    "include_timestamp": False  # 關閉時間戳避免測試複雜性
                }
            }
        }
        
        discord_context = {
            "bot_id": "123456789",
            "channel_id": "987654321",
            "guild_name": "測試伺服器"
        }
        
        prompt = system.build_system_prompt(cfg, discord_context)
        assert "基礎提示詞" in prompt
        assert "Discord 環境資訊" in prompt
        assert "123456789" in prompt
        assert "測試伺服器" in prompt
    
    @patch('prompt_system.prompts.pytz')
    @patch('prompt_system.prompts.datetime')
    def test_build_timestamp_info(self, mock_datetime, mock_pytz):
        """測試時間戳資訊建立"""
        system = PromptSystem()
        
        # Mock datetime
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2024-01-01 12:00:00 CST"
        mock_datetime.now.return_value = mock_now
        
        # Mock timezone
        mock_tz = MagicMock()
        mock_pytz.timezone.return_value = mock_tz
        
        cfg = {
            "prompt_system": {
                "discord_integration": {
                    "include_timestamp": True,
                    "timezone": "Asia/Taipei"
                }
            }
        }
        
        timestamp_info = system._build_timestamp_info(cfg)
        assert "當前時間" in timestamp_info
        assert "2024-01-01 12:00:00 CST" in timestamp_info
    
    def test_generate_tool_descriptions(self):
        """測試工具說明生成"""
        system = PromptSystem()
        
        tools = ["google_search"]
        descriptions = system.generate_tool_descriptions(tools)
        
        assert "我的能力包括" in descriptions
        assert "我可以提供網路搜尋結果" in descriptions
        assert "來源引用" not in descriptions # Ensure citation is removed
    
    def test_generate_tool_descriptions_empty(self):
        system = PromptSystem()
        descriptions = system.generate_tool_descriptions([])
        assert "我的能力包括" not in descriptions
        assert "沒有可用的工具" not in descriptions # This assertion was incorrect, empty should return empty string.

    def test_generate_tool_descriptions_unsupported(self):
        system = PromptSystem()
        descriptions = system.generate_tool_descriptions(["unsupported_tool"])
        assert "我的能力包括" not in descriptions  # 修正：不應包含此字串
        assert descriptions == ""  # 修正：應返回空字串

    def test_generate_tool_descriptions_multiple(self):
        system = PromptSystem()
        descriptions = system.generate_tool_descriptions(["google_search", "web_research"])
        
        assert "我的能力包括" in descriptions
        assert "我可以提供網路搜尋結果" in descriptions
        assert "我可以進行深度網路研究和分析" in descriptions

    def test_get_system_instructions_without_tools(self):
        system = PromptSystem()
        cfg = {"system_prompt": "你是一個友善、聰明的聊天助手。"}
        system_instructions = system.get_system_instructions(cfg, [])
        assert "你是一個友善、聰明的聊天助手" in system_instructions
        assert "我的能力包括" not in system_instructions # 沒有工具，不應該有此區塊

    def test_get_system_instructions_with_google_search(self):
        system = PromptSystem()
        cfg = {"system_prompt": "你是一個智能搜尋計劃生成器。"}
        system_instructions = system.get_system_instructions(cfg, ["google_search"])
        assert "你是一個智能搜尋計劃生成器" in system_instructions
        assert "我的能力包括" in system_instructions
        assert "我可以提供網路搜尋結果" in system_instructions
        assert "google_search" not in system_instructions  # 確保工具名稱本身不在系統指令中
        assert "web_research" not in system_instructions # 確保其他工具不被提及

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


def test_random_system_prompt_function():
    """測試便利函數 random_system_prompt"""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_content = "便利函數測試"
        with open(Path(temp_dir) / "test.txt", 'w', encoding='utf-8') as f:
            f.write(test_content)
        
        content = random_system_prompt(temp_dir)
        assert content == test_content


def test_build_system_prompt_function():
    """測試便利函數 build_system_prompt"""
    cfg = {
        "system_prompt": "便利函數測試",
        "is_random_system_prompt": False,
        "prompt_system": {
            "discord_integration": {
                "include_timestamp": False
            }
        }
    }
    
    prompt = build_system_prompt(cfg)
    assert "便利函數測試" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 