"""SoulSync - 私人记忆：导出/导入"""
import json
from ..trainer_types import PrivateMemoryStore
from ..trainer_storage import TrainerStorage


class PrivateMemoryExport:
    def __init__(self, storage: TrainerStorage, user_id: str):
        self.storage = storage
        self.user_id = user_id

    def export(self) -> str:
        store = PrivateMemoryStore.from_dict(self.storage.load(self.user_id, "private_memory.json") or {})
        return json.dumps(store.to_dict(), ensure_ascii=False, indent=2)

    def import_data(self, json_str: str) -> dict:
        try:
            data = json.loads(json_str)
            store = PrivateMemoryStore.from_dict(data)
            self.storage.save(self.user_id, "private_memory.json", store.to_dict())
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}