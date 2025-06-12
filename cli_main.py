#!/usr/bin/env python3
"""
簡易 CLI 測試介面

用於測試統一 Agent 的功能，包括純對話模式和工具輔助模式。
"""

import asyncio
import sys
import logging
from typing import Dict, Any

# 設置基本日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from agent_core.graph import create_unified_agent
from schemas.agent_types import OverallState, MsgNode
from utils.config_loader import load_config


class AgentCLI:
    """Agent CLI 測試介面"""
    
    def __init__(self):
        self.config = load_config()
        self.agent = None
        self.current_state = None
        
    def display_welcome(self):
        """顯示歡迎訊息"""
        print("="*60)
        print("🤖 統一 Agent CLI 測試介面")
        print("="*60)
        print("可用指令：")
        print("  /help    - 顯示幫助")
        print("  /config  - 顯示當前配置")
        print("  /mode    - 切換模式 (chat/tool)")
        print("  /reset   - 重置對話")
        print("  /quit    - 退出")
        print("  直接輸入訊息開始對話")
        print("-"*60)
    
    def display_config(self):
        """顯示當前配置"""
        agent_config = self.config.get("agent", {})
        tools_config = agent_config.get("tools", {})
        behavior_config = agent_config.get("behavior", {})
        
        print("\n📋 當前配置：")
        print(f"  最大工具輪次: {behavior_config.get('max_tool_rounds', 0)}")
        print(f"  啟用反思: {behavior_config.get('enable_reflection', True)}")
        
        print("  可用工具:")
        for tool_name, tool_config in tools_config.items():
            enabled = tool_config.get("enabled", False)
            priority = tool_config.get("priority", "無")
            print(f"    - {tool_name}: {'✅' if enabled else '❌'} (優先級: {priority})")
        
        has_api_key = bool(self.config.get("gemini_api_key"))
        print(f"  Gemini API: {'✅' if has_api_key else '❌'}")
        print()
    
    def toggle_mode(self):
        """切換模式"""
        current_max_rounds = self.config.get("agent", {}).get("behavior", {}).get("max_tool_rounds", 0)
        
        if current_max_rounds == 0:
            # 當前是純對話模式，切換到工具模式
            new_max_rounds = 2
            mode_name = "工具輔助模式"
        else:
            # 當前是工具模式，切換到純對話模式
            new_max_rounds = 0
            mode_name = "純對話模式"
        
        # 更新配置
        if "agent" not in self.config:
            self.config["agent"] = {}
        if "behavior" not in self.config["agent"]:
            self.config["agent"]["behavior"] = {}
        
        self.config["agent"]["behavior"]["max_tool_rounds"] = new_max_rounds
        
        # 重新建立 agent
        self.agent = create_unified_agent(self.config)
        
        print(f"✅ 已切換到 {mode_name} (max_tool_rounds: {new_max_rounds})")
        print()
    
    def reset_conversation(self):
        """重置對話"""
        self.current_state = OverallState()
        print("✅ 對話已重置")
        print()
    
    def process_user_input(self, user_input: str) -> str:
        """處理用戶輸入並獲取 Agent 回應"""
        if not self.agent:
            self.agent = create_unified_agent(self.config)
        
        if not self.current_state:
            self.current_state = OverallState()
        
        # 添加用戶訊息
        user_message = MsgNode(role="user", content=user_input)
        self.current_state.messages.append(user_message)
        
        try:
            # 執行 Agent 圖
            graph = self.agent.build_graph()
            
            # 運行圖並獲取結果
            result = graph.invoke(self.current_state)
            
            # 提取最終答案
            final_answer = result.get("final_answer", "抱歉，無法生成回應。")
            
            # 顯示一些除錯資訊（如果啟用）
            if result.get("needs_tools"):
                print(f"  🔧 使用了工具: {result.get('selected_tool', '無')}")
                if result.get("tool_results"):
                    print(f"  📊 工具結果數量: {len(result.get('tool_results', []))}")
            
            # 添加 Assistant 回應到對話歷史
            assistant_message = MsgNode(role="assistant", content=final_answer)
            self.current_state.messages.append(assistant_message)
            
            return final_answer
            
        except Exception as e:
            error_msg = f"處理請求時發生錯誤: {str(e)}"
            logging.error(error_msg, exc_info=True)
            return error_msg
    
    def run(self):
        """運行 CLI 介面"""
        self.display_welcome()
        self.display_config()
        
        while True:
            try:
                user_input = input("👤 您: ").strip()
                
                if not user_input:
                    continue
                
                # 處理指令
                if user_input == "/help":
                    self.display_welcome()
                    continue
                elif user_input == "/config":
                    self.display_config()
                    continue
                elif user_input == "/mode":
                    self.toggle_mode()
                    continue
                elif user_input == "/reset":
                    self.reset_conversation()
                    continue
                elif user_input in ["/quit", "/exit", "quit", "exit"]:
                    print("👋 再見！")
                    break
                
                # 處理一般對話
                print("🤖 思考中...", end="", flush=True)
                
                response = self.process_user_input(user_input)
                
                # 清除 "思考中..." 並顯示回應
                print(f"\r🤖 Agent: {response}")
                print()
                
            except KeyboardInterrupt:
                print("\n👋 再見！")
                break
            except Exception as e:
                print(f"\n❌ 發生錯誤: {e}")
                logging.error("CLI 運行時錯誤", exc_info=True)


def main():
    """主函數"""
    cli = AgentCLI()
    cli.run()


if __name__ == "__main__":
    main() 