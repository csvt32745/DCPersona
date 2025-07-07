# DCPersona 專案架構與實現說明

---

## 專案檔案結構

```
DCPersona/
│
├── main.py                  # Discord Bot 主程式入口，初始化與啟動
├── cli_main.py              # CLI 測試介面，支援對話模式和配置調整
├── config-example.yaml              # 系統設定檔（型別安全配置）
├── personas/                # Agent 人格系統提示詞資料夾
│
├── tools/                   # **[新增]** LangChain 工具定義
│   ├── google_search.py     # Google 搜尋工具
│   └── set_reminder.py      # 設定提醒工具
│
├── event_scheduler/         # **[新增]** 通用事件排程系統
│   └── scheduler.py         # 基於 APScheduler 的排程器核心
│
├── discord_bot/             # **[核心]** Discord 整合層
│   ├── client.py            # Discord Client 初始化與設定
│   ├── message_handler.py   # Discord 訊息事件處理主流程
│   ├── message_collector.py # 訊息收集、歷史處理與多模態支援
│   ├── progress_manager.py  # Discord 進度消息管理系統
│   ├── progress_adapter.py  # Discord 進度適配器（支援串流回應）
│   └── message_manager.py   # Discord 訊息快取管理
│
├── agent_core/              # **[核心]** 統一 Agent 處理引擎
│   ├── graph.py             # LangGraph 構建與 Agent 節點實現
│   ├── agent_utils.py       # Agent 核心輔助函式
│   ├── progress_observer.py # 進度觀察者介面（支援串流）
│   └── progress_mixin.py    # 進度更新混入（整合串流功能）
│
├── schemas/                 # **[重要]** 型別安全資料架構
│   ├── agent_types.py       # Agent 相關型別定義（狀態、計劃等）
│   ├── config_types.py      # 完整的型別安全配置定義
│   └── __init__.py
│
├── prompt_system/           # 統一提示詞管理系統
│   ├── prompts.py           # 核心提示詞功能與 PromptSystem
│   └── tool_prompts/        # 工具相關提示詞模板
│
├── utils/                   # 通用工具與配置
│   ├── config_loader.py     # 型別安全配置載入器
│   ├── logger.py            # 日誌系統設定
│   ├── common_utils.py      # 通用輔助函式
│   ├── image_processor.py   # 圖片 / Emoji / Sticker / 動畫處理核心
│   ├── wordle_service.py    # Wordle 遊戲提示服務
│   └── __init__.py
│
└── tests/                   # 測試檔案
    └── ...                  # 各種單元測試與整合測試
```

---

## 核心架構設計理念

### 1. 統一 Agent 架構
本專案採用基於 LangGraph 的統一 Agent 架構，實現了：

- **配置驅動的代理行為**: 透過 `config-example.yaml` 動態調整 Agent 能力
- **智能工具決策**: Agent 根據問題複雜度自主決定使用哪些工具
- **多輪對話支援**: 支援複雜的多步驟研究與推理流程
- **智能串流系統**: 整合即時串流回應，支援基於時間和內容長度的智能更新策略
- **統一進度管理**: 觀察者模式的解耦進度系統，支援多平台適配

### 2. 型別安全配置系統
完全採用 dataclass 配置架構，消除字串 key 存取：

- **嚴格型別檢查**: 所有配置欄位都有明確的型別定義
- **配置驗證**: 啟動時自動驗證配置完整性
- **IntelliSense 支援**: IDE 可提供完整的自動完成
- **串流配置**: 支援串流啟用控制和內容長度閾值設定
- **進度配置**: 靈活的進度更新間隔和顯示模式配置

### 3. 模組化與解耦設計
各模組職責清晰，低耦合高內聚：

- **Discord 層獨立**: 可輕鬆替換為其他平台
- **Agent 核心通用**: 支援 CLI 和 Discord 雙模式
- **工具系統可擴展**: 標準化的工具介面
- **統一訊息管理**: 所有 Discord 訊息操作統一通過 ProgressManager 處理
- **進度系統解耦**: 觀察者模式支援自定義進度處理器

