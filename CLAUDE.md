# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DCPersona** 是一個現代化的 Discord AI 助手，採用統一 Agent 架構和型別安全設計。基於 LangGraph 的智能工作流程，支援多模態輸入（文字、圖片、emoji、sticker、動畫）、智能工具決策和即時串流回應，為使用者提供流暢且智能的對話體驗。

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Copy configuration files
cp config-example.yaml config.yaml
cp emoji_config-example.yaml emoji_config.yaml

# Set environment variables (create .env file)
cp env.example .env
# Edit .env and set: GEMINI_API_KEY=your_gemini_api_key_here
```

### Running the Application
```bash
# Start Discord bot
python main.py

# Start CLI testing interface
python cli_main.py

# Docker deployment
docker compose up
```

### Testing
```bash
# Run all tests (pytest auto-mode enabled)
python -m pytest tests/ -v

# Run specific test modules
python -m pytest tests/test_agent_core_langchain_integration.py -v
python -m pytest tests/test_streaming.py -v
python -m pytest tests/test_progress_manager_concurrency.py -v
python -m pytest tests/test_wordle_integration.py -v
python -m pytest tests/test_emoji_system.py -v
python -m pytest tests/test_trend_following.py -v

# Run single test
python -m pytest tests/test_basic_structure.py::test_config_loading -v
```

## Core Architecture

### LangGraph State Machine
The heart of the system is `agent_core/graph.py` which implements a LangGraph StateGraph with these key nodes:
- `generate_query_or_plan`: Uses LLM with bound tools to decide tool usage
- `execute_tools_node`: Parallel tool execution with progress tracking  
- `reflection`: Evaluates tool results sufficiency
- `finalize_answer`: Generates final response with streaming support

### Type-Safe Configuration System
All configuration uses dataclasses in `schemas/config_types.py`:
- Complete type safety eliminates string key access
- Deep merging supports config inheritance from `config-example.yaml`
- Environment variable integration for API keys
- Runtime validation ensures configuration integrity

### Observer Pattern for Progress Management
- `agent_core/progress_observer.py`: Abstract observer interface
- `agent_core/progress_mixin.py`: Mixin providing progress notification
- `discord_bot/progress_adapter.py`: Discord-specific progress implementation
- `discord_bot/progress_manager.py`: Manages Discord message updates

### Tool System Architecture
Tools in `tools/` directory use LangChain's `@tool` decorator:
- `google_search.py`: Web search with result processing
- `youtube_summary.py`: Video content analysis with caching
- `set_reminder.py`: Natural language time parsing and scheduling
- Tools are dynamically bound to LLM via `llm.bind_tools()`

### Trend Following System Architecture
DCPersona includes an intelligent trend following system that operates independently of the main agent:
- `discord_bot/trend_following.py`: Comprehensive trend following handler with three modes
- `schemas/config_types.py`: Type-safe configuration with `TrendFollowingConfig` dataclass
- Channel-level controls with asyncio locks for concurrency safety
- Bot loop prevention mechanisms to avoid infinite trend cycles
- Integration with existing emoji registry for intelligent emoji responses
- **Probabilistic trend following**: Configurable probability-based decisions for natural interactions

#### Probabilistic Trend Following
The system supports probabilistic decision-making to create more natural interactions:

**Decision Formula**:
```
final_probability = min(max_probability, base_probability + excess_count * boost_factor)
where excess_count = max(0, current_count - threshold)
```

**Configuration Parameters**:
- `enable_probabilistic`: Enable/disable probabilistic mode (default: true)
- `base_probability`: Base probability when threshold is reached (default: 0.5)
- `probability_boost_factor`: Probability increase per excess count (default: 0.15)
- `max_probability`: Maximum probability cap (default: 0.95)

**Example Probability Progression** (with default settings, threshold=3):
```
Count | Excess | Probability | Behavior
  3   |   0    |    50%     | 1 in 2 chance to follow
  4   |   1    |    65%     | Higher chance as activity increases
  5   |   2    |    80%     | Very likely in active discussions
  6+  |   3+   |    95%     | Almost certain but retains randomness
