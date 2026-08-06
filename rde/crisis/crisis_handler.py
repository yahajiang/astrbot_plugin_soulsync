"""RDE 关系危机系统 - 选择处理

resolve_choice / auto_resolve / generate_crisis_context：
- 应用好感变化（正向受 fav_growth_rate 缩放，负向不变）
- 应用 8 维情感变化
- 阶段倒退（仅危机中、最多 1 级、72h 保护期、触发退行叙事）
- 写入危机历史记录
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .crisis_definitions import CrisisEvent, get_crisis_event
from .crisis_state import CrisisStateStore

DEFAULT_CONFIG = {
    "crisis_protection_hours": 72,   # 阶段倒退保护期
    "fav_growth_rate": 0.5,          # 好感正向增长放缓（对齐主系统配置）
}

_PLACEHOLDER_DEFAULTS = {
    "char_name": "对方",
    "user_name": "你",
    "friend_name": "朋友",
    "secret_hint": "有个小秘密一直藏在我心里",
}


@dataclass
class ResolutionResult:
    crisis_id: str
    choice_id: str
    favorability_delta: float = 0.0        # 已按 fav_growth_rate 缩放
    emotion_deltas: Dict[str, float] = field(default_factory=dict)
    stage_delta: int = 0                    # 已钳制的建议阶段变化（0/±1）
    downgrade_protected: bool = False       # 是否因保护期被阻止倒退
    memory_text: str = ""
    response_text: str = ""
    resolved: bool = True

    def to_dict(self) -> dict:
        return {
            "crisis_id": self.crisis_id,
            "choice_id": self.choice_id,
            "favorability_delta": self.favorability_delta,
            "emotion_deltas": self.emotion_deltas,
            "stage_delta": self.stage_delta,
            "downgrade_protected": self.downgrade_protected,
            "memory_text": self.memory_text,
            "response_text": self.response_text,
            "resolved": self.resolved,
        }


def _fill(template: str, ctx: dict) -> str:
    out = template
    for key, default in _PLACEHOLDER_DEFAULTS.items():
        val = ctx.get(key) or default
        out = out.replace("{" + key + "}", str(val))
    return out


class CrisisHandler:
    def __init__(self, store: CrisisStateStore, config: Optional[dict] = None) -> None:
        cfg = {**DEFAULT_CONFIG, **(config or {})}
        self.store = store
        self.enabled = bool(cfg.get("enable_crisis_system", True))
        self.protection_hours = float(cfg.get("crisis_protection_hours", 72))
        self.fav_growth_rate = float(cfg.get("fav_growth_rate", 0.5))

    def resolve_choice(self, user_id: str, crisis_id: str,
                       choice_id: str, context: Optional[dict] = None) -> Optional[ResolutionResult]:
        """用户做出选择；返回结果（含角色回复），异常输入返回 None"""
        if not self.enabled:
            return None
        st = self.store.get(user_id)
        active = st.active
        if active is None or active.crisis.id != crisis_id:
            return None
        ctx = dict(context or {})
        choice = next((c for c in active.crisis.choices if c.id == choice_id), None)
        if choice is None:
            return None

        # 好感变化：正向按 fav_growth_rate 缩放，负向不变
        fav_delta = choice.favorability_delta
        if fav_delta > 0:
            fav_delta = round(fav_delta * self.fav_growth_rate, 2)

        # 阶段倒退：保护期内钳制为 0
        stage_delta = choice.stage_delta
        downgrade_protected = False
        if stage_delta < 0 and self.store.in_protection(user_id):
            stage_delta = 0
            downgrade_protected = True
        elif stage_delta < 0:
            self.store.set_protection(user_id, self.protection_hours)

        result = ResolutionResult(
            crisis_id=crisis_id,
            choice_id=choice_id,
            favorability_delta=fav_delta,
            emotion_deltas=dict(choice.emotion_deltas),
            stage_delta=stage_delta,
            downgrade_protected=downgrade_protected,
            memory_text=_fill(choice.memory_text, ctx),
            response_text=_fill(choice.response_text, ctx),
        )

        self._record(user_id, active.crisis, result)
        self.store.clear_active(user_id)
        return result

    def auto_resolve(self, user_id: str, context: Optional[dict] = None) -> Optional[ResolutionResult]:
        """超时自动解决（duration_rounds 耗尽）；无待处理危机返回 None"""
        if not self.enabled:
            return None
        st = self.store.get(user_id)
        active = st.active
        if active is None or active.rounds_left > 0:
            return None
        ctx = dict(context or {})
        effect = active.crisis.auto_resolve_effect or {}
        fav_delta = float(effect.get("favorability_delta", -3))
        if fav_delta > 0:
            fav_delta = round(fav_delta * self.fav_growth_rate, 2)
        result = ResolutionResult(
            crisis_id=active.crisis.id,
            choice_id="__auto__",
            favorability_delta=fav_delta,
            emotion_deltas={k: float(v) for k, v in effect.items()
                            if k != "favorability_delta"},
            resolved=True,
            memory_text=_fill(f"没有回应{active.crisis.title}的危机", ctx),
            response_text=_fill(
                f"{active.crisis.title}的事没有得到回应，{active.crisis.narrative.splitlines()[0][:40]}",
                ctx,
            ),
        )
        self._record(user_id, active.crisis, result)
        self.store.clear_active(user_id)
        return result

    def generate_crisis_context(self, user_id: str) -> str:
        """生成注入 LLM 的危机上下文（叙事 + 等待用户选择）"""
        if not self.enabled:
            return ""
        active = self.store.get(user_id).active
        if active is None:
            return ""
        lines = ["【正在进行的关系危机事件】"]
        lines.append(f"{active.crisis.narrative}")
        choice_lines = []
        for i, c in enumerate(active.crisis.choices):
            choice_lines.append(f"  [{c.id.upper()}] {c.text}")
        lines.append("用户需要在对话中回应（选择其一）：\n" + "\n".join(choice_lines))
        lines.append("请在角色回复中自然地承接危机叙事，不要让用户察觉是脚本，等待用户做出选择。")
        return "\n".join(lines)

    def _record(self, user_id: str, crisis: CrisisEvent, result: ResolutionResult) -> None:
        rec = {
            "crisis_id": crisis.id,
            "type": crisis.type,
            "title": crisis.title,
            "choice_id": result.choice_id,
            "favorability_delta": result.favorability_delta,
            "stage_delta": result.stage_delta,
            "resolved_at": time.time(),
        }
        self.store.add_history(user_id, rec)
