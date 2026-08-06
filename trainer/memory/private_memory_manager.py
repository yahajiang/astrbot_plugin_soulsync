"""SoulSync - 私人记忆：记忆增删改查（含容量上限）"""
import uuid
import time
from ..trainer_types import PrivateMemory, PrivateMemoryStore

CAPACITY_LIMITS = {"text": 500, "image": 200, "promise": 50, "emotional": 100}


class PrivateMemoryManager:
    def __init__(self, storage, user_id: str):
        self.storage = storage
        self.user_id = user_id

    def get(self) -> PrivateMemoryStore:
        data = self.storage.load(self.user_id, "private_memory.json")
        return PrivateMemoryStore.from_dict(data) if data else PrivateMemoryStore()

    def save(self, store: PrivateMemoryStore):
        self.storage.save(self.user_id, "private_memory.json", store.to_dict())

    def add(self, mem_type: str, content: str, **kwargs) -> PrivateMemory:
        store = self.get()
        target_map = {"text": store.text, "image": store.images, "promise": store.promises, "emotional": store.emotional}
        target = target_map.get(mem_type, store.text)
        limit = CAPACITY_LIMITS.get(mem_type, 500)
        if len(target) >= limit:
            raise ValueError(f"{mem_type}记忆已达上限({limit}条)，请删除一些后再添加")
        mem = PrivateMemory(
            id=f"pm_{uuid.uuid4().hex[:8]}",
            type=mem_type,
            content=content,
            date=kwargs.get("date", time.strftime("%Y-%m-%d")),
            tags=kwargs.get("tags", []),
            mood=kwargs.get("mood", ""),
            importance=kwargs.get("importance", 5),
            promise_due=kwargs.get("promise_due", ""),
            emotion_tags=kwargs.get("emotion_tags", []),
            intensity=kwargs.get("intensity", 0.0),
        )
        target.append(mem)
        self.save(store)
        return mem

    def remove(self, memory_id: str) -> bool:
        store = self.get()
        for lst in [store.text, store.images, store.promises, store.emotional]:
            for i, m in enumerate(lst):
                if m.id == memory_id:
                    lst.pop(i)
                    store.starred = [s for s in store.starred if s != memory_id]
                    self.save(store)
                    return True
        return False

    def star(self, memory_id: str):
        store = self.get()
        if memory_id not in store.starred:
            store.starred.append(memory_id)
            self.save(store)

    def unstar(self, memory_id: str):
        store = self.get()
        store.starred = [s for s in store.starred if s != memory_id]
        self.save(store)

    def mark_sensitive(self, memory_id: str):
        store = self.get()
        for lst in [store.text, store.images, store.promises, store.emotional]:
            for m in lst:
                if m.id == memory_id:
                    m.sensitive = True
                    self.save(store)
                    return

    def all_memories(self, store: PrivateMemoryStore = None) -> list:
        if store is None:
            store = self.get()
        result = []
        for lst in [store.text, store.images, store.promises, store.emotional]:
            result.extend(lst)
        return result