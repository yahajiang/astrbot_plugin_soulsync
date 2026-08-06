"""RDE 调度器骨架（Phase A + B）

聚合叙事引擎与危机系统，对外提供统一接口：
- get_stage_config / generate_stage_context / check_transition / get_address / get_stage_description
- check_crisis_trigger / get_active_crisis / resolve_choice / auto_resolve
  / generate_crisis_context / get_cooldown / get_crisis_history

Phase A/B 为纯计算骨架（无持久化）；状态存储与 main.py 接入在 Phase D/E。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .crisis import (
    CrisisEvent,
    CrisisStateStore,
    CrisisTriggerEngine,
    CrisisHandler,
    ResolutionResult,
)
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
    "enable_crisis_system": True,
}


class RDEOrchestrator:
    def __init__(self, config: Optional[dict] = None) -> None:
        cfg = {**DEFAULT_CONFIG, **(config or {})}
        self.enabled = bool(cfg.get("enable_rde", False))
        self.injector = StageInjector(enabled=self.enabled)
        self.address = AddressSystem(enabled=self.enabled)
        self.transition = TransitionHandler(enabled=self.enabled)
        self._recent_transitions: Dict[str, dict] = {}

        # ── 危机系统（Phase B）──
        self.crisis_store = CrisisStateStore()
        crisis_cfg = dict(cfg)
        if not self.enabled:
            crisis_cfg["enable_crisis_system"] = False
        self.crisis_trigger = CrisisTriggerEngine(self.crisis_store, crisis_cfg)
        self.crisis_handler = CrisisHandler(self.crisis_store, crisis_cfg)

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

    # ── 危机系统接口（Phase B）────────────────────────────

    def check_crisis_trigger(self, user_id: str, context: dict) -> Optional[CrisisEvent]:
        """每轮对话调用；命中返回危机事件并写入状态"""
        return self.crisis_trigger.check_crisis_trigger(user_id, context)

    def get_active_crisis(self, user_id: str) -> Optional[CrisisEvent]:
        """获取未解决的危机事件"""
        active = self.crisis_store.get(user_id).active
        return active.crisis if active else None

    def resolve_choice(self, user_id: str, crisis_id: str,
                       choice_id: str, context: Optional[dict] = None) -> Optional[ResolutionResult]:
        """用户做出选择，返回结果（含好感/情感/阶段变化建议与角色回复）"""
        return self.crisis_handler.resolve_choice(user_id, crisis_id, choice_id, context)

    def auto_resolve(self, user_id: str, context: Optional[dict] = None) -> Optional[ResolutionResult]:
        """超时自动解决（在 duration_rounds 内未选择）"""
        return self.crisis_handler.auto_resolve(user_id, context)

    def generate_crisis_context(self, user_id: str) -> str:
        """生成注入 LLM 的危机上下文"""
        return self.crisis_handler.generate_crisis_context(user_id)

    def get_cooldown(self, user_id: str, current_round: Optional[int] = None) -> dict:
        """查询冷却/保护状态"""
        st = self.crisis_store.get(user_id)
        remaining = max(0, st.cooldown_until_round - (current_round or 0))
        return {
            "in_cooldown": st.cooldown_until_round > (current_round or 0),
            "rounds_remaining": remaining,
            "last_crisis_round": st.last_crisis_round,
            "in_protection": st.protection_until_ts > 0,
            "cold_penalties": st.cold_penalties,
            "total_rounds": st.total_rounds,
        }

    def get_crisis_history(self, user_id: str) -> List[dict]:
        """查看过往危机及结果"""
        return list(self.crisis_store.get(user_id).history)

    def add_cold_penalty(self, user_id: str, n: int = 1) -> None:
        """冷落惩罚计数（由外部惩罚系统回调）"""
        self.crisis_store.add_cold_penalty(user_id, n)
