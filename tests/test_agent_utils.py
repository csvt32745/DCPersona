"""
測試 agent_core.agent_utils 模組

此測試檔案測試 Agent 核心輔助函數，包括多模態內容提取和 URL 解析功能。
"""

import pytest
from unittest.mock import Mock
from typing import List, Dict, Any

from agent_core.agent_utils import _extract_text_content, resolve_urls


class TestExtractTextContent:
    """測試 _extract_text_content 函數"""
    
    def test_extract_text_content_string(self):
        """測試字串內容提取"""
        content = "這是一個測試字串"
        result = _extract_text_content(content)
        assert result == "這是一個測試字串"
    
    def test_extract_text_content_empty_string(self):
        """測試空字串"""
        content = ""
        result = _extract_text_content(content)
        assert result == ""
    
    def test_extract_text_content_multimodal_text_only(self):
        """測試僅包含文字的多模態列表"""
        content = [
            {"type": "text", "text": "第一段文字"},
            {"type": "text", "text": "第二段文字"}
        ]
        result = _extract_text_content(content)
        assert result == "第一段文字 第二段文字"
    
    def test_extract_text_content_with_images(self):
        """測試包含圖片的多模態內容"""
        content = [
            {"type": "text", "text": "這是文字"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,xyz"}},
            {"type": "text", "text": "更多文字"}
        ]
        result = _extract_text_content(content)
        assert result == "這是文字 [圖片] 更多文字"
    
    def test_extract_text_content_images_only(self):
        """測試僅包含圖片的內容"""
        content = [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,xyz"}},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,abc"}}
        ]
        result = _extract_text_content(content)
        assert result == "[圖片] [圖片]"
    
    def test_extract_text_content_missing_text_field(self):
        """測試缺少 text 欄位的情況"""
        content = [
            {"type": "text"},  # 缺少 text 欄位
            {"type": "text", "text": "有效文字"}
        ]
        result = _extract_text_content(content)
        assert result == " 有效文字"
    
    def test_extract_text_content_unknown_type(self):
        """測試未知類型的處理"""
        content = [
            {"type": "text", "text": "正常文字"},
            {"type": "unknown", "data": "其他資料"},
            {"type": "text", "text": "更多文字"}
        ]
        result = _extract_text_content(content)
        assert result == "正常文字 更多文字"
    
    def test_extract_text_content_empty_list(self):
        """測試空列表"""
        content = []
        result = _extract_text_content(content)
        assert result == ""
    
    def test_extract_text_content_non_dict_items(self):
        """測試列表中包含非字典項目"""
        content = [
            {"type": "text", "text": "正常文字"},
            "字串項目",  # 非字典項目
            {"type": "text", "text": "更多文字"}
        ]
        result = _extract_text_content(content)
        assert result == "正常文字 更多文字"
    
    def test_extract_text_content_none_input(self):
        """測試 None 輸入"""
        content = None
        result = _extract_text_content(content)
        assert result == "None"
    
    def test_extract_text_content_numeric_input(self):
        """測試數字輸入"""
        content = 123
        result = _extract_text_content(content)
        assert result == "123"


class TestResolveUrls:
    """測試 resolve_urls 函數"""
    
    def test_resolve_urls_empty_chunks(self):
        """測試空的 grounding_chunks"""
        result = resolve_urls([], "task123")
        assert result == {}
    
    def test_resolve_urls_none_chunks(self):
        """測試 None grounding_chunks"""
        result = resolve_urls(None, "task123")
        assert result == {}
    
    def test_resolve_urls_with_web_archive_url(self):
        """測試包含 web_archive_url 的 chunks"""
        mock_chunk1 = Mock()
        mock_chunk1.web_archive_url = "https://web.archive.org/example1"
        mock_chunk1.uri = "https://example1.com"
        
        mock_chunk2 = Mock()
        mock_chunk2.web_archive_url = "https://web.archive.org/example2"
        mock_chunk2.uri = "https://example2.com"
        
        chunks = [mock_chunk1, mock_chunk2]
        result = resolve_urls(chunks, "task456")
        
        expected = {
            "https://web.archive.org/example1": "urltask456_1",
            "https://web.archive.org/example2": "urltask456_2"
        }
        assert result == expected
    
    def test_resolve_urls_with_uri_only(self):
        """測試僅包含 uri 的 chunks"""
        mock_chunk1 = Mock()
        mock_chunk1.web_archive_url = None
        mock_chunk1.uri = "https://example1.com"
        
        mock_chunk2 = Mock()
        # 模擬沒有 web_archive_url 屬性
        del mock_chunk2.web_archive_url
        mock_chunk2.uri = "https://example2.com"
        
        chunks = [mock_chunk1, mock_chunk2]
        result = resolve_urls(chunks, "task789")
        
        expected = {
            "https://example1.com": "urltask789_1",
            "https://example2.com": "urltask789_2"
        }
        assert result == expected
    
    def test_resolve_urls_mixed_url_types(self):
        """測試混合 URL 類型"""
        mock_chunk1 = Mock()
        mock_chunk1.web_archive_url = "https://web.archive.org/example1"
        mock_chunk1.uri = "https://example1.com"
        
        mock_chunk2 = Mock()
        mock_chunk2.web_archive_url = None
        mock_chunk2.uri = "https://example2.com"
        
        mock_chunk3 = Mock()
        # 完全沒有 URL
        mock_chunk3.web_archive_url = None
        mock_chunk3.uri = None
        
        chunks = [mock_chunk1, mock_chunk2, mock_chunk3]
        result = resolve_urls(chunks, "mixed")
        
        expected = {
            "https://web.archive.org/example1": "urlmixed_1",
            "https://example2.com": "urlmixed_2"
        }
        assert result == expected
    
    def test_resolve_urls_no_attributes(self):
        """測試沒有相關屬性的 chunks"""
        mock_chunk = Mock()
        # 移除相關屬性
        del mock_chunk.web_archive_url
        del mock_chunk.uri
        
        chunks = [mock_chunk]
        result = resolve_urls(chunks, "noattr")
        assert result == {}
    
    def test_resolve_urls_empty_urls(self):
        """測試空 URL 值"""
        mock_chunk = Mock()
        mock_chunk.web_archive_url = ""
        mock_chunk.uri = ""
        
        chunks = [mock_chunk]
        result = resolve_urls(chunks, "empty")
        assert result == {}
    
    def test_resolve_urls_task_id_in_result(self):
        """測試 task_id 正確出現在結果中"""
        mock_chunk = Mock()
        mock_chunk.web_archive_url = "https://example.com"
        mock_chunk.uri = "https://backup.com"
        
        chunks = [mock_chunk]
        result = resolve_urls(chunks, "specific_task_123")
        
        # 應該使用 web_archive_url，且包含 task_id
        expected = {
            "https://example.com": "urlspecific_task_123_1"
        }
        assert result == expected
    
    def test_resolve_urls_multiple_chunks_indexing(self):
        """測試多個 chunks 的索引編號"""
        chunks = []
        for i in range(5):
            mock_chunk = Mock()
            mock_chunk.web_archive_url = f"https://example{i}.com"
            mock_chunk.uri = f"https://backup{i}.com"
            chunks.append(mock_chunk)
        
        result = resolve_urls(chunks, "index_test")
        
        # 驗證索引從 1 開始
        for i in range(5):
            expected_key = f"https://example{i}.com"
            expected_value = f"urlindex_test_{i+1}"
            assert result[expected_key] == expected_value