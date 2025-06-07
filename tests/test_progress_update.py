#!/usr/bin/env python3
"""
Discord 進度更新機制測試腳本

用於驗證修復後的進度更新功能是否正常工作。
"""

import asyncio
import logging
from unittest.mock import Mock, AsyncMock
from agents.tools_and_schemas import DiscordProgressUpdate, DiscordTools, ProgressMessageManager

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockDiscordMessage:
    """模擬 Discord 消息物件"""
    
    def __init__(self, channel_id: int = 12345, message_id: int = None):
        self.id = message_id or (channel_id * 1000 + hash(str(channel_id)) % 1000)
        self.channel = Mock()
        self.channel.id = channel_id
        self.author = Mock()
        self.author.id = 67890
        self.reply = AsyncMock()
        self.edit = AsyncMock()
        self.embeds = []
    
    async def reply(self, content: str = None, embed=None, mention_author: bool = False):
        """模擬回覆消息"""
        reply_msg = MockDiscordMessage(self.channel.id, self.id + 1)
        if content:
            reply_msg.content = content
            logger.info(f"發送回覆: {content}")
        if embed:
            reply_msg.embeds = [embed]
            logger.info(f"發送 Embed 回覆: {embed.description[:100] if embed.description else 'No description'}...")
        return reply_msg
    
    async def edit(self, content: str = None, embed=None):
        """模擬編輯消息"""
        if content:
            self.content = content
            logger.info(f"編輯消息: {content}")
        if embed:
            self.embeds = [embed]
            logger.info(f"編輯 Embed: {embed.description[:100] if embed.description else 'No description'}...")
        return self


async def test_progress_manager():
    """測試進度消息管理器"""
    logger.info("🧪 開始測試進度消息管理器...")
    
    # 創建模擬消息
    original_msg = MockDiscordMessage(channel_id=12345)
    
    # 測試進度更新序列
    progress_updates = [
        DiscordProgressUpdate(
            stage="generate_query",
            message="正在分析問題並生成搜尋策略...",
            progress_percentage=10
        ),
        DiscordProgressUpdate(
            stage="web_research",
            message="正在進行網路研究",
            progress_percentage=40,
            eta_seconds=15
        ),
        DiscordProgressUpdate(
            stage="reflection",
            message="正在分析結果並評估資訊完整性...",
            progress_percentage=70,
            eta_seconds=8
        ),
        DiscordProgressUpdate(
            stage="finalize_answer",
            message="正在整理最終答案...",
            progress_percentage=90,
            eta_seconds=3
        ),
        DiscordProgressUpdate(
            stage="completed",
            message="研究完成！",
            progress_percentage=100
        )
    ]
    
    logger.info("📝 測試進度更新序列...")
    progress_msg = None
    
    for i, progress in enumerate(progress_updates):
        logger.info(f"步驟 {i+1}: {progress.stage}")
        
        # 發送進度更新
        result_msg = await DiscordTools.send_progress_update(
            original_msg, progress, edit_previous=True
        )
        
        if i == 0:
            # 第一次應該創建新消息
            progress_msg = result_msg
            assert result_msg is not None, "第一次進度更新應該創建新消息"
        else:
            # 後續應該編輯同一條消息
            assert result_msg == progress_msg, "後續進度更新應該編輯同一條消息"
        
        # 模擬處理延遲
        await asyncio.sleep(0.1)
    
    logger.info("✅ 進度更新序列測試完成")
    
    # 測試統計功能
    stats = DiscordTools.get_progress_manager_stats()
    logger.info(f"📊 進度管理器統計: {stats}")
    
    # 測試清理功能
    logger.info("🧹 測試清理功能...")
    DiscordTools.cleanup_progress_messages(12345)
    
    stats_after_cleanup = DiscordTools.get_progress_manager_stats()
    logger.info(f"📊 清理後統計: {stats_after_cleanup}")
    
    logger.info("✅ 進度消息管理器測試完成")


async def test_progress_formatting():
    """測試進度格式化功能"""
    logger.info("🧪 開始測試進度格式化...")
    
    manager = ProgressMessageManager()
    
    # 測試不同的進度格式
    test_cases = [
        {
            "stage": "generate_query",
            "message": "正在分析問題",
            "progress_percentage": None,
            "eta_seconds": None
        },
        {
            "stage": "web_research",
            "message": "正在搜尋",
            "progress_percentage": 50,
            "eta_seconds": None
        },
        {
            "stage": "reflection",
            "message": "正在分析",
            "progress_percentage": 75,
            "eta_seconds": 10
        },
        {
            "stage": "completed",
            "message": "完成",
            "progress_percentage": 100,
            "eta_seconds": 0
        }
    ]
    
    for i, case in enumerate(test_cases):
        progress = DiscordProgressUpdate(**case)
        formatted = manager._format_progress_content(progress)
        logger.info(f"測試案例 {i+1}:")
        logger.info(f"輸入: {case}")
        logger.info(f"格式化結果:\n{formatted}")
        logger.info("-" * 50)
    
    logger.info("✅ 進度格式化測試完成")


