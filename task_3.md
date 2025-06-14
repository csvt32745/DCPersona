# Task 3: Persona 系統整合與 System Prompt 統一

## 概述
將 Persona 系統完全整合到 Agent 主流程中，並統一 system prompt 處理，實現動態 persona 切換和統一的提示詞管理。

## 目標
- 將 Persona 系統完全整合到主流程中
- 建立統一的 System Prompt 管理器
- 支援動態 persona 切換
- 統一處理所有 system prompt 相關邏輯

## 當前問題
- **Persona 未整合**: Persona 系統沒有整合到主流程中
- **System Prompt 分散**: system prompt 邏輯散布在各個模組中
- **缺乏統一管理**: 沒有統一的提示詞管理機制

## 子任務

### Task 3.1: 建立統一的 System Prompt 管理器
**狀態**: ✅ 已完成

**目標**: 建立 `prompt_system/system_prompt_manager.py`，統一處理所有 system prompt 相關邏輯

**需要創建的文件**:
- [ ] `prompt_system/system_prompt_manager.py`: 統一 System Prompt 管理器

**實作要點**:
```python
# prompt_system/system_prompt_manager.py
from datetime import datetime
from typing import Optional, Dict, Any
from schemas.config_types import AppConfig
from .persona_manager import PersonaManager

class SystemPromptManager:
    def __init__(self, config: AppConfig):
        self.config = config
        self.persona_manager = PersonaManager(config.prompt_system.persona)
    
    def build_system_prompt(self, 
                           context: str = "",
                           persona_name: Optional[str] = None,
                           discord_context: Optional[Dict] = None) -> str:
        """構建完整的系統提示詞"""
        parts = []
        
        # 1. 基礎 persona
        persona_prompt = self.persona_manager.get_system_prompt(persona_name)
        if persona_prompt:
            parts.append(persona_prompt)
        
        # 2. 動態格式化資訊
        dynamic_info = self._build_dynamic_info()
        if dynamic_info:
            parts.append(dynamic_info)
        
        # 3. 上下文資訊
        if context:
            context_prompt = f"以下是相關資訊，請用於回答問題：\n{context}"
            parts.append(context_prompt)
        
        # 4. Discord 特定資訊
        if discord_context:
            discord_info = self._build_discord_context(discord_context)
            if discord_info:
                parts.append(discord_info)
        
        return "\n\n".join(parts)
    
    def _build_dynamic_info(self) -> str:
        """構建動態資訊（時間、日期等）"""
        from prompt_system.prompts import get_current_date
        
        current_date = get_current_date(self.config.system.timezone)
        return f"當前日期時間：{current_date}"
    
    def _build_discord_context(self, discord_context: Dict) -> str:
        """構建 Discord 上下文資訊"""
        # 實現 Discord 特定的上下文處理
        parts = []
        
        if discord_context.get("guild_name"):
            parts.append(f"伺服器：{discord_context['guild_name']}")
        
        if discord_context.get("channel_name"):
            parts.append(f"頻道：{discord_context['channel_name']}")
        
        if discord_context.get("user_name"):
            parts.append(f"用戶：{discord_context['user_name']}")
        
        return "Discord 上下文：" + "，".join(parts) if parts else ""
```

**驗收標準**:
- 統一的 system prompt 構建邏輯
- 支援動態資訊格式化
- 支援 Discord 上下文整合

### Task 3.2: 建立 Persona 管理器
**狀態**: ✅ 已完成

**目標**: 建立 `prompt_system/persona_manager.py`，整合現有的 persona 選擇邏輯

**需要創建的文件**:
- [ ] `prompt_system/persona_manager.py`: Persona 管理器

