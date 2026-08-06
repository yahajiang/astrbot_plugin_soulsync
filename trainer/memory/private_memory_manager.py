"""SoulSync - 私人记忆：记忆增删改查"""
import uuid
import time
from ..trainer_types import PrivateMemory, PrivateMemoryStore
from ..trainer_storage import TrainerStorage


class PrivateMemoryManager:
    def __init__(self, storage: TrainerStorage, user_id: str):
        self.storage = storage
        self.user_id = user_id

    def get(self) -> PrivateMemoryStore:
        data = self.storage.load(self.user_id, "private_memory.json")
        return PrivateMemoryStore.from_dict(data) if data else PrivateMemoryStore()

    def save(self, store: PrivateMemoryStore):
        self.storage.save(self.user_id, "private_memory.json", store.to_dict())

    def add(self, mem_type: str, content: str, **kwargs) -> PrivateMemory:
        store = self.get()
        mem = PrivateMemory(
            id=f"pm_{uuid.uuid4().hex[:8]}",
            type=mem_type,
            content=content,
            date=kwargs.get("date", time.strftime("%Y-%m-%d")),
            tags=kwargs.get("tags", []),
            mood=kwargs.get("mood", ""),
            importance=kwargs.get("importance", 5),
        )
        target = {"text": store.text, "image": store.images, "promise": store.promises, "emotional": store.emotional}
        target.get(mem_type, store.text).append(mem)
        self.save(store)
        return mem

    def remove(self, memory_id: str) -> bool:
        store = self.get()
        for lst in [store.text, store.images, store.promises, store.emotional]:
            for i, m in enumerate(lst):
                if m.id == memory_id:
                    lst.pop(i)
                    self.save(store)
                    return True
        return False

    def star(self, memory_id: str):
        store = self.get()
        if memory_id not in store.starred:
            store.starred.append(memory_id)
            self.save(store)

    def mark_sensitive(self, memory_id: str):
        store = self.get()
        for lst in [store.text, store.images, store.promises, store.emotional]:
            for m in lst:
                if m.id == memory_id:
                    m.sensitive = True
                    self.save(store)
                    return