# LangGraph 整合指南

## 概述

本指南說明如何在 llmcord Discord bot 中使用新整合的 LangGraph 智能研究功能。這個整合提供了強大的多步驟研究能力，能夠自動判斷問題複雜度並選擇最適合的回應策略。

## 🌟 主要功能

### 智能模式切換
- **簡單問答**：使用傳統 LLM 流程，快速回應
- **複雜研究**：自動啟動 LangGraph 多步驟研究
- **強制模式**：支援用戶使用 `!research` 前綴強制啟動研究模式

### 即時互動優化
- 研究開始時發送 "🔍 正在進行深度研究..."
- 每個階段完成後更新進度
- 30秒超時降級機制

### 狀態管理
- Discord 會話與 LangGraph 狀態綁定
- 支援多輪對話追問
- 自動清理過期會話

## 🛠️ 安裝和配置

### 1. 安裝依賴

```bash
cd llmcord
pip install -r requirements.txt
```

### 2. 配置 API 金鑰

複製並編輯配置檔案：

```bash
cp config-example.yaml config.yaml
```

在 `config.yaml` 中設定以下必要的 API 金鑰：

```yaml
# Gemini API 配置
providers:
  gemini:
    api_key: "YOUR_GEMINI_API_KEY"

# LangGraph 智能研究配置
langgraph:
  enabled: true
  gemini_api_key: "YOUR_GEMINI_API_KEY"
  google_search_api_key: "YOUR_GOOGLE_SEARCH_API_KEY"
  google_search_engine_id: "YOUR_GOOGLE_SEARCH_ENGINE_ID"
```

### 3. 獲取必要的 API 金鑰

