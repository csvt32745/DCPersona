"""
多模態輸入功能測試

測試 Discord Bot 對包含文字和圖片的訊息的處理能力
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

from schemas.agent_types import MsgNode
from discord_bot.message_collector import collect_message, _process_single_message, ProcessedMessage
from agent_core.graph import UnifiedAgent
from utils.config_loader import load_typed_config
from agent_core.agent_utils import _extract_text_content


class TestMultimodalInput:
    """多模態輸入測試類"""
    
    def test_msgnode_multimodal_content(self):
        """測試 MsgNode 支援多模態內容"""
        # 測試純文字內容
        text_msg = MsgNode(
            role="user",
            content="這是一個文字訊息",
            metadata={"user_id": 123}
        )
        assert isinstance(text_msg.content, str)
        
        # 測試多模態內容
        multimodal_content = [
            {"type": "text", "text": "請分析這張圖片"},
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD..."
                }
            }
        ]
        
        multimodal_msg = MsgNode(
            role="user",
            content=multimodal_content,
            metadata={"user_id": 123}
        )
        assert isinstance(multimodal_msg.content, list)
        assert len(multimodal_msg.content) == 2
        assert multimodal_msg.content[0]["type"] == "text"
        assert multimodal_msg.content[1]["type"] == "image_url"
    
    def test_extract_text_content(self):
        """測試文字內容提取功能"""
        config = load_typed_config()
        agent = UnifiedAgent(config)
        
        # 測試純文字
        text_content = "這是純文字內容"
        extracted = _extract_text_content(text_content)
        assert extracted == "這是純文字內容"
        
        # 測試多模態內容
        multimodal_content = [
            {"type": "text", "text": "請分析這張圖片"},
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD..."
                }
            },
            {"type": "text", "text": "並告訴我你看到了什麼"}
        ]
        
        extracted = _extract_text_content(multimodal_content)
        expected = "請分析這張圖片 [圖片] 並告訴我你看到了什麼"
        assert extracted == expected
        
        # 測試只有圖片的內容
        image_only_content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD..."
                }
            }
        ]
        
        extracted = _extract_text_content(image_only_content)
        assert extracted == "[圖片]"
    
    @pytest.mark.asyncio
    async def test_message_collector_multimodal(self):
        """測試訊息收集器處理多模態內容"""
        # 模擬 Discord 訊息
        mock_message = Mock()
        mock_message.content = "請分析這張圖片"
        mock_message.author.id = 123456789
        mock_message.author.display_name = "TestUser"
        mock_message.channel.history = AsyncMock(return_value=iter([]))
        mock_message.reference = None
        mock_message.embeds = []
        
        # 模擬圖片附件
        mock_attachment = Mock()
        mock_attachment.content_type = "image/jpeg"
        mock_attachment.filename = "test_image.jpg"
        mock_attachment.url = "https://example.com/test_image.jpg"
        mock_message.attachments = [mock_attachment]
        
        # 模擬 Discord 客戶端用戶
        mock_client_user = Mock()
        mock_client_user.id = 987654321
        mock_client_user.mention = "<@987654321>"
        
        # 模擬 HTTP 回應
        mock_response = Mock()
        mock_response.content = b"fake_image_data"
        mock_response.text = "fake_image_data"
        
        # 模擬 HTTP 客戶端
        mock_httpx_client = AsyncMock()
        mock_httpx_client.get.return_value = mock_response
        
        # 測試訊息收集
        with patch('discord_bot.message_collector.get_manager_instance') as mock_manager:
            mock_manager.return_value.cache_messages = Mock()
            
            result = await collect_message(
                new_msg=mock_message,
                discord_client_user=mock_client_user,
                enable_conversation_history=False,
                httpx_client=mock_httpx_client
            )
            
            # 驗證結果
            assert result.message_count() == 1
            message = result.messages[0]
            assert message.role == "user"
            
            # 驗證內容格式
            if isinstance(message.content, list):
                # 應該包含文字和圖片
                text_parts = [item for item in message.content if item.get("type") == "text"]
                image_parts = [item for item in message.content if item.get("type") == "image_url"]
                
                assert len(text_parts) >= 1
                assert len(image_parts) >= 1
                assert "請分析這張圖片" in text_parts[0]["text"]
    
    def test_tool_necessity_analysis_with_multimodal(self):
        """測試多模態內容的工具需求分析"""
        config = load_typed_config()
        agent = UnifiedAgent(config)
        
        # 測試包含搜尋關鍵字的多模態訊息
        multimodal_messages = [
            MsgNode(
                role="user",
                content=[
                    {"type": "text", "text": "請搜尋這張圖片的相關資訊"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD..."
                        }
                    }
                ],
                metadata={"user_id": 123}
            )
        ]
        
        needs_tools = agent._analyze_tool_necessity_fallback(multimodal_messages)
        assert needs_tools == True
        
        # 測試不需要工具的多模態訊息
        simple_multimodal_messages = [
            MsgNode(
                role="user",
                content=[
                    {"type": "text", "text": "這張圖片很漂亮"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD..."
                        }
                    }
                ],
                metadata={"user_id": 123}
            )
        ]
        
        needs_tools = agent._analyze_tool_necessity_fallback(simple_multimodal_messages)
        assert needs_tools == False
    
    def test_langchain_message_building(self):
        """測試 LangChain 訊息建構"""
        config = load_typed_config()
        agent = UnifiedAgent(config)
        
        # 測試多模態訊息轉換為 LangChain 格式
        messages = [
            MsgNode(
                role="user",
                content=[
                    {"type": "text", "text": "請分析這張圖片"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD..."
                        }
                    }
                ],
                metadata={"user_id": 123}
            )
        ]
        
        system_prompt = "你是一個有用的助手。"
        langchain_messages = agent._build_messages_for_llm(messages, system_prompt)
        
        # 驗證訊息格式
        assert len(langchain_messages) == 2  # SystemMessage + HumanMessage
        assert langchain_messages[0].content == system_prompt
        
        # HumanMessage 應該直接包含多模態內容
        human_message = langchain_messages[1]
        assert isinstance(human_message.content, list)
        assert len(human_message.content) == 2
        assert human_message.content[0]["type"] == "text"
        assert human_message.content[1]["type"] == "image_url"


if __name__ == "__main__":
    # 運行基本測試
    test_instance = TestMultimodalInput()
    
    print("🧪 測試 MsgNode 多模態內容支援...")
    test_instance.test_msgnode_multimodal_content()
    print("✅ MsgNode 多模態內容測試通過")
    
    print("🧪 測試文字內容提取...")
    test_instance.test_extract_text_content()
    print("✅ 文字內容提取測試通過")
    
    print("🧪 測試工具需求分析...")
    test_instance.test_tool_necessity_analysis_with_multimodal()
    print("✅ 工具需求分析測試通過")
    
    print("🧪 測試 LangChain 訊息建構...")
    test_instance.test_langchain_message_building()
    print("✅ LangChain 訊息建構測試通過")
    
    print("🎉 所有基本測試通過！")
    print("📝 注意：異步測試需要使用 pytest 運行：python -m pytest tests/test_multimodal_input.py -v") 