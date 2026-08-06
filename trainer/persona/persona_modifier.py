"""SoulSync - 人格微调：核心引擎（读写/偏移/衰减/历史记录）"""
import time
from ..trainer_types import PersonaParams, PersonaHistoryEntry
from .persona_params import default_params
from ..trainer_storage import TrainerStorage


class PersonaModifier:
    def __init__(self, storage: TrainerStorage, user_id: str):
        self.storage = storage
        self.user_id = user_id
        self._history: list = []

    def get(self) -> PersonaParams:
        data = self.storage.load(self.user_id, "persona.json")
        return PersonaParams.from_dict(data) if data else default_params()

    def save(self, params: PersonaParams):
        params.last_updated = time.strftime("%Y-%m-%d %H:%M")
        self.storage.save(self.user_id, "persona.json", params.to_dict())

    def apply_offset(self, params: PersonaParams, param_name: str, delta: float, reason: str = ""):
        if params.locked or param_name == "locked":
            return False
        meta = self._meta(param_name)
        if not meta:
            return False
        old = getattr(params, param_name)
        if isinstance(old, (int, float)):
            new = old + delta
            if "min" in meta:
                new = max(meta["min"], new)
            if "max" in meta:
                new = min(meta["max"], new)
            new = type(old)(new)
            setattr(params, param_name, new)
            entry = PersonaHistoryEntry(
                ts=time.time(),
                param_name=param_name,
                old_value=float(old),
                new_value=float(new),
                reason=reason,
            )
            self._history.append(entry.to_dict())
            params.total_training_turns += 1
            return True
        return False

    def lock(self, params: PersonaParams):
        params.locked = True
        self.save(params)

    def unlock(self, params: PersonaParams):
        params.locked = False
        self.save(params)

    def reset(self):
        p = default_params()
        self.save(p)

    def get_history(self, limit: int = 20) -> list:
        return self._history[-limit:]

    def _meta(self, param_name: str) -> dict:
        from .persona_params import PARAM_META
        return PARAM_META.get(param_name)