"""
Discord 圖片處理核心模組

提供 Emoji、Sticker 和動畫圖片的統一處理功能，
支援多種格式轉換、動畫幀取樣和 Base64 編碼。
"""

import re
import logging
import aiohttp
import discord
from PIL import Image
from base64 import b64encode
from typing import List, Dict, Any, Union, Optional
from io import BytesIO
from dataclasses import dataclass, field


# 常數定義
CUSTOM_EMOJI_RE = re.compile(r"<a?:\w+:\d+>")
MAX_IMAGE_SIZE = 256  # 預設最大圖片尺寸
DEFAULT_FRAME_LIMIT = 4  # 預設動畫幀數限制

# 支援的圖片格式擴展名
SUPPORTED_IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif', '.svg'
}

# 支援的影片格式擴展名（用於識別和標記）
SUPPORTED_VIDEO_EXTENSIONS = {
    '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v'
}


class ImageProcessingError(Exception):
    """圖片處理異常類別"""
    pass


@dataclass
class VirtualAttachment:
    """虛擬附件物件，模擬 discord.Attachment 介面以複用現有處理邏輯"""
    url: str
    content_type: str = "image/png"
    filename: str = "inline.png"
    
    def __post_init__(self):
        # 只有在使用預設檔名時才從 URL 提取檔名
        if self.filename == "inline.png":
            self.filename = self.url.split('/')[-1].split('?')[0] or "inline.png"
        
        # 如果使用預設 content_type，嘗試從 URL 推斷格式
        if self.content_type == "image/png":
            self.content_type = _infer_content_type_from_url(self.url)
        
    # 標記為虛擬附件，便於後續邏輯識別
    _is_virtual: bool = True


def _infer_content_type_from_url(url: str) -> str:
    """從 URL 推斷 content_type
    
    Args:
        url: 圖片 URL
        
    Returns:
        str: 推斷的 content_type，預設為 "image/png"
    """
    if not url:
        return "image/png"
    
    # 移除查詢參數並轉為小寫
    url_path = url.split('?')[0].lower()
    
    # 根據副檔名推斷 content_type
    if url_path.endswith(('.jpg', '.jpeg')):
        return "image/jpeg"
    elif url_path.endswith('.png'):
        return "image/png"
    elif url_path.endswith('.gif'):
        return "image/gif"
    elif url_path.endswith('.webp'):
        return "image/webp"
    elif url_path.endswith('.bmp'):
        return "image/bmp"
    elif url_path.endswith(('.tiff', '.tif')):
        return "image/tiff"
    elif url_path.endswith('.svg'):
        return "image/svg+xml"
    else:
        return "image/png"  # 預設值



def is_video_url(url: str) -> bool:
    """檢查 URL 是否為影片格式（僅用於識別和標記）
    
    Args:
        url: 要檢查的 URL
        
    Returns:
        bool: 如果是影片 URL 則返回 True
    """
    if not url or not isinstance(url, str):
        return False
    
    # 移除查詢參數並轉為小寫
    url_path = url.split('?')[0].lower()
    
    # 檢查是否為支援的影片格式
    return any(url_path.endswith(ext) for ext in SUPPORTED_VIDEO_EXTENSIONS)


# 保留舊函數以維持向後相容性，但標記為已棄用
def is_discord_gif_url(url: str) -> bool:
    """檢查 URL 是否為 Discord GIF URL
    
    ⚠️ 已棄用：請使用 is_image_url() 替代
    
    Args:
        url: 要檢查的 URL
        
    Returns:
        bool: 如果是 Discord GIF URL 則返回 True
    """
    import warnings
    warnings.warn(
        "is_discord_gif_url() 已棄用，請使用 is_image_url() 替代",
        DeprecationWarning,
        stacklevel=2
    )
    
    if not url or not isinstance(url, str):
        return False
    
    # 檢查域名（保持原有邏輯以維持相容性）
    discord_domains = (
        'https://media.discordapp.net/', 'https://cdn.discordapp.com/',
        'http://media.discordapp.net/', 'http://cdn.discordapp.com/'
    )
    
    if not any(url.startswith(domain) for domain in discord_domains):
        return False
    
    # 檢查是否為 .gif 格式（支援查詢參數）
    url_lower = url.lower()
    return url_lower.endswith('.gif') or '.gif?' in url_lower