---

## 主要工作流程

### Discord Bot 工作流程

```mermaid
flowchart TD
    A[Discord 訊息] --> B[message_handler.py]
    B --> C[message_collector.py]
    C --> D[收集訊息歷史與多模態內容]
    D --> E[創建 UnifiedAgent]
    E --> F[註冊 DiscordProgressAdapter]
    F --> G[LangGraph 執行]
    G --> H[即時進度更新]
    H --> I[最終回應]
    I --> J[Discord 回覆]
    J --> K[提醒排程]
    K --> L[提醒觸發]
```

**詳細步驟說明**:
1. **訊息接收**: `message_handler.py` 接收 Discord 事件
2. **權限檢查**: 驗證使用者權限和頻道設定
3. **訊息收集**: `message_collector.py` 收集對話歷史和圖片等多模態內容
4. **Agent 初始化**: 創建 `UnifiedAgent` 實例並配置進度觀察者
5. **LangGraph 執行**: 執行 `generate_query_or_plan` → `execute_tools` → `reflection` → `finalize_answer` 流程
6. **智能串流處理**: 在 `finalize_answer` 階段根據配置啟用串流回應，基於時間和內容長度智能更新
7. **統一進度管理**: 透過 `DiscordProgressAdapter` 和 `ProgressManager` 統一處理所有 Discord 訊息操作
8. **結果回覆**: 將最終答案格式化後回覆到 Discord，支援串流和非串流兩種模式
9. **提醒排程**:
    - 若 Agent 執行 `set_reminder` 工具成功，`message_handler.py` 會從 Agent 狀態中提取 `ReminderDetails`。
    - 將 `ReminderDetails` 傳遞給 `EventScheduler` 進行排程。
10. **提醒觸發**:
    - `EventScheduler` 觸發事件時，會呼叫 `message_handler.py` 中註冊的回調。
    - 回調函數會建構一個模擬的 `MsgNode`，並重新送回 Agent 處理，以生成提醒訊息。

### CLI 工作流程

```mermaid
flowchart TD
    A[CLI 啟動] --> B[載入型別安全配置]
    B --> C[顯示配置資訊]
    C --> D[互動選單]
    D --> E{用戶選擇}
    E -->|1| F[開始對話]
    E -->|2| G[調整工具輪次]
    E -->|3| H[顯示配置]
    E -->|4| I[退出]
    F --> J[創建 UnifiedAgent]
    J --> K[LangGraph 執行]
    K --> L[顯示結果]
    L --> M[繼續對話]
    M --> F
    G --> D
    H --> D
```

### Slash Command 工作流程 (`/wordle_hint`)

除了透過對話與 Agent 互動外，DCPersona 也支援特定的 Slash Commands，提供更直接的功能操作。

```mermaid
flowchart TD
    A[使用者執行 /wordle_hint] --> B[discord_bot/client.py]
    B --> C{解析日期 (可選)}
    C --> D[utils/wordle_service.py<br>獲取 Wordle 答案]
    D --> |成功| E[prompt_system/prompts.py<br>載入提示詞模板]
    D --> |失敗: 404/Timeout| F[回覆錯誤訊息]
    E --> G[呼叫 LLM 生成提示]
    G --> H[utils/wordle_service.py<br>safe_wordle_output<br>確保 Spoiler Tag]
    H --> I[回覆 Discord 提示]
```

**詳細步驟說明**:
1.  **指令觸發**: 使用者在 Discord 中執行 `/wordle_hint` 命令，可選擇性提供 `date` 參數。
2.  **指令處理**: `discord_bot/client.py` 中的 `DCPersonaBot` 實例接收並處理該指令。
3.  **日期解析**: 若使用者未提供日期，則使用系統預設時區的當前日期。
4.  **獲取答案**: 呼叫 `utils/wordle_service.py` 中的 `WordleService` 從 NYT API 獲取指定日期的 Wordle 答案。若 API 請求失敗則向使用者回覆錯誤訊息。
5.  **提示詞生成**: 使用 `PromptSystem` 載入 `wordle_hint_instructions.txt` 模板，並填入答案和 Persona 風格。
6.  **LLM 呼叫**: 呼叫 LLM 模型生成創意提示。
7.  **安全後處理**: 使用 `safe_wordle_output` 函數確保 LLM 的回覆包含 Discord Spoiler Tag (`||...||`)。
8.  **回覆使用者**: 將最終提示回覆到 Discord 頻道。

