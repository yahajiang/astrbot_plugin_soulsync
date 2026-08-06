"""SoulSync - 语言风格：快照管理"""
import time
from ..trainer_types import LanguageProfile, StyleSnapshot, StyleState
from ..trainer_storage import TrainerStorage


class StyleSnapshotManager:
    def __init__(self, storage: TrainerStorage, user_id: str):
        self.storage = storage
        self.user_id = user_id

    def save_snapshot(self, state: StyleState, name: str = ""):
        name = name or f"快照_{time.strftime('%m-%d_%H%M')}"
        snap = StyleSnapshot(
            name=name,
            created_ts=time.time(),
            profile=state.profile,
        )
        state.snapshots.append(snap)
        self.storage.save(self.user_id, "language_profile.json", state.to_dict())

    def restore_snapshot(self, state: StyleState, name: str) -> bool:
        for snap in state.snapshots:
            if snap.name == name:
                state.profile = snap.profile
                self.storage.save(self.user_id, "language_profile.json", state.to_dict())
                return True
        return False