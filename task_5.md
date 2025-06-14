# Task 5: 整合測試與優化

## 概述
確保所有新功能正常運作，包含多模態輸入支援的實作，進行性能優化，完善錯誤處理，並更新相關文檔。

## 目標
- 實作多模態輸入支援
- 端到端測試所有重構功能
- 性能優化和瓶頸排除
- 完善錯誤處理和降級機制
- 更新文檔和部署指南

## 依賴關係
- **前置條件**: Task 1-4 全部完成
- **後續任務**: 正式發布和部署

## 子任務

### Task 5.1: 多模態輸入支援
**狀態**: ⏳ 待開始

**目標**: 實現 LLM 對 Discord 圖片輸入的支援，使其能夠理解並處理包含文字和圖片的訊息。

**任務清單**:

- [x] **Task 5.1.1**: 修改 `schemas/agent_types.py` 中的 `MsgNode`
  - **說明**: 將 `MsgNode.content` 的型別從 `str` 修改為 `Union[str, List[Dict[str, Any]]]`，以支援多模態內容的結構化列表。這是確保圖片資訊能在系統內部正確傳遞的基礎。
  - **修改位置**: `schemas/agent_types.py`
  - **狀態**: ✅ 已完成
  - **參考修改**:
    ```python
    # schemas/agent_types.py
    from dataclasses import dataclass, field
    from typing import List, Dict, Any, Optional, Annotated, Union # <-- 新增 Union

    # ... existing imports ...

    @dataclass
    class MsgNode:
        \"\"\"結構化訊息節點。\"\"\"
        role: str
        content: Union[str, List[Dict[str, Any]]] # <-- 修改這裡的型別
        metadata: Dict[str, Any] = field(default_factory=dict)
    ```

- [x] **Task 5.1.2**: 修改 `discord_bot/message_collector.py` 中的 `collect_message` 函數
  - **說明**: 確保在將 `ProcessedMessage` 轉換為 `MsgNode` 時，不再對 `content` 進行強制字串轉換。這樣，圖片的 Base64 編碼結構化資料就能被正確地儲存到 `MsgNode.content` 中。
  - **修改位置**: `discord_bot/message_collector.py`
  - **狀態**: ✅ 已完成
  - **參考修改**:
    ```python
    # discord_bot/message_collector.py
    # ... existing code ...

    # 轉換為 MsgNode 格式
    for processed_msg in processed_messages[::-1]:
        msg_node = MsgNode(
            role=processed_msg.role,
            content=processed_msg.content, # <-- 移除 `if isinstance(...) else str(...)` 轉換
            metadata={\"user_id\": processed_msg.user_id} if processed_msg.user_id else {}
        )
        messages.append(msg_node)

    # ... existing code ...
    ```

- [x] **Task 5.1.3**: 確認 `agent_core/graph.py` 中的 LLM 訊息構建
  - **說明**: 驗證 `_build_planning_prompt` 和 `_generate_final_answer` 等函數在構建 LangChain 的 `HumanMessage` 和 `AIMessage` 時，能夠直接傳遞 `MsgNode.content`。根據 LangChain 文件，這些訊息類別本身就支援多模態內容的列表格式，因此預期此任務無需代碼修改，僅為確認步驟。
  - **狀態**: ✅ 已完成，並修正了相關問題
  - **實際修改**:
    * 添加了 `_extract_text_content()` 輔助函數來安全地從多模態內容中提取文字
    * 修正了所有直接存取 `content` 並調用字串方法的地方
    * 修正了 `_analyze_tool_necessity_fallback()` 中的 `.lower()` 調用
    * 修正了 `agent_utils.py` 中的類似問題
  - **確認點**:
    *   ✅ 檢查 `_build_planning_prompt` 和 `_build_messages_for_llm` 中，對 `HumanMessage(content=msg.content)` 和 `AIMessage(content=msg.content)` 的使用。確認 `msg.content` 會直接傳遞。
    *   ✅ **特別注意：** LangChain 對於多模態內容的列表格式有特定的結構要求。對於圖片，`MsgNode.content` 中的 `List[Dict[str, Any]]` 預期應包含以下格式的字典：
        ```python
        # OpenAI Chat Completions 格式範例 (廣泛支援，已在 message_collector.py 中實作)
        {
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64,<Base64 編碼的圖片字串>"}
        }
        ```
        `discord_bot/message_collector.py` 已確保在將圖片轉換為 `MsgNode.content` 時，遵循上述 LangChain 期望的格式。
    *   ✅ 由於 LangChain 內部機制會處理這個列表，因此不需要額外的字串化操作。

