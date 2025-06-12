# llmcord 專案重構提案 (簡化版)

---

## 1. 目標 (Goals)

本次重構旨在建立一個統一、模組化且可擴展的智慧代理（Agent）架構，核心目標是實現一個靈活且配置驅動的工作流程：

*   **統一工作流程**: 透過一個統一的 LangGraph 流程處理所有請求。代理將根據配置和輪次限制，動態評估並決定使用適當的工具，實現「訊息 -> (代理評估使用工具 -> 回傳 -> 多輪交互) -> 最終答案」的自動化流程。
*   **可組合的代理**: 代理的能力由一套可插拔、可設定的工具和輪次限制定義，使其功能可透過設定檔動態調整。
*   **提升模組化與簡潔性**: 重新組織專案結構，使模組職責更清晰、耦合度降低，提升可維護性與擴展性。
*   **以參考架構為基礎**: 以 `reference_arch.md` 中定義的核心流程和概念為指導，確保 `agent_core` 的設計和實作與之保持一致。

---

## 2. 現有 LangGraph Agent 功能流程分析

本節重點說明為實現統一代理架構，訊息處理流程將如何簡化與變革：

#### 主要變革點：統一代理處理流程
*   **Agent 配置檢查**: 根據配置確認可用工具及最大工具使用輪次。
*   **統一 Agent 執行**: 取代原有模式選擇，Agent 將自動決策是否使用工具，支援多輪工具調用、進度回報，並受輪次控制。
*   **LangGraph 統一執行**: 流程將基於新的 LangGraph 設計，包含 LLM 推理、工具調用、結果整合、反思與路由、以及最終答案生成。

#### 關鍵功能注意事項
*   **Random System Prompt (Persona)**: 透過 `prompt_system/prompts.py` 統一管理，依配置決定是否啟用隨機系統提示詞。
*   **Discord 特定系統提示**: 統一在 `prompt_system/prompts.py` 中處理時間戳、Bot ID 及用戶名等 Discord 相關提示。
*   **LangGraph 會話狀態管理**: 由 `agent_core/agent_session.py` 負責會話 ID 生成、狀態持久化與自動清理，支援多輪對話上下文。

---

## 3. 新專案架構設計（統一 Agent 行為）

```
llmcord/
│
├── main.py                  # 程式主入口，初始化 Bot 並啟動 Agent 核心
├── config.yaml              # 系統設定檔，包含工具配置、輪次限制等
├── personas/                # 存放不同性格的 Agent 系統提示詞
│
├── discord_bot/
│   ├── client.py            # Discord Client 初始化
│   ├── message_handler.py   # 處理 Discord 事件，將訊息轉換為通用訊息格式後傳遞給統一 Agent
│   ├── message_collector.py # 訊息收集與預處理
│   ├── progress_manager.py  # Discord 進度消息管理
│   └── response_formatter.py# LLM 回覆後處理與發送
│
├── agent_core/              # **[核心]** 統一的 Agent 處理引擎
│   ├── agent.py             # **[新/簡化]** 統一 Agent 實作，提供獨立運作介面 (極度精簡，僅作為入口)
│   ├── graph.py             # **[核心新]** 負責 LangGraph 構建、所有節點定義及直接內嵌工具邏輯 (如 Google Search)
│   ├── agent_session.py     # 管理單次對話的 Agent 會話與狀態
│   └── agent_utils.py       # **[新]** 存放 Agent 核心專屬的輔助函式
│
├── prompt_system/           # **[簡化]** 統一的提示詞管理系統
│   ├── prompts.py           # **[新/合併]** 統一管理所有 Agent 提示詞、Persona 選擇與系統提示詞組裝
│
├── schemas/                 # 結構化資料模式
│   ├── agent_types.py       # **[新/合併]** 統一的代理相關型別定義 (包含 OverallState, SearchQueryList, Reflection 等)
│   └── discord.py           # Discord 相關結構
│
├── tools/
│   └── citation.py          # 引用管理工具
│
├── utils/
│   ├── config_loader.py     # 設定檔讀取與管理
│   ├── logger.py            # 日誌系統設定
│   └── discord_utils.py     # Discord 互動輔助函式
│
└── tests/
    └── ...                  # 所有測試檔案
```

---

## 4. 模組職責與新流程設計

