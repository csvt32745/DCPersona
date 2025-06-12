"""
測試 agent_core/graph.py 統一 LangGraph 實作
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# 調整導入路徑，確保可以找到 AgentCLI 模組
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agent_core.graph import UnifiedAgent, create_unified_agent, create_agent_graph
from schemas.agent_types import OverallState, MsgNode


class TestUnifiedAgent:
    """測試 UnifiedAgent 類別"""
    
    def test_agent_creation(self):
        """測試 Agent 創建"""
        config = {
            "agent": {
                "tools": {"google_search": {"enabled": False}},
                "behavior": {"max_tool_rounds": 1}
            }
        }
        
        agent = UnifiedAgent(config)
        
        assert agent.config == config
        assert agent.agent_config == config["agent"]
        assert agent.tools_config == config["agent"]["tools"]
        assert agent.behavior_config == config["agent"]["behavior"]
    
    def test_agent_creation_with_default_config(self):
        """測試使用預設配置創建 Agent"""
        with patch('agent_core.graph.load_config') as mock_load_config:
            mock_load_config.return_value = {"agent": {"tools": {}, "behavior": {}}}
            
            agent = UnifiedAgent()
            
            mock_load_config.assert_called_once()
    
    def test_build_graph_pure_conversation_mode(self):
        """測試純對話模式的圖建立"""
        config = {
            "agent": {
                "tools": {},
                "behavior": {"max_tool_rounds": 0}
            }
        }
        
        agent = UnifiedAgent(config)
        graph = agent.build_graph()
        
        assert graph is not None
        # 圖應該包含所有節點，但流程會跳過工具相關節點
    
    def test_build_graph_tool_mode(self):
        """測試工具模式的圖建立"""
        config = {
            "agent": {
                "tools": {"google_search": {"enabled": True}},
                "behavior": {"max_tool_rounds": 2}
            }
        }
        
        agent = UnifiedAgent(config)
        graph = agent.build_graph()
        
        assert graph is not None
    
    def test_generate_query_or_plan_no_messages(self):
        """測試無訊息的查詢生成"""
        agent = UnifiedAgent({"agent": {"tools": {}, "behavior": {}}})
        
        state = OverallState()
        result = agent.generate_query_or_plan(state)
        
        assert result["finished"] is True
    
    def test_generate_query_or_plan_with_user_message(self):
        """測試有用戶訊息的查詢生成"""
        config = {
            "agent": {
                "tools": {"google_search": {"enabled": True}},
                "behavior": {"max_tool_rounds": 1}
            }
        }
        agent = UnifiedAgent(config)
        
        state = OverallState(
            messages=[MsgNode(role="user", content="搜尋最新的 AI 新聞")]
        )
        
        result = agent.generate_query_or_plan(state)
        
        assert "tool_round" in result
        assert "needs_tools" in result
        assert "search_queries" in result
        assert "research_topic" in result
    
    def test_analyze_tool_necessity(self):
        """測試工具需求分析"""
        agent = UnifiedAgent({"agent": {"tools": {}, "behavior": {}}})
        
        # 包含工具關鍵字的內容
        assert agent._analyze_tool_necessity([MsgNode(role="user", content="請搜尋最新資訊")]) is True
        assert agent._analyze_tool_necessity([MsgNode(role="user", content="查詢今天的新聞")]) is True
        
        # 不包含工具關鍵字的內容
        assert agent._analyze_tool_necessity([MsgNode(role="user", content="你好嗎？")]) is False
        assert agent._analyze_tool_necessity([MsgNode(role="user", content="謝謝你的幫助")]) is False
    
    def test_tool_selection_no_tools_needed(self):
        """測試不需要工具時的工具選擇"""
        agent = UnifiedAgent({"agent": {"tools": {}, "behavior": {}}})
        
        state = OverallState(needs_tools=False)
        result = agent.tool_selection(state)
        
        assert result["selected_tool"] is None
        assert result["available_tools"] == []
    
    def test_tool_selection_with_available_tools(self):
        """測試有可用工具時的工具選擇"""
        config = {
            "agent": {
                "tools": {
                    "google_search": {"enabled": True, "priority": 1},
                    "citation": {"enabled": True, "priority": 2}
                },
                "behavior": {}
            }
        }
        agent = UnifiedAgent(config)
        
        # 模擬 self.google_client 以確保 google_search 被視為可用
        with patch.object(agent, 'google_client', new=MagicMock()):
            state = OverallState(needs_tools=True)
            result = agent.tool_selection(state)
            
            assert "google_search" in result["available_tools"]
            assert "citation" in result["available_tools"]
            assert result["selected_tool"] == "google_search"  # 優先級較高
    
    def test_execute_tool_no_tool_selected(self):
        """測試沒有選擇工具時的執行"""
        agent = UnifiedAgent({"agent": {"tools": {}, "behavior": {}}})
        
        state = OverallState(selected_tool=None)
        result = agent.execute_tool(state)
        
        assert result["tool_results"] == []
    
    def test_execute_google_search_tool(self):
        """測試執行 Google 搜尋工具"""
        agent = UnifiedAgent({"agent": {"tools": {}, "behavior": {}}})
        
        state = OverallState(
            selected_tool="google_search",
            search_queries=["測試查詢"]
        )
        
        result = agent.execute_tool(state)
        
        assert len(result["tool_results"]) > 0
        assert result["tool_round"] == 1
    
    def test_execute_citation_tool(self):
        """測試執行引用工具"""
        agent = UnifiedAgent({"agent": {"tools": {}, "behavior": {}}})
        
        state = OverallState(
            selected_tool="citation",
            tool_results=["測試結果1", "測試結果2"]
        )
        
        result = agent.execute_tool(state)
        
        assert len(result["tool_results"]) > 0
        assert "[1]" in result["tool_results"][0]
    
    def test_reflection_enabled(self):
        """測試啟用反思的情況"""
        config = {
            "agent": {
                "tools": {},
                "behavior": {"enable_reflection": True}
            }
        }
        agent = UnifiedAgent(config)
        
        state = OverallState(
            tool_results=["足夠長的測試結果內容來通過充分性檢查"],
            research_topic="測試主題"
        )
        
        result = agent.reflection(state)
        
        assert "is_sufficient" in result
        assert "reflection_complete" in result
        assert result["reflection_complete"] is True
    
    def test_reflection_disabled(self):
        """測試禁用反思的情況"""
        config = {
            "agent": {
                "tools": {},
                "behavior": {"enable_reflection": False}
            }
        }
        agent = UnifiedAgent(config)
        
        state = OverallState()
        result = agent.reflection(state)
        
        assert result["is_sufficient"] is True
    
    def test_evaluate_research_sufficient(self):
        """測試結果充分時的研究評估"""
        agent = UnifiedAgent({"agent": {"tools": {}, "behavior": {}}})
        
        state = OverallState(
            is_sufficient=True,
            tool_round=1
        )
        
        result = agent.evaluate_research(state)
        assert result == "finish"
    
    def test_evaluate_research_max_rounds_reached(self):
        """測試達到最大輪次時的研究評估"""
        config = {
            "agent": {
                "tools": {},
                "behavior": {"max_tool_rounds": 2}
            }
        }
        agent = UnifiedAgent(config)
        
        state = OverallState(
            is_sufficient=False,
            tool_round=2
        )
        
        result = agent.evaluate_research(state)
        assert result == "finish"
    
    def test_evaluate_research_continue(self):
        """測試繼續研究的情況"""
        config = {
            "agent": {
                "tools": {},
                "behavior": {"max_tool_rounds": 3}
            }
        }
        agent = UnifiedAgent(config)
        
        state = OverallState(
            is_sufficient=False,
            tool_round=1
        )
        
        result = agent.evaluate_research(state)
        assert result == "continue"
    
    def test_finalize_answer_no_messages(self):
        """測試無訊息時的最終答案生成"""
        agent = UnifiedAgent({"agent": {"tools": {}, "behavior": {}}})
        
        state = OverallState()
        result = agent.finalize_answer(state)
        
        assert result["finished"] is True
    
    def test_finalize_answer_with_context(self):
        """測試有上下文的最終答案生成"""
        agent = UnifiedAgent({"agent": {"tools": {}, "behavior": {}}})
        
        state = OverallState(
            messages=[MsgNode(role="user", content="什麼是 AI？")],
            tool_results=["AI 是人工智慧的縮寫", "AI 技術正在快速發展"]
        )
        
        result = agent.finalize_answer(state)
        
        assert "final_answer" in result
        assert "AI" in result["final_answer"]
        assert result["finished"] is True
    
    def test_finalize_answer_without_context(self):
        """測試無上下文的最終答案生成"""
        agent = UnifiedAgent({"agent": {"tools": {}, "behavior": {}}})
        
        state = OverallState(
            messages=[MsgNode(role="user", content="你好")],
            tool_results=[]
        )
        
        result = agent.finalize_answer(state)
        
        assert "final_answer" in result
        assert "你好" in result["final_answer"]
        assert result["finished"] is True
    
    def test_evaluate_results_sufficiency(self):
        """測試結果充分性評估"""
        # 啟用反思功能
        config = {
            "agent": {
                "tools": {},
                "behavior": {"enable_reflection": True}
            }
        }
        agent = UnifiedAgent(config)

        # 假設 LLM 判斷為充分
        with patch.object(agent, '_evaluate_results_sufficiency', return_value=True) as mock_sufficiency:
            state = OverallState(tool_results=["一些工具結果"], research_topic="測試主題")
            
            result = agent.reflection(state)

            mock_sufficiency.assert_called_once_with(["一些工具結果"], "測試主題")
            assert result["is_sufficient"] is True
            assert result["reflection_complete"] is True


def test_create_unified_agent():
    """測試便利函數 create_unified_agent"""
    with patch('agent_core.graph.load_config') as mock_load_config:
        mock_load_config.return_value = {"agent": {"tools": {}, "behavior": {}}}
        
        agent = create_unified_agent()
        
        assert isinstance(agent, UnifiedAgent)


def test_create_agent_graph():
    """測試便利函數 create_agent_graph"""
    config = {
        "agent": {
            "tools": {},
            "behavior": {"max_tool_rounds": 0}
        }
    }
    
    graph = create_agent_graph(config)
    
    assert graph is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 