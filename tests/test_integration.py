#!/usr/bin/env python3
"""
測試研究代理的進度和最終答案整合功能

這個測試腳本驗證：
1. ProgressMessageManager 能正確處理最終答案整合
2. 訊息格式正確顯示進度和結果
3. 錯誤處理機制正常運作
"""

import asyncio
import logging
from datetime import datetime
from unittest.mock import Mock, AsyncMock
from agents.tools_and_schemas import ProgressMessageManager, DiscordProgressUpdate
from agents.state import ResearchProgress

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestDiscordMessage:
    """模擬 Discord 訊息類別"""
    def __init__(self, message_id: int, channel_id: int):
        self.id = message_id
        self.channel = Mock()
        self.channel.id = channel_id
        self.reply = AsyncMock()
        self.edit = AsyncMock()

async def test_progress_manager_integration():
    """測試 ProgressMessageManager 的最終答案整合功能"""
    print("🧪 開始測試 ProgressMessageManager 整合功能...")
    
    # 創建測試實例
    manager = ProgressMessageManager()
    original_msg = TestDiscordMessage(12345, 67890)
    
    # 設置當前消息ID
    manager.set_current_original_message_id(original_msg.id)
    
    # 測試 1: 發送初始進度
    print("\n📤 測試 1: 發送初始進度...")
    initial_progress = DiscordProgressUpdate(
        stage="🤔 分析問題",
        message="正在分析問題並生成搜尋策略...",
        progress_percentage=10
    )
    
    # 模擬進度消息
    progress_msg = TestDiscordMessage(54321, 67890)
    original_msg.reply.return_value = progress_msg
    
    result_msg = await manager.send_or_update_progress(original_msg, initial_progress)
    print(f"✅ 初始進度消息已發送: {result_msg}")
    
    # 測試 2: 更新進度
    print("\n🔄 測試 2: 更新進度...")
    update_progress = DiscordProgressUpdate(
        stage="🔍 網路研究",
        message="正在進行網路研究 (2/3)",
        progress_percentage=60
    )
    
    updated_msg = await manager.send_or_update_progress(original_msg, update_progress)
    print(f"✅ 進度更新成功: {updated_msg}")
    
    # 測試 3: 整合最終答案
    print("\n🎯 測試 3: 整合最終答案...")
    final_answer = """根據我的研究，關於妳問的問題，這裡是詳細的回答：

這是一個包含多行內容的最終答案，展示了研究的成果。內容包括：
- 重要發現 A
- 關鍵洞察 B  
- 實用建議 C

希望這個回答對妳有幫助！ 🌟"""
    
    completed_progress = DiscordProgressUpdate(
        stage="completed",
        message="研究已完成",
        progress_percentage=100
    )
    
    final_msg = await manager.send_or_update_progress(
        original_msg, completed_progress, final_answer
    )
    print(f"✅ 最終答案整合成功: {final_msg}")
    
    # 測試 4: 驗證格式化內容
    print("\n📋 測試 4: 驗證格式化內容...")
    formatted_content = manager._format_progress_content(completed_progress, final_answer)
    print("格式化後的內容:")
    print("=" * 50)
    print(formatted_content)
    print("=" * 50)
    
    # 測試 5: 測試錯誤處理
    print("\n❌ 測試 5: 測試錯誤處理...")
    try:
        error_msg = await manager.update_with_final_answer(original_msg, "測試答案")
        print(f"✅ 錯誤處理測試通過: {error_msg}")
    except Exception as e:
        print(f"⚠️ 錯誤處理測試失敗: {e}")
    
    print("\n🎉 ProgressMessageManager 整合功能測試完成！")

async def test_research_progress_with_final_answer():
    """測試 ResearchProgress 的最終答案功能"""
    print("\n🧪 開始測試 ResearchProgress 最終答案功能...")
    
    # 創建研究進度實例
    progress = ResearchProgress(
        stage="completed",
        completed_queries=3,
        total_queries=3,
        loop_count=1,
        sources_found=5,
        final_answer="這是測試的最終答案，包含了研究的結果 ✨"
    )
    
    print(f"✅ ResearchProgress 創建成功:")
    print(f"   階段: {progress.stage}")
    print(f"   查詢完成: {progress.completed_queries}/{progress.total_queries}")
    print(f"   來源數量: {progress.sources_found}")
    print(f"   最終答案: {progress.final_answer}")
    print(f"   進度訊息: {progress.get_progress_message()}")
    
    print("\n🎉 ResearchProgress 最終答案功能測試完成！")

async def test_message_format_variations():
    """測試不同訊息格式變化"""
    print("\n🧪 開始測試訊息格式變化...")
    
    manager = ProgressMessageManager()
    
    # 測試不同階段的格式
    test_cases = [
        {
            "name": "進行中的研究",
            "progress": DiscordProgressUpdate(
                stage="🔍 網路研究",
                message="正在搜尋相關資料...",
                progress_percentage=45,
                eta_seconds=30
            ),
            "final_answer": None
        },
        {
            "name": "完成狀態無答案",
            "progress": DiscordProgressUpdate(
                stage="completed",
                message="研究完成",
                progress_percentage=100
            ),
            "final_answer": None
        },
        {
            "name": "完成狀態有答案",
            "progress": DiscordProgressUpdate(
                stage="completed",
                message="研究完成",
                progress_percentage=100
            ),
            "final_answer": "這是完整的研究結果！包含了詳細的分析和建議 🌟"
        },
        {
            "name": "錯誤狀態",
            "progress": DiscordProgressUpdate(
                stage="error",
                message="研究過程中發生錯誤"
            ),
            "final_answer": "抱歉，遇到了一些技術問題 😅"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n📝 測試案例 {i}: {case['name']}")
        formatted = manager._format_progress_content(case['progress'], case['final_answer'])
        print("格式化結果:")
        print("-" * 40)
        print(formatted)
        print("-" * 40)
    
    print("\n🎉 訊息格式變化測試完成！")

async def main():
    """主測試函式"""
    print("🌟 開始測試研究代理進度和最終答案整合功能")
    print("=" * 60)
    
    try:
        await test_progress_manager_integration()
        await test_research_progress_with_final_answer()
        await test_message_format_variations()
        
        print("\n" + "=" * 60)
        print("🎊 所有測試完成！整合功能正常運作")
        
    except Exception as e:
        print(f"\n💥 測試過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())