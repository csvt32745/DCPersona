# Media Input / Output 重構任務

> 本文件統整 **Input / Output 多媒體重構** 的目標、架構、流程與待辦。依章節順序閱讀即可快速掌握重構範圍與進度。

---
## 1. 目標
1. 拆分現有 Emoji / Sticker 邏輯，形成 **Input**（訊息解析）與 **Output**（Bot 回覆）兩條媒體管線。
2. Sticker 僅預留介面 (`OutputStickerRegistry`)，本輪不實作實際貼圖邏輯。
3. 強化型別安全與單一職責，並確保重構完成後測試全部通過。

---
## 2. 模組架構總覽
### 2.1 Input Pipeline
| 模組 | 說明 |
|------|------|
| `schemas/input_media_config.py` | `InputMediaConfig` (取代舊 `EmojiStickerConfig`) |
| `utils/input_emoji_cache.py` | 原 `emoji_cache.py`，僅供 Input 使用 |
| `utils/image_processor.py` | 下載、取樣、resize、Base64 (不變) |
| `discord_bot/message_collector.py` | 使用 `InputMediaConfig`＋`InputEmojiCache` 解析 Emoji / Sticker / 圖片 |

### 2.2 Output Pipeline
| 模組 | 說明 |
|------|------|
| `output_media/emoji_registry.py` | 由 `prompt_system/emoji_handler.py` 搬遷；僅文字格式化 |
| `output_media/sticker_registry.py` | 介面 + TODO，暫不實作 |
| `output_media/context_builder.py` | 整合 Emoji / Sticker 資訊產生 Prompt Context |
| `output_media/emoji_types.py` | 由 `schemas/emoji_types.py` 搬遷，描述可用 Emoji 配置 |

**Placeholder 規範**  
Emoji：`<:name:id>` / `<a:name:id>`  
Sticker：`<sticker:id>` *(暫定)*  
Bot 僅傳文字，Discord 端自行渲染。

---
## 3. 預計檔案結構（完成後）
```text
llmcord/
├── schemas/
│   ├── config_types.py          # AppConfig，引用 InputMediaConfig
│   └── input_media_config.py    # InputMediaConfig dataclass
│
├── utils/
│   ├── input_emoji_cache.py     # 原 emoji_cache.py
│   └── image_processor.py
│
├── output_media/
│   ├── __init__.py
│   ├── emoji_registry.py
│   ├── sticker_registry.py
│   ├── emoji_types.py
│   └── context_builder.py
│
├── discord_bot/
│   ├── client.py
│   ├── message_handler.py
│   └── message_collector.py
│
└── prompt_system/
    └── (emoji_handler.py)       # 移除
```

---
## 4. 任務執行流程（每個子任務）
1. **讀取 task.md** ➜ 確認任務
2. **實作 / 重構**
3. **測試** ➜ `python -m pytest`（全部）
4. **更新 task.md** ➜ 勾選進度或新增任務
5. **進入下一任務**

---
## 5. TODO 列表
### 5.1 核心重構
- [x] **Input**
  - [x] 1. 建立 `schemas/input_media_config.py`，將 `InputMediaConfig` 從 `config_types.py` 移出；更新 `DiscordConfig.input_media` 與 YAML
  - [x] 2. 重新命名 `utils/emoji_cache.py` ➜ `utils/input_emoji_cache.py`
  - [x] 3. 更新 `discord_bot/message_collector.py` 使用新 Config 與 Cache
- [x] **Output**
  - [x] 4. 搬遷 `prompt_system/emoji_handler.py` ➜ `output_media/emoji_registry.py`
  - [x] 5. 搬遷 `schemas/emoji_types.py` ➜ `output_media/emoji_types.py` 並更新 import
  - [x] 6. 建立 `output_media/sticker_registry.py` (介面 + TODO)
  - [x] 7. 建立 `output_media/context_builder.py` 整合 Prompt Context
  - [x] 8. 調整 `discord_bot/client.py`、`message_handler.py`、`progress_adapter.py` 之 import 與使用邏輯

### 5.2 測試與文檔
- [x] 9. 測試重構
  - [x] 9.1 `tests/test_emoji_system.py` 拆分為 `test_emoji_registry.py`、`test_input_emoji_cache.py`
  - [x] 9.2 更新所有 `EmojiStickerConfig` 參照
- [x] 10. 新增/更新測試：`test_input_media_config.py`, `test_context_builder.py`
- [ ] 11. 更新文件：`README.md`, `project_rules.md`, `project_structure.md`

### 5.3 收尾 & 檢查
- [x] 12. YAML 與 Loader：修改 `config-example.yaml`（新增 `discord.input_media:`；移除 `emoji_sticker:`）、更新 `utils/config_loader.py` key 轉換
- [x] 13. Cache 改名副作用：在 `utils/__init__.py` re-export `EmojiCache`
- [x] 14. Logging / CLI：更新 `cli_main.py` 等列印路徑
- [x] 15. 最終殘留檢查：`grep -R EmojiStickerConfig|emoji_handler|emoji_sticker`
- [x] 16. 確認 CI 綠燈

---
## 6. Git Workflow
- **分支**：`refactor/input-output-media`（已建立）  
- **Commit 樣式**：
  - `feat(input): add InputMediaConfig and yaml loader`
  - `refactor(output): migrate EmojiHandler to emoji_registry`
  - `test: update tests for input/output media refactor`

---
## 7. YAML 範例
`input_media_config.yaml`
```yaml
max_emoji_per_message: 3
max_sticker_per_message: 2
max_animated_frames: 4
emoji_sticker_max_size: 256
enable_emoji_processing: true
enable_sticker_processing: true
enable_animated_processing: true
```

---
## 8. 後續擴充（非本輪範圍）
- 完成 `OutputStickerRegistry` 貼圖驗證與下載
- OutputMedia 快取與 Bot 主動傳圖片能力