#### Gemini API 金鑰
1. 前往 [Google AI Studio](https://makersuite.google.com/)
2. 創建新的 API 金鑰
3. 複製金鑰到配置檔案

#### Google Search API 金鑰
1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 啟用 Custom Search API
3. 創建憑證並獲取 API 金鑰
4. 創建自訂搜尋引擎並獲取引擎 ID

## ⚙️ 配置選項

### 基本配置

```yaml
langgraph:
  enabled: true  # 啟用智能研究功能
  
  # 研究行為配置
  initial_queries: 2  # 初始搜尋查詢數量
  max_loops: 1  # 最大研究循環次數
  timeout: 30  # 研究超時時間（秒）
  
  # 智能模式切換
  complexity_threshold: 0.4  # 複雜度閾值（0-1）
  force_research_keywords:  # 強制研究模式關鍵字
    - "研究"
    - "調查"
    - "分析"
    - "!research"
```

### 進階配置

```yaml
langgraph:
  # Discord 體驗優化
  progress_updates: true  # 啟用進度更新訊息
  fallback: true  # 啟用降級機制
  simple_max_tokens: 1000  # 簡單回應最大 token 數
  
  # 會話管理
  session_timeout_hours: 24  # 會話超時時間
  cleanup_interval: 3600  # 清理間隔（秒）
  
  # 模型配置
  models:
    query_generator: "gemini-2.0-flash-exp"
    reflection: "gemini-2.0-flash-exp"
    answer: "gemini-2.0-flash-exp"
```

## 🚀 使用方法

### 啟動 Bot

```bash
cd llmcord
python main.py
```

### Discord 中的使用

#### 1. 自動模式切換

Bot 會自動判斷問題複雜度：

**簡單問題（使用傳統流程）：**
```
用戶: 你好嗎？
初華: 我很好呢 ✨ 謝謝妳的關心...
```

**複雜問題（自動啟動研究模式）：**
```
用戶: 請分析 2024 年 AI 發展的最新趨勢
初華: 🔍 讓我為妳進行深度研究...
初華: 🤔 正在思考最佳的搜尋策略...
初華: 📚 正在收集相關資料... (1/2)
初華: 📝 正在整理答案... 馬上就好了 ✨
初華: 根據我的研究，2024年AI發展呈現以下趨勢...
      [詳細的研究結果和來源引用]
```

#### 2. 強制研究模式

使用特殊前綴強制啟動研究：

```
用戶: !research 台北今天的天氣
初華: 🔍 讓我為妳進行深度研究...
```

#### 3. 多輪對話

支援基於會話的多輪對話：

```
用戶: 請研究電動車市場
初華: [進行研究並回應]

用戶: 那台灣的情況呢？
初華: [基於之前會話繼續研究台灣電動車市場]
```

## 🔧 故障排除

### 常見問題

#### 1. API 金鑰錯誤
**症狀**：研究功能無法啟動，日誌顯示 API 錯誤
**解決方案**：
- 檢查 `config.yaml` 中的 API 金鑰是否正確
- 確認 Gemini API 金鑰有效且有足夠配額
- 驗證 Google Search API 啟用且有權限

#### 2. 研究超時
**症狀**：研究過程中顯示超時訊息
**解決方案**：
- 調整 `langgraph.timeout` 設定（預設 30 秒）
- 檢查網路連接
- 降低 `initial_queries` 和 `max_loops` 以減少處理時間

#### 3. 進度更新失敗
**症狀**：研究進行中但沒有進度更新
**解決方案**：
- 檢查 `langgraph.progress_updates` 是否啟用
- 確認 Discord 訊息權限正常

### 調試模式

啟用調試模式以獲取更多資訊：

```yaml
development:
  debug_mode: true
  log_level: "DEBUG"
  langgraph_test_mode: true
```

### 日誌檢查

重要日誌訊息：
- `✨ LangGraph 智能研究系統初始化完成` - 系統成功啟動
- `訊息分析 - 複雜度: X.XX, 使用研究模式: true/false` - 模式切換決定
- `LangGraph 研究失敗` - 研究過程錯誤

## 📊 效能監控

### 查看統計資訊

```python
from llmcord.pipeline.rag import get_rag_pipeline
from llmcord.core.session_manager import get_session_manager

# 獲取 RAG 統計
rag_pipeline = await get_rag_pipeline()
stats = rag_pipeline.get_research_stats()

# 獲取會話統計
session_manager = get_session_manager()
session_stats = session_manager.get_session_stats()
```

### 效能調優建議

1. **對於高流量伺服器**：
   - 降低 `complexity_threshold` 減少研究模式觸發
   - 調整 `session_timeout_hours` 控制記憶體使用
   - 使用 `cleanup_interval` 定期清理

2. **對於研究重度使用**：
   - 增加 `timeout` 允許更長研究時間
   - 提高 `max_loops` 獲得更深入研究
   - 監控 API 配額使用情況

## 🧪 測試

### 運行整合測試

```bash
python test_langgraph_integration.py
```

### 手動測試案例

1. **簡單問答測試**：
   ```
   @Bot 你今天過得如何？
   ```

2. **複雜研究測試**：
   ```
   @Bot 請詳細分析 OpenAI 和 Google 在 AI 領域的競爭狀況
   ```

3. **強制研究測試**：
   ```
   @Bot !research 今天的新聞
   ```

4. **多輪對話測試**：
   ```
   @Bot 請研究量子計算的發展
   @Bot 那中國的量子計算發展如何？
   ```

## 📈 未來擴展

### 計劃中的功能

1. **向量資料庫整合**：持久化知識儲存
2. **更精確的複雜度評估**：使用機器學習模型
3. **自訂研究模板**：針對特定領域的專門研究流程
4. **多語言支援**：支援英文和日文研究

### 貢獻指南

歡迎提交 Issue 和 Pull Request！請確保：
- 遵循現有的代碼風格
- 添加適當的測試
- 更新相關文檔

## 📞 支援

如遇到問題，請：
1. 檢查本指南的故障排除部分
2. 查看日誌文件尋找錯誤資訊
3. 在 GitHub 提交 Issue 並附上詳細描述

---

**享受妳的智能研究助手初華帶來的全新體驗！** ✨🌟