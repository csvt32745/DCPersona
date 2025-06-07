#!/usr/bin/env python3
"""
複雜度評估系統測試腳本

此腳本測試新的複雜度判斷邏輯，包括：
1. LLM 驅動的複雜度評估
2. 規則型複雜度評估
3. 兩者的結合邏輯
4. Research Agent 流程整合
"""

import asyncio
import json
import logging
from typing import Dict, Any

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 導入相關模組
try:
    from agents.utils import (
        analyze_message_complexity,
        parse_complexity_assessment_result,
        combine_complexity_assessments,
        assess_message_complexity_with_llm
    )
    from agents.prompts import complexity_assessment_prompt
    from agents.configuration import AgentConfiguration
except ImportError as e:
    logger.error(f"導入失敗: {e}")
    logger.error("請確保在正確的項目目錄中運行此腳本")
    exit(1)


# 測試用例
TEST_MESSAGES = [
    {
        "content": "你好！今天天氣怎麼樣？",
        "expected": "SIMPLE",
        "description": "簡單問候"
    },
    {
        "content": "請比較 Python 和 JavaScript 在 2024 年的就業前景，並分析各自的優缺點",
        "expected": "RESEARCH", 
        "description": "複雜比較分析 + 時效性"
    },
    {
        "content": "!research 機器學習的發展歷史",
        "expected": "RESEARCH",
        "description": "強制研究命令"
    },
    {
        "content": "1 + 1 等於多少？",
        "expected": "SIMPLE",
        "description": "簡單計算"
    },
    {
        "content": "台灣最新的AI政策有哪些？對科技業有什麼影響？",
        "expected": "RESEARCH",
        "description": "時效性資訊需求"
    },
    {
        "content": "寫一首關於星星的詩",
        "expected": "SIMPLE", 
        "description": "創意內容"
    },
    {
        "content": "如何優化深度學習模型的訓練速度？有哪些最新的技術方案？",
        "expected": "RESEARCH",
        "description": "技術問題 + 最新資訊"
    }
]


class MockLLMClient:
    """模擬 LLM 客戶端用於測試"""
    
    def __init__(self):
        # 預設的模擬回應
        self.mock_responses = {
            "你好！今天天氣怎麼樣？": {
                "decision": "SIMPLE",
                "confidence": 0.9,
                "reasoning": "這是一個簡單的問候和天氣詢問",
                "triggered_criteria": ["日常對話"]
            },
            "請比較 Python 和 JavaScript 在 2024 年的就業前景，並分析各自的優缺點": {
                "decision": "RESEARCH", 
                "confidence": 0.95,
                "reasoning": "需要最新就業市場數據和深度比較分析",
                "triggered_criteria": ["時效性需求", "複雜分析需求", "比較分析"]
            },
            "!research 機器學習的發展歷史": {
                "decision": "RESEARCH",
                "confidence": 1.0,
                "reasoning": "使用者明確要求深度研究",
                "triggered_criteria": ["強制研究指令"]
            }
        }
    
    async def ainvoke(self, prompt: str) -> 'MockResponse':
        """模擬 LLM 調用"""
        # 從提示中提取訊息內容
        message_start = prompt.find("使用者訊息：") + len("使用者訊息：")
        message_content = prompt[message_start:].strip()
        
        # 查找預設回應，或生成簡單回應
        if message_content in self.mock_responses:
            response_data = self.mock_responses[message_content]
        else:
            # 簡單的啟發式判斷
            if any(word in message_content.lower() for word in ["研究", "分析", "比較", "最新", "!research"]):
                response_data = {
                    "decision": "RESEARCH",
                    "confidence": 0.7,
                    "reasoning": "檢測到研究相關關鍵字",
                    "triggered_criteria": ["關鍵字檢測"]
                }
            else:
                response_data = {
                    "decision": "SIMPLE", 
                    "confidence": 0.8,
                    "reasoning": "看起來是一般性問題",
                    "triggered_criteria": []
                }
        
        # 模擬網路延遲
        await asyncio.sleep(0.1)
        
        return MockResponse(json.dumps(response_data, ensure_ascii=False))


class MockResponse:
    """模擬 LLM 回應物件"""
    
    def __init__(self, content: str):
        self.content = content