```

**Benefits**:
- **Natural Interaction**: Avoids predictable mechanical responses
- **Activity-Responsive**: Higher probability during active discussions
- **Configurable**: Adaptable to different server cultures
- **Backward Compatible**: Can revert to hard thresholds by disabling

## Key Implementation Patterns

### Unified Agent Design
`UnifiedAgent` class in `agent_core/graph.py` centralizes:
- Multiple LLM instances for different purposes (tool analysis, final answer)
- Tool registration and binding
- Progress observation management
- State graph construction

### LLM Instance Management
The Discord Bot uses a simplified LLM classification system:
- `smart_llm`: High-quality model (based on `final_answer` config) for complex reasoning tasks
- `fast_llm`: Fast model (based on `tool_analysis` config) for quick decision-making
- `wordle_llm`: Alias for `smart_llm` to maintain backward compatibility
- Trend following uses `fast_llm` for optimal response time

### Emoji System Architecture
DCPersona includes an intelligent emoji assistance system that enhances message expressiveness:
- `output_media/emoji_types.py`: Type-safe emoji configuration with `EmojiConfig` dataclass
- `output_media/emoji_registry.py`: Unified emoji processing with async validation and sync formatting
- `emoji_config.yaml`: Configuration-driven emoji management for guild-specific and application emojis
- `output_media/context_builder.py`: Builds emoji context for LLM prompts
- Integration with Discord bot for context-aware emoji suggestions and automatic formatting

### Discord Integration Flow
1. `discord_bot/message_handler.py` processes Discord events
2. **Trend Following Processing**: Priority handling of trend following features (if enabled)
3. `discord_bot/message_collector.py` gathers conversation history and multimodal content
4. Creates `UnifiedAgent` with `DiscordProgressAdapter` and `EmojiHandler`
5. Executes LangGraph with real-time progress updates and emoji context injection
6. `discord_bot/progress_manager.py` handles all Discord message operations
7. `output_media/emoji_registry.py` provides intelligent emoji suggestions and formatting

### Multimodal Content Processing
- `utils/image_processor.py` handles emoji, stickers, and animations
- Images converted to Base64 for LLM consumption
- Content deduplication and timestamp sorting
- Media statistics appended to messages with `[包含: ...]` markers

### Configuration Access Pattern
```python
# Type-safe access (preferred)
max_rounds = config.agent.behavior.max_tool_rounds
enable_streaming = config.streaming.enabled

# Tool checking
if config.is_tool_enabled("google_search"):
    # Initialize tool
```

### Emoji System Usage Pattern
```python
# Emoji registry initialization (in bot startup)
emoji_registry = EmojiRegistry("emoji_config.yaml")
await emoji_registry.load_emojis(discord_client)

# Generate LLM prompt context
guild_id = message.guild.id if message.guild else None
emoji_context = emoji_registry.build_prompt_context(guild_id)

# LLM directly generates Discord emoji format
# The LLM response will contain: "Check this out <:emoji_name:123456789>!"
# No additional formatting needed
```

### Progress Notification Pattern
```python
# In agent nodes
await self._notify_progress(
    stage="tool_execution",
    message="🔧 正在平行執行工具...",
    progress_percentage=50
)

# Streaming support
async for chunk in llm.astream(messages):
    await self._notify_streaming_chunk(chunk.content)
```

### Trend Following Usage Pattern
```python
# Trend following handler initialization (in bot startup)
trend_following_handler = TrendFollowingHandler(
    config=config.trend_following,
    llm=fast_llm,  # Use fast_llm for optimal response time
    emoji_registry=emoji_handler
)

# Event handling in Discord client
async def on_message(message):
    # Priority: Handle trend following first
    await trend_following_handler.handle_message_following(message, bot)
    # Then proceed with normal message processing...

async def on_raw_reaction_add(payload):
    # Handle reaction following
    await trend_following_handler.handle_raw_reaction_following(payload, bot)
