"""
測試 utils.common_utils 模組

此測試檔案測試通用工具函數，包括提示詞讀取和隨機提示詞選擇功能。
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, mock_open
import logging

from utils.common_utils import get_prompt, random_system_prompt, ROOT_PROMPT_DIR


class TestGetPrompt:
    """測試 get_prompt 函數"""
    
    def test_get_prompt_success(self, tmp_path):
        """測試成功讀取提示詞檔案"""
        # 創建測試檔案
        test_file = tmp_path / "test_prompt.txt"
        test_content = "這是一個測試提示詞\n包含多行內容"
        test_file.write_text(test_content, encoding="utf-8")
        
        result = get_prompt(test_file)
        assert result == test_content
    
    def test_get_prompt_with_pathlib_path(self, tmp_path):
        """測試使用 Path 物件讀取檔案"""
        test_file = tmp_path / "pathlib_test.txt"
        test_content = "使用 Path 物件的測試"
        test_file.write_text(test_content, encoding="utf-8")
        
        result = get_prompt(Path(test_file))
        assert result == test_content
    
    def test_get_prompt_file_not_found(self, caplog):
        """測試檔案不存在的錯誤處理"""
        non_existent_file = "non_existent_file.txt"
        
        with caplog.at_level(logging.ERROR):
            result = get_prompt(non_existent_file)
        
        assert result == ""
        assert "Failed to load prompt from" in caplog.text
        assert non_existent_file in caplog.text
    
    def test_get_prompt_permission_error(self, tmp_path, caplog):
        """測試權限錯誤處理"""
        test_file = tmp_path / "permission_test.txt"
        test_file.write_text("test content")
        
        # Mock open 來模擬權限錯誤
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with caplog.at_level(logging.ERROR):
                result = get_prompt(test_file)
        
        assert result == ""
        assert "Failed to load prompt from" in caplog.text
    
    def test_get_prompt_empty_file(self, tmp_path):
        """測試空檔案"""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("", encoding="utf-8")
        
        result = get_prompt(test_file)
        assert result == ""
    
    def test_get_prompt_unicode_content(self, tmp_path):
        """測試包含 Unicode 字元的檔案"""
        test_file = tmp_path / "unicode.txt"
        test_content = "測試中文字元 🚀 和表情符號"
        test_file.write_text(test_content, encoding="utf-8")
        
        result = get_prompt(test_file)
        assert result == test_content
    
    def test_get_prompt_large_file(self, tmp_path):
        """測試大檔案讀取"""
        test_file = tmp_path / "large.txt"
        # 創建一個較大的檔案內容
        large_content = "重複內容 " * 1000
        test_file.write_text(large_content, encoding="utf-8")
        
        result = get_prompt(test_file)
        assert result == large_content


class TestRandomSystemPrompt:
    """測試 random_system_prompt 函數"""
    
    def test_random_system_prompt_success(self, tmp_path):
        """測試成功隨機選擇提示詞"""
        # 創建測試目錄和檔案
        prompt_dir = tmp_path / "test_persona"
        prompt_dir.mkdir()
        
        # 創建多個測試檔案
        prompts = {
            "friendly.txt": "友善的提示詞",
            "professional.txt": "專業的提示詞",
            "casual.txt": "隨意的提示詞"
        }
        
        for filename, content in prompts.items():
            (prompt_dir / filename).write_text(content, encoding="utf-8")
        
        # 多次調用確保隨機選擇正常工作
        results = set()
        for _ in range(10):
            result = random_system_prompt(prompt_dir)
            results.add(result)
            assert result in prompts.values()
        
        # 確保至少選中了一個檔案（由於隨機性，不保證全選中）
        assert len(results) >= 1
    
    def test_random_system_prompt_single_file(self, tmp_path):
        """測試只有一個檔案的情況"""
        prompt_dir = tmp_path / "single_file"
        prompt_dir.mkdir()
        
        test_file = prompt_dir / "only.txt"
        test_content = "唯一的提示詞"
        test_file.write_text(test_content, encoding="utf-8")
        
        result = random_system_prompt(prompt_dir)
        assert result == test_content
    
    def test_random_system_prompt_empty_directory(self, tmp_path, caplog):
        """測試空目錄"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        with caplog.at_level(logging.WARNING):
            result = random_system_prompt(empty_dir)
        
        assert result == ""
        assert "No prompt files found" in caplog.text
    
    def test_random_system_prompt_nonexistent_directory(self, caplog):
        """測試不存在的目錄"""
        non_existent_dir = "non_existent_directory"
        
        with caplog.at_level(logging.WARNING):
            result = random_system_prompt(non_existent_dir)
        
        assert result == ""
        assert "No prompt files found" in caplog.text
    
    def test_random_system_prompt_default_directory(self, tmp_path):
        """測試使用預設目錄"""
        # Mock Path.glob 來避免依賴實際的 persona 目錄
        with patch("utils.common_utils.Path") as mock_path:
            mock_path_instance = mock_path.return_value
            mock_path_instance.glob.return_value = []
            
            with patch("utils.common_utils.logging.warning") as mock_warning:
                result = random_system_prompt()
            
            assert result == ""
            mock_path.assert_called_with(ROOT_PROMPT_DIR)
            mock_warning.assert_called_once()
    
    def test_random_system_prompt_with_non_txt_files(self, tmp_path):
        """測試包含非 .txt 檔案的目錄"""
        prompt_dir = tmp_path / "mixed_files"
        prompt_dir.mkdir()
        
        # 創建 .txt 檔案
        (prompt_dir / "valid1.txt").write_text("有效提示詞1", encoding="utf-8")
        (prompt_dir / "valid2.txt").write_text("有效提示詞2", encoding="utf-8")
        
        # 創建非 .txt 檔案
        (prompt_dir / "invalid.md").write_text("Markdown 檔案", encoding="utf-8")
        (prompt_dir / "config.json").write_text('{"config": true}', encoding="utf-8")
        
        # 多次測試確保只選擇 .txt 檔案
        valid_prompts = {"有效提示詞1", "有效提示詞2"}
        for _ in range(10):
            result = random_system_prompt(prompt_dir)
            assert result in valid_prompts
    
    def test_random_system_prompt_with_subdirectories(self, tmp_path):
        """測試包含子目錄的情況"""
        prompt_dir = tmp_path / "with_subdirs"
        prompt_dir.mkdir()
        
        # 在根目錄創建檔案
        (prompt_dir / "root_prompt.txt").write_text("根目錄提示詞", encoding="utf-8")
        
        # 創建子目錄和檔案
        sub_dir = prompt_dir / "subdir"
        sub_dir.mkdir()
        (sub_dir / "sub_prompt.txt").write_text("子目錄提示詞", encoding="utf-8")
        
        # glob("*.txt") 應該只匹配根目錄的檔案
        result = random_system_prompt(prompt_dir)
        assert result == "根目錄提示詞"
    
    def test_random_system_prompt_file_read_error(self, tmp_path, caplog):
        """測試檔案讀取錯誤"""
        prompt_dir = tmp_path / "read_error"
        prompt_dir.mkdir()
        
        # 創建一個檔案
        test_file = prompt_dir / "test.txt"
        test_file.write_text("測試內容", encoding="utf-8")
        
        # Mock get_prompt 來模擬讀取錯誤
        with patch("utils.common_utils.get_prompt", return_value=""):
            with caplog.at_level(logging.INFO):
                result = random_system_prompt(prompt_dir)
        
        assert result == ""
        assert "Random Select test" in caplog.text
    
    def test_random_system_prompt_string_path(self, tmp_path):
        """測試使用字串路徑"""
        prompt_dir = tmp_path / "string_path"
        prompt_dir.mkdir()
        
        test_file = prompt_dir / "string_test.txt"
        test_content = "字串路徑測試"
        test_file.write_text(test_content, encoding="utf-8")
        
        result = random_system_prompt(str(prompt_dir))
        assert result == test_content