---

## 核心模組詳解

### agent_core/ - 統一 Agent 引擎

#### `graph.py` - LangGraph 核心實現
這是整個系統的核心，實現了基於 LangGraph 的智能代理：

**主要組件**:
- `UnifiedAgent`: 統一代理類，整合所有功能
- `generate_query_or_plan`: 智能計劃生成節點，LLM 在此決定是否呼叫工具。
- `execute_tools_node`: 負責解析 LLM 的 `tool_calls` 並執行對應的 LangChain 工具。
- `reflection`: 結果評估與反思節點
- `finalize_answer`: 最終答案生成節點

**關鍵特性**:
- **動態工具決策**: LangChain 模型根據對話上下文和工具描述，自動決定何時以及如何使用工具。
- **LangChain 工具整合**: 透過 `llm.bind_tools()` 將 `tools/` 目錄下的工具綁定到模型，實現自動化的提示詞注入和參數解析。
- **並行執行**: 支援同時執行多個搜尋查詢
- **智能反思**: 評估結果充分性，決定是否需要更多資訊
- **進度整合**: 內建進度通知機制

#### `progress_mixin.py` & `progress_observer.py` - 進度系統
實現了觀察者模式的進度通知系統：

- **解耦設計**: Agent 專注核心邏輯，進度處理獨立
- **多觀察者支援**: 可同時通知多個進度處理器
- **完整串流支援**: 整合 `on_streaming_chunk` 和 `on_streaming_complete` 方法
- **統一介面**: 提供標準化的進度觀察者介面，支援自定義實現
- **並行通知**: 支援並行通知所有註冊的觀察者，提高響應效率

### discord_bot/ - Discord 整合層

#### `message_handler.py` - 核心訊息處理器
負責 Discord 與 Agent 系統的橋接：

**主要功能**:
- 權限檢查與頻道過濾
- 訊息歷史收集協調
- Agent 實例管理
- 進度適配器註冊
- **事件排程與觸發**: 負責將 Agent 產生的提醒請求排程到 `EventScheduler`，並處理排程器觸發後的回調邏輯。

#### `message_collector.py` - 多模態訊息收集
處理複雜的訊息收集邏輯：

**支援功能**:
- **對話歷史**: 智能提取相關對話上下文
- **多模態內容**: 支援文字、圖片等多種輸入格式，圖片會被轉換為 Base64 編碼
- **訊息去重複與排序**: 根據訊息 ID 進行去重複，並依時間戳進行排序，確保上下文的準確性和時間順序
- **內容過濾**: 根據配置限制訊息長度和數量
- **結構化輸出**: 轉換為標準 `MsgNode` 格式

**重要型別**:
- `OverallState`: LangGraph 全域狀態
- `MsgNode`: 標準化訊息節點（支援多模態）
- `AgentPlan`: Agent 執行計劃
- `ReminderDetails`: 儲存提醒事件的詳細資訊（內容、時間、頻道 ID 等）。
- `ToolExecutionResult`: 標準化工具執行結果的資料結構，包含成功狀態和訊息。

#### `progress_adapter.py` - Discord 進度整合
實現 Discord 特定的進度顯示：

**功能特性**:
- **統一訊息管理**: 所有 Discord 訊息操作統一通過 ProgressManager 處理
- **智能串流支援**: 基於時間和內容長度的智能串流更新策略
- **即時進度更新**: 根據配置間隔更新 Discord 訊息
- **多階段支援**: 支援 starting、searching、analyzing、streaming、completed 等多種階段
- **狀態指示**: 使用表情符號和 embed 格式指示不同處理階段
- **錯誤處理**: 優雅處理網路異常和API限制，自動回退機制