### 4.1 核心模組職責

#### `agent_core/` - 統一 Agent 處理引擎
*   **`agent.py`**: 作為統一入口點，負責初始化並執行 `agent_core/graph.py` 中的 LangGraph 實例，管理 Agent 執行生命週期。**此模組設計為與特定的應用（如 Discord）完全解耦，只處理通用的訊息和狀態。**
*   **`graph.py`**: **核心職責**是根據配置動態構建 LangGraph 的 `StateGraph`。它將定義所有 LangGraph 節點的實現，包括 `generate_query_or_plan` (生成查詢/規劃)、`tool_selection` (工具選擇)、`execute_tool` (執行工具)，以及 `reflection` (反思)、`evaluate_research` (評估研究) 和 `finalize_answer` (最終答案)。**這些節點的設計和流程將嚴格參考 `reference_arch.md` 中定義的 Agent 核心流程。**所有工具的具體實現（如 Google Search 的調用、grounding metadata 處理、引用生成）將直接內嵌於相應的節點內部 (例如 `execute_tool` 節點內)，不再作為獨立的 `tools/` 模組。
*   **`agent_session.py`**: 管理單次對話的 Agent 會話與狀態。
*   **`agent_utils.py`**: 存放 Agent 核心邏輯強相關的輔助函式，如引用處理、研究主題獲取。

#### `prompt_system/prompts.py` - 統一提示詞管理
*   負責合併所有提示詞管理功能，包括 Random persona 選擇、系統提示詞組裝（包含 Discord 特定、時間、用戶名等資訊）、動態工具說明生成。

#### `schemas/agent_types.py` - 統一的代理相關型別定義
*   合併與 Agent 核心流程相關的所有類型定義，包含 `OverallState` (簡化後的統一狀態結構)、`SearchQueryList`、`Reflection` 及通用訊息結構 `MsgNode`。

#### `tools/` - 工具系統
*   `base.py` (LangGraph 工具基底類別) 將被**移除**，因為工具邏輯將直接內嵌於 `agent_core/graph.py` 中的節點。
*   `citation.py` 引用管理工具維持。

### Web Search 實作說明 (更新)
*   **Google Search 邏輯直接內嵌於 `agent_core/graph.py` 的 `execute_tool` 節點中**：這包括 `google.genai.Client` 的調用、搜尋查詢執行、grounding metadata 處理、引用和來源生成。這將消除獨立的 `tools/google_search.py` 模組。
*   **支援兩種使用場景**：
    1.  **0 輪模式**：不使用任何工具，純對話。
    2.  **N 輪模式**：使用 `execute_tool` 節點進行工具調用與研究，該節點內部直接處理所有工具相關邏輯。

### 4.2 新的統一流程設計

```
Discord Message
      ↓
discord_bot/message_handler.py (轉換為通用 MsgNode & 載入配置)
      ↓
agent_core/agent.py (初始化並執行 LangGraph)
      ↓
agent_core/graph.py (LangGraph 統一執行流程)
      ↓
generate_query_or_plan (生成查詢/規劃)
      ↓
tool_selection (工具選擇)
      ↓
execute_tool (執行工具，例如 web_search 節點直接處理 Google Search)
      ↓
reflection (反思)
      ↓
evaluate_research (評估研究)
      ├─ 達到輪次限制 / 結果充分 → finalize_answer (生成最終回覆) → END
      └─ 需要更多資訊 → 返回 generate_query_or_plan 或 tool_selection (下一輪)
      ↓
finalize_answer (生成最終回覆)
      ↓
prompt_system/prompts.py (統一的提示詞組裝，包含 Persona & Discord 特定處理)
      ↓
Final Answer
      ↓
discord_bot/response_formatter.py (格式化 & 發送回覆)
```

---

## 4.3 配置驅動的 Agent 行為

#### Tool Priority 說明
*   **priority 數值**：決定工具在 LangGraph 中的調用順序
*   **較小數值 = 較高優先級**：priority: 1 會在 priority: 2 之前執行
*   **用途**：當 Agent 決定使用多個工具時，按優先級順序執行
*   **範例**：google_search (priority: 1) → citation (priority: 2)

