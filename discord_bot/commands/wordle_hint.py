"""
/wordle_hint Slash Command 實作
搬移自 discord_bot.client，以模組化方式集中管理指令。
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import discord
from discord import app_commands
import pytz

from utils.wordle_service import (
    WordleNotFound,
    WordleAPITimeout,
    WordleServiceError,
    safe_wordle_output,
)

# PromptSystem 用於取得 persona 與提示模板
from prompt_system.prompts import PromptSystem

if TYPE_CHECKING:
    # 僅型別檢查時才導入，避免循環匯入
    from discord_bot.client import DCPersonaBot

logger = logging.getLogger(__name__)


@app_commands.command(name="wordle_hint", description="獲取 Wordle 遊戲提示")
@app_commands.describe(date="指定日期 (YYYY-MM-DD)，預設為今天")
async def wordle_hint_command(
    interaction: discord.Interaction, date: Optional[str] = None
):
    """/wordle_hint Slash Command 處理器"""

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
        # 1. 解析日期
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                error_embed = discord.Embed(
                    description="❌ 日期格式錯誤！請使用 YYYY-MM-DD 格式，例如：2024-01-15",
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=error_embed)
                return
        else:
            # 使用配置中的時區獲取今天的日期
            timezone = bot.config.system.timezone
            tz = pytz.timezone(timezone)
            target_date = datetime.now(tz).date()

        logger.info(f"用戶 {interaction.user} 請求 {target_date} 的 Wordle 提示")

        # 2. 獲取 Wordle 答案
        try:
            wordle_result = await bot.wordle_service.fetch_solution(target_date)
            solution = wordle_result.solution
            logger.info(f"成功獲取 {target_date} 的 Wordle 答案")
        except WordleNotFound:
            not_found_embed = discord.Embed(
                description=f"❌ 找不到 {target_date} 的 Wordle 資料，請檢查日期是否正確。",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=not_found_embed)
            return
        except WordleAPITimeout:
            timeout_embed = discord.Embed(
                description="⏰ 請求超時，請稍後再試。",
                color=discord.Color.orange(),
            )
            await interaction.followup.send(embed=timeout_embed)
            return
        except WordleServiceError as e:
            service_error_embed = discord.Embed(
                description=f"❌ 服務暫時不可用：{str(e)}",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=service_error_embed)
            return

        # 3. 生成提示
        if not bot.wordle_llm:
            llm_error_embed = discord.Embed(
                description="❌ LLM 服務不可用，無法生成提示。",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=llm_error_embed)
            return

        try:
            # 獲取當前 persona 風格
            persona_style = "友善且有趣"  # 預設風格
            try:
                if bot.config.prompt_system.persona.enabled:
                    if bot.config.prompt_system.persona.random_selection:
                        persona_style = bot.prompt_system.random_system_prompt(
                            bot.config.prompt_system.persona.persona_directory
                        )
                    else:
                        persona_style = bot.prompt_system.get_specific_persona(
                            bot.config.prompt_system.persona.default_persona,
                            bot.config.prompt_system.persona.persona_directory,
                        )
            except Exception as e:
                logger.warning(f"獲取 persona 風格失敗，使用預設風格: {e}")

            # 1. 取得隨機的提示風格描述
            hint_style_dir = Path("prompt_system/tool_prompts/wordle_hint_types")
            hint_style_description = bot.prompt_system.random_system_prompt(
                hint_style_dir, use_cache=False
            )
            if not hint_style_description:
                logger.error("無法獲取隨機 Wordle 提示風格，流程中止。")
                style_error_embed = discord.Embed(
                    description="❌ 內部錯誤：無法載入提示風格。",
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=style_error_embed)
                return

            # 2. 取得主提示詞模板並傳入風格描述
            prompt_template = bot.prompt_system.get_tool_prompt(
                "wordle_hint_instructions",
                solution=solution,
                persona_style=persona_style,
                hint_style_description=hint_style_description,
            )

            logger.debug(f"Wordle 提示生成提示詞: {prompt_template}")

            # 調用 LLM 生成提示
            response = await bot.wordle_llm.ainvoke(
                [{"role": "user", "content": prompt_template}]
            )
            hint_content = response.content

            # 將 <think> 和 <check> 區塊轉為 Discord spoiler
            hint_content = re.sub(
                r"<think>(.*?)</think>",
                r"||\\1||",
                hint_content,
                flags=re.DOTALL | re.IGNORECASE,
            )

            def _replace_check(match):
                inner = match.group(1).strip()
                return f"題解:\n|| {inner} ||"

            hint_content = re.sub(
                r"<check>(.*?)</check>",
                _replace_check,
                hint_content,
                flags=re.DOTALL | re.IGNORECASE,
            )

            # 4. 安全後處理
            safe_hint = safe_wordle_output(hint_content, solution)

            # 5. 發送回應
            success_embed = discord.Embed(
                title=f"Wordle 提示 - {target_date}",
                description=safe_hint,
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=success_embed)

        except Exception as e:
            logger.error(f"生成 Wordle 提示時發生錯誤: {e}")
            generate_error_embed = discord.Embed(
                description="❌ 生成提示時發生錯誤，請稍後再試。",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=generate_error_embed)

    except Exception as e:
        logger.error(f"Wordle hint 指令處理時發生未預期錯誤: {e}")
        try:
            internal_error_embed = discord.Embed(
                description="❌ 處理指令時發生內部錯誤，請稍後再試。",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=internal_error_embed)
        except Exception:
            pass 