"""RDE 多角色关系网 - 跨角色好感传导

calculate_cross_impact(source, delta, current_round)：
- 遍历与 source 有关联的所有角色 Bi
- ΔBi = ΔA × coefficient（正向/负向可不对称）
- 传导有延迟：加入队列，下一轮生效（settle 时返回）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .relation_definitions import RelationshipMatrix, RelationDef
from .network_state import NetworkStateStore, PendingTransfer


@dataclass
class Impact:
    target: str
    delta: float                    # 传导量（未舍入）
    relation_type: str
    source: str = ""
    relation: Optional[RelationDef] = None

    def to_dict(self) -> dict:
        return {"target": self.target, "delta": round(self.delta, 3),
                "relation_type": self.relation_type, "source": self.source}


class CrossImpactEngine:
    """跨角色好感传导（ΔBi = ΔA × coeff，带延迟）"""

    def __init__(self, matrix: RelationshipMatrix, store: NetworkStateStore,
                 config: Optional[dict] = None) -> None:
        self.matrix = matrix
        self.store = store
        cfg = config or {}
        self.enabled = bool(cfg.get("enable_network", True))
        self.transmission_delay = int(cfg.get("network_transmission_delay_turns", 1))

    def calculate_cross_impact(self, source: str, delta: float,
                               current_round: int = 0,
                               user_id: str = "") -> List[Impact]:
        """计算好感变化的跨角色影响（并排队延迟传导）"""
        if not self.enabled or delta == 0:
            return []
        impacts: List[Impact] = []
        for edge in self.matrix.neighbors(source):
            coeff = edge.coefficient_for(delta)
            if coeff == 0:
                continue
            amount = delta * coeff
            impacts.append(Impact(target=edge.target, delta=amount,
                                  relation_type=edge.relation_type,
                                  source=source, relation=edge))
            if user_id:
                self.store.queue_transfer(
                    user_id, edge.target, amount,
                    current_round + self.transmission_delay, source=source)
        return impacts

    def settle_transfers(self, user_id: str, current_round: int) -> List[PendingTransfer]:
        """结算到期传导（下一轮生效），返回生效列表"""
        return self.store.settle_due(user_id, current_round)
