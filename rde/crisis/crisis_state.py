"""RDE 关系危机系统 - 每用户危机状态存储（内存态）

状态内容：未解决危机 / 冷却轮次 / 阶段倒退保护期 / 危机历史 / 冷落惩罚计数 / 总轮次。
Phase D 将接入持久化（data/rde/），当前为进程内存储。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .crisis_definitions import CrisisEvent


@dataclass
class ActiveCrisis:
    crisis: CrisisEvent
    started_round: int = 0          # 触发时的轮次
    rounds_left: int = 3            # 剩余选择期限轮数
    injected: bool = False          # 是否已注入对话

    def to_dict(self) -> dict:
        return {
            "crisis_id": self.crisis.id,
            "type": self.crisis.type,
            "title": self.crisis.title,
            "started_round": self.started_round,
            "rounds_left": self.rounds_left,
        }


@dataclass
class UserCrisisState:
    active: Optional[ActiveCrisis] = None
    cooldown_until_round: int = 0   # 该轮次之前不触发新危机
    protection_until_ts: float = 0.0  # 阶段倒退保护期（72h）
    last_crisis_round: int = 0      # 上次危机触发轮次（概率递增修正用）
    cold_penalties: int = 0         # 冷落惩罚累积次数（触发冷落型条件）
    total_rounds: int = 0           # 总互动轮次（触发秘密型条件）
    history: List[dict] = field(default_factory=list)  # 危机历史记录


class CrisisStateStore:
    """每用户危机状态（线程安全：GIL 内字典操作）"""

    def __init__(self) -> None:
        self._states: Dict[str, UserCrisisState] = {}

    def get(self, user_id: str) -> UserCrisisState:
        st = self._states.get(user_id)
        if st is None:
            st = UserCrisisState()
            self._states[user_id] = st
        return st

    def set_active(self, user_id: str, crisis: CrisisEvent,
                   current_round: int, rounds_left: int) -> None:
        st = self.get(user_id)
        st.active = ActiveCrisis(crisis, started_round=current_round,
                                 rounds_left=rounds_left)
        st.last_crisis_round = current_round
        st.cooldown_until_round = current_round + crisis.cooldown_rounds

    def clear_active(self, user_id: str) -> None:
        st = self.get(user_id)
        st.active = None

    def set_protection(self, user_id: str, hours: float) -> None:
        self.get(user_id).protection_until_ts = time.time() + hours * 3600

    def in_protection(self, user_id: str) -> bool:
        return time.time() < self.get(user_id).protection_until_ts

    def add_cold_penalty(self, user_id: str, n: int = 1) -> None:
        self.get(user_id).cold_penalties += n

    def tick_round(self, user_id: str, rounds: int = 1) -> None:
        st = self.get(user_id)
        st.total_rounds += rounds
        if st.active is not None:
            st.active.rounds_left -= rounds

    def add_history(self, user_id: str, record: dict) -> None:
        st = self.get(user_id)
        st.history.append(record)
        if len(st.history) > 50:
            st.history = st.history[-50:]

    def clear_user(self, user_id: str) -> None:
        self._states.pop(user_id, None)

    def export_state(self, user_id: str) -> dict:
        """导出可落盘状态（ActiveCrisis 以 crisis_id 引用）"""
        st = self._states.get(user_id)
        if st is None:
            return {}
        active = None
        if st.active is not None:
            active = {
                "crisis_id": st.active.crisis.id,
                "started_round": st.active.started_round,
                "rounds_left": st.active.rounds_left,
                "injected": st.active.injected,
            }
        return {
            "active": active,
            "cooldown_until_round": st.cooldown_until_round,
            "protection_until_ts": st.protection_until_ts,
            "last_crisis_round": st.last_crisis_round,
            "cold_penalties": st.cold_penalties,
            "total_rounds": st.total_rounds,
            "history": list(st.history),
        }

    def import_state(self, user_id: str, data: dict,
                     get_crisis=None) -> None:
        """从导出的 dict 恢复状态；get_crisis(crisis_id) 用于还原 CrisisEvent"""
        if not data:
            return
        st = self.get(user_id)
        active_data = data.get("active")
        if active_data and get_crisis is not None:
            crisis = get_crisis(active_data.get("crisis_id"))
            if crisis is not None:
                st.active = ActiveCrisis(
                    crisis,
                    started_round=int(active_data.get("started_round", 0)),
                    rounds_left=int(active_data.get("rounds_left", 1)),
                    injected=bool(active_data.get("injected", False)),
                )
        st.cooldown_until_round = int(data.get("cooldown_until_round", 0))
        st.protection_until_ts = float(data.get("protection_until_ts", 0.0))
        st.last_crisis_round = int(data.get("last_crisis_round", 0))
        st.cold_penalties = int(data.get("cold_penalties", 0))
        st.total_rounds = int(data.get("total_rounds", 0))
        hist = data.get("history") or []
        st.history = [h for h in hist if isinstance(h, dict)][-50:]

    def snapshot(self) -> dict:
        return {uid: state.__dict__ for uid, state in self._states.items()}
