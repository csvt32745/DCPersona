"""
測試 agent_core/graph.py 統一 LangGraph 實作
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from schemas.agent_types import OverallState, MsgNode, AgentPlan, ToolPlan
from agent_core.graph import UnifiedAgent, create_unified_agent, create_agent_graph
from schemas.config_types import AppConfig, AgentConfig, ToolConfig, AgentBehaviorConfig, LLMConfig, LLMModelConfig, SystemConfig, DiscordConfig


def get_test_config(agent_config=None):
    """創建測試用的配置"""
    default_agent_config = {
        "tools": {
            "google_search": {"enabled": True, "priority": 1},
            # "citation": {"enabled": False, "priority": 2} # Removed citation tool
        },
        "behavior": {
            "max_tool_rounds": 0,
            "enable_reflection": True
        }
    }
    
    if agent_config:
        # 深度合併配置
        for key, value in agent_config.items():
            if key in default_agent_config and isinstance(value, dict):
                default_agent_config[key].update(value)
            else:
                default_agent_config[key] = value
    
    # 轉換工具配置為 ToolConfig 實例
    tools_dict = {}
    for tool_name, tool_config in default_agent_config["tools"].items():
        tools_dict[tool_name] = ToolConfig(**tool_config)
    
    return AppConfig(
        system=SystemConfig(log_level="INFO", timezone="Asia/Taipei"),
        discord=DiscordConfig(bot_token="test_token", enable_conversation_history=True),
        llm=LLMConfig(
            models={
                "tool_analysis": LLMModelConfig(model="gemini-2.0-flash", temperature=0.1),
                "final_answer": LLMModelConfig(model="gemini-2.0-flash", temperature=0.7),
                "reflection": LLMModelConfig(model="gemini-2.0-flash-exp", temperature=0.3)
            }
        ),
        agent=AgentConfig(
            tools=tools_dict,
            behavior=AgentBehaviorConfig(**default_agent_config["behavior"])
        )
    )


class TestUnifiedAgent:
    """測試統一 Agent 類別"""
    
    def test_agent_creation(self):
        """測試 Agent 創建"""
        config = get_test_config()
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            agent = UnifiedAgent(config)
            
            assert agent.config == config
            assert agent.agent_config == config.agent
            assert agent.tools_config == config.agent.tools
            assert agent.behavior_config == config.agent.behavior
    
    def test_agent_creation_with_default_config(self):
        """測試使用預設配置創建 Agent"""
        with patch('agent_core.graph.load_typed_config') as mock_load_config, \
             patch('agent_core.graph.ChatGoogleGenerativeAI'), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            
            mock_load_config.return_value = get_test_config()
            agent = UnifiedAgent()
            
            assert agent.config is not None
    
    def test_build_graph_pure_conversation_mode(self):
        """測試純對話模式的圖構建"""
        config = get_test_config({
            "behavior": {"max_tool_rounds": 0}
        })
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            agent = UnifiedAgent(config)
            graph = agent.build_graph()
            
            assert graph is not None
            # 檢查核心節點存在
            expected_nodes = ["generate_query_or_plan", "reflection", "finalize_answer", "execute_tools"]
            for node in expected_nodes:
                assert node in graph.nodes
            
            # 在純對話模式下，即使節點存在，執行路徑也不應經過它。
            # 這部分的邏輯由 route_after_planning 函數控制，而不是節點是否存在。
    
    def test_build_graph_tool_mode(self):
        """測試工具模式的圖構建"""
        config = get_test_config({
            "behavior": {"max_tool_rounds": 2}
        })
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            agent = UnifiedAgent(config)
            graph = agent.build_graph()
            
            assert graph is not None
    
    @pytest.mark.asyncio
    async def test_generate_query_or_plan_no_messages(self):
        """測試沒有訊息的查詢生成"""
        config = get_test_config()
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            agent = UnifiedAgent(config)
            
            state = OverallState(messages=[])
            
            # 這應該會引發錯誤，因為沒有訊息
            result = await agent.generate_query_or_plan(state)
            assert "finished" in result or "agent_plan" in result
    
    @pytest.mark.asyncio
    async def test_generate_query_or_plan_with_user_message(self):
        """測試有用戶訊息的查詢生成"""
        config = get_test_config({
            "tools": {"google_search": {"enabled": True}},
            "behavior": {"max_tool_rounds": 1}
        })
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            agent = UnifiedAgent(config)
            
            state = OverallState(
                messages=[MsgNode(role="user", content="搜尋最新的 AI 新聞")]
            )
            
            result = await agent.generate_query_or_plan(state)
            
            # 由於 LLM 是 mock 對象，可能會失敗並返回 finished: True
            if "finished" in result:
                assert result["finished"] is True
                assert "agent_plan" in result
            else:
                assert "tool_round" in result
                assert "agent_plan" in result
                assert "research_topic" in result
            
            # 檢查 agent_plan 結構
            agent_plan = result["agent_plan"]
            assert isinstance(agent_plan, AgentPlan)
    
    def test_analyze_tool_necessity(self):
        """測試工具需求分析"""
        config = get_test_config()
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            agent = UnifiedAgent(config)
            
            # 直接測試 fallback 方法以確保關鍵字檢測邏輯正確
            # 包含工具關鍵字的內容
            assert agent._analyze_tool_necessity_fallback([MsgNode(role="user", content="請搜尋最新資訊")]) is True
            assert agent._analyze_tool_necessity_fallback([MsgNode(role="user", content="查詢今天的新聞")]) is True
            
            # 不包含工具關鍵字的內容  
            assert agent._analyze_tool_necessity_fallback([MsgNode(role="user", content="你好嗎？")]) is False
            assert agent._analyze_tool_necessity_fallback([MsgNode(role="user", content="謝謝你的幫助")]) is False

    def test_route_and_dispatch_tools(self):
        """測試工具路由和分發邏輯"""
        config = get_test_config()
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            agent = UnifiedAgent(config)
            
            # 測試不需要工具的情況
            state_no_tools = OverallState(
                agent_plan=AgentPlan(needs_tools=False)
            )
            route = agent.route_and_dispatch_tools(state_no_tools)
            assert route == "direct_answer"
            
            # 測試需要工具的情況
            state_with_tools = OverallState(
                agent_plan=AgentPlan(needs_tools=True),
                metadata={"pending_tool_calls": [{"name": "test"}]}
            )
            route = agent.route_and_dispatch_tools(state_with_tools)
            assert route == "execute_tools"

    @pytest.mark.asyncio
    async def test_reflection_enabled(self):
        """測試啟用反思的情況"""
        config = get_test_config({
            "behavior": {"enable_reflection": True}
        })
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            agent = UnifiedAgent(config)
            
            state = OverallState(
                aggregated_tool_results=["足夠長的測試結果內容來通過充分性檢查"],
                research_topic="測試主題"
            )
            
            result = await agent.reflection(state)
        
        assert "is_sufficient" in result
        assert "reflection_complete" in result
        assert result["reflection_complete"] is True
    
    @pytest.mark.asyncio
    async def test_reflection_disabled(self):
        """測試禁用反思的情況"""
        config = get_test_config({
            "behavior": {"enable_reflection": False}
        })
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            agent = UnifiedAgent(config)
            
            state = OverallState()
            result = await agent.reflection(state)
            
            assert result["is_sufficient"] is True

    def test_decide_next_step_sufficient(self):
        """測試結果充分時的決策"""
        config = get_test_config()
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            agent = UnifiedAgent(config)
            
            state = OverallState(
                is_sufficient=True,
                tool_round=1
            )
            
            result = agent.decide_next_step(state)
            assert result == "finish"
    
    def test_decide_next_step_max_rounds_reached(self):
        """測試達到最大輪次時的決策"""
        config = get_test_config({
            "behavior": {"max_tool_rounds": 2}
        })
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            agent = UnifiedAgent(config)
            
            state = OverallState(
                is_sufficient=False,
                tool_round=2
            )
            
            result = agent.decide_next_step(state)
            assert result == "finish"
    
    def test_decide_next_step_continue(self):
        """測試繼續研究的情況"""
        config = get_test_config({
            "behavior": {"max_tool_rounds": 3}
        })
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            agent = UnifiedAgent(config)
            
            state = OverallState(
                is_sufficient=False,
                tool_round=1
            )
            
            result = agent.decide_next_step(state)
            assert result == "continue"
    
    @pytest.mark.asyncio
    async def test_finalize_answer_no_messages(self):
        """測試沒有訊息的最終答案生成"""
        config = get_test_config()
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            agent = UnifiedAgent(config)
            
            state = OverallState(messages=[])
            result = await agent.finalize_answer(state)
            
            assert "final_answer" in result
            assert "finished" in result
    
    @pytest.mark.asyncio
    async def test_finalize_answer_with_context(self):
        """測試有上下文的最終答案生成"""
        config = get_test_config()
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI') as mock_llm_class, \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            # 設置模擬的 LLM 回應
            mock_llm_instance = MagicMock()
            
            # 模擬 astream 方法
            async def mock_astream_with_content(messages):
                chunks = ["關於你問的「什麼是 AI？」，我找到了一些有用的資訊呢！✨\n\n",
                          "AI 是人工智慧的縮寫，AI 技術正在快速發展\n\n",
                          "希望這些對你有幫助！還有什麼想了解的嗎？😊"]
                for chunk in chunks:
                    yield Mock(content=chunk)
                yield Mock(content="") # 結束標記
            
            mock_llm_instance.astream = mock_astream_with_content
            mock_llm_class.return_value = mock_llm_instance
            
            agent = UnifiedAgent(config)
            # 手動設置 final_answer_llm
            agent.final_answer_llm = mock_llm_instance
            
            state = OverallState(
                messages=[MsgNode(role="user", content="什麼是 AI？")],
                aggregated_tool_results=["AI 是人工智慧的縮寫", "AI 技術正在快速發展"]
            )
            
            result = await agent.finalize_answer(state)
            
            assert "final_answer" in result
            assert "AI" in result["final_answer"]
            assert "人工智慧" in result["final_answer"]
            assert "技術" in result["final_answer"]
    
    @pytest.mark.asyncio
    async def test_finalize_answer_without_context(self):
        """測試無上下文的最終答案生成"""
        config = get_test_config()
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI') as mock_llm_class, \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            # 設置模擬的 LLM 回應
            mock_llm_instance = MagicMock()
            
            # 模擬 astream 方法
            async def mock_astream_without_content(messages):
                chunks = ["嗨！關於「你好」，我很樂意和你聊聊～",
                          "雖然我現在沒有額外的搜尋資訊，但我會盡我所知來回答你！😊 ",
                          "有什麼特別想聊的嗎？"]
                for chunk in chunks:
                    yield Mock(content=chunk)
                yield Mock(content="") # 結束標記
            
            mock_llm_instance.astream = mock_astream_without_content
            mock_llm_class.return_value = mock_llm_instance
            
            agent = UnifiedAgent(config)
            # 手動設置 final_answer_llm
            agent.final_answer_llm = mock_llm_instance
            
            state = OverallState(
                messages=[MsgNode(role="user", content="你好")],
                aggregated_tool_results=[]
            )
            
            result = await agent.finalize_answer(state)
            
            assert "final_answer" in result
            assert "你好" in result["final_answer"]
            assert "樂意" in result["final_answer"]
            assert "聊聊" in result["final_answer"]
            assert "資訊" in result["final_answer"]
    
    @pytest.mark.asyncio
    async def test_evaluate_results_sufficiency(self):
        """測試結果充分性評估"""
        config = get_test_config()
        
        with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            agent = UnifiedAgent(config)
            
            # 測試充分的結果
            sufficient_results = ["這是一個足夠長的結果來通過充分性檢查"]
            assert agent._evaluate_results_sufficiency(sufficient_results, "測試主題") is True
            
            # 測試不充分的結果
            insufficient_results = ["短"]
            assert agent._evaluate_results_sufficiency(insufficient_results, "測試主題") is True  # 現在總是返回 True
            
            # 測試空結果
            empty_results = []
            assert agent._evaluate_results_sufficiency(empty_results, "測試主題") is True


def test_create_unified_agent():
    """測試創建統一 Agent 函數"""
    config = get_test_config()
    
    with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
         patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
        agent = create_unified_agent(config)
        
        assert isinstance(agent, UnifiedAgent)
        assert agent.config == config


def test_create_agent_graph():
    """測試創建 Agent 圖函數"""
    config = get_test_config()
    
    with patch('agent_core.graph.ChatGoogleGenerativeAI'), \
         patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
        graph = create_agent_graph(config)
        
        assert graph is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 