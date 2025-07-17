# Task: 自動產生進度訊息（Progress-LLM）- 架構重構

## 1. 目標
1. 在 **不變動既有 `llm.models.main`** 的前提下，於 `config` 新增第二支 Gemini 模型 `progress_msg`，專責生成簡短進度訊息。
2. 允許透過 `progress.discord.auto_generate_messages` 開啟／關閉自動產生功能，預設關閉，向後相容。
3. 透過 `ProgressMixin` 呼叫 `progress_msg` LLM，並在 `ProgressMixin` 內生成；當 `message` 留空且 auto_msg 條件成立時，自動呼叫並回傳最長 16 字以內的短句。
4. TOOL_STATUS 等高頻事件維持模板，不呼叫 LLM。

---

## 2. 架構調整 - 責任分離

### 核心原則
- **Agent 責任**：只處理 Agent 特有資訊（消息、Persona）
- **ProgressMixin 責任**：只處理 progress 相關資訊（stage、template、progress prompt）
- **清晰分離**：Agent 永遠不碰 progress 資訊，ProgressMixin 永遠不碰 Agent 特有資訊

### 關鍵設計決策
**為什麼 ProgressMixin 需要 `current_state` 參數？**

經過討論，確認以下關鍵事實：
1. **Agent 實例是一次性的**：每次 Discord 訊息都會 `create_unified_agent()` 創建新實例
2. **LangGraph state 是持久的**：在整個 graph 執行期間，`OverallState` 在各節點間流轉
3. **Progress 調用可能在 Agent 銷毀後發生**：例如 cleanup 或 async 延遲調用
4. **LangGraph 標準做法**：狀態應該透過 `state` 參數傳遞，而不是依賴實例變數

因此，**必須透過 `current_state: OverallState` 參數**來傳遞狀態，而不是依賴 `self` 屬性。

### 執行流程
1. **ProgressMixin** 收到 `_generate_progress_message(stage, current_state)` 請求
2. **ProgressMixin** 調用 `_build_agent_messages_for_progress(stage, current_state)`
3. **UnifiedAgent** 重寫的方法從 `current_state` 取得 Agent 特有資訊（消息、Persona），返回 messages
4. **ProgressMixin** 收到 Agent 準備的 messages，加入 progress 指令
5. **ProgressMixin** 調用 LLM 生成最終結果
6. **progress_adapter** 使用 emoji_handler 格式化輸出

---

## 3. Config 調整
```yaml
llm:
  models:
    tool_analysis:
      model: "gemini-2.0-flash-exp"
      temperature: 0.1
    final_answer:
      model: "gemini-2.0-flash-exp"
      temperature: 0.7
    reflection:
      model: "gemini-2.0-flash-exp"
      temperature: 0.3
    progress_msg:              # ★ 新增
      model: "gemini-2.0-flash-lite"
      temperature: 0.4
      max_output_tokens: 16    # 嚴格限制回傳長度

progress:
  discord:
    auto_generate_messages: false   # 預設關閉，可在 YAML 切換
```

---

## 4. 程式碼修改詳細項目

### A. 架構核心修改

#### 1. **schemas/agent_types.py**
```python
@dataclass
class OverallState:
    current_persona: Optional[str] = None  # ★ 新增
    messages: List[MsgNode] = field(default_factory=list)
    # ... 其他欄位
```

