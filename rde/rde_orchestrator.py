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
    get_crisis_event,
)
from .network import NetworkSystem, RelationDef, Impact, SocialEvent, PendingTransfer
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
        self._last_stage: Dict[str, str] = {}

        # ── 危机系统（Phase B）──
        self.crisis_store = CrisisStateStore()
        crisis_cfg = dict(cfg)
        if not self.enabled:
            crisis_cfg["enable_crisis_system"] = False
        self.crisis_trigger = CrisisTriggerEngine(self.crisis_store, crisis_cfg)
        self.crisis_handler = CrisisHandler(self.crisis_store, crisis_cfg)

        # ── 多角色关系网（Phase C）──
        network_cfg = dict(cfg)
        if not self.enabled:
            network_cfg["enable_network"] = False
        self.network = NetworkSystem(network_cfg)

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

    # ── 每轮完整处理流程（Phase D）─────────────────────────

    def process_message(self, user_id: str, context: dict) -> dict:
        """每轮对话完整处理流程（Step 1-6），供 main.py 每轮调用。

        context 键：
          round: int            本轮对话序号
          stage_id: str         当前 RDE 阶段（s1-s12 / n1-n4，由 stage_index 映射）
          favorability: float   当前好感度
          fav_delta: float      本轮好感变化（跨角色传导的源增量）
          cold_penalty_add: int 本轮冷落惩罚增量（默认 0）
          special_date: bool    本轮是否节日/纪念日
          mention_other: bool   本轮用户是否提及他人
          user_name / char_name / friend_name: str  叙事占位符
          current_role: str     当前关系角色 key（社交事件用）
          source_role: str      好感变化源角色名（跨角色传导用，通常=current_role）
          favorabilities: dict  各角色好感（社交事件用）

        返回 dict：
          stage_id: str 处理后的阶段
          context_text: str 拼接后的注入文本（为空则无需注入）
          stage_ctx / crisis_ctx / perception_ctx: str 三段注入
          crisis_triggered: Optional[CrisisEvent] 新触发的危机
          crisis_resolved: Optional[ResolutionResult] 自动解决的危机
          transition: Optional[TransitionEvent] 阶段跃迁事件
          impacts: List[Impact] 跨角色影响（延迟队列）
          settled: List[PendingTransfer] 本轮到账的传导
          social_event: Optional[SocialEvent] 触发的关系网社交事件
        """
        ctx = dict(context)
        ctx["user_id"] = user_id
        round_no = int(ctx.get("round", 0))
        stage_id = str(ctx.get("stage_id", "s1"))
        fav_delta = float(ctx.get("fav_delta", 0) or 0)

        crisis_triggered = None
        crisis_resolved = None

        # Step 2 危机检测：先处理超期未决（自动解决），再推进轮次并尝试触发新危机
        st = self.crisis_store.get(user_id)
        if st.active is not None and st.active.rounds_left <= 0:
            crisis_resolved = self.auto_resolve(user_id, ctx)
        # check_crisis_trigger 内部每轮 tick（递减期限/累计轮次）；
        # 有未决危机时只推进不触发（内置前置检查）
        crisis_triggered = self.check_crisis_trigger(user_id, ctx)

        # Step 3 多角色交叉影响：源角色好感变化传导（延迟一轮到账）
        impacts: List[Impact] = []
        settled: List[PendingTransfer] = []
        source_role = str(ctx.get("source_role", "") or "")
        if fav_delta and source_role:
            impacts = self.calculate_cross_impact(source_role, fav_delta, round_no, user_id)
        settled = self.settle_transfers(user_id, round_no)

        # Step 4 阶段跃迁事件（主系统已应用新阶段，此处判定叙事）
        transition = None
        last_stage = self._last_stage.get(user_id)
        if last_stage is not None and last_stage != stage_id:
            transition = self.check_transition(last_stage, stage_id)
        self._last_stage[user_id] = stage_id

        # Step 5 上下文生成（阶段叙事 + 危机叙事 + 关系网感知）
        ctx["crisis_active"] = st.active is not None
        stage_ctx = self.generate_stage_context(
            stage_id, {"user_name": ctx.get("user_name")}
        )
        crisis_ctx = self.generate_crisis_context(user_id)
        perc_ctx = dict(ctx)
        perc_ctx["recent_settled"] = settled
        perception_ctx = self.generate_perception_context(user_id, perc_ctx)
        social_event = self.check_social_event(user_id, ctx)

        parts = [p for p in (stage_ctx, crisis_ctx, perception_ctx) if p]
        context_text = "\n\n".join(parts)

        return {
            "stage_id": stage_id,
            "context_text": context_text,
            "stage_ctx": stage_ctx,
            "crisis_ctx": crisis_ctx,
            "perception_ctx": perception_ctx,
            "crisis_triggered": crisis_triggered,
            "crisis_resolved": crisis_resolved,
            "transition": transition,
            "impacts": impacts,
            "settled": settled,
            "social_event": social_event,
        }

    # ── 工具 ────────────────────────────────────────────────

    def all_stages(self) -> list:
        return STAGE_DEFINITIONS

    def save_state(self, user_id: str) -> dict:
        """导出单用户 RDE 状态（危机/关系网/跃迁缓存），供落盘"""
        return {
            "crisis": self.crisis_store.export_state(user_id),
            "network": self.network.store.export_state(user_id),
            "last_stage": self._last_stage.get(user_id),
            "recent_transitions": dict(self._recent_transitions),
        }

    def load_state(self, user_id: str, data: Optional[dict]) -> None:
        """从导出的 dict 恢复单用户 RDE 状态"""
        if not data:
            return
        self.crisis_store.import_state(
            user_id, data.get("crisis") or {}, get_crisis=get_crisis_event
        )
        self.network.store.import_state(user_id, data.get("network") or {})
        last_stage = data.get("last_stage")
        if isinstance(last_stage, str):
            self._last_stage[user_id] = last_stage
        recent = data.get("recent_transitions")
        if isinstance(recent, dict):
            self._recent_transitions.update(
                {k: v for k, v in recent.items() if isinstance(v, dict)}
            )

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

    # ── 多角色关系网接口（Phase C）────────────────────────

    def get_relation(self, source: str, target: str) -> Optional[RelationDef]:
        """查询两角色间的关系定义"""
        return self.network.get_relation(source, target)

    def calculate_cross_impact(self, source: str, delta: float,
                               current_round: int = 0,
                               user_id: str = "") -> List[Impact]:
        """计算好感变化的跨角色影响（延迟传导入队）"""
        return self.network.calculate_cross_impact(source, delta, current_round, user_id)

    def settle_transfers(self, user_id: str, current_round: int) -> List[PendingTransfer]:
        """结算到期传导（下一轮生效）"""
        return self.network.settle_transfers(user_id, current_round)

    def check_social_event(self, user_id: str, context: dict) -> Optional[SocialEvent]:
        """检测社交事件（吃醋/助攻/竞争/调解/误解传播）"""
        return self.network.check_social_event(user_id, context)

    def generate_perception_context(self, user_id: str,
                                    context: Optional[dict] = None) -> str:
        """生成 LLM 关系感知注入"""
        return self.network.generate_perception_context(user_id, context)

    def get_interaction_stats(self, user_id: str) -> dict:
        """各角色互动频次/好感变化趋势"""
        return self.network.get_interaction_stats(user_id)

    def record_interaction(self, user_id: str, role: str, current_round: int,
                           fav_delta: float = 0.0) -> None:
        """记录与某角色的互动（统计用）"""
        self.network.record_interaction(user_id, role, current_round, fav_delta)

    def get_network_status(self, user_id: str) -> dict:
        """关系网整体状态（关系对/待结算传导/互动统计）"""
        return self.network.get_network_status(user_id)
