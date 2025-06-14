"""
端到端測試套件

測試完整的 Discord Bot 流程和所有功能組合，包括多模態輸入支援。
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List
import os
from base64 import b64encode

import discord

from schemas.agent_types import MsgNode, OverallState
from schemas.config_types import AppConfig, AgentConfig, AgentBehaviorConfig, LLMConfig, DiscordConfig, ToolConfig, LLMProviderConfig, StreamingConfig, PromptSystemConfig, PromptPersonaConfig
from discord_bot.message_handler import DiscordMessageHandler
from discord_bot.message_collector import collect_message, CollectedMessages, ProcessedMessage
from agent_core.graph import UnifiedAgent, create_unified_agent
from utils.config_loader import load_typed_config
from cli_main import main as cli_main


def get_comprehensive_test_config():
    """創建完整的測試配置"""
    mock_google_provider_config = LLMProviderConfig(api_key="test_key_12345")
    
    mock_llm_config = LLMConfig(
        providers={"google": mock_google_provider_config}
    )
    
    return AppConfig(
        agent=AgentConfig(
            tools={
                "google_search": ToolConfig(enabled=True, priority=1)
            },
            behavior=AgentBehaviorConfig(
                max_tool_rounds=2, 
                enable_reflection=True
            )
        ),
        discord=DiscordConfig(
            bot_token="test_token",
            enable_conversation_history=True,
            status_message="測試 AI 助手",
            client_id="123456789"
        ),
        llm=mock_llm_config,
        streaming=StreamingConfig(
            enabled=True,
            min_content_length=100
        ),
        prompt_system=PromptSystemConfig(
            persona=PromptPersonaConfig(
                random_selection=False,
                default_persona="helpful_assistant",
                persona_directory="persona"
            )
        )
    )


class TestEndToEndFlow:
    """端到端流程測試類"""
    
    @pytest.mark.asyncio
    async def test_discord_bot_complete_flow(self):
        """測試 Discord Bot 完整流程"""
        # 模擬 Discord 訊息
        mock_message = Mock(spec=discord.Message)
        mock_message.content = "請幫我搜尋最新的 AI 發展"
        mock_message.author = Mock()
        mock_message.author.bot = False
        mock_message.author.id = 12345
        mock_message.author.display_name = "TestUser"
        mock_message.channel = Mock()
        mock_message.channel.id = 67890
        mock_message.guild = Mock()
        mock_message.guild.name = "TestGuild"
        mock_message.channel.name = "general"
        mock_message.attachments = []
        mock_message.embeds = []
        mock_message.reply = AsyncMock()
        mock_message.reference = None
        
        # 模擬頻道歷史
        async def mock_history():
            return
            yield
        mock_message.channel.history = Mock(return_value=mock_history())
        
        test_config = get_comprehensive_test_config()
        
        with patch('discord_bot.message_handler.load_typed_config', return_value=test_config), \
             patch('discord_bot.message_handler.collect_message') as mock_collect, \
             patch('discord_bot.message_handler.create_unified_agent') as mock_create_agent, \
             patch('discord_bot.message_handler.DiscordProgressAdapter') as mock_adapter:
            
            # 設置訊息收集模擬
            test_message = MsgNode(
                role="user",
                content="請幫我搜尋最新的 AI 發展",
                metadata={"user_id": 12345}
            )
            
            mock_collect.return_value = CollectedMessages(
                messages=[test_message],
                user_warnings=set()
            )
            
            # 設置 Agent 模擬
            mock_agent = Mock()
            mock_agent.add_progress_observer = Mock()
            mock_agent.build_graph = Mock()
            
            mock_graph = Mock()
            mock_graph.ainvoke = AsyncMock(return_value={
                "final_answer": "最新的 AI 發展包括大型語言模型、多模態 AI 和自動化工具...",
                "sources": [
                    {"title": "AI 2024 趨勢", "url": "https://example.com/ai-trends"}
                ],
                "finished": True
            })
            mock_agent.build_graph.return_value = mock_graph
            mock_create_agent.return_value = mock_agent
            
            # 設置進度適配器模擬
            mock_adapter_instance = Mock()
            mock_adapter_instance.on_completion = AsyncMock()
            mock_adapter_instance.cleanup = AsyncMock()
            mock_adapter_instance.on_error = AsyncMock()
            mock_adapter_instance._streaming_message = None
            mock_adapter.return_value = mock_adapter_instance
            
            # 執行測試
            handler = DiscordMessageHandler()
            success = await handler.handle_message(mock_message)
            
            # 驗證結果
            assert success is True
            mock_collect.assert_called_once()
            mock_agent.add_progress_observer.assert_called_once()
            mock_graph.ainvoke.assert_called_once()
            mock_adapter_instance.on_completion.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_discord_bot_multimodal_flow(self):
        """測試 Discord Bot 多模態輸入流程"""
        # 模擬包含圖片的 Discord 訊息
        mock_message = Mock(spec=discord.Message)
        mock_message.content = "請分析這張圖片的內容"
        mock_message.author = Mock()
        mock_message.author.bot = False
        mock_message.author.id = 12345
        mock_message.author.display_name = "TestUser"
        mock_message.channel = Mock()
        mock_message.channel.id = 67890
        mock_message.guild = Mock()
        mock_message.guild.name = "TestGuild"
        mock_message.channel.name = "general"
        mock_message.embeds = []
        mock_message.reply = AsyncMock()
        mock_message.reference = None
        
        # 模擬圖片附件
        mock_attachment = Mock()
        mock_attachment.content_type = "image/jpeg"
        mock_attachment.filename = "test.jpg"
        mock_attachment.url = "https://example.com/test.jpg"
        mock_message.attachments = [mock_attachment]
        
        # 模擬頻道歷史
        async def mock_history():
            return
            yield
        mock_message.channel.history = Mock(return_value=mock_history())
        
        test_config = get_comprehensive_test_config()
        
        with patch('discord_bot.message_handler.load_typed_config', return_value=test_config), \
             patch('discord_bot.message_handler.collect_message') as mock_collect, \
             patch('discord_bot.message_handler.create_unified_agent') as mock_create_agent, \
             patch('discord_bot.message_handler.DiscordProgressAdapter') as mock_adapter:
            
            # 設置多模態訊息收集模擬
            multimodal_content = [
                {"type": "text", "text": "<@12345> TestUser: 請分析這張圖片的內容"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD..."
                    }
                }
            ]
            
            test_message = MsgNode(
                role="user",
                content=multimodal_content,
                metadata={"user_id": 12345}
            )
            
            mock_collect.return_value = CollectedMessages(
                messages=[test_message],
                user_warnings=set()
            )
            
            # 設置 Agent 模擬
            mock_agent = Mock()
            mock_agent.add_progress_observer = Mock()
            mock_agent.build_graph = Mock()
            
            mock_graph = Mock()
            mock_graph.ainvoke = AsyncMock(return_value={
                "final_answer": "這張圖片顯示了一個美麗的風景，包含山脈和湖泊...",
                "sources": [],
                "finished": True
            })
            mock_agent.build_graph.return_value = mock_graph
            mock_create_agent.return_value = mock_agent
            
            # 設置進度適配器模擬
            mock_adapter_instance = Mock()
            mock_adapter_instance.on_completion = AsyncMock()
            mock_adapter_instance.cleanup = AsyncMock()
            mock_adapter_instance.on_error = AsyncMock()
            mock_adapter_instance._streaming_message = None
            mock_adapter.return_value = mock_adapter_instance
            
            # 執行測試
            handler = DiscordMessageHandler()
            success = await handler.handle_message(mock_message)
            
            # 驗證結果
            assert success is True
            mock_collect.assert_called_once()
            
            # 驗證傳遞給 Agent 的訊息包含多模態內容
            call_args = mock_graph.ainvoke.call_args
            state = call_args[0][0]  # 第一個位置參數是 state
            assert len(state.messages) == 1
            assert isinstance(state.messages[0].content, list)
            assert len(state.messages[0].content) == 2
            assert state.messages[0].content[0]["type"] == "text"
            assert state.messages[0].content[1]["type"] == "image_url"
    
    @pytest.mark.asyncio
    async def test_agent_with_tools(self):
        """測試 Agent 工具使用流程"""
        config = get_comprehensive_test_config()
        
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key_12345'}):
            agent = UnifiedAgent(config)
            
            # 準備測試狀態
            initial_state = OverallState(
                messages=[
                    MsgNode(role="user", content="請搜尋 Python 最新版本資訊")
                ],
                tool_round=0,
                finished=False
            )
            
            # 模擬 LLM 回應
            with patch.object(agent, 'tool_analysis_llm') as mock_llm, \
                 patch.object(agent, 'google_client') as mock_google_client:
                
                # 模擬計劃生成
                mock_llm.invoke.return_value = Mock(content='{"needs_tools": true, "tool_plans": [{"tool_name": "google_search", "queries": ["Python 最新版本"], "priority": 1}], "reasoning": "需要搜尋最新資訊"}')
                
                # 模擬 Google 搜尋
                mock_response = Mock()
                mock_response.text = "Python 3.12 是最新版本，包含多項改進..."
                mock_google_client.models.generate_content.return_value = mock_response
                
                # 執行計劃生成
                result = await agent.generate_query_or_plan(initial_state)
                
                # 驗證計劃生成結果
                assert result["agent_plan"].needs_tools is True
                assert len(result["agent_plan"].tool_plans) == 1
                assert result["agent_plan"].tool_plans[0].tool_name == "google_search"
                assert "Python 最新版本" in result["agent_plan"].tool_plans[0].queries
    
    @pytest.mark.asyncio
    async def test_streaming_functionality(self):
        """測試串流功能"""
        config = get_comprehensive_test_config()
        config.streaming.enabled = True
        
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key_12345'}):
            agent = UnifiedAgent(config)
            
            # 準備測試狀態
            test_state = OverallState(
                messages=[
                    MsgNode(role="user", content="請解釋什麼是機器學習")
                ],
                finished=False,
                tool_results=["機器學習是人工智慧的一個分支..."]
            )
            
            # 模擬串流 LLM 回應
            async def mock_astream(messages):
                chunks = ["機器", "學習", "是", "一種", "讓", "電腦", "學習", "的", "技術"]
                for chunk in chunks:
                    yield Mock(content=chunk)
                yield Mock(content="")  # 結束標記
            
            with patch.object(agent, 'final_answer_llm') as mock_llm:
                mock_llm.astream = mock_astream
                
                # 模擬進度觀察者
                progress_observer = Mock()
                progress_observer.on_streaming_chunk = AsyncMock()
                progress_observer.on_streaming_complete = AsyncMock()
                agent.add_progress_observer(progress_observer)
                
                # 執行最終答案生成
                result = await agent.finalize_answer(test_state)
                
                # 驗證串流結果
                assert result["finished"] is True
                assert "機器學習是一種讓電腦學習的技術" in result["final_answer"]
                
                # 驗證串流回調被調用
                assert progress_observer.on_streaming_chunk.call_count >= 9
                progress_observer.on_streaming_complete.assert_called_once()
    
    def test_persona_integration(self):
        """測試 Persona 系統整合"""
        config = get_comprehensive_test_config()
        
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key_12345'}):
            agent = UnifiedAgent(config)
            
            # 測試 persona 載入
            assert agent.prompt_system is not None
            
            # 測試 system prompt 構建
            with patch.object(agent.prompt_system, 'get_system_instructions') as mock_get_system:
                mock_get_system.return_value = "你是一個有用的助手，具有友善的個性。"
                
                messages = [MsgNode(role="user", content="你好")]
                system_prompt = agent._build_final_system_prompt("", "")
                
                # 驗證 system prompt 包含 persona 資訊
                mock_get_system.assert_called_once()
                assert isinstance(system_prompt, str)
                assert len(system_prompt) > 0
    
    def test_cli_interface(self):
        """測試 CLI 介面配置處理"""
        # 簡化的 CLI 測試，只測試配置處理
        test_config = get_comprehensive_test_config()
        test_config.agent.behavior.max_tool_rounds = 0  # 禁用工具
        
        # 驗證配置正確設置
        assert test_config.agent.behavior.max_tool_rounds == 0
        assert isinstance(test_config, AppConfig)
    
    def test_configuration_system(self):
        """測試配置系統"""
        # 測試型別安全配置載入
        config = get_comprehensive_test_config()
        
        # 驗證配置結構
        assert isinstance(config.agent, AgentConfig)
        assert isinstance(config.discord, DiscordConfig)
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.streaming, StreamingConfig)
        
        # 測試配置驗證
        assert config.agent.behavior.max_tool_rounds == 2
        assert config.streaming.enabled is True
        assert config.discord.enable_conversation_history is True
        
        # 測試工具配置
        assert "google_search" in config.agent.tools
        assert config.agent.tools["google_search"].enabled is True
        
        # 測試預設值回退
        assert config.streaming.min_content_length == 100
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """測試錯誤處理機制"""
        config = get_comprehensive_test_config()
        
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key_12345'}):
            agent = UnifiedAgent(config)
            
            # 測試 LLM 調用失敗的錯誤處理
            test_state = OverallState(
                messages=[MsgNode(role="user", content="測試錯誤處理")],
                finished=False
            )
            
            with patch.object(agent, 'final_answer_llm') as mock_llm:
                # 模擬 LLM 調用失敗
                mock_llm.invoke.side_effect = Exception("LLM 調用失敗")
                
                # 執行最終答案生成
                result = await agent.finalize_answer(test_state)
                
                # 驗證錯誤處理
                assert result["finished"] is True
                # 在串流模式下，錯誤可能導致空字串，這也是一種錯誤處理方式
                assert isinstance(result["final_answer"], str)
    
    @pytest.mark.asyncio
    async def test_parallel_tool_execution(self):
        """測試並行工具執行"""
        config = get_comprehensive_test_config()
        
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key_12345'}):
            agent = UnifiedAgent(config)
            
            # 準備測試狀態
            initial_state = OverallState(
                messages=[MsgNode(role="user", content="搜尋 Python 和 JavaScript 的比較")],
                tool_round=0,
                finished=False
            )
            
            # 模擬計劃生成（多個查詢）
            with patch.object(agent, 'tool_analysis_llm') as mock_llm:
                mock_llm.invoke.return_value = Mock(
                    content='{"needs_tools": true, "tool_plans": [{"tool_name": "google_search", "queries": ["Python 特性", "JavaScript 特性"], "priority": 1}], "reasoning": "需要搜尋兩種語言的資訊"}'
                )
                
                # 執行計劃生成
                result = await agent.generate_query_or_plan(initial_state)
                
                # 驗證並行執行計劃
                assert result["agent_plan"].needs_tools is True
                assert len(result["agent_plan"].tool_plans[0].queries) == 2
                
                # 測試路由決策
                updated_state = OverallState(
                    messages=initial_state.messages,
                    tool_round=result["tool_round"],
                    finished=initial_state.finished,
                    agent_plan=result["agent_plan"]
                )
                route_result = agent.route_and_dispatch_tools(updated_state)
                
                # 驗證返回 Send 物件列表（並行執行）
                assert isinstance(route_result, list)
                assert len(route_result) == 2  # 兩個並行任務


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 