# llmcord 專案實作工作項目

本文件將 #file:llmcord.py 的現有功能，以及 #file:llmcord_structure.md 的重構目標，拆解為可執行的工作項目。

--- 

## Phase 1: 核心架構建立與流程佔位 (Core Architecture & Placeholder Flow)

**目標：** 建立新的檔案結構，將 `llmcord.py` 中的現有核心邏輯，平移至對應的模組中。對於 `llmcord.py` 中尚未完整實作的功能 (如 Google Search 的實際執行)，則建立 placeholder 函式，確保主要流程可以建立並測試。

### 1. `main.py` (專案啟動點)
   - **任務：**
     - 建立 `main()` 函式。
     - 呼叫 `core.config.load_config()` 載入設定。
     - 呼叫 `core.logger.setup_logger()` 初始化 logger。
     - 呼叫 `discordbot.client.create_discord_client()` 建立 Discord client。
     - 呼叫 `discordbot.message_handler.register_handlers()` 註冊事件處理器。
     - 使用 `cfg["bot_token"]` 啟動 Discord client。
   - **參考 `llmcord.py`：** `main()` 函式、`discord_client.start()`。

### 2. `core/config.py` (設定管理)
   - **任務：**
     - 建立 `load_config(filename="config.yaml")` 函式，讀取並回傳 `config.yaml` 內容。
     - (可選) `reload_config()` 函式。
   - **參考 `llmcord.py`：** `get_config()`。

### 3. `core/logger.py` (日誌設定)
   - **任務：**
     - 建立 `setup_logger(cfg)` 函式，根據設定檔初始化 `logging`。
   - **參考 `llmcord.py`：** `logging.basicConfig()` 部分。

### 4. `core/utils.py` (通用工具)
   - **任務：**
     - 建立 `random_system_prompt(root="persona")` 函式，隨機選擇 persona。
     - 建立 `get_prompt(filename)` 函式，讀取指定 prompt 檔案。
     - (可選) 移入其他可共用的輔助函式。
   - **參考 `llmcord.py`：** `random_system_prompt()`、`get_prompt()`。

### 5. `discordbot/client.py` (Discord Client 初始化)
   - **任務：**
     - 建立 `create_discord_client(cfg)` 函式。
     - 設定 `intents`。
     - 設定 `activity` (從 `cfg["status_message"]`)。
     - 回傳 `discord.Client` 實例。
   - **參考 `llmcord.py`：** `intents`、`activity`、`discord.Client()` 初始化部分。

### 6. `discordbot/msg_node.py` (訊息節點)
   - **任務：**
     - 定義 `MsgNode` dataclass，包含 `text`, `images`, `role`, `user_id`, `has_bad_attachments`, `fetch_parent_failed`, `parent_msg`, `lock` 等屬性。
     - 初始化 `msg_nodes = {}` 字典 (可考慮移至 `message_handler.py` 或作為 `MessageHandler` class 的屬性)。
     - 定義 `MAX_MESSAGE_NODES` 常數。
   - **參考 `llmcord.py`：** `MsgNode` class, `msg_nodes` dict, `MAX_MESSAGE_NODES`。

### 7. `discordbot/message_handler.py` (訊息處理主流程)
   - **任務：**
     - 建立 `on_message(new_msg: discord.Message)` 非同步函式。
     - **將 `llmcord.py` 中 `on_message` 的主要邏輯遷移至此，包括：**
       - DM 與提及檢查。
       - 權限檢查 (user, role, channel ID 黑白名單)。
       - 維護模式檢查。
       - 初始化 `AsyncOpenAI` client (可考慮移至 `pipeline/llm.py`)。
       - 模型能力判斷 (vision, username support)。
       - 設定限制 (max_text, max_images, max_messages)。
       - 呼叫 `pipeline.collector.collect_message()`。
       - 呼叫 `pipeline.llm.build_llm_input()`。
       - 呼叫 `pipeline.llm.call_llm_api()` (此階段會呼叫 `tools` 中的 placeholder)。
       - 呼叫 `pipeline.postprocess.format_llm_output_and_reply()` (或類似功能)。
       - `MsgNode` 快取管理 (刪除舊節點)。
     - 建立 `register_handlers(discord_client, cfg)` 函式，將 `on_message` 註冊到 `discord_client.event`。
   - **參考 `llmcord.py`：** `on_message` 完整邏輯。

### 8. `pipeline/collector.py` (訊息收集與預處理)
   - **任務：**
     - 建立 `collect_message(new_msg, cfg, discord_client_user, msg_nodes)` (或類似簽章) 函式。
     - **實作 `llmcord.py` `on_message` 中訊息鏈的建立邏輯：**
       - 處理 `new_msg` 的內容與附件。
       - 迭代處理 `parent_msg`，從 `msg_nodes` 快取或 `fetch_message`。
       - 處理歷史訊息 (`channel.history`)。
       - 處理圖片附件 (轉換為 base64，檢查數量限制)。
       - 組合訊息內容 (加入 user ID)。
       - 收集 `user_warnings`。
     - 回傳 `messages` 列表 (供 LLM 輸入) 和 `user_warnings` 集合。
   - **參考 `llmcord.py`：** `on_message` 中 `while curr_msg != None...` 迴圈及相關處理。