async def parse_emoji_from_message(
    message: discord.Message,
    max_emoji_count: int = 3
) -> List[Union[discord.Emoji, discord.PartialEmoji]]:
    """
    從訊息中解析自定義 emoji
    
    Args:
        message: Discord 訊息物件
        max_emoji_count: 最大 emoji 處理數量
        
    Returns:
        List[Union[discord.Emoji, discord.PartialEmoji]]: 解析出的 emoji 列表
        
    Raises:
        ImageProcessingError: 解析失敗時拋出
    """
    try:
        # 使用正規表達式找出所有自定義 emoji
        raw_emojis = CUSTOM_EMOJI_RE.findall(message.content)
        raw_emojis = list(set(raw_emojis))  # 去重複
        
        # 限制處理數量
        if len(raw_emojis) > max_emoji_count:
            logging.warning(f"訊息中有 {len(raw_emojis)} 個 emoji，僅處理前 {max_emoji_count} 個")
            raw_emojis = raw_emojis[:max_emoji_count]
        
        emoji_objects = []
        for raw_emoji in raw_emojis:
            try:
                # 轉換為 PartialEmoji
                partial_emoji = discord.PartialEmoji.from_str(raw_emoji)
                
                if partial_emoji.is_custom_emoji():
                    # 嘗試從 guild 獲取完整的 emoji 物件
                    if message.guild:
                        full_emoji = message.guild.get_emoji(partial_emoji.id)
                        emoji_objects.append(full_emoji or partial_emoji)
                    else:
                        emoji_objects.append(partial_emoji)
                        
            except Exception as e:
                logging.warning(f"無法解析 emoji {raw_emoji}: {e}")
                continue
        
        return emoji_objects
        
    except Exception as e:
        logging.error(f"解析 emoji 時發生錯誤: {e}")
        # 如果完全無法解析，返回空列表而不是拋出異常
        return []


async def load_from_discord_emoji_sticker(
    media_obj: Union[discord.Emoji, discord.PartialEmoji, discord.Sticker],
    frame_limit: int = DEFAULT_FRAME_LIMIT
) -> tuple[list[Image.Image], bool]:
    """
    統一載入 Discord emoji 或 sticker 圖片
    
    Args:
        media_obj: Discord 媒體物件 (Emoji, PartialEmoji, 或 Sticker)
        frame_limit: 動畫幀數限制
        
    Returns:
        tuple[list[Image.Image], bool]: 載入的圖片列表和是否為動畫的標誌
        
    Raises:
        ImageProcessingError: 載入失敗時拋出
    """
    try:
        img_bytes = None
        
        # 根據不同類型載入圖片數據
        # 檢查類型時使用字串名稱以支援 Mock 測試
        media_type = type(media_obj).__name__
        
        if media_type == 'Sticker' or hasattr(media_obj, 'read'):
            try:
                # 優先使用 sticker.read() 方法
                img_bytes = await media_obj.read()
            except Exception as e:
                logging.debug(f"sticker.read() 失敗，使用 URL 下載: {e}")
                # 回退到 URL 下載
                async with aiohttp.ClientSession() as session:
                    async with session.get(media_obj.url) as resp:
                        if resp.status == 200:
                            img_bytes = await resp.read()
                        else:
                            raise ImageProcessingError(f"下載 sticker 失敗，狀態碼: {resp.status}")
                            
        elif media_type in ('Emoji', 'PartialEmoji') or hasattr(media_obj, 'url'):
            # 對於 emoji，直接使用 URL 下載
            async with aiohttp.ClientSession() as session:
                async with session.get(media_obj.url) as resp:
                    if resp.status == 200:
                        img_bytes = await resp.read()
                    else:
                        raise ImageProcessingError(f"下載 emoji 失敗，狀態碼: {resp.status}")
        else:
            raise ImageProcessingError(f"不支援的媒體物件類型: {type(media_obj)}")
        
        if not img_bytes:
            raise ImageProcessingError("載入的圖片數據為空")
        
        # 載入圖片
        img = Image.open(BytesIO(img_bytes))
        
        # 處理動畫
        return sample_animated_frames(img, frame_limit)
        
    except Exception as e:
        if isinstance(e, ImageProcessingError):
            raise
        raise ImageProcessingError(f"載入 Discord 媒體失敗: {e}")


def sample_animated_frames(
    img: Image.Image,
    frame_limit: int = DEFAULT_FRAME_LIMIT
) -> tuple[list[Image.Image], bool]:
    """
    對動畫圖片進行幀取樣
    
    Args:
        img: PIL 圖片物件
        frame_limit: 最大幀數限制
        
    Returns:
        tuple[list[Image.Image], bool]: 取樣後的幀列表和是否為動畫的標誌
        
    Raises:
        ImageProcessingError: 處理失敗時拋出
    """
    try:
        frames = []
        
        # 檢查是否為動畫圖片（兼容不同 PIL 版本）
        is_animated = getattr(img, 'is_animated', False)
        
        if is_animated:
            # 提取所有幀
            try:
                while True:
                    frames.append(img.copy().convert('RGB'))
                    img.seek(img.tell() + 1)
            except EOFError:
                # 到達動畫結尾
                pass
            
            # 均勻取樣幀
            if len(frames) > frame_limit:
                step = len(frames) // frame_limit
                frames = [frames[i * step] for i in range(frame_limit)]
                logging.debug(f"動畫共 {len(frames)} 幀，取樣為 {frame_limit} 幀")
        else:
            # 靜態圖片
            frames = [ensure_rgb_format(img)]
        
        return frames, is_animated
        
    except Exception as e:
        raise ImageProcessingError(f"動畫幀取樣失敗: {e}")


