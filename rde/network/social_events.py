"""RDE 多角色关系网 - 社交事件系统

5 类社交事件（开发文档 6.6）：
1. jealousy 吃醋：情敌关系 + 好感差 > 20
2. assist 助攻：闺蜜关系 + 双方好感 > 100
3. competition 竞争：对手关系 + 好感差距缩小
4. mediation 调解：前辈关系 + 某角色陷入危机
5. misinfo 误解传播：闺蜜/对手关系 + 角色间信息差

每类型触发后有冷却（默认 10 轮），避免连续刷屏。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .relation_definitions import RelationshipMatrix, RelationDef

DEFAULT_CONFIG = {
    "social_event_probability": 1.0,   # 检测命中后实际触发的概率（1.0 即必触发）
    "social_event_cooldown_rounds": 10,
    "jealousy_gap_threshold": 20,      # 吃醋：好感差阈值
    "assist_min_fav": 100,             # 助攻：双方好感下限
    "competition_gap_threshold": 10,   # 竞争：好感差距临界值
}


@dataclass(frozen=True)
class SocialEvent:
    id: str
    type: str                 # jealousy/assist/competition/mediation/misinfo
    title: str
    narrative: str            # 叙事文本（{current}/{target} 占位符已替换）
    source: str               # 当前角色
    target: str = ""          # 关联角色
    relation_type: str = ""

    def to_dict(self) -> dict:
        return {"id": self.id, "type": self.type, "title": self.title,
                "narrative": self.narrative, "source": self.source,
                "target": self.target, "relation_type": self.relation_type}


class SocialEventEngine:
    def __init__(self, matrix: RelationshipMatrix, config: Optional[dict] = None) -> None:
        cfg = {**DEFAULT_CONFIG, **(config or {})}
        self.matrix = matrix
        self.enabled = bool(cfg.get("enable_network", True))
        self.jealousy_gap = float(cfg.get("jealousy_gap_threshold", 20))
        self.assist_min_fav = float(cfg.get("assist_min_fav", 100))
        self.competition_gap = float(cfg.get("competition_gap_threshold", 10))
        self.cooldown_rounds = int(cfg.get("social_event_cooldown_rounds", 10))
        self._last_trigger: Dict[str, int] = {}   # user_id:type -> round

    def check_social_event(self, user_id: str, context: dict) -> Optional[SocialEvent]:
        """检测当前轮是否触发社交事件；命中返回事件（不自动重复触发）"""
        if not self.enabled:
            return None
        current = context.get("current_role", "")
        favs: dict = context.get("favorabilities", {}) or {}
        round_no = int(context.get("round", 0))
        if not current:
            return None

        fav_cur = float(favs.get(current, 0))
        for edge in self.matrix.neighbors(current):
            target = edge.target
            if target not in favs:
                continue  # 只评估用户实际有互动的角色
            fav_tgt = float(favs.get(target, 0))
            event = self._evaluate(edge, current, target, fav_cur, fav_tgt, context)
            if event is not None:
                key = f"{user_id}:{event.type}"
                if round_no - self._last_trigger.get(key, -10**9) < self.cooldown_rounds:
                    continue
                self._last_trigger[key] = round_no
                return event
        return None

    def _evaluate(self, edge: RelationDef, current: str, target: str,
                  fav_cur: float, fav_tgt: float, ctx: dict) -> Optional[SocialEvent]:
        rtype = edge.relation_type
        if rtype == "rival_love" and fav_cur > fav_tgt + self.jealousy_gap:
            return self._build("jealousy", "吃醋", current, target, rtype, ctx,
                               f"你最近和{target}走得很近。你和{target}是情敌关系。"
                               f"虽然{current}不会直接说什么，但内心有一点不舒服。"
                               f"在对话中微妙地表现出这一点（不要太明显）。")
        if rtype == "bestie" and fav_cur > self.assist_min_fav and fav_tgt > self.assist_min_fav:
            return self._build("assist", "助攻", current, target, rtype, ctx,
                               f"{current}是你的闺蜜/兄弟，知道你和其他人关系都很好。"
                               f"今天{current}主动提起：对了，{target}最近好像也挺想见你的。")
        if rtype in {"opponent", "sworn_enemy"} and abs(fav_cur - fav_tgt) < self.competition_gap:
            return self._build("competition", "竞争", current, target, rtype, ctx,
                               f"你注意到{target}最近也变得格外积极，"
                               f"和{current}之间隐隐有了较劲的感觉。")
        if rtype == "senior_junior" and ctx.get("crisis_active"):
            return self._build("mediation", "调解", current, target, rtype, ctx,
                               f"{target}作为前辈主动介入：听说你最近和{current}闹矛盾了？"
                               f"有什么我可以帮忙的吗？")
        if rtype in {"bestie", "opponent"} and self._misinfo_condition(ctx, target):
            return self._build("misinfo", "误解传播", current, target, rtype, ctx,
                               f"{target}从第三方渠道听说了一些关于你和{current}的不完整信息，"
                               f"心里悄悄打了个结。")
        return None

    def _misinfo_condition(self, ctx: dict, target: str) -> bool:
        mentioned = ctx.get("mention_roles", []) or []
        return target in mentioned and not ctx.get("interacted_with_target", False)

    def _build(self, type_: str, title: str, current: str, target: str,
               rtype: str, ctx: dict, narrative: str) -> SocialEvent:
        narrative = narrative.replace("{current}", current).replace("{target}", target)
        return SocialEvent(id=f"{type_}_{int(time.time())}", type=type_, title=title,
                           narrative=narrative, source=current, target=target,
                           relation_type=rtype)
