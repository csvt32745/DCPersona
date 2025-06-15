#!/usr/bin/env python3
"""
簡易 CLI 測試介面

用於測試統一 Agent 的功能，包括純對話模式和工具輔助模式。
"""

import asyncio
import sys
import logging
import os
import base64
from typing import Dict, Any, Optional, List, Union
from dataclasses import asdict
from datetime import datetime
import uuid

# 設置基本日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from agent_core.graph import create_unified_agent
from schemas.agent_types import OverallState, MsgNode, ReminderDetails
from utils.config_loader import load_typed_config
from utils.logger import setup_logger
from schemas.config_types import AppConfig, ConfigurationError, DiscordContextData
from event_scheduler.scheduler import EventScheduler
from prompt_system.prompts import get_prompt_system

from langchain.globals import set_verbose, set_debug

set_verbose(True)  # 較簡潔的詳細資訊
set_debug(True)    # 更詳細的除錯資訊


def _load_image_as_base64(image_path: str) -> Optional[Dict[str, Any]]:
    """
    載入圖片檔案並轉換為 LangChain 格式的 Base64 編碼字典。
    支援 JPEG 和 PNG 格式。
    
    Args:
        image_path: 圖片檔案路徑。
        
    Returns:
        Optional[Dict[str, Any]]: LangChain 期望的圖片字典格式，或 None 如果載入失敗。
    """
    if not os.path.exists(image_path):
        logging.error(f"圖片檔案不存在: {image_path}")
        return None
    
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        
        # 判斷 MIME 類型
        # 簡單判斷，實際應用可能需要更 robust 的方法
        if image_path.lower().endswith(('.png')):
            mime_type = "image/png"
        elif image_path.lower().endswith(('.jpg', '.jpeg')):
            mime_type = "image/jpeg"
        else:
            logging.warning(f"不支援的圖片格式，僅支援 .png 和 .jpg/.jpeg: {image_path}")
            return None
            
        base64_string = base64.b64encode(image_bytes).decode("utf-8")
        
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{base64_string}"}
        }
    except Exception as e:
        logging.error(f"載入或編碼圖片失敗 {image_path}: {e}")
        return None


