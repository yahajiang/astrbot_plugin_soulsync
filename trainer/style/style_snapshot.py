"""SoulSync - 语言风格：快照管理（保存/恢复/对比）"""
import time
from ..trainer_types import LanguageProfile, StyleSnapshot, StyleState


class StyleSnapshotManager:
    def __init__(self, storage, user_id: str):
        self.storage = storage
        self.user_id = user_id

    def save_snapshot(self, state: StyleState, name: str = ""):
        name = name or f"snap_{time.strftime('%m%d_%H%M')}"
        profile_copy = LanguageProfile.from_dict(state.profile.to_dict()) if state.profile else None
        snap = StyleSnapshot(name=name, created_ts=time.time(), profile=profile_copy)
        state.snapshots.append(snap)
        self.storage.save(self.user_id, "language_profile.json", state.to_dict())

    def restore_snapshot(self, state: StyleState, name: str) -> bool:
        for snap in state.snapshots:
            if snap.name == name:
                state.profile = snap.profile
                from .style_trainer import StyleTrainer
                trainer = StyleTrainer(self.storage, self.user_id)
                trainer.update_phase(state, state.profile.total_turns if state.profile else 0)
                self.storage.save(self.user_id, "language_profile.json", state.to_dict())
                return True
        return False

    def compare_snapshots(self, state: StyleState, name1: str, name2: str) -> dict:
        s1 = next((s for s in state.snapshots if s.name == name1), None)
        s2 = next((s for s in state.snapshots if s.name == name2), None)
        if not s1 or not s2 or not s1.profile or not s2.profile:
            return {"error": "one or both snapshots not found"}
        p1, p2 = s1.profile, s2.profile
        diffs = {
            "avg_length": round(p2.avg_length - p1.avg_length, 1),
            "formality": round(p2.formality_score - p1.formality_score, 2),
            "directness": round(p2.directness_score - p1.directness_score, 2),
            "english_mix": round(p2.english_mix_rate - p1.english_mix_rate, 2),
            "turns_delta": p2.total_turns - p1.total_turns,
        }
        return diffs