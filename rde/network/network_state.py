"""RDE 多角色关系网 - 网络状态存储

- 延迟传导队列：跨角色好感变化按轮次延迟生效（下一轮对话才体现）
- 互动统计：各角色互动频次 / 最近互动轮次 / 好感变化趋势
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PendingTransfer:
    target: str          # 受影响角色
    amount: float        # ΔBi = ΔA × coeff（传导量）
    ready_round: int     # 生效轮次（下一轮）
    source: str = ""

    def to_dict(self) -> dict:
        return {"target": self.target, "amount": self.amount,
                "ready_round": self.ready_round, "source": self.source}


@dataclass
class InteractionStat:
    count: int = 0
    last_round: int = 0
    fav_delta_total: float = 0.0   # 累计好感变化
    fav_delta_last: float = 0.0    # 最近一次变化


@dataclass
class UserNetworkState:
    pending: List[PendingTransfer] = field(default_factory=list)
    stats: Dict[str, InteractionStat] = field(default_factory=dict)


class NetworkStateStore:
    def __init__(self) -> None:
        self._states: Dict[str, UserNetworkState] = {}

    def get(self, user_id: str) -> UserNetworkState:
        st = self._states.get(user_id)
        if st is None:
            st = UserNetworkState()
            self._states[user_id] = st
        return st

    def queue_transfer(self, user_id: str, target: str, amount: float,
                       ready_round: int, source: str = "") -> None:
        """排队一条延迟传导（若同轮同目标已存在则累加）"""
        st = self.get(user_id)
        for p in st.pending:
            if p.target == target and p.ready_round == ready_round:
                p.amount += amount
                return
        st.pending.append(PendingTransfer(target=target, amount=amount,
                                          ready_round=ready_round, source=source))

    def settle_due(self, user_id: str, current_round: int) -> List[PendingTransfer]:
        """结算所有 ready_round <= current_round 的传导，返回列表并移除"""
        st = self.get(user_id)
        due = [p for p in st.pending if p.ready_round <= current_round]
        st.pending = [p for p in st.pending if p.ready_round > current_round]
        return due

    def record_interaction(self, user_id: str, role: str, current_round: int,
                           fav_delta: float = 0.0) -> None:
        st = self.get(user_id)
        s = st.stats.get(role)
        if s is None:
            s = InteractionStat()
            st.stats[role] = s
        s.count += 1
        s.last_round = current_round
        if fav_delta:
            s.fav_delta_total += fav_delta
            s.fav_delta_last = fav_delta

    def interaction_stats(self, user_id: str) -> dict:
        st = self.get(user_id)
        return {
            role: {
                "count": s.count,
                "last_round": s.last_round,
                "fav_delta_total": round(s.fav_delta_total, 2),
                "fav_delta_last": round(s.fav_delta_last, 2),
            }
            for role, s in st.stats.items()
        }

    def clear_user(self, user_id: str) -> None:
        self._states.pop(user_id, None)

    def export_state(self, user_id: str) -> dict:
        """导出可落盘状态（pending/stats 纯 dict）"""
        st = self._states.get(user_id)
        if st is None:
            return {}
        return {
            "pending": [p.to_dict() for p in st.pending],
            "stats": self.interaction_stats(user_id),
        }

    def import_state(self, user_id: str, data: dict) -> None:
        if not data:
            return
        st = self.get(user_id)
        st.pending = []
        for p in (data.get("pending") or []):
            if isinstance(p, dict):
                st.pending.append(PendingTransfer(
                    target=str(p.get("target", "")),
                    amount=float(p.get("amount", 0.0)),
                    ready_round=int(p.get("ready_round", 0)),
                    source=str(p.get("source", "")),
                ))
        for role, s in (data.get("stats") or {}).items():
            if isinstance(s, dict):
                st.stats[str(role)] = InteractionStat(
                    count=int(s.get("count", 0)),
                    last_round=int(s.get("last_round", 0)),
                    fav_delta_total=float(s.get("fav_delta_total", 0.0)),
                    fav_delta_last=float(s.get("fav_delta_last", 0.0)),
                )
