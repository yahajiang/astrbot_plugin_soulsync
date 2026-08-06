"""SoulSync - 私人记忆：调用审计日志"""
import time
from ..trainer_types import MemoryAuditEntry
from ..trainer_storage import TrainerStorage


class MemoryAuditor:
    def __init__(self, storage: TrainerStorage, user_id: str):
        self.storage = storage
        self.user_id = user_id

    def log(self, memory_id: str, scene: str, context: str = ""):
        entries = self.storage.load(self.user_id, "memory_audit.json", [])
        entry = MemoryAuditEntry(
            memory_id=memory_id,
            access_time=time.time(),
            trigger_scene=scene,
            conversation_context=context[:200],
        )
        entries.append(entry.to_dict())
        if len(entries) > 1000:
            entries = entries[-500:]
        self.storage.save(self.user_id, "memory_audit.json", entries)