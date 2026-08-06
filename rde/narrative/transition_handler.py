"""RDE 阶段跃迁/退行处理

阶段变化（升级/降级）时生成叙事事件：
- 正向跃迁：角色内心独白式微妙变化（目标阶段的 transition_trigger）
- 退行（含负向）："最近感觉我们之间好像少了点什么"式降温叙事
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from .stage_definitions import (
    STAGE_DEFINITIONS,
    get_stage_definition,
    stage_id_from_index,
)

_UPGRADE_NARRATIVE = (
    "你们的关系跨过了新的界限——{old}的余温尚在，{new}的气息已然浮现。"
)
_DOWNGRADE_NARRATIVE = (
    "最近感觉我们之间好像少了点什么……{new}的气息悄然弥漫，曾经{old}的温度正在褪去。"
)


@dataclass
class TransitionEvent:
    old_stage: str                     # 旧 stage_id
    new_stage: str                     # 新 stage_id
    kind: str                          # "upgrade" / "downgrade"
    narrative_lines: List[str] = field(default_factory=list)
    triggered_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "old_stage": self.old_stage,
            "new_stage": self.new_stage,
            "kind": self.kind,
            "narrative": "\n".join(self.narrative_lines),
            "triggered_at": self.triggered_at,
        }


def _positive_rank(stage_id: str) -> Optional[int]:
    """正向阶段排名：s1→0 ... s12→11；负向/未知返回 None"""
    if not stage_id.startswith("s"):
        return None
    try:
        idx = int(stage_id[1:])
    except ValueError:
        return None
    if 1 <= idx <= 12:
        return idx - 1
    return None


class TransitionHandler:
    """跃迁/退行判定与叙事生成（无状态，线程安全）"""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def check_transition(
        self,
        old_stage: str,
        new_stage: str,
        via_index: Optional[int] = None,
        negative_stage: Optional[str] = None,
    ) -> Optional[TransitionEvent]:
        """比较新旧阶段，阶段变化时返回 TransitionEvent，无变化返回 None

        支持两种输入：
        1) stage_id 对（s1~s12 / n1~n4）
        2) 由 via_index + negative_stage 推导新阶段（emotion_engine 视角）
        """
        if not self.enabled:
            return None
        if old_stage == new_stage:
            return None
        if via_index is not None:
            new_stage = stage_id_from_index(via_index, negative_stage)
            if old_stage == new_stage:
                return None

        old_def = get_stage_definition(old_stage)
        new_def = get_stage_definition(new_stage)
        old_name = old_def.stage_name if old_def else old_stage
        new_name = new_def.stage_name if new_def else new_stage

        old_rank = _positive_rank(old_stage)
        new_rank = _positive_rank(new_stage)

        if old_rank is not None and new_rank is not None:
            kind = "upgrade" if new_rank > old_rank else "downgrade"
        elif old_def and new_def and old_def.positive and not new_def.positive:
            kind = "downgrade"
        elif not old_def.positive and new_def.positive:
            kind = "upgrade"
        elif old_def and new_def and not old_def.positive and not new_def.positive:
            old_idx = int(old_stage[1:]) if old_stage.startswith("n") else 0
            new_idx = int(new_stage[1:]) if new_stage.startswith("n") else 0
            kind = "downgrade" if new_idx > old_idx else "upgrade"
        else:
            kind = "upgrade"

        trigger = new_def.transition_trigger if new_def else ""
        if kind == "upgrade":
            narrative = _UPGRADE_NARRATIVE.format(old=old_name, new=new_name)
        else:
            narrative = _DOWNGRADE_NARRATIVE.format(old=old_name, new=new_name)
        lines = [narrative]
        if trigger:
            lines.append(trigger)
        return TransitionEvent(old_stage, new_stage, kind, lines)

    def build_transition_narrative(self, event: TransitionEvent) -> str:
        """将事件转为可注入的叙事文本"""
        return "\n".join(event.narrative_lines)
