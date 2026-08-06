"""SoulSync - 个性化训练 Orchestrator 骨架（四模块调度器）"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .trainer_types import PersonaParams, KnowledgeBase, StyleState, PrivateMemoryStore


class PersonalizationOrchestrator:
    """四模块调度器：每轮对话时处理各模块，生成 LLM 注入块"""

    def __init__(self, user_id: str, storage):
        self.user_id = user_id
        self.storage = storage
        self._cached_results: Dict[str, Any] = {}
        self._persona_params: Optional[PersonaParams] = None
        self._knowledge: Optional[KnowledgeBase] = None
        self._style: Optional[StyleState] = None
        self._memory: Optional[PrivateMemoryStore] = None

    # ── 懒加载四子模块 ──
    def get_persona(self) -> PersonaParams:
        if self._persona_params is None:
            data = self.storage.load(self.user_id, "persona.json")
            self._persona_params = PersonaParams.from_dict(data) if data else PersonaParams()
        return self._persona_params

    def get_knowledge(self) -> KnowledgeBase:
        if self._knowledge is None:
            data = self.storage.load(self.user_id, "knowledge.json")
            self._knowledge = KnowledgeBase.from_dict(data) if data else KnowledgeBase()
        return self._knowledge

    def get_style(self) -> StyleState:
        if self._style is None:
            data = self.storage.load(self.user_id, "language_profile.json")
            self._style = StyleState.from_dict(data) if data else StyleState()
        return self._style

    def get_private_memory(self) -> PrivateMemoryStore:
        if self._memory is None:
            data = self.storage.load(self.user_id, "private_memory.json")
            self._memory = PrivateMemoryStore.from_dict(data) if data else PrivateMemoryStore()
        return self._memory

    # ── 每轮对话处理 ──
    def on_each_turn(self, message: str, context: dict) -> None:
        """每轮对话时调用"""
        pass

    # ── 生成 LLM 注入块 ──
    def get_full_injection(self) -> str:
        """生成完整 LLM 注入上下文"""
        return ""

    # ── 记忆写入回调 ──
    def on_memory_write(self, event: dict) -> None:
        """长期记忆写入时回调"""
        pass

    # ── 持久化 ──
    def save_all(self):
        if self._persona_params:
            self.storage.save(self.user_id, "persona.json", self._persona_params.to_dict())
        if self._knowledge:
            self.storage.save(self.user_id, "knowledge.json", self._knowledge.to_dict())
        if self._style:
            self.storage.save(self.user_id, "language_profile.json", self._style.to_dict())
        if self._memory:
            self.storage.save(self.user_id, "private_memory.json", self._memory.to_dict())