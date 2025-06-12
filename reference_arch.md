# 參考架構文件 (Reference Architecture Document)

## 0. 專案概述 (Project Overview)

本專案是一個基於 LangGraph 的智慧代理程式，專為執行網路研究並生成帶有引用資訊的答案而設計。它透過多個模組協同工作，實現從接收使用者問題到提供綜合答案的自動化流程。

## 1. 核心流程 (Core Process Flow)

該代理程式的運作流程由 LangGraph 定義，形成一個多步驟的狀態機迴圈：

1.  **起始 (START)** -> **生成查詢 (`generate_query`)**:
    *   代理程式從使用者輸入的問題開始，`generate_query` 節點負責根據該問題生成一或多個初始搜尋查詢。

2.  **生成查詢 (`generate_query`)** -> **繼續網路研究 (`continue_to_web_research`)** -> **網路研究 (`web_research`)** (平行執行):
    *   `continue_to_web_research` 節點會將生成的搜尋查詢分派給多個平行的 `web_research` 節點，每個節點獨立執行網路搜尋。

3.  **網路研究 (`web_research`)** -> **反思 (`reflection`)**:
    *   所有平行網路研究完成後，代理程式進入 `reflection` 節點，評估收集到的資訊是否足以回答問題，並識別知識缺口。

4.  **反思 (`reflection`)** -> **評估研究 (`evaluate_research`)** (條件路由):
    *   `evaluate_research` 節點根據 `reflection` 節點的評估結果和預設的最大研究迴圈次數來決定下一步：
        *   若資訊足夠或達到最大迴圈次數，流程轉至 **最終答案 (`finalize_answer`)** 節點。
        *   若資訊不足且未達到最大迴圈次數，流程返回 **網路研究 (`web_research`)** 節點，使用追蹤查詢再次執行網路研究。

5.  **評估研究 (`evaluate_research`)** -> **最終答案 (`finalize_answer`)** -> **結束 (END)**:
    *   `finalize_answer` 節點負責整理所有研究結果和來源，並生成最終的高品質答案，包含正確的引用。

## 2. 模組詳解 (Module Details)

### 2.1 `state.py` - 共享狀態定義

*   **目的**: 定義代理程式在不同處理階段之間共享的資料結構和狀態。它使用了 Python 的 `TypedDict` 和 `dataclass` 來結構化數據，確保數據的一致性和可預測性。
*   **關鍵類別**:
    *   `OverallState`: 代理程式的整體狀態，包含訊息、搜尋查詢、網路研究結果、收集到的來源、研究迴圈計數等。
    *   `ReflectionState`: 儲存反思階段的狀態，包括資訊是否足夠、知識缺口描述和追蹤查詢。
    *   `Query`: 定義單個查詢的結構，包含查詢字串和理由。
    *   `QueryGenerationState`: 儲存查詢生成階段的狀態，主要是生成的查詢列表。
    *   `WebSearchState`: 儲存網路搜尋階段的狀態，包含要搜尋的查詢和唯一的 ID。

### 2.2 `tools_and_schemas.py` - 工具與架構定義

*   **目的**: 定義用於與大型語言模型 (LLM) 進行結構化輸入/輸出交互的 Pydantic 模型。這些模型確保數據的格式化和驗證，使代理程式能夠以可預測的方式與 LLM 互動。
*   **關鍵類別**:
    *   `SearchQueryList`: 用於定義生成的搜尋查詢列表及其理由的結構。
    *   `Reflection`: 用於定義反思結果的結構，包括資訊是否足夠、知識缺口和追蹤查詢。

### 2.3 `prompts.py` - 提示管理

*   **目的**: 包含用於引導 LLM 在不同階段（例如查詢生成、網路搜尋、反思和答案生成）行為的文本提示。這些提示是動態格式化的，以包含上下文資訊（如研究主題、當前日期等），確保 LLM 的回應符合預期。
*   **關鍵提示**:
    *   `query_writer_instructions`: 指導 LLM 如何生成優化和多樣化的網路搜尋查詢。
    *   `web_searcher_instructions`: 指導 LLM 如何執行目標性 Google 搜尋並綜合資訊。
    *   `reflection_instructions`: 指導 LLM 如何分析摘要、識別知識缺口並生成追蹤查詢。
    *   `answer_instructions`: 指導 LLM 如何根據收集到的資訊生成高品質的最終答案。

