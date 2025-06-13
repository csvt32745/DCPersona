# llmcord 專案重構提案 (更新版)

---

## 1. 目標 (Goals)

本次重構旨在建立一個統一、模組化且可擴展的智慧代理（Agent）架構，核心目標是實現一個靈活且配置驅動的工作流程：

*   **統一工作流程**: 透過一個統一的 LangGraph 流程處理所有請求。代理將根據配置和輪次限制，動態評估並決定使用適當的工具，實現「訊息 -> (代理評估使用工具 -> 回傳 -> 多輪交互) -> 最終答案」的自動化流程。
*   **可組合的代理**: 代理的能力由一套可插拔、可設定的工具和輪次限制定義，使其功能可透過設定檔動態調整。
*   **提升模組化與簡潔性**: 重新組織專案結構，使模組職責更清晰、耦合度降低，提升可維護性與擴展性。
*   **型別安全配置**: 完全使用 dataclass 配置系統，消除字串 key 存取，提升代碼安全性。
*   **智能工具決策**: Agent 能根據工具描述和參數自主決定使用哪些工具。
*   **Streaming 回應**: 支援即時串流回應，提升用戶體驗。

---

## 2. 現有問題分析

### 2.1 配置系統問題
- **字串 key 存取**: 大量使用 `config.get("key")` 方式存取配置，缺乏型別安全
- **配置分散**: 配置邏輯散布在各個模組中，難以維護
- **向後相容性負擔**: 新舊配置格式混用，增加複雜度

### 2.2 工具系統問題
- **硬編碼工具選擇**: Agent 無法智能決定使用哪些工具
- **缺乏工具描述**: 工具沒有標準化的描述和參數定義
- **工具邏輯內嵌**: 工具邏輯直接寫在 graph.py 中，不利於擴展

### 2.3 回應系統問題
- **非串流回應**: 用戶需要等待完整回應，體驗不佳
- **Persona 未整合**: Persona 系統沒有整合到主流程中

---

## 3. 新專案架構設計

```
llmcord/
│
├── main.py                  # 程式主入口
├── config.yaml              # 系統設定檔
├── personas/                # 存放不同性格的 Agent 系統提示詞
│
├── discord_bot/
│   ├── client.py            # Discord Client 初始化
│   ├── message_handler.py   # 處理 Discord 事件
│   ├── message_collector.py # 訊息收集與預處理
│   ├── progress_manager.py  # Discord 進度消息管理
│   └── progress_adapter.py  # Discord 進度適配器（整合 streaming）
│
├── agent_core/              # **[核心]** 統一的 Agent 處理引擎
│   ├── agent.py             # 統一 Agent 實作入口
│   ├── graph.py             # LangGraph 構建與節點定義
│   ├── agent_session.py     # Agent 會話管理
│   ├── agent_utils.py       # Agent 核心輔助函式
│   ├── progress_observer.py # 進度觀察者介面（支援 streaming）
│   └── progress_mixin.py    # 進度更新混入（整合 streaming）
│
├── tools/                   # **[重構]** 標準化工具系統
│   ├── base.py              # **[新]** 工具基底類別
│   ├── google_search.py     # **[重構]** Google 搜尋工具
│   ├── citation.py          # 引用管理工具
│   └── registry.py          # **[新]** 工具註冊系統
│
├── prompt_system/           # 統一的提示詞管理系統
│   ├── prompts.py           # 基礎提示詞功能
│   ├── persona_manager.py   # **[新]** Persona 管理器
│   └── system_prompt_manager.py # **[新]** 統一 System Prompt 管理
│
├── schemas/                 # 結構化資料模式
│   ├── agent_types.py       # 統一的代理相關型別定義
│   ├── config_types.py      # **[完善]** 型別安全配置定義
│   ├── tool_types.py        # **[新]** 工具相關型別定義
│   └── discord.py           # Discord 相關結構
│
├── utils/
│   ├── config_loader.py     # **[重構]** 型別安全配置載入
│   ├── logger.py            # 日誌系統設定
│   └── discord_utils.py     # Discord 互動輔助函式
│
└── tests/
    └── ...                  # 所有測試檔案
```

### 主要架構變更說明

1. **移除 `discord_bot/response_formatter.py`**: 該模組未被使用，其功能整合到 `progress_adapter.py` 中
2. **Progress 系統整合 Streaming**: `progress_observer.py` 和 `progress_mixin.py` 現在支援串流功能
3. **統一 System Prompt 管理**: 新增 `system_prompt_manager.py` 統一處理所有 system prompt 邏輯
4. **標準化工具系統**: 完整的工具基底類別、註冊系統和型別定義