#### 2. **agent_core/progress_mixin.py**
```python
# 主要修改：責任分離和清理
async def _generate_progress_message(self, stage: str, current_state: OverallState) -> str:
    """基礎方法：處理 progress 相關資訊"""
    
    # 1. 獲取 Agent 準備好的 messages
    agent_messages = await self._build_agent_messages_for_progress(stage, current_state)
    
    # 2. 加入 progress 指令（ProgressMixin 的責任）
    messages = self._add_progress_instruction(agent_messages, stage)
    
    # 3. 調用 LLM 生成
    return await self._generate_with_llm(messages, stage)

async def _build_agent_messages_for_progress(self, stage: str, current_state: OverallState) -> List[BaseMessage]:
    """讓 Agent 構建 messages（子類重寫）"""
    return []

def _add_progress_instruction(self, messages: List[BaseMessage], stage: str) -> List[BaseMessage]:
    """加入 progress 指令"""
    template_message = self.config.progress.discord.messages.get(stage, "")
    
    progress_instruction = f'''
你現在需要為進度階段 "{stage}" 生成簡短的進度訊息。

參考模板: {template_message}

要求:
- 嚴格限制在16字左右
- 保持簡潔友好
- 使用適當的 emoji
- 基於當前對話上下文
'''
    
    # 在現有 SystemMessage 基礎上 chain
    original_system = messages[0].content
    new_messages = messages.copy()
    new_messages[0] = SystemMessage(content=f"{original_system}\n\n{progress_instruction}")
    
    # 添加生成指令
    new_messages.append(HumanMessage(content=f"請為 {stage} 階段生成約16字的簡短進度訊息"))
    
    return new_messages

async def _generate_with_llm(self, messages: List[BaseMessage], stage: str) -> str:
    """純粹的 LLM 調用"""
    
    if not self._progress_llm:
        return self.config.progress.discord.messages.get(stage, "🔄 處理中...")
    
    try:
        response = await self._progress_llm.ainvoke(messages)
        content = response.content.strip()
        
        # 長度控制
        if len(content) > 16:
            content = content[:13] + "..."
        
        return content
        
    except Exception as e:
        self.logger.error(f"進度訊息生成失敗: {e}")
        return self.config.progress.discord.messages.get(stage, "🔄 處理中...")

# 修改原有方法簽名
async def _notify_progress(self, stage: str, message: str = "", 
                          progress_percentage: Optional[int] = None,
                          eta_seconds: Optional[int] = None,
                          auto_msg: Optional[bool] = None,
                          current_state: Optional[OverallState] = None):  # ★ 新增參數
    # ... 原有邏輯
    
    if should_auto_generate:
        message = await self._generate_progress_message(stage, current_state)
    
    # ... 其他邏輯
```

#### 3. **agent_core/graph.py**
```python
class UnifiedAgent(ProgressMixin):
    def __init__(self, config: Optional[AppConfig] = None):
        # ... 其他初始化
        
        # 初始化 progress LLM
        self._progress_llm = self._initialize_progress_llm()
        
        # 移除 ProgressMessageFactory 相關代碼

    async def generate_query_or_plan(self, state: OverallState) -> Dict[str, Any]:
        """生成查詢或計劃（在此處初始化 persona）"""
        
        # ★ 新增：確定 current_persona（在第一個節點處理）
        if not state.current_persona:
            if self.config.prompt_system.persona.random_selection:
                state.current_persona = self.prompt_system.get_random_persona_name()
            else:
                state.current_persona = self.config.prompt_system.persona.default_persona
        
        # 繼續原有的 generate_query_or_plan 邏輯...
        await self._notify_progress(
            stage=ProgressStage.GENERATE_QUERY.value,
            message="",
            progress_percentage=20,
            current_state=state  # ★ 新增
        )
        
        # ... 其他邏輯

    async def _build_agent_messages_for_progress(self, stage: str, current_state: OverallState) -> List[BaseMessage]:
        """Agent 只處理 Agent 特有資訊"""
        
        # 1. 獲取前10則消息
        recent_msg_nodes = current_state.messages[-10:] if current_state.messages else []
        
        # 2. 使用固定 persona 構建 system prompt
        system_prompt = self.prompt_system.get_system_instructions(
            self.config, persona=current_state.current_persona
        )
        
        # 3. 構建 messages
        messages = self._build_messages_for_llm(recent_msg_nodes, system_prompt)
        
        return messages

    def _initialize_progress_llm(self) -> Optional[ChatGoogleGenerativeAI]:
        """初始化進度 LLM"""
        try:
            progress_config = self.config.llm.models.get("progress_msg")
            if not progress_config:
                return None
                
            api_key = self.config.gemini_api_key
            if not api_key:
                return None
                
            llm_params = {
                "model": progress_config.model,
                "temperature": progress_config.temperature,
                "api_key": api_key
            }
            
            if progress_config.max_output_tokens and progress_config.max_output_tokens > 0:
                llm_params["max_output_tokens"] = progress_config.max_output_tokens
                
            return ChatGoogleGenerativeAI(**llm_params)
            
        except Exception as e:
            self.logger.error(f"初始化進度 LLM 失敗: {e}")
            return None

    # 修改所有 _notify_progress 調用，新增 current_state 參數
    # 例如在各節點中：
    await self._notify_progress(
        stage=ProgressStage.SEARCHING.value,
        message="",
        progress_percentage=50,
        current_state=state  # ★ 新增
    )
```

