import re
from typing import Optional

# 匹配一般 YouTube 網址與 youtu.be 短網址，僅抓取第一個影片連結
YOUTUBE_URL_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)(?P<id>[A-Za-zA-Z0-9_-]{11})(?:[?&][^\s]*)?',
    flags=re.IGNORECASE,
)

def extract_first_youtube_url(text: str) -> Optional[str]:
    """從文字中擷取第一個符合的 YouTube 影片 URL。

    Args:
        text: 任意文字

    Returns:
        匹配到的影片 URL，若無則回傳 None。
    """
    if not text:
        return None
    match = YOUTUBE_URL_PATTERN.search(text)
    if not match:
        return None
    video_id = match.group('id')
    return f"https://youtu.be/{video_id}"


def get_video_id(url: str) -> Optional[str]:
    """從網址中擷取影片 ID。若無效則回傳 None"""
    m = YOUTUBE_URL_PATTERN.search(url)
    return m.group('id') if m else None 