class CLIInterface:
    """命令行介面"""
    
    def __init__(self, config: Optional[AppConfig] = None):
        """初始化 CLI 介面
        
        Args:
            config: 型別安全的配置實例
        """
        self.config = config or load_typed_config()
        setup_logger(self.config)
        self.logger = logging.getLogger(__name__)
        
        self.event_scheduler = EventScheduler()
        self.event_scheduler.register_callback(
            event_type="reminder",
            callback=self._on_cli_reminder_triggered
        )
        self.logger.info("CLI EventScheduler 已初始化並註冊回調函數。")

        self.cli_reminder_triggers: Dict[str, Dict[str, Any]] = {}
        self.prompt_system = get_prompt_system()
        self.agent = create_unified_agent(self.config)
        
        # 設置日誌
    
    def show_config_info(self):
        """顯示配置資訊"""
        print("=" * 50)
        print("🔧 DCPersona 配置資訊")
        print("=" * 50)
        
        # 使用型別安全的配置存取
        agent_config = self.config.agent
        tools_config = self.config.agent.tools
        behavior_config = self.config.agent.behavior
        
        print(f"  最大工具輪次: {behavior_config.max_tool_rounds}")
        print(f"  啟用反思: {behavior_config.enable_reflection}")
        print(f"  啟用進度: {behavior_config.enable_progress}")
        
        print("\n🔧 工具狀態:")
        for tool_name, tool_config in tools_config.items():
            enabled = tool_config.enabled
            priority = tool_config.priority
            status = "✅ 啟用" if enabled else "❌ 停用"
            print(f"  {tool_name}: {status} (優先級: {priority})")
        
        has_api_key = bool(self.config.gemini_api_key)
        print(f"\n🔑 API 金鑰: {'✅ 已設置' if has_api_key else '❌ 未設置'}")
        print("=" * 50)
    
    def show_interactive_menu(self):
        """顯示互動選單"""
        print("\n📋 選擇操作:")
        print("1. 開始對話")
        print("2. 調整工具輪次")
        print("3. 顯示配置")
        print("4. 退出")
        
        while True:
            try:
                choice = input("\n請輸入選項 (1-4): ").strip()
                if choice in ['1', '2', '3', '4']:
                    return int(choice)
                else:
                    print("❌ 無效選項，請輸入 1-4")
            except (EOFError, KeyboardInterrupt):
                return 4
    
    def adjust_tool_rounds(self):
        """調整工具輪次設定"""
        current_max_rounds = self.config.agent.behavior.max_tool_rounds
        print(f"\n當前最大工具輪次: {current_max_rounds}")
        print("輸入新的最大工具輪次 (0 = 純對話模式):")
        
        try:
            new_rounds = int(input("新輪次: ").strip())
            if new_rounds >= 0:
                # 更新配置（注意：這只是臨時更新，不會保存到文件）
                self.config.agent.behavior.max_tool_rounds = new_rounds
                print(f"✅ 已更新最大工具輪次為: {new_rounds}")
                if new_rounds == 0:
                    print("💬 現在處於純對話模式")
                else:
                    print(f"🔧 現在最多使用 {new_rounds} 輪工具")
            else:
                print("❌ 輪次數必須大於等於 0")
        except ValueError:
            print("❌ 請輸入有效的數字")
        except (EOFError, KeyboardInterrupt):
            print("\n操作已取消")
    
    async def _on_cli_reminder_triggered(self, event_type: str, event_details: Dict[str, Any], event_id: str):
        """
        當排程器觸發提醒事件時的回調函數。
        直接對 Agent 調用，並在 system prompt 中加入提醒內容。
        """
        self.logger.info(f"接收到 CLI 提醒觸發事件: {event_id}, 類型: {event_type}")
        try:
            reminder_details = ReminderDetails(**event_details)
            
            # 儲存提醒觸發資訊到字典中
            # 使用 event_id 作為 msg_id 的替代，確保唯一性
            self.cli_reminder_triggers[event_id] = {
                'is_trigger': True,
                'content': reminder_details.message
            }
            
            self.logger.info(f"準備觸發 CLI 提醒處理: {reminder_details.message}")
            
            # 模擬一個 MsgNode
            messages = [MsgNode(role="user", content=reminder_details.message)]
            
            # 準備初始狀態
            initial_state = self._prepare_cli_agent_state(
                messages=messages,
                is_reminder_trigger=True,
                reminder_content=reminder_details.message,
                original_msg_id=event_id # 傳遞 event_id 作為 original_msg_id
            )
            
            print(f"\n🔔 提醒時間到！內容: {reminder_details.message}")
            print("🤖 正在思考提醒回覆...")
            
            # 執行 Agent
            graph = self.agent.build_graph()
            result = await graph.ainvoke(initial_state)
            
            # 顯示結果
            final_answer = result.get("final_answer", "抱歉，無法生成提醒回應。")
            print(f"\n🤖 助手 (提醒回覆): {final_answer}")
            
            # 清理提醒觸發資訊
            if event_id in self.cli_reminder_triggers:
                self.event_scheduler.cancel_event(event_id)
                del self.cli_reminder_triggers[event_id]
                
        except Exception as e:
            self.logger.error(f"處理 CLI 提醒觸發事件失敗: {event_id}, 錯誤: {e}", exc_info=True)
            
    def _prepare_cli_agent_state(self, messages: List[MsgNode], is_reminder_trigger: bool = False, reminder_content: str = "", original_msg_id: Optional[str] = None) -> OverallState:
        """
        準備 Agent 初始狀態，加入 CLI 環境的 metadata (模擬 Discord metadata)。
        
        Args:
            messages: 收集到的訊息資料 (MsgNode 列表)。
            is_reminder_trigger: 是否為提醒觸發情況。
            reminder_content: 提醒內容。
            original_msg_id: 原始訊息 ID 或提醒的 event ID。
            
        Returns:
            OverallState: Agent 初始狀態。
        """
        try:
            # 模擬 Discord context data for CLI
            discord_context = DiscordContextData(
                bot_id="cli_bot_id",
                bot_name="CLI_Bot",
                channel_id="cli_channel", # 模擬頻道 ID
                channel_name="cli_console",
                guild_name=None, # CLI 無伺服器
                user_id="cli_user_id", # 模擬用戶 ID
                user_name="CLI_User",
                mentions=[]
            )
            
            # 使用 PromptSystem 的 _build_discord_context 轉換為字串，傳遞提醒觸發標誌和內容
            # 確保 config 和 discord_context 是正確的類型
            discord_metadata = self.prompt_system._build_discord_context(self.config, discord_context, is_reminder_trigger, reminder_content)
            
            # 創建初始狀態，將 metadata 加入
            initial_state = OverallState(
                messages=messages,
                tool_round=0,
                finished=False,
                messages_global_metadata=discord_metadata
            )
            
            return initial_state
            
        except Exception as e:
            self.logger.warning(f"格式化 CLI metadata 失敗: {e}")
            return OverallState(
                messages=messages,
                tool_round=0,
                finished=False,
                messages_global_metadata=""
            )

    async def start_conversation(self):
        """開始對話模式"""
        print("\n💬 對話模式已啟動")
        print("輸入 'quit' 或 'exit' 退出對話")
        print("輸入 'config' 查看當前配置")
        print("輸入 '/image <圖片路徑> [文字訊息]' 來發送圖片和文字")
        print("-" * 50)
        
        # 創建 Agent
        agent = create_unified_agent(self.config)
        
        while True:
            try:
                user_input = input("\n👤 您: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', '退出']:
                    print("👋 對話結束")
                    break
                
                if user_input.lower() == 'config':
                    self.show_config_info()
                    continue
                
                # 處理圖片輸入
                content_for_msg_node: Union[str, List[Dict[str, Any]]] = user_input
                
                if user_input.lower().startswith("/image "):
                    parts = user_input.split(" ", 2) # /image <path> [text]
                    if len(parts) < 2:
                        print("❌ 錯誤: /image 命令需要圖片路徑。用法: /image <圖片路徑> [文字訊息]")
                        continue
                    
                    image_path = parts[1]
                    text_message = parts[2] if len(parts) > 2 else ""
                    
                    image_data = _load_image_as_base64(image_path)
                    
                    if image_data:
                        if text_message:
                            content_for_msg_node = [
                                {"type": "text", "text": text_message},
                                image_data
                            ]
                        else:
                            content_for_msg_node = [image_data]
                    else:
                        print(f"❌ 無法載入圖片或圖片格式不支援: {image_path}")
                        continue
                
                # 準備訊息
                messages = [MsgNode(role="user", content=content_for_msg_node)]
                
                # 創建初始狀態
                initial_state = self._prepare_cli_agent_state(messages=messages)
                
                print("🤖 正在思考...")
                
                # 執行 Agent
                graph = agent.build_graph()
                result = await graph.ainvoke(initial_state)
                
                # 處理提醒請求
                reminder_requests: List[ReminderDetails] = result.get("reminder_requests", [])
                if reminder_requests:
                    for reminder_detail in reminder_requests:
                        try:
                            # 為 CLI 環境模擬 channel_id, user_id, msg_id
                            reminder_detail.channel_id = "cli_channel"
                            reminder_detail.user_id = "cli_user_id"
                            reminder_detail.msg_id = str(uuid.uuid4()) # 生成唯一的 msg_id
                            
                            # 將 final answer 加入到提醒內容中
                            final_answer_for_reminder = result.get("final_answer", "")
                            if final_answer_for_reminder:
                                reminder_detail.message = f"{reminder_detail.message}\n\n之前的回覆：{final_answer_for_reminder}"
                            
                            # 解析目標時間
                            target_time = datetime.fromisoformat(reminder_detail.target_timestamp)
                            
                            await self.event_scheduler.schedule_event(
                                event_type="reminder",
                                event_details=asdict(reminder_detail), # 使用 model_dump 將 dataclass 轉為 dict
                                target_time=target_time,
                                event_id=reminder_detail.reminder_id
                            )
                            self.logger.info(f"已成功排程 CLI 提醒: {reminder_detail.message} 於 {target_time}")
                        except Exception as e:
                            self.logger.error(f"排程 CLI 提醒失敗: {reminder_detail.message}, 錯誤: {e}", exc_info=True)
                
                # 顯示結果
                final_answer = result.get("final_answer", "抱歉，無法生成回應。")
                print(f"\n🤖 助手: {final_answer}")
                
                # 顯示額外資訊
                if result.get("needs_tools"):
                    print(f"  🔧 使用了工具: {result.get('selected_tool', '無')}")
                if result.get("tool_results"):
                    print(f"  📊 工具結果數量: {len(result.get('tool_results', []))}")
                
            except (EOFError, KeyboardInterrupt):
                print("\n👋 對話結束")
                break
            except Exception as e:
                print(f"❌ 處理請求時發生錯誤: {e}")
                self.logger.error(f"對話處理錯誤: {e}", exc_info=True)
    
    async def run(self):
        """運行 CLI 介面"""
        try:
            print("🚀 歡迎使用 DCPersona CLI")
            self.show_config_info()
            
            while True:
                choice = self.show_interactive_menu()
                
                if choice == 1:
                    await self.start_conversation()
                elif choice == 2:
                    self.adjust_tool_rounds()
                elif choice == 3:
                    self.show_config_info()
                elif choice == 4:
                    print("👋 再見！")
                    break
                
        except Exception as e:
            print(f"❌ CLI 運行錯誤: {e}")
            self.logger.error(f"CLI 錯誤: {e}", exc_info=True)


async def main():
    """主程式入口"""
    try:
        # 載入配置
        config = load_typed_config()
        
        # 驗證必要配置
        if not config.gemini_api_key:
            print("❌ 未設置 GEMINI_API_KEY 環境變數，請檢查 .env 文件")
            sys.exit(1)
        
        # 創建並運行 CLI
        cli = CLIInterface(config)
        # 啟動排程器
        scheduler_task = asyncio.create_task(cli.event_scheduler.start())
        try:
            await cli.run()
        finally:
            scheduler_task.cancel()
            try:
                await scheduler_task # 等待排程器任務完成清理
            except asyncio.CancelledError:
                pass
            await cli.event_scheduler.shutdown() # 確保 EventScheduler 關閉
        
    except ConfigurationError as e:
        print(f"❌ 配置錯誤: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 用戶中斷，正在退出...")
    except Exception as e:
        print(f"❌ 程式異常: {e}")
        logging.error(f"主程式錯誤: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 