---

## 4. 核心重構任務

### Phase 1: 型別安全配置系統 (1 week)

#### 目標
完全消除字串 key 存取配置，建立型別安全的配置系統。

#### 任務清單

- [ ] **Task 1.1**: 完善 `schemas/config_types.py`
  - 補充缺失的配置類型定義
  - 確保所有配置欄位都有對應的 dataclass
  - 添加配置驗證邏輯
  - **參考實現**:
    ```python
    @dataclass
    class StreamingConfig:
        """串流配置"""
        enabled: bool = True
        chunk_size: int = 50  # 字符數
        delay_ms: int = 50    # 毫秒延遲
        
    @dataclass 
    class ToolDescriptionConfig:
        """工具描述配置"""
        name: str
        description: str
        parameters: Dict[str, Any] = field(default_factory=dict)
        enabled: bool = True
        priority: int = 999
    ```

- [ ] **Task 1.2**: 重構 `utils/config_loader.py`
  - 強制使用型別安全載入
  - 移除所有字典格式的回退邏輯
  - 添加配置驗證和錯誤處理
  - **參考實現**:
    ```python
    def load_typed_config(config_path: str = "config.yaml") -> AppConfig:
        """載入型別安全配置（唯一入口）"""
        try:
            return AppConfig.from_yaml(config_path)
        except Exception as e:
            logging.error(f"配置載入失敗: {e}")
            raise ConfigurationError(f"無法載入配置: {e}")
    
    # 移除所有 load_config() 函數，強制使用型別安全版本
    ```

- [ ] **Task 1.3**: 更新所有模組使用型別安全配置
  - 替換所有 `config.get("key")` 為 `config.field.subfield`
  - 更新 `agent_core/graph.py` 使用新配置
  - 更新 `discord_bot/` 模組使用新配置
  - 更新 `prompt_system/` 模組使用新配置
  - **重點文件**:
    - `agent_core/graph.py`: 替換所有 `self.config.get()` 調用
    - `discord_bot/message_handler.py`: 使用 `config.discord.*` 
    - `prompt_system/prompts.py`: 使用 `config.prompt_system.*`

- [ ] **Task 1.4**: 刪除未使用的 `discord_bot/response_formatter.py`
  - 確認沒有任何地方使用 `format_llm_output_and_reply` 函數
  - 刪除整個 `response_formatter.py` 檔案
  - 將必要的 Discord 回應功能整合到 `progress_adapter.py` 中

**測試驗證**:
```bash
# 確保沒有任何 .get() 調用配置
grep -r "\.get(" --include="*.py" . | grep -v test | grep -v __pycache__
# 應該只剩下非配置相關的 .get() 調用

# 確認 response_formatter 已刪除
find . -name "response_formatter.py" | wc -l  # 應該是 0
```

### Phase 2: 重構 Graph 流程 - 統一工具決策與查詢生成 (1-2 weeks)

#### 目標
參考 Gemini 實作，重構 `agent_core/graph.py` 的流程，在 `generate_query_or_plan` 階段就同時決定工具使用和生成查詢，實現更簡潔高效的流程。

#### 當前問題分析
1. **流程過於複雜**: 現有流程分為 `generate_query_or_plan` → `tool_selection` → `execute_tool` → `reflection`，步驟過多
2. **決策分散**: 工具選擇和查詢生成分離，導致邏輯重複和效率低下
3. **與參考實作不一致**: Gemini 實作在 `generate_query` 就決定了所有搜尋查詢，更加直接

#### 新流程設計
```
on message → generate_query_or_plan (決定工具+生成查詢) → execute_tools (並行執行) → reflection (如果使用工具) → [循環 max_tool_rounds 次] → finalize_answer
```

#### 任務清單

