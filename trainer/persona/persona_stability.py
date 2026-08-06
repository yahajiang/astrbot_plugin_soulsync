"""SoulSync - 人格微调：稳定化"""
import time
from ..trainer_types import PersonaParams


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

    def decay_half_life(self, params: PersonaParams) -> float:
        if params.stability < 30:
            return 7 * 86400
        if params.stability < 70:
            return 30 * 86400
        return 90 * 86400