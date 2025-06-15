# DCPersona 專案守則

---

## 1. 專案檔案架構

```
DCPersona/
│
├── main.py                  # Discord Bot 主程式入口，初始化與啟動
├── cli_main.py              # CLI 測試介面，支援對話模式和配置調整
├── config-example.yaml              # 系統設定檔（型別安全配置）
├── personas/                # Agent 人格系統提示詞資料夾
│
├── tools/                   # LangChain 工具定義
│   ├── google_search.py     # Google 搜尋工具
│   └── set_reminder.py      # 設定提醒工具
│
├── event_scheduler/         # 通用事件排程系統
│   └── scheduler.py         # 排程器核心
│
├── discord_bot/             # Discord 整合層
│   ├── client.py            # Discord Client 初始化與設定
│   ├── message_handler.py   # Discord 訊息事件處理主流程
│   ├── message_collector.py # 訊息收集、歷史處理與多模態支援
│   ├── progress_manager.py  # Discord 進度消息管理系統
│   ├── progress_adapter.py  # Discord 進度適配器（支援串流回應）
│   └── message_manager.py   # Discord 訊息快取管理
│
├── agent_core/              # 統一 Agent 處理引擎
│   ├── graph.py             # LangGraph 構建與 Agent 節點實現
│   ├── agent_utils.py       # Agent 核心輔助函式
│   ├── progress_observer.py # 進度觀察者介面（支援串流）
│   └── progress_mixin.py    # 進度更新混入（整合串流功能）
│
├── schemas/                 # 型別安全資料架構
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
│   └── __init__.py
│
└── tests/                   # 測試檔案
    └── ...                  # 各種單元測試與整合測試
```

---

## 2. 核心模組職責

1.  **`agent_core/` - 統一 Agent 引擎**:
    *   `graph.py`: LangGraph 核心實現，包含 `UnifiedAgent` 及其各階段節點（計劃生成、工具執行、反思、最終答案生成）。
    *   `progress_mixin.py` & `progress_observer.py`: 實現觀察者模式的進度通知系統，支援解耦設計、多觀察者、完整串流支援和統一介面。

2.  **`tools/` - LangChain 工具定義**:
    *   `google_search.py`: 實作 Google 搜尋工具，用於網路查詢。
    *   `set_reminder.py`: 實作設定提醒工具，用於處理時間解析和提醒排程。

3.  **`event_scheduler/` - 通用事件排程系統**:
    *   `scheduler.py`: 通用排程器核心，負責初始化和管理 `APScheduler`，提供事件的排程、持久化和觸發回調機制。

4.  **`discord_bot/` - Discord 整合層**:
    *   `message_handler.py`: 核心訊息處理器，負責 Discord 與 Agent 系統的橋接，包括權限檢查、訊息歷史收集協調、Agent 實例管理，並處理提醒排程和觸發邏輯。
    *   `message_collector.py`: 處理複雜的訊息收集邏輯，支援對話歷史、多模態內容（圖片轉 Base64）、訊息去重複與排序。
    *   `progress_adapter.py`: Discord 進度整合，實現統一訊息管理、智能串流支援、即時進度更新和多階段狀態指示。
    *   `message_manager.py`: 管理 Discord 訊息的快取和緩存，用於性能優化。

5.  **`schemas/` - 型別安全資料架構**:
    *   `config_types.py`: 定義所有配置的型別安全結構，確保嚴格型別檢查和配置驗證。
    *   `agent_types.py`: 定義 Agent 系統的核心資料結構，如 `OverallState`、`MsgNode`、`AgentPlan`、`ReminderDetails` 和 `ToolExecutionResult`。

6.  **`prompt_system/` - 統一提示詞管理系統**:
    *   管理核心提示詞功能和工具相關提示詞模板。

7.  **`utils/` - 通用工具與配置**:
    *   包含型別安全配置載入器、日誌系統設定和通用輔助函式。

---

## 3. 主要工作流程步驟

### Discord Bot 工作流程

1.  **訊息接收**: `message_handler.py` 接收 Discord 事件。
2.  **權限檢查**: 驗證使用者權限和頻道設定。
3.  **訊息收集**: `message_collector.py` 收集對話歷史和圖片等多模態內容。
4.  **Agent 初始化**: 創建 `UnifiedAgent` 實例並配置進度觀察者。
5.  **LangGraph 執行**: 執行 `generate_query_or_plan` → `execute_tools` → `reflection` → `finalize_answer` 流程，其中 `execute_tools` 節點會呼叫 LangChain 工具（如 `set_reminder`）。
6.  **智能串流處理**: 在 `finalize_answer` 階段根據配置啟用串流回應，基於時間和內容長度智能更新。
7.  **統一進度管理**: 透過 `DiscordProgressAdapter` 和 `ProgressManager` 統一處理所有 Discord 訊息操作。
8.  **結果回覆**: 將最終答案格式化後回覆到 Discord，支援串流和非串流兩種模式。
9.  **提醒排程**: 若 Agent 執行 `set_reminder` 工具成功，`message_handler.py` 會從 Agent 狀態中提取 `ReminderDetails`，並將其傳遞給 `event_scheduler/scheduler.py` 進行排程。
10. **提醒觸發**: 當 `event_scheduler/scheduler.py` 觸發提醒事件時，會呼叫 `message_handler.py` 中註冊的回調函數，該函數會建構一個模擬訊息，重新送回 Agent 處理以生成提醒內容，並最終發送至 Discord。

### CLI 工作流程

1.  **CLI 啟動**。
2.  **載入型別安全配置**。
3.  **顯示配置資訊**。
4.  **進入互動選單**。
5.  **用戶選擇**：
    *   選擇 `1` 進入開始對話模式。
    *   選擇 `2` 調整工具輪次。
    *   選擇 `3` 顯示配置。
    *   選擇 `4` 退出。
6.  **對話模式**: 創建 `UnifiedAgent`，執行 LangGraph，顯示結果並可繼續對話。

### 圖片處理流程

1.  **圖片接收**: `message_collector.py` 收集 Discord 附件。
2.  **Base64 編碼**: 將圖片轉換為 Base64 編碼，以供 LLM 可處理的格式。
3.  **結構化儲存**: 使用 `MsgNode.content` 的 `List[Dict]` 格式儲存圖片內容。
4.  **訊息去重複與排序**: 在轉換為 `MsgNode` 之前，根據訊息 ID 進行去重複，並根據時間戳進行排序。
5.  **LLM 傳遞**: 直接將結構化內容傳遞給支援多模態的 LLM 模型。 