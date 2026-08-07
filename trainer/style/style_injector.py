"""SoulSync - 语言风格：LLM上下文注入（阶段差异化）"""
from ..trainer_types import LanguageProfile, StyleState


PHASE_DESC = {
    "collection": "正在默默学习你的表达习惯，暂时保持原有风格",
    "adoption": "逐渐融入你的语言特征，融合度{fusion_ratio:.0f}%，保留角色底色",
    "fused": "已形成混合风格，融合度100%，角色表达自然贴合你的习惯",
}


class StyleInjector:
    def generate(self, state: StyleState) -> str:
        if not state or not state.profile:
            return ""
        # v2.21 融合度≥90%：风格已内化，不再注入（节省每轮 token）
        if state.fusion_ratio >= 0.9:
            return ""
        p = state.profile
        phase_desc = PHASE_DESC.get(state.phase, "").format(fusion_ratio=state.fusion_ratio * 100)
        lock_tag = " · 🔒 已锁定" if state.locked else ""
        lines = [
            "[语言风格·用户习惯]",
            f"阶段：{state.phase} 融合度{state.fusion_ratio:.0%}{lock_tag}",
            f"（{phase_desc}）",
            f"平均句长{p.avg_length:.0f}字 · 正式度{p.formality_score:.0%} · 直白度{p.directness_score:.0%}",
        ]
        return "\n".join(lines)