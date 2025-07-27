<h1 align="center">
  DCPersona
</h1>

<h3 align="center"><i>
  Discord × LangGraph × 統一 Agent × 多模態智能對話
</i></h3>

---

## 目錄

- [目錄](#目錄)
- [專案簡介](#專案簡介)
- [核心特色](#核心特色)
  - [🤖 統一 Agent 架構](#-統一-agent-架構)
  - [🔧 型別安全設計](#-型別安全設計)
  - [🌐 多模態支援](#-多模態支援)
  - [⚡ 即時體驗](#-即時體驗)
  - [🛠️ 靈活架構](#️-靈活架構)
- [安裝與設定](#安裝與設定)
  - [1. 下載專案](#1-下載專案)
  - [2. 安裝依賴](#2-安裝依賴)
  - [3. 設定環境變數](#3-設定環境變數)
  - [4. 複製並編輯設定檔](#4-複製並編輯設定檔)
  - [5. 設定 Discord Bot](#5-設定-discord-bot)
- [使用方法](#使用方法)
  - [啟動 Discord Bot](#啟動-discord-bot)
  - [CLI 測試介面](#cli-測試介面)
  - [Discord 互動方式](#discord-互動方式)
- [專案架構](#專案架構)
- [工具系統 (Tool System)](#工具系統-tool-system)
  - [支援工具](#支援工具)
    - [🌐 Google Search](#-google-search)
    - [⏰ 設定提醒 (`set_reminder`)](#-設定提醒-set_reminder)
    - [📺 YouTube 摘要 (`youtube_summary`)](#-youtube-摘要-youtube_summary)
- [Slash Commands](#slash-commands)
  - [🧩 Wordle 每日提示 (`/wordle_hint`)](#-wordle-每日提示-wordle_hint)
- [配置系統](#配置系統)
  - [配置特色](#配置特色)
- [測試](#測試)
  - [執行測試](#執行測試)
  - [測試覆蓋](#測試覆蓋)
- [部署](#部署)
  - [Docker 部署](#docker-部署)

---

## 專案簡介

**DCPersona** 是一個現代化的 Discord AI 助手，採用統一 Agent 架構和型別安全設計。基於 LangGraph 的智能工作流程，支援多模態輸入（文字、圖片）、智能工具決策和即時串流回應，為使用者提供流暢且智能的對話體驗。

---

## 核心特色

### 🤖 統一 Agent 架構
- **配置驅動**: 透過 `config.yaml` 動態調整 Agent 行為
- **智能決策**: 根據問題複雜度自動選擇工具和策略
- **LangGraph 整合**: 多步驟推理與工具協調
- **多輪對話**: 完整的對話上下文管理

### 🔧 型別安全設計
- **完全型別安全**: 消除字串 key 存取，使用 dataclass 配置
- **配置驗證**: 啟動時自動檢查配置完整性
- **IDE 支援**: 完整的 IntelliSense 和自動完成

### 🌐 多模態支援
- **圖片理解**: 支援 Discord 圖片輸入和 Vision 模型，並將圖片內容轉換為 Base64 編碼以供 LLM 處理
- **Emoji / Sticker / 動畫**: 內建 `image_processor` 模組，完整支援自定義 Emoji、Discord Sticker（PNG/APNG/GIF/WebP）與 GIF/APNG/WebP 動畫（含幀取樣）。
- **輸入/輸出媒體管線**:
  - **Input**: `message_collector` 結合 `InputMediaConfig` 和 `input_emoji_cache` 解析用戶訊息中的媒體。
  - **Output**: `output_media` 模組（`EmojiRegistry`, `OutputStickerRegistry`, `OutputMediaContextBuilder`）負責生成 Bot 回覆的媒體內容和提示上下文。
- **智能 Emoji 輔助**: 配置驅動的 emoji 系統，根據伺服器上下文智能建議 emoji，LLM 直接生成正確的 Discord 格式，Wordle 提示功能也支援此功能，使提示更生動有趣。
- **Emoji 防呆補償**: 自動修復 LLM 輸出的常見 emoji 格式錯誤，包含 `:name:` → `<:name:id>`、`<:name:>` → `<:name:id>`、`<a:name:>` → `<a:name:id>` 等格式，確保 Discord 能正確顯示 emoji。
- **Embed Media 支援**: 自動偵測 `embed._thumbnail` / `embed.image` 的外部圖片 URL，封裝為 VirtualAttachment 與附件流程統一。
- **媒體統計與摘要**: `message_collector` 會統計 emoji/sticker/靜態/動畫圖片數量並於訊息末尾附加 `[包含: ...]` 標記，`MULTIMODAL_GUIDANCE` 提示詞協助 LLM 解讀。
- **文件處理**: 自動處理文字附件
- **結構化內容**: 標準化的多模態內容處理，包含訊息 ID 去重複和時間戳排序

### ⚡ 即時體驗
- **智能串流**: 基於時間和內容長度的智能串流策略
- **智能進度訊息**: LLM 自動生成個性化進度訊息，可透過配置啟用/關閉
- **統一進度管理**: 觀察者模式的解耦進度系統，支援多平台適配
- **即時回應**: 逐字串流回應，即時進度更新和狀態同步
- **錯誤處理**: 優雅的降級和錯誤恢復機制，自動回退到同步模式

### 🛠️ 靈活架構
- **模組化設計**: 清晰的職責分離和低耦合
- **平台無關**: Discord 和 CLI 雙模式支援，統一的進度介面
- **易於擴展**: 標準化的工具和模組介面，支援自定義進度觀察者
- **統一管理**: 所有 Discord 訊息操作統一通過 ProgressManager 處理

### 🎭 智能跟風系統
- **Reaction 跟風**: 當訊息 reaction 達到閾值時，Bot 自動添加相同 reaction
- **內容跟風**: 檢測連續相同訊息（文字或 sticker）並自動複製
- **Emoji 跟風**: 識別連續 emoji 訊息並使用 LLM 生成適合的 emoji 回應
- **防循環機制**: 內建 Bot 參與檢測，避免無限循環跟風
- **🎲 機率性跟風**: 可配置的機率決策系統，基礎機率 50%，隨活躍度提升至 95%，創造更自然的互動體驗
- **動態調整**: 根據訊息頻率動態調整跟風機率，活躍討論時更容易觸發
- **頻道級控制**: 支援特定頻道啟用，配置冷卻時間防止過度回應

---

## 安裝與設定

### 1. 下載專案

```bash
git clone https://github.com/csvt32745/DCPersona
cd DCPersona
```

### 2. 安裝依賴

```bash
pip install -r requirements.txt
```

### 3. 設定環境變數

```bash
cp env.example .env
```

編輯 `.env` 文件，設定必要的 API 金鑰：

```bash
# Gemini API 金鑰 (必需)
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. 複製並編輯設定檔

```bash
cp config-example.yaml config.yaml
cp emoji_config-example.yaml emoji_config.yaml
```

### 5. 設定 Discord Bot

- 於 [Discord Developer Portal](https://discord.com/developers/applications) 建立 Bot
- 取得 `bot_token` 並設定到 `config.yaml` 文件
- 啟用 **MESSAGE CONTENT INTENT**
- 配置 Bot 權限和頻道存取

---

## 使用方法

### 啟動 Discord Bot

```bash
python main.py
```

或使用 Docker：
```bash
docker compose up
```

### CLI 測試介面

```bash
python cli_main.py
```

CLI 模式提供：
- 互動式對話測試
- 配置參數動態調整
- 除錯和開發支援

### Discord 互動方式

- **自然對話**: 直接與 Bot 對話，支援文字和圖片
- **多輪對話**: 保持對話上下文，支援連續提問
- **智能研究**: 複雜問題自動啟動多步驟搜尋和分析
- **設定提醒**: 透過 "提醒我..."、"設定提醒..." 等自然語言來設定排程
- **智能跟風**: Bot 會自動偵測頻道中的跟風模式並參與其中

---

## 專案架構

```plaintext
DCPersona/
│
├── main.py                  # Discord Bot 主程式入口
├── cli_main.py              # CLI 測試介面
├── config.yaml              # 型別安全配置檔
├── emoji_config.yaml        # Emoji 系統配置檔
├── tools/                   # LangChain 工具定義
│   ├── google_search.py     # Google 搜尋工具
│   ├── youtube_summary.py   # YouTube 摘要工具
│   └── set_reminder.py      # 設定提醒工具
│
├── event_scheduler/         # 通用事件排程系統
│   └── scheduler.py         # 排程器核心
│
├── personas/                # Agent 人格系統提示詞
│
├── discord_bot/             # Discord 整合層
│   ├── client.py            # Discord Client 初始化
│   ├── commands/            # Slash Command 定義 (自動掃描並集中註冊)
│   ├── message_handler.py   # 訊息事件處理
│   ├── message_collector.py # 多模態訊息收集 (Input)
│   ├── progress_manager.py  # 進度消息管理
│   ├── progress_adapter.py  # 進度適配器（串流支援）
│   └── trend_following.py   # 跟風功能處理器
│
├── output_media/            # ✨ 輸出媒體管線 (Output)
│   ├── emoji_registry.py    # Emoji 註冊與格式化
│   ├── sticker_registry.py  # Sticker 註冊 (預留)
│   ├── context_builder.py   # 媒體提示上下文建構 + Emoji 格式防呆補償
│   └── emoji_types.py       # Emoji 系統型別定義
│
├── agent_core/              # 統一 Agent 引擎
│   ├── graph.py             # LangGraph 核心實現
│   ├── agent_utils.py       # Agent 輔助函式
│   ├── progress_observer.py # 進度觀察者介面
│   ├── progress_mixin.py    # 進度更新混入 (支援LLM進度訊息生成)
│   └── progress_types.py    # 進度型別定義
│
├── schemas/                 # 型別安全架構
│   ├── agent_types.py       # Agent 核心型別
│   ├── config_types.py      # 配置型別定義
│   ├── input_media_config.py # ✨ 輸入媒體配置型別
│   └── __init__.py
│
├── prompt_system/           # 提示詞管理
│   ├── prompts.py           # 核心提示詞功能
│   ├── emoji_handler.py     # Emoji 處理器 (智能建議與格式化)
│   └── tool_prompts/        # 工具提示詞模板
│
├── utils/                   # 通用工具
│   ├── config_loader.py     # 型別安全配置載入
│   ├── logger.py            # 日誌系統
│   ├── common_utils.py      # 通用輔助函式
│   ├── image_processor.py   # 圖片 / Emoji / Sticker / 動畫處理核心
│   ├── input_emoji_cache.py # ✨ 輸入 Emoji 快取
│   ├── wordle_service.py    # Wordle 遊戲提示服務
│   └── __init__.py
│
│
└── tests/                   # 測試檔案
    ├── test_emoji_system.py # Emoji 系統完整測試 (21 項測試)
    └── ...                  # 單元與整合測試
```

詳細架構說明請參考 [`project_structure.md`](project_structure.md)

---

## 工具系統 (Tool System)

DCPersona 透過 LangChain 的工具系統，賦予 Agent 與外部世界互動的能力。

### 支援工具

#### 🌐 Google Search
- **功能**: 提供即時的網路搜尋能力，用於回答需要最新資訊或外部知識的問題。
- **觸發方式**: 當使用者提問內容涉及 Agent 自身知識庫以外的資訊時，將自動觸發。

#### ⏰ 設定提醒 (`set_reminder`)
- **功能**: 讓使用者可以透過自然語言設定提醒。
- **使用範例**:
  - `"提醒我 10 分鐘後喝水"`
  - `"明天早上九點提醒我開會"`
- **運作方式**: Agent 解析時間和提醒內容後，將其交由內建的事件排程系統處理，並在指定時間到達時發送通知。

#### 📺 YouTube 摘要 (`youtube_summary`)
- **功能**: 自動偵測 YouTube 影片連結並生成摘要。
- **觸發方式**: 當訊息中出現 YouTube 影片 URL 時，Agent 會在背景呼叫此工具並將摘要插入回覆。
- **使用範例**:
  - `https://youtu.be/pmNP54vTlxg 這部影片在講什麼？`
- **運作方式**: 工具將影片 URI 傳入 Gemini API 取得核心內容摘要，結果將納入 Agent 回覆中。

---

## Slash Commands

除了透過對話與 Agent 互動，DCPersona 也提供方便的 Slash Commands 來執行特定功能。

### 🧩 Wordle 每日提示 (`/wordle_hint`)
- **功能**: 獲取當日或指定日期的 Wordle 遊戲提示，並由 LLM 生成富有趣味的創意線索。此功能支援智能 Emoji 輸出，LLM 會根據當前伺服器的可用 emoji 上下文，在提示中適當使用 emoji，使提示更生動有趣。
- **特色**:
  - **即時互動**: 無需等待 Agent 回應，指令立即觸發。
  - **多樣化風格**: 提示風格已模組化，所有風格模板位於 `prompt_system/tool_prompts/wordle_hint_types/`，Bot 會隨機選擇一種風格並注入至主提示詞。
  - **自我驗證**: LLM 會在 `<check>...</check>` 區塊中逐句說明提示與答案的關聯性；Bot 會自動將其轉換成 `題解:\n|| ... ||` 形式並隱藏於 Spoiler 中，方便需要時查看。
  - **隱私防雷**: 任意 `<check>...</check>` 心理描寫區塊會被轉換為 `|| ... ||` Spoiler，答案同樣使用 Discord Spoiler Tag (`||答案||`) 包裹，避免意外暴雷。
- **使用範例**:
  - `/wordle_hint`：獲取今天的 Wordle 提示。
  - `/wordle_hint date:2024-05-20`：獲取特定日期的提示。


> 註：所有 Slash Command 由 `register_commands(bot)` 於啟動階段自動註冊，無需手動新增。

---

## 配置系統

DCPersona 採用完全型別安全的配置系統：

```yaml
# config.yaml 範例
agent:
  behavior:
    max_tool_rounds: 3
    enable_reflection: true
    enable_progress: true
  
  tools:
    google_search:
      enabled: true
      priority: 1

streaming:
  enabled: true
  min_content_length: 50

progress:
  discord:
    update_interval: 2.0
    use_embeds: true
    auto_generate_messages: true  # 啟用LLM智能進度訊息生成

llm:
  models:
    progress_msg:
      model: "gemini-2.0-flash-lite"
      temperature: 0.4
      max_output_tokens: 20  # 嚴格限制進度訊息長度

trend_following:
  enabled: true
  allowed_channels: []  # 空表示所有頻道
  cooldown_seconds: 60
  reaction_threshold: 3
  content_threshold: 2
  emoji_threshold: 3

discord:
  limits:
    max_text: 8000
    max_images: 5
    max_messages: 20
  enable_conversation_history: true
```

### 配置特色
- **型別安全**: 使用 dataclass 而非字典存取
- **自動驗證**: 啟動時檢查配置完整性
- **智能進度訊息**: 支援 LLM 自動生成進度訊息，可透過 `auto_generate_messages` 啟用/關閉
- **串流控制**: 可配置的串流啟用和內容長度閾值
- **跟風系統**: 靈活的跟風閾值和冷卻設定，支援頻道級控制
- **進度管理**: 靈活的進度更新間隔和顯示模式，並可在 `progress.discord.messages` 透過對應 `ProgressStage` key 來自訂文字/emoji（含新加入的 `tool_status` 階段）

   **範例**：

   ```yaml
   progress:
     discord:
       messages:
         starting: "🔄 正在處理您的訊息..."
         searching: "🔍 正在搜尋資料..."
         tool_status: "🔧 正在平行執行工具..."  # 新增，可在此自訂
   ```

- **型別安全配置**: 透過 `config.yaml` 管理系統核心配置，提供嚴格的型別檢查和自動驗證。
- **Emoji 配置**: 專用的 `emoji_config.yaml` 管理所有應用程式和伺服器專屬的 Emoji，支援智能建議與格式化。
    ```yaml
    # 應用程式通用 Emojis
    application:
      1362820638489972937: "裝可愛，招牌表情"

    # 伺服器專屬 Emojis  
    730024186852147240:
      791232834697953330: "好笑青蛙"
      959699262587928586: "得意 =w= 烏龜"
    ```
     描述（例如：裝可愛，招牌表情）將會作為上下文資訊提供給 Agent，理解每個 emoji 的含義與適用情境

---

## 測試

### 執行測試

```bash
# 執行所有測試
python -m pytest tests/ -v

# 特定測試
python -m pytest tests/test_phase2_progress.py -v
```

### 測試覆蓋
- **單元測試**: 各模組核心功能
- **整合測試**: Agent 端到端流程
- **配置測試**: 型別安全配置載入
- **串流測試**: 串流系統和進度管理功能
- **Emoji 系統測試**: 完整的 emoji 配置、處理和整合測試 (21 項測試)

---

## 部署

### Docker 部署

```bash
# 建立映像
docker build -t dcpersona .

# 啟動容器
docker compose up -d
```

---

**DCPersona 採用現代化架構設計，結合 LangGraph 智能工作流程、統一串流系統和型別安全配置，為您打造最佳的 Discord AI 助手體驗。✨**