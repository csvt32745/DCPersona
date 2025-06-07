#!/usr/bin/env python3
"""
簡單的進度更新測試
"""

import asyncio
import sys
import os

# 添加當前目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_import():
    """測試模組導入"""
    try:
        from agents.tools_and_schemas import DiscordProgressUpdate, ProgressMessageManager
        print("✅ 模組導入成功")
        return True
    except Exception as e:
        print(f"❌ 模組導入失敗: {e}")
        return False

def test_progress_update_creation():
    """測試進度更新物件創建"""
    try:
        from agents.tools_and_schemas import DiscordProgressUpdate
        
        progress = DiscordProgressUpdate(
            stage="test",
            message="測試訊息",
            progress_percentage=50,
            eta_seconds=10
        )
        
        print(f"✅ 進度更新物件創建成功: {progress}")
        return True
    except Exception as e:
        print(f"❌ 進度更新物件創建失敗: {e}")
        return False

def test_progress_manager():
    """測試進度管理器"""
    try:
        from agents.tools_and_schemas import ProgressMessageManager
        
        manager = ProgressMessageManager()
        
        # 測試格式化功能
        from agents.tools_and_schemas import DiscordProgressUpdate
        progress = DiscordProgressUpdate(
            stage="test",
            message="測試訊息",
            progress_percentage=75
        )
        
        formatted = manager._format_progress_content(progress)
        print(f"✅ 進度格式化成功:")
        print(formatted)
        print("-" * 30)
        
        return True
    except Exception as e:
        print(f"❌ 進度管理器測試失敗: {e}")
        return False

def test_progress_bar():
    """測試進度條功能"""
    try:
        from agents.tools_and_schemas import ProgressMessageManager
        
        manager = ProgressMessageManager()
        
        # 測試不同百分比的進度條
        percentages = [0, 25, 50, 75, 100]
        for pct in percentages:
            bar = manager._create_progress_bar(pct)
            print(f"{pct:3d}%: {bar}")
        
        print("✅ 進度條測試成功")
        return True
    except Exception as e:
        print(f"❌ 進度條測試失敗: {e}")
        return False

def test_eta_formatting():
    """測試時間格式化"""
    try:
        from agents.tools_and_schemas import ProgressMessageManager
        
        manager = ProgressMessageManager()
        
        # 測試不同時間的格式化
        times = [5, 65, 3661]  # 5秒, 1分5秒, 1小時1分1秒
        for seconds in times:
            formatted = manager._format_eta(seconds)
            print(f"{seconds}秒 -> {formatted}")
        
        print("✅ 時間格式化測試成功")
        return True
    except Exception as e:
        print(f"❌ 時間格式化測試失敗: {e}")
        return False

def main():
    """主測試函數"""
    print("🚀 開始簡單的進度更新測試")
    
    tests = [
        ("模組導入", test_import),
        ("進度更新物件創建", test_progress_update_creation),
        ("進度管理器", test_progress_manager),
        ("進度條功能", test_progress_bar),
        ("時間格式化", test_eta_formatting),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📝 測試: {test_name}")
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ 測試 {test_name} 發生異常: {e}")
    
    print(f"\n📊 測試結果: {passed}/{total} 通過")
    
    if passed == total:
        print("🎉 所有測試通過！修復成功！")
        return True
    else:
        print("❌ 部分測試失敗")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)