```yaml
# 統一 Agent 配置
agent:
  # 工具配置 - 決定 Agent 能力
  tools:
    google_search:
      enabled: true
      priority: 1
    citation:
      enabled: true
      priority: 2
  
  # 行為控制 - 決定 Agent 使用深度
  behavior:
    max_tool_rounds: 2        # 0=純對話, 1=簡單查詢, 2+=深度研究
    timeout_per_round: 30     # 每輪最大時間
    enable_reflection: true   # 啟用結果反思
    enable_progress: true     # 啟用進度回報
    
  # 決策參數
  thresholds:
    tool_usage: 0.3          # 何時開始使用工具
    completion: 0.8          # 何時認為結果足夠
    confidence: 0.7          # 工具結果信心度閾值

# 提示詞系統配置  
prompt_system:
  persona:
    enabled: true
    random_selection: true
    cache_personas: true
  discord_integration:
    include_timestamp: true
    include_mentions: true
    timezone: "Asia/Taipei"
```

### 4.4 現有 `agents/` 目錄模組處理細則

為了實現新架構的統一性與模組化，現有 `agents/` 目錄下的模組將按以下原則進行處理：

*   **`agents/tools_and_schemas.py`**
    *   **重構方案**：工具定義將被**移除**並整合至 `agent_core/graph.py` 的 `execute_tool` 節點內部。代理相關的資料結構將遷移至 `schemas/agent_types.py`。
    *   **目標**：確保所有工具定義和資料結構都符合新的模組化原則，並清除冗餘或過時的代碼。

*   **`agents/configuration.py`**
    *   **重構方案**：此檔案的內容將會被整合至新的 `config.yaml` 中，作為 Agent 行為和決策的統一配置來源。
    *   **目標**：實現 Agent 行為的完全配置驅動，消除代碼中硬編碼的配置邏輯。

*   **`agents/utils.py`**
    *   **重構方案**：此檔案中的 Agent 核心相關輔助函式將遷移至新的 `agent_core/agent_utils.py`。其餘通用輔助函數將遷移至其他通用 `utils` 檔案，若無用則移除。
    *   **目標**：確保輔助函數的職責清晰，避免單一大型工具檔案，提升代碼可讀性與維護性。

---

## 5. 實作任務拆分與階段目標

### Phase 1: 基礎架構與狀態管理 (2-3 weeks)

#### Week 1: 基礎架構建立
**目標**: 建立新目錄結構和基礎模組

**任務清單**:
- [ ] **Task 1.1**: 建立新目錄結構與基礎模組框架
  - 建立 `agent_core/`, `prompt_system/`, `schemas/`, `discord_bot/` 目錄
  - 設置基本的 `__init__.py` 檔案
  - 建立基本的模組框架

- [ ] **Task 1.2**: 遷移基礎模組
  - 遷移 `utils/config_loader.py` (原 `core/config.py`)
  - 遷移 `utils/logger.py` (原 `core/logger.py`)
  - 遷移 `utils/common_utils.py` (原 `core/utils.py` 部分功能)
  - 更新 import 路徑

- [ ] **Task 1.3**: 建立 schemas 模組
  - 遷移 `schemas/agent_types.py` (合併原 `agents/state.py` 及 `discordbot/msg_node.py` 中的相關結構)
  - 統一狀態結構，移除模式相關狀態

**測試驗證**:
```bash
# 基礎模組測試
python -c "from utils.config_loader import load_config; print('✓ Config loader works')"
python -c "from schemas.agent_types import OverallState; print('✓ Agent schemas work')"
```

#### Week 2: 會話管理與 Discord 模組
**目標**: 建立會話管理和 Discord 相關模組

**任務清單**:
- [ ] **Task 2.1**: 建立 `agent_session.py`
  - 實作會話 ID 生成邏輯
  - 建立 Discord 訊息歷史快取機制
  - 實作 LangGraph 狀態存儲與管理
  - 建立基於時間的清理機制

- [ ] **Task 2.2**: 遷移 Discord 模組
  - 遷移 `discord_bot/message_collector.py` (原 `pipeline/collector.py`)
  - 遷移 `discord_bot/response_formatter.py` (原 `pipeline/postprocess.py`)
  - 遷移 `discord_bot/progress_manager.py` 並簡化介面
  - 整合會話管理到訊息收集流程

