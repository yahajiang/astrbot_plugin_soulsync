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
            state.fusion_ratio = min(1.0, (total_turns - COLLECTION_TURNS) / (ADOPTION_TURNS - COLLECTION_TURNS))
        else:
            state.phase = "fused"
            state.fusion_ratio = 1.0