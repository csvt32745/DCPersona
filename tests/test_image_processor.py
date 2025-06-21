"""
image_processor 模組單元測試

測試 Discord 圖片處理核心功能，包含 emoji 解析、
媒體載入、動畫處理和格式轉換等功能。
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from PIL import Image
from io import BytesIO
import base64

# 導入待測試的模組
from utils.image_processor import (
    ImageProcessingError,
    CUSTOM_EMOJI_RE,
    parse_emoji_from_message,
    load_from_discord_emoji_sticker,
    sample_animated_frames,
    process_attachment_image,
    ensure_rgb_format,
    resize_image,
    convert_images_to_base64_dict,
    is_discord_gif_url,
    VirtualAttachment,
    # Phase 7 新增的函數
    is_video_url,
    _infer_content_type_from_url,
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS
)


class TestImageProcessingError:
    """測試 ImageProcessingError 異常類別"""
    
    def test_exception_creation(self):
        """測試異常建立"""
        error = ImageProcessingError("測試錯誤")
        assert str(error) == "測試錯誤"
        assert isinstance(error, Exception)


class TestConstants:
    """測試常數定義"""
    
    def test_custom_emoji_regex(self):
        """測試自定義 emoji 正規表達式"""
        test_cases = [
            ("<:test:123456>", True),
            ("<a:animated:789012>", True),
            (":standard_emoji:", False),
            ("regular text", False),
            ("<:test:123456> <a:anim:789>", True)
        ]
        
        for text, should_match in test_cases:
            matches = CUSTOM_EMOJI_RE.findall(text)
            if should_match:
                assert len(matches) > 0, f"應該匹配: {text}"
            else:
                assert len(matches) == 0, f"不應該匹配: {text}"


class TestParseEmojiFromMessage:
    """測試 parse_emoji_from_message 函數"""
    
    @pytest.mark.asyncio
    async def test_parse_custom_emoji(self):
        """測試解析自定義 emoji"""
        # 建立模擬的 Discord 訊息
        mock_message = Mock()
        mock_message.content = "Hello <:test:123456> world <a:animated:789012>"
        mock_message.guild = Mock()
        
        # 建立模擬的 emoji 物件
        mock_partial_emoji = Mock()
        mock_partial_emoji.is_custom_emoji.return_value = True
        mock_partial_emoji.id = 123456
        
        mock_full_emoji = Mock()
        mock_message.guild.get_emoji.return_value = mock_full_emoji
        
        with patch('discord.PartialEmoji.from_str', return_value=mock_partial_emoji):
            result = await parse_emoji_from_message(mock_message)
            
            assert len(result) == 2
            assert mock_full_emoji in result
    
    @pytest.mark.asyncio
    async def test_parse_emoji_limit(self):
        """測試 emoji 數量限制"""
        mock_message = Mock()
        mock_message.content = "<:e1:1> <:e2:2> <:e3:3> <:e4:4> <:e5:5>"
        mock_message.guild = Mock()
        
        mock_partial_emoji = Mock()
        mock_partial_emoji.is_custom_emoji.return_value = True
        mock_partial_emoji.id = 123
        
        with patch('discord.PartialEmoji.from_str', return_value=mock_partial_emoji):
            result = await parse_emoji_from_message(mock_message, max_emoji_count=3)
            
            assert len(result) <= 3
    
    @pytest.mark.asyncio
    async def test_parse_emoji_no_guild(self):
        """測試無 guild 的情況"""
        mock_message = Mock()
        mock_message.content = "<:test:123456>"
        mock_message.guild = None
        
        mock_partial_emoji = Mock()
        mock_partial_emoji.is_custom_emoji.return_value = True
        
        with patch('discord.PartialEmoji.from_str', return_value=mock_partial_emoji):
            result = await parse_emoji_from_message(mock_message)
            
            assert len(result) == 1
            assert result[0] == mock_partial_emoji
    
    @pytest.mark.asyncio
    async def test_parse_emoji_error_handling(self):
        """測試錯誤處理"""
        mock_message = Mock()
        mock_message.content = "<:invalid:>"
        
        with patch('discord.PartialEmoji.from_str', side_effect=Exception("解析錯誤")):
            result = await parse_emoji_from_message(mock_message)
            # 現在應該返回空列表而不是拋出異常
            assert result == []


class TestLoadFromDiscordEmojiSticker:
    """測試 load_from_discord_emoji_sticker 函數"""
    
    def create_test_image(self, size=(100, 100), mode='RGB'):
        """建立測試用圖片"""
        img = Image.new(mode, size, color='red')
        return img
    
    def image_to_bytes(self, img):
        """將圖片轉換為位元組"""
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()
    
    @pytest.mark.asyncio
    async def test_load_sticker_with_read_method(self):
        """測試使用 sticker.read() 載入"""
        mock_sticker = Mock()
        mock_sticker.__class__.__name__ = 'Sticker'  # 設定類型名稱
        test_img = self.create_test_image()
        img_bytes = self.image_to_bytes(test_img)
        
        mock_sticker.read = AsyncMock(return_value=img_bytes)
        
        with patch('utils.image_processor.sample_animated_frames') as mock_sample:
            mock_sample.return_value = [test_img]
            
            result = await load_from_discord_emoji_sticker(mock_sticker)
            
            assert len(result) == 1
            mock_sticker.read.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_load_unsupported_type(self):
        """測試不支援的類型"""
        unsupported_obj = "not_a_discord_object"
        
        with pytest.raises(ImageProcessingError, match="不支援的媒體物件類型"):
            await load_from_discord_emoji_sticker(unsupported_obj)


class TestSampleAnimatedFrames:
    """測試 sample_animated_frames 函數"""
    
    def create_test_image(self, animated=False):
        """建立測試用圖片"""
        if animated:
            # 建立模擬動畫圖片
            img = Mock()
            img.is_animated = True
            
            # 模擬幀序列
            frames = []
            for i in range(8):  # 8 幀動畫
                frame = Image.new('RGB', (50, 50), color=(i*30, 0, 0))
                frames.append(frame)
            
            def mock_copy():
                if hasattr(mock_copy, 'frame_index'):
                    mock_copy.frame_index += 1
                else:
                    mock_copy.frame_index = 0
                
                if mock_copy.frame_index < len(frames):
                    return frames[mock_copy.frame_index]
                else:
                    raise EOFError()
            
            def mock_seek(pos):
                pass
            
            def mock_tell():
                return getattr(mock_copy, 'frame_index', 0)
            
            img.copy = mock_copy
            img.seek = mock_seek
            img.tell = mock_tell
            
            return img
        else:
            return Image.new('RGB', (50, 50), color='blue')
    
    def test_static_image(self):
        """測試靜態圖片"""
        img = self.create_test_image(animated=False)
        
        frames, is_animated = sample_animated_frames(img)
        
        assert len(frames) == 1
        assert not is_animated
        assert isinstance(frames[0], Image.Image)
    
    def test_animated_image_no_sampling(self):
        """測試動畫圖片（無需取樣）"""
        img = self.create_test_image(animated=True)
        
        # 修改 mock 以模擬較少的幀數
        def mock_copy():
            if hasattr(mock_copy, 'frame_index'):
                mock_copy.frame_index += 1
            else:
                mock_copy.frame_index = 0
            
            if mock_copy.frame_index < 3:  # 只有 3 幀
                return Image.new('RGB', (50, 50), color='red')
            else:
                raise EOFError()
        
        img.copy = mock_copy
        
        frames, is_animated = sample_animated_frames(img, frame_limit=4)
        
        assert len(frames) == 3
        assert is_animated
    
    def test_animated_image_with_sampling(self):
        """測試動畫圖片（需要取樣）"""
        img = self.create_test_image(animated=True)
        
        frames, is_animated = sample_animated_frames(img, frame_limit=4)
        
        assert len(frames) == 4
        assert is_animated


class TestProcessAttachmentImage:
    """測試 process_attachment_image 函數"""
    
    def create_test_image_bytes(self):
        """建立測試用圖片位元組"""
        img = Image.new('RGB', (100, 100), color='green')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()
    
    @pytest.mark.asyncio
    async def test_process_non_image_attachment(self):
        """測試處理非圖片附件"""
        mock_attachment = Mock()
        mock_attachment.content_type = "text/plain"
        
        with pytest.raises(ImageProcessingError, match="附件不是圖片格式"):
            await process_attachment_image(mock_attachment)
    
    @pytest.mark.asyncio
    async def test_process_attachment_with_httpx(self):
        """測試使用 httpx 客戶端處理附件"""
        mock_attachment = Mock()
        mock_attachment.content_type = "image/png"
        mock_attachment.url = "https://example.com/image.png"
        
        mock_httpx_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = self.create_test_image_bytes()
        
        mock_httpx_client.get.return_value = mock_response
        
        with patch('utils.image_processor.sample_animated_frames') as mock_sample:
            test_img = Image.new('RGB', (50, 50))
            mock_sample.return_value = ([test_img], False)
            
            result, is_animated = await process_attachment_image(mock_attachment, httpx_client=mock_httpx_client)
            
            assert len(result) == 1
            assert not is_animated
            mock_httpx_client.get.assert_called_once_with(mock_attachment.url)


class TestEnsureRgbFormat:
    """測試 ensure_rgb_format 函數"""
    
    def test_already_rgb(self):
        """測試已經是 RGB 格式的圖片"""
        img = Image.new('RGB', (50, 50), color='red')
        
        result = ensure_rgb_format(img)
        
        assert result.mode == 'RGB'
        assert result is img  # 應該返回原圖片
    
    def test_convert_to_rgb(self):
        """測試轉換為 RGB 格式"""
        img = Image.new('RGBA', (50, 50), color=(255, 0, 0, 128))
        
        result = ensure_rgb_format(img)
        
        assert result.mode == 'RGB'
        assert result is not img  # 應該是新的圖片物件
    
    def test_conversion_error(self):
        """測試轉換錯誤"""
        mock_img = Mock()
        mock_img.mode = 'RGBA'
        mock_img.convert.side_effect = Exception("轉換失敗")
        
        with pytest.raises(ImageProcessingError, match="轉換 RGB 格式失敗"):
            ensure_rgb_format(mock_img)


class TestResizeImage:
    """測試 resize_image 函數"""
    
    def test_no_resize_needed(self):
        """測試不需要調整大小"""
        img = Image.new('RGB', (100, 100), color='blue')
        
        result = resize_image(img, max_size=256)
        
        assert result.size == (100, 100)
    
    def test_resize_width_larger(self):
        """測試寬度較大的情況"""
        img = Image.new('RGB', (400, 200), color='green')
        
        result = resize_image(img, max_size=256)
        
        assert result.size == (256, 128)
        assert result.mode == 'RGB'
    
    def test_resize_height_larger(self):
        """測試高度較大的情況"""
        img = Image.new('RGB', (200, 400), color='red')
        
        result = resize_image(img, max_size=256)
        
        assert result.size == (128, 256)
        assert result.mode == 'RGB'
    
    def test_resize_square_image(self):
        """測試正方形圖片"""
        img = Image.new('RGB', (400, 400), color='yellow')
        
        result = resize_image(img, max_size=200)
        
        assert result.size == (200, 200)


class TestConvertImagesToBase64Dict:
    """測試 convert_images_to_base64_dict 函數"""
    
    def test_single_image_conversion(self):
        """測試單張圖片轉換"""
        img = Image.new('RGB', (50, 50), color='purple')
        
        result = convert_images_to_base64_dict([img])
        
        assert len(result) == 1
        assert result[0]['type'] == 'image_url'
        assert 'image_url' in result[0]
        assert 'url' in result[0]['image_url']
        assert result[0]['image_url']['url'].startswith('data:image/png;base64,')
    
    def test_multiple_images_conversion(self):
        """測試多張圖片轉換"""
        images = [
            Image.new('RGB', (50, 50), color='red'),
            Image.new('RGB', (50, 50), color='green'),
            Image.new('RGB', (50, 50), color='blue')
        ]
        
        result = convert_images_to_base64_dict(images)
        
        assert len(result) == 3
        for item in result:
            assert item['type'] == 'image_url'
            assert 'image_url' in item
            assert item['image_url']['url'].startswith('data:image/png;base64,')
    
    def test_different_format(self):
        """測試不同格式"""
        img = Image.new('RGB', (50, 50), color='orange')
        
        result = convert_images_to_base64_dict([img], image_format='JPEG')
        
        assert len(result) == 1
        assert result[0]['image_url']['url'].startswith('data:image/jpeg;base64,')
    
    def test_conversion_error(self):
        """測試轉換錯誤"""
        mock_img = Mock()
        mock_img.save.side_effect = Exception("儲存失敗")
        
        with pytest.raises(ImageProcessingError, match="轉換圖片為 Base64 失敗"):
            convert_images_to_base64_dict([mock_img])


class TestDiscordGifUrlValidation:
    """測試 Discord GIF URL 驗證功能"""
    
    def test_is_discord_gif_url(self):
        """測試 Discord GIF URL 驗證函數"""
        test_cases = [
            ("https://media.discordapp.net/stickers/1349767432977252372.gif", True),
            ("https://cdn.discordapp.com/attachments/123/456/image.gif", True),
            ("https://media.discordapp.net/stickers/123.png", False),
            ("https://example.com/image.gif", False),
            ("https://media.discordapp.net/stickers/test.gif?width=100", True),
            ("http://media.discordapp.net/stickers/test.gif", True),
            ("not a url", False),
            ("", False),
            (None, False)
        ]
        
        for url, should_match in test_cases:
            result = is_discord_gif_url(url)
            if should_match:
                assert result, f"應該匹配: {url}"
            else:
                assert not result, f"不應該匹配: {url}"
    
    def test_complex_gif_url_with_query_parameters(self):
        """測試帶有複雜查詢參數的 Discord GIF URLs"""
        complex_url = "https://cdn.discordapp.com/attachments/440535831942397963/1349774629320917003/QQ20250313234405.gif?ex=68582915&is=6856d795&hm=712a8710c52baf8a2b60faceb12a81d44d5160e415861afa6cc3bcedb973eec4"
        
        assert is_discord_gif_url(complex_url)
        
        # 測試其他格式
        simple_url = "https://media.discordapp.net/stickers/simple.gif"
        assert is_discord_gif_url(simple_url)


class TestVirtualAttachment:
    """測試 VirtualAttachment 類別"""
    
    def test_virtual_attachment_creation(self):
        """測試虛擬附件創建"""
        url = "https://media.discordapp.net/stickers/1349767432977252372.gif"
        
        virtual_att = VirtualAttachment(url=url)
        
        assert virtual_att.url == url
        assert virtual_att.content_type == "image/gif"  # 從 URL 推斷為 GIF
        assert virtual_att.filename == "1349767432977252372.gif"
        assert virtual_att._is_virtual == True
    
    def test_virtual_attachment_filename_extraction(self):
        """測試從 URL 提取檔名"""
        test_cases = [
            ("https://media.discordapp.net/stickers/test.gif", "test.gif"),
            ("https://cdn.discordapp.com/attachments/123/456/funny.gif", "funny.gif"),
            ("https://media.discordapp.net/stickers/", "inline.png"),  # 空檔名的回退
        ]
        
        for url, expected_filename in test_cases:
            virtual_att = VirtualAttachment(url=url)
            assert virtual_att.filename == expected_filename
    
    def test_virtual_attachment_custom_values(self):
        """測試自定義值"""
        url = "https://media.discordapp.net/stickers/test.gif"
        
        virtual_att = VirtualAttachment(
            url=url,
            content_type="image/webp",
            filename="custom.webp"
        )
        
        assert virtual_att.url == url
        assert virtual_att.content_type == "image/webp"
        assert virtual_att.filename == "custom.webp"  # 不會被 __post_init__ 覆蓋
        assert virtual_att._is_virtual == True
    
    def test_virtual_attachment_filename_with_query_params(self):
        """測試帶查詢參數的 URL 檔名提取"""
        url = "https://media.discordapp.net/stickers/test.gif?width=100&height=100"
        
        virtual_att = VirtualAttachment(url=url)
        
        assert virtual_att.filename == "test.gif"  # 應該移除查詢參數
    
    def test_virtual_attachment_content_type_inference(self):
        """測試從 URL 推斷 content_type"""
        test_cases = [
            ("https://example.com/image.png", "image/png"),
            ("https://example.com/photo.jpg", "image/jpeg"),
            ("https://example.com/animation.gif", "image/gif"),
            ("https://example.com/modern.webp", "image/webp"),
            ("https://example.com/bitmap.bmp", "image/bmp"),
            ("https://example.com/vector.svg", "image/svg+xml"),
            ("https://example.com/unknown.xyz", "image/png"),  # 預設值
        ]
        
        for url, expected_content_type in test_cases:
            virtual_att = VirtualAttachment(url=url)
            assert virtual_att.content_type == expected_content_type


class TestPhase7UrlValidation:
    """測試 Phase 7 新增的 URL 驗證功能"""
    
    def test_url_processing_simplified(self):
        """測試簡化的 URL 處理邏輯"""
        # 由於移除了 is_image_url，現在的邏輯是：
        # 1. 只檢查是否為影片格式
        # 2. 非影片格式的 URL 都會嘗試處理
        # 3. 錯誤處理在下載和圖片處理階段進行
        
        # 測試影片 URL 識別仍然有效
        video_urls = [
            "https://example.com/video.mp4",
            "https://example.com/movie.webm",
        ]
        
        for url in video_urls:
            result = is_video_url(url)
            assert result, f"應該識別為影片 URL: {url}"
        
        # 其他格式不在這裡判斷，由後續處理決定
    
    def test_is_video_url(self):
        """測試影片 URL 驗證"""
        test_cases = [
            # 影片格式
            ("https://example.com/video.mp4", True),
            ("https://example.com/movie.avi", True),
            ("https://example.com/clip.mov", True),
            ("https://example.com/stream.webm", True),
            ("https://example.com/recording.mkv", True),
            
            # 帶查詢參數
            ("https://example.com/video.mp4?t=123", True),
            ("https://example.com/movie.webm?quality=hd", True),
            
            # 非影片格式
            ("https://example.com/image.png", False),
            ("https://example.com/document.pdf", False),
            ("https://example.com/audio.mp3", False),
            
            # 無效 URL
            ("not a url", False),
            ("", False),
            (None, False),
        ]
        
        for url, should_match in test_cases:
            result = is_video_url(url)
            if should_match:
                assert result, f"應該匹配影片 URL: {url}"
            else:
                assert not result, f"不應該匹配影片 URL: {url}"
    
    def test_infer_content_type_from_url(self):
        """測試從 URL 推斷 content_type"""
        test_cases = [
            ("https://example.com/image.png", "image/png"),
            ("https://example.com/photo.jpg", "image/jpeg"),
            ("https://example.com/photo.jpeg", "image/jpeg"),
            ("https://example.com/animation.gif", "image/gif"),
            ("https://example.com/modern.webp", "image/webp"),
            ("https://example.com/bitmap.bmp", "image/bmp"),
            ("https://example.com/document.tiff", "image/tiff"),
            ("https://example.com/document.tif", "image/tiff"),
            ("https://example.com/vector.svg", "image/svg+xml"),
            ("https://example.com/unknown.xyz", "image/png"),  # 預設值
            ("", "image/png"),  # 空字串預設值
        ]
        
        for url, expected_content_type in test_cases:
            result = _infer_content_type_from_url(url)
            assert result == expected_content_type, f"URL: {url}, 期望: {expected_content_type}, 實際: {result}"
    
    def test_supported_extensions_constants(self):
        """測試支援的擴展名常數"""
        # 檢查圖片格式常數
        expected_image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif', '.svg'}
        assert SUPPORTED_IMAGE_EXTENSIONS == expected_image_extensions
        
        # 檢查影片格式常數
        expected_video_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v'}
        assert SUPPORTED_VIDEO_EXTENSIONS == expected_video_extensions
    
    def test_is_discord_gif_url_deprecation_warning(self):
        """測試 is_discord_gif_url 的棄用警告"""
        import warnings
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # 調用已棄用的函數
            result = is_discord_gif_url("https://media.discordapp.net/stickers/test.gif")
            
            # 檢查警告
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "已棄用" in str(w[0].message)
            assert "is_image_url()" in str(w[0].message)
            
            # 檢查函數仍然正常工作
            assert result == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 