- [ ] **Task 2.1**: 重構 `generate_query_or_plan` 節點
  - 整合工具決策和查詢生成邏輯
  - 參考 Gemini 的 `generate_query` 實作，使用 structured output
  - 一次性決定所有需要的工具和對應的查詢參數
  - **參考實現**:
    ```python
    # schemas/agent_types.py - 新增結構化輸出類型
    @dataclass
    class ToolPlan:
        """工具使用計劃"""
        tool_name: str
        queries: List[str]  # 該工具的查詢列表
        priority: int = 1
        metadata: Dict[str, Any] = field(default_factory=dict)
    
    @dataclass 
    class AgentPlan:
        """Agent 執行計劃"""
        needs_tools: bool
        tool_plans: List[ToolPlan] = field(default_factory=list)
        reasoning: str = ""  # 決策推理過程
    
    # agent_core/graph.py - 重構後的節點
    async def generate_query_or_plan(self, state: OverallState) -> Dict[str, Any]:
        """
        統一的計劃生成節點：同時決定工具使用和生成查詢
        
        參考 Gemini 實作，使用 structured output 一次性決定：
        1. 是否需要使用工具
        2. 需要使用哪些工具
        3. 每個工具的具體查詢參數
        """
        try:
            user_content = state.messages[-1].content
            max_tool_rounds = self.behavior_config.get("max_tool_rounds", 0)
            
            if max_tool_rounds == 0:
                # 純對話模式
                return {
                    "agent_plan": AgentPlan(needs_tools=False),
                    "tool_round": 0
                }
            
            # 使用 structured LLM 生成完整計劃
            structured_llm = self.tool_analysis_llm.with_structured_output(AgentPlan)
            
            # 構建計劃生成提示詞
            plan_prompt = self._build_planning_prompt(state.messages)
            
            # 生成執行計劃
            agent_plan = structured_llm.invoke(plan_prompt)
            
            self.logger.info(f"生成計劃: 需要工具={agent_plan.needs_tools}, 工具數量={len(agent_plan.tool_plans)}")
            
            return {
                "agent_plan": agent_plan,
                "tool_round": 0,
                "research_topic": user_content[:200]
            }
            
        except Exception as e:
            self.logger.error(f"generate_query_or_plan 失敗: {e}")
            return {
                "agent_plan": AgentPlan(needs_tools=False),
                "finished": True
            }
    ```

- [ ] **Task 2.2**: 簡化 Graph 結構
  - 移除 `tool_selection` 節點（邏輯整合到 `generate_query_or_plan`）
  - 重構 `execute_tool` 為 `execute_tools`，支援並行執行多個工具
  - 參考 Gemini 的 `continue_to_web_research` 使用 `Send` 實現並行執行
  - **參考實現**:
    ```python
    def build_graph(self) -> StateGraph:
        """建立簡化的 LangGraph"""
        builder = StateGraph(OverallState)
        
        # 添加節點
        builder.add_node("generate_query_or_plan", self.generate_query_or_plan)
        builder.add_node("execute_tools", self.execute_tools)
        builder.add_node("reflection", self.reflection)
        builder.add_node("finalize_answer", self.finalize_answer)
        
        # 設置流程
        builder.add_edge(START, "generate_query_or_plan")
        
        # 條件路由：根據計劃決定下一步
        builder.add_conditional_edges(
            "generate_query_or_plan",
            self.route_after_planning,
            {
                "use_tools": "execute_tools",
                "direct_answer": "finalize_answer"
            }
        )
        
        # 工具執行後的反思
        builder.add_edge("execute_tools", "reflection")
        
        # 反思後的路由決策
        builder.add_conditional_edges(
            "reflection",
            self.decide_next_step,
            {
                "continue": "generate_query_or_plan",  # 重新規劃下一輪
                "finish": "finalize_answer"
            }
        )
        
        builder.add_edge("finalize_answer", END)
        return builder.compile()
    
    def route_after_planning(self, state: OverallState) -> str:
        """規劃後的路由決策"""
        agent_plan = state.agent_plan
        if agent_plan.needs_tools and agent_plan.tool_plans:
            return "use_tools"
        else:
            return "direct_answer"
    
    def continue_to_tool_execution(self, state: OverallState):
        """並行執行工具（參考 Gemini 實作）"""
        agent_plan = state.agent_plan
        
        # 為每個工具計劃創建並行執行任務
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
    ```

