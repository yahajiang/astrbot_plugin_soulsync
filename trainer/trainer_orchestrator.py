"""SoulSync - 个性化训练 Orchestrator（四模块调度器）"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from .trainer_types import PersonaParams, KnowledgeBase, StyleState, PrivateMemoryStore
from .trainer_storage import TrainerStorage
from .persona.persona_modifier import PersonaModifier
from .persona.persona_trainer import PersonaTrainer
from .persona.persona_stability import PersonaStability
from .persona.persona_injector import PersonaInjector


class PersonalizationOrchestrator:
    def __init__(self, user_id: str, storage: TrainerStorage):
        self.user_id = user_id
        self.storage = storage
        self._cached_results: Dict[str, Any] = {}
        self._persona_params: Optional[PersonaParams] = None
        self._knowledge: Optional[KnowledgeBase] = None
        self._style: Optional[StyleState] = None
        self._memory: Optional[PrivateMemoryStore] = None
        self._modifier = PersonaModifier(storage, user_id)
        self._trainer = PersonaTrainer(self._modifier)
        self._stability = PersonaStability()
        self._injector = PersonaInjector()

    def get_persona(self) -> PersonaParams:
        if self._persona_params is None:
            self._persona_params = self._modifier.get()
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

    def on_each_turn(self, message: str, context: dict) -> None:
        params = self.get_persona()
        self._stability.decay_params(params)
        self._trainer.check_feedback(message, params)
        self._stability.update_stability(params)
        self._cached_results["persona"] = params

    def get_full_injection(self) -> str:
        parts = []
        if self._persona_params:
            persona = self._injector.generate(self._persona_params)
            if persona:
                parts.append(persona)
        return "\n\n".join(parts)

    def on_memory_write(self, event: dict) -> None:
        pass

    def save_all(self):
        if self._persona_params:
            self._modifier.save(self._persona_params)
        if self._knowledge:
            self.storage.save(self.user_id, "knowledge.json", self._knowledge.to_dict())
        if self._style:
            self.storage.save(self.user_id, "language_profile.json", self._style.to_dict())
        if self._memory:
            self.storage.save(self.user_id, "private_memory.json", self._memory.to_dict())