### 9. `pipeline/llm.py` (LLM 互動)
   - **任務：**
     - 建立 `build_llm_input(collected_messages, system_prompt_parts, cfg, discord_client_user_id)` 函式。
       - 組合 system prompt (加入日期時間、bot ID 等)。
       - 將 system prompt 加入 `messages` 列表。
       - 回傳最終的 `messages` 列表。
     - 建立 `call_llm_api(openai_client, model_name, messages, tools, cfg)` 非同步函式。
       - 執行 `openai_client.chat.completions.create()` 呼叫。
       - 處理 streaming 回應。
       - 處理 function calling (目前是 Google Search)。若 LLM 要求工具調用，則呼叫 `tools.google_search.perform_google_search` 的 placeholder。
       - 回傳 LLM 的回應內容和 `finish_reason`。
     - (可選) 初始化 `AsyncOpenAI` client 的邏輯移至此處。
     - 定義 `google_search_tool` (JSON structure for function calling)。
   - **參考 `llmcord.py`：** `system_prompt` 組合、`openai_client.chat.completions.create()` 呼叫、`google_search_tool`。

### 10. `pipeline/postprocess.py` (回覆後處理與發送)
    - **任務：**
      - 建立 `format_llm_output_and_reply(llm_response_content, finish_reason, new_msg, user_warnings, cfg, msg_nodes)` (或類似簽章) 非同步函式。
      - **實作 `llmcord.py` `on_message` 中回應處理和發送的邏輯：**
        - 處理 `user_warnings` 並建立 `discord.Embed`。
        - 根據 `use_plain_responses` 決定是否使用 embed。
        - 處理訊息長度限制，將長訊息分段發送。
        - 處理 streaming 回應的編輯 (`edit_task`)。
        - 將回應訊息存入 `msg_nodes`。
        - 實際發送/編輯 Discord 訊息 (`new_msg.reply`, `response_msg.edit`)。
    - **參考 `llmcord.py`：** `on_message` 中 `curr_content = finish_reason = edit_task = None` 之後的邏輯。

### 11. `tools/google_search.py` (Google Search 工具 - Placeholder)
    - **任務：**
      - 建立 `perform_google_search(query)` (或類似名稱) 非同步函式的 placeholder。
      - 此函式應能被 `pipeline.llm.call_llm_api` 安全地呼叫。
      - 在 Phase 1 中，此函式可以僅 `pass`、`return None`，或回傳一個固定的模擬結果/提示訊息，例如：`return "Google Search功能將在 Phase 2 中實作。"`。
      - 目的是確保 Phase 1 的整體流程可以呼叫此工具而不產生錯誤，即使功能尚未完整實作。
    - **參考 `llmcord.py`：** `google_search_tool` (了解參數定義)。

--- 

## Phase 2: 功能完整實作與進階 RAG (Full Implementation & Advanced RAG)

**目標：** 完整實作 Phase 1 中的 placeholder 功能，並擴展 RAG 能力。

### 1. 工具實作 (Tool Implementation)
   - **`tools/google_search.py`**
     - `perform_google_search(query)`：完整實作 Google 搜尋功能。
       - 接收查詢字串。
       - 使用合適的函式庫或 API 執行實際的 Google 搜尋。
       - 處理 API 回應，抽取相關資訊。
       - 回傳結構化的搜尋結果 (例如，摘要列表或相關網頁內容)，供 LLM 使用。

### 2. RAG 流程增強 (RAG Pipeline Enhancement)
   - **`pipeline/rag.py`**
     - `retrieve_augmented_context(message_data)`：
       - **整合已完整實作的 `tools.google_search.perform_google_search()`。**
       - (未來) 規劃並整合向量資料庫/知識庫檢索功能。
       - (未來) 規劃並整合知識圖譜查詢功能。
       - 回傳增強後的 context，供 `pipeline/llm.py` 用於組裝更豐富、更準確的 prompt。

### 3. 其他 `llmcord.py` 中未完全移植或需優化的部分
   - 檢視 `llmcord.py` 中是否有其他小型輔助函式或邏輯片段，在 Phase 1 未被明確分配，並將其整合到合適的模組中。
   - 根據 Phase 1 的運作情況，進行效能優化或錯誤處理的增強。

--- 

## 測試與驗證

- 每個模組/函式完成後，應進行單元測試 (可考慮使用 `pytest`)。
- Phase 1 完成後，進行整合測試，確保機器人基本對話、圖片處理、權限控制等功能，以及對工具 placeholder 的呼叫流程正常。
- Phase 2 各功能點完成後，進行對應的整合測試與端對端測試。

--- 

**注意事項：**
- 上述工作項目中的函式簽章僅為建議，可依實際需求調整。
- `llmcord.py` 中的全域變數 (如 `httpx_client`, `last_task_time`) 需要評估如何在新架構中管理，例如作為 class 屬性或透過參數傳遞。
- 錯誤處理和日誌記錄應貫穿所有模組。
