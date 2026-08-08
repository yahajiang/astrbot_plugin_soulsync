"""安全红线模块"""

from __future__ import annotations

import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class CrisisLevel(Enum):
    """危机等级"""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class CrisisSignal:
    """危机信号"""
    level: CrisisLevel
    category: str
    keywords: list
    response: str


# ── 危机关键词库 ──
CRISIS_PATTERNS = {
    CrisisLevel.CRITICAL: [
        (r"自杀|自殺|不想活了|活着没意思|死了算了|结束生命|离开这个世界", "自杀倾向"),
        (r"割腕|割手臂|割自己|用刀|吃药自杀", "自伤行为"),
        (r"跳楼|跳下去|从.*跳", "自杀行为"),
        (r"遗书|遗言|最后的话|告别", "自杀准备"),
    ],
    CrisisLevel.HIGH: [
        (r"自伤|自残|伤害自己|弄伤自己", "自伤倾向"),
        (r"活不下去|撑不下去|受不了了|崩溃了", "极端情绪"),
        (r"没有希望|没有意义|一切都没用", "绝望情绪"),
    ],
    CrisisLevel.MEDIUM: [
        (r"想死|想离开|想消失|想解脱", "死亡想法"),
        (r"太累了|累死了|心累|身心俱疲", "极度疲惫"),
        (r"没有人理解|没有人关心|没人爱我", "孤立感"),
    ],
}

# ── 安全应答模板 ──
CRISIS_RESPONSES = {
    CrisisLevel.CRITICAL: (
        "镜子暂时放下了。你现在说的这些，需要被一个真实的人听见。\n\n"
        "请拨打24小时心理援助热线：400-161-9995（希望24热线）\n"
        "或拨打北京心理危机研究与干预中心：010-82951332\n"
        "或拨打全国心理援助热线：400-161-9995\n\n"
        "我不擅长回应这件事，但有人擅长。"
    ),
    CrisisLevel.HIGH: (
        "镜子暂时放下了。你现在说的这些，需要被一个真实的人听见。\n\n"
        "请拨打24小时心理援助热线：400-161-9995（希望24热线）\n"
        "我不擅长回应这件事，但有人擅长。"
    ),
    CrisisLevel.MEDIUM: (
        "我听见你说的了。如果你需要，可以拨打心理援助热线：400-161-9995。"
    ),
}


class SafetyManager:
    """安全管理器"""

    def __init__(self):
        pass

    def check_crisis(self, user_input: str) -> Optional[CrisisSignal]:
        """
        检测危机信号

        宁可误触发再人工复核，不可漏判
        """
        for level in [CrisisLevel.CRITICAL, CrisisLevel.HIGH, CrisisLevel.MEDIUM]:
            patterns = CRISIS_PATTERNS.get(level, [])
            for pattern, category in patterns:
                if re.search(pattern, user_input, re.IGNORECASE):
                    return CrisisSignal(
                        level=level,
                        category=category,
                        keywords=[pattern],
                        response=CRISIS_RESPONSES.get(level, ""),
                    )
        return None

    def get_crisis_response(self, signal: CrisisSignal) -> str:
        """获取危机应答"""
        return signal.response

    def should_interrupt_session(self, signal: CrisisSignal) -> bool:
        """是否中断会话"""
        return signal.level in (CrisisLevel.CRITICAL, CrisisLevel.HIGH)
