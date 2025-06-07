<h1 align="center">
  llmcord
</h1>

<p align="center">
  <img src="https://github.com/jakobdylanc/llmcord/assets/38699060/789d49fe-ef5c-470e-b60e-48ac03057443" alt="llmcord banner">
</p>

<p align="center">
  <a href="https://github.com/jakobdylanc/llmcord/actions"><img src="https://img.shields.io/github/workflow/status/jakobdylanc/llmcord/CI?style=flat-square" alt="CI"></a>
  <a href="https://github.com/jakobdylanc/llmcord/stargazers"><img src="https://img.shields.io/github/stars/jakobdylanc/llmcord?style=flat-square" alt="Stars"></a>
  <a href="https://github.com/jakobdylanc/llmcord/blob/main/LICENSE.md"><img src="https://img.shields.io/github/license/jakobdylanc/llmcord?style=flat-square" alt="License"></a>
</p>

<h3 align="center"><i>
  Discord × LLM × 智能研究 × 互動體驗
</i></h3>

---

## 目錄

- [目錄](#目錄)
- [專案簡介](#專案簡介)
- [功能特色](#功能特色)
- [安裝與設定](#安裝與設定)
  - [1. 下載專案](#1-下載專案)
  - [2. 安裝依賴](#2-安裝依賴)
  - [3. 複製並編輯設定檔](#3-複製並編輯設定檔)
  - [4. 設定 Discord 與 API 金鑰](#4-設定-discord-與-api-金鑰)
- [使用方法](#使用方法)
  - [啟動 Bot](#啟動-bot)
  - [Discord 互動方式](#discord-互動方式)
    - [範例](#範例)
- [專案結構](#專案結構)
- [貢獻與支援](#貢獻與支援)
- [Star History](#star-history)

---

## 專案簡介

**llmcord** 將 Discord 變身為強大的 LLM 互動與智能研究平台。支援多種 LLM（OpenAI、Gemini、Ollama 等），並整合 LangGraph 智能研究系統，能根據問題自動切換簡單問答或多步驟研究模式，提供即時進度回報與多輪對話體驗。

---

## 功能特色

- **🌟 LangGraph 智能研究整合**
  - 自動判斷問題複雜度，啟動多步驟研究
  - 支援 `!research` 等關鍵字強制進入研究模式
  - 研究過程即時進度回報，30 秒超時自動降級
  - Discord 會話與研究狀態綁定，支援多輪追問

- **💬 多樣 LLM 支援**
  - OpenAI、xAI、Mistral、Groq、OpenRouter、Gemini、Ollama、LM Studio、vLLM 等
  - 支援 OpenAI API 相容服務

- **🔗 附件與多模態**
  - 支援圖片（vision model）、文字檔案等附件
  - 可自訂系統人格（persona）

- **⚡ 即時互動優化**
  - 研究啟動時顯示「🔍 正在進行深度研究...」
  - 每階段自動更新進度
  - 進度更新與降級機制，確保流暢體驗

- **🧠 複雜度評估與模式切換**
  - 自動評估問題複雜度，智慧切換回應流程
  - 可自訂複雜度閾值與觸發關鍵字

- **🛡️ 高效狀態管理**
  - 會話自動清理、狀態持久化
  - 多用戶多會話並行

- **🧪 完善測試與模組化架構**
  - agents/ 智能代理模組
  - tests/ 單元與整合測試

---

## 安裝與設定

### 1. 下載專案

```bash
git clone https://github.com/jakobdylanc/llmcord
cd llmcord
```

### 2. 安裝依賴

```bash
pip install -r requirements.txt
```

### 3. 複製並編輯設定檔

```bash
cp config-example.yaml config.yaml
```

### 4. 設定 Discord 與 API 金鑰

- **Discord Bot Token**：於 [Discord Developer Portal](https://discord.com/developers/applications) 建立 Bot，取得 `bot_token` 與 `client_id`，並啟用 MESSAGE CONTENT INTENT。
- **LLM API 金鑰**：於 `config.yaml` 設定各 LLM 服務的 API 金鑰（如 OpenAI、Gemini 等）。
- **LangGraph 智能研究**：
  ```yaml
  langgraph:
    enabled: true
    gemini_api_key: "YOUR_GEMINI_API_KEY"
    google_search_api_key: "YOUR_GOOGLE_SEARCH_API_KEY"
    google_search_engine_id: "YOUR_GOOGLE_SEARCH_ENGINE_ID"
  ```

詳細設定請參考 [`LANGGRAPH_INTEGRATION_GUIDE.md`](LANGGRAPH_INTEGRATION_GUIDE.md)。

---

## 使用方法

### 啟動 Bot

```bash
python main.py
```
或使用 Docker：
```bash
docker compose up
```

### Discord 互動方式

- **自動模式切換**：Bot 會根據訊息自動判斷是否進入研究模式
- **強制研究模式**：訊息前綴 `!research` 強制啟動多步驟研究
- **多輪對話**：支援基於會話的多輪追問與延續

#### 範例

- 簡單問答：
  ```
  用戶: 你好嗎？
  初華: 我很好呢 ✨ 謝謝妳的關心...
  ```
- 複雜研究：
  ```
  用戶: !research 請分析 2024 年 AI 發展趨勢
  初華: 🔍 讓我為妳進行深度研究...
  初華: 🤔 正在思考最佳的搜尋策略...
  初華: 📚 正在收集相關資料... (1/2)
  初華: 📝 正在整理答案... 馬上就好了 ✨
  初華: 根據我的研究，2024年AI發展呈現以下趨勢...
  ```

---

## 專案結構

```plaintext
llmcord/
│
├── main.py                  # 主程式入口
├── config.yaml              # 系統設定檔
├── persona/                 # 系統提示詞
│
├── core/
│   ├── config.py            # 設定管理
│   ├── logger.py            # 日誌系統
│   ├── utils.py             # 通用工具
│   └── session_manager.py   # 會話與狀態管理
│
├── agents/
│   ├── configuration.py     # 智能代理組態
│   ├── prompts.py           # 代理提示詞
│   ├── research_agent.py    # 研究型代理
│   ├── state.py             # 狀態管理
│   ├── tools_and_schemas.py # 工具與資料結構
│   └── utils.py             # 代理輔助工具
│
├── discordbot/
│   ├── client.py            # Discord client 初始化
│   ├── message_handler.py   # 訊息處理主流程
│   └── msg_node.py          # 訊息快取
│
├── pipeline/
│   ├── collector.py         # 訊息收集與預處理
│   ├── rag.py               # RAG 流程與 LangGraph 整合
│   ├── llm.py               # LLM 輸入組裝
│   └── postprocess.py       # 回覆後處理
│
├── tools/
│   └── google_search.py     # Google Search 工具
│
├── tests/
│   ├── test_progress_update.py
│   ├── test_embed_integration.py
│   ├── test_complexity_assessment.py
│   ├── test_integration.py
│   └── test_llm_complexity_integration.py
│
├── LANGGRAPH_INTEGRATION_GUIDE.md   # LangGraph 整合指南
├── llmcord_structure.md             # 專案結構說明
├── llmcord.py                       # 主要邏輯入口
├── README.md                        # 專案說明
├── requirements.txt                 # 依賴套件列表
└── ...（其他文件略）
```

---

## 貢獻與支援

- 歡迎提交 Issue 與 Pull Request，請遵循專案風格並附上測試
- 常見問題與故障排除請參考 [`LANGGRAPH_INTEGRATION_GUIDE.md`](LANGGRAPH_INTEGRATION_GUIDE.md)
- 有任何疑問歡迎於 GitHub 提出

---

## Star History

<a href="https://star-history.com/#jakobdylanc/llmcord&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=jakobdylanc/llmcord&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=jakobdylanc/llmcord&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=jakobdylanc/llmcord&type=Date" />
  </picture>
</a>

---

**llmcord 以 LangGraph 智能研究為核心，結合多層次代理架構與即時互動優化，讓初華能溫柔而堅定地陪伴妳，無論是簡單的問候還是複雜的研究，都能給妳最貼心的回應。✨**
