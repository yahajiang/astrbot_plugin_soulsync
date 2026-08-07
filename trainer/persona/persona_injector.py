"""SoulSync - 人格微调：LLM上下文生成（v2.21 按文本相关性裁剪维度）"""
from ..trainer_types import PersonaParams


STAGE_LABELS = {0: "探索期", 30: "成长期", 70: "定型期", 100: "锁定态"}


def _stage_label(stability: float) -> str:
    if stability >= 100:
        return "锁定态"
    if stability >= 70:
        return "定型期"
    if stability >= 30:
        return "成长期"
    return "探索期"


# (触发关键词, 维度行模板)
_PERSONA_ROWS = [
    (["难过", "伤心", "生气", "委屈", "失望", "害怕", "焦虑", "哭", "吵架", "烦", "讨厌", "气"],
     "· 情感倾向：悲伤敏感{sadness_sensitivity:.1f}x 愤怒门槛{anger_threshold:.1f}x"),
    (["开心", "幸福", "喜欢", "甜", "高兴", "快乐"],
     "· 情感倾向：快乐基线{joy_baseline:+.0f}"),
    (["相信", "信任", "秘密", "坦诚", "说给你"],
     "· 情感倾向：信任基线{trust_baseline:+.0f}"),
    (["以后", "将来", "约好", "答应", "期待", "一起", "计划"],
     "· 情感倾向：期待增长{expectation_growth:.1f}x"),
    (["话题", "聊", "游戏", "电影", "吃", "喝", "玩"],
     "· 行为模式：话题{proactive_topic}"),
    (["吃醋", "别人", "异性", "闺蜜", "兄弟"],
     "· 行为模式：吃醋{jealousy_threshold}"),
    (["吵架", "冲突", "闹", "分歧"],
     "· 行为模式：分歧{conflict_style} 安慰{support_style}"),
    (["吐槽", "怼", "损"],
     "· 表达风格：吐槽{tequila_rate:.0f}%"),
    (["撒娇", "哼", "亲", "抱", "爱你", "想你"],
     "· 表达风格：撒娇{sajiao_rate:.0f}%"),
    (["直白", "直接", "说实话"],
     "· 表达风格：直白{emotional_express:.0f}% 幽默{humor_tone}"),
    (["记仇", "记得", "上次", "以前", "永远"],
     "· 记忆偏好：记仇{grudge_coefficient:.1f}x 浪漫回忆{romantic_memory_weight:.1f}x"),
]


class PersonaInjector:
    def generate(self, params: PersonaParams, text: str = "") -> str:
        if not params:
            return ""
        stage = _stage_label(params.stability)
        lock_tag = "🔒 已锁定" if params.locked else ""
        lines = [
            "[角色人格·训练调制]",
            f"训练阶段：{stage} 稳定度{params.stability:.0f}% 累计{params.total_training_turns}轮 {lock_tag}".strip(),
        ]
        if not text:
            lines.extend(self._all_rows(params))
        else:
            t = text.lower()
            for kws, tmpl in _PERSONA_ROWS:
                if any(kw in t for kw in kws):
                    lines.append(tmpl.format(**params.__dict__))
        return "\n".join(lines)

    @staticmethod
    def _all_rows(params: PersonaParams) -> list:
        return [
            f"· 情感倾向：快乐基线{params.joy_baseline:+.0f} 悲伤敏感{params.sadness_sensitivity:.1f}x 愤怒门槛{params.anger_threshold:.1f}x",
            f"  信任基线{params.trust_baseline:+.0f} 期待增长{params.expectation_growth:.1f}x",
            f"· 行为模式：话题{params.proactive_topic} 吃醋{params.jealousy_threshold} 分歧{params.conflict_style} 安慰{params.support_style}",
            f"· 表达风格：吐槽{params.tequila_rate:.0f}% 撒娇{params.sajiao_rate:.0f}% 直白{params.emotional_express:.0f}% 幽默{params.humor_tone}",
            f"· 记忆偏好：回复长度{params.length_preference} 记仇{params.grudge_coefficient:.1f}x 浪漫回忆{params.romantic_memory_weight:.1f}x",
        ]
