"""
/patchnote Slash Command 實作
簡化版更新記錄顯示，移除版本號複雜度，提供簡潔的 Discord 訊息格式。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import discord
from discord import app_commands

from schemas.patchnote_types import load_patchnote_config

if TYPE_CHECKING:
    from discord_bot.client import DCPersonaBot

logger = logging.getLogger(__name__)


@app_commands.command(name="patchnote", description="顯示最新的功能更新記錄")
@app_commands.describe(count="顯示的更新數量 (1-10，預設 5)")
async def patchnote_command(
    interaction: discord.Interaction, count: Optional[int] = 5
):
    """/patchnote Slash Command 處理器"""

    # 透過 interaction.client 取得我們自定義的 Bot 實例
    bot: "DCPersonaBot" = interaction.client  # type: ignore[assignment]

    # 延遲回應（Discord 最多 3 秒內需要收到 ACK）
    try:
        if not interaction.response.is_done():
            await interaction.response.defer()
    except discord.errors.HTTPException as http_exc:
        # 忽略已回應 (40060) 或已失效 (10062) 的互動錯誤
        if getattr(http_exc, "code", None) not in (40060, 10062):
            raise

    try:
        # 1. 驗證參數
        if count is None:
            count = 5
        
        if count < 1 or count > 10:
            error_embed = discord.Embed(
                description="❌ 數量範圍錯誤！請輸入 1-10 之間的數字。",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=error_embed)
            return

        logger.info(f"用戶 {interaction.user} 請求顯示最新 {count} 個更新記錄")

        # 2. 載入 patchnote 配置
        config_path = Path("patchnotes.yaml")
        config = load_patchnote_config(config_path)
        
        if config is None:
            not_found_embed = discord.Embed(
                description=f"❌ 找不到更新記錄檔案或檔案格式錯誤。",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=not_found_embed)
            return

        # 3. 獲取最新更新記錄
        latest_updates = config.get_latest_updates(count)
        
        if not latest_updates:
            empty_embed = discord.Embed(
                description="ℹ️ 目前沒有任何更新記錄。",
                color=discord.Color.blue(),
            )
            await interaction.followup.send(embed=empty_embed)
            return

        # 4. 建立 Embed 回應
        bot_name = bot.user.name
        success_embed = discord.Embed(
            title=f"📝 {bot_name} 更新記錄",
            color=discord.Color.green(),
        )
        
        # 5. 為每個更新新增 field
        for update in latest_updates:
            # 檢查是否有具體的更新項目
            if update.items:
                # 組合更新項目為條列格式
                items_text = "\n".join(f"• {item}" for item in update.items)
                
                # 限制 field value 長度（Discord Embed field 限制 1024 字元）
                if len(items_text) > 1020:
                    items_text = items_text[:1017] + "..."
                    logger.warning(f"更新記錄 {update.date} 內容過長，已截斷")
                
                # 添加 field：name 為標題（含日期），value 為條列項目
                field_name = f"{update.date}: {update.title}"
                success_embed.add_field(
                    name=field_name,
                    value=items_text,
                    inline=False  # 每個更新獨佔一行
                )
            else:
                # 當沒有具體項目時，直接使用標題作為完整更新內容
                field_name = f"{update.date}: {update.title}"
                success_embed.add_field(
                    name=field_name,
                    value="",  # 空值會讓 Discord 只顯示標題
                    inline=False
                )
        
        # 6. 添加頁腳資訊
        total_updates = len(config.updates)
        if total_updates > count:
            success_embed.set_footer(text=f"顯示最新 {count} 個更新 (共 {total_updates} 個)")
        else:
            success_embed.set_footer(text=f"共 {total_updates} 個更新")

        await interaction.followup.send(embed=success_embed)
        logger.info(f"成功顯示 {len(latest_updates)} 個更新記錄")

    except Exception as e:
        logger.error(f"處理 patchnote 指令時發生錯誤: {e}")
        try:
            internal_error_embed = discord.Embed(
                description="❌ 處理指令時發生內部錯誤，請稍後再試。",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=internal_error_embed)
        except Exception:
            pass