**測試驗證**:
```bash
# 為了驗證此階段的更改，您可能需要：
# 1. 在模擬環境中發送一個包含文字和圖片的 Discord 訊息。
# 2. 追蹤該訊息在 `discord_bot/message_collector.py` 和 `agent_core/graph.py` 中的傳遞過程。
# 3. 確保 `MsgNode.content` 確實包含了圖片的結構化資料（而不是字串），並且格式符合 LangChain 的多模態輸入規範。
# 4. 如果可能，嘗試使用一個支援多模態輸入的 LLM 模型（例如 Gemini Vision 模型）來測試其對圖片內容的理解。
```

#### 預期改進效果
1.  **真正的多模態支援**: LLM 將能夠直接接收和處理圖片內容，提升理解能力和回應品質。
2.  **資料流一致性**: 確保圖片資料從 Discord 輸入到 LLM 處理層的完整性。
3.  **減少資訊損失**: 避免因強制字串轉換而導致的圖片資訊丟失。

### Task 5.2: 端到端測試
**狀態**: ⏳ 待開始

**目標**: 測試完整的 Discord Bot 流程和所有功能組合

**測試範圍**:
- [ ] **Discord Bot 完整流程測試**
  - 訊息接收和處理
  - Agent 執行流程
  - 工具使用和並行執行
  - Persona 系統整合
  - 串流回應功能
  - 進度通知系統
  - **新增**: 包含文字和圖片的訊息處理 (多模態測試)

- [ ] **CLI 介面測試**
  - 命令行參數處理
  - 配置載入
  - Agent 執行
  - 輸出格式化

- [ ] **配置系統測試**
  - 型別安全配置載入
  - 配置驗證
  - 錯誤處理
  - 預設值回退

**測試腳本**:
```python
# tests/test_end_to_end.py
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

class TestEndToEndFlow:
    @pytest.mark.asyncio
    async def test_discord_bot_complete_flow(self):
        \"\"\"測試 Discord Bot 完整流程\"\"\"
        # 模擬 Discord 訊息
        mock_message = Mock()
        mock_message.content = "請幫我搜尋最新的 AI 發展"
        mock_message.author.display_name = "TestUser"
        mock_message.guild.name = "TestGuild"
        mock_message.channel.name = "general"
        
        # 測試訊息處理
        handler = MessageHandler(config)
        await handler.handle_message(mock_message)
        
        # 驗證結果
        assert mock_message.reply.called
        # 更多驗證...
    
    @pytest.mark.asyncio
    async def test_agent_with_tools(self):\
        \"\"\"測試 Agent 工具使用流程\"\"\"
        # 測試計劃生成
        # 測試並行工具執行
        # 測試結果聚合
        # 測試反思邏輯
        pass
    
    @pytest.mark.asyncio
    async def test_streaming_functionality(self):
        \"\"\"測試串流功能\"\"\"
        # 測試串流啟用條件
        # 測試串流塊生成
        # 測試 Discord 串流顯示
        pass
    
    def test_persona_integration(self):
        \"\"\"測試 Persona 系統整合\"\"\"
        # 測試 persona 載入
        # 測試 system prompt 構建
        # 測試動態切換
        pass
```

**驗收標準**:
- 所有端到端測試通過
- 覆蓋率達到 80% 以上
- 無關鍵功能缺失

### Task 5.4: 錯誤處理改進
**狀態**: ⏳ 待開始

**目標**: 完善所有模組的錯誤處理，實現優雅的降級機制

**錯誤處理策略**:
- [ ] **配置錯誤處理**
  ```python
  # utils/config_loader.py
  class ConfigurationError(Exception):
      \"\"\"配置相關錯誤\"\"\"
      pass
  
  def load_typed_config_with_fallback(config_path: str = "config.yaml") -> AppConfig:
      \"\"\"帶回退的配置載入\"\"\"
      try:
          return AppConfig.from_yaml(config_path)
      except FileNotFoundError:
          logger.warning(f"配置文件 {config_path} 不存在，使用預設配置")
          return AppConfig()  # 預設配置
      except Exception as e:
          logger.error(f"配置載入失敗: {e}")
          raise ConfigurationError(f"無法載入配置: {e}")
  ```

- [ ] **LLM 調用錯誤處理**
  ```python
  # agent_core/graph.py
  async def _generate_final_answer_with_retry(self, messages: List[MsgNode], context: str) -> str:
      \"\"\"帶重試的答案生成\"\"\"
      max_retries = 3
      for attempt in range(max_retries):
          try:
              return self._generate_final_answer(messages, context)
          except Exception as e:
              self.logger.warning(f"LLM 調用失敗 (嘗試 {attempt + 1}/{max_retries}): {e}")
              if attempt == max_retries - 1:
                  # 最後一次嘗試失敗，使用回退答案
                  return self._generate_basic_fallback_answer(messages, context)
              await asyncio.sleep(2 ** attempt)  # 指數退避
  ```