```

## Important Implementation Details

### Tool Execution Strategy
- Tools execute in parallel using `asyncio.gather()`
- YouTube URL detection happens programmatically before LLM tool calls
- Tool results use `ToolExecutionResult` for standardized success/failure handling
- Progress tracking at individual tool level with status updates

### Message Processing Pipeline
1. Permission and channel validation
2. **Trend Following Processing**: Priority handling of reaction/content/emoji following
3. Multimodal content collection with deduplication
4. Agent state initialization
5. LangGraph execution with progress observers
6. Response formatting and delivery
7. Reminder scheduling integration

### Trend Following Implementation Details
- **Three Following Modes**: Reaction, content (text/sticker), and emoji following
- **Concurrency Control**: Channel-specific asyncio locks prevent duplicate responses
- **Bot Loop Prevention**: Automatic detection of bot participation in trend segments
- **Priority System**: Content following has higher priority than emoji following
- **Intelligent Responses**: LLM-powered emoji responses using existing emoji registry
- **Configuration-Driven**: Flexible thresholds, cooldowns, and channel restrictions

### Streaming Implementation
- Configurable via `config.streaming.enabled` and `min_content_length`
- Smart fallback to synchronous mode on errors
- Progress adapter handles both streaming and non-streaming modes
- Content length-based streaming decision

### Event Scheduling System
- `event_scheduler/scheduler.py` uses APScheduler
- Integrates with `set_reminder` tool via `ReminderDetails`
- Persistent storage in `data/events.json`
- Automatic cleanup of expired events

## Testing Strategy

The test suite covers:
- Unit tests for individual modules
- Integration tests for agent workflows
- Configuration validation tests
- Streaming and progress system tests
- Discord bot functionality tests
- Tool integration tests including YouTube and Wordle
- **Trend following system comprehensive testing**

Key test files:
- `test_agent_core_langchain_integration.py`: Core agent functionality
- `test_streaming.py`: Streaming response system
- `test_progress_manager_concurrency.py`: Progress management
- `test_actual_discord_usage.py`: Discord integration
- `test_emoji_system.py`: Emoji system functionality with 21 comprehensive tests
- `test_trend_following.py`: **Comprehensive trend following tests with 37 test cases covering all functionality**

## Configuration Management

### Environment Variables
- `GEMINI_API_KEY`: Required for LLM functionality
- Discord bot token set in `config.yaml`

### Configuration Structure
- `system`: Timezone, debug, logging configuration
- `discord`: Bot settings, permissions, limits, emoji/sticker processing
- `llm.models`: Multiple model configurations for different purposes
- `agent`: Tool enablement, behavior, thresholds
- `progress`: Platform-specific progress update settings
- `streaming`: Streaming response configuration
- `trend_following`: **Comprehensive trend following configuration with channel controls, thresholds, and cooldowns**

### Tool Configuration
Tools can be enabled/disabled and prioritized:
```yaml
agent:
  tools:
    google_search:
      enabled: true
      priority: 1
```

Special cases:
- `reminder` tool controlled by `reminder.enabled`
- `youtube_summary` enabled by default if not explicitly configured

### Trend Following Configuration
```yaml
trend_following:
  enabled: true
  allowed_channels: []  # Empty = all channels allowed
  cooldown_seconds: 60
  message_history_limit: 10
  reaction_threshold: 3
  content_threshold: 2
  emoji_threshold: 3
  
  # Probabilistic trend following
  enable_probabilistic: true     # Enable probability-based decisions
  base_probability: 0.5          # Base chance when threshold is met (50%)
  probability_boost_factor: 0.15 # Probability increase per excess count
  max_probability: 0.95          # Maximum probability cap (95%)
