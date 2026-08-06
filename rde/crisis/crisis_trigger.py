"""RDE 关系危机系统 - 触发引擎

每轮对话调用 check_crisis_trigger(user_id, context)：
- 前置检查：开关 / 未解决危机 / 冷却期
- 概率计算：基础 2% + 修正因子（阶段/好感/冷落/距上次/节日），上限 10%
- 候选池筛选：最低阶段 + 好感下限 + 类型附加条件（冷落次数/轮次/节日/提及他人）
- 随机命中后写入用户危机状态并返回事件
"""
from __future__ import annotations

import random
from typing import Dict, Optional

from .crisis_definitions import CrisisEvent, crises_for_stage
from .crisis_state import CrisisStateStore

DEFAULT_CONFIG = {
    "crisis_trigger_probability": 0.02,  # 基础触发概率
    "crisis_max_probability": 0.10,      # 触发概率上限
    "crisis_min_stage": "s3",            # 全局最低触发阶段
    "crisis_min_cold_penalties": 3,      # 冷落型所需累积次数
    "crisis_min_rounds_secret": 500,     # 秘密型所需总轮次
}

# 阶段修正因子：s6 起递增，s10+ 封顶 2%
_STAGE_PROBABILITY = {6: 0.005, 7: 0.008, 8: 0.011, 9: 0.015, 10: 0.02, 11: 0.02, 12: 0.02}
_HIGH_FAV_BONUS = 0.01          # 好感 >150
_COLD_PENALTY_BONUS = 0.005     # 每次冷落惩罚
_DISTANCE_BONUS_PER_100 = 0.003  # 距上次危机每 100 轮
_SPECIAL_DATE_BONUS = 0.01      # 节日/纪念日


def _stage_rank(stage_id: str) -> int:
    try:
        return int(stage_id[1:]) if stage_id.startswith("s") else 0
    except (IndexError, ValueError):
        return 0


class CrisisTriggerEngine:
    def __init__(self, store: CrisisStateStore,
                 config: Optional[dict] = None, rng: Optional[random.Random] = None) -> None:
        cfg = {**DEFAULT_CONFIG, **(config or {})}
        self.store = store
        self.enabled = bool(cfg.get("enable_crisis_system", True))
        self.base_chance = float(cfg.get("crisis_trigger_probability", 0.02))
        self.max_chance = float(cfg.get("crisis_max_probability", 0.10))
        self.min_stage = str(cfg.get("crisis_min_stage", "s3"))
        self.min_cold = int(cfg.get("crisis_min_cold_penalties", 3))
        self.min_rounds_secret = int(cfg.get("crisis_min_rounds_secret", 500))
        self.rng = rng or random.Random()

    def compute_chance(self, context: dict) -> float:
        """计算本轮触发概率（含修正因子）"""
        stage_id = context.get("stage_id", "s1")
        fav = float(context.get("favorability", 0))
        st = self.store.get(context["user_id"])
        chance = self.base_chance

        rank = _stage_rank(stage_id)
        chance += _STAGE_PROBABILITY.get(rank, 0.0)
        if fav > 150:
            chance += _HIGH_FAV_BONUS
        chance += st.cold_penalties * _COLD_PENALTY_BONUS
        distance = max(0, int(context.get("round", 0)) - st.last_crisis_round)
        chance += (distance // 100) * _DISTANCE_BONUS_PER_100
        if context.get("special_date"):
            chance += _SPECIAL_DATE_BONUS
        return min(self.max_chance, chance)

    def check_crisis_trigger(self, user_id: str, context: dict) -> Optional[CrisisEvent]:
        """每轮对话调用；命中返回事件并写入状态，未命中返回 None"""
        if not self.enabled:
            return None
        ctx = dict(context)
        ctx["user_id"] = user_id

        st = self.store.get(user_id)
        # 本轮回调冷落惩罚增量累计
        if ctx.get("cold_penalty_add"):
            self.store.add_cold_penalty(user_id, int(ctx["cold_penalty_add"]))
        self.store.tick_round(user_id)

        # Step 1 前置检查：有未解决危机 / 冷却期
        if st.active is not None:
            return None
        round_no = int(ctx.get("round", 0))
        if round_no < st.cooldown_until_round:
            return None
        if _stage_rank(str(ctx.get("stage_id", "s1"))) < _stage_rank(self.min_stage):
            return None

        # Step 2/3 概率判定
        if self.rng.random() >= self.compute_chance(ctx):
            return None

        # Step 4 候选池筛选
        stage_id = str(ctx.get("stage_id", "s1"))
        fav = float(ctx.get("favorability", 0))
        candidates = [
            c for c in crises_for_stage(stage_id)
            if fav >= c.favorability_requirement
            and self._type_condition_ok(c, st, ctx)
        ]
        if not candidates:
            # 附加条件事件不满足时，回退到无条件事件池（保证系统可运转）
            candidates = [
                c for c in crises_for_stage(stage_id)
                if fav >= c.favorability_requirement
            ]
        if not candidates:
            return None

        event = self.rng.choice(candidates)
        self.store.set_active(user_id, event, round_no, event.duration_rounds)
        return event

    def _type_condition_ok(self, crisis: CrisisEvent, st, ctx: dict) -> bool:
        """类型附加条件：冷落型/秘密型/外部型/嫉妒型"""
        if crisis.type == "cold" and st.cold_penalties < self.min_cold:
            return False
        if crisis.type == "secret" and st.total_rounds < self.min_rounds_secret:
            return False
        if crisis.type == "external" and not ctx.get("special_date"):
            return False
        if crisis.type == "jealousy" and not ctx.get("mention_other"):
            return False
        return True
