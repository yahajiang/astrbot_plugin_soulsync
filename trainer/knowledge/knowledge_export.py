"""SoulSync - 知识库：导出/导入"""
import json
from ..trainer_types import KnowledgeBase
from ..trainer_storage import TrainerStorage


class KnowledgeExport:
    def __init__(self, storage: TrainerStorage, user_id: str):
        self.storage = storage
        self.user_id = user_id

    def export(self) -> str:
        kb = KnowledgeBase.from_dict(self.storage.load(self.user_id, "knowledge.json") or {})
        return json.dumps(kb.to_dict(), ensure_ascii=False, indent=2)

    def import_data(self, json_str: str) -> dict:
        try:
            data = json.loads(json_str)
            kb = KnowledgeBase.from_dict(data)
            self.storage.save(self.user_id, "knowledge.json", kb.to_dict())
            return {"ok": True, "count": len(kb.items)}
        except Exception as e:
            return {"ok": False, "error": str(e)}