### 2.4 `utils.py` - 輔助函數與實用程式

*   **目的**: 提供一系列輔助函數和實用程式，用於資料處理、URL 解析、引用管理等，這些功能在代理程式的各個節點中被重複使用，提高了程式碼的重用性和可維護性。
*   **關鍵函數**:
    *   `get_research_topic(messages)`: 從 LangChain 訊息列表中提取研究主題。
    *   `resolve_urls(urls_to_resolve, id)`: 將 Vertex AI 搜尋結果中冗長的 URL 映射為簡短的、帶有唯一 ID 的 URL，以節省 Token 並提高可讀性。
    *   `insert_citation_markers(text, citations_list)`: 根據提供的引用資訊，將引用標記（例如 `[1](short_url)`）插入到文本字串中。
    *   `get_citations(response, resolved_urls_map)`: 從 Gemini 模型的回應中提取和格式化引用資訊，包括引用文本的索引和相關來源。

### 2.5 `graph.py` - 代理程式核心協調器 (LangGraph)

*   **目的**: 作為代理程式的核心協調器，使用 LangGraph 框架定義了整個工作流程的節點、邊和條件邏輯。它將其他模組中的功能組合成一個連貫的研究流程。
*   **核心組件**:
    *   `StateGraph`: 定義了代理程式的狀態機。
    *   **節點 (Nodes)**: 每個節點代表工作流程中的一個特定步驟。
        *   `generate_query(state, config)`:
            *   **職責**: 根據使用者問題生成初始搜尋查詢列表。
            *   **實現**: 使用 `ChatGoogleGenerativeAI` (基於 `configurable.query_generator_model`，預設為 `gemini-2.0-flash`) 和 `SearchQueryList` 結構化輸出。
        *   `continue_to_web_research(state)`:
            *   **職責**: 一個路由函數，將生成的搜尋查詢分派給多個並行的 `web_research` 節點。
        *   `web_research(state, config)`:
            *   **職責**: 執行網路搜尋，收集資訊，並生成初步的網路研究結果，同時處理引用。
            *   **API 使用**: 透過 **Google Gemini API** 的 `genai_client.models.generate_content` 方法執行網路搜尋。
                *   **客戶端**:
                    ```python
                    genai_client = Client(api_key=os.getenv("GEMINI_API_KEY"))
                    ```
                *   **模型**:
                    ```
                    model=configurable.query_generator_model
                    ```
                    (預設為 `gemini-2.0-flash`)。
                *   **內容**:
                    ```
                    contents=formatted_prompt
                    ```
                *   **配置**:
                    ```python
                    config={"tools": [{"google_search": {}}], "temperature": 0}
                    ```
                    。關鍵在於啟用 `google_search` 工具，讓模型自動執行搜尋。
            *   **API 呼叫流程**:
                1.  **格式化提示**: 根據 `web_searcher_instructions` 和當前的研究主題，準備好傳遞給 Gemini 模型的提示。
                2.  **執行 `generate_content`**: 呼叫 `genai_client.models.generate_content`，模型會根據提示和配置（啟用 `google_search` 工具）執行網路搜尋。
                3.  **接收回應**: Gemini API 返回包含搜尋結果和接地元數據的回應對象。
            *   **結果處理**:
                *   **URL 解析 (`resolve_urls`)**:
                    ```python
                    resolved_urls = resolve_urls(response.candidates[0].grounding_metadata.grounding_chunks, state["id"])
                    ```
                *   **獲取引用 (`get_citations`)**:
                    ```python
                    citations = get_citations(response, resolved_urls)
                    ```
                *   **插入引用標記 (`insert_citation_markers`)**:
                    ```python
                    modified_text = insert_citation_markers(response.text, citations)
                    ```
                *   **收集來源**:
                    ```python
                    sources_gathered = [item for citation in citations for item in citation["segments"]]
                    ```
            *   **職責總結**: 執行網路搜尋、理解並綜合結果、管理引用、更新狀態。
        *   `reflection(state, config)`:
            *   **職責**: 分析當前的研究摘要，識別知識缺口，並生成潛在的追蹤查詢。
            *   **實現**: 使用 `ChatGoogleGenerativeAI` (基於 `configurable.reasoning_model` 或預設模型) 和 `Reflection` 結構化輸出。
        *   `evaluate_research(state, config)`:
            *   **職責**: 路由函數，根據反思結果和最大研究迴圈次數，決定是繼續網路研究還是最終確定答案。
        *   `finalize_answer(state, config)`:
            *   **職責**: 整理所有收集到的研究結果和引用，生成高品質的最終答案。
            *   **實現**: 使用 `ChatGoogleGenerativeAI` (基於 `configurable.reasoning_model` 或預設模型) 和 `answer_instructions` 提示。處理並替換短 URL 為原始 URL。
    *   **邊 (Edges)**: 定義了節點之間的轉換邏輯，包括條件邊緣 (`add_conditional_edges`)，實現了靈活的流程控制。

