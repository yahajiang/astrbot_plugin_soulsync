"""SoulSync - 语言风格：三阶段训练"""
from ..trainer_types import LanguageProfile, StyleState

COLLECTION_TURNS = 100
ADOPTION_TURNS = 300


class StyleTrainer:
    def __init__(self, storage, user_id: str):
        self.storage = storage
        self.user_id = user_id

    def get_state(self) -> StyleState:
        data = self.storage.load(self.user_id, "language_profile.json")
        return StyleState.from_dict(data) if data else StyleState()

    def save_state(self, state: StyleState):
        self.storage.save(self.user_id, "language_profile.json", state.to_dict())

    def update_phase(self, state: StyleState, total_turns: int):
        if total_turns <= COLLECTION_TURNS:
            state.phase = "collection"
            state.fusion_ratio = 0.0
        elif total_turns <= ADOPTION_TURNS:
            state.phase = "adoption"
            state.fusion_ratio = min(1.0, max(0.0, (total_turns - COLLECTION_TURNS) / max(1, ADOPTION_TURNS - COLLECTION_TURNS)))
        else:
            state.phase = "fused"
            state.fusion_ratio = 1.0

    def update_profile(self, state: StyleState, increment: dict):
        if not state.profile:
            state.profile = LanguageProfile()
        p = state.profile
        p.total_turns += 1
        if "length" in increment:
            length = increment["length"]
            p.avg_length = (p.avg_length * (p.total_turns - 1) + length) / p.total_turns
        if "formality" in increment:
            p.formality_score = increment["formality"]
        if "directness" in increment:
            p.directness_score = increment["directness"]
        self.update_phase(state, p.total_turns)
        self.save_state(state)