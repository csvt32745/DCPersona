# llmcord 專案任務日誌

## 當前狀態 (2024-12-19)

### 專案概況
- **分支**: `google_deepresearch_vibe`
- **主要目標**: 重構 Agent 架構，實現統一、模組化且可擴展的智慧代理系統
- **當前重點**: Graph 流程重構 - 統一工具決策與查詢生成

### 已完成任務
- [x] 初步分析現有架構問題
- [x] 制定重構提案 (`refactor_proposal.md`)
- [x] 識別 Graph 流程優化需求

---

## Phase 2: Graph 流程重構任務 (進行中)

### 背景與問題分析

#### 當前 Graph 流程問題
1. **流程過於複雜**: 
   - 現有流程: `generate_query_or_plan` → `tool_selection` → `execute_tool` → `reflection` → `evaluate_research`
   - 步驟過多，邏輯分散，維護困難

2. **決策分散**: 
   - 工具選擇邏輯在 `tool_selection` 節點
   - 查詢生成邏輯在 `generate_query_or_plan` 節點
   - 導致重複判斷和效率低下

3. **與參考實作不一致**: 
   - Gemini 參考實作在 `generate_query` 就決定所有搜尋查詢
   - 使用 structured output 和並行執行，更加高效

#### 目標流程設計
```on message → generate_query_or_plan (決定工具+生成查詢) → execute_tools (並行執行) → reflection (如果使用工具) → [循環 max_tool_rounds 次] → finalize_answer
```

### 具體任務清單

#### Task 2.1: 重構 `generate_query_or_plan` 節點 ⏳
**目標**: 整合工具決策和查詢生成邏輯，參考 Gemini 實作使用 structured output

**當前實作問題**:
- `generate_query_or_plan` 只做基本的工具需求判斷
- 查詢生成邏輯簡單，沒有使用 structured output
- 工具選擇邏輯分離在另一個節點

**需要修改的文件**:
- `schemas/agent_types.py`: 新增 `ToolPlan`, `AgentPlan` 結構化輸出類型
- `agent_core/graph.py`: 重構 `generate_query_or_plan` 方法

**實作要點**:
1. 新增結構化輸出類型:
   ```python
   @dataclass
   class ToolPlan:
       tool_name: str
       queries: List[str]  # 該工具的查詢列表
       priority: int = 1
       metadata: Dict[str, Any] = field(default_factory=dict)
   
   @dataclass 
   class AgentPlan:
       needs_tools: bool
       tool_plans: List[ToolPlan] = field(default_factory=list)
       reasoning: str = ""  # 決策推理過程
   ```

2. 重構節點邏輯:
   - 使用 `structured_llm = self.tool_analysis_llm.with_structured_output(AgentPlan)`
   - 一次性決定所有工具使用和查詢參數
   - 構建專門的計劃生成提示詞

**依賴**: 需要先完成 Phase 1 的型別安全配置系統

#### Task 2.2: 簡化 Graph 結構 ⏳
**目標**: 移除冗余節點，重構為更簡潔的流程

**需要修改**:
- 移除 `tool_selection` 節點（邏輯整合到 `generate_query_or_plan`）
- 移除 `evaluate_research` 節點（邏輯整合到 `reflection`）
- 重構 `execute_tool` 為 `execute_tools`，支援並行執行

**新的 Graph 結構**:
```python
def build_graph(self) -> StateGraph:
    builder = StateGraph(OverallState)
    
    # 核心節點
    builder.add_node("generate_query_or_plan", self.generate_query_or_plan)
    builder.add_node("execute_tools", self.execute_tools)
    builder.add_node("reflection", self.reflection)
    builder.add_node("finalize_answer", self.finalize_answer)
    
    # 流程設置
    builder.add_edge(START, "generate_query_or_plan")
    builder.add_conditional_edges(
        "generate_query_or_plan",
        self.route_after_planning,
        {"use_tools": "execute_tools", "direct_answer": "finalize_answer"}
    )
    builder.add_edge("execute_tools", "reflection")
    builder.add_conditional_edges(
        "reflection",
        self.decide_next_step,
        {"continue": "generate_query_or_plan", "finish": "finalize_answer"}
    )
    builder.add_edge("finalize_answer", END)
    
    return builder.compile()
```

#### Task 2.3: 實現並行工具執行 ⏳
**目標**: 參考 Gemini 的 `continue_to_web_research` 實作，使用 `Send` 實現並行執行