- [ ] **Task 2.3**: 重構工具執行邏輯
  - 實現並行工具執行
  - 支援多種工具類型（Google Search, Citation 等）
  - 優化結果聚合和去重
  - **參考實現**:
    ```python
    async def execute_single_tool(self, state: ToolExecutionState) -> Dict[str, Any]:
        """執行單個工具任務（並行節點）"""
        tool_name = state.tool_name
        query = state.query
        task_id = state.task_id
        
        try:
            if tool_name == "google_search":
                result = await self._execute_google_search_single(query, task_id)
            elif tool_name == "citation":
                result = await self._execute_citation_single(query, task_id)
            else:
                result = f"未知工具: {tool_name}"
            
            return {
                "tool_results": [result],
                "task_id": task_id,
                "tool_name": tool_name
            }
            
        except Exception as e:
            self.logger.error(f"工具執行失敗 {tool_name}({query}): {e}")
            return {
                "tool_results": [],
                "task_id": task_id,
                "error": str(e)
            }
    
    async def execute_tools(self, state: OverallState) -> Dict[str, Any]:
        """聚合所有工具執行結果"""
        # 這個節點會自動等待所有並行的 execute_single_tool 完成
        # 然後聚合結果
        
        all_results = []
        for result in state.tool_results:
            if isinstance(result, list):
                all_results.extend(result)
            else:
                all_results.append(result)
        
        # 去重和排序
        unique_results = self._deduplicate_results(all_results)
        
        return {
            "aggregated_tool_results": unique_results,
            "tool_round": state.tool_round + 1
        }
    ```

- [ ] **Task 2.4**: 更新狀態管理
  - 擴展 `OverallState` 支援新的計劃結構
  - 添加工具執行狀態追蹤
  - 優化狀態傳遞效率
  - **參考實現**:
    ```python
    # schemas/agent_types.py
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

**測試驗證**:
```bash
# 測試新的計劃生成
python -c "from agent_core.graph import UnifiedAgent; agent = UnifiedAgent(); print('✓ 新流程構建成功')"