#### `message_manager.py` - Discord 訊息快取管理
管理 Discord 訊息的快取和緩存：

**主要功能**:
- **訊息快取**: 儲存最近接收的訊息
- **緩存管理**: 管理訊息的過期和清理
- **性能優化**: 減少重複訊息處理

### schemas/ - 型別安全架構

#### `config_types.py` - 完整配置定義
定義了所有配置的型別安全結構：

**主要配置類**:
- `AppConfig`: 根配置類
- `AgentConfig`: Agent 行為配置
- `DiscordConfig`: Discord 相關設定
- `ToolConfig`: 工具配置與優先級
- `LLMConfig`: 多 LLM 實例配置

#### `agent_types.py` - Agent 核心型別
定義 Agent 系統的核心資料結構：

**重要型別**:
- `OverallState`: LangGraph 全域狀態
- `MsgNode`: 標準化訊息節點（支援多模態）
- `AgentPlan`: Agent 執行計劃
- `ToolPlan`: 個別工具執行計劃

---

## 多模態支援實現

### 圖片處理流程
本系統支援 Discord 圖片輸入的完整處理：

1. **圖片接收**: `message_collector.py` 收集 Discord 附件。
2. **Base64 編碼**: 將圖片轉換為 Base64 編碼，以供 LLM 可處理的格式。
3. **結構化儲存**: 使用 `MsgNode.content` 的 `List[Dict]` 格式儲存圖片內容。
4. **訊息去重複與排序**: 在轉換為 `MsgNode` 之前，根據訊息 ID 進行去重複，並根據時間戳進行排序。
5. **LLM 傳遞**: 直接將結構化內容傳遞給支援多模態的 LLM 模型。

6. **Emoji / Sticker 處理**: 透過 `image_processor` 解析訊息文字中的自定義 Emoji 與 Discord Sticker，並統一轉為圖片進行後續處理。

7. **動畫幀取樣**: 若檢測為 GIF/APNG/WebP 等動畫，使用 `sample_animated_frames` 均勻取樣幀數並轉換。

8. **Embed Media 與 VirtualAttachment**: 針對 `embed._thumbnail` 與 `embed.image` 的外部圖片 URL，封裝為 `VirtualAttachment` 進入統一附件流程，影片格式（mp4/webm）僅標記 TODO。

9. **媒體統計與摘要**: `message_collector` 會統計 emoji/sticker/靜態圖片/動畫數量並在訊息末尾附加 `[包含: ...]`，同時 `MULTIMODAL_GUIDANCE` 提示詞協助 LLM 解讀。

### 配置範例
```yaml
discord:
  limits:
    max_images: 5           # 最大圖片數量
    max_text: 8000         # 最大文字長度
    max_messages: 20       # 最大訊息歷史
  enable_conversation_history: true

streaming:
  enabled: true             # 啟用串流回應
  min_content_length: 50    # 最小串流內容長度

progress:
  discord:
    update_interval: 2.0    # 進度更新間隔（秒）
    use_embeds: true        # 使用 Discord embed 格式
```

---

## 工具系統 (Tool System)

本專案採用基於 LangChain 的標準化工具架構，確保了高度的可擴展性和模組化。所有工具都在 `tools/` 目錄下定義，並使用 `@tool` 裝飾器進行封裝。

### 架構特色
- **LangChain `@tool` 裝飾器**: 自動處理工具描述生成和參數 Schema 解析，簡化工具定義。
- **動態綁定**: 在 `UnifiedAgent` 中，透過 `llm.bind_tools()` 將工具動態綁定到語言模型，讓模型能夠自主決策。
- **標準化輸出**: 工具回傳 `ToolExecutionResult`，提供結構化的成功/失敗資訊，便於 Agent 進行後續處理。
- **中心化管理**: 所有工具集中在 `tools/` 目錄，職責清晰，易於維護和擴展。

