"""SoulSync - 人格微调：核心引擎（读写/偏移/衰减）"""
from ..trainer_types import PersonaParams
from .persona_params import PARAM_META, default_params
from ..trainer_storage import TrainerStorage


class PersonaModifier:
    def __init__(self, storage: TrainerStorage, user_id: str):
        self.storage = storage
        self.user_id = user_id

    def get(self) -> PersonaParams:
        data = self.storage.load(self.user_id, "persona.json")
        return PersonaParams.from_dict(data) if data else default_params()

    def save(self, params: PersonaParams):
        self.storage.save(self.user_id, "persona.json", params.to_dict())

    def apply_offset(self, params: PersonaParams, param_name: str, delta: float):
        if not hasattr(params, param_name):
            return
        meta = PARAM_META.get(param_name)
        if not meta:
            return
        old = getattr(params, param_name)
        if isinstance(old, (int, float)):
            new = old + delta
            if "min" in meta:
                new = max(meta["min"], new)
            if "max" in meta:
                new = max(meta["min"], min(meta["max"], new))
            setattr(params, param_name, type(old)(new))

    def reset(self):
        self.storage.save(self.user_id, "persona.json", default_params().to_dict())