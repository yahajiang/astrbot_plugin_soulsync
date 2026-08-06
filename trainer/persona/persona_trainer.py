"""SoulSync - 人格微调：隐式训练检测"""
from ..trainer_types import PersonaParams


POSITIVE_FEEDBACK = {
    "humor": ["哈哈", "笑死", "有趣", "逗", "好笑", "搞笑", "有意思", "太绝了"],
    "gentle": ["温柔", "贴心", "暖心", "体贴", "好暖", "感动", "真好"],
    "direct": ["直接", "坦诚", "真实", "不说废话", "干脆", "爽快"],
    "company": ["陪我", "在吗", "别走", "一直在", "安心", "踏实"],
}

NEGATIVE_FEEDBACK = {
    "over_tease": ["过分", "太损了", "别损我", "认真的", "不好笑"],
    "less_care": ["冷漠", "不关心", "敷衍", "不在乎", "没意思"],
}


class PersonaTrainer:
    def __init__(self, modifier):
        self.modifier = modifier

    def check_feedback(self, message: str, params: PersonaParams) -> list:
        results = []
        for kind, words in POSITIVE_FEEDBACK.items():
            for w in words:
                if w in message:
                    results.append(("positive", kind, w))
        for kind, words in NEGATIVE_FEEDBACK.items():
            for w in words:
                if w in message:
                    results.append(("negative", kind, w))
        return results