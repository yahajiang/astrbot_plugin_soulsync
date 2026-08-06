"""SoulSync - 知识库：知识增删改查 + 冲突检测 + 相关检索"""
import uuid
import time
from ..trainer_types import KnowledgeBase, KnowledgeItem


class ConflictResult:
    def __init__(self, has_conflict: bool = False, existing: list = None):
        self.has_conflict = has_conflict
        self.existing = existing or []


class KnowledgeManager:
    def __init__(self, storage, user_id: str):
        self.storage = storage
        self.user_id = user_id

    def get(self) -> KnowledgeBase:
        data = self.storage.load(self.user_id, "knowledge.json")
        return KnowledgeBase.from_dict(data) if data else KnowledgeBase()

    def save(self, kb: KnowledgeBase):
        self.storage.save(self.user_id, "knowledge.json", kb.to_dict())

    def add(self, category: str, key: str, value: str, source: str = "user_direct") -> KnowledgeItem:
        kb = self.get()
        item = KnowledgeItem(
            id=f"kn_{uuid.uuid4().hex[:8]}",
            category=category,
            key=key,
            value=value,
            source=source,
            created_ts=time.time(),
            updated_ts=time.time(),
        )
        kb.items.append(item)
        self.save(kb)
        return item

    def remove(self, item_id: str) -> bool:
        kb = self.get()
        for i, item in enumerate(kb.items):
            if item.id == item_id:
                kb.items.pop(i)
                self.save(kb)
                return True
        return False

    def check_conflict(self, category: str, key: str, value: str) -> ConflictResult:
        kb = self.get()
        conflicts = []
        for item in kb.items:
            if item.category == category and item.key == key and item.value != value:
                conflicts.append(item)
            if item.category == category and item.key == "自我陈述" and item.value != value:
                conflicts.append(item)
        return ConflictResult(has_conflict=len(conflicts) > 0, existing=conflicts)

    def query_relevant(self, keywords: str, max_items: int = 5) -> list:
        kb = self.get()
        if not keywords:
            return kb.items[:max_items]
        kw_lower = keywords.lower()
        scored = []
        for item in kb.items:
            score = 0
            if kw_lower in item.key.lower():
                score += 3
            if kw_lower in item.value.lower():
                score += 2
            for tag in item.tags:
                if kw_lower in tag.lower():
                    score += 1
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda x: -x[0])
        return [item for _, item in scored[:max_items]]