async def process_attachment_image(
    attachment: discord.Attachment,
    frame_limit: int = DEFAULT_FRAME_LIMIT,
    httpx_client = None
) -> tuple[list[Image.Image], bool]:
    """
    處理 Discord 附件圖片（包含動畫支援）
    
    Args:
        attachment: Discord 附件物件
        frame_limit: 動畫幀數限制
        httpx_client: HTTP 客戶端（可選，如果提供則使用，否則使用 aiohttp）
        
    Returns:
        tuple[list[Image.Image], bool]: 處理後的圖片列表和是否為動畫的標誌
        
    Raises:
        ImageProcessingError: 處理失敗時拋出
    """
    try:
        # 檢查是否為圖片附件
        if not attachment.content_type or not attachment.content_type.startswith("image"):
            raise ImageProcessingError(f"附件不是圖片格式: {attachment.content_type}")
        
        img_bytes = None
        
        # 下載附件內容
        if httpx_client:
            # 使用提供的 httpx 客戶端
            try:
                response = await httpx_client.get(attachment.url)
                if response.status_code == 200:
                    img_bytes = response.content
                else:
                    raise ImageProcessingError(f"下載附件失敗，狀態碼: {response.status_code}")
            except Exception as e:
                raise ImageProcessingError(f"使用 httpx 下載附件失敗: {e}")
        else:
            # 使用 aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    if resp.status == 200:
                        img_bytes = await resp.read()
                    else:
                        raise ImageProcessingError(f"下載附件失敗，狀態碼: {resp.status}")
        
        if not img_bytes:
            raise ImageProcessingError("下載的附件內容為空")
        
        # 載入圖片
        img = Image.open(BytesIO(img_bytes))
        
        # 處理動畫
        return sample_animated_frames(img, frame_limit)
        
    except Exception as e:
        if isinstance(e, ImageProcessingError):
            raise
        raise ImageProcessingError(f"處理附件圖片失敗: {e}")


def ensure_rgb_format(img: Image.Image) -> Image.Image:
    """
    確保圖片為 RGB 格式
    
    Args:
        img: PIL 圖片物件
        
    Returns:
        Image.Image: RGB 格式的圖片
        
    Raises:
        ImageProcessingError: 轉換失敗時拋出
    """
    try:
        if img.mode != 'RGB':
            return img.convert('RGB')
        return img
    except Exception as e:
        raise ImageProcessingError(f"轉換 RGB 格式失敗: {e}")


def resize_image(
    img: Image.Image,
    max_size: int = MAX_IMAGE_SIZE
) -> Image.Image:
    """
    調整圖片大小（等比例縮放）
    
    Args:
        img: PIL 圖片物件
        max_size: 最大尺寸（寬或高的最大值）
        
    Returns:
        Image.Image: 調整大小後的圖片
        
    Raises:
        ImageProcessingError: 調整失敗時拋出
    """
    try:
        # 確保 RGB 格式
        img = ensure_rgb_format(img)
        
        # 檢查是否需要縮放
        if img.width <= max_size and img.height <= max_size:
            return img
        
        # 計算縮放比例
        scale = max_size / max(img.width, img.height)
        new_size = (int(img.width * scale), int(img.height * scale))
        
        # 調整大小
        return img.resize(new_size, Image.LANCZOS)
        
    except Exception as e:
        if isinstance(e, ImageProcessingError):
            raise
        raise ImageProcessingError(f"調整圖片大小失敗: {e}")


def convert_images_to_base64_dict(
    images: List[Image.Image],
    image_format: str = "PNG"
) -> List[Dict[str, Any]]:
    """
    將圖片列表轉換為 Discord 訊息格式的 Base64 字典列表
    
    Args:
        images: PIL 圖片列表
        image_format: 圖片格式（PNG, JPEG 等）
        
    Returns:
        List[Dict[str, Any]]: Discord 訊息格式的圖片字典列表
        
    Raises:
        ImageProcessingError: 轉換失敗時拋出
    """
    try:
        result = []
        
        for i, img in enumerate(images):
            # 轉換為 Base64
            buffer = BytesIO()
            img.save(buffer, format=image_format)
            img_base64 = b64encode(buffer.getvalue()).decode('utf-8')
            
            # 構建 Discord 格式
            image_data = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/{image_format.lower()};base64,{img_base64}"
                }
            }
            result.append(image_data)
            
            logging.debug(f"轉換第 {i+1} 張圖片為 Base64，大小: {len(img_base64)} 字元")
        
        return result
        
    except Exception as e:
        raise ImageProcessingError(f"轉換圖片為 Base64 失敗: {e}") 