- [ ] **Task 2.3**: 建立 Prompt System 基礎
  - 建立 `prompt_system/prompts.py` (合併原 `persona_manager.py`, `system_prompt_builder.py`, `agent_prompts.py` 功能)
  - 遷移 `random_system_prompt()` 功能
  - 添加 persona 快取機制

**測試驗證**:
```bash
# 會話管理測試
python -c """
from agent_core.agent_session import AgentSession
session = AgentSession()
session_id = session.create_session(channel_id=456)
print(f'✓ 會話創建成功: {session_id}')
"""
# Discord 模組測試 (需有測試檔案)
# python tests/test_message_collector.py
# python tests/test_response_formatter.py
```

#### Week 3: LangGraph 節點統一化
**目標**: 重構 LangGraph 節點，支援統一的工具使用流程

**任務清單**:
- [ ] **Task 3.1**: 重構 `agent_core/graph.py` 的節點定義
  - 實作 `generate_query_or_plan` 節點（整合生成查詢與初步規劃邏輯）
  - 實作 `tool_selection` 節點（決策使用何種工具）
  - 實作 `execute_tool` 節點（通用工具調用器，內嵌 `web_search` 等工具邏輯）
  - 實作 `reflection` 節點（結果反思）
  - 實作 `evaluate_research` 節點（路由判斷，基於輪次與配置）
  - 保留 `finalize_answer` 節點

- [ ] **Task 3.2**: 重構狀態管理
  - 統一 `schemas/agent_types.py` 的狀態結構
  - 簡化 `OverallState` 結構，專注於工具使用追蹤
  - 改進會話狀態管理 (配合 `agent_session.py`)

- [ ] **Task 3.3**: 整合測試
  - 建立端到端的 Agent 測試
  - 驗證不同工具配置下的行為
  - 測試輪次控制機制

- [ ] **Task 3.4**: 修正 `_execute_google_search` 未返回搜尋結果的問題
  - 分析問題：`_execute_google_search` 在第二次對話中未能返回實際的 Google 搜尋結果，大型語言模型 (LLM) 僅回應其角色設定而非執行搜尋工具。
  - 解決方案：修改 `_execute_google_search` 函數中的 `google_client.models.generate_content` 調用，將 `contents` 參數調整為包含兩個部分：第一部分是 `web_searcher_instructions`（作為系統指示），第二部分是實際的搜尋查詢 `query`。這樣 LLM 就能正確觸發搜尋工具並返回結果。

**測試驗證**:
```bash
# LangGraph 統一流程測試 (需有測試檔案)
# python tests/test_unified_workflow.py
# 不同配置下的行為測試 (需有測試檔案)
# python tests/test_configurable_behavior.py
# 搜尋結果修正測試 (需有測試檔案)
# python tests/test_google_search_fix.py
```

### Phase 2: Discord Bot 整合 (1-2 weeks)

#### Week 4: Discord 模組重構
**目標**: 重構 Discord 相關模組，整合統一 Agent

**任務清單**:
- [ ] **Task 4.1**: 簡化 `message_handler.py`
  - 移除模式選擇邏輯
  - 整合統一 Agent 調用
  - 簡化錯誤處理流程

- [ ] **Task 4.2**: 遷移支援模組
  - 遷移 `discord_bot/message_collector.py` (原 `pipeline/collector.py`)
  - 遷移 `discord_bot/response_formatter.py` (原 `pipeline/postprocess.py`)
  - 遷移 `discord_bot/progress_manager.py` 並簡化介面

- [ ] **Task 4.3**: 更新配置系統
  - 調整配置結構支援統一 Agent
  - 移除模式相關配置選項
  - 確保向後兼容性

**測試驗證**:
```bash
# Discord 整合測試 (需有測試檔案)
# python tests/test_discord_integration.py
# 配置兼容性測試 (需有測試檔案)
# python tests/test_config_compatibility.py
```

### Phase 3: 整合測試與優化 (1 week)

#### Week 5: 系統整合與測試
**目標**: 完整系統測試與性能優化

**任務清單**:
- [ ] **Task 5.1**: 端到端測試
  - 測試不同工具配置的完整流程
  - 驗證輪次控制機制
  - 測試錯誤處理與降級

- [ ] **Task 5.2**: 性能優化
  - 統一 Agent 性能優化
  - 提示詞快取機制
  - 會話管理優化