```

## Discord Bot Features

### Slash Commands
- Auto-discovery system in `discord_bot/commands/`
- Commands registered via `register_commands(bot)`
- `/wordle_hint`: Daily puzzle hints with creative AI-generated clues

### Message Handling
- Conversation history with configurable limits
- Multimodal support (text, images, emoji, stickers)
- Permission system with user/role/channel filtering
- Maintenance mode support
- **Intelligent Trend Following**: Automatic detection and participation in reaction, content, and emoji trends

### Progress Updates
- Real-time embed-based progress indicators
- Intelligent update intervals to avoid rate limits
- Error handling with graceful degradation
- Cleanup of old progress messages

This architecture enables a highly modular, type-safe, and extensible Discord AI assistant with clear separation of concerns and platform independence.

## Key File Locations and Architecture References

### Core Architecture Files
- `agent_core/graph.py`: LangGraph 核心實現，包含 `UnifiedAgent` 及其各階段節點
- `schemas/config_types.py`: 型別安全配置定義
- `schemas/agent_types.py`: Agent 核心型別定義（狀態、計劃等）
- `discord_bot/client.py`: Discord Client 初始化與 Slash Commands 註冊
- `discord_bot/message_handler.py`: Discord 訊息事件處理主流程

### Tool System
- `tools/__init__.py`: 工具模組匯出
- `tools/google_search.py`: Google 搜尋工具
- `tools/set_reminder.py`: 設定提醒工具
- `tools/youtube_summary.py`: YouTube 摘要工具
- `utils/youtube_utils.py`: YouTube URL 解析輔助函式

### Output Media System  
- `output_media/emoji_registry.py`: Emoji 註冊器和管理
- `output_media/emoji_types.py`: Emoji 系統型別定義
- `output_media/context_builder.py`: 媒體提示上下文建構
- `output_media/sticker_registry.py`: Sticker 註冊（預留）

### Progress Management
- `agent_core/progress_mixin.py`: 進度更新混入
- `agent_core/progress_observer.py`: 進度觀察者介面
- `agent_core/progress_types.py`: 進度型別定義
- `discord_bot/progress_adapter.py`: Discord 進度適配器
- `discord_bot/progress_manager.py`: Discord 訊息進度管理

### Testing
- `tests/test_emoji_system.py`: Emoji 系統完整測試（21 項測試）
- `tests/test_agent_core_langchain_integration.py`: Agent 核心功能測試
- `tests/test_streaming.py`: 串流回應系統測試
- `tests/test_progress_manager_concurrency.py`: 進度管理測試
- `tests/test_wordle_integration.py`: Wordle 整合測試
- `tests/test_trend_following.py`: **跟風功能完整測試（37 項測試，涵蓋所有核心功能和邊界情況）**

### Configuration Files
- `config-example.yaml`: 主配置範例檔
- `emoji_config-example.yaml`: Emoji 配置範例檔
- `env.example`: 環境變數範例檔

## DCPersona Development Guidelines

### 開發原則
- 禁止千萬絕對一律不要搞向後相容 這是讓 code 髒亂的第一步\
- 採用型別安全的配置系統，避免字串 key 存取 (hasattr, getattr, setattr 都是禁用 function)
- 使用 LangChain 工具系統 (`@tool` decorator) 實現工具整合  
- 遵循觀察者模式進行進度管理
- 支援多模態輸入處理（文字、圖片、emoji、sticker、動畫）
- 實現統一 Agent 架構，支援 Discord 和 CLI 雙模式

### 參考文檔架構
- `README.md`: 對外功能簡介和安裝指南，完整的專案架構說明
- `project_rules.md`: 開發概覽用的專案架構和職責，主要工作流程
- `project_structure.md`: 開發用詳細實現說明，模組細項作法職責

### 開發流程
1. 任務開始前，先向 user 確認 task list 和架構
2. 實作完成後向 user 確認結果
3. 編寫對應的測試案例
4. 執行 `python -m pytest tests/ -v` 確保所有測試通過
5. 修復任何測試錯誤和回歸問題

### 工具查詢
- 若需要查詢不熟悉的 library 使用方式，使用 `context7` tool 查詢最新文檔

## Recent Major Updates

### 跟風功能系統 (Trend Following System)
**實施日期**: 最近完成

**核心功能**:
- **Reaction 跟風**: 當 reaction 達到設定閾值時自動添加相同 reaction
- **內容跟風**: 檢測連續相同內容（文字或 sticker）並自動複製
- **Emoji 跟風**: 識別連續 emoji 訊息並使用 LLM 生成適合的 emoji 回應

**技術特色**:
- 頻道級別的併發控制使用 asyncio.Lock 防止重複回應
- Bot 循環防護機制避免無限跟風
- 配置驅動的行為控制，支援頻道白名單和冷卻時間
- 與現有 emoji 註冊系統整合，提供智能 emoji 回應
- **延遲發送系統**: 隨機延遲 (0.5-3秒) 提升回應自然性
- **重複防護機制**: 原子性操作防止延遲期間的重複發送
- **分離處理架構**: Reaction 和 Message 活動獨立處理，可並行執行
- 完整的單元測試覆蓋，包含 50+ 項測試案例

**檔案位置**:
- `discord_bot/trend_following.py`: 核心處理器實現
- `schemas/config_types.py`: 新增 `TrendFollowingConfig` 配置類型
- `tests/test_trend_following.py`: 完整測試套件
- `config-example.yaml`: 配置範例更新