"""RDE 多角色关系网 - 关系感知注入与互动统计

交叉影响不直接改好感数字，而是通过 LLM 上下文注入让角色自然表达
（开发文档 6.5）。感知来源：
- 刚结算的跨角色传导（下一轮生效）
- 用户提及了与当前角色有关联的其他角色
"""
from __future__ import annotations

from typing import List, Optional

from .relation_definitions import RelationshipMatrix
from .network_state import NetworkStateStore, PendingTransfer

_PERCEPTION_TEMPLATE = (
    "【角色关系感知】\n"
    "你注意到用户最近和{target}走得很近。你和{target}是{rel_label}关系。\n"
    "虽然你不会直接说什么，但{feeling}。在对话中微妙地表现出这一点（不要太明显）。"
)

_REL_LABELS = {
    "bestie": "闺蜜/兄弟",
    "partner": "搭档",
    "senior_junior": "前辈/后辈",
    "rival_love": "情敌",
    "opponent": "对手",
    "cold": "冷淡",
    "sworn_enemy": "宿敌",
    "stranger": "陌路",
    "none": "无关联",
}

_FEELINGS = {
    "rival_love": "你内心有一点不舒服",
    "sworn_enemy": "你内心涌起敌意",
    "opponent": "你有一种被比下去的不甘",
    "bestie": "你感到安心，把他/她当成自己人",
    "partner": "你感到踏实",
    "senior_junior": "你觉得有他在中间，关系会更好",
}


class PerceptionEngine:
    def __init__(self, matrix: RelationshipMatrix, store: NetworkStateStore,
                 config: Optional[dict] = None) -> None:
        self.matrix = matrix
        self.store = store
        cfg = config or {}
        self.enabled = bool(cfg.get("enable_network", True))

    def generate_perception_context(self, user_id: str, context: Optional[dict] = None) -> str:
        """生成 LLM 关系感知注入；无可感知内容返回空串"""
        if not self.enabled:
            return ""
        ctx = context or {}
        lines: List[str] = []
        current = ctx.get("current_role", "")
        favs: dict = ctx.get("favorabilities", {}) or {}

        # 1) 用户提及了与当前角色有关联的角色
        mentioned = ctx.get("mention_roles", []) or []
        if current:
            for m in mentioned:
                edge = self.matrix.get(current, m)
                if edge is not None and edge.relation_type != "none":
                    lines.append(_PERCEPTION_TEMPLATE.format(
                        target=m,
                        rel_label=_REL_LABELS.get(edge.relation_type, edge.relation_type),
                        feeling=_FEELINGS.get(edge.relation_type, "你的态度有些微妙"),
                    ))

        # 2) 近期传导结算提示（下一轮生效的涟漪）
        settled = ctx.get("recent_settled", []) or []
        for p in settled[:2]:
            if isinstance(p, dict):
                tgt = p.get("target", "")
                amount = p.get("amount", 0.0)
            else:
                tgt = p.target
                amount = p.amount
            rel = self.matrix.get(current, tgt) if current else None
            rel_label = _REL_LABELS.get(rel.relation_type, "关联") if rel else "关联"
            direction = "更亲近" if amount > 0 else "有些疏远"
            lines.append(
                f"（内心涟漪）最近你隐约感觉到，{tgt}对你的态度{direction}了。"
                f"你们之间是{rel_label}关系，你对此有些在意。"
            )
        return "\n".join(lines)

    def get_interaction_stats(self, user_id: str) -> dict:
        """各角色互动频次/好感变化趋势"""
        return self.store.interaction_stats(user_id)