**技術要點**:
1. 使用 LangGraph 的 `Send` 機制創建並行任務
2. 為每個工具查詢創建獨立的執行節點
3. 實現結果聚合和去重邏輯

**實作結構**:
```python
def continue_to_tool_execution(self, state: OverallState):
    """並行執行工具（參考 Gemini 實作）"""
    agent_plan = state.agent_plan
    sends = []
    for idx, tool_plan in enumerate(agent_plan.tool_plans):
        for query_idx, query in enumerate(tool_plan.queries):
            sends.append(Send(
                "execute_single_tool", 
                {
                    "tool_name": tool_plan.tool_name,
                    "query": query,
                    "task_id": f"{idx}_{query_idx}",
                    "priority": tool_plan.priority
                }
            ))
    return sends

async def execute_single_tool(self, state: ToolExecutionState) -> Dict[str, Any]:
    """執行單個工具任務（並行節點）"""
    # 實現單個工具的執行邏輯
    pass

async def execute_tools(self, state: OverallState) -> Dict[str, Any]:
    """聚合所有工具執行結果"""
    # 等待所有並行任務完成，聚合結果
    pass
```

#### Task 2.4: 更新狀態管理 ⏳
**目標**: 擴展 `OverallState` 支援新的計劃結構

**需要修改**:
- `schemas/agent_types.py`: 擴展 `OverallState`
- 新增 `ToolExecutionState` 用於並行執行

