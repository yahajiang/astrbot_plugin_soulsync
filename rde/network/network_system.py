"""RDE 多角色关系网 - 系统聚合

对外接口（开发文档 6.8）：
- get_relation(source, target) -> RelationDef | None
- calculate_cross_impact(source, delta, current_round, user_id) -> list[Impact]
- get_network_status(user_id) -> dict
- check_social_event(user_id, context) -> SocialEvent | None
- generate_perception_context(user_id, context) -> str
- get_interaction_stats(user_id) -> dict
- settle_transfers(user_id, current_round) -> list[PendingTransfer]
- record_interaction(user_id, role, current_round, fav_delta)
"""
from __future__ import annotations

from typing import List, Optional

from .relation_definitions import RelationshipMatrix, RelationDef
from .network_state import NetworkStateStore, PendingTransfer
from .cross_impact import CrossImpactEngine, Impact
from .social_events import SocialEventEngine, SocialEvent
from .perception import PerceptionEngine


class NetworkSystem:
    def __init__(self, config: Optional[dict] = None) -> None:
        cfg = dict(config or {})
        self.enabled = bool(cfg.get("enable_network", True))
        self.matrix = RelationshipMatrix(custom=cfg.get("custom_relations"))
        self.store = NetworkStateStore()
        self.impact = CrossImpactEngine(self.matrix, self.store, cfg)
        self.events = SocialEventEngine(self.matrix, cfg)
        self.perception = PerceptionEngine(self.matrix, self.store, cfg)

    # ── 关系查询 ──────────────────────────────────────────

    def get_relation(self, source: str, target: str) -> Optional[RelationDef]:
        return self.matrix.get(source, target)

    def relation_count(self) -> int:
        return self.matrix.count()

    def all_edges(self) -> List[RelationDef]:
        return self.matrix.edges()

    # ── 跨角色传导 ────────────────────────────────────────

    def calculate_cross_impact(self, source: str, delta: float,
                               current_round: int = 0,
                               user_id: str = "") -> List[Impact]:
        if not self.enabled:
            return []
        return self.impact.calculate_cross_impact(source, delta, current_round, user_id)

    def settle_transfers(self, user_id: str, current_round: int) -> List[PendingTransfer]:
        return self.impact.settle_transfers(user_id, current_round)

    # ── 社交事件 ──────────────────────────────────────────

    def check_social_event(self, user_id: str, context: dict) -> Optional[SocialEvent]:
        if not self.enabled:
            return None
        return self.events.check_social_event(user_id, context)

    # ── 感知注入与统计 ────────────────────────────────────

    def generate_perception_context(self, user_id: str,
                                    context: Optional[dict] = None) -> str:
        if not self.enabled:
            return ""
        return self.perception.generate_perception_context(user_id, context)

    def get_interaction_stats(self, user_id: str) -> dict:
        return self.perception.get_interaction_stats(user_id)

    def record_interaction(self, user_id: str, role: str, current_round: int,
                           fav_delta: float = 0.0) -> None:
        if not self.enabled:
            return
        self.store.record_interaction(user_id, role, current_round, fav_delta)

    # ── 状态快照 ──────────────────────────────────────────

    def get_network_status(self, user_id: str) -> dict:
        """当前所有关系定义与用户互动状态"""
        st = self.store.get(user_id)
        return {
            "relation_count": self.matrix.count(),
            "edges": [e.to_dict() for e in self.matrix.edges()],
            "pending_transfers": [p.to_dict() for p in st.pending],
            "interaction_stats": self.store.interaction_stats(user_id),
        }

    def clear_user(self, user_id: str) -> None:
        self.store.clear_user(user_id)
