"""RDE 调度器骨架（Phase A）

聚合叙事引擎三个子组件，对外提供统一接口：
- get_stage_config(stage_id) -> StageDefinition
- generate_stage_context(stage_id, context) -> str
- check_transition(old_stage, new_stage) -> TransitionEvent | None
- get_address(stage_id, context) -> str
- get_stage_description(stage_id) -> str

Phase A 为纯计算骨架（无持久化）；状态存储与 main.py 接入在 Phase D/E。
"""
from __future__ import annotations

from typing import Dict, Optional

from .narrative.address_system import AddressSystem
from .narrative.stage_definitions import (
    StageDefinition,
    STAGE_DEFINITIONS,
    get_stage_definition,
    stage_id_from_index,
)
from .narrative.stage_injector import StageInjector
from .narrative.transition_handler import TransitionEvent, TransitionHandler

DEFAULT_CONFIG = {
    "enable_rde": False,
}


class RDEOrchestrator:
    def __init__(self, config: Optional[dict] = None) -> None:
        cfg = {**DEFAULT_CONFIG, **(config or {})}
        self.enabled = bool(cfg.get("enable_rde", False))
        self.injector = StageInjector(enabled=self.enabled)
        self.address = AddressSystem(enabled=self.enabled)
        self.transition = TransitionHandler(enabled=self.enabled)
        self._recent_transitions: Dict[str, dict] = {}

    # ── 对外接口 ─────────────────────────────────────────────

    def get_stage_config(self, stage_id: str) -> Optional[StageDefinition]:
        return get_stage_definition(stage_id)

    def get_stage_description(self, stage_id: str) -> str:
        return self.injector.get_stage_description(stage_id)

    def generate_stage_context(
        self,
        stage_id: str,
        context: Optional[dict] = None,
    ) -> str:
        """生成注入 LLM 的阶段叙事上下文；context 可含 user_name"""
        ctx = context or {}
        recent = self._recent_transitions.get(stage_id)
        return self.injector.generate_stage_context(
            stage_id,
            user_name=ctx.get("user_name"),
            recent_transition=recent,
        )

    def check_transition(
        self,
        old_stage: str,
        new_stage: str,
    ) -> Optional[TransitionEvent]:
        event = self.transition.check_transition(old_stage, new_stage)
        if event is not None:
            self._recent_transitions[event.new_stage] = event.to_dict()
        return event

    def check_transition_by_index(
        self,
        old_stage: str,
        stage_index: int,
        negative_stage: Optional[str] = None,
    ) -> Optional[TransitionEvent]:
        """emotion_engine 视角入口：索引+负阶段 → stage_id → 判定"""
        new_stage = stage_id_from_index(stage_index, negative_stage)
        return self.check_transition(old_stage, new_stage)

    def get_address(self, stage_id: str, context: Optional[dict] = None) -> str:
        return self.address.get_address(stage_id, context)

    # ── 工具 ────────────────────────────────────────────────

    def all_stages(self) -> list:
        return STAGE_DEFINITIONS

    def clear_recent_transitions(self) -> None:
        self._recent_transitions.clear()

    def recent_transition_for(self, stage_id: str) -> Optional[dict]:
        return self._recent_transitions.get(stage_id)
