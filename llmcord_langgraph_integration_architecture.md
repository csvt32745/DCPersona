# llmcord + LangGraph 整合架構設計方案

## 專案概述 🌟

本方案將 **gemini-fullstack-langgraph-quickstart backend** 的智能研究能力整合到 **llmcord** Discord bot 中，重點加強狀態管理和多輪對話能力，讓 Discord bot 能夠進行更智能的持續對話和資訊收集。

## 整合後的架構設計 🏗️

### 完整目錄結構

```
llmcord/
│
├── main.py                        # 主程式入口
├── config.yaml                    # 設定檔 (擴展支援 LangGraph 配置)
├── persona/                       # 系統提示詞資料夾
│
├── core/
│   ├── __init__.py
│   ├── config.py                  # 設定檔讀取與管理 (新增 LangGraph 配置)
│   ├── logger.py                  # 日誌系統設定
│   └── utils.py                   # 通用工具函式
│
├── discordbot/
│   ├── __init__.py
│   ├── client.py                  # Discord client 初始化
│   ├── message_handler.py         # 訊息事件處理主流程 (整合狀態管理)
│   └── msg_node.py                # MsgNode 類別定義與訊息快取
│
├── pipeline/
│   ├── __init__.py
│   ├── collector.py               # 訊息收集與預處理
│   ├── rag.py                     # **[核心整合點]** 智能 RAG 路由系統
│   ├── llm.py                     # LLM 輸入組裝與 API 呼叫
│   ├── postprocess.py             # LLM 回覆的後處理與發送
│   │
│   └── langgraph/                 # **[新增]** LangGraph 研究系統
│       ├── __init__.py
│       ├── state.py               # 狀態定義與管理
│       ├── graph.py               # LangGraph 工作流定義
│       ├── agents.py              # 各個研究節點實現
│       ├── prompts.py             # LangGraph 專用提示詞
│       ├── tools.py               # 工具與結構化輸出定義
│       ├── config.py              # LangGraph 專用配置
│       └── session_manager.py     # **[核心]** 會話狀態管理器
│
├── storage/                       # **[新增]** 狀態持久化
│   ├── __init__.py
│   ├── memory_store.py            # 記憶體狀態管理
│   ├── serializer.py              # 狀態序列化/反序列化
│   └── session_data/              # 序列化狀態檔案目錄
│
└── tools/
    ├── __init__.py
    └── google_search.py           # Google Search 工具實作
```

## 核心整合點設計 🔧

### 1. 智能 RAG 路由系統 (`pipeline/rag.py`)

```python
# 核心架構設計
class IntelligentRAGRouter:
    def __init__(self):
        self.session_manager = LangGraphSessionManager()
        self.simple_search = GoogleSearchTool()
        
    async def process_query(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """智能路由決策系統"""
        query_type = await self.analyze_query_complexity(message_data)
        
        if query_type == "simple":
            return await self.simple_search_flow(message_data)
        elif query_type == "research":
            return await self.langgraph_research_flow(message_data)
        else:
            return await self.conversational_flow(message_data)
```

### 2. 會話狀態管理器 (`pipeline/langgraph/session_manager.py`)

```python
class LangGraphSessionManager:
    """管理 Discord 頻道的 LangGraph 研究會話"""
    
    def __init__(self):
        self.active_sessions = {}  # 記憶體狀態
        self.serializer = StateSerializer()
        
    async def get_or_create_session(self, channel_id: int, user_id: int):
        """獲取或創建研究會話"""
        
    async def update_session_state(self, session_id: str, state_update: Dict):
        """更新會話狀態並觸發序列化"""
        
    async def cleanup_expired_sessions(self):
        """清理過期會話"""
```

### 3. Discord 整合的 LangGraph 工作流 (`pipeline/langgraph/graph.py`)

```python
class DiscordLangGraphWorkflow:
    """適配 Discord 環境的 LangGraph 工作流"""
    
    def __init__(self):
        self.graph = self.build_discord_adapted_graph()
        
    def build_discord_adapted_graph(self):
        """構建適合 Discord 環境的研究圖"""
        builder = StateGraph(DiscordOverallState)
        
        # 節點定義
        builder.add_node("query_analysis", self.analyze_discord_query)
        builder.add_node("web_research", self.discord_web_research)
        builder.add_node("reflection", self.discord_reflection)
        builder.add_node("response_formatting", self.format_for_discord)
        
        # 流程定義
        builder.add_edge(START, "query_analysis")
        builder.add_conditional_edges("query_analysis", self.route_next_step)
        
        return builder.compile()
```