### 2.6 `configuration.py` - 配置管理

*   **目的**: 管理代理程式的各種配置參數，如使用的 LLM 模型名稱、初始搜尋查詢數量和最大研究迴圈次數。這允許在不修改核心邏輯的情況下，通過環境變數或程式碼配置輕鬆調整代理程式行為。
*   **關鍵參數**:
    *   `query_generator_model`: 用於查詢生成的模型名稱。
    *   `reflection_model`: 用於反思的模型名稱。
    *   `answer_model`: 用於答案生成的模型名稱。
    *   `number_of_initial_queries`: 初始生成搜尋查詢的數量。
    *   `max_research_loops`: 執行研究迴圈的最大次數。

### 2.7 `app.py` - 應用程式入口點

*   **目的**: 作為 FastAPI 應用程式的主入口點，負責設定 API 路由、掛載靜態文件（如前端應用），並初始化代理程式。
*   **主要功能**:
    *   創建 FastAPI 應用實例。
    *   `create_frontend_router()`: 函數用於創建一個路由來服務 React 前端應用程式的靜態文件，確保前端和後端可以協同工作。
    *   掛載前端應用: 將前端靜態文件掛載到 `/app` 路徑下，避免與 API 路由衝突。

## 3. 架構總結表 (Architecture Summary Table)

| 檔案名稱 / 模組       | 主要職責                             | 關鍵組件 / 功能                                              |
| :-------------------- | :----------------------------------- | :----------------------------------------------------------- |
| `state.py`            | 定義代理程式的共享狀態和資料結構     | `OverallState`, `ReflectionState`, `Query`, `WebSearchState` |
| `tools_and_schemas.py` | 定義 LLM 結構化輸入/輸出模型         | `SearchQueryList`, `Reflection`                              |
| `prompts.py`          | 管理 LLM 的提示文本                  | `query_writer_instructions`, `web_searcher_instructions`, `reflection_instructions`, `answer_instructions` |
| `utils.py`            | 提供輔助函數和實用程式               | `get_research_topic`, `resolve_urls`, `insert_citation_markers`, `get_citations` |
| `graph.py`            | 代理程式核心協調器 (LangGraph)       | `StateGraph`, `generate_query`, `web_research`, `reflection`, `finalize_answer` (節點); 邊緣定義 |
| `configuration.py`    | 管理代理程式的配置參數               | `query_generator_model`, `reflection_model`, `answer_model`, `max_research_loops` |
| `app.py`              | 應用程式入口點，設置 FastAPI 和前端服務 | FastAPI 實例, `create_frontend_router`, 前端靜態文件掛載 |

## 4. `web_research` 節點詳解

### 4.1 目的
`web_research` 節點是代理程式的核心研究組件，其主要目的是執行網路搜尋，收集與特定研究主題相關的最新、可靠資訊，並將這些資訊整合為可驗證的文本內容。它負責與外部搜尋服務互動，並對搜尋結果進行初步處理，以便後續的反思和答案生成階段使用。

### 4.2 API 使用
`web_research` 節點透過 **Google Gemini API** 執行網路搜尋。具體來說，它利用 `google.genai.Client` 提供的 `models.generate_content` 方法，並在請求配置中啟用 `google_search` 工具。

