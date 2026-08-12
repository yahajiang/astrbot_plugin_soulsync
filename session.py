"""会话状态管理模块"""

from __future__ import annotations

import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


class SessionMode(Enum):
    """会话模式"""
    OFF = "off"
    GUIDE = "guide"


@dataclass
class UserSession:
    """用户会话"""
    user_id: str

    # ── 模式状态 ──
    mode: SessionMode = SessionMode.OFF

    # ── 对话历史（最近 N 轮）──
    history: List[Tuple[str, str]] = field(default_factory=list)

    # ── 图鉴状态 ──
    guide_key: Optional[str] = None
    guide_round: int = 0
    signals: Dict[str, str] = field(default_factory=dict)

    # ── 时间戳 ──
    last_activity: float = field(default_factory=time.time)

    def add_turn(self, user: str, assistant: str, max_rounds: int = 6):
        """添加一轮对话，保留最近 max_rounds 轮"""
        self.history.append((user, assistant))
        if len(self.history) > max_rounds:
            self.history.pop(0)
        self.last_activity = time.time()

    def is_timeout(self, timeout_seconds: int = 600) -> bool:
        """检查会话是否超时"""
        return time.time() - self.last_activity > timeout_seconds

    def add_signal(self, dim: str, signal: str):
        """添加维度信号"""
        self.signals[dim] = signal

    def get_full_history_text(self) -> str:
        """获取完整对话记录文本（用于轮廓卡生成）"""
        return "\n".join([f"用户：{u}\n镜子：{a}" for u, a in self.history])

    def get_signals_text(self) -> str:
        """获取信号文本"""
        if not self.signals:
            return "暂无"
        return "\n".join([f"● {k}: {v}" for k, v in self.signals.items()])

    def reset(self):
        """重置会话"""
        self.mode = SessionMode.OFF
        self.history.clear()
        self.guide_key = None
        self.guide_round = 0
        self.signals.clear()
        self.last_activity = time.time()

    def activate_guide(self, guide_key: str):
        """激活图鉴模式"""
        self.reset()
        self.mode = SessionMode.GUIDE
        self.guide_key = guide_key
        self.last_activity = time.time()

    def to_dict(self) -> dict:
        """转换为字典（用于持久化，图鉴状态不持久化）"""
        return {
            "user_id": self.user_id,
            "mode": self.mode.value,
            "history": self.history,
            "last_activity": self.last_activity,
        }

    def load_from_dict(self, data: dict):
        """从字典加载"""
        self.user_id = data.get("user_id", self.user_id)
        self.mode = SessionMode(data.get("mode", "off"))
        self.history = data.get("history", [])
        self.last_activity = data.get("last_activity", time.time())


# 兼容性别名
SessionManager = UserSession
SessionState = SessionMode