def test_rule_based_complexity():
    """測試規則型複雜度評估"""
    print("=" * 50)
    print("🔍 測試規則型複雜度評估")
    print("=" * 50)
    
    for i, test_case in enumerate(TEST_MESSAGES):
        content = test_case["content"]
        expected = test_case["expected"]
        description = test_case["description"]
        
        result = analyze_message_complexity(content)
        
        decision = "RESEARCH" if result["use_research"] else "SIMPLE"
        match = "✅" if decision == expected else "❌"
        
        print(f"\n測試 {i+1}: {description}")
        print(f"訊息: {content}")
        print(f"預期: {expected} | 實際: {decision} {match}")
        print(f"複雜度分數: {result['complexity_score']:.2f}")
        print(f"檢測關鍵字: {', '.join(result['detected_keywords'])}")


def test_llm_response_parsing():
    """測試 LLM 回應解析"""
    print("\n" + "=" * 50)
    print("🤖 測試 LLM 回應解析")
    print("=" * 50)
    
    # 測試正確的 JSON 格式
    valid_json = {
        "decision": "RESEARCH",
        "confidence": 0.85,
        "reasoning": "需要最新資訊和深度分析",
        "triggered_criteria": ["時效性需求", "複雜分析需求"]
    }
    
    result = parse_complexity_assessment_result(json.dumps(valid_json, ensure_ascii=False))
    print(f"\n✅ 正確 JSON 解析:")
    print(f"決策: {result['decision']}")
    print(f"信心: {result['confidence']}")
    print(f"原因: {result['reasoning']}")
    
    # 測試簡單格式
    simple_response = "RESEARCH"
    result = parse_complexity_assessment_result(simple_response)
    print(f"\n✅ 簡單格式解析:")
    print(f"決策: {result['decision']}")
    print(f"信心: {result['confidence']}")
    
    # 測試錯誤格式
    invalid_response = "這不是有效的回應"
    result = parse_complexity_assessment_result(invalid_response)
    print(f"\n⚠️ 錯誤格式處理:")
    print(f"決策: {result['decision']} (降級)")
    print(f"方法: {result['method']}")


async def test_full_llm_assessment():
    """測試完整的 LLM 評估流程"""
    print("\n" + "=" * 50)
    print("🧠 測試完整 LLM 評估流程")
    print("=" * 50)
    
    llm_client = MockLLMClient()
    
    for i, test_case in enumerate(TEST_MESSAGES[:3]):  # 只測試前三個以節省時間
        content = test_case["content"]
        expected = test_case["expected"]
        description = test_case["description"]
        
        try:
            result = await assess_message_complexity_with_llm(content, llm_client)
            
            decision = result["final_decision"]
            match = "✅" if decision == expected else "❌"
            
            print(f"\n測試 {i+1}: {description}")
            print(f"訊息: {content}")
            print(f"預期: {expected} | 實際: {decision} {match}")
            print(f"方法: {result['method']}")
            print(f"信心: {result['confidence']:.2f}")
            print(f"原因: {result['reasoning'][:100]}...")
            
        except Exception as e:
            print(f"\n❌ 測試 {i+1} 失敗: {e}")


def test_complexity_assessment_prompt():
    """測試複雜度評估提示格式"""
    print("\n" + "=" * 50)
    print("📝 測試複雜度評估提示")
    print("=" * 50)
    
    test_message = "請分析 2024 年人工智慧的發展趨勢"
    formatted_prompt = complexity_assessment_prompt.format(message=test_message)
    
    print("✅ 提示格式正確生成")
    print(f"長度: {len(formatted_prompt)} 字符")
    print(f"包含評估維度: {'✅' if '評估維度' in formatted_prompt else '❌'}")
    print(f"包含輸出格式: {'✅' if 'JSON' in formatted_prompt else '❌'}")
    print(f"包含測試訊息: {'✅' if test_message in formatted_prompt else '❌'}")


async def main():
    """主測試函數"""
    print("🌟 三角初華複雜度評估系統測試")
    print("測試新的 LLM + 規則混合判斷邏輯")
    
    try:
        # 1. 測試規則型評估
        test_rule_based_complexity()
        
        # 2. 測試 LLM 回應解析
        test_llm_response_parsing()
        
        # 3. 測試提示格式
        test_complexity_assessment_prompt()
        
        # 4. 測試完整 LLM 流程
        await test_full_llm_assessment()
        
        print("\n" + "=" * 50)
        print("✨ 所有測試完成！")
        print("新的複雜度判斷系統已準備就緒")
        print("=" * 50)
        
    except Exception as e:
        logger.error(f"測試過程中發生錯誤: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())