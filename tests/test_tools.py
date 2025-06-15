"""
測試 LangChain 工具功能
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from tools.set_reminder import set_reminder
from tools import GoogleSearchTool
from schemas.agent_types import ReminderDetails, ToolExecutionResult
from schemas.config_types import AppConfig, LLMConfig, LLMModelConfig


class TestSetReminderTool:
    """測試 set_reminder 工具"""
    
    def test_set_reminder_success(self):
        """測試成功設定提醒"""
        future_time = (datetime.now() + timedelta(hours=1)).isoformat()
        
        result = set_reminder.invoke({
            'message': '測試提醒',
            'target_time_str': future_time,
            'channel_id': 'test_channel',
            'user_id': 'test_user'
        })
        
        # 解析 JSON 結果
        result_data = json.loads(result)
        
        assert result_data['success'] is True
        assert '測試提醒' in result_data['message']
        assert 'reminder_details' in result_data['data']
        
    def test_set_reminder_invalid_time_format(self):
        """測試無效時間格式"""
        result = set_reminder.invoke({
            'message': '測試提醒',
            'target_time_str': 'invalid_time',
            'channel_id': 'test_channel',
            'user_id': 'test_user'
        })
        
        result_data = json.loads(result)
        
        assert result_data['success'] is False
        assert 'ISO 8601' in result_data['message']
        
    def test_set_reminder_past_time(self):
        """測試過去時間"""
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        
        result = set_reminder.invoke({
            'message': '測試提醒',
            'target_time_str': past_time,
            'channel_id': 'test_channel',
            'user_id': 'test_user'
        })
        
        result_data = json.loads(result)
        
        assert result_data['success'] is False
        assert '未來時間' in result_data['message']


class TestGoogleSearchTool:
    """測試 GoogleSearchTool"""
    
    def test_google_search_tool_creation(self):
        """測試 GoogleSearchTool 創建"""
        # 暫時只測試類是否可以導入
        assert GoogleSearchTool is not None
        
        # 測試類的基本屬性（通過 model_fields 訪問）
        # 由於這是 Pydantic 模型，我們需要創建實例來測試屬性
        # 但由於需要依賴，我們暫時只測試類的存在
        assert hasattr(GoogleSearchTool, '__name__')
        assert GoogleSearchTool.__name__ == "GoogleSearchTool"
    
    def test_google_search_tool_execution_result_format(self):
        """測試 GoogleSearchTool 返回 ToolExecutionResult 格式"""
        # 創建模擬的配置
        mock_config = Mock()
        mock_config.system = Mock()
        mock_config.system.timezone = "Asia/Taipei"
        mock_config.llm = Mock()
        mock_config.llm.models = {
            "tool_analysis": Mock(model="gemini-1.5-flash")
        }
        
        # 創建模擬的 Google 客戶端
        mock_google_client = Mock()
        mock_response = Mock()
        mock_response.text = "這是搜尋結果"
        mock_google_client.models.generate_content.return_value = mock_response
        
        # 創建模擬的 prompt system
        mock_prompt_system = Mock()
        mock_prompt_system.get_web_searcher_instructions.return_value = "搜尋提示"
        
        # 創建 GoogleSearchTool 實例
        tool = GoogleSearchTool(
            google_client=mock_google_client,
            prompt_system_instance=mock_prompt_system,
            config=mock_config
        )
        
        # 測試 _execute_search 方法
        result = tool._execute_search("測試查詢")
        
        # 驗證返回的是 ToolExecutionResult 實例
        assert isinstance(result, ToolExecutionResult)
        assert result.success is True
        assert result.message == "這是搜尋結果"
        assert "query" in result.data
        assert result.data["query"] == "測試查詢"
    
    def test_google_search_tool_no_client_error(self):
        """測試沒有 Google 客戶端時的錯誤處理"""
        mock_config = Mock()
        mock_config.system = Mock()
        mock_config.system.timezone = "Asia/Taipei"
        
        # 創建沒有客戶端的工具
        tool = GoogleSearchTool(
            google_client=None,
            prompt_system_instance=Mock(),
            config=mock_config
        )
        
        # 測試錯誤情況
        result = tool._execute_search("測試查詢")
        
        # 驗證錯誤結果
        assert isinstance(result, ToolExecutionResult)
        assert result.success is False
        assert "Google 客戶端未配置" in result.message
        assert result.data["query"] == "測試查詢"

    def test_google_search_tool_multiple_queries_sync(self):
        """測試 GoogleSearchTool 同步多個查詢"""
        mock_config = Mock()
        mock_config.system = Mock()
        mock_config.system.timezone = "Asia/Taipei"
        mock_config.llm = Mock()
        mock_config.llm.models = {
            "tool_analysis": Mock(model="gemini-1.5-flash")
        }

        mock_google_client = Mock()
        mock_responses = [
            Mock(text="搜尋結果 1"),
            Mock(text="搜尋結果 2"),
            Mock(text="搜尋結果 3")
        ]
        mock_google_client.models.generate_content.side_effect = mock_responses

        mock_prompt_system = Mock()
        mock_prompt_system.get_web_searcher_instructions.return_value = "搜尋提示"

        tool = GoogleSearchTool(
            google_client=mock_google_client,
            prompt_system_instance=mock_prompt_system,
            config=mock_config
        )

        queries = ["查詢 1", "查詢 2", "查詢 3"]
        result = tool._run(queries)
        
        # _run 方法返回 ToolExecutionResult 對象，不是 JSON 字符串
        assert isinstance(result, ToolExecutionResult)

        assert result.success is True
        # 檢查訊息包含所有搜尋結果
        assert "搜尋結果 1" in result.message
        assert "搜尋結果 2" in result.message
        assert "搜尋結果 3" in result.message
        # 檢查資料結構
        assert "queries_results" in result.data
        assert len(result.data["queries_results"]) == 3

    @pytest.mark.asyncio
    async def test_google_search_tool_multiple_queries_async(self):
        """測試 GoogleSearchTool 非同步多個查詢"""
        mock_config = Mock()
        mock_config.system = Mock()
        mock_config.system.timezone = "Asia/Taipei"
        mock_config.llm = Mock()
        mock_config.llm.models = {
            "tool_analysis": Mock(model="gemini-1.5-flash")
        }

        mock_google_client = Mock()
        # 為每個查詢設置一個返回值
        mock_responses = [
            Mock(text="異步結果 1"),
            Mock(text="異步結果 2"),
            Mock(text="異步結果 3")
        ]
        mock_google_client.models.generate_content.side_effect = mock_responses

        mock_prompt_system = Mock()
        mock_prompt_system.get_web_searcher_instructions.return_value = "搜尋提示"

        tool = GoogleSearchTool(
            google_client=mock_google_client,
            prompt_system_instance=mock_prompt_system,
            config=mock_config
        )

        queries = ["查詢 A", "查詢 B", "查詢 C"]
        result = await tool._arun(queries)
        
        # _arun 方法返回 ToolExecutionResult 對象，不是 JSON 字符串
        assert isinstance(result, ToolExecutionResult)

        assert result.success is True
        # 檢查訊息包含所有搜尋結果
        assert "異步結果 1" in result.message
        assert "異步結果 2" in result.message
        assert "異步結果 3" in result.message
        # 檢查資料結構
        assert "queries_results" in result.data
        assert len(result.data["queries_results"]) == 3


if __name__ == "__main__":
    # 運行基本測試
    test_reminder = TestSetReminderTool()
    test_reminder.test_set_reminder_success()
    test_reminder.test_set_reminder_invalid_time_format()
    test_reminder.test_set_reminder_past_time()
    
    test_google = TestGoogleSearchTool()
    test_google.test_google_search_tool_creation()
    test_google.test_google_search_tool_execution_result_format()
    test_google.test_google_search_tool_no_client_error()
    test_google.test_google_search_tool_multiple_queries_sync()
    
    print("所有基本測試通過！")
    # 為非同步測試手動運行 pytest，因為直接從 __main__ 調用 await 需要事件循環
    # pytest.main([__file__ + '::TestGoogleSearchTool::test_google_search_tool_multiple_queries_async', '-s']) 