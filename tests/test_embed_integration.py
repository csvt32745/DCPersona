#!/usr/bin/env python3
"""
Research Agent Embed 整合測試

測試 research agent 的新 embed 格式是否與傳統 LLM 處理保持一致。
"""

import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch
import discord
from agents.tools_and_schemas import DiscordProgressUpdate, DiscordTools, EMBED_COLOR_COMPLETE, EMBED_COLOR_INCOMPLETE
from agents.research_agent import ResearchAgent
from agents.configuration import AgentConfiguration
from agents.state import DiscordContext, ResearchProgress

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
        self.guild = Mock()
        self.guild.id = 98765
        self.embeds = []
        self.content = ""
    
    async def reply(self, content: str = None, embed=None, mention_author: bool = False):
        """模擬回覆消息"""
        reply_msg = MockDiscordMessage(self.channel.id, self.id + 1)
        if content:
            reply_msg.content = content
            logger.info(f"📝 發送文字回覆: {content[:100]}...")
        if embed:
            reply_msg.embeds = [embed]
            logger.info(f"🎨 發送 Embed 回覆: 顏色={embed.color}, 描述長度={len(embed.description or '')}")
            if embed.fields:
                logger.info(f"   📚 包含 {len(embed.fields)} 個欄位")
        return reply_msg
    
    async def edit(self, content: str = None, embed=None):
        """模擬編輯消息"""
        if content:
            self.content = content
            logger.info(f"✏️ 編輯文字內容: {content[:100]}...")
        if embed:
            self.embeds = [embed]
            logger.info(f"🎨 編輯 Embed: 顏色={embed.color}, 描述長度={len(embed.description or '')}")
            if embed.fields:
                logger.info(f"   📚 包含 {len(embed.fields)} 個欄位")
        return self


async def test_embed_color_consistency():
    """測試 embed 顏色與 postprocess.py 的一致性"""
    logger.info("🧪 測試 embed 顏色一致性...")
    
    # 從 postprocess.py 導入顏色常數
    from pipeline.postprocess import EMBED_COLOR_COMPLETE as POST_COMPLETE
    from pipeline.postprocess import EMBED_COLOR_INCOMPLETE as POST_INCOMPLETE
    
    # 檢查顏色一致性
    assert EMBED_COLOR_COMPLETE.value == POST_COMPLETE.value, "完成狀態顏色應該一致"
    assert EMBED_COLOR_INCOMPLETE.value == POST_INCOMPLETE.value, "未完成狀態顏色應該一致"
    
    logger.info(f"✅ 顏色一致性驗證通過:")
    logger.info(f"   完成狀態: {EMBED_COLOR_COMPLETE.value} (深綠色)")
    logger.info(f"   未完成狀態: {EMBED_COLOR_INCOMPLETE.value} (橘色)")


async def test_research_agent_embed_format():
    """測試 research agent 的 embed 格式"""
    logger.info("🧪 測試 research agent embed 格式...")
    
    # 創建模擬消息和進度
    original_msg = MockDiscordMessage(channel_id=12345)
    
    # 模擬研究完成的情況
    final_answer = """根據我的深入研究，關於「人工智慧的未來發展」，我發現了以下重要趨勢：

🔮 **主要發展方向：**
1. **AGI (通用人工智慧)** - 朝向更接近人類智能的系統發展
2. **多模態 AI** - 整合視覺、語言、音訊等多種感知能力
3. **個人化助手** - 根據個人需求客製化的 AI 服務

💡 **技術突破：**
- 更強的推理與規劃能力
- 更好的常識理解
- 更高效的學習機制

這些發展將在未來 5-10 年內深刻改變我們的工作和生活方式 ✨"""

    # 模擬來源資訊
    sources = [
        {
            "label": "MIT Technology Review: AI 發展報告 2024",
            "value": "https://www.technologyreview.com/ai-trends-2024",
            "title": "AI 發展報告 2024"
        },
        {
            "label": "OpenAI 研究論文: GPT-4 與未來發展",
            "value": "https://openai.com/research/gpt4-future",
            "title": "GPT-4 與未來發展"
        },
        {
            "label": "Nature: 人工智慧的社會影響研究",
            "value": "https://nature.com/articles/ai-social-impact",
            "title": "人工智慧的社會影響研究"
        }
    ]
    
    # 測試完成狀態的 embed
    completed_progress = DiscordProgressUpdate(
        stage="completed",
        message="🎯 研究完成！已找到 3 個權威來源",
        progress_percentage=100
    )
    
    logger.info("📊 發送完成狀態的 research agent embed...")
    result_msg = await DiscordTools.send_progress_update(
        original_msg,
        completed_progress,
        edit_previous=False,
        final_answer=final_answer,
        sources=sources
    )
    
    assert result_msg is not None, "應該成功創建最終答案 embed"
    logger.info("✅ Research agent embed 格式測試完成")
    
    # 測試進行中狀態的 embed
    logger.info("📊 發送進行中狀態的 research agent embed...")
    progress_update = DiscordProgressUpdate(
        stage="web_research",
        message="🔍 正在搜尋相關資料...",
        progress_percentage=65,
        eta_seconds=12
    )
    
    result_msg2 = await DiscordTools.send_progress_update(
        original_msg,
        progress_update,
        edit_previous=False
    )
    
    assert result_msg2 is not None, "應該成功創建進度 embed"
    logger.info("✅ Research agent 進度 embed 測試完成")