### 現有工具介紹

#### 1. Google Search (`google_search`)
- **功能**: 提供即時的網路搜尋能力。當 Agent 需要獲取最新資訊、查證事實或研究特定主題時，會自動呼叫此工具。
- **使用方式**: Agent 自動觸發。當使用者提出需要外部知識的問題時 (例如 "今天天氣如何？" 或 "LangGraph 是什麼？")，Agent 會生成執行 `google_search` 的計畫。
- **檔案位置**: `tools/google_search.py`

#### 2. 設定提醒 (`set_reminder`)
- **功能**: 讓使用者可以設定一個未來的提醒。此工具能解析自然語言中的時間表達，並將提醒事件交由 `EventScheduler` 系統管理。
- **使用方式**: 使用者透過自然語言提出請求。
  - **範例**:
    - `"提醒我五分鐘後去開會"`
    - `"明天早上 9 點提醒我要交報告"`
    - `"下週一下午三點記得打電話"`
- **互動流程**:
  1. Agent 解析使用者意圖，呼叫 `set_reminder` 工具並傳入提醒內容與時間。
  2. 工具成功後，Agent 會回覆確認訊息，例如："好的，已為您設定提醒。"`
  3. 時間到達時，Bot 會在原始頻道發送提醒訊息。
- **檔案位置**: `tools/set_reminder.py`

---

## 配置系統特色

### 型別安全存取
```python
# 舊方式（已淘汰）
max_rounds = config.get("agent", {}).get("behavior", {}).get("max_tool_rounds", 3)

# 新方式（型別安全）
max_rounds = config.agent.behavior.max_tool_rounds
```

### 動態配置驗證
啟動時自動檢查：
- 必要欄位完整性
- 型別正確性
- 邏輯一致性（如工具啟用但缺少 API 金鑰）

---

## 測試與品質保證

### 測試覆蓋範圍
- **單元測試**: 各模組核心功能測試
- **整合測試**: Agent 流程端到端測試
- **配置測試**: 型別安全配置載入測試
- **串流測試**: 串流系統和智能更新策略測試
- **進度系統測試**: 進度觀察者和適配器功能測試

### 執行測試
```bash
# 執行所有測試
python -m pytest tests/ -v

# 串流系統測試
python -m pytest tests/test_streaming.py -v

# 進度系統測試
python -m pytest tests/test_phase2_progress.py -v

# CLI 功能測試
python cli_main.py

# Discord Bot 手動測試（需要配置）
python main.py
```

---

## 部署與維護

### 環境設定
1. **安裝依賴**: `pip install -r requirements.txt`
2. **配置文件**: 複製 `config-example.yaml` 為 `config.yaml`
3. **環境變數**: 設定 `GEMINI_API_KEY` 和 Discord Token
4. **權限配置**: 配置 Discord 頻道與使用者權限

### 監控與日誌
- **結構化日誌**: 使用標準 logging 模組
- **進度追蹤**: 內建進度觀察者系統
- **錯誤處理**: 多層次錯誤處理與降級機制

---

## 未來發展方向

### Phase 2 規劃功能
1. **Persona 系統整合**: 完整的人格化對話體驗
2. **擴展工具生態**: 更多專業工具整合
3. **性能優化**: 並行處理與快取機制
4. **多平台支援**: Telegram、Line 等平台整合

### 架構演進目標
- **微服務化**: 核心功能服務化部署
- **分散式處理**: 支援高並發使用場景
- **智能路由**: 根據問題類型智能分配處理資源

---

## 總結

DCPersona 採用現代化的型別安全架構和統一 Agent 設計，實現了高度可配置、可擴展的智能對話系統。透過 LangGraph 的強大流程控制能力，結合多模態輸入支援和即時進度回饋，為使用者提供了流暢且智能的互動體驗。

系統的模組化設計確保了優秀的可維護性，而型別安全的配置系統則大幅提升了開發效率和系統穩定性。未來將持續朝向更智能、更個性化的 AI 助手方向發展。✨
