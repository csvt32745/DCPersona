# Task 4: 整合 Streaming 到 Progress 系統

## 概述
將 Discord streaming 整合到 progress_mixin 中，實現統一的進度和串流管理，提升用戶體驗。

## 目標
- 將 streaming 功能整合到現有的 progress 系統中
- 實現即時串流回應，提升用戶體驗
- 統一管理進度通知和串流事件
- 支援可配置的串流參數

## 當前問題
- **非串流回應**: 用戶需要等待完整回應，體驗不佳
- **Progress 系統未支援串流**: 現有進度系統沒有串流功能
- **缺乏統一管理**: 進度和串流分離管理

## 子任務

### Task 4.1: 擴展 Progress 系統支援 Streaming
**狀態**: ⏳ 待開始

**目標**: 修改 `agent_core/progress_observer.py` 和 `progress_mixin.py` 添加串流事件支援

**需要修改的文件**:
- [ ] `agent_core/progress_observer.py`: 添加串流事件定義
- [ ] `agent_core/progress_mixin.py`: 實現串流通知邏輯

**新增串流事件類型**:
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
```

**擴展 ProgressMixin**:
```python
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

**驗收標準**:
- 串流事件類型定義完整
- ProgressMixin 支援串流通知
- 串流邏輯可配置（chunk_size, delay_ms）

### Task 4.2: 更新 Discord Progress Adapter 支援 Streaming
**狀態**: ⏳ 待開始

**目標**: 修改 `discord_bot/progress_adapter.py` 實現串流方法，根據配置控制更新頻率

**需要修改的文件**:
- [ ] `discord_bot/progress_adapter.py`: 實現串流處理邏輯

**實作要點**:
```python
# discord_bot/progress_adapter.py
import time
import asyncio
from typing import Optional

class DiscordProgressAdapter(ProgressObserver):
    def __init__(self, original_message: discord.Message, config: AppConfig):
        self.original_message = original_message
        self.config = config
        self.progress_manager = get_progress_manager()
        self._streaming_content = ""
        self._last_update = 0
        self._streaming_message: Optional[discord.Message] = None
        self._update_lock = asyncio.Lock()
    
    async def on_streaming_chunk(self, chunk: StreamingChunk) -> None:
        """處理串流塊"""
        async with self._update_lock:
            self._streaming_content += chunk.content
            
            current_time = time.time()
            update_interval = self.config.progress.discord.update_interval
            
            # 根據配置的更新間隔決定是否更新
            should_update = (
                (current_time - self._last_update >= update_interval) or 
                chunk.is_final or
                len(self._streaming_content) > 1500  # Discord 字符限制考量
            )
            
            if should_update:
                await self._update_streaming_message()
                self._last_update = current_time
    
    async def on_streaming_complete(self) -> None:
        """處理串流完成"""
        async with self._update_lock:
            if self._streaming_message:
                # 移除串流指示器，標記完成
                final_embed = discord.Embed(
                    description=self._streaming_content,
                    color=discord.Color.green()
                )
                final_embed.set_footer(text="✅ 回答完成")
                
                try:
                    await self._streaming_message.edit(embed=final_embed)
                except discord.HTTPException as e:
                    self.logger.warning(f"更新最終訊息失敗: {e}")
    
    async def _update_streaming_message(self):
        """更新串流訊息"""
        try:
            # 截斷過長的內容
            display_content = self._streaming_content
            if len(display_content) > 1800:
                display_content = display_content[:1800] + "..."
            
            embed = discord.Embed(
                description=display_content + " ⚪",  # 串流指示器
                color=discord.Color.orange()
            )
            embed.set_footer(text="🔄 正在回答...")
            
            if self._streaming_message:
                await self._streaming_message.edit(embed=embed)
            else:
                self._streaming_message = await self.original_message.reply(embed=embed)
                
        except discord.HTTPException as e:
            self.logger.error(f"更新串流訊息失敗: {e}")
        except Exception as e:
            self.logger.error(f"串流訊息處理失敗: {e}")
    
    async def on_progress_update(self, update: DiscordProgressUpdate) -> None:
        """處理一般進度更新（與串流並存）"""
        # 如果正在串流，則不顯示一般進度更新
        if self._streaming_message:
            return
        
        # 原有的進度更新邏輯
        await super().on_progress_update(update)
```

**驗收標準**:
- Discord 串流訊息正確顯示
- 更新頻率可配置
- 串流指示器正常工作
- 錯誤處理完善

### Task 4.3: 修改 Agent 支援 Streaming
**狀態**: ⏳ 待開始

**目標**: 修改 `agent_core/graph.py` 的 `finalize_answer` 節點支援串流，根據配置決定是否啟用

**需要修改的文件**:
- [ ] `agent_core/graph.py`: 修改 `finalize_answer` 節點
- [ ] `schemas/config_types.py`: 添加串流配置類型

**添加串流配置**:
```python
# schemas/config_types.py
@dataclass
class StreamingConfig:
    """串流配置"""
    enabled: bool = True
    chunk_size: int = 50  # 字符數
    delay_ms: int = 50    # 毫秒延遲
    min_content_length: int = 100  # 最小內容長度才啟用串流
```

