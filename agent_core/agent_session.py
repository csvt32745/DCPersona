"""
會話管理系統

統一管理 Discord 會話與 LangGraph 狀態的綁定，
支援會話創建、狀態管理、訊息快取和自動清理。
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import hashlib

from schemas.agent_types import OverallState, MsgNode


@dataclass
class SessionData:
    """會話資料結構"""
    session_id: str
    channel_id: str
    created_at: datetime
    last_activity: datetime
    message_count: int
    is_active: bool
    
    # LangGraph 狀態
    langgraph_state: Optional[Dict[str, Any]] = None
    
    # Discord 訊息快取
    cached_messages: Optional[List[Dict]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式以便序列化"""
        data = asdict(self)
        # 轉換 datetime 為 ISO 格式字串
        data['created_at'] = self.created_at.isoformat()
        data['last_activity'] = self.last_activity.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionData':
        """從字典創建會話資料"""
        # 轉換 ISO 格式字串為 datetime
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_activity'] = datetime.fromisoformat(data['last_activity'])
        return cls(**data)
    
    def update_activity(self):
        """更新最後活動時間"""
        self.last_activity = datetime.now()
        self.message_count += 1
    
    def is_expired(self, timeout_hours: int = 24) -> bool:
        """檢查會話是否過期"""
        expiry_time = self.last_activity + timedelta(hours=timeout_hours)
        return datetime.now() > expiry_time


@dataclass
class DiscordMessageCache:
    """Discord 訊息快取結構"""
    messages: List[Dict]
    last_updated: datetime
    max_size: int = 100
    
    def add_message(self, message: Dict):
        """添加訊息到快取"""
        self.messages.append(message)
        if len(self.messages) > self.max_size:
            # 保留最新的訊息
            self.messages = self.messages[-self.max_size:]
        self.last_updated = datetime.now()
    
    def get_recent_messages(self, count: int = 10) -> List[Dict]:
        """獲取最近的訊息"""
        return self.messages[-count:]


