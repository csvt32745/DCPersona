"""
輸出媒體上下文建構器

統一的 OutputMediaContextBuilder 類別，負責整合多種媒體類型的提示上下文。
結合 EmojiRegistry 和 OutputStickerRegistry 為 LLM 提供完整的媒體使用指南。
"""

import logging
import re
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
    
    def parse_emoji_output(self, text: str, guild_id: Optional[int] = None) -> str:
        """
        修復 LLM 輸出的錯誤 emoji 格式
        
        Args:
            text: 要修復的文字內容
            guild_id: 可選的伺服器 ID
            
        Returns:
            str: 修復後的文字內容
        """
        if not self.emoji_registry:
            return text
            
        # 先修復 <:name:> → <:name:id> 和 <a:name:> → <a:name:id>
        text = re.sub(r'<(a?):([a-zA-Z0-9_]+):>', 
                      lambda m: self._fix_missing_id(m.group(1), m.group(2), guild_id), text)
        
        # 再修復 :name: → <:name:id>（使用更簡單的方法避免已經在 <> 中的）
        # 先暫時替換正確的 emoji 格式
        placeholders = []
        def preserve_correct_emojis(match):
            placeholder = f"__EMOJI_PLACEHOLDER_{len(placeholders)}__"
            placeholders.append(match.group(0))
            return placeholder
        
        # 暫存正確的 emoji 格式
        text = re.sub(r'<a?:[a-zA-Z0-9_]+:\d+>', preserve_correct_emojis, text)
        
        # 修復簡單的 :name: 格式
        text = re.sub(r':([a-zA-Z0-9_]+):', 
                      lambda m: self._fix_simple_emoji(m.group(1), guild_id), text)
        
        # 恢復正確的 emoji 格式
        for i, placeholder in enumerate(placeholders):
            text = text.replace(f"__EMOJI_PLACEHOLDER_{i}__", placeholder)
        return text

    def _fix_simple_emoji(self, name: str, guild_id: Optional[int]) -> str:
        """修復簡單的 :name: 格式"""
        emoji_str = self._find_emoji_exact_match(name, guild_id)
        return emoji_str if emoji_str else f':{name}:'

    def _fix_missing_id(self, animated: str, name: str, guild_id: Optional[int]) -> str:
        """修復缺少 ID 的格式"""
        emoji_str = self._find_emoji_exact_match(name, guild_id)
        return emoji_str if emoji_str else f'<{animated}:{name}:>'

    def _find_emoji_exact_match(self, name: str, guild_id: Optional[int]) -> Optional[str]:
        """
        精確匹配 emoji 名稱
        
        Args:
            name: emoji 名稱
            guild_id: 可選的伺服器 ID
            
        Returns:
            Optional[str]: 找到的 emoji 字串或 None
        """
        # 優先伺服器 emoji
        if guild_id and guild_id in self.emoji_registry.available_emojis:
            for emoji_obj in self.emoji_registry.available_emojis[guild_id].values():
                if emoji_obj.name.lower() == name.lower():
                    return str(emoji_obj)
        
        # 應用程式 emoji  
        for emoji_obj in self.emoji_registry.available_emojis.get(-1, {}).values():
            if emoji_obj.name.lower() == name.lower():
                return str(emoji_obj)
        
        return None