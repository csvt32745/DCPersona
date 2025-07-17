# DCPersona 專案守則

---

## 1. 專案檔案架構

```
DCPersona/
│
├── main.py                  # Discord Bot 主程式入口，初始化與啟動
├── cli_main.py              # CLI 測試介面，支援對話模式和配置調整
├── config-example.yaml      # 系統設定檔（型別安全配置）
├── emoji_config.yaml        # Emoji 系統配置檔（伺服器和應用程式 emoji）
├── personas/                # Agent 人格系統提示詞資料夾
│
├── tools/                   # LangChain 工具定義
│   ├── google_search.py     # Google 搜尋工具
│   ├── youtube_summary.py   # YouTube 摘要工具
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
│   ├── progress_types.py    # ProgressStage / ToolStatus 枚舉與符號映射
│   └── progress_mixin.py    # 進度更新混入（支援LLM智能進度訊息生成）
│
├── schemas/                 # 型別安全資料架構
│   ├── agent_types.py       # Agent 相關型別定義（狀態、計劃等）
│   ├── config_types.py      # 完整的型別安全配置定義
│   ├── emoji_types.py       # Emoji 系統型別定義（EmojiConfig）
│   └── __init__.py
│
├── prompt_system/           # 統一提示詞管理系統
│   ├── prompts.py           # 核心提示詞功能與 PromptSystem
│   ├── emoji_handler.py     # Emoji 處理器（智能建議與格式化）
│   └── tool_prompts/        # 工具相關提示詞模板
│       ├── wordle_hint_instructions.txt # Wordle 提示生成指令
│       └── wordle_hint_types/           # 提示風格模板 (多個 .txt)
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

## 2. 核心模組職責

1.  **`agent_core/` - 統一 Agent 引擎**:
    *   `graph.py`: LangGraph 核心實現，包含 `UnifiedAgent` 及其各階段節點（計劃生成、工具執行、反思、最終答案生成）。
    *   `progress_types.py`: 定義 `ProgressStage`、`ToolStatus` 枚舉與 `TOOL_STATUS_SYMBOLS`，提供型別安全且可配置的進度階段。
    *   `progress_mixin.py` & `progress_observer.py`: 實現觀察者模式的進度通知系統，支援解耦設計、多觀察者、完整串流支援和統一介面。

2.  **`tools/` - LangChain 工具定義**:
    *   `google_search.py`: 實作 Google 搜尋工具，用於網路查詢。
    *   `youtube_summary.py`: 實作 YouTube 影片摘要工具，用於為影片連結生成摘要。
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
    *   `emoji_types.py`: 定義 Emoji 系統的型別安全資料結構，包含 `EmojiConfig` dataclass 和 YAML 配置載入功能。

6.  **`prompt_system/` - 統一提示詞管理系統**:
    *   `prompts.py`: 管理核心提示詞功能和工具相關提示詞模板。
    *   `emoji_handler.py`: Emoji 智能處理系統，提供配置驅動的 emoji 建議、驗證和格式化功能，支援伺服器特定和應用程式 emoji。

7.  **`utils/` - 通用工具與配置**:
    *   包含型別安全配置載入器、日誌系統設定、通用輔助函式，並以 `image_processor.py` 提供 Emoji、Sticker、GIF/APNG/WebP 動畫與 Embed 圖片的載入、取樣、尺寸調整與 Base64 轉換功能。
    * `wordle_service.py`: 提供 Wordle 每日答案查詢和提示生成後的安全處理功能。

---

## 3. 主要工作流程步驟

### Discord Bot 工作流程

1.  **訊息接收**: `message_handler.py` 接收 Discord 事件。
2.  **權限檢查**: 驗證使用者權限和頻道設定。
3.  **訊息收集**: `message_collector.py` 收集對話歷史和圖片等多模態內容。
4.  **Agent 初始化**: 創建 `UnifiedAgent` 實例並配置進度觀察者，同時載入 `EmojiHandler` 提供 emoji 上下文。
5.  **LangGraph 執行**: 執行 `generate_query_or_plan` → `execute_tools` → `reflection` → `finalize_answer` 流程，其中 `execute_tools` 節點會呼叫 LangChain 工具（如 `set_reminder`）。
6.  **智能串流處理**: 在 `finalize_answer` 階段根據配置啟用串流回應，基於時間和內容長度智能更新。
7.  **統一進度管理**: 透過 `DiscordProgressAdapter` 和 `ProgressManager` 統一處理所有 Discord 訊息操作。
8.  **Emoji 提示**: 使用 `EmojiHandler` 在 LLM 提示中提供可用的 emoji 格式，LLM 直接生成正確的 Discord emoji 格式。
9.  **結果回覆**: 將最終答案格式化後回覆到 Discord，支援串流和非串流兩種模式。
10. **提醒排程**: 若 Agent 執行 `set_reminder` 工具成功，`message_handler.py` 會從 Agent 狀態中提取 `ReminderDetails`，並將其傳遞給 `event_scheduler/scheduler.py` 進行排程。
11. **提醒觸發**: 當 `event_scheduler/scheduler.py` 觸發提醒事件時，會呼叫 `message_handler.py` 中註冊的回調函數，該函數會建構一個模擬訊息，重新送回 Agent 處理以生成提醒內容，並最終發送至 Discord。

### Slash Command 工作流程 (`/wordle_hint`)
1.  **指令觸發**: 使用者在 Discord 中執行 `/wordle_hint` 命令，可選擇性提供 `date` 參數。
2.  **指令處理**: `discord_bot/client.py` 中的 `DCPersonaBot` 實例接收並處理該指令。
3.  **日期解析**: 若使用者未提供日期，則使用系統預設時區的當前日期。
4.  **獲取答案**: 呼叫 `utils/wordle_service.py` 中的 `WordleService` 從 NYT API 獲取指定日期的 Wordle 答案。
    - 若 API 請求失敗（如 404 或超時），則向使用者回覆錯誤訊息。
5.  **提示詞生成**:
    - 使用 `prompt_system/prompts.py` 中的 `PromptSystem` 載入 `wordle_hint_instructions.txt` 提示詞模板。
    - 將 Wordle 答案和 Persona 風格填入模板。
6.  **LLM 呼叫**: 實例化一個獨立的 `ChatGoogleGenerativeAI` 模型，並傳入格式化後的提示詞以生成創意提示。
7.  **安全後處理**: 使用 `utils/wordle_service.py` 中的 `safe_wordle_output` 函數，確保 LLM 的回覆包含 Discord Spoiler Tag (`||...||`)，並符合輸出格式。
8.  **回覆使用者**: 將包含 Spoiler Tag 的最終提示回覆到 Discord 頻道。

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

### Emoji / Sticker / Embed 多媒體擴充

6.  **Emoji / Sticker 處理**: 透過 `image_processor.parse_emoji_from_message()` 與 `load_from_discord_emoji_sticker()` 解析訊息文字與 Sticker 物件，並統一轉為圖片後處理。

7.  **動畫幀取樣**: 若檢測為動畫（`is_animated`），使用 `sample_animated_frames()` 均勻取樣幀數 (預設 4)。

8.  **Embed 圖片與 VirtualAttachment**: `message_collector` 從 `embed._thumbnail` / `embed.image` 提取 URL，封裝為 `VirtualAttachment`，與實際附件統一流程處理。

9.  **媒體統計與摘要標記**: `message_collector` 彙總 emoji/sticker/靜慶圖片/動畫數量，於訊息末尾附加 `[包含: 1個emoji, 2個動畫]`，並在 `prompt_system.prompts` 透過 `MULTIMODAL_GUIDANCE` 指導 LLM。