#### 4. **prompt_system/prompts.py**
```python
def get_system_instructions(
    self,
    config: AppConfig,
    messages_global_metadata: str = "",
    persona: Optional[str] = None  # ★ 新增參數
) -> str:
    """獲取系統指令，支援固定 persona"""
    
    # 時間戳資訊
    timestamp_info = self.build_timestamp_info()
    
    # Persona 處理
    if persona:
        # 使用指定的 persona
        persona_content = self.get_specific_persona(persona)
    elif config.prompt_system.persona.enabled:
        if config.prompt_system.persona.random_selection:
            persona_content = self.get_random_persona()
        else:
            persona_content = self.get_specific_persona(config.prompt_system.persona.default_persona)
    else:
        persona_content = config.prompt_system.persona.fallback
    
    # 組合最終的系統指令
    system_instructions = f"{persona_content}\n\n{timestamp_info}"
    
    if messages_global_metadata:
        system_instructions += f"\n\n{messages_global_metadata}"
    
    return system_instructions

def get_random_persona_name(self) -> str:
    """獲取隨機 persona 名稱"""
    available_personas = self.get_available_personas()
    if available_personas:
        import random
        return random.choice(available_personas)
    return self.config.persona.default_persona
```

#### 5. **discord_bot/progress_adapter.py**
```python
async def on_progress_update(self, event: ProgressEvent) -> None:
    """處理進度更新事件，添加 emoji 處理"""
    
    # ... 現有邏輯
    
    # 檢查是否有自訂訊息，如果沒有則從配置載入
    message = event.message
    if not message:
        message = self.config.progress.discord.messages.get(event.stage.value, event.stage.value)
    
    # ★ 新增：emoji 處理
    if self.emoji_handler and message:
        try:
            guild_id = self.original_message.guild.id if self.original_message.guild else None
            message = self.emoji_handler.format_emoji_output(message, guild_id)
        except Exception as e:
            self.logger.warning(f"格式化進度訊息 emoji 失敗: {e}")
    
    # ... 其他邏輯
```

### B. 清理工作

#### 6. **agent_core/progress_message_factory.py**
- **刪除整個文件**，功能已整合到 ProgressMixin

#### 7. **tests/** 相關測試
- **修改** `test_progress_message_factory.py` 為 `test_progress_mixin_llm.py`
- **更新** `test_progress_mixin_integration.py` 適應新的架構
- **新增** persona 相關測試

---

## 5. 測試策略

### 單元測試
1. **ProgressMixin LLM 調用**：驗證 `_generate_with_llm` 功能
2. **Agent 消息構建**：驗證 `_build_agent_messages_for_progress` 功能
3. **Persona 一致性**：驗證同一對話使用相同 persona
4. **配置驗證**：驗證 `auto_generate_messages: false` 時不呼叫 LLM

### 整合測試
1. **完整流程**：從 `_notify_progress` 到最終 emoji 格式化
2. **錯誤處理**：LLM 失敗時的備用機制
3. **長度控制**：16字限制的前後處理

### 回歸測試
1. **現有功能**：確保所有 357 個既有測試通過
2. **向後相容**：確保預設關閉時行為不變

---

## 6. 待辦清單

### 已完成 ✅
- [x] schema 變更與 YAML 範例
- [x] 基礎 ProgressMessageFactory 實作（將被移除）
- [x] ProgressMixin 基本改動
- [x] 配置驗證和測試

### 進行中 🔄
- [ ] 架構重構：責任分離
- [ ] OverallState 添加 current_persona
- [ ] UnifiedAgent 整合新架構
- [ ] PromptSystem 支援固定 persona
- [ ] progress_adapter emoji 處理

### 待完成 ⏳
- [ ] 清理 ProgressMessageFactory
- [ ] 更新所有 _notify_progress 調用點
- [ ] 測試套件調整
- [ ] 回歸測試執行