**實作要點**:
```python
# prompt_system/persona_manager.py
import os
import random
from typing import Optional, List
from pathlib import Path
from schemas.config_types import PromptPersonaConfig

class PersonaManager:
    def __init__(self, config: PromptPersonaConfig):
        self.config = config
        self._cache = {}
        self._available_personas = self._discover_personas()
    
    def get_system_prompt(self, persona_name: Optional[str] = None) -> str:
        """獲取系統提示詞"""
        if persona_name:
            return self._load_specific_persona(persona_name)
        elif self.config.random_selection:
            return self._load_random_persona()
        else:
            return self._load_default_persona()
    
    def _discover_personas(self) -> List[str]:
        """發現可用的 persona 文件"""
        persona_dir = Path(self.config.persona_directory)
        if not persona_dir.exists():
            return []
        
        personas = []
        for file_path in persona_dir.glob("*.txt"):
            personas.append(file_path.stem)
        
        return personas
    
    def _load_specific_persona(self, persona_name: str) -> str:
        """載入指定的 persona"""
        if persona_name in self._cache:
            return self._cache[persona_name]
        
        persona_path = Path(self.config.persona_directory) / f"{persona_name}.txt"
        if not persona_path.exists():
            # 回退到預設 persona
            return self._load_default_persona()
        
        try:
            with open(persona_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            self._cache[persona_name] = content
            return content
        except Exception as e:
            # 載入失敗，回退到預設
            return self._load_default_persona()
    
    def _load_random_persona(self) -> str:
        """載入隨機 persona"""
        if not self._available_personas:
            return self._load_default_persona()
        
        random_persona = random.choice(self._available_personas)
        return self._load_specific_persona(random_persona)
    
    def _load_default_persona(self) -> str:
        """載入預設 persona"""
        if self.config.default_persona:
            return self._load_specific_persona(self.config.default_persona)
        
        # 最終回退
        return "你是一個有用的 AI 助手。"
    
    def list_available_personas(self) -> List[str]:
        """列出可用的 persona"""
        return self._available_personas.copy()
    
    def reload_personas(self):
        """重新載入 persona 列表"""
        self._cache.clear()
        self._available_personas = self._discover_personas()
```

**驗收標準**:
- 支援指定 persona 載入
- 支援隨機 persona 選擇
- 完善的錯誤處理和回退機制
- 支援 persona 列表發現

### Task 3.3: 重構 `agent_core/graph.py` 使用統一 System Prompt
**狀態**: ✅ 已完成

**目標**: 移除 `_generate_final_answer` 中分散的 system prompt 邏輯，使用 `SystemPromptManager` 統一處理

**需要修改的文件**:
- [ ] `agent_core/graph.py`: 重構 `_generate_final_answer` 和其他使用 system prompt 的方法

**修改要點**:
```python
# agent_core/graph.py
from prompt_system.system_prompt_manager import SystemPromptManager

class UnifiedAgent(ProgressMixin):
    def __init__(self, config: AppConfig):
        # ... 現有初始化 ...
        self.system_prompt_manager = SystemPromptManager(config)
    
    def _generate_final_answer(self, messages: List[MsgNode], context: str) -> str:
        """生成最終答案（使用統一 System Prompt）"""
        try:
            # 構建統一的系統提示詞
            system_prompt = self.system_prompt_manager.build_system_prompt(
                context=context,
                persona_name=None,  # 或從配置/狀態獲取
                discord_context=None  # 如果需要的話
            )
            
            messages_for_final_answer = [SystemMessage(content=system_prompt)]
            
            # 添加對話歷史
            for msg in messages:
                if msg.role == "user":
                    messages_for_final_answer.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages_for_final_answer.append(AIMessage(content=msg.content))
            
            # 使用 LLM 生成答案
            response = self.final_answer_llm.invoke(messages_for_final_answer)
            return response.content
            
        except Exception as e:
            self.logger.error(f"LLM 答案生成失敗: {e}")
            raise
    
    def _build_planning_prompt(self, messages: List[MsgNode]) -> str:
        """構建計劃生成提示詞"""
        # 使用統一的 system prompt 管理器
        base_prompt = self.system_prompt_manager.build_system_prompt()
        
        # 添加計劃生成特定的指令
        planning_instructions = """
        請分析用戶的問題，決定是否需要使用工具來獲取資訊。
        
        可用工具：
        - google_search: 搜尋最新資訊
        - citation: 處理引用和來源
        
        請以 JSON 格式回應你的計劃。
        """
        
        return f"{base_prompt}\n\n{planning_instructions}"
```

