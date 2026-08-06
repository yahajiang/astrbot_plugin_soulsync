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
from .knowledge.knowledge_manager import KnowledgeManager, ConflictResult
from .knowledge.knowledge_capture import KnowledgeCapture
from .knowledge.knowledge_injector import KnowledgeInjector
from .style.style_analyzer import StyleAnalyzer
from .style.style_trainer import StyleTrainer
from .style.style_injector import StyleInjector
from .memory.private_memory_manager import PrivateMemoryManager
from .memory.private_memory_retriever import PrivateMemoryRetriever
from .memory.private_memory_auditor import MemoryAuditor


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
        self._knowledge_mgr = KnowledgeManager(storage, user_id)
        self._knowledge_capture = KnowledgeCapture(self._knowledge_mgr)
        self._knowledge_injector = KnowledgeInjector()
        self._style_analyzer = StyleAnalyzer()
        self._style_trainer = StyleTrainer(storage, user_id)
        self._style_injector = StyleInjector()
        self._memory_mgr = PrivateMemoryManager(storage, user_id)
        self._memory_retriever = PrivateMemoryRetriever()
        self._memory_auditor = MemoryAuditor(storage, user_id)

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
        kb = self.get_knowledge()
        trigger = self._knowledge_capture.check_trigger_full(message, kb)
        if trigger["triggered"] and not trigger.get("conflict"):
            self._knowledge_mgr.add(trigger["category"], trigger["word"], trigger["content"], "auto_capture")
        elif trigger.get("repeat_suggested"):
            context["knowledge_repeat"] = trigger["message"]
        self._cached_results["knowledge"] = kb
        style_state = self.get_style()
        if not style_state.locked:
            incr = self._style_analyzer.analyze_increment(message, style_state.profile)
            self._style_trainer.update_profile(style_state, incr)
        self._cached_results["style"] = style_state
        mem_store = self.get_private_memory()
        if mem_store:
            context_keywords = message[:50] if message else ""
            memories = self._memory_retriever.retrieve(mem_store, {"keywords": context_keywords}, max_items=3)
            self._cached_results["memories"] = memories

    def get_full_injection(self) -> str:
        parts = []
        if self._persona_params:
            persona = self._injector.generate(self._persona_params)
            if persona:
                parts.append(persona)
        if self._knowledge:
            knowledge = self._knowledge_injector.generate(self._knowledge)
            if knowledge:
                parts.append(knowledge)
        if self._style:
            style = self._style_injector.generate(self._style)
            if style:
                parts.append(style)
        memories = self._cached_results.get("memories")
        if memories:
            mem_text = self._memory_retriever.format_for_llm(memories)
            if mem_text:
                parts.append(mem_text)
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