- [ ] **Task 5.3**: 文檔與部署準備
  - 更新配置文檔
  - 建立新架構說明
  - 準備正式發布

**測試驗證**:
```bash
# 完整系統測試套件 (需有測試檔案)
# python -m pytest tests/ -v
# 性能基準測試 (需有測試檔案)
# python tests/test_performance_benchmark.py
```

---

## 6. 配置設計與行為定義

### 6.1 統一配置結構
```yaml
# 統一 Agent 配置
agent:
  # 工具配置 - 決定 Agent 能力
  tools:
    google_search:
      enabled: true
      priority: 1
    citation:
      enabled: true
      priority: 2
  
  # 行為控制 - 決定 Agent 使用深度
  behavior:
    max_tool_rounds: 2        # 0=純對話, 1=簡單查詢, 2+=深度研究
    timeout_per_round: 30     # 每輪最大時間
    enable_reflection: true   # 啟用結果反思
    enable_progress: true     # 啟用進度回報
    
  # 決策參數
  thresholds:
    tool_usage: 0.3          # 何時開始使用工具
    completion: 0.8          # 何時認為結果足夠
    confidence: 0.7          # 工具結果信心度閾值

# 提示詞系統配置  
prompt_system:
  persona:
    enabled: true
    random_selection: true
    cache_personas: true
  discord_integration:
    include_timestamp: true
    include_mentions: true
    timezone: "Asia/Taipei"
```

### 6.2 Agent 行為範例

#### 場景 1: 純對話 Agent (max_tool_rounds: 0)
```yaml
agent:
  tools: {}  # 不啟用任何工具
  behavior:
    max_tool_rounds: 0
```
→ 行為：純 LLM 對話，快速回應，適合閒聊

#### 場景 2: 簡單查詢 Agent (max_tool_rounds: 1)
```yaml
agent:
  tools:
    google_search: {enabled: true}
  behavior:
    max_tool_rounds: 1
```
→ 行為：最多進行一次搜索，適合簡單問題查詢

#### 場景 3: 深度研究 Agent (max_tool_rounds: 3)
```yaml
agent:
  tools:
    google_search: {enabled: true}
    citation: {enabled: true}
  behavior:
    max_tool_rounds: 3
    enable_reflection: true
```
→ 行為：多輪工具使用，深度分析，適合複雜研究

---

## 7. 成功標準與驗收條件

### 7.1 功能性標準
- [ ] 統一 Agent 支援 0-N 輪工具使用
- [ ] 配置驅動的 Agent 行為調整
- [ ] 保留所有現有功能
- [ ] Persona 系統正常運作

### 7.2 簡潔性標準  
- [ ] 移除模式相關的代碼與配置
- [ ] Agent 實作統一在單一模組中
- [ ] 提示詞系統統一管理
- [ ] 配置結構更直觀易懂

### 7.3 可擴展性標準
- [ ] 新增工具只需實作工具類別並更新配置
- [ ] 調整 Agent 行為只需修改配置檔案
- [ ] 支援動態工具組合與輪次調整
- [ ] 模組職責清晰，易於維護

---

## 8. 總結

本重構提案採用**統一 Agent 設計**，透過**工具配置與輪次限制**來定義 Agent 能力，並將**工具邏輯直接內嵌於 LangGraph 節點中**，徹底簡化了系統架構：

### 8.1 主要改進
1.  **移除模式區分**: 不再有研究模式 vs 傳統模式，全部統一為可配置的 Agent 行為。
2.  **配置驅動**: Agent 的能力完全由配置檔案決定，從純對話到深度研究都在同一套系統中。
3.  **輪次控制**: 通過 `max_tool_rounds` 參數控制 Agent 的工具使用深度。
4.  **工具組合**: 可任意組合工具，每個工具可獨立啟用/停用。
5.  **架構簡化**: 移除了 router、多個 agent 類別等複雜結構，工具邏輯直接內嵌，減少模組間依賴。

### 8.2 使用靈活性
*   **0 輪**: 純對話 Agent，快速回應。
*   **1 輪**: 簡單查詢 Agent，進行一次工具調用。
*   **N 輪**: 深度研究 Agent，多次工具調用與反思。

這種設計讓系統更簡潔、更直觀，同時保持了原有的所有功能，並提供了更大的擴展靈活性。