**驗收標準**:
- 所有 system prompt 邏輯統一管理
- `_generate_final_answer` 使用新的管理器
- 計劃生成也使用統一的 prompt 系統
- 保持所有現有功能

### Task 3.4: 整合 Discord 上下文支援
**狀態**: ⏳ 待開始

**目標**: 在 Discord Bot 中整合 persona 和上下文資訊

**需要修改的文件**:
- [ ] `discord_bot/message_handler.py`: 整合 Discord 上下文
- [ ] `discord_bot/message_collector.py`: 收集上下文資訊

**修改要點**:
```python
# discord_bot/message_handler.py
async def handle_message(self, message: discord.Message):
    """處理 Discord 訊息（整合 persona 系統）"""
    try:
        # 收集 Discord 上下文
        discord_context = {
            "guild_name": message.guild.name if message.guild else None,
            "channel_name": message.channel.name,
            "user_name": message.author.display_name,
            "user_id": str(message.author.id)
        }
        
        # 構建訊息節點
        msg_node = MsgNode(
            role="user",
            content=message.content,
            metadata={
                "discord_context": discord_context,
                "message_id": str(message.id),
                "timestamp": message.created_at.isoformat()
            }
        )
        
        # 創建初始狀態
        initial_state = OverallState(
            messages=[msg_node],
            discord_context=discord_context  # 新增欄位
        )
        
        # 執行 Agent
        await self._execute_agent(initial_state, message)
        
    except Exception as e:
        self.logger.error(f"處理訊息失敗: {e}")
        await message.reply("❌ 處理訊息時發生錯誤")
```

**驗收標準**:
- Discord 上下文正確收集和傳遞
- Persona 系統在 Discord 中正常工作
- 上下文資訊正確整合到 system prompt 中

## 測試驗證

### 自動化測試
```bash
# 測試 persona 和 system prompt 系統
python -c "from prompt_system.system_prompt_manager import SystemPromptManager; print('✓ System prompt manager works')"

# 測試 persona 管理器
python -c "from prompt_system.persona_manager import PersonaManager; print('✓ Persona manager works')"

# 測試整合
python -m pytest tests/test_persona_integration.py -v
```

### 功能測試
- [ ] Persona 載入正常
- [ ] System prompt 構建正確
- [ ] Discord 上下文整合正常
- [ ] 動態資訊格式化正確

## 依賴關係
- **前置條件**: Task 1 (型別安全配置系統) 完成
- **並行任務**: 可與 Task 2 (Graph 流程重構) 並行進行
- **後續任務**: Task 4 (Streaming 整合) 依賴此任務

## 預估時間
**1 週** (5-7 個工作日)

## 風險與注意事項
1. **Persona 文件管理**: 需要確保 persona 文件的正確載入和快取
2. **上下文資訊**: Discord 上下文資訊需要謹慎處理，避免洩露敏感資訊
3. **向後相容性**: 確保現有的 prompt 系統功能不受影響

## 預期改進效果
1. **統一管理**: 所有 system prompt 邏輯統一管理
2. **動態切換**: 支援動態 persona 切換
3. **上下文感知**: 更好的上下文感知能力
4. **可維護性**: 提升 prompt 系統的可維護性

## 成功標準
- [ ] Persona 系統完全整合到主流程
- [ ] 統一的 system prompt 管理器正常工作
- [ ] Discord 上下文正確整合
- [ ] 所有現有功能保持正常
- [ ] 支援動態 persona 切換 