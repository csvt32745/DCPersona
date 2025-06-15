"""
簡單的 PromptSystem LangChain 適配測試
"""

import logging
from unittest.mock import Mock

from prompt_system.prompts import PromptSystem
from schemas.config_types import AppConfig


def test_generate_tool_descriptions_removed():
    """測試 generate_tool_descriptions 方法已移除"""
    prompt_system = PromptSystem()
    
    # 方法應該不存在
    assert not hasattr(prompt_system, 'generate_tool_descriptions')
    print("✅ generate_tool_descriptions 移除測試通過")


def test_get_planning_instructions_removed():
    """測試 get_planning_instructions 方法已移除"""
    prompt_system = PromptSystem()
    
    # 方法應該不存在
    assert not hasattr(prompt_system, 'get_planning_instructions')
    print("✅ get_planning_instructions 移除測試通過")


def test_get_system_instructions_without_tools():
    """測試系統指令生成（不再需要工具參數）"""
    prompt_system = PromptSystem()
    
    # 創建一個最小的配置
    config = AppConfig()
    
    result = prompt_system.get_system_instructions(
        config=config,
        messages_global_metadata="測試 metadata"
    )
    
    # 應該包含基本的系統指令
    assert isinstance(result, str)
    assert len(result) > 0
    # 不應該包含工具描述
    assert "我的能力包括" not in result
    
    print("✅ get_system_instructions 測試通過")


def test_clean_interface():
    """測試簡潔的介面"""
    prompt_system = PromptSystem()
    config = AppConfig()
    
    # 新的簡潔調用方式
    result = prompt_system.get_system_instructions(
        config=config
    )
    
    assert isinstance(result, str)
    assert len(result) > 0
    
    print("✅ 簡潔介面測試通過")


if __name__ == "__main__":
    print("開始 PromptSystem LangChain 適配測試...")
    
    test_generate_tool_descriptions_removed()
    test_get_planning_instructions_removed()
    test_get_system_instructions_without_tools()
    test_clean_interface()
    
    print("🎉 所有 PromptSystem LangChain 適配測試通過！") 