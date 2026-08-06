"""SoulSync - 知识库：知识增删改查"""
import uuid
import time
from ..trainer_types import KnowledgeBase, KnowledgeItem
from ..trainer_storage import TrainerStorage


class KnowledgeManager:
    def __init__(self, storage: TrainerStorage, user_id: str):
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