## 狀態管理架構 📊

### Discord 適配的狀態結構

```python
class DiscordOverallState(TypedDict):
    # 原有 LangGraph 狀態
    messages: Annotated[list, add_messages]
    search_query: Annotated[list, operator.add]
    web_research_result: Annotated[list, operator.add]
    sources_gathered: Annotated[list, operator.add]
    
    # Discord 專用狀態
    discord_channel_id: int
    discord_user_id: int
    session_id: str
    conversation_context: Annotated[list, operator.add]
    response_mode: str  # "immediate", "progressive", "final"
    
    # 智能對話狀態
    conversation_history: Annotated[list, add_messages]
    user_intent: str
    current_research_topic: str
    research_depth_level: int
```

### 記憶體狀態管理 (`storage/memory_store.py`)

```python
class MemoryStateStore:
    """記憶體狀態存儲，配合定期序列化"""
    
    def __init__(self, serialization_interval: int = 300):  # 5分鐘序列化一次
        self.sessions = {}
        self.last_updated = {}
        self.serialization_interval = serialization_interval
        self.start_background_tasks()
    
    async def store_session(self, session_id: str, state: Dict):
        """存儲會話狀態到記憶體"""
        
    async def get_session(self, session_id: str) -> Optional[Dict]:
        """從記憶體獲取會話狀態"""
        
    async def periodic_serialization(self):
        """定期序列化狀態到檔案"""
```

## 資料流程設計 🔄

### 整合後的訊息處理流程

```
Discord 訊息接收
         ↓
    權限與配置檢查
         ↓
    訊息收集與預處理 (collector.py)
         ↓
    智能 RAG 路由決策 (rag.py)
         ↓
    ┌─────────────────┬─────────────────┬─────────────────┐
    ↓                 ↓                 ↓                 ↓
簡單查詢模式        研究模式           對話模式         混合模式
(Google Search)    (LangGraph)      (Context Aware)   (動態切換)
    ↓                 ↓                 ↓                 ↓
    └─────────────────┴─────────────────┴─────────────────┘
                              ↓
                        LLM 處理 (llm.py)
                              ↓
                      後處理與回覆 (postprocess.py)
                              ↓
                        Discord 訊息發送
```

### LangGraph 研究流程在 Discord 中的適配

```
用戶查詢 → 查詢分析 → 生成搜尋策略
    ↓
會話狀態檢查 ← 狀態管理器 → 載入歷史上下文
    ↓
多輪網路研究 → 即時進度更新 (Discord 訊息)
    ↓
反思與知識缺口分析 → 決定是否繼續研究
    ↓
最終答案整合 → Discord 格式化 → 發送回覆
    ↓
狀態序列化與清理
```

## 配置檔案擴展 ⚙️

### config.yaml 新增區塊

```yaml
# 原有配置保持不變...

# LangGraph 整合配置
langgraph:
  enabled: true
  
  # 查詢路由配置
  routing:
    simple_query_keywords: ["what", "when", "where", "who"]
    research_query_keywords: ["analyze", "compare", "research", "investigate"]
    complexity_threshold: 0.7
  
  # 狀態管理配置
  session_management:
    memory_store_size: 1000
    serialization_interval: 300  # 秒
    session_timeout: 3600  # 1小時
    max_conversation_history: 50
  
  # Gemini 配置
  gemini:
    api_key: "${GEMINI_API_KEY}"
    query_generator_model: "gemini-2.0-flash"
    reflection_model: "gemini-2.5-flash-preview-04-17"
    answer_model: "gemini-2.5-pro-preview-05-06"
  
  # 研究參數
  research:
    number_of_initial_queries: 3
    max_research_loops: 2
    enable_progressive_responses: true
    
  # Discord 適配
  discord:
    enable_typing_indicator: true
    progress_update_interval: 30  # 秒
    max_response_length: 2000
    enable_thread_for_long_research: true
```