- [ ] **工具執行錯誤處理**
  - 工具超時控制
  - 網路錯誤重試
  - 部分失敗處理

- [ ] **Discord 錯誤處理**
  - API 限制處理
  - 訊息發送失敗重試
  - 權限錯誤處理

**驗收標準**:
- 所有關鍵路徑都有錯誤處理
- 錯誤訊息清晰有用
- 降級機制正常工作
- 系統不會因單點錯誤崩潰

### Task 5.5: 文檔更新
**狀態**: ⏳ 待開始

**目標**: 更新所有相關文檔，確保部署和使用指南完整

**文檔更新清單**:
- [ ] **配置文檔更新**
  ```markdown
  # config.yaml 配置指南
  
  ## 型別安全配置
  
  新的配置系統使用 dataclass 提供型別安全保證：
  
  ```yaml
  # 串流配置
  streaming:
    enabled: true
    chunk_size: 50
    delay_ms: 50
    min_content_length: 100
  
  # Persona 配置
  prompt_system:
    persona:
      random_selection: false
      default_persona: "helpful_assistant"
      persona_directory: "personas"
  ```

- [ ] **API 文檔更新**
  - 新的 Agent 介面
  - 工具系統 API
  - Progress 和 Streaming API

- [ ] **部署指南更新**
  - 新的依賴需求
  - 配置遷移指南
  - 性能調優建議

- [ ] **開發者指南**
  - 新的架構說明
  - 工具開發指南
  - 測試指南
  - **新增**: 多模態輸入處理指南

**驗收標準**:
- 所有文檔與實際實作一致
- 部署指南可以成功部署
- 開發者指南清晰易懂

### Task 5.6: 回歸測試
**狀態**: ⏳ 待開始

**目標**: 確保重構沒有破壞現有功能

**回歸測試範圍**:
- [ ] **現有功能驗證**
  - Discord Bot 基本功能
  - CLI 工具功能
  - 配置系統功能
  - 日誌系統功能
  - **新增**: 多模態輸入功能驗證 (確保圖片處理正確)

- [ ] **向後相容性測試**
  - 舊配置文件相容性
  - API 介面相容性
  - 行為一致性

- [ ] **邊界條件測試**
  - 極端輸入處理
  - 資源限制測試
  - 併發壓力測試

**測試自動化**:
```bash
# 完整回歸測試套件
python -m pytest tests/ -v --cov=. --cov-report=html

# 性能回歸測試
python -m pytest tests/test_performance.py -v

# 端到端測試
python -m pytest tests/test_end_to_end.py -v
```

**驗收標準**:
- 所有回歸測試通過
- 性能沒有明顯下降
- 向後相容性保持

## 測試驗證

### 自動化測試套件
```bash
# 完整測試套件
make test-all

# 性能測試
make test-performance

# 端到端測試
make test-e2e

# 覆蓋率報告
make coverage-report
```

### 手動測試清單
- [ ] Discord Bot 手動測試
- [ ] CLI 工具手動測試
- [ ] 配置系統手動測試
- [ ] 串流功能手動測試
- [ ] Persona 系統手動測試
- [ ] **新增**: 多模態輸入功能手動測試 (發送圖片訊息並驗證 LLM 回應)

## 預估時間
**2.5 週** (12-15 個工作日)

## 風險與注意事項
1. **測試覆蓋率**: 確保測試覆蓋所有關鍵功能
2. **性能回歸**: 注意重構可能帶來的性能影響
3. **相容性問題**: 確保向後相容性
4. **文檔同步**: 確保文檔與實作同步
5. **多模態 LLM 支援**: 確保所使用的 Gemini 模型版本確實支援圖片輸入，並能正確解析 Base64 編碼。

## 成功標準
- [ ] 所有自動化測試通過
- [ ] 性能指標達標
- [ ] 錯誤處理完善
- [ ] 文檔完整更新
- [ ] 回歸測試通過
- [ ] 系統穩定性良好
- [ ] **新增**: 多模態輸入功能正常運作，LLM 能理解圖片內容。

## 交付物
- [ ] 完整的測試套件
- [ ] 性能基準報告
- [ ] 錯誤處理文檔
- [ ] 更新的部署指南
- [ ] 回歸測試報告
- [ ] **新增**: 多模態輸入實作與測試報告 