#### API 呼叫細節:
*   **客戶端 (Client)**: 
    ```python
    genai_client = Client(api_key=os.getenv("GEMINI_API_KEY"))
    ```
    這行程式碼初始化了 Google Gemini API 的客戶端，它需要 `GEMINI_API_KEY` 環境變數來進行認證。
*   **方法 (Method)**: 
    ```
    genai_client.models.generate_content
    ```
    這是用於生成內容並利用模型工具的主要方法。
*   **模型 (Model)**: 
    ```
    model=configurable.query_generator_model
    ```
    模型名稱由 `Configuration` 物件提供，預設為 `gemini-2.0-flash`。此模型負責理解搜尋提示並調用 `google_search` 工具。
*   **內容 (Contents)**: 
    ```
    contents=formatted_prompt
    ```
    `formatted_prompt` 是從 `prompts.py` 中的 `web_searcher_instructions` 格式化而來，其中包含了當前日期和研究主題，指導模型如何進行搜尋。
*   **配置 (Config)**: 
    ```python
    config={"tools": [{"google_search": {}}], "temperature": 0}
    ```
    這是 API 呼叫的關鍵部分：
    *   `"tools": [{"google_search": {}}]`: 明確告知 Gemini 模型應使用 `google_search` 工具來完成任務。這允許模型在需要時自動執行網路搜尋。
    *   `"temperature": 0`: 將溫度設置為 0，這意味著模型在生成回應時會更具確定性和專注於事實，這對於研究任務至關重要。

#### API 呼叫流程:
1.  **格式化提示**: 根據 `web_searcher_instructions` 和當前的研究主題，準備好傳遞給 Gemini 模型的提示。
2.  **執行 `generate_content`**: 呼叫 `genai_client.models.generate_content`，模型會根據提示和配置（啟用 `google_search` 工具）執行網路搜尋。
3.  **接收回應**: Gemini API 返回包含搜尋結果和接地元數據 (grounding metadata) 的回應對象。

### 4.3 結果處理

收到 Gemini API 的回應後，`web_research` 節點會對結果進行進一步處理，特別是處理搜尋結果的引用資訊：

*   **URL 解析 (`resolve_urls`)**:
    ```python
    resolved_urls = resolve_urls(response.candidates[0].grounding_metadata.grounding_chunks, state["id"])
    ```
    `resolve_urls` 函數（來自 `utils.py`）會將 Gemini API 返回的冗長或內部 URL 映射為簡短且易於閱讀的 URL。這有助於在最終答案中節省 token 和提高可讀性。

*   **獲取引用 (`get_citations`)**:
    ```python
    citations = get_citations(response, resolved_urls)
    ```
    `get_citations` 函數（來自 `utils.py`）從 Gemini 回應的 `grounding_metadata` 中提取引用資訊。這包括引用文本的起始和結束索引，以及相關的來源 URL。

*   **插入引用標記 (`insert_citation_markers`)**:
    ```python
    modified_text = insert_citation_markers(response.text, citations)
    ```
    `insert_citation_markers` 函數（來自 `utils.py`）將格式化後的引用標記（例如 `[1](short_url)`）插入到模型生成的文本內容中，確保最終答案中的資訊來源可追溯。

*   **收集來源**:
    ```python
    sources_gathered = [item for citation in citations for item in citation["segments"]]
    ```
    此步驟從處理後的引用中收集所有唯一的來源資訊，這些來源將在最終答案階段提供給使用者。

### 4.4 職責總結

`web_research` 節點的職責可以總結為：
*   **執行網路搜尋**: 利用 Google Gemini API 和 `google_search` 工具。
*   **結果理解與綜合**: 讓 LLM 理解搜尋結果，並將其綜合為連貫的文本。
*   **引用管理**: 處理搜尋結果中的引用資訊，包括 URL 解析、引用提取和在文本中插入引用標記。
*   **狀態更新**: 將處理後的網路研究結果、收集到的來源和更新的搜尋查詢儲存到 `OverallState` 中，供後續節點使用。

這個模組化的設計使得網路搜尋功能清晰且可管理，並且能夠確保在最終答案中包含準確的引用。 