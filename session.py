"""会话状态管理模块"""

from __future__ import annotations

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional


class SessionState(Enum):
    """会话状态"""
    IDLE = "idle"
    DECLARATION = "declaration"
    ICEBREAKER_FIXED = "icebreaker_fixed"
    ICEBREAKER_RANDOM = "icebreaker_random"
    MIRROR_MODE = "mirror_mode"
    SUSPENDED = "suspended"


@dataclass
class DialogueEntry:
    """对话条目"""
    user_input: str
    mirror_response: str
    timestamp: float
    sharpness_level: int
    reflection_type: str
    mirror_type: str


@dataclass
class UserSession:
    """用户会话"""
    user_id: str
    state: SessionState = SessionState.IDLE
    nickname: str = ""

    # ── 破冰数据 ──
    icebreaker_stage: int = 0  # 0-5: 固定三问0-2, 随机三问3-5
    icebreaker_answers: Dict[int, str] = field(default_factory=dict)
    icebreaker_random_questions: List[str] = field(default_factory=list)

    # ── 对话数据 ──
    dialogue_history: List[DialogueEntry] = field(default_factory=list)
    current_round: int = 0

    # ── 锐度数据 ──
    current_sharpness: int = 2
    sharpness_consecutive_rise: int = 0
    sharpness_last_change: float = 0.0

    # ── 修正数据 ──
    correction_count: int = 0
    last_correction_time: float = 0.0

    # ── 重复词数据 ──
    word_frequency: Dict[str, int] = field(default_factory=dict)
    repeat_warnings: List[str] = field(default_factory=list)

    # ── 矛盾数据 ──
    conflicts: List[dict] = field(default_factory=list)

    # ── 金句数据 ──
    saved_quotes: List[str] = field(default_factory=list)

    # ── 时间戳 ──
    last_input_time: float = field(default_factory=time.time)
    session_start_time: float = field(default_factory=time.time)

    def reset(self):
        """重置会话"""
        self.state = SessionState.DECLARATION
        self.nickname = ""
        self.icebreaker_stage = 0
        self.icebreaker_answers.clear()
        self.icebreaker_random_questions.clear()
        self.dialogue_history.clear()
        self.current_round = 0
        self.current_sharpness = 2
        self.sharpness_consecutive升 = 0
        self.correction_count = 0
        self.word_frequency.clear()
        self.repeat_warnings.clear()
        self.conflicts.clear()
        self.last_input_time = time.time()
        self.session_start_time = time.time()

    def add_dialogue(self, entry: DialogueEntry):
        """添加对话条目"""
        self.dialogue_history.append(entry)
        self.current_round += 1
        self.last_input_time = time.time()

    def update_word_frequency(self, words: List[str]):
        """更新词频"""
        for word in words:
            self.word_frequency[word] = self.word_frequency.get(word, 0) + 1

    def get_recent_words(self, n: int = 5) -> List[str]:
        """获取最近n轮的词"""
        recent_words = []
        for entry in self.dialogue_history[-n:]:
            words = entry.user_input.split()
            recent_words.extend(words)
        return recent_words

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "state": self.state.value,
            "nickname": self.nickname,
            "icebreaker_stage": self.icebreaker_stage,
            "icebreaker_answers": self.icebreaker_answers,
            "current_round": self.current_round,
            "current_sharpness": self.current_sharpness,
            "word_frequency": self.word_frequency,
            "saved_quotes": self.saved_quotes,
            "dialogue_history": [
                {
                    "user_input": e.user_input,
                    "mirror_response": e.mirror_response,
                    "timestamp": e.timestamp,
                    "sharpness_level": e.sharpness_level,
                    "reflection_type": e.reflection_type,
                    "mirror_type": e.mirror_type,
                }
                for e in self.dialogue_history
            ],
        }

    def load_from_dict(self, data: dict):
        """从字典加载"""
        self.user_id = data.get("user_id", self.user_id)
        self.state = SessionState(data.get("state", "idle"))
        self.nickname = data.get("nickname", "")
        self.icebreaker_stage = data.get("icebreaker_stage", 0)
        self.icebreaker_answers = data.get("icebreaker_answers", {})
        self.current_round = data.get("current_round", 0)
        self.current_sharpness = data.get("current_sharpness", 2)
        self.word_frequency = data.get("word_frequency", {})
        self.saved_quotes = data.get("saved_quotes", [])

        for entry_data in data.get("dialogue_history", []):
            entry = DialogueEntry(
                user_input=entry_data["user_input"],
                mirror_response=entry_data["mirror_response"],
                timestamp=entry_data["timestamp"],
                sharpness_level=entry_data["sharpness_level"],
                reflection_type=entry_data["reflection_type"],
                mirror_type=entry_data["mirror_type"],
            )
            self.dialogue_history.append(entry)


# 兼容性别名
SessionManager = UserSession