async def test_embed_structure_consistency():
    """測試 embed 結構與傳統 LLM 處理的一致性"""
    logger.info("🧪 測試 embed 結構一致性...")
    
    # 模擬傳統 LLM 的 embed 格式（參考 postprocess.py）
    traditional_embed = discord.Embed(
        description="這是傳統 LLM 處理的回應內容...",
        color=EMBED_COLOR_COMPLETE
    )
    
    # 模擬 research agent 的 embed 格式
    from agents.tools_and_schemas import ProgressMessageManager
    manager = ProgressMessageManager()
    
    final_answer = "這是 research agent 的最終答案..."
    sources = [{"label": "測試來源", "value": "https://example.com"}]
    
    completed_progress = DiscordProgressUpdate(
        stage="completed",
        message="研究完成",
        progress_percentage=100
    )
    
    research_embed = manager._create_progress_embed(
        completed_progress, 
        final_answer, 
        sources
    )
    
    # 檢查結構一致性
    assert research_embed is not None, "Research agent 應該產生有效的 embed"
    assert hasattr(research_embed, 'description'), "應該有 description 屬性"
    assert hasattr(research_embed, 'color'), "應該有 color 屬性"
    assert research_embed.color == EMBED_COLOR_COMPLETE, "顏色應該與完成狀態一致"
    
    logger.info("✅ Embed 結構一致性驗證通過")


async def test_source_formatting():
    """測試來源資訊格式化"""
    logger.info("🧪 測試來源資訊格式化...")
    
    from agents.tools_and_schemas import ProgressMessageManager
    manager = ProgressMessageManager()
    
    # 測試不同數量的來源
    test_cases = [
        {
            "name": "無來源",
            "sources": [],
            "expected_empty": True
        },
        {
            "name": "單一來源",
            "sources": [
                {"label": "Wikipedia", "value": "https://wikipedia.org"}
            ],
            "expected_empty": False
        },
        {
            "name": "多個來源",
            "sources": [
                {"label": "研究論文 A", "value": "https://paper-a.com"},
                {"label": "新聞報導 B", "value": "https://news-b.com"},
                {"label": "官方文件 C", "value": "https://official-c.gov"},
                {"label": "額外來源 D", "value": "https://extra-d.com"}  # 應該被截斷
            ],
            "expected_empty": False
        }
    ]
    
    for case in test_cases:
        logger.info(f"   測試案例: {case['name']}")
        formatted = manager._format_sources_for_embed(case["sources"])
        
        if case["expected_empty"]:
            assert formatted == "", f"{case['name']} 應該返回空字串"
        else:
            assert formatted != "", f"{case['name']} 應該返回非空字串"
            assert "1." in formatted, f"{case['name']} 應該包含編號"
        
        logger.info(f"      結果: {formatted}")
    
    logger.info("✅ 來源資訊格式化測試完成")


async def main():
    """主測試函數"""
    logger.info("🚀 開始 Research Agent Embed 整合測試")
    logger.info("=" * 60)
    
    try:
        await test_embed_color_consistency()
        logger.info("-" * 40)
        
        await test_research_agent_embed_format()
        logger.info("-" * 40)
        
        await test_embed_structure_consistency()
        logger.info("-" * 40)
        
        await test_source_formatting()
        logger.info("-" * 40)
        
        logger.info("🎉 所有整合測試通過！")
        logger.info("✨ Research Agent 現在與傳統 LLM 處理使用一致的 embed 風格")
        
    except Exception as e:
        logger.error(f"❌ 整合測試失敗: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())