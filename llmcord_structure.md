# llmcord 專案重構建議

## 檔案結構

```
llmcord/
│
├── main.py                # 主程式入口，負責初始化及啟動 Discord bot
├── config.yaml            # 設定檔
├── persona/               # 系統提示詞（persona）資料夾
│
├── core/
│   ├── __init__.py
│   ├── config.py          # 設定檔讀取與管理
│   ├── logger.py          # 日誌系統設定
│   └── utils.py           # 通用工具函式 (如 persona 選擇、prompt 讀取)
│
├── discordbot/
│   ├── __init__.py
│   ├── client.py          # Discord client 初始化
│   ├── message_handler.py # 訊息事件處理主流程 (on_message)
│   └── msg_node.py        # MsgNode 類別定義與訊息快取相關邏輯
│
├── pipeline/
│   ├── __init__.py
│   ├── collector.py       # 訊息收集與預處理 (對話歷史、附件)
│   ├── rag.py             # RAG 流程 (未來擴展，如工具使用、知識庫檢索)
│   ├── llm.py             # LLM 輸入組裝與 API 呼叫
│   └── postprocess.py     # LLM 回覆的後處理與 Discord 訊息發送
│
└── tools/
    ├── __init__.py
    └── google_search.py   # Google Search 工具實作 (供 LLM function calling)
```

## 各檔案簡介

### main.py
專案的啟動點。執行此檔案以啟動機器人。
- 讀取設定檔 (`core.config`)
- 初始化日誌系統 (`core.logger`)
- 建立 Discord client (`discordbot.client`)
- 註冊訊息處理等事件 (`discordbot.message_handler`)
- 使用 bot token 連接並啟動 Discord bot

### core/
- `config.py`: 統一管理 `config.yaml` 的讀取與存取。
- `logger.py`: 集中化日誌設定，方便調整日誌級別與格式。
- `utils.py`: 放置通用小工具，例如隨機選擇 persona、讀取 prompt 檔案等。

### discordbot/
- `client.py`: 負責初始化 Discord client，包括設定 intents 和 activity。
- `message_handler.py`: 核心的訊息處理邏輯所在地。包含 `on_message` 事件處理函式，負責接收訊息、權限檢查，並將處理流程分派到 `pipeline` 中的各個模組。
- `msg_node.py`: 定義 `MsgNode` 資料結構，用於快取訊息內容、狀態及相關資訊，輔助對話歷史的建立與管理。

### pipeline/
此目錄下的模組構成訊息處理的主要流程。
- `collector.py`: 負責從 Discord 傳入的訊息中收集必要的資訊，包括文字內容、附件（圖片）、參考的訊息（上下文），並進行初步的格式化與清理。
- `rag.py`: 實現 RAG (Retrieval Augmented Generation) 的相關邏輯。現階段可能包含工具（如 Google Search）的整合準備，未來可擴展至向量資料庫檢索、知識圖譜查詢等，以增強 LLM 的回應內容。
- `llm.py`: 負責組裝最終提交給 LLM 的輸入（通常是一個訊息列表），並呼叫 LLM API（例如 OpenAI API）以獲取模型的回應。處理 LLM 的 function calling 機制也在此模組。
- `postprocess.py`: 將從 LLM 收到的原始輸出進行處理，例如文字分段、格式化（如 Markdown）、錯誤處理，並將最終結果透過 Discord API 回覆給使用者。

### tools/
- `google_search.py`: 實作 Google Search 的具體功能。當 LLM 決定使用 Google Search 工具時，會呼叫此處定義的函式。
