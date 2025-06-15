"""
EventScheduler 使用示例

展示如何使用 EventScheduler 進行事件排程和回調處理。
"""

import asyncio
from datetime import datetime, timedelta
from scheduler import EventScheduler


async def reminder_callback(event_type: str, event_details: dict, event_id: str):
    """提醒事件的回調函數"""
    print(f"🔔 提醒觸發！")
    print(f"   事件ID: {event_id}")
    print(f"   事件類型: {event_type}")
    print(f"   提醒內容: {event_details.get('message', '無內容')}")
    print(f"   觸發時間: {datetime.now()}")
    print("-" * 50)


async def notification_callback(event_type: str, event_details: dict, event_id: str):
    """通知事件的回調函數"""
    print(f"📢 通知觸發！")
    print(f"   事件ID: {event_id}")
    print(f"   通知內容: {event_details.get('title', '無標題')}")
    print(f"   詳細資訊: {event_details.get('description', '無描述')}")
    print("-" * 50)


async def main():
    """主要示例函數"""
    print("🚀 EventScheduler 示例開始")
    print("=" * 50)
    
    # 創建排程器實例
    scheduler = EventScheduler(data_dir="example_data")
    
    # 註冊回調函數
    scheduler.register_callback("reminder", reminder_callback)
    scheduler.register_callback("notification", notification_callback)
    
    # 啟動排程器
    await scheduler.start()
    
    try:
        # 排程一些測試事件
        print("📅 排程測試事件...")
        
        # 5秒後的提醒
        reminder_time = datetime.now() + timedelta(seconds=5)
        reminder_id = await scheduler.schedule_event(
            event_type="reminder",
            event_details={
                "message": "這是一個測試提醒！",
                "user_id": "user123",
                "channel_id": "channel456"
            },
            target_time=reminder_time
        )
        print(f"✅ 已排程提醒事件: {reminder_id} (5秒後觸發)")
        
        # 8秒後的通知
        notification_time = datetime.now() + timedelta(seconds=8)
        notification_id = await scheduler.schedule_event(
            event_type="notification",
            event_details={
                "title": "系統通知",
                "description": "這是一個測試通知訊息",
                "priority": "high"
            },
            target_time=notification_time
        )
        print(f"✅ 已排程通知事件: {notification_id} (8秒後觸發)")
        
        # 15秒後的另一個提醒（我們會在10秒後取消它）
        future_reminder_time = datetime.now() + timedelta(seconds=15)
        future_reminder_id = await scheduler.schedule_event(
            event_type="reminder",
            event_details={
                "message": "這個提醒會被取消",
                "user_id": "user789"
            },
            target_time=future_reminder_time,
            event_id="will_be_cancelled"
        )
        print(f"✅ 已排程將被取消的提醒: {future_reminder_id} (15秒後觸發)")
        
        # 顯示當前已排程的事件
        print("\n📋 當前已排程的事件:")
        events = await scheduler.get_scheduled_events()
        for i, event in enumerate(events, 1):
            print(f"   {i}. 事件ID: {event['event_id']}")
            print(f"      下次執行時間: {event['next_run_time']}")
        
        # 等待一些事件觸發
        print(f"\n⏰ 等待事件觸發... (當前時間: {datetime.now()})")
        await asyncio.sleep(10)
        
        # 取消未來的提醒
        print(f"\n❌ 取消事件: {future_reminder_id}")
        cancelled = await scheduler.cancel_event(future_reminder_id)
        if cancelled:
            print("✅ 事件已成功取消")
        else:
            print("❌ 取消事件失敗")
        
        # 再等待一段時間確保所有事件都處理完
        print("\n⏰ 等待剩餘事件處理完成...")
        await asyncio.sleep(5)
        
        # 顯示最終狀態
        print("\n📋 最終已排程的事件:")
        final_events = await scheduler.get_scheduled_events()
        if final_events:
            for i, event in enumerate(final_events, 1):
                print(f"   {i}. 事件ID: {event['event_id']}")
        else:
            print("   無剩餘事件")
        
    except KeyboardInterrupt:
        print("\n⚠️  收到中斷信號，正在關閉...")
    
    finally:
        # 關閉排程器
        await scheduler.shutdown()
        print("\n🛑 EventScheduler 示例結束")


if __name__ == "__main__":
    asyncio.run(main()) 