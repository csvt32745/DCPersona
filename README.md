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
- **文件處理**: 自動處理文字附件
- **結構化內容**: 標準化的多模態內容處理，包含訊息 ID 去重複和時間戳排序

### ⚡ 即時體驗
- **智能串流**: 基於時間和內容長度的智能串流策略
- **統一進度管理**: 觀察者模式的解耦進度系統，支援多平台適配
- **即時回應**: 逐字串流回應，即時進度更新和狀態同步
- **錯誤處理**: 優雅的降級和錯誤恢復機制，自動回退到同步模式

### 🛠️ 靈活架構
- **模組化設計**: 清晰的職責分離和低耦合
- **平台無關**: Discord 和 CLI 雙模式支援，統一的進度介面
- **易於擴展**: 標準化的工具和模組介面，支援自定義進度觀察者
- **統一管理**: 所有 Discord 訊息操作統一通過 ProgressManager 處理

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

---

## 專案架構

```plaintext
DCPersona/
│
├── main.py                  # Discord Bot 主程式入口
├── cli_main.py              # CLI 測試介面
├── config.yaml              # 型別安全配置檔
├── personas/                # Agent 人格系統提示詞
│
├── discord_bot/             # Discord 整合層
│   ├── client.py            # Discord Client 初始化
│   ├── message_handler.py   # 訊息事件處理
│   ├── message_collector.py # 多模態訊息收集
│   ├── progress_manager.py  # 進度消息管理
│   └── progress_adapter.py  # 進度適配器（串流支援）
│
├── agent_core/              # 統一 Agent 引擎
│   ├── graph.py             # LangGraph 核心實現
│   ├── agent_session.py     # 會話狀態管理
│   ├── agent_utils.py       # Agent 輔助函式
│   ├── progress_observer.py # 進度觀察者介面
│   └── progress_mixin.py    # 進度更新混入
│
├── schemas/                 # 型別安全架構
│   ├── agent_types.py       # Agent 核心型別
│   ├── config_types.py      # 配置型別定義
│   └── __init__.py
│
├── prompt_system/           # 提示詞管理
│   ├── prompts.py           # 核心提示詞功能
│   └── tool_prompts/        # 工具提示詞模板
│
├── utils/                   # 通用工具
│   ├── config_loader.py     # 型別安全配置載入
│   ├── logger.py            # 日誌系統
│   └── common_utils.py      # 通用輔助函式
│
└── tests/                   # 測試檔案
    └── ...                  # 單元與整合測試
```

詳細架構說明請參考 [`DCPersona_structure.md`](project_structure.md)

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
- **控制**: 可配置的串流啟用和內容長度閾值
- **進度管理**: 靈活的進度更新間隔和顯示模式

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