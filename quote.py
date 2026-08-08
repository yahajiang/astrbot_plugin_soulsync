"""金句引用机制模块"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from .session import UserSession


@dataclass
class Quote:
    """金句"""
    content: str
    timestamp: float
    source: str  # "user" 或 "reflection"


class QuoteManager:
    """金句管理器"""

    def __init__(self, data_dir: Optional[Path] = None):
        self.quotes: dict[str, List[Quote]] = {}
        self.data_dir = data_dir
        if data_dir:
            self._load_all()

    def _load_all(self):
        """加载所有用户金句"""
        if not self.data_dir:
            return

        try:
            data_file = self.data_dir / "quotes.json"
            if data_file.exists():
                data = json.loads(data_file.read_text(encoding="utf-8"))
                for user_id, quotes_data in data.items():
                    self.quotes[user_id] = [
                        Quote(
                            content=q["content"],
                            timestamp=q["timestamp"],
                            source=q.get("source", "user"),
                        )
                        for q in quotes_data
                    ]
                logger.info(f"QuoteManager 已加载 {len(self.quotes)} 个用户的金句")
        except Exception as e:
            logger.error(f"QuoteManager 加载金句失败: {e}")

    def _save_all(self):
        """保存所有用户金句"""
        if not self.data_dir:
            return

        try:
            data = {}
            for user_id, quotes in self.quotes.items():
                data[user_id] = [
                    {
                        "content": q.content,
                        "timestamp": q.timestamp,
                        "source": q.source,
                    }
                    for q in quotes
                ]

            data_file = self.data_dir / "quotes.json"
            data_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"QuoteManager 保存金句失败: {e}")

    def save_session(self, user_id: str, session: UserSession):
        """保存会话中的金句"""
        if user_id not in self.quotes:
            self.quotes[user_id] = []

        for entry in session.dialogue_history:
            # 检查是否是高密度表达
            if self._is_high_density(entry.user_input):
                quote = Quote(
                    content=entry.user_input,
                    timestamp=entry.timestamp,
                    source="user",
                )
                self.quotes[user_id].append(quote)

        self._save_all()

    def get_quotes(self, user_id: str) -> List[Quote]:
        """获取用户金句"""
        return self.quotes.get(user_id, [])

    def remove_quote(self, user_id: str, keyword: str):
        """移除包含关键词的金句"""
        if user_id not in self.quotes:
            return

        self.quotes[user_id] = [
            q for q in self.quotes[user_id]
            if keyword not in q.content
        ]
        self._save_all()

    def clear_all(self, user_id: str):
        """清空所有金句"""
        self.quotes[user_id] = []
        self._save_all()

    def check引用(self, user_id: str, user_input: str) -> Optional[str]:
        """
        检查是否需要引用金句

        仅在用户提到与某条金句相关的话题时引用
        """
        if user_id not in self.quotes:
            return None

        quotes = self.quotes[user_id]
        if not quotes:
            return None

        # 简单实现：检查关键词匹配
        for quote in quotes:
            if self._is_related(quote.content, user_input):
                return f"你之前说过一句话：『{quote.content}』。今天这句话还成立吗？"

        return None

    def _is_high_density(self, text: str) -> bool:
        """判断是否是高密度表达"""
        # 长度超过15个字
        if len(text) < 15:
            return False

        # 包含明确情绪指向
        emotion_words = [
            "累", "烦", "开心", "难过", "生气", "害怕",
            "孤独", "焦虑", "压力", "迷茫", "无聊",
            "想", "不想", "喜欢", "讨厌", "爱", "恨",
        ]
        return any(w in text for w in emotion_words)

    def _is_related(self, quote: str, user_input: str) -> bool:
        """判断是否相关"""
        # 简单实现：检查是否有共同关键词
        quote_words = set(quote)
        input_words = set(user_input)

        # 排除功能词
        function_words = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一"}
        quote_words -= function_words
        input_words -= function_words

        # 检查交集
        common = quote_words & input_words
        return len(common) >= 3