## 實施路線圖 📅

### Phase 1: 基礎整合 (2-3 週)

**目標**: 建立核心架構和基本整合

**任務清單**:
- [ ] 創建 `pipeline/langgraph/` 目錄結構
- [ ] 實現 `session_manager.py` 基礎版本
- [ ] 擴展 `rag.py` 為智能路由系統
- [ ] 實現記憶體狀態管理 (`storage/memory_store.py`)
- [ ] 修改 `config.yaml` 支援 LangGraph 配置
- [ ] 基本的 Discord 狀態適配

**成功標準**:
- Discord bot 能夠識別查詢類型並路由到對應處理流程
- 基本的會話狀態能夠在記憶體中維護
- 簡單的 LangGraph 工作流能夠執行

### Phase 2: 智能對話能力 (3-4 週)

**目標**: 實現多輪對話和上下文感知

**任務清單**:
- [ ] 完善 `DiscordOverallState` 狀態結構
- [ ] 實現對話歷史管理和上下文感知
- [ ] 開發智能查詢分析系統
- [ ] 實現漸進式回應機制 (研究進度即時更新)
- [ ] 完善狀態序列化和恢復機制
- [ ] 添加會話清理和過期處理

**成功標準**:
- Bot 能夠記住對話歷史並在後續查詢中參考
- 複雜研究查詢能夠分多次回應，保持用戶參與
- 狀態能夠正確持久化和恢復

### Phase 3: 高級功能與優化 (2-3 週)

**目標**: 增強用戶體驗和系統穩定性

**任務清單**:
- [ ] 實現研究進度的視覺化顯示 (Discord Embed)
- [ ] 添加用戶中斷和重新開始研究的功能
- [ ] 實現多用戶並發研究會話管理
- [ ] 優化反思循環的 Discord 適配
- [ ] 添加詳細的日誌和監控
- [ ] 性能優化和錯誤處理

**成功標準**:
- 用戶體驗流暢，研究過程可視化
- 系統能夠穩定處理多用戶並發場景
- 完善的錯誤處理和恢復機制

### Phase 4: 進階特性 (1-2 週)

**目標**: 增加進階功能和自定義選項

**任務清單**:
- [ ] 實現用戶自定義研究參數 (深度、範圍等)
- [ ] 添加研究結果的不同展示模式
- [ ] 實現研究歷史的查詢和管理功能
- [ ] 添加統計和分析功能
- [ ] 文檔完善和部署指南

**成功標準**:
- 用戶可以根據需求自定義研究行為
- 完整的功能文檔和部署指南
- 生產環境就緒

## 技術挑戰與解決方案 🚧

### 1. Discord 即時性 vs LangGraph 多輪處理

**挑戰**: Discord 用戶期望即時回應，但 LangGraph 的研究流程可能需要較長時間

**解決方案**:
- **漸進式回應**: 研究過程中發送階段性更新
- **智能路由**: 根據查詢複雜度選擇合適的處理方式
- **異步處理**: 使用 Discord 的 typing indicator 和階段性訊息更新

```python
async def progressive_research_update(self, channel, session_id: str):
    """漸進式研究更新"""
    async with channel.typing():
        await channel.send("🔍 開始分析您的查詢...")
        
    # 執行初始查詢生成
    await channel.send("📝 生成搜尋策略中...")
    
    # Web 研究階段
    await channel.send("🌐 正在進行網路研究...")
    
    # 反思階段
    await channel.send("🤔 分析資訊完整性...")
    
    # 最終回答
    await channel.send("✅ 整理最終答案中...")
```

### 2. 狀態持久化與 Discord 會話管理

**挑戰**: LangGraph 需要複雜狀態管理，但 Discord 是無狀態的

**解決方案**:
- **混合存儲策略**: 記憶體 + 定期序列化
- **會話 ID 設計**: `{channel_id}_{user_id}_{timestamp}`
- **智能清理**: 基於時間和使用頻率的會話清理策略

```python
class SessionIDGenerator:
    @staticmethod
    def generate(channel_id: int, user_id: int) -> str:
        timestamp = int(time.time())
        return f"dc_{channel_id}_{user_id}_{timestamp}"
    
    @staticmethod
    def parse_session_id(session_id: str) -> Dict[str, int]:
        parts = session_id.split('_')
        return {
            'channel_id': int(parts[1]),
            'user_id': int(parts[2]),
            'timestamp': int(parts[3])
        }
```

