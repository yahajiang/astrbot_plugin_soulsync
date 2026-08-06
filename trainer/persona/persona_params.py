"""SoulSync - 人格微调：20个参数定义与默认值"""
from ..trainer_types import PersonaParams

PARAM_META = {
    "joy_baseline": {"type": "float", "min": -20, "max": 20, "default": 0, "label": "快乐基线", "desc": "喜悦维度日常偏移量"},
    "sadness_sensitivity": {"type": "float", "min": 0.5, "max": 3.0, "default": 1.0, "label": "悲伤敏感度", "desc": "悲伤维度放大系数"},
    "anger_threshold": {"type": "float", "min": 0.5, "max": 3.0, "default": 1.0, "label": "愤怒门槛", "desc": "愤怒触发门槛"},
    "trust_baseline": {"type": "float", "min": -15, "max": 15, "default": 0, "label": "信任基线", "desc": "信任维度日常偏移"},
    "expectation_growth": {"type": "float", "min": 0.5, "max": 2.0, "default": 1.0, "label": "期待增长", "desc": "期待维度增长速率"},
    "proactive_topic": {"type": "str", "options": ["low", "med", "high"], "default": "med", "label": "话题主动性", "desc": "主动话题频率"},
    "jealousy_threshold": {"type": "str", "options": ["low", "med", "high"], "default": "med", "label": "吃醋敏感度", "desc": "吃醋触发门槛"},
    "conflict_style": {"type": "str", "options": ["avoid", "confront", "balance"], "default": "balance", "label": "分歧处理", "desc": "分歧处理模式"},
    "support_style": {"type": "str", "options": ["gentle", "direct", "practical"], "default": "gentle", "label": "安慰风格", "desc": "安慰表达方式"},
    "tequila_rate": {"type": "float", "min": 0, "max": 100, "default": 30, "label": "吐槽频率", "desc": "吐槽频率%"},
    "sajiao_rate": {"type": "float", "min": 0, "max": 100, "default": 20, "label": "撒娇频率", "desc": "撒娇频率%"},
    "emotional_express": {"type": "float", "min": 0, "max": 100, "default": 50, "label": "情感直白度", "desc": "情感表达的直白程度"},
    "humor_tone": {"type": "str", "options": ["warm", "ironic", "deadpan"], "default": "warm", "label": "幽默风格", "desc": "幽默风格"},
    "length_preference": {"type": "str", "options": ["short", "medium", "long"], "default": "medium", "label": "回复长度", "desc": "回复长度倾向"},
    "grudge_coefficient": {"type": "float", "min": 0, "max": 3.0, "default": 1.0, "label": "记仇系数", "desc": "记仇系数"},
    "romantic_memory_weight": {"type": "float", "min": 0.5, "max": 3.0, "default": 1.0, "label": "浪漫回忆权重", "desc": "浪漫记忆引用权重"},
    "forget_speed": {"type": "float", "min": 0.5, "max": 2.0, "default": 1.0, "label": "遗忘速度", "desc": "未提及话题遗忘速率"},
    "milestone_sensitivity": {"type": "float", "min": 0.5, "max": 2.0, "default": 1.0, "label": "里程碑重视度", "desc": "里程碑重视度"},
    "stability": {"type": "float", "min": 0, "max": 100, "default": 0, "label": "稳定度", "desc": "训练稳定度%"},
    "total_training_turns": {"type": "int", "min": 0, "max": 999999, "default": 0, "label": "累计训练轮数", "desc": "累计训练轮数"},
    "locked": {"type": "bool", "default": False, "label": "锁定状态", "desc": "锁定后参数不再变化"},
}

def default_params() -> PersonaParams:
    return PersonaParams()