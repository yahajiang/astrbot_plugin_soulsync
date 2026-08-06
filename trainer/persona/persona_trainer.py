"""SoulSync - 人格微调：隐式训练检测（正负反馈词匹配 + 参数偏移计算）"""
from ..trainer_types import PersonaParams


POSITIVE_FEEDBACK = {
    "humor": {
        "words": ["哈哈", "笑死", "有趣", "逗", "好笑", "搞笑", "有意思", "太绝了"],
        "effects": {"tequila_rate": 0.5, "humor_tone_score": 0.3},
    },
    "gentle": {
        "words": ["温柔", "贴心", "暖心", "体贴", "好暖", "感动", "真好"],
        "effects": {"support_style_score": 0.5, "sajiao_rate": 0.3},
    },
    "direct": {
        "words": ["直接", "坦诚", "真实", "不说废话", "干脆", "爽快"],
        "effects": {"emotional_express": 0.5, "conflict_style_score": 0.3},
    },
    "company": {
        "words": ["陪我", "在吗", "别走", "一直在", "安心", "踏实"],
        "effects": {"trust_baseline": 0.3, "romantic_memory_weight": 0.2},
    },
}

NEGATIVE_FEEDBACK = {
    "over_tease": {
        "words": ["过分", "太损了", "别损我", "认真的", "不好笑"],
        "effects": {"tequila_rate": -0.8, "humor_tone_score": -0.5},
    },
    "less_care": {
        "words": ["冷漠", "不关心", "敷衍", "不在乎", "没意思"],
        "effects": {"support_style_score": -0.5, "emotional_express": -0.3},
    },
}

HUMOR_TONE_MAP = {"warm": 0, "ironic": 1, "deadpan": 2}
HUMOR_TONE_REV = {0: "warm", 1: "ironic", 2: "deadpan"}
SUPPORT_MAP = {"gentle": 0, "direct": 1, "practical": 2}
SUPPORT_REV = {0: "gentle", 1: "direct", 2: "practical"}
CONFLICT_MAP = {"avoid": 0, "balance": 1, "confront": 2}
CONFLICT_REV = {0: "avoid", 1: "balance", 2: "confront"}


class PersonaTrainer:
    def __init__(self, modifier):
        self.modifier = modifier

    def check_feedback(self, message: str, params: PersonaParams) -> list:
        results = []
        for kind, cfg in POSITIVE_FEEDBACK.items():
            for w in cfg["words"]:
                if w in message:
                    for param, delta in cfg["effects"].items():
                        self._apply_effect(params, param, delta, f"正面-{kind}")
                    results.append(("positive", kind, w))
        for kind, cfg in NEGATIVE_FEEDBACK.items():
            for w in cfg["words"]:
                if w in message:
                    for param, delta in cfg["effects"].items():
                        self._apply_effect(params, param, delta, f"负面-{kind}")
                    results.append(("negative", kind, w))
        if results:
            params.total_training_turns += 1
        return results

    def _apply_effect(self, params: PersonaParams, param: str, delta: float, reason: str):
        if params.locked:
            return
        if param == "humor_tone_score":
            cur = HUMOR_TONE_MAP.get(params.humor_tone, 0)
            new_idx = max(0, min(2, cur + (1 if delta > 0 else -1)))
            params.humor_tone = HUMOR_TONE_REV[new_idx]
        elif param == "support_style_score":
            cur = SUPPORT_MAP.get(params.support_style, 0)
            new_idx = max(0, min(2, cur + (1 if delta > 0 else -1)))
            params.support_style = SUPPORT_REV[new_idx]
        elif param == "conflict_style_score":
            cur = CONFLICT_MAP.get(params.conflict_style, 0)
            new_idx = max(0, min(2, cur + (1 if delta > 0 else -1)))
            params.conflict_style = CONFLICT_REV[new_idx]
        else:
            self.modifier.apply_offset(params, param, delta, reason)