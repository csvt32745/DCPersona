"""
LangGraph 狀態持久化管理

管理 Discord 會話與 LangGraph 狀態的綁定，
支援多輪對話追問和自動清理過期會話。
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import discord

from agents.state import OverallState, DiscordContext, ResearchProgress
from agents.utils import generate_session_id, extract_discord_context


@dataclass
class SessionData:
    """會話資料結構"""
    session_id: str
    user_id: int
    channel_id: int
    guild_id: Optional[int]
    created_at: datetime
    last_activity: datetime
    message_count: int
    is_active: bool
    
    # LangGraph 狀態
    langgraph_state: Optional[Dict[str, Any]] = None
    
    # 研究進度
    current_progress: Optional[ResearchProgress] = None
    
    # Discord 上下文
    discord_context: Optional[Dict[str, Any]] = None
    
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


class SessionManager:
    """會話管理器"""
    
    def __init__(self, cleanup_interval: int = 3600, session_timeout_hours: int = 24):
        """
        初始化會話管理器
        
        Args:
            cleanup_interval: 清理間隔（秒）
            session_timeout_hours: 會話超時時間（小時）
        """
        self.sessions: Dict[str, SessionData] = {}
        self.user_sessions: Dict[int, List[str]] = {}  # 使用者 ID -> 會話 ID 列表
        self.channel_sessions: Dict[int, List[str]] = {}  # 頻道 ID -> 會話 ID 列表
        
        self.cleanup_interval = cleanup_interval
        self.session_timeout_hours = session_timeout_hours
        self.logger = logging.getLogger(__name__)
        
        # 啟動定期清理任務
        self._cleanup_task = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """啟動定期清理任務"""
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
                self.logger.error(f"定期清理會話時發生錯誤: {str(e)}")
    
    async def create_session(self, message: discord.Message) -> SessionData:
        """
        創建新會話
        
        Args:
            message: Discord 訊息
            
        Returns:
            SessionData: 新建的會話資料
        """
        # 提取 Discord 上下文
        discord_ctx_dict = extract_discord_context(message)
        
        # 生成會話 ID
        session_id = generate_session_id(message.author.id, message.channel.id)
        
        # 創建會話資料
        session_data = SessionData(
            session_id=session_id,
            user_id=message.author.id,
            channel_id=message.channel.id,
            guild_id=message.guild.id if message.guild else None,
            created_at=datetime.now(),
            last_activity=datetime.now(),
            message_count=1,
            is_active=True,
            discord_context=discord_ctx_dict
        )
        
        # 儲存會話
        self.sessions[session_id] = session_data
        
        # 更新索引
        self._add_to_user_sessions(message.author.id, session_id)
        self._add_to_channel_sessions(message.channel.id, session_id)
        
        self.logger.info(f"創建新會話: {session_id} (使用者: {message.author.id})")
        return session_data
    
    def get_session(self, session_id: str) -> Optional[SessionData]:
        """
        獲取會話資料
        
        Args:
            session_id: 會話 ID
            
        Returns:
            Optional[SessionData]: 會話資料或 None
        """
        return self.sessions.get(session_id)
    
    def get_active_session_for_user(self, user_id: int, channel_id: int) -> Optional[SessionData]:
        """
        獲取使用者在特定頻道的活躍會話
        
        Args:
            user_id: 使用者 ID
            channel_id: 頻道 ID
            
        Returns:
            Optional[SessionData]: 活躍會話或 None
        """
        user_session_ids = self.user_sessions.get(user_id, [])
        
        for session_id in user_session_ids:
            session = self.sessions.get(session_id)
            if (session and 
                session.is_active and 
                session.channel_id == channel_id and
                not session.is_expired(self.session_timeout_hours)):
                return session
        
        return None
    
    def get_or_create_session(self, message: discord.Message) -> SessionData:
        """
        獲取或創建會話
        
        Args:
            message: Discord 訊息
            
        Returns:
            SessionData: 會話資料
        """
        # 先嘗試獲取現有會話
        existing_session = self.get_active_session_for_user(
            message.author.id, 
            message.channel.id
        )
        
        if existing_session:
            existing_session.update_activity()
            return existing_session
        
        # 創建新會話
        return asyncio.create_task(self.create_session(message))
    
    def update_session_state(self, session_id: str, langgraph_state: Dict[str, Any]):
        """
        更新會話的 LangGraph 狀態
        
        Args:
            session_id: 會話 ID
            langgraph_state: LangGraph 狀態
        """
        session = self.sessions.get(session_id)
        if session:
            session.langgraph_state = langgraph_state
            session.update_activity()
    
    def update_session_progress(self, session_id: str, progress: ResearchProgress):
        """
        更新會話的研究進度
        
        Args:
            session_id: 會話 ID
            progress: 研究進度
        """
        session = self.sessions.get(session_id)
        if session:
            session.current_progress = progress
            session.update_activity()
    
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
        session = self.sessions.pop(session_id, None)
        if session:
            # 從索引中移除
            self._remove_from_user_sessions(session.user_id, session_id)
            self._remove_from_channel_sessions(session.channel_id, session_id)
            self.logger.info(f"移除會話: {session_id}")
    
    async def cleanup_expired_sessions(self):
        """清理過期會話"""
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if session.is_expired(self.session_timeout_hours):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.remove_session(session_id)
        
        if expired_sessions:
            self.logger.info(f"清理了 {len(expired_sessions)} 個過期會話")
    
    def get_user_sessions(self, user_id: int) -> List[SessionData]:
        """
        獲取使用者的所有會話
        
        Args:
            user_id: 使用者 ID
            
        Returns:
            List[SessionData]: 會話列表
        """
        session_ids = self.user_sessions.get(user_id, [])
        return [self.sessions[sid] for sid in session_ids if sid in self.sessions]
    
    def get_channel_sessions(self, channel_id: int) -> List[SessionData]:
        """
        獲取頻道的所有會話
        
        Args:
            channel_id: 頻道 ID
            
        Returns:
            List[SessionData]: 會話列表
        """
        session_ids = self.channel_sessions.get(channel_id, [])
        return [self.sessions[sid] for sid in session_ids if sid in self.sessions]
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        獲取會話統計資訊
        
        Returns:
            Dict: 統計資訊
        """
        active_sessions = sum(1 for s in self.sessions.values() if s.is_active)
        total_sessions = len(self.sessions)
        
        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "expired_sessions": total_sessions - active_sessions,
            "unique_users": len(self.user_sessions),
            "unique_channels": len(self.channel_sessions),
        }
    
    def _add_to_user_sessions(self, user_id: int, session_id: str):
        """添加會話到使用者索引"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = []
        self.user_sessions[user_id].append(session_id)
    
    def _remove_from_user_sessions(self, user_id: int, session_id: str):
        """從使用者索引中移除會話"""
        if user_id in self.user_sessions:
            try:
                self.user_sessions[user_id].remove(session_id)
                if not self.user_sessions[user_id]:
                    del self.user_sessions[user_id]
            except ValueError:
                pass
    
    def _add_to_channel_sessions(self, channel_id: int, session_id: str):
        """添加會話到頻道索引"""
        if channel_id not in self.channel_sessions:
            self.channel_sessions[channel_id] = []
        self.channel_sessions[channel_id].append(session_id)
    
    def _remove_from_channel_sessions(self, channel_id: int, session_id: str):
        """從頻道索引中移除會話"""
        if channel_id in self.channel_sessions:
            try:
                self.channel_sessions[channel_id].remove(session_id)
                if not self.channel_sessions[channel_id]:
                    del self.channel_sessions[channel_id]
            except ValueError:
                pass
    
    async def save_to_file(self, filepath: str):
        """
        將會話資料保存到檔案
        
        Args:
            filepath: 檔案路徑
        """
        try:
            data = {
                "sessions": {sid: session.to_dict() for sid, session in self.sessions.items()},
                "user_sessions": self.user_sessions,
                "channel_sessions": self.channel_sessions,
                "saved_at": datetime.now().isoformat(),
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"會話資料已保存到: {filepath}")
            
        except Exception as e:
            self.logger.error(f"保存會話資料失敗: {str(e)}")
    
    async def load_from_file(self, filepath: str):
        """
        從檔案載入會話資料
        
        Args:
            filepath: 檔案路徑
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 載入會話
            self.sessions = {}
            for sid, session_dict in data.get("sessions", {}).items():
                self.sessions[sid] = SessionData.from_dict(session_dict)
            
            # 載入索引
            self.user_sessions = data.get("user_sessions", {})
            self.channel_sessions = data.get("channel_sessions", {})
            
            # 轉換索引鍵為整數（JSON 序列化後變成字串）
            self.user_sessions = {int(k): v for k, v in self.user_sessions.items()}
            self.channel_sessions = {int(k): v for k, v in self.channel_sessions.items()}
            
            self.logger.info(f"會話資料已從 {filepath} 載入，共 {len(self.sessions)} 個會話")
            
        except FileNotFoundError:
            self.logger.info(f"會話檔案 {filepath} 不存在，將創建新的會話管理器")
        except Exception as e:
            self.logger.error(f"載入會話資料失敗: {str(e)}")
    
    async def shutdown(self):
        """關閉會話管理器"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("會話管理器已關閉")


# 全域會話管理器實例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """獲取全域會話管理器實例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


async def init_session_manager(
    cleanup_interval: int = 3600,
    session_timeout_hours: int = 24,
    load_from_file: Optional[str] = None
) -> SessionManager:
    """
    初始化全域會話管理器
    
    Args:
        cleanup_interval: 清理間隔（秒）
        session_timeout_hours: 會話超時時間（小時）
        load_from_file: 載入會話資料的檔案路徑
        
    Returns:
        SessionManager: 會話管理器實例
    """
    global _session_manager
    _session_manager = SessionManager(cleanup_interval, session_timeout_hours)
    
    if load_from_file:
        await _session_manager.load_from_file(load_from_file)
    
    return _session_manager


async def shutdown_session_manager(save_to_file: Optional[str] = None):
    """
    關閉全域會話管理器
    
    Args:
        save_to_file: 保存會話資料的檔案路徑
    """
    global _session_manager
    if _session_manager:
        if save_to_file:
            await _session_manager.save_to_file(save_to_file)
        await _session_manager.shutdown()
        _session_manager = None