class AgentSession:
    """Agent 會話管理器"""
    
    def __init__(self, cleanup_interval: int = 3600, session_timeout_hours: int = 24):
        """
        初始化會話管理器
        
        Args:
            cleanup_interval: 清理間隔（秒）
            session_timeout_hours: 會話超時時間（小時）
        """
        self.sessions: Dict[str, SessionData] = {}
        self.cache: Dict[str, DiscordMessageCache] = {}
        
        self.cleanup_interval = cleanup_interval
        self.session_timeout_hours = session_timeout_hours
        self.logger = logging.getLogger(__name__)
        
        # 啟動定期清理任務
        self._cleanup_task = None
        # 只在有運行的事件循環時才啟動清理任務
        try:
            asyncio.get_running_loop()
            self._start_cleanup_task()
        except RuntimeError:
            # 沒有運行的事件循環，稍後再啟動
            pass
    
    def _start_cleanup_task(self):
        """啟動清理任務"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """定期清理過期會話"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"清理任務出錯: {e}")
    
    def create_session(self, channel_id: str) -> str:
        """
        基於 channel_id 生成唯一會話 ID
        
        Args:
            channel_id: Discord 頻道 ID
            
        Returns:
            str: 新生成的會話 ID
        """
        # 生成基於時間戳和頻道 ID 的唯一會話 ID
        timestamp = str(datetime.now().timestamp())
        unique_string = f"{channel_id}_{timestamp}"
        session_id = f"session_{hashlib.md5(unique_string.encode()).hexdigest()[:8]}"
        
        # 創建會話資料
        session_data = SessionData(
            session_id=session_id,
            channel_id=channel_id,
            created_at=datetime.now(),
            last_activity=datetime.now(),
            message_count=0,
            is_active=True,
            langgraph_state={
                'messages': [],
                'tool_calls': [],
                'current_round': 0,
                'research_progress': None
            }
        )
        
        # 儲存會話
        self.sessions[session_id] = session_data
        
        # 初始化訊息快取
        self.cache[session_id] = DiscordMessageCache(
            messages=[],
            last_updated=datetime.now()
        )
        
        self.logger.info(f"創建新會話: {session_id} (頻道: {channel_id})")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[SessionData]:
        """
        獲取會話資料
        
        Args:
            session_id: 會話 ID
            
        Returns:
            Optional[SessionData]: 會話資料或 None
        """
        return self.sessions.get(session_id)
    
    def get_active_session_for_channel(self, channel_id: str) -> Optional[SessionData]:
        """
        獲取頻道的活躍會話
        
        Args:
            channel_id: 頻道 ID
            
        Returns:
            Optional[SessionData]: 活躍會話或 None
        """
        for session in self.sessions.values():
            if (session.channel_id == channel_id and 
                session.is_active and
                not session.is_expired(self.session_timeout_hours)):
                return session
        
        return None
    
    def get_langgraph_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取 LangGraph 狀態
        
        Args:
            session_id: 會話 ID
            
        Returns:
            Optional[Dict]: LangGraph 狀態或 None
        """
        session = self.sessions.get(session_id)
        if session:
            return session.langgraph_state
        return None
    
    def update_langgraph_state(self, session_id: str, state: Dict[str, Any]):
        """
        更新 LangGraph 狀態
        
        Args:
            session_id: 會話 ID
            state: 新的狀態資料
        """
        session = self.sessions.get(session_id)
        if session:
            session.langgraph_state = state
            session.update_activity()
            self.logger.debug(f"更新會話 {session_id} 的 LangGraph 狀態")
    
    def cache_discord_messages(self, session_id: str, messages: List[Dict]):
        """
        快取 Discord 訊息歷史
        
        Args:
            session_id: 會話 ID
            messages: 訊息列表
        """
        if session_id in self.cache:
            cache = self.cache[session_id]
            for message in messages:
                cache.add_message(message)
            self.logger.debug(f"快取 {len(messages)} 條訊息到會話 {session_id}")
    
    def get_cached_messages(self, session_id: str, count: int = 10) -> List[Dict]:
        """
        獲取快取的訊息
        
        Args:
            session_id: 會話 ID
            count: 返回的訊息數量
            
        Returns:
            List[Dict]: 快取的訊息列表
        """
        cache = self.cache.get(session_id)
        if cache:
            return cache.get_recent_messages(count)
        return []
    
    async def cleanup_expired_sessions(self):
        """清理過期會話"""
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if session.is_expired(self.session_timeout_hours):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.sessions.pop(session_id, None)
            self.cache.pop(session_id, None)
            self.logger.info(f"清理過期會話: {session_id}")
        
        if expired_sessions:
            self.logger.info(f"清理了 {len(expired_sessions)} 個過期會話")
    
    def close_session(self, session_id: str):
        """
        關閉會話
        
        Args:
            session_id: 會話 ID
        """
        session = self.sessions.get(session_id)
        if session:
            session.is_active = False
            self.logger.info(f"關閉會話: {session_id}")
    
    def remove_session(self, session_id: str):
        """
        移除會話
        
        Args:
            session_id: 會話 ID
        """
        self.sessions.pop(session_id, None)
        self.cache.pop(session_id, None)
        self.logger.info(f"移除會話: {session_id}")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        獲取會話統計資訊
        
        Returns:
            Dict: 統計資訊
        """
        active_sessions = sum(1 for s in self.sessions.values() if s.is_active)
        total_messages = sum(len(cache.messages) for cache in self.cache.values())
        
        return {
            'total_sessions': len(self.sessions),
            'active_sessions': active_sessions,
            'total_cached_messages': total_messages,
            'cache_size': len(self.cache)
        }
    
    async def shutdown(self):
        """關閉會話管理器"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("會話管理器已關閉")


# 全域會話管理器實例
_agent_session_manager = None

def get_agent_session() -> AgentSession:
    """獲取全域會話管理器實例"""
    global _agent_session_manager
    if _agent_session_manager is None:
        _agent_session_manager = AgentSession()
    return _agent_session_manager 