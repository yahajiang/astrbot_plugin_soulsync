"""SoulSync - 个性化训练 Orchestrator（四模块调度器）"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, Optional

from .trainer_types import PersonaParams, KnowledgeBase, StyleState, PrivateMemoryStore
from .trainer_storage import TrainerStorage
from .persona.persona_modifier import PersonaModifier
from .persona.persona_trainer import PersonaTrainer
from .persona.persona_stability import PersonaStability
from .persona.persona_guard import PersonaGuard
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


def approx_tokens(text: str) -> int:
    """近似 token 数：CJK 字符 1 字 1 token，英文按单词计。"""
    if not text:
        return 0
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    words = len(re.findall(r"[A-Za-z0-9]+", text))
    return cjk + words


# 注入优先级（0 最高）：人格 > 知识 > 记忆 > 风格
_INJECTION_PRIORITY = {"persona": 0, "knowledge": 1, "memory": 2, "style": 3}
# 各块默认配额（token），与总预算 450 对应
_DEFAULT_QUOTAS = {"persona": 80, "knowledge": 150, "memory": 120, "style": 100}
_DEFAULT_BUDGET = 450


class PersonalizationOrchestrator:
    def __init__(self, user_id: str, storage: TrainerStorage, config: dict = None):
        self.user_id = user_id
        self.storage = storage
        self.config = config or {}
        self._cached_results: Dict[str, Any] = {}
        self._persona_params: Optional[PersonaParams] = None
        self._knowledge: Optional[KnowledgeBase] = None
        self._style: Optional[StyleState] = None
        self._memory: Optional[PrivateMemoryStore] = None
        self._anniversary_hook = None
        self._modifier = PersonaModifier(storage, user_id)
        self._trainer = PersonaTrainer(self._modifier)
        self._stability = PersonaStability()
        self._guard = PersonaGuard(storage, user_id, self._modifier)
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

    # ── 存取 ──
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

    def save_all(self):
        if self._persona_params:
            self._modifier.save(self._persona_params)
        if self._knowledge:
            self.storage.save(self.user_id, "knowledge.json", self._knowledge.to_dict())
        if self._style:
            self.storage.save(self.user_id, "language_profile.json", self._style.to_dict())
        if self._memory:
            self.storage.save(self.user_id, "private_memory.json", self._memory.to_dict())

    # ── 联动钩子 ──
    def set_anniversary_hook(self, callback):
        """注册纪念日联动回调（promises 类知识新增时调用 callback(item)）。"""
        self._anniversary_hook = callback

    # ── 门面：带联动的写入 ──
    def _add_knowledge_item(self, category: str, key: str, value: str, source: str = "user_direct"):
        """向缓存知识库添加条目并持久化（保证缓存与 storage 一致）。"""
        import uuid as _uuid
        from .trainer_types import KnowledgeItem as _KI
        kb = self.get_knowledge()
        item = _KI(
            id=f"kn_{_uuid.uuid4().hex[:8]}",
            category=category,
            key=key,
            value=value,
            source=source,
            created_ts=time.time(),
            updated_ts=time.time(),
        )
        kb.items.append(item)
        self._knowledge_mgr.save(kb)
        return item

    def add_knowledge(self, category: str, key: str, value: str, source: str = "user_direct"):
        """新增知识；promises 类别自动联动纪念日钩子。"""
        item = self._add_knowledge_item(category, key, value, source)
        if category == "promises" and self._anniversary_hook:
            try:
                self._anniversary_hook(item)
            except Exception:
                pass
        return item

    def add_memory(self, mem_type: str, content: str, **kwargs):
        """新增记忆；importance>=8 的高显著性记忆自动提取为个人经历知识（知识→记忆联动）。"""
        mem = self._memory_mgr.add(mem_type, content, **kwargs)
        self._memory = None
        if mem.importance >= 8 and mem_type in ("text", "emotional"):
            kb = self.get_knowledge()
            exists = any(i.value == content and i.category == "experiences" for i in kb.items)
            if not exists:
                self._add_knowledge_item("experiences", "个人经历", content, "memory_extract")
        return mem

    # ── 每轮处理 ──
    def on_each_turn(self, message: str, context: dict) -> None:
        params = self.get_persona()
        # v2.20 人格护栏：自动锁定 / 震荡回滚（每轮先跑，护栏事件进 context）
        guard_events = self._guard.on_turn(params)
        if guard_events:
            context["persona_guard"] = guard_events
            self.save_all()
        if not self._guard.is_auto_paused(params):
            fb = self._trainer.check_feedback(message, params)
            self._stability.decay_params(params)
            self._stability.update_stability(params)
            if fb:
                context["needs_persona_hint"] = True
        self._cached_results["persona"] = params
        kb = self.get_knowledge()
        trigger = self._knowledge_capture.check_trigger_full(message, kb)
        if trigger["triggered"] and not trigger.get("conflict"):
            self._add_knowledge_item(trigger["category"], trigger["word"], trigger["content"], "auto_capture")
        elif trigger.get("repeat_suggested"):
            context["knowledge_repeat"] = trigger["message"]
            context["needs_knowledge_ask"] = True
        elif trigger.get("conflict"):
            context["needs_knowledge_ask"] = True
        self._cached_results["knowledge"] = kb
        style_state = self.get_style()
        if not style_state.locked:
            incr = self._style_analyzer.analyze_increment(message, style_state.profile)
            self._style_trainer.update_profile(style_state, incr)
        self._cached_results["style"] = style_state
        mem_store = self.get_private_memory()
        if mem_store:
            persona = {
                "grudge_coefficient": params.grudge_coefficient,
                "romantic_memory_weight": params.romantic_memory_weight,
                "forget_speed": params.forget_speed,
            }
            memories = self._memory_retriever.retrieve(mem_store, {"keywords": message[:50] if message else "", "persona": persona}, max_items=3)
            self._cached_results["memories"] = memories

    # ── 注入组装 + token 预算裁剪 ──
    def get_full_injection(self) -> str:
        sections: list = []
        if self._persona_params:
            text = self._injector.generate(self._persona_params)
            if text:
                sections.append(("persona", text))
        if self._knowledge:
            text = self._knowledge_injector.generate(self._knowledge)
            if text:
                sections.append(("knowledge", text))
        memories = self._cached_results.get("memories")
        if memories:
            text = self._memory_retriever.format_for_llm(memories)
            if text:
                sections.append(("memory", text))
        if self._style:
            text = self._style_injector.generate(self._style)
            if text:
                sections.append(("style", text))
        trimmed = self._trim_to_budget(sections)
        return "\n\n".join(t for _, t in trimmed)

    def _trim_to_budget(self, sections: list) -> list:
        """总预算裁剪：超限时从低优先级（风格→记忆→知识）开始裁剪，人格永不整块丢弃。"""
        if not sections:
            return []
        budget = int(self.config.get("personalization_total_token_budget", _DEFAULT_BUDGET))
        sections = sorted(sections, key=lambda s: _INJECTION_PRIORITY[s[0]])
        total = sum(approx_tokens(t) for _, t in sections)
        if total <= budget:
            return sections
        # 从低优先级开始：先截断到各自默认配额，仍超则整块丢弃
        for idx in range(len(sections) - 1, -1, -1):
            if total <= budget:
                break
            key, text = sections[idx]
            quota = _DEFAULT_QUOTAS.get(key, 80)
            if approx_tokens(text) > quota:
                sections[idx] = (key, self._truncate_to(text, quota))
            total = sum(approx_tokens(t) for _, t in sections)
            if total > budget:
                sections.pop(idx)
                total = sum(approx_tokens(t) for _, t in sections)
        return sections

    @staticmethod
    def _truncate_to(text: str, limit: int) -> str:
        if approx_tokens(text) <= limit:
            return text
        out = ""
        for ch in text:
            if approx_tokens(out + ch) > limit:
                break
            out += ch
        return (out.rstrip() + "…") if out else text[:10] + "…"

    # ── v2.16 联动：长期记忆写入通知 ──
    def on_memory_write(self, event: dict) -> None:
        """v2.16 长期记忆写入时：高显著性事件自动提取为私人记忆（text 类）。"""
        try:
            sig = float(event.get("significance", 0) or 0)
            if not (sig >= 8 or event.get("important")):
                return
            content = (event.get("message") or event.get("description") or "").strip()
            if not content or len(content) < 4:
                return
            store = self.get_private_memory()
            if any(m.content == content for m in store.text):
                return
            self._memory_mgr.add("text", content, importance=8)
            self._memory = None
        except Exception:
            pass

    def on_llm_response(self, response: str) -> None:
        pass
