"""SoulSync - 语言风格：LLM上下文注入"""
from ..trainer_types import LanguageProfile, StyleState


class StyleInjector:
    def generate(self, state: StyleState) -> str:
        if not state or not state.profile:
            return ""
        p = state.profile
        lines = ["[语言风格·用户习惯]"]
        if state.phase == "collection":
            lines.append("（正在学习用户的表达习惯，暂不改变角色语言风格）")
        elif state.phase == "adoption":
            lines.append(f"（融合度 {state.fusion_ratio:.0f}%，逐步融入用户语言特征）")
        elif state.phase == "fused":
            lines.append("（已形成混合风格，角色表达与用户习惯自然融合）")
        lines.append(f"平均句长 {p.avg_length:.0f}字 · 正式度 {p.formality_score:.0%} · 直白度 {p.directness_score:.0%}")
        return "\n".join(lines)