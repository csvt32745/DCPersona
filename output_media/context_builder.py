"""
輸出媒體上下文建構器

統一的 OutputMediaContextBuilder 類別，負責整合多種媒體類型的提示上下文。
結合 EmojiRegistry 和 OutputStickerRegistry 為 LLM 提供完整的媒體使用指南。
"""

import logging
from typing import Optional, List, Dict, Any
from .emoji_registry import EmojiRegistry
from .sticker_registry import OutputStickerRegistry


class OutputMediaContextBuilder:
    """
    輸出媒體上下文建構器
    
    整合 emoji 和 sticker 的提示上下文，為 LLM 提供統一的媒體使用指南。
    """
    
    def __init__(
        self, 
        emoji_registry: Optional[EmojiRegistry] = None,
        sticker_registry: Optional[OutputStickerRegistry] = None
    ):
        """
        初始化 OutputMediaContextBuilder
        
        Args:
            emoji_registry: Emoji 註冊器實例
            sticker_registry: Sticker 註冊器實例
        """
        self.logger = logging.getLogger(__name__)
        self.emoji_registry = emoji_registry
        self.sticker_registry = sticker_registry
        
        self.logger.info("OutputMediaContextBuilder 已初始化")
    
    def build_full_context(self, guild_id: Optional[int] = None) -> str:
        """
        建構完整的媒體上下文
        
        Args:
            guild_id: 可選的伺服器 ID
            
        Returns:
            str: 完整的媒體使用指南
        """
        context_parts = []
        
        # 建構 emoji 上下文
        if self.emoji_registry:
            emoji_context = self.emoji_registry.build_prompt_context(guild_id)
            if emoji_context.strip():
                context_parts.append(emoji_context)
        
        # 建構 sticker 上下文
        if self.sticker_registry:
            sticker_context = self.sticker_registry.build_prompt_context(guild_id)
            if sticker_context.strip():
                context_parts.append(sticker_context)
        
        # 組合上下文
        if not context_parts:
            return ""
        
        full_context = "\n\n".join(context_parts)
        
        # 添加統一的使用指南
        usage_guide = self._build_usage_guide()
        if usage_guide:
            full_context += f"\n\n{usage_guide}"
        
        return full_context
    
    def build_emoji_context(self, guild_id: Optional[int] = None) -> str:
        """
        僅建構 emoji 上下文
        
        Args:
            guild_id: 可選的伺服器 ID
            
        Returns:
            str: Emoji 使用指南
        """
        if not self.emoji_registry:
            return ""
        
        return self.emoji_registry.build_prompt_context(guild_id)
    
    def build_sticker_context(self, guild_id: Optional[int] = None) -> str:
        """
        僅建構 sticker 上下文
        
        Args:
            guild_id: 可選的伺服器 ID
            
        Returns:
            str: Sticker 使用指南
        """
        if not self.sticker_registry:
            return ""
        
        return self.sticker_registry.build_prompt_context(guild_id)
    
    def _build_usage_guide(self) -> str:
        """
        建構統一的媒體使用指南
        
        Returns:
            str: 使用指南文字
        """
        guide_parts = []
        
        # Emoji 使用指南
        if self.emoji_registry:
            guide_parts.append("• Emoji 格式：<:emoji_name:emoji_id> 或 <a:animated_emoji:emoji_id>")
        
        # Sticker 使用指南
        if self.sticker_registry:
            guide_parts.append("• Sticker 格式：<sticker:sticker_id>（尚未實作）")
        
        if not guide_parts:
            return ""
        
        return f"""
📝 **媒體使用規則：**
{chr(10).join(guide_parts)}

請適度使用這些媒體元素來增強回應的表達力和互動性。
"""
    
    def get_media_stats(self) -> Dict[str, Any]:
        """
        獲取所有媒體的統計資訊
        
        Returns:
            Dict[str, Any]: 完整的統計資訊
        """
        stats = {
            "emoji": {},
            "sticker": {},
            "total_media_types": 0
        }
        
        # 收集 emoji 統計
        if self.emoji_registry:
            stats["emoji"] = self.emoji_registry.get_stats()
            stats["total_media_types"] += 1
        
        # 收集 sticker 統計
        if self.sticker_registry:
            stats["sticker"] = self.sticker_registry.get_stats()
            if stats["sticker"].get("status") != "not_implemented":
                stats["total_media_types"] += 1
        
        return stats
    
    def has_media_available(self, guild_id: Optional[int] = None) -> bool:
        """
        檢查是否有可用的媒體內容
        
        Args:
            guild_id: 可選的伺服器 ID
            
        Returns:
            bool: 是否有可用媒體
        """
        # 檢查 emoji
        if self.emoji_registry:
            emoji_context = self.emoji_registry.build_prompt_context(guild_id)
            if emoji_context.strip():
                return True
        
        # 檢查 sticker（目前預留）
        if self.sticker_registry:
            sticker_context = self.sticker_registry.build_prompt_context(guild_id)
            if sticker_context.strip():
                return True
        
        return False 