"""
型別安全的 Patchnote 配置結構定義

簡化版 patchnote 系統，移除版本號複雜度，提供簡潔的更新記錄顯示。
"""

from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path
import yaml
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PatchnoteUpdate:
    """單一更新記錄"""
    date: str
    title: str
    items: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """驗證資料格式"""
        # 驗證日期格式
        try:
            datetime.strptime(self.date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"日期格式錯誤: {self.date}，應為 YYYY-MM-DD 格式")
        
        # 驗證標題不為空
        if not self.title.strip():
            raise ValueError("標題不能為空")
        
        # items 可以為空（當標題已包含完整資訊時）
        # 不需要驗證 items 必須存在


@dataclass
class PatchnoteConfig:
    """Patchnote 配置根結構"""
    updates: List[PatchnoteUpdate] = field(default_factory=list)
    
    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "PatchnoteConfig":
        """從 YAML 檔案載入配置
        
        Args:
            yaml_path: YAML 檔案路徑
            
        Returns:
            PatchnoteConfig: 解析後的配置實例
            
        Raises:
            FileNotFoundError: 檔案不存在
            yaml.YAMLError: YAML 格式錯誤
            ValueError: 資料驗證錯誤
        """
        if not yaml_path.exists():
            raise FileNotFoundError(f"找不到 patchnote 配置檔案: {yaml_path}")
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data or 'updates' not in data:
                raise ValueError("YAML 檔案必須包含 'updates' 欄位")
            
            updates = []
            for update_data in data['updates']:
                try:
                    update = PatchnoteUpdate(
                        date=update_data['date'],
                        title=update_data['title'],
                        items=update_data.get('items', [])
                    )
                    updates.append(update)
                except KeyError as e:
                    raise ValueError(f"更新記錄缺少必要欄位: {e}")
                except Exception as e:
                    raise ValueError(f"更新記錄格式錯誤: {e}")
            
            # 按日期排序（最新的在前）
            updates.sort(key=lambda x: x.date, reverse=True)
            
            return cls(updates=updates)
            
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"YAML 檔案格式錯誤: {e}")
    
    def get_latest_updates(self, count: int = 5) -> List[PatchnoteUpdate]:
        """獲取最新的 N 個更新記錄
        
        Args:
            count: 要返回的更新數量
            
        Returns:
            List[PatchnoteUpdate]: 最新的更新記錄列表
        """
        return self.updates[:count]
    
    def validate(self) -> bool:
        """驗證配置完整性
        
        Returns:
            bool: 驗證是否通過
        """
        try:
            if not self.updates:
                logger.warning("沒有找到任何更新記錄")
                return False
            
            # 驗證每個更新記錄
            for i, update in enumerate(self.updates):
                try:
                    # 觸發 __post_init__ 驗證
                    update.__post_init__()
                except Exception as e:
                    logger.error(f"更新記錄 #{i+1} 驗證失敗: {e}")
                    return False
            
            logger.info(f"配置驗證通過，共 {len(self.updates)} 個更新記錄")
            return True
            
        except Exception as e:
            logger.error(f"配置驗證時發生錯誤: {e}")
            return False


def load_patchnote_config(yaml_path: Optional[Path] = None) -> Optional[PatchnoteConfig]:
    """載入 patchnote 配置
    
    Args:
        yaml_path: YAML 檔案路徑，預設為當前目錄下的 patchnotes.yaml
        
    Returns:
        Optional[PatchnoteConfig]: 載入成功時返回配置實例，失敗時返回 None
    """
    if yaml_path is None:
        yaml_path = Path("patchnotes.yaml")
    
    try:
        config = PatchnoteConfig.from_yaml(yaml_path)
        if config.validate():
            return config
        else:
            logger.error("配置驗證失敗")
            return None
    except Exception as e:
        logger.error(f"載入 patchnote 配置失敗: {e}")
        return None