### 關鍵對話記錄
**設計決策討論**：
1. **原始想法**：讓 ProgressMixin 直接使用 `self` 取得 Agent 狀態
2. **問題發現**：Agent 實例是一次性的，每次 Discord 訊息都會重新創建
3. **修正方案**：必須透過 `current_state: OverallState` 參數傳遞狀態
4. **原因**：LangGraph 的狀態管理模式 + Agent 生命週期短暫

---

## 7. 現在狀況

### 已實作功能
1. **配置結構** - 完整的 `progress_msg` 模型配置和 `auto_generate_messages` 選項
2. **基礎架構** - ProgressMixin 和 ProgressMessageFactory 基本實作
3. **測試覆蓋** - 31 個新測試，100% 通過率

### 待重構部分
1. **責任分離** - 需要重新分配 Agent 和 ProgressMixin 的職責
2. **Persona 管理** - 需要確保對話中 persona 一致性
3. **Emoji 處理** - 需要在 progress_adapter 中處理 LLM 生成的 emoji

### 潛在問題
1. **調用點更新** - 所有 `_notify_progress` 調用需要添加 `current_state` 參數
2. **測試調整** - 需要更新測試以適應新架構
3. **向後相容** - 確保重構不影響現有功能

---

## 8. 專案現況分析 (2025-07-17 更新)

### 已完成工作 ✅
1. **ProgressStage 枚舉轉換修正**: 修復了 `'str' object has no attribute 'value'` 錯誤
   - 修改 `graph.py` 中所有 `_notify_progress` 調用，改用枚舉對象而非字串
   - 更新 `progress_mixin.py` 和 `progress_adapter.py` 加入枚舉處理邏輯
   - 更新相關測試，確保型別安全
   
2. **LLM 進度訊息生成整合**: 將 LLM 智能進度訊息功能整合至現有架構
   - 在 `progress_mixin.py` 中實現 `_generate_progress_message` 和相關方法
   - 支援透過 `auto_generate_messages` 配置啟用/關閉
   - 加入高頻事件過濾（TOOL_STATUS、STREAMING 維持模板）
   - 支援 `current_state` 參數傳遞以維持狀態一致性

3. **文檔組織完成**: 更新所有專案文檔
   - `README.md`: 加入 LLM 進度訊息功能說明和配置範例
   - `project_rules.md`: 更新 progress_mixin 描述以反映 LLM 支援
   - `project_structure.md`: 更新進度系統架構說明和配置範例
   - 移除 debug print 語句和未使用的 `_progress_history` 功能

### 當前系統狀態
- **測試通過率**: 全部 progress 相關測試（55個）通過
- **核心功能**: ProgressStage 枚舉一致性問題已解決
- **新功能**: LLM 智能進度訊息生成已整合但需配置啟用
- **向後相容**: 完全保持，預設關閉新功能

### 配置示例 (已實現)
```yaml
progress:
  discord:
    auto_generate_messages: true  # 啟用LLM智能進度訊息生成
    
llm:
  models:
    progress_msg:
      model: "gemini-2.0-flash-lite"
      temperature: 0.4
      max_output_tokens: 20  # 嚴格限制進度訊息長度
```

### 待辦事項 (已完成主要項目)
- [x] 檢查 ProgressStage enum str 轉換一致性
- [x] 把其他 notify progress 也加入 LLM 生成訊息能力
- [x] 整理文檔：README、project_rules、project_structure
- [x] 更新 task.md 記錄最新狀態

### 技術實現摘要
1. **枚舉轉換修正**: 標準化 ProgressStage 枚舉使用，確保型別安全
2. **責任分離**: ProgressMixin 處理進度生成，Agent 提供上下文
3. **LLM 整合**: 透過 `_progress_llm` 實例生成個性化進度訊息
4. **配置驅動**: 完全可配置的功能啟用/關閉機制
5. **向後相容**: 不影響現有系統行為

### 系統具備能力
- ✅ 型別安全的進度階段管理
- ✅ 智能進度訊息生成（可選）
- ✅ 高頻事件優化（維持既有模板）
- ✅ 完整的 emoji 支援整合
- ✅ 錯誤處理與降級機制
- ✅ 100% 向後相容性

**結論**: 主要技術任務已完成，系統穩定運行，具備智能進度訊息生成能力且完全向後相容。