# 測試並行工具執行
python test_parallel_tools.py
```

#### 預期改進效果
1. **流程簡化**: 從 4 個主要節點減少到 3 個，邏輯更清晰
2. **效率提升**: 並行執行工具，減少總執行時間
3. **決策統一**: 在一個節點內完成所有工具決策，避免邏輯分散
4. **更好的可控性**: 通過結構化輸出精確控制工具使用策略

### Phase 3: Persona 系統整合與 System Prompt 統一 (1 week)

#### 目標
將 Persona 系統完全整合到 Agent 主流程中，並統一 system prompt 處理。

#### 任務清單

- [ ] **Task 3.1**: 建立統一的 System Prompt 管理器
  - 建立 `prompt_system/system_prompt_manager.py`
  - 統一處理所有 system prompt 相關邏輯
  - 支援動態格式化（current date/time 等）
  - **參考實現**:
    ```python
    # prompt_system/system_prompt_manager.py
    from datetime import datetime
    from typing import Optional, Dict, Any
    from schemas.config_types import AppConfig
    from .persona_manager import PersonaManager
    
    class SystemPromptManager:
        def __init__(self, config: AppConfig):
            self.config = config
            self.persona_manager = PersonaManager(config.prompt_system.persona)
        
        def build_system_prompt(self, 
                               context: str = "",
                               persona_name: Optional[str] = None,
                               discord_context: Optional[Dict] = None) -> str:
            """構建完整的系統提示詞"""
            parts = []
            
            # 1. 基礎 persona
            persona_prompt = self.persona_manager.get_system_prompt(persona_name)
            if persona_prompt:
                parts.append(persona_prompt)
            
            # 2. 動態格式化資訊
            dynamic_info = self._build_dynamic_info()
            if dynamic_info:
                parts.append(dynamic_info)
            
            # 3. 上下文資訊
            if context:
                context_prompt = f"以下是相關資訊，請用於回答問題：\n{context}"
                parts.append(context_prompt)
            
            # 4. Discord 特定資訊
            if discord_context:
                discord_info = self._build_discord_context(discord_context)
                if discord_info:
                    parts.append(discord_info)
            
            return "\n\n".join(parts)
        
        def _build_dynamic_info(self) -> str:
            """構建動態資訊（時間、日期等）"""
            from prompt_system.prompts import get_current_date
            
            current_date = get_current_date(self.config.system.timezone)
            return f"當前日期時間：{current_date}"
        
        def _build_discord_context(self, discord_context: Dict) -> str:
            """構建 Discord 上下文資訊"""
            # 實現 Discord 特定的上下文處理
            pass
    ```

- [ ] **Task 3.2**: 建立 Persona 管理器
  - 建立 `prompt_system/persona_manager.py`
  - 整合現有的 persona 選擇邏輯
  - 支援動態 persona 切換
  - **參考實現**:
    ```python
    # prompt_system/persona_manager.py
    class PersonaManager:
        def __init__(self, config: PromptPersonaConfig):
            self.config = config
            self._cache = {}
        
        def get_system_prompt(self, persona_name: Optional[str] = None) -> str:
            """獲取系統提示詞"""
            if persona_name:
                return self._load_specific_persona(persona_name)
            elif self.config.random_selection:
                return self._load_random_persona()
            else:
                return self._load_default_persona()
    ```

- [ ] **Task 3.3**: 重構 `agent_core/graph.py` 使用統一 System Prompt
  - 移除 `_generate_final_answer` 中分散的 system prompt 邏輯
  - 使用 `SystemPromptManager` 統一處理
  - **參考修改**:
    ```python
    # agent_core/graph.py
    from prompt_system.system_prompt_manager import SystemPromptManager
    
    class UnifiedAgent(ProgressMixin):
        def __init__(self, config: AppConfig):
            # ...
            self.system_prompt_manager = SystemPromptManager(config)
        
        def _generate_final_answer(self, messages: List[MsgNode], context: str) -> str:
            """生成最終答案（使用統一 System Prompt）"""
            # 構建統一的系統提示詞
            system_prompt = self.system_prompt_manager.build_system_prompt(
                context=context,
                persona_name=None,  # 或從配置/狀態獲取
                discord_context=None  # 如果需要的話
            )
            
            messages_for_final_answer = [SystemMessage(content=system_prompt)]
            # ... 其餘邏輯
    ```

**測試驗證**:
```bash
# 測試 persona 和 system prompt 系統
python -c "from prompt_system.system_prompt_manager import SystemPromptManager; print('✓ System prompt manager works')"
```

### Phase 4: 整合 Streaming 到 Progress 系統 (1-2 weeks)

#### 目標
將 Discord streaming 整合到 progress_mixin 中，實現統一的進度和串流管理。

#### 任務清單

- [ ] **Task 4.1**: 擴展 Progress 系統支援 Streaming
  - 修改 `agent_core/progress_observer.py` 添加串流事件
  - 修改 `agent_core/progress_mixin.py` 支援串流通知
  - **參考實現**:
    ```python
    # agent_core/progress_observer.py
    @dataclass
    class StreamingChunk:
        content: str
        is_final: bool = False
        chunk_id: Optional[str] = None
        metadata: Dict[str, Any] = field(default_factory=dict)
    
    class ProgressObserver(ABC):
        # ... 現有方法 ...
        
        @abstractmethod
        async def on_streaming_chunk(self, chunk: StreamingChunk) -> None:
            """處理串流塊"""
            pass
        
        @abstractmethod
        async def on_streaming_complete(self) -> None:
            """處理串流完成"""
            pass
    
    # agent_core/progress_mixin.py
    class ProgressMixin:
        # ... 現有方法 ...
        
        async def _notify_streaming_chunk(self, content: str, is_final: bool = False, **metadata):
            """通知串流塊"""
            chunk = StreamingChunk(
                content=content,
                is_final=is_final,
                metadata=metadata
            )
            
            for observer in self._progress_observers:
                try:
                    await observer.on_streaming_chunk(chunk)
                except Exception as e:
                    self.logger.error(f"串流通知失敗: {e}")
        
        async def stream_response(self, content: str, 
                                chunk_size: int = 50,
                                delay_ms: int = 50) -> None:
            """串流回應內容"""
            words = content.split()
            current_chunk = ""
            
            for word in words:
                current_chunk += word + " "
                if len(current_chunk) >= chunk_size:
                    await self._notify_streaming_chunk(current_chunk.strip())
                    current_chunk = ""
                    await asyncio.sleep(delay_ms / 1000)
            
            if current_chunk:
                await self._notify_streaming_chunk(current_chunk.strip(), is_final=True)
            
            # 通知串流完成
            for observer in self._progress_observers:
                try:
                    await observer.on_streaming_complete()
                except Exception as e:
                    self.logger.error(f"串流完成通知失敗: {e}")
    ```

- [ ] **Task 4.2**: 更新 Discord Progress Adapter 支援 Streaming
  - 修改 `discord_bot/progress_adapter.py` 實現串流方法
  - 根據 `config.progress.discord.update_interval` 控制更新頻率
  - **參考實現**:
    ```python
    # discord_bot/progress_adapter.py
    class DiscordProgressAdapter(ProgressObserver):
        def __init__(self, original_message: discord.Message, config: AppConfig):
            self.original_message = original_message
            self.config = config
            self.progress_manager = get_progress_manager()
            self._streaming_content = ""
            self._last_update = 0
            self._streaming_message: Optional[discord.Message] = None
        
        async def on_streaming_chunk(self, chunk: StreamingChunk) -> None:
            """處理串流塊"""
            self._streaming_content += chunk.content
            
            current_time = time.time()
            update_interval = self.config.progress.discord.update_interval
            
            # 根據配置的更新間隔決定是否更新
            if (current_time - self._last_update >= update_interval) or chunk.is_final:
                await self._update_streaming_message()
                self._last_update = current_time
        
        async def on_streaming_complete(self) -> None:
            """處理串流完成"""
            if self._streaming_message:
                # 移除串流指示器，標記完成
                final_embed = discord.Embed(
                    description=self._streaming_content,
                    color=discord.Color.green()
                )
                await self._streaming_message.edit(embed=final_embed)
        
        async def _update_streaming_message(self):
            """更新串流訊息"""
            embed = discord.Embed(
                description=self._streaming_content + " ⚪",  # 串流指示器
                color=discord.Color.orange()
            )
            
            if self._streaming_message:
                await self._streaming_message.edit(embed=embed)
            else:
                self._streaming_message = await self.original_message.reply(embed=embed)
    ```

- [ ] **Task 4.3**: 修改 Agent 支援 Streaming
  - 修改 `agent_core/graph.py` 的 `finalize_answer` 節點支援串流
  - 根據配置決定是否啟用串流
  - **參考實現**:
    ```python
    async def finalize_answer(self, state: OverallState) -> Dict[str, Any]:
        # ... 生成答案邏輯 ...
        
        # 根據配置決定是否串流
        if self.config.progress.discord.enabled and self._progress_observers:
            # 串流回應
            await self.stream_response(
                final_answer,
                chunk_size=self.config.streaming.chunk_size,
                delay_ms=self.config.streaming.delay_ms
            )
        
        return {"final_answer": final_answer, "finished": True}
    ```

**測試驗證**:
```bash
# 測試串流功能
python -c "from agent_core.progress_mixin import ProgressMixin; print('✓ Streaming mixin works')"
```

### Phase 5: 整合測試與優化 (1 week)

#### 目標
確保所有新功能正常運作，進行性能優化。

#### 任務清單

- [ ] **Task 5.1**: 端到端測試
  - 測試完整的 Discord Bot 流程
  - 測試 CLI 介面
  - 測試所有工具和 persona 組合
  - 測試串流回應功能

- [ ] **Task 5.2**: 性能優化
  - 優化配置載入性能
  - 優化工具執行性能
  - 優化串流回應性能

- [ ] **Task 5.3**: 錯誤處理改進
  - 完善所有模組的錯誤處理
  - 添加詳細的錯誤日誌
  - 實現優雅的降級機制

- [ ] **Task 5.4**: 文檔更新
  - 更新配置文檔
  - 更新工具開發指南
  - 更新部署指南

**測試驗證**:
```bash
# 完整功能測試
python -m pytest tests/ -v
python cli_main.py "測試問題"
# Discord Bot 手動測試（包含串流功能）
```

---

## 5. 成功標準與驗收條件

### 5.1 功能性標準
- [ ] 完全消除字串 key 配置存取
- [ ] Agent 能智能選擇和使用工具
- [ ] Persona 系統完全整合到主流程
- [ ] 支援即時串流回應
- [ ] 保留所有現有功能

### 5.2 代碼品質標準
- [ ] 型別安全的配置系統
- [ ] 標準化的工具介面
- [ ] 清晰的模組職責分離
- [ ] 完善的錯誤處理

### 5.3 性能標準
- [ ] 配置載入時間 < 100ms
- [ ] 工具執行響應時間合理
- [ ] 串流回應延遲 < 100ms
- [ ] 記憶體使用穩定

---

## 6. 總結

本重構提案重點解決了四個核心問題：

1. **型別安全配置**: 完全消除字串 key 存取，提升代碼安全性
2. **智能工具系統**: 讓 Agent 能根據工具描述自主決定使用哪些工具
3. **Persona 整合**: 將 persona 系統完全整合到主流程中
4. **串流回應**: 實現即時回應，提升用戶體驗

這些改進將使系統更加健壯、可維護和用戶友好。