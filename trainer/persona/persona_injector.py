"""SoulSync - 人格微调：LLM上下文生成"""
from ..trainer_types import PersonaParams


class PersonaInjector:
    def generate(self, params: PersonaParams) -> str:
        if not params:
            return ""
        lines = [
            "[角色人格·训练调制]",
            f"快乐基线 {params.joy_baseline:+.0f} · 悲伤敏感 {params.sadness_sensitivity:.1f}x · 愤怒门槛 {params.anger_threshold:.1f}x",
            f"信任基线 {params.trust_baseline:+.0f} · 期待增长 {params.expectation_growth:.1f}x",
            f"话题主动性 {params.proactive_topic} · 吃醋敏感 {params.jealousy_threshold} · 分歧处理 {params.conflict_style}",
            f"安慰风格 {params.support_style} · 吐槽率 {params.tequila_rate:.0f}% · 撒娇率 {params.sajiao_rate:.0f}%",
            f"情感直白度 {params.emotional_express:.0f}% · 幽默风格 {params.humor_tone} · 回复长度 {params.length_preference}",
            f"记仇系数 {params.grudge_coefficient:.1f}x · 浪漫回忆权重 {params.romantic_memory_weight:.1f}x",
            f"遗忘速度 {params.forget_speed:.1f}x · 稳定度 {params.stability:.0f}%",
        ]
        return "\n".join(lines)