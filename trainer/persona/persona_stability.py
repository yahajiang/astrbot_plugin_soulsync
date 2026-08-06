"""SoulSync - 人格微调：稳定化（稳定度计算/半衰期/锁定/衰减）"""
import time
from ..trainer_types import PersonaParams
from .persona_params import PARAM_META


class PersonaStability:
    EXPLORE_MAX = 100
    GROWTH_MAX = 300

    def update_stability(self, params: PersonaParams):
        turns = params.total_training_turns
        if turns <= self.EXPLORE_MAX:
            params.stability = round(turns / self.EXPLORE_MAX * 30, 1)
        elif turns <= self.GROWTH_MAX:
            ratio = (turns - self.EXPLORE_MAX) / (self.GROWTH_MAX - self.EXPLORE_MAX)
            params.stability = round(30 + ratio * 40, 1)
        else:
            ratio = min(1.0, (turns - self.GROWTH_MAX) / 500)
            params.stability = round(70 + ratio * 30, 1)

    def decay_half_life_sec(self, params: PersonaParams) -> float:
        if params.stability < 30:
            return 7 * 86400
        if params.stability < 70:
            return 30 * 86400
        return 90 * 86400

    def decay_params(self, params: PersonaParams, now: float = 0.0):
        if params.locked or params.stability >= 100:
            return
        now = now or time.time()
        half_life = self.decay_half_life_sec(params)
        if not params.last_updated:
            return
        try:
            updated = time.mktime(time.strptime(params.last_updated, "%Y-%m-%d %H:%M"))
        except Exception:
            return
        elapsed = now - updated
        if elapsed <= 0:
            return
        decay_factor = 0.5 ** (elapsed / half_life)
        if decay_factor > 0.95:
            return
        for name in PARAM_META:
            meta = PARAM_META[name]
            if meta["type"] != "float" or not hasattr(params, name):
                continue
            if name in ("stability", "total_training_turns", "locked"):
                continue
            cur = getattr(params, name)
            default = meta["default"]
            new = default + (cur - default) * decay_factor
            if "min" in meta:
                new = max(meta["min"], new)
            if "max" in meta:
                new = min(meta["max"], new)
            setattr(params, name, round(new, 2))