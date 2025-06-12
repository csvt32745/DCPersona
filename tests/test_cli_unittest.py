import unittest
import sys
import io
from contextlib import redirect_stdout
import os

# 調整導入路徑，確保可以找到 AgentCLI 模組
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cli_main import AgentCLI

class TestAgentCLI(unittest.TestCase):

    def setUp(self):
        """在每個測試方法執行前初始化 CLI"""
        self.cli = AgentCLI()

    def test_cli_initialization(self):
        """測試 CLI 初始化及配置顯示"""
        print("\n🧪 測試 CLI 初始化...")
        f = io.StringIO()
        with redirect_stdout(f):
            self.cli.display_config()
        config_output = f.getvalue()
        self.assertIn("當前配置", config_output, "配置顯示功能異常")
        print("✅ CLI 初始化成功")
        print("✅ 配置顯示功能正常")

    def test_cli_processing(self):
        """測試 CLI 處理邏輯"""
        print("\n🧪 測試 CLI 處理邏輯...")
        response = self.cli.process_user_input("你好")
        print(f"  測試對話: '你好' -> '{response[:50]}...'")
        self.assertTrue(response and len(response) > 5, "CLI 處理邏輯異常或返回空值")
        print("✅ CLI 處理邏輯正常")

if __name__ == '__main__':
    unittest.main() 