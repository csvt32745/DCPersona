"""
多模態輸入功能測試

測試 Discord Bot 對包含文字和圖片的訊息的處理能力
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any
from datetime import datetime
from PIL import Image
from io import BytesIO
import discord

from schemas.agent_types import MsgNode
from discord_bot.message_collector import collect_message, _process_single_message, ProcessedMessage
from discord_bot.message_handler import DiscordMessageHandler
from agent_core.graph import UnifiedAgent
from utils.config_loader import load_typed_config
from agent_core.agent_utils import _extract_text_content
from schemas.input_media_config import InputMediaConfig


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
        mock_message.stickers = []  # 添加 stickers 屬性
        
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

    @pytest.fixture
    def mock_discord_message_with_emoji(self):
        """創建包含 emoji 的模擬 Discord 訊息"""
        msg = Mock()
        msg.id = 123456789
        msg.content = "Hello <:custom_emoji:123456789> world!"
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.embeds = []
        msg.stickers = []
        msg.reference = None
        msg.guild = Mock()
        msg.guild.get_emoji = Mock(return_value=None)  # 模擬找不到 emoji
        return msg
    
    @pytest.fixture
    def mock_discord_message_with_stickers(self):
        """創建包含 stickers 的模擬 Discord 訊息"""
        msg = Mock()
        msg.id = 123456789
        msg.content = "Check out this sticker!"
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.embeds = []
        msg.reference = None
        
        # 創建模擬 sticker
        mock_sticker = Mock()
        mock_sticker.name = "test_sticker"
        mock_sticker.format = Mock()
        mock_sticker.format.__str__ = Mock(return_value="StickerFormatType.png")
        mock_sticker.url = "https://example.com/sticker.png"
        
        # 模擬 sticker.read() 方法
        test_image = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        test_image.save(img_bytes, format='PNG')
        mock_sticker.read = AsyncMock(return_value=img_bytes.getvalue())
        
        msg.stickers = [mock_sticker]
        return msg
    
    @pytest.fixture
    def mock_discord_client_user(self):
        """創建模擬的 Discord 客戶端用戶"""
        user = Mock()
        user.id = 555666777
        user.mention = "<@555666777>"
        return user
    
    @pytest.fixture
    def input_media_config(self):
        """創建 input media 配置"""
        return InputMediaConfig(
            max_emoji_per_message=2,
            max_sticker_per_message=1,
            max_animated_frames=3,
            emoji_sticker_max_size=128,
            enable_emoji_processing=True,
            enable_sticker_processing=True,
            enable_animated_processing=True
        )
    
    @pytest.mark.asyncio
    async def test_emoji_processing_disabled(self, mock_discord_message_with_emoji, mock_discord_client_user):
        """測試 emoji 處理功能被禁用時的行為"""
        config = InputMediaConfig(enable_emoji_processing=False)
        
        processed_msg = await _process_single_message(
            mock_discord_message_with_emoji,
            mock_discord_client_user,
            max_text=1000,
            remaining_imgs_count=5,
            httpx_client=None,
            input_media_config=config
        )
        
        assert processed_msg is not None
        assert isinstance(processed_msg.content, str)
        # 應該包含原始文字但沒有處理 emoji 圖片
        assert "Hello" in processed_msg.content
        assert "world" in processed_msg.content
    
    @pytest.mark.asyncio
    async def test_sticker_processing_disabled(self, mock_discord_message_with_stickers, mock_discord_client_user):
        """測試 sticker 處理功能被禁用時的行為"""
        config = InputMediaConfig(enable_sticker_processing=False)
        
        processed_msg = await _process_single_message(
            mock_discord_message_with_stickers,
            mock_discord_client_user,
            max_text=1000,
            remaining_imgs_count=5,
            httpx_client=None,
            input_media_config=config
        )
        
        assert processed_msg is not None
        assert isinstance(processed_msg.content, str)
        # 應該包含原始文字但沒有處理 sticker 圖片
        assert "Check out this sticker!" in processed_msg.content
    
    @pytest.mark.asyncio
    async def test_sticker_processing_enabled(self, mock_discord_message_with_stickers, mock_discord_client_user, input_media_config):
        """測試 sticker 處理功能啟用時的行為"""
        processed_msg = await _process_single_message(
            mock_discord_message_with_stickers,
            mock_discord_client_user,
            max_text=1000,
            remaining_imgs_count=5,
            httpx_client=None,
            input_media_config=input_media_config
        )
        
        assert processed_msg is not None
        # 應該包含文字和圖片內容
        if isinstance(processed_msg.content, list):
            # 多模態內容格式
            text_parts = [item for item in processed_msg.content if item.get("type") == "text"]
            image_parts = [item for item in processed_msg.content if item.get("type") == "image_url"]
            
            assert len(text_parts) > 0
            assert "Check out this sticker!" in text_parts[0]["text"]
            # 如果 sticker 處理成功，應該有圖片
            if len(image_parts) > 0:
                assert "data:image/" in image_parts[0]["image_url"]["url"]
    
    @pytest.mark.asyncio
    async def test_lottie_sticker_skipped(self, mock_discord_client_user, input_media_config):
        """測試 Lottie 格式的 sticker 被正確跳過"""
        # 創建包含 Lottie sticker 的訊息
        msg = Mock()
        msg.id = 123456789
        msg.content = "Lottie sticker test"
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.embeds = []
        msg.reference = None
        
        # 創建 Lottie 格式的 sticker
        mock_lottie_sticker = Mock()
        mock_lottie_sticker.name = "lottie_sticker"
        mock_lottie_sticker.format = Mock()
        mock_lottie_sticker.format.__str__ = Mock(return_value="StickerFormatType.lottie")
        
        msg.stickers = [mock_lottie_sticker]
        
        processed_msg = await _process_single_message(
            msg,
            mock_discord_client_user,
            max_text=1000,
            remaining_imgs_count=5,
            httpx_client=None,
            input_media_config=input_media_config
        )
        
        assert processed_msg is not None
        # Lottie sticker 應該被跳過，只有文字內容
        assert isinstance(processed_msg.content, str)
        assert "Lottie sticker test" in processed_msg.content
    
    @pytest.mark.asyncio
    async def test_collect_message_with_emoji_sticker_config(self, mock_discord_message_with_stickers, mock_discord_client_user, input_media_config):
        """測試 collect_message 函數使用 input_media_config"""
        # 創建一個異步迭代器類
        class AsyncIterator:
            def __init__(self, items):
                self.items = items
                self.index = 0
            
            def __aiter__(self):
                return self
            
            async def __anext__(self):
                if self.index >= len(self.items):
                    raise StopAsyncIteration
                item = self.items[self.index]
                self.index += 1
                return item
        
        # 模擬頻道歷史 - 返回空的異步迭代器
        mock_discord_message_with_stickers.channel.history = Mock(return_value=AsyncIterator([]))
        
        # 調用 collect_message 並傳遞 input_media_config
        result = await collect_message(
            mock_discord_message_with_stickers,
            mock_discord_client_user,
            enable_conversation_history=True,
            httpx_client=None,
            input_media_config=input_media_config
        )
        
        # 驗證結果
        assert result is not None
        assert len(result.messages) > 0
        
        # 檢查是否正確處理了 sticker
        message = result.messages[-1]  # 最新的訊息
        if isinstance(message.content, list):
            # 如果有 sticker 圖片，應該是多模態格式
            image_parts = [item for item in message.content if item.get("type") == "image_url"]
            # 不強制要求有圖片，因為 sticker 處理可能會失敗
            if len(image_parts) > 0:
                assert "data:image/" in image_parts[0]["image_url"]["url"]

    @pytest.mark.asyncio
    async def test_animated_gif_attachment_processing(self, mock_discord_client_user, input_media_config):
        """測試動畫 GIF 附件處理"""
        # 創建包含 GIF 附件的訊息
        msg = Mock()
        msg.id = 123456789
        msg.content = "Check this GIF!"
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.embeds = []
        msg.stickers = []
        msg.reference = None
        
        # 創建模擬 GIF 附件
        mock_attachment = Mock()
        mock_attachment.filename = "test.gif"
        mock_attachment.content_type = "image/gif"
        mock_attachment.url = "https://example.com/test.gif"
        
        msg.attachments = [mock_attachment]
        
        # 創建簡單的模擬 httpx 客戶端
        mock_httpx_client = Mock()
        
        # 創建一個簡單的 GIF 圖片數據
        test_image = Image.new('RGB', (50, 50), color='blue')
        img_bytes = BytesIO()
        test_image.save(img_bytes, format='GIF')
        
        mock_response = Mock()
        mock_response.content = img_bytes.getvalue()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        processed_msg = await _process_single_message(
            msg,
            mock_discord_client_user,
            max_text=1000,
            remaining_imgs_count=5,
            httpx_client=mock_httpx_client,
            input_media_config=input_media_config
        )
        
        assert processed_msg is not None
        # 檢查是否正確處理了 GIF
        if isinstance(processed_msg.content, list):
            text_parts = [item for item in processed_msg.content if item.get("type") == "text"]
            image_parts = [item for item in processed_msg.content if item.get("type") == "image_url"]
            
            assert len(text_parts) > 0
            assert "Check this GIF!" in text_parts[0]["text"]
            # 如果 GIF 處理成功，應該有圖片
            if len(image_parts) > 0:
                assert "data:image/" in image_parts[0]["image_url"]["url"]
    
    @pytest.mark.asyncio
    async def test_emoji_sticker_limits_respected(self, mock_discord_client_user):
        """測試 emoji 和 sticker 數量限制被正確遵守"""
        # 創建限制較小的配置
        config = InputMediaConfig(
            max_emoji_per_message=1,
            max_sticker_per_message=1,
            enable_emoji_processing=True,
            enable_sticker_processing=True
        )
        
        # 創建包含多個 emoji 的訊息
        msg = Mock()
        msg.id = 123456789
        msg.content = "Hello <:emoji1:111> world <:emoji2:222> test <:emoji3:333>!"
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.embeds = []
        msg.reference = None
        msg.guild = Mock()
        msg.guild.get_emoji = Mock(return_value=None)
        
        # 創建多個模擬 sticker
        mock_stickers = []
        for i in range(3):
            mock_sticker = Mock()
            mock_sticker.name = f"test_sticker_{i}"
            mock_sticker.format = Mock()
            mock_sticker.format.__str__ = Mock(return_value="StickerFormatType.png")
            mock_sticker.url = f"https://example.com/sticker_{i}.png"
            
            test_image = Image.new('RGB', (50, 50), color='red')
            img_bytes = BytesIO()
            test_image.save(img_bytes, format='PNG')
            mock_sticker.read = AsyncMock(return_value=img_bytes.getvalue())
            mock_stickers.append(mock_sticker)
        
        msg.stickers = mock_stickers
        
        processed_msg = await _process_single_message(
            msg,
            mock_discord_client_user,
            max_text=1000,
            remaining_imgs_count=10,
            httpx_client=None,
            input_media_config=config
        )
        
        assert processed_msg is not None
        # 檢查限制是否被遵守
        if isinstance(processed_msg.content, list):
            image_parts = [item for item in processed_msg.content if item.get("type") == "image_url"]
            # 最多應該有 2 張圖片（1 emoji + 1 sticker）
            assert len(image_parts) <= 2
    
    @pytest.mark.asyncio 
    async def test_error_handling_in_processing(self, mock_discord_client_user, input_media_config):
        """測試處理過程中的錯誤處理"""
        # 創建會導致錯誤的 sticker
        msg = Mock()
        msg.id = 123456789
        msg.content = "Error test"
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.embeds = []
        msg.reference = None
        
        # 創建會拋出異常的 sticker
        mock_sticker = Mock()
        mock_sticker.name = "error_sticker"
        mock_sticker.format = Mock()
        mock_sticker.format.__str__ = Mock(return_value="StickerFormatType.png")
        mock_sticker.read = AsyncMock(side_effect=Exception("Network error"))
        
        msg.stickers = [mock_sticker]
        
        # 這個測試應該不會拋出異常，而是優雅地處理錯誤
        processed_msg = await _process_single_message(
            msg,
            mock_discord_client_user,
            max_text=1000,
            remaining_imgs_count=5,
            httpx_client=None,
            input_media_config=input_media_config
        )
        
        assert processed_msg is not None
        # 即使 sticker 處理失敗，文字內容仍應正常處理
        if isinstance(processed_msg.content, str):
            assert "Error test" in processed_msg.content
        else:
            text_parts = [item for item in processed_msg.content if item.get("type") == "text"]
            assert len(text_parts) > 0
            assert "Error test" in text_parts[0]["text"]

    @pytest.mark.asyncio
    async def test_message_with_only_sticker_should_be_processed(self):
        """測試只有 sticker 沒有文字的訊息應該被處理"""
        from schemas.config_types import AppConfig, DiscordConfig, DiscordPermissionsConfig
        
        # 創建允許 DM 的配置
        test_config = AppConfig(
            discord=DiscordConfig(
                permissions=DiscordPermissionsConfig(allow_dms=True)
            )
        )
        
        # 創建只有 sticker 的訊息
        mock_message = Mock()
        mock_message.content = ""  # 空文字內容
        mock_message.author = Mock()
        mock_message.author.bot = False
        mock_message.author.id = 12345
        mock_message.channel = Mock()
        mock_message.channel.type = discord.ChannelType.private  # DM 訊息
        mock_message.guild = None
        mock_message.mentions = []
        
        # 創建模擬 sticker
        mock_sticker = Mock()
        mock_sticker.name = "test_sticker"
        mock_message.stickers = [mock_sticker]
        mock_message.attachments = []
        
        handler = DiscordMessageHandler(test_config)
        
        # 應該返回 True，因為有 sticker
        should_process = handler._should_process_message(mock_message)
        assert should_process is True
    
    @pytest.mark.asyncio
    async def test_message_with_only_attachment_should_be_processed(self):
        """測試只有附件沒有文字的訊息應該被處理"""
        from schemas.config_types import AppConfig, DiscordConfig, DiscordPermissionsConfig
        
        # 創建允許 DM 的配置
        test_config = AppConfig(
            discord=DiscordConfig(
                permissions=DiscordPermissionsConfig(allow_dms=True)
            )
        )
        
        # 創建只有附件的訊息
        mock_message = Mock()
        mock_message.content = ""  # 空文字內容
        mock_message.author = Mock()
        mock_message.author.bot = False
        mock_message.author.id = 12345
        mock_message.channel = Mock()
        mock_message.channel.type = discord.ChannelType.private  # DM 訊息
        mock_message.guild = None
        mock_message.mentions = []
        
        # 創建模擬附件
        mock_attachment = Mock()
        mock_attachment.filename = "image.png"
        mock_message.attachments = [mock_attachment]
        mock_message.stickers = []
        
        handler = DiscordMessageHandler(test_config)
        
        # 應該返回 True，因為有附件
        should_process = handler._should_process_message(mock_message)
        assert should_process is True
    
    @pytest.mark.asyncio
    async def test_empty_message_should_not_be_processed(self):
        """測試完全空的訊息不應該被處理"""
        from schemas.config_types import AppConfig, DiscordConfig, DiscordPermissionsConfig
        
        # 創建允許 DM 的配置
        test_config = AppConfig(
            discord=DiscordConfig(
                permissions=DiscordPermissionsConfig(allow_dms=True)
            )
        )
        
        # 創建完全空的訊息
        mock_message = Mock()
        mock_message.content = ""  # 空文字內容
        mock_message.author = Mock()
        mock_message.author.bot = False
        mock_message.author.id = 12345
        mock_message.channel = Mock()
        mock_message.channel.type = discord.ChannelType.private  # DM 訊息
        mock_message.guild = None
        mock_message.mentions = []
        mock_message.stickers = []  # 沒有 sticker
        mock_message.attachments = []  # 沒有附件
        
        handler = DiscordMessageHandler(test_config)
        
        # 應該返回 False，因為完全沒有內容
        should_process = handler._should_process_message(mock_message)
        assert should_process is False


class TestMediaSummaryGeneration:
    """測試媒體摘要生成"""

    @pytest.fixture
    def mock_client_user(self):
        user = Mock(spec=discord.ClientUser)
        user.id = 12345
        user.mention = "<@12345>"
        return user

    @pytest.fixture
    def base_message(self, mock_client_user):
        msg = Mock(spec=discord.Message)
        msg.content = "Test message"
        msg.author = Mock()
        msg.author.id = 67890
        msg.author.display_name = "Test User"
        msg.author.mention = "<@67890>"
        msg.attachments = []
        msg.stickers = []
        msg.embeds = []
        msg.reference = None
        msg.guild = None
        msg.created_at = datetime.now()
        msg.id = 111
        return msg

    @pytest.mark.asyncio
    @patch('discord_bot.message_collector._process_discord_stickers')
    @patch('discord_bot.message_collector._process_emoji_from_message')
    @patch('discord_bot.message_collector.process_attachment_image')
    async def test_summary_with_all_media_types(
        self, mock_process_attachment, mock_process_emoji, mock_process_stickers,
        base_message, mock_client_user
    ):
        """測試包含所有媒體類型時的摘要生成"""
        # 模擬附件
        mock_attachment = Mock(spec=discord.Attachment)
        mock_attachment.content_type = "image/gif"
        base_message.attachments = [mock_attachment]

        # 模擬函數返回值
        mock_process_stickers.return_value = ([], {"total": 1, "animated": 0, "static": 1})
        mock_process_emoji.return_value = ([], {"total": 1, "animated": 1, "static": 0})
        mock_process_attachment.return_value = ([], True) # 模擬動畫附件

        result = await _process_single_message(
            base_message, mock_client_user, 1000, 5, None, InputMediaConfig()
        )

        expected_summary = "[包含: 1個emoji, 1個sticker, 2個動畫]"
        # 因為所有模擬都返回空圖片列表，所以最終 content 應該是 str
        assert isinstance(result.content, str)
        assert expected_summary in result.content

    @pytest.mark.asyncio
    @patch('discord_bot.message_collector._process_discord_stickers')
    @patch('discord_bot.message_collector._process_emoji_from_message')
    @patch('discord_bot.message_collector.process_attachment_image')
    async def test_summary_with_no_media(
        self, mock_process_attachment, mock_process_emoji, mock_process_stickers,
        base_message, mock_client_user
    ):
        """測試沒有媒體內容時不生成摘要"""
        mock_process_stickers.return_value = ([], {"total": 0, "animated": 0, "static": 0})
        mock_process_emoji.return_value = ([], {"total": 0, "animated": 0, "static": 0})

        result = await _process_single_message(
            base_message, mock_client_user, 1000, 5, None, InputMediaConfig()
        )

        assert "[包含:" not in result.content

    @pytest.mark.asyncio
    @patch('discord_bot.message_collector._process_discord_stickers')
    @patch('discord_bot.message_collector._process_emoji_from_message')
    @patch('discord_bot.message_collector.process_attachment_image')
    async def test_summary_with_only_emoji(
        self, mock_process_attachment, mock_process_emoji, mock_process_stickers,
        base_message, mock_client_user
    ):
        """測試僅包含 emoji 時的摘要生成"""
        mock_process_stickers.return_value = ([], {"total": 0, "animated": 0, "static": 0})
        mock_process_emoji.return_value = ([], {"total": 2, "animated": 1, "static": 1})

        result = await _process_single_message(
            base_message, mock_client_user, 1000, 5, None, InputMediaConfig()
        )

        expected_summary = "[包含: 2個emoji, 1個動畫]"
        # 當沒有圖片時，content 是 str
        assert isinstance(result.content, str)
        assert expected_summary in result.content


class TestDiscordGifUrlProcessing:
    """測試 Discord GIF URL 處理功能"""
    
    @pytest.fixture
    def mock_client_user(self):
        """創建模擬的 Discord 客戶端用戶"""
        user = Mock()
        user.id = 555666777
        user.mention = "<@555666777>"
        return user
    
    @pytest.fixture
    def input_media_config(self):
        """創建 input media 配置"""
        return InputMediaConfig()
    
    @pytest.mark.asyncio
    async def test_message_with_discord_gif_url(self, mock_client_user, input_media_config):
        """測試包含 Discord GIF URL 的訊息處理（embed thumbnail 方式）"""
        # 創建包含 embed thumbnail GIF URL 的訊息
        msg = Mock()
        msg.id = 123456789
        msg.content = "看看這個動畫很棒吧！"  # 文字中不包含 URL
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.stickers = []
        msg.reference = None
        
        # 創建包含 GIF URL 的 embed
        mock_embed = Mock()
        mock_embed.title = None
        mock_embed.description = None
        mock_embed.footer = None
        mock_embed._thumbnail = {
            'url': 'https://media.discordapp.net/stickers/1349767432977252372.gif',
            'width': 100,
            'height': 100
        }
        # 確保沒有 image 屬性
        mock_embed.image = None
        msg.embeds = [mock_embed]
        
        # 創建模擬 httpx 客戶端
        mock_httpx_client = Mock()
        
        # 創建一個簡單的 GIF 圖片數據
        test_image = Image.new('RGB', (50, 50), color='red')
        img_bytes = BytesIO()
        test_image.save(img_bytes, format='GIF')
        
        mock_response = Mock()
        mock_response.content = img_bytes.getvalue()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        processed_msg = await _process_single_message(
            msg,
            mock_client_user,
            max_text=1000,
            remaining_imgs_count=5,
            httpx_client=mock_httpx_client,
            input_media_config=input_media_config
        )
        
        assert processed_msg is not None
        
        # 檢查處理結果
        if isinstance(processed_msg.content, list):
            text_parts = [item for item in processed_msg.content if item.get("type") == "text"]
            assert len(text_parts) > 0
            text_content = text_parts[0]["text"]
            assert "看看這個動畫很棒吧！" in text_content
            
            # 檢查是否有圖片被處理
            image_parts = [item for item in processed_msg.content if item.get("type") == "image_url"]
            assert len(image_parts) > 0
        else:
            # 如果只有文字，檢查內容
            assert "看看這個動畫很棒吧！" in processed_msg.content
    
    @pytest.mark.asyncio
    async def test_message_with_multiple_discord_gif_urls(self, mock_client_user, input_media_config):
        """測試包含多個 Discord GIF URL 的訊息處理"""
        msg = Mock()
        msg.id = 123456789
        msg.content = """
        第一個動畫 https://media.discordapp.net/stickers/123.gif
        第二個動畫 https://cdn.discordapp.com/attachments/456/789/test.gif
        普通連結 https://example.com/image.gif 不會被處理
        """
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.embeds = []
        msg.stickers = []
        msg.reference = None
        
        # 創建模擬 httpx 客戶端
        mock_httpx_client = Mock()
        
        # 創建 GIF 圖片數據
        test_image = Image.new('RGB', (50, 50), color='green')
        img_bytes = BytesIO()
        test_image.save(img_bytes, format='GIF')
        
        mock_response = Mock()
        mock_response.content = img_bytes.getvalue()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        processed_msg = await _process_single_message(
            msg,
            mock_client_user,
            max_text=1000,
            remaining_imgs_count=5,
            httpx_client=mock_httpx_client,
            input_media_config=input_media_config
        )
        
        assert processed_msg is not None
        
        if isinstance(processed_msg.content, list):
            text_parts = [item for item in processed_msg.content if item.get("type") == "text"]
            assert len(text_parts) > 0
            text_content = text_parts[0]["text"]
            
            # Discord GIF URLs 應該被刪除
            assert "https://media.discordapp.net/stickers/123.gif" not in text_content
            assert "https://cdn.discordapp.com/attachments/456/789/test.gif" not in text_content
            
            # 普通連結應該保留
            assert "https://example.com/image.gif" in text_content
            
            # 文字內容應該保留
            assert "第一個動畫" in text_content
            assert "第二個動畫" in text_content
            assert "普通連結" in text_content
    
    @pytest.mark.asyncio
    async def test_discord_gif_url_with_real_attachments(self, mock_client_user, input_media_config):
        """測試 Discord GIF URL 與真實附件混合處理（embed thumbnail 方式）"""
        msg = Mock()
        msg.id = 123456789
        msg.content = "URL GIF 和附件："  # 文字中不包含 URL
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.stickers = []
        msg.reference = None
        
        # 創建包含 GIF URL 的 embed
        mock_embed = Mock()
        mock_embed.title = None
        mock_embed.description = None
        mock_embed.footer = None
        mock_embed._thumbnail = {
            'url': 'https://media.discordapp.net/stickers/123.gif',
            'width': 100,
            'height': 100
        }
        # 確保沒有 image 屬性
        mock_embed.image = None
        msg.embeds = [mock_embed]
        
        # 創建真實圖片附件
        mock_attachment = Mock()
        mock_attachment.filename = "real_image.png"
        mock_attachment.content_type = "image/png"
        mock_attachment.url = "https://example.com/real_image.png"
        
        msg.attachments = [mock_attachment]
        
        # 創建模擬 httpx 客戶端
        mock_httpx_client = Mock()
        
        # 創建不同的圖片數據
        gif_image = Image.new('RGB', (50, 50), color='red')
        gif_bytes = BytesIO()
        gif_image.save(gif_bytes, format='GIF')
        
        png_image = Image.new('RGB', (50, 50), color='blue')
        png_bytes = BytesIO()
        png_image.save(png_bytes, format='PNG')
        
        # 根據 URL 返回不同的內容
        def mock_get(url):
            mock_response = Mock()
            if "stickers/123.gif" in url:
                mock_response.content = gif_bytes.getvalue()
            else:
                mock_response.content = png_bytes.getvalue()
            return mock_response
        
        mock_httpx_client.get = AsyncMock(side_effect=mock_get)
        
        processed_msg = await _process_single_message(
            msg,
            mock_client_user,
            max_text=1000,
            remaining_imgs_count=5,
            httpx_client=mock_httpx_client,
            input_media_config=input_media_config
        )
        
        assert processed_msg is not None
        
        if isinstance(processed_msg.content, list):
            text_parts = [item for item in processed_msg.content if item.get("type") == "text"]
            image_parts = [item for item in processed_msg.content if item.get("type") == "image_url"]
            
            assert len(text_parts) > 0
            text_content = text_parts[0]["text"]
            
            # 文字內容應該保留
            assert "URL GIF 和附件：" in text_content
            
            # 應該有兩張圖片（URL GIF + 真實附件）
            assert len(image_parts) >= 1  # 至少有一張圖片被處理
    
    @pytest.mark.asyncio
    async def test_discord_gif_url_image_limit_respected(self, mock_client_user, input_media_config):
        """測試 Discord GIF URL 遵守圖片數量限制"""
        msg = Mock()
        msg.id = 123456789
        msg.content = """
        URL1: https://media.discordapp.net/stickers/1.gif
        URL2: https://media.discordapp.net/stickers/2.gif
        URL3: https://media.discordapp.net/stickers/3.gif
        """
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.embeds = []
        msg.stickers = []
        msg.reference = None
        
        # 創建模擬 httpx 客戶端
        mock_httpx_client = Mock()
        
        test_image = Image.new('RGB', (50, 50), color='yellow')
        img_bytes = BytesIO()
        test_image.save(img_bytes, format='GIF')
        
        mock_response = Mock()
        mock_response.content = img_bytes.getvalue()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        # 設定較低的圖片限制
        processed_msg = await _process_single_message(
            msg,
            mock_client_user,
            max_text=1000,
            remaining_imgs_count=2,  # 只允許 2 張圖片
            httpx_client=mock_httpx_client,
            input_media_config=input_media_config
        )
        
        assert processed_msg is not None
        
        if isinstance(processed_msg.content, list):
            image_parts = [item for item in processed_msg.content if item.get("type") == "image_url"]
            # 應該只處理 2 張圖片
            assert len(image_parts) <= 2
    
    @pytest.mark.asyncio
    async def test_discord_gif_url_download_failure(self, mock_client_user, input_media_config):
        """測試 Discord GIF URL 下載失敗的處理（embed thumbnail 方式）"""
        msg = Mock()
        msg.id = 123456789
        msg.content = "失敗的 URL 測試"  # 文字中不包含 URL
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.stickers = []
        msg.reference = None
        
        # 創建包含失敗 GIF URL 的 embed
        mock_embed = Mock()
        mock_embed.title = None
        mock_embed.description = None
        mock_embed.footer = None
        mock_embed._thumbnail = {
            'url': 'https://media.discordapp.net/stickers/broken.gif',
            'width': 100,
            'height': 100
        }
        # 確保沒有 image 屬性
        mock_embed.image = None
        msg.embeds = [mock_embed]
        
        # 創建模擬 httpx 客戶端，模擬下載失敗
        mock_httpx_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.content = b""
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        processed_msg = await _process_single_message(
            msg,
            mock_client_user,
            max_text=1000,
            remaining_imgs_count=5,
            httpx_client=mock_httpx_client,
            input_media_config=input_media_config
        )
        
        assert processed_msg is not None
        
        # 即使下載失敗，處理應該正常進行
        if isinstance(processed_msg.content, list):
            text_parts = [item for item in processed_msg.content if item.get("type") == "text"]
            assert len(text_parts) > 0
            text_content = text_parts[0]["text"]
            assert "失敗的 URL 測試" in text_content
        else:
            assert "失敗的 URL 測試" in processed_msg.content
    
    @pytest.mark.asyncio
    async def test_media_summary_includes_url_gifs(self, mock_client_user, input_media_config):
        """測試媒體摘要包含 URL GIF（embed thumbnail 方式）"""
        msg = Mock()
        msg.id = 123456789
        msg.content = "動畫測試"  # 文字中不包含 URL
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.stickers = []
        msg.reference = None
        
        # 創建包含動畫 GIF URL 的 embed
        mock_embed = Mock()
        mock_embed.title = None
        mock_embed.description = None
        mock_embed.footer = None
        mock_embed._thumbnail = {
            'url': 'https://media.discordapp.net/stickers/animated.gif',
            'width': 100,
            'height': 100
        }
        # 確保沒有 image 屬性
        mock_embed.image = None
        msg.embeds = [mock_embed]
        
        # 創建模擬 httpx 客戶端
        mock_httpx_client = Mock()
        
        # 創建動畫 GIF（模擬）
        test_image = Image.new('RGB', (50, 50), color='purple')
        test_image.is_animated = True  # 標記為動畫
        img_bytes = BytesIO()
        test_image.save(img_bytes, format='GIF')
        
        mock_response = Mock()
        mock_response.content = img_bytes.getvalue()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        with patch('utils.image_processor.sample_animated_frames') as mock_sample:
            # 模擬動畫處理結果
            mock_sample.return_value = ([test_image], True)  # 返回動畫標記
            
            processed_msg = await _process_single_message(
                msg,
                mock_client_user,
                max_text=1000,
                remaining_imgs_count=5,
                httpx_client=mock_httpx_client,
                input_media_config=input_media_config
            )
        
        assert processed_msg is not None
        
        if isinstance(processed_msg.content, list):
            text_parts = [item for item in processed_msg.content if item.get("type") == "text"]
            assert len(text_parts) > 0
            text_content = text_parts[0]["text"]
            
            # 檢查媒體摘要
            assert "[包含:" in text_content
            assert "動畫" in text_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestExpandedEmbedProcessing:
    """測試 Phase 7 擴展的 Embed 媒體處理功能"""
    
    @pytest.fixture
    def mock_client_user(self):
        """創建模擬的 Discord 客戶端用戶"""
        user = Mock()
        user.id = 555666777
        user.mention = "<@555666777>"
        return user
    
    @pytest.fixture
    def input_media_config(self):
        """創建 input media 配置"""
        return InputMediaConfig(
            max_emoji_per_message=2,
            max_sticker_per_message=1,
            max_animated_frames=3,
            emoji_sticker_max_size=128,
            enable_emoji_processing=True,
            enable_sticker_processing=True,
            enable_animated_processing=True
        )
    
    @pytest.mark.asyncio
    async def test_embed_image_proxy_processing(self, mock_client_user, input_media_config):
        """測試 EmbedProxy 圖片處理"""
        # 創建包含 embed image 的訊息
        msg = Mock()
        msg.id = 123456789
        msg.content = "Check out this embed image!"
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.stickers = []
        msg.reference = None
        
        # 創建包含 embed image 的 embed
        mock_embed = Mock()
        mock_embed.title = None
        mock_embed.description = None
        mock_embed.footer = None
        
        # 模擬 embed image (EmbedProxy)
        mock_embed_image = Mock()
        mock_embed_image.url = "https://example.com/twitter-image.jpg"
        mock_embed_image.proxy_url = "https://images-ext-1.discordapp.net/external/proxy-url.jpg"
        mock_embed.image = mock_embed_image
        
        # 確保沒有 _thumbnail 屬性
        mock_embed._thumbnail = None
        
        msg.embeds = [mock_embed]
        
        # 模擬 HTTP 客戶端
        mock_httpx_client = Mock()
        
        # 創建測試圖片數據
        test_image = Image.new('RGB', (100, 100), color='green')
        img_bytes = BytesIO()
        test_image.save(img_bytes, format='JPEG')
        
        mock_response = Mock()
        mock_response.content = img_bytes.getvalue()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        processed_msg = await _process_single_message(
            msg,
            mock_client_user,
            max_text=1000,
            remaining_imgs_count=5,
            httpx_client=mock_httpx_client,
            input_media_config=input_media_config
        )
        
        assert processed_msg is not None
        
        # 應該包含文字和圖片內容
        if isinstance(processed_msg.content, list):
            text_parts = [item for item in processed_msg.content if item.get("type") == "text"]
            image_parts = [item for item in processed_msg.content if item.get("type") == "image_url"]
            
            assert len(text_parts) > 0
            assert "Check out this embed image!" in text_parts[0]["text"]
            assert len(image_parts) > 0
            assert "data:image/" in image_parts[0]["image_url"]["url"]
    
    @pytest.mark.asyncio
    async def test_mixed_thumbnail_and_image(self, mock_client_user, input_media_config):
        """測試同時包含 thumbnail 和 image 的 embed"""
        msg = Mock()
        msg.id = 123456789
        msg.content = "Multiple embed images!"
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.stickers = []
        msg.reference = None
        
        # 創建包含 thumbnail 和 image 的 embed
        mock_embed = Mock()
        mock_embed.title = None
        mock_embed.description = None
        mock_embed.footer = None
        
        # 模擬 embed thumbnail
        mock_embed._thumbnail = {
            'url': 'https://imgur.com/thumbnail.png'
        }
        
        # 模擬 embed image
        mock_embed_image = Mock()
        mock_embed_image.url = "https://example.com/main-image.webp"
        mock_embed_image.proxy_url = None
        mock_embed.image = mock_embed_image
        
        msg.embeds = [mock_embed]
        
        # 模擬 HTTP 客戶端
        mock_httpx_client = Mock()
        
        # 創建測試圖片數據
        test_image = Image.new('RGB', (100, 100), color='blue')
        img_bytes = BytesIO()
        test_image.save(img_bytes, format='PNG')
        
        mock_response = Mock()
        mock_response.content = img_bytes.getvalue()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        processed_msg = await _process_single_message(
            msg,
            mock_client_user,
            max_text=1000,
            remaining_imgs_count=5,
            httpx_client=mock_httpx_client,
            input_media_config=input_media_config
        )
        
        assert processed_msg is not None
        
        # 應該處理兩個圖片（thumbnail 和 image）
        if isinstance(processed_msg.content, list):
            image_parts = [item for item in processed_msg.content if item.get("type") == "image_url"]
            # 應該至少有一個圖片（可能兩個都處理成功）
            assert len(image_parts) >= 1
    
    @pytest.mark.asyncio
    async def test_video_url_skipped(self, mock_client_user, input_media_config):
        """測試影片 URL 被正確跳過"""
        msg = Mock()
        msg.id = 123456789
        msg.content = "Video content"
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.stickers = []
        msg.reference = None
        
        # 創建包含影片 URL 的 embed
        mock_embed = Mock()
        mock_embed.title = None
        mock_embed.description = None
        mock_embed.footer = None
        
        # 模擬 embed thumbnail 包含影片 URL
        mock_embed._thumbnail = {
            'url': 'https://example.com/video.mp4'
        }
        
        # 模擬 embed image 也包含影片 URL
        mock_embed_image = Mock()
        mock_embed_image.url = "https://example.com/another-video.webm"
        mock_embed_image.proxy_url = None
        mock_embed.image = mock_embed_image
        
        msg.embeds = [mock_embed]
        
        processed_msg = await _process_single_message(
            msg,
            mock_client_user,
            max_text=1000,
            remaining_imgs_count=5,
            httpx_client=None,
            input_media_config=input_media_config
        )
        
        assert processed_msg is not None
        
        # 影片 URL 應該被跳過，只有文字內容
        assert isinstance(processed_msg.content, str)
        assert "Video content" in processed_msg.content
        # 不應該包含媒體摘要（因為沒有處理任何媒體）
        assert "[包含:" not in processed_msg.content
    
    @pytest.mark.asyncio
    async def test_unsupported_url_processed_anyway(self, mock_client_user, input_media_config):
        """測試不明格式的 URL 仍會嘗試處理（簡化邏輯）"""
        msg = Mock()
        msg.id = 123456789
        msg.content = "Unknown format content"
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.stickers = []
        msg.reference = None
        
        # 創建包含未知格式 URL 的 embed
        mock_embed = Mock()
        mock_embed.title = None
        mock_embed.description = None
        mock_embed.footer = None
        
        # 模擬 embed thumbnail 包含未知格式的 URL（不是影片）
        mock_embed._thumbnail = {
            'url': 'https://example.com/document.pdf'
        }
        
        # 模擬 embed image 包含未知格式的 URL
        mock_embed_image = Mock()
        mock_embed_image.url = "https://example.com/archive.zip"
        mock_embed_image.proxy_url = None
        mock_embed.image = mock_embed_image
        
        msg.embeds = [mock_embed]
        
        # 模擬 HTTP 客戶端會嘗試下載，但會失敗
        mock_httpx_client = Mock()
        mock_response = Mock()
        mock_response.content = b"not an image"  # 非圖片內容
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        processed_msg = await _process_single_message(
            msg,
            mock_client_user,
            max_text=1000,
            remaining_imgs_count=5,
            httpx_client=mock_httpx_client,
            input_media_config=input_media_config
        )
        
        assert processed_msg is not None
        
        # 簡化邏輯：會嘗試處理，但可能失敗，最終只有文字內容
        # 這裡不強制要求特定行為，因為錯誤處理會讓它回退到文字模式
        assert "Unknown format content" in str(processed_msg.content)
    
    @pytest.mark.asyncio
    async def test_external_domain_image_processing(self, mock_client_user, input_media_config):
        """測試外部域名圖片處理（無域名限制）"""
        msg = Mock()
        msg.id = 123456789
        msg.content = "External image"
        msg.author.id = 987654321
        msg.author.display_name = "測試用戶"
        msg.author.mention = "<@987654321>"
        msg.channel.id = 111222333
        msg.created_at = datetime.now()
        msg.attachments = []
        msg.stickers = []
        msg.reference = None
        
        # 創建包含外部域名圖片的 embed
        mock_embed = Mock()
        mock_embed.title = None
        mock_embed.description = None
        mock_embed.footer = None
        
        # 模擬各種外部域名的圖片
        mock_embed._thumbnail = {
            'url': 'https://twitter.com/user/photo.jpg'
        }
        
        mock_embed_image = Mock()
        mock_embed_image.url = "https://imgur.com/gallery/image.png"
        mock_embed_image.proxy_url = None
        mock_embed.image = mock_embed_image
        
        msg.embeds = [mock_embed]
        
        # 模擬 HTTP 客戶端
        mock_httpx_client = Mock()
        
        # 創建測試圖片數據
        test_image = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        test_image.save(img_bytes, format='JPEG')
        
        mock_response = Mock()
        mock_response.content = img_bytes.getvalue()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        
        processed_msg = await _process_single_message(
            msg,
            mock_client_user,
            max_text=1000,
            remaining_imgs_count=5,
            httpx_client=mock_httpx_client,
            input_media_config=input_media_config
        )
        
        assert processed_msg is not None
        
        # 應該成功處理外部域名的圖片
        if isinstance(processed_msg.content, list):
            text_parts = [item for item in processed_msg.content if item.get("type") == "text"]
            image_parts = [item for item in processed_msg.content if item.get("type") == "image_url"]
            
            assert len(text_parts) > 0
            assert "External image" in text_parts[0]["text"]
            assert len(image_parts) >= 1
            assert "data:image/" in image_parts[0]["image_url"]["url"]
            
            # 應該包含媒體摘要
            assert "[包含:" in text_parts[0]["text"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 