### 3. 錯誤處理和降級策略

**挑戰**: LangGraph 流程可能在任何階段失敗，需要優雅處理

**解決方案**:
- **多層級降級**: LangGraph → 簡單搜尋 → 基礎回應
- **狀態恢復**: 從序列化狀態恢復中斷的研究
- **用戶通知**: 清晰的錯誤說明和建議操作

```python
class GracefulDegradation:
    async def handle_langgraph_failure(self, error, fallback_query):
        logging.warning(f"LangGraph 處理失敗: {error}")
        
        # 嘗試簡單搜尋
        try:
            return await self.simple_search_fallback(fallback_query)
        except Exception as e:
            logging.error(f"簡單搜尋也失敗: {e}")
            return self.generate_error_response()
```

### 4. 性能和記憶體優化

**挑戰**: 長時間運行可能導致記憶體洩漏和性能下降

**解決方案**:
- **智能緩存管理**: LRU 緩存 + 定期清理
- **資源限制**: 最大並發會話數限制
- **監控與警報**: 記憶體使用監控和自動清理

```python
class ResourceManager:
    def __init__(self, max_concurrent_sessions=50):
        self.max_sessions = max_concurrent_sessions
        self.session_queue = deque()
        
    async def acquire_session_slot(self) -> bool:
        if len(self.session_queue) >= self.max_sessions:
            # 清理最舊的會話
            await self.cleanup_oldest_session()
        return True
```

## 向後相容性考量 🔄

### 保持現有功能

1. **原有 pipeline 保持不變**: `collector.py`、`llm.py`、`postprocess.py` 的核心功能不變
2. **配置向下相容**: 原有 `config.yaml` 配置完全有效
3. **漸進式啟用**: LangGraph 功能可通過配置開關控制

### 遷移策略

```python
# 在 rag.py 中實現向後相容的接口
async def retrieve_augmented_context(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """保持原有接口，內部智能路由"""
    
    # 檢查 LangGraph 是否啟用
    if not config.get("langgraph", {}).get("enabled", False):
        # 使用原有的簡單實現
        return await simple_rag_implementation(message_data)
    
    # 使用新的智能路由系統
    return await intelligent_rag_router.process_query(message_data)
```

## 監控與維護 📊

### 關鍵指標監控

1. **會話指標**:
   - 活躍會話數量
   - 平均會話持續時間
   - 會話成功率

2. **性能指標**:
   - 響應時間分布
   - 記憶體使用量
   - LangGraph 執行成功率

3. **用戶體驗指標**:
   - 查詢滿意度
   - 功能使用分布
   - 錯誤發生頻率

### 日誌設計

```python
class IntegrationLogger:
    def log_session_created(self, session_id: str, user_id: int):
        logging.info(f"[SESSION] Created: {session_id} for user {user_id}")
    
    def log_langgraph_execution(self, session_id: str, node: str, duration: float):
        logging.info(f"[LANGGRAPH] {session_id} - {node}: {duration:.2f}s")
    
    def log_state_serialization(self, session_count: int, size_mb: float):
        logging.info(f"[STATE] Serialized {session_count} sessions, {size_mb:.2f}MB")
```

## 結論 🎯

這個整合方案將 LangGraph 的強大研究能力與 llmcord 的 Discord 整合優勢結合，創造出一個智能的多輪對話研究助手。重點特色包括：

✨ **智能狀態管理**: 記憶體 + 序列化的混合方案，平衡性能與持久性
🔄 **多輪對話能力**: 保持對話上下文，支援複雜的持續研究
🚀 **漸進式用戶體驗**: 即時回饋與深度研究的完美結合  
⚙️ **高度可配置**: 從簡單到複雜的多層級智능服務
🛡️ **穩健的錯誤處理**: 多層級降級策略確保服務可用性

通過這個架構，Discord 用戶將能夠享受到類似專業研究助手的體驗，同時保持 Discord bot 的即時性和易用性。整個系統設計充分考慮了向後相容性和漸進式部署的需求，可以安全地在現有 llmcord 部署中實施。