**新的狀態結構**:
```python
@dataclass
class OverallState:
    """統一代理狀態（重構版）"""
    messages: List[MsgNode] = field(default_factory=list)
    tool_round: int = 0
    finished: bool = False
    
    # 新的計劃驅動欄位
    agent_plan: Optional[AgentPlan] = None
    research_topic: str = ""
    
    # 工具執行結果
    tool_results: List[str] = field(default_factory=list)
    aggregated_tool_results: List[str] = field(default_factory=list)
    
    # 反思和評估
    is_sufficient: bool = False
    reflection_reasoning: str = ""
    
    # 最終結果
    final_answer: str = ""
    sources: List[Dict[str, str]] = field(default_factory=list)

@dataclass
class ToolExecutionState:
    """單個工具執行狀態"""
    tool_name: str
    query: str
    task_id: str
    priority: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### 測試計劃
1. **單元測試**: 測試新的計劃生成邏輯
2. **整合測試**: 測試並行工具執行
3. **端到端測試**: 測試完整的 Discord Bot 流程

### 預期改進效果
1. **流程簡化**: 從 5 個主要節點減少到 4 個
2. **效率提升**: 並行執行工具，減少總執行時間
3. **決策統一**: 在一個節點內完成所有工具決策
4. **更好的可控性**: 通過結構化輸出精確控制工具使用策略

---

## 相關文件與上下文

### 核心文件
- `agent_core/graph.py`: 主要重構目標，包含所有 Graph 節點邏輯
- `schemas/agent_types.py`: 狀態和類型定義，需要擴展
- `refactor_proposal.md`: 完整的重構提案文檔

### 參考實作
- `gemini-fullstack-langgraph-quickstart/backend/src/agent/graph.py`: Gemini 參考實作
  - `generate_query`: 使用 structured output 生成查詢
  - `continue_to_web_research`: 使用 Send 實現並行執行
  - `web_research`: 並行工具執行節點

### 配置相關
- `config.yaml`: 系統配置文件
- `utils/config_loader.py`: 配置載入邏輯（Phase 1 重構目標）

---

## 下一步行動
1. 完成 Task 2.1: 重構 `generate_query_or_plan` 節點
2. 實作新的結構化輸出類型
3. 測試計劃生成邏輯
4. 繼續後續任務的實作

---

## 備註
- 此重構需要與 Phase 1 的型別安全配置系統協調
- 需要保持與現有 Discord Bot 功能的相容性
- 重點參考 Gemini 實作的設計模式和最佳實踐

# 任務執行日誌

## 2024-12-19

### Task 1: 型別安全配置系統重構 ✅ 已完成

**執行時間**: 2024-12-19 14:00 - 16:30

#### 完成的子任務:

##### Task 1.1: 完善 `schemas/config_types.py` ✅
- ✅ 添加了 `StreamingConfig` 配置類型
- ✅ 添加了 `ToolDescriptionConfig` 配置類型  
- ✅ 完善了 `ProgressDiscordConfig`，添加了 `show_percentage` 和 `show_eta` 欄位
- ✅ 添加了 `ConfigurationError` 異常類型
- ✅ 完善了 `AppConfig.from_yaml()` 方法，包含：
  - 深度合併配置邏輯
  - 配置驗證功能
  - 完整的錯誤處理
- ✅ 添加了 `enable_conversation_history` 欄位到 `DiscordConfig`

##### Task 1.2: 重構 `utils/config_loader.py` ✅
- ✅ 移除了舊的 `load_config()` 函數的字典格式回退邏輯
- ✅ 強制使用型別安全的 `load_typed_config()` 作為唯一入口
- ✅ 移除了所有字典格式支援
- ✅ 添加了完整的錯誤處理和 `ConfigurationError` 拋出
- ✅ 保留了向後相容性別名，但會發出棄用警告

##### Task 1.3: 更新所有模組使用型別安全配置 ✅
- ✅ **agent_core/graph.py**: 替換所有 `config.get()` 為型別安全存取
  - 更新了 LLM 實例初始化邏輯
  - 添加了向後相容性支援
  - 修復了工具配置存取
- ✅ **discord_bot/message_handler.py**: 完全重構配置存取
  - 使用 `config.discord.limits.*` 替代 `config.get()`
  - 使用 `config.discord.permissions.*` 替代字典存取
  - 使用 `config.discord.maintenance.*` 替代舊格式
- ✅ **prompt_system/prompts.py**: 重構提示詞系統配置
  - 使用 `config.prompt_system.*` 替代 `config.get()`
  - 更新了 Discord 上下文格式化
  - 完善了系統提示詞載入邏輯
- ✅ **main.py**: 更新主程式配置存取
  - 使用 `config.discord.bot_token` 替代 `config.get()`
  - 添加了完整的錯誤處理
  - 改善了日誌設置
- ✅ **cli_main.py**: 重構 CLI 介面
  - 完全重寫為型別安全版本
  - 添加了互動式選單
  - 使用 `config.agent.*` 替代字典存取
- ✅ **discord_bot/client.py**: 更新客戶端配置
  - 使用 `config.discord.*` 替代 `config.get()`
  - 簡化了事件處理邏輯

##### Task 1.4: 刪除未使用的 `discord_bot/response_formatter.py` ✅
- ✅ 確認沒有任何地方使用 `format_llm_output_and_reply` 函數
- ✅ 確認沒有任何地方導入 `response_formatter`
- ✅ 成功刪除了 `discord_bot/response_formatter.py` 檔案

#### 測試驗證結果:

✅ **配置載入測試**: 
```bash
python -c "from utils.config_loader import load_typed_config; config = load_typed_config(); print('✅ 配置載入成功')"
# 輸出: ✅ 配置載入成功
```

✅ **型別安全存取測試**:
```bash
# Discord Bot Token: True
# Gemini API Key: True  
# 最大工具輪次: 1
# 對話歷史: True
```

✅ **Agent 創建測試**:
```bash
# ✅ Agent 創建成功
# 工具配置: ['google_search', 'citation']
# 最大工具輪次: 1
```

✅ **配置相關 .get() 調用檢查**:
- 剩餘的 `.get()` 調用都是非配置相關的（如字典操作、測試文件等）
- 所有配置存取都已改為型別安全方式

#### 成果總結:

1. **完全消除字串 key 配置存取**: 所有 `config.get("key")` 都已替換為 `config.field.subfield`
2. **建立完整的 dataclass 配置系統**: 所有配置都有對應的型別安全 dataclass
3. **提升代碼安全性**: 配置存取現在有完整的型別檢查
4. **保持向後相容性**: 舊的配置欄位仍然支援，但會逐步遷移
5. **改善錯誤處理**: 配置載入失敗時提供清晰的錯誤信息

#### 技術改進:

- 使用 `@dataclass` 定義所有配置結構
- 實現了深度合併配置邏輯
- 添加了配置驗證機制
- 建立了統一的錯誤處理體系
- 保持了完整的向後相容性

**Task 1 狀態**: ✅ **已完成**

---

## 待執行任務

### Task 2: Graph 流程重構
**狀態**: ⏳ 待開始
**依賴**: Task 1 (已完成)

### Task 3: 進度系統優化  
**狀態**: ⏳ 待開始

### Task 4: 測試覆蓋完善
**狀態**: ⏳ 待開始

### Task 5: 文檔和部署優化
**狀態**: ⏳ 待開始
