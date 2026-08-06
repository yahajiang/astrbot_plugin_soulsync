"""SoulSync - 人格微调：LLM上下文生成"""
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


class PersonaInjector:
    def generate(self, params: PersonaParams) -> str:
        if not params:
            return ""
        stage = _stage_label(params.stability)
        lock_tag = "🔒 已锁定" if params.locked else ""
        lines = [
            "[角色人格·训练调制]",
            f"训练阶段：{stage} 稳定度{params.stability:.0f}% 累计{params.total_training_turns}轮 {lock_tag}".strip(),
            f"· 情感倾向：快乐基线{params.joy_baseline:+.0f} 悲伤敏感{params.sadness_sensitivity:.1f}x 愤怒门槛{params.anger_threshold:.1f}x",
            f"  信任基线{params.trust_baseline:+.0f} 期待增长{params.expectation_growth:.1f}x",
            f"· 行为模式：话题{params.proactive_topic} 吃醋{params.jealousy_threshold} 分歧{params.conflict_style} 安慰{params.support_style}",
            f"· 表达风格：吐槽{params.tequila_rate:.0f}% 撒娇{params.sajiao_rate:.0f}% 直白{params.emotional_express:.0f}% 幽默{params.humor_tone}",
            f"· 记忆偏好：回复长度{params.length_preference} 记仇{params.grudge_coefficient:.1f}x 浪漫回忆{params.romantic_memory_weight:.1f}x",
        ]
        return "\n".join(lines)