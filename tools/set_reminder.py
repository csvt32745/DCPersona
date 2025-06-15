"""
設定提醒工具 - 使用 LangChain @tool 裝飾器實作

此模組提供設定提醒的功能，支援時間解析和提醒詳細資料創建。
"""

import logging
from datetime import datetime
from typing import Optional

from langchain_core.tools import tool

from schemas.agent_types import ReminderDetails, ToolExecutionResult


logger = logging.getLogger(__name__)


@tool
def set_reminder(
    message: str,
    target_time_str: str
) -> str:
    """根據使用者提供的訊息和時間，設定提醒
    
    Args:
        message: The reminder message content
        target_time_str: Target time in ISO 8601 format (e.g., '2024-07-26T10:00:00')
    
    Note: channel_id and user_id will be filled by the Discord message handler
    """
    try:
        logger.info(f"設定提醒: {message} 在 {target_time_str}")
        
        # 嘗試解析時間字串
        try:
            target_timestamp = datetime.fromisoformat(target_time_str)
        except ValueError as ve:
            logger.warning(f"時間格式解析失敗: {target_time_str}, 錯誤: {ve}")
            result = ToolExecutionResult(
                success=False,
                message=f"無效的時間格式。請使用 ISO 8601 格式 (YYYY-MM-DDTHH:MM:SS)。錯誤: {str(ve)}"
            )
            # 返回 JSON 格式的結果供 LangChain 處理
            import json
            return json.dumps({
                "success": result.success,
                "message": result.message,
                "data": result.data
            }, ensure_ascii=False)
        
        # 檢查時間是否為未來時間
        current_time = datetime.now()
        if target_timestamp <= current_time:
            result = ToolExecutionResult(
                success=False,
                message="提醒時間必須為未來時間。請提供一個晚於現在的時間。"
            )
            import json
            return json.dumps({
                "success": result.success,
                "message": result.message,
                "data": result.data
            }, ensure_ascii=False)
        
        # 創建提醒詳細資料（channel_id、user_id 和 msg_id 將由 message handler 填入）
        reminder_details = ReminderDetails(
            message=message,
            target_timestamp=target_timestamp.isoformat(),
            channel_id="",  # 將由 Discord message handler 填入
            user_id="",     # 將由 Discord message handler 填入
            msg_id="",      # 將由 Discord message handler 填入
            reminder_id=None,  # 將由 event_scheduler 設定
            metadata={
                "created_at": current_time.isoformat(),
                "tool_name": "set_reminder"
            }
        )
        
        # 創建成功結果
        result = ToolExecutionResult(
            success=True,
            message=f"提醒已成功設定：{message}，時間：{target_timestamp.strftime('%Y年%m月%d日 %H:%M:%S')}, 跟使用者講你設定好了!",
            data={
                "reminder_details": {
                    "message": reminder_details.message,
                    "target_timestamp": reminder_details.target_timestamp,
                    "channel_id": reminder_details.channel_id,
                    "user_id": reminder_details.user_id,
                    "reminder_id": reminder_details.reminder_id,
                    "metadata": reminder_details.metadata
                }
            }
        )
        
        # 返回 JSON 格式的結果供 LangChain 處理
        import json
        return json.dumps({
            "success": result.success,
            "message": result.message,
            "data": result.data
        }, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"設定提醒時發生錯誤: {e}")
        result = ToolExecutionResult(
            success=False,
            message=f"設定提醒時發生錯誤: {str(e)}"
        )
        
        import json
        return json.dumps({
            "success": result.success,
            "message": result.message,
            "data": result.data
        }, ensure_ascii=False) 