"""矛盾检测模块"""

from __future__ import annotations

import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional

from .session import UserSession


class ConflictType(Enum):
    """矛盾类型"""
    WILL = "will"  # 意愿矛盾
    EMOTION = "emotion"  # 情感矛盾
    SELF = "self"  # 自我矛盾
    TEMPORAL = "temporal"  # 时序矛盾


@dataclass
class Conflict:
    """矛盾记录"""
    type: ConflictType
    content: str
    timestamp: float
    resolved: bool = False


class ConflictDetector:
    """矛盾检测器"""

    def __init__(self):
        pass

    def detect(self, session: UserSession, user_input: str) -> Optional[Conflict]:
        """
        检测矛盾

        四种矛盾类型：
        1. 意愿矛盾：「我想……但是……」
        2. 情感矛盾：「我爱他，但我恨他」
        3. 自我矛盾：「我不是在意，我只是……」
        4. 时序矛盾：「我之前觉得……现在又……」
        """
        # ── 意愿矛盾 ──
        if self._is_will_conflict(user_input):
            return Conflict(
                type=ConflictType.WILL,
                content=user_input,
                timestamp=__import__("time").time(),
            )

        # ── 情感矛盾 ──
        if self._is_emotion_conflict(user_input):
            return Conflict(
                type=ConflictType.EMOTION,
                content=user_input,
                timestamp=__import__("time").time(),
            )

        # ── 自我矛盾 ──
        if self._is_self_conflict(user_input):
            return Conflict(
                type=ConflictType.SELF,
                content=user_input,
                timestamp=__import__("time").time(),
            )

        # ── 时序矛盾 ──
        if self._is_temporal_conflict(user_input):
            return Conflict(
                type=ConflictType.TEMPORAL,
                content=user_input,
                timestamp=__import__("time").time(),
            )

        return None

    def _is_will_conflict(self, text: str) -> bool:
        """检测意愿矛盾"""
        patterns = [
            r"我想.*但是",
            r"我想.*可是",
            r"我想.*然而",
            r"我想.*不过",
            r"我想要.*但是",
            r"我希望.*但是",
        ]
        return any(re.search(p, text) for p in patterns)

    def _is_emotion_conflict(self, text: str) -> bool:
        """检测情感矛盾"""
        patterns = [
            r"我爱.*但我恨",
            r"我喜欢.*但我讨厌",
            r"我开心.*但我难过",
            r"我爱.*但是我恨",
            r"我喜欢.*但是我讨厌",
        ]
        return any(re.search(p, text) for p in patterns)

    def _is_self_conflict(self, text: str) -> bool:
        """检测自我矛盾"""
        patterns = [
            r"我不是在意.*我只是",
            r"我不是.*我只是",
            r"我不在乎.*其实",
            r"我说不在意.*但是",
        ]
        return any(re.search(p, text) for p in patterns)

    def _is_temporal_conflict(self, text: str) -> bool:
        """检测时序矛盾"""
        patterns = [
            r"我之前觉得.*现在又",
            r"以前.*现在",
            r"之前.*现在",
            r"原来.*现在",
        ]
        return any(re.search(p, text) for p in patterns)

    def get_conflict_response(self, conflict: Conflict) -> str:
        """获取矛盾应答"""
        if conflict.type == ConflictType.WILL:
            return "你想，但又有顾虑。顾虑是什么？"
        elif conflict.type == ConflictType.EMOTION:
            return "爱和恨同时指向同一个人。这种感觉，是什么样的？"
        elif conflict.type == ConflictType.SELF:
            return "你说不在意，但你刚才花了解释这件事。"
        elif conflict.type == ConflictType.TEMPORAL:
            return "之前是这样，现在变了。变了的那部分，是什么带来的？"
        return ""
