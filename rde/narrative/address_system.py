"""RDE 称谓体系：按阶段返回对用户的称呼方式

阶段 1-2：用「你」；阶段 3-4：偶尔「你啊」；
阶段 5-6：稳定昵称；阶段 7-8：多种称呼+专属爱称；
阶段 9-12：自然随意（含「我的+昵称」式）；
负向：n1「你」/ n2 省略 / n3「那个人」/ n4 不愿提及。
若上下文中提供用户昵称（user_name），中高阶段会生成基于昵称的专属称呼。
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional

from .stage_definitions import StageDefinition, get_stage_definition

_POSITIVE_BY_INDEX = {
    "s1": 0, "s2": 0,
    "s3": 1, "s4": 1,
    "s5": 2, "s6": 2,
    "s7": 3, "s8": 3,
    "s9": 4, "s10": 4,
    "s11": 5, "s12": 5,
}

_NEGATIVE_ADDRESS = {
    "n1": ["你"],
    "n2": ["（省略称呼）", "你"],
    "n3": ["那个人", "（省略称呼）"],
    "n4": ["（不愿提及名字，生硬地省略称呼）"],
}

_NICKNAME_LEVELS: Dict[int, List[str]] = {
    2: ["{name}", "傻瓜{name}", "笨蛋{name}"],
    3: ["宝贝{name}", "{name}", "亲爱的{name}"],
    4: ["宝贝{name}", "亲爱的{name}", "我的{name}"],
    5: ["亲爱的{name}", "我的宝贝{name}", "我的{name}", "{name}"],
}


class AddressSystem:
    """称谓生成器（无状态，线程安全）"""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def get_address(self, stage_id: str, context: Optional[dict] = None) -> str:
        """按阶段返回称呼建议；context 可含 user_name（用户昵称）"""
        if not self.enabled:
            return "你"
        stage: Optional[StageDefinition] = get_stage_definition(stage_id)
        if stage is None:
            return "你"

        user_name = ""
        if context and context.get("user_name"):
            user_name = str(context["user_name"]).strip()
            if len(user_name) > 8:
                user_name = user_name[:8]

        if not stage.positive:
            pool = _NEGATIVE_ADDRESS.get(stage_id, ["你"])
            return pool[0]

        level = _POSITIVE_BY_INDEX.get(stage_id, 0)
        if level == 0:
            return "你"
        pool = _NICKNAME_LEVELS.get(level, ["你"])
        if user_name and level >= 2:
            return random.choice(pool).format(name=user_name)
        fallback = {
            1: "你啊",
            2: "傻瓜",
            3: "宝贝",
            4: "亲爱的",
            5: "我的宝贝",
        }
        return fallback.get(level, "你")

    def address_summary(self, stage_id: str) -> str:
        """返回该阶段称谓体系的文字说明（命令展示用）"""
        stage = get_stage_definition(stage_id)
        if stage is None:
            return "你"
        return stage.address_changes