**修改 finalize_answer 節點**:
```python
# agent_core/graph.py
async def finalize_answer(self, state: OverallState) -> Dict[str, Any]:
    """
    LangGraph 節點：生成最終答案（支援串流）
    """
    try:
        self.logger.info("finalize_answer: 生成最終答案")
        
        # 通知答案生成階段
        await self._notify_progress(
            stage="finalize_answer",
            message="✍️ 正在整理答案...",
            progress_percentage=90
        )
        
        messages = state.messages
        tool_results = state.aggregated_tool_results or state.tool_results or []
        
        # 構建上下文
        context = ""
        if tool_results:
            context = "\n".join([f"搜尋結果: {result}" for result in tool_results])
        
        # 生成最終答案
        try:
            final_answer = self._generate_final_answer(messages, context)
        except Exception as e:
            self.logger.warning(f"LLM 答案生成失敗，使用基本回覆: {e}")
            final_answer = self._generate_basic_fallback_answer(messages, context)
        
        # 根據配置決定是否串流
        streaming_config = self.config.streaming
        should_stream = (
            streaming_config.enabled and 
            self._progress_observers and
            len(final_answer) >= streaming_config.min_content_length
        )
        
        if should_stream:
            self.logger.info("finalize_answer: 啟用串流回應")
            # 串流回應
            await self.stream_response(
                final_answer,
                chunk_size=streaming_config.chunk_size,
                delay_ms=streaming_config.delay_ms
            )
        else:
            self.logger.info("finalize_answer: 使用一般回應")
            # 一般回應（通過進度系統）
            await self._notify_progress(
                stage="completed",
                message="✅ 回答完成！",
                progress_percentage=100,
                final_answer=final_answer
            )
        
        return {
            "final_answer": final_answer,
            "finished": True,
            "sources": self._extract_sources_from_results(tool_results)
        }
        
    except Exception as e:
        self.logger.error(f"finalize_answer 失敗: {e}")
        await self._notify_error(e)
        return {
            "final_answer": "抱歉，生成答案時發生錯誤。",
            "finished": True
        }
```

**驗收標準**:
- 串流功能可配置啟用/禁用
- 根據內容長度智能決定是否串流
- 串流和一般回應模式都正常工作

### Task 4.4: 實現智能串流策略
**狀態**: ⏳ 待開始

**目標**: 實現更智能的串流策略，包括內容分析和自適應調整

**實作要點**:
```python
# agent_core/progress_mixin.py
class ProgressMixin:
    async def smart_stream_response(self, content: str) -> None:
        """智能串流回應"""
        streaming_config = self.config.streaming
        
        # 分析內容特性
        content_analysis = self._analyze_content_for_streaming(content)
        
        # 根據內容調整串流參數
        chunk_size = self._calculate_optimal_chunk_size(content_analysis)
        delay_ms = self._calculate_optimal_delay(content_analysis)
        
        # 執行串流
        await self.stream_response(content, chunk_size, delay_ms)
    
    def _analyze_content_for_streaming(self, content: str) -> Dict[str, Any]:
        """分析內容特性"""
        return {
            "length": len(content),
            "word_count": len(content.split()),
            "has_code": "```" in content,
            "has_lists": any(line.strip().startswith(('-', '*', '1.')) for line in content.split('\n')),
            "complexity_score": self._calculate_complexity_score(content)
        }
    
    def _calculate_optimal_chunk_size(self, analysis: Dict[str, Any]) -> int:
        """計算最佳塊大小"""
        base_size = self.config.streaming.chunk_size
        
        # 根據內容特性調整
        if analysis["has_code"]:
            return base_size * 2  # 代碼塊較大
        elif analysis["has_lists"]:
            return base_size * 1.5  # 列表項目較大
        else:
            return base_size
    
    def _calculate_optimal_delay(self, analysis: Dict[str, Any]) -> int:
        """計算最佳延遲"""
        base_delay = self.config.streaming.delay_ms
        
        # 根據複雜度調整延遲
        complexity = analysis["complexity_score"]
        if complexity > 0.8:
            return base_delay * 1.5  # 複雜內容延遲較長
        elif complexity < 0.3:
            return base_delay * 0.7  # 簡單內容延遲較短
        else:
            return base_delay
```

**驗收標準**:
- 智能內容分析正常工作
- 串流參數自適應調整
- 不同類型內容的串流體驗優化

## 測試驗證

### 自動化測試
```bash
# 測試串流功能
python -c "from agent_core.progress_mixin import ProgressMixin; print('✓ Streaming mixin works')"

# 測試 Discord 適配器
python -c "from discord_bot.progress_adapter import DiscordProgressAdapter; print('✓ Discord streaming works')"

# 測試完整串流流程
python -m pytest tests/test_streaming.py -v
```

### 功能測試
- [ ] 串流回應正常顯示
- [ ] 更新頻率符合配置
- [ ] 串流完成正確標記
- [ ] 錯誤情況處理正確

### 性能測試
- [ ] 串流延遲符合預期
- [ ] Discord API 調用頻率合理
- [ ] 記憶體使用穩定

## 依賴關係
- **前置條件**: Task 1 (型別安全配置系統) 完成
- **建議前置**: Task 3 (Persona 系統整合) 完成，以便整合 system prompt
- **後續任務**: Task 5 (整合測試與優化)

## 預估時間
**1-2 週** (7-10 個工作日)

## 風險與注意事項
1. **Discord API 限制**: 需要注意 Discord 的訊息更新頻率限制
2. **網路延遲**: 串流體驗可能受網路狀況影響
3. **錯誤處理**: 串流過程中的錯誤需要優雅處理
4. **記憶體管理**: 長時間串流需要注意記憶體使用

## 預期改進效果
1. **用戶體驗提升**: 即時回應，減少等待時間
2. **互動性增強**: 用戶可以即時看到回應生成過程
3. **系統感知**: 更好的系統回應感知
4. **可配置性**: 靈活的串流參數配置

## 成功標準
- [ ] 串流功能正常工作
- [ ] Discord 整合無問題
- [ ] 串流延遲 < 100ms
- [ ] 配置系統完整
- [ ] 錯誤處理完善
- [ ] 性能影響最小化 