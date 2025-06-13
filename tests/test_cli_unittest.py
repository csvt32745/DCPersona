import unittest
import sys
import io
from contextlib import redirect_stdout
import os
from unittest.mock import patch, MagicMock

# 調整導入路徑，確保可以找到 AgentCLI 模組
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cli_main import CLIInterface
from schemas.config_types import AppConfig, AgentConfig, AgentBehaviorConfig, LLMConfig

class TestAgentCLI(unittest.TestCase):

    def setUp(self):
        """在每個測試方法執行前初始化 CLI"""
        # 創建測試配置
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            test_config = AppConfig(
                agent=AgentConfig(
                    behavior=AgentBehaviorConfig(max_tool_rounds=1)
                )
            )
            self.cli = CLIInterface(test_config)

    def test_cli_initialization(self):
        """測試 CLI 初始化及配置顯示"""
        print("\n🧪 測試 CLI 初始化...")
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.show_config_info()
        config_output = f.getvalue()
        self.assertIn("配置資訊", config_output, "配置顯示功能異常")
        print("✅ CLI 初始化成功")
        print("✅ 配置顯示功能正常")

    def test_cli_processing(self):
        """測試 CLI 處理邏輯"""
        print("\n🧪 測試 CLI 處理邏輯...")
        # 測試選單功能
        with patch('builtins.input', return_value='4'):  # 選擇退出
            choice = self.cli.show_interactive_menu()
            self.assertEqual(choice, 4, "選單處理邏輯異常")
        print("✅ CLI 處理邏輯正常")

if __name__ == '__main__':
    unittest.main() 