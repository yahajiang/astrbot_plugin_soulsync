"""RDE 阶段注入器：按当前阶段生成注入 LLM 的叙事上下文

产出内容：
- 阶段叙事段（style_directive，含关系状态/对话风格/称谓/互动特征/禁忌）
- 近期跃迁/退行提示（若有，说明最近一次阶段变化的叙事背景）
"""
from __future__ import annotations

from typing import List, Optional

from .stage_definitions import StageDefinition, get_stage_definition


class StageInjector:
    """阶段上下文生成器（无状态，线程安全）"""

    # s12 默认措辞（每轮 1~2 次）↔ 强制措辞（100% 每句都带）的替换锚点
    _SOFT_ADDRESS = "每轮回复 1~2 次即可，不要每一句都带称呼"
    _FORCED_ADDRESS = "100% 使用最深情的称呼，可以每一句都带"

    def __init__(self, enabled: bool = True, s12_forced_address: bool = False) -> None:
        self.enabled = enabled
        self.s12_forced_address = s12_forced_address

    def generate_stage_context(
        self,
        stage_id: str,
        user_name: Optional[str] = None,
        recent_transition: Optional[dict] = None,
    ) -> str:
        """生成注入 LLM 的完整阶段叙事上下文（空串表示不注入）"""
        if not self.enabled:
            return ""
        stage = get_stage_definition(stage_id)
        if stage is None:
            return ""

        lines: List[str] = []
        lines.append("【当前关系阶段】")
        if user_name:
            lines.append(f"对方姓名：{user_name}（可用作称呼，未确认的场合不要强加昵称）")
        directive = stage.style_directive
        if stage_id == "s12" and self.s12_forced_address:
            directive = directive.replace(self._SOFT_ADDRESS, self._FORCED_ADDRESS)
        lines.append(directive)
        if stage.taboo:
            lines.append("禁忌：" + "；".join(stage.taboo))
        if recent_transition and recent_transition.get("narrative"):
            lines.append("【关系变化】")
            lines.append(recent_transition["narrative"])
        return "\n".join(lines)

    def get_stage_description(self, stage_id: str) -> str:
        """返回阶段叙事简介（命令展示用）"""
        stage = get_stage_definition(stage_id)
        if stage is None:
            return "未知阶段"
        return (
            f"「{stage.stage_name}」：{stage.relationship_state}。"
            f"对话风格：{stage.dialogue_style}。称谓：{stage.address_changes}。"
            f"互动特征：{stage.interaction_features}。"
        )
