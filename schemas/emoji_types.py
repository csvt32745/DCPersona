"""
Emoji 配置相關的資料類型定義

定義 EmojiConfig 資料結構，用於安全地載入和解析 emoji_config.yaml 配置檔案。
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import yaml
import logging
from pathlib import Path


@dataclass
class EmojiConfig:
    """
    Emoji 配置資料結構
    
    Attributes:
        application: 應用程式通用 emoji 配置 {emoji_id: description}
        guilds: 伺服器專屬 emoji 配置 {guild_id: {emoji_id: description}}
    """
    application: Dict[int, str]
    guilds: Dict[int, Dict[int, str]]
    
    @classmethod
    def from_yaml(cls, config_path: str) -> 'EmojiConfig':
        """
        從 YAML 檔案安全地載入 Emoji 配置
        
        Args:
            config_path: YAML 配置檔案路徑
            
        Returns:
            EmojiConfig: 解析後的配置實例
            
        Raises:
            FileNotFoundError: 配置檔案不存在
            yaml.YAMLError: YAML 格式錯誤
            ValueError: 配置格式不正確
        """
        logger = logging.getLogger(__name__)
        
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                logger.warning(f"Emoji 配置檔案不存在: {config_path}，使用預設空白配置")
                return cls(application={}, guilds={})
            
            with open(config_file, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f) or {}
            
            # 解析應用程式 emoji
            application = raw_config.get('application', {})
            if not isinstance(application, dict):
                logger.warning("應用程式 emoji 配置格式不正確，使用空白配置")
                application = {}
            
            # 確保 emoji_id 是整數格式
            parsed_application = {}
            for k, v in application.items():
                try:
                    emoji_id = int(k)
                    parsed_application[emoji_id] = str(v)
                except ValueError:
                    logger.warning(f"無效的應用程式 emoji_id: {k}，跳過")
            application = parsed_application
            
            # 解析伺服器 emoji
            guilds = {}
            for key, value in raw_config.items():
                if key == 'application':
                    continue
                
                # 嘗試將 key 轉換為 guild_id (整數)
                try:
                    guild_id = int(key)
                    if isinstance(value, dict):
                        # 確保 emoji_id 是整數格式
                        parsed_guild_emojis = {}
                        for k, v in value.items():
                            try:
                                emoji_id = int(k)
                                parsed_guild_emojis[emoji_id] = str(v)
                            except ValueError:
                                logger.warning(f"無效的伺服器 {guild_id} emoji_id: {k}，跳過")
                        guilds[guild_id] = parsed_guild_emojis
                    else:
                        logger.warning(f"伺服器 {guild_id} 的 emoji 配置格式不正確，跳過")
                except ValueError:
                    logger.warning(f"無效的 guild_id: {key}，跳過")
            
            logger.info(f"成功載入 Emoji 配置: {len(application)} 個應用程式 emoji，{len(guilds)} 個伺服器")
            return cls(application=application, guilds=guilds)
            
        except yaml.YAMLError as e:
            logger.error(f"YAML 格式錯誤: {e}")
            raise ValueError(f"配置檔案格式錯誤: {e}")
        except Exception as e:
            logger.error(f"載入 Emoji 配置失敗: {e}")
            raise
    