async def test_concurrent_progress():
    """測試併發進度更新"""
    logger.info("🧪 開始測試併發進度更新...")
    
    # 創建多個不同頻道的消息
    channels = [12345, 23456, 34567]
    messages = [MockDiscordMessage(channel_id) for channel_id in channels]
    
    async def update_progress_for_channel(msg, channel_num):
        """為單一頻道更新進度"""
        for i in range(3):
            progress = DiscordProgressUpdate(
                stage=f"step_{i+1}",
                message=f"頻道 {channel_num} - 步驟 {i+1}",
                progress_percentage=(i+1) * 33
            )
            
            await DiscordTools.send_progress_update(msg, progress, edit_previous=True)
            await asyncio.sleep(0.05)  # 模擬處理時間
    
    # 併發執行多個頻道的進度更新
    tasks = [
        update_progress_for_channel(msg, i+1) 
        for i, msg in enumerate(messages)
    ]
    
    await asyncio.gather(*tasks)
    
    # 檢查統計
    stats = DiscordTools.get_progress_manager_stats()
    logger.info(f"📊 併發測試後統計: {stats}")
    
    # 清理所有
    DiscordTools.cleanup_progress_messages()
    
    logger.info("✅ 併發進度更新測試完成")


async def main():
    """主測試函數"""
    logger.info("🚀 開始 Discord 進度更新機制測試")
    
    try:
        await test_progress_manager()
        await test_progress_formatting()
        await test_concurrent_progress()
        await test_embed_formatting()
        
        logger.info("🎉 所有測試通過！")
        
    except Exception as e:
        logger.error(f"❌ 測試失敗: {str(e)}", exc_info=True)
        raise


async def test_embed_formatting():
    """測試 embed 格式化功能"""
    logger.info("🧪 開始測試 embed 格式化...")
    
    # 創建模擬消息
    original_msg = MockDiscordMessage(channel_id=12345)
    
    # 測試完成狀態的 embed 格式
    final_answer = """根據我的研究，人工智慧在未來將會有以下幾個重要發展趨勢：

1. **更強的推理能力** - AI 系統將具備更好的邏輯推理和問題解決能力
2. **多模態整合** - 能夠同時處理文字、圖像、音訊等多種數據類型
3. **個人化應用** - 根據個人需求提供客製化的 AI 助手服務

這些發展將深刻改變我們的工作和生活方式 ✨"""
    
    # 模擬來源資訊
    sources = [
        {
            "label": "MIT Technology Review - AI 發展趨勢報告",
            "value": "https://example.com/ai-trends-2024",
            "title": "AI 發展趨勢報告"
        },
        {
            "label": "Nature - 人工智慧研究進展",
            "value": "https://example.com/nature-ai-research",
            "title": "人工智慧研究進展"
        },
        {
            "label": "IEEE Spectrum - 未來 AI 技術展望",
            "value": "https://example.com/ieee-ai-future",
            "title": "未來 AI 技術展望"
        }
    ]
    
    # 測試完成狀態的進度更新
    completed_progress = DiscordProgressUpdate(
        stage="completed",
        message="研究完成！",
        progress_percentage=100
    )
    
    logger.info("📝 測試最終答案的 embed 格式...")
    result_msg = await DiscordTools.send_progress_update(
        original_msg,
        completed_progress,
        edit_previous=False,  # 創建新消息以便檢查
        final_answer=final_answer,
        sources=sources
    )
    
    assert result_msg is not None, "應該成功創建最終答案消息"
    logger.info("✅ 最終答案 embed 格式測試完成")
    
    # 測試進度狀態的 embed 格式
    logger.info("📝 測試進度狀態的 embed 格式...")
    progress_update = DiscordProgressUpdate(
        stage="web_research",
        message="正在進行網路研究",
        progress_percentage=60,
        eta_seconds=15
    )
    
    result_msg2 = await DiscordTools.send_progress_update(
        original_msg,
        progress_update,
        edit_previous=False  # 創建新消息以便檢查
    )
    
    assert result_msg2 is not None, "應該成功創建進度消息"
    logger.info("✅ 進度狀態 embed 格式測試完成")
    
    logger.info("✅ Embed 格式化測試完成")


if __name__ == "__main__":
    asyncio.run(main())