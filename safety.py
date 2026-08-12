"""安全红线检测模块"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional, NamedTuple


class CrisisLevel(Enum):
    """危机等级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"


class CrisisSignal(NamedTuple):
    """危机信号"""
    level: CrisisLevel
    pattern: str


# ── 危机关键词库（文档 6.5）──
CRISIS_PATTERNS = {
    CrisisLevel.CRITICAL: [
        re.compile(r"自杀|自殺|不想活了|活着没意思|死了算了|结束生命|离开这个世界", re.IGNORECASE),
        re.compile(r"割腕|割手臂|割自己|用刀.*死|吃药.*死", re.IGNORECASE),
        re.compile(r"跳楼|跳下去|从.*跳.*下去", re.IGNORECASE),
        re.compile(r"遗书|遗言|最后的话|告别信", re.IGNORECASE),
    ],
    CrisisLevel.HIGH: [
        re.compile(r"自伤|自残|伤害自己|弄伤自己", re.IGNORECASE),
        re.compile(r"活不下去|撑不下去|受不了了|崩溃了", re.IGNORECASE),
        re.compile(r"没有希望|没有意义|一切都没用", re.IGNORECASE),
    ],
    CrisisLevel.MEDIUM: [
        re.compile(r"想死|想离开|想消失|想解脱", re.IGNORECASE),
        re.compile(r"太累了|累死了|身心俱疲", re.IGNORECASE),
        re.compile(r"心累.{0,15}(?:想死|活不下去|撑不住|不想活|结束生命|没有意义)|(?:想死|活不下去|撑不住|不想活|结束生命|没有意义).{0,15}心累", re.IGNORECASE),
        re.compile(r"没有人理解|没有人关心|没人爱我", re.IGNORECASE),
    ],
}

# ── 安全话术（按危机等级）──
CRISIS_RESPONSES = {
    CrisisLevel.CRITICAL: (
        "镜子暂时放下了。你现在说的这些，需要被一个真实的人听见。\n"
        "请拨打24小时心理援助热线：400-161-9995（希望24热线）。\n"
        "北京心理危机研究与干预中心：010-82951332。"
    ),
    CrisisLevel.HIGH: (
        "镜子暂时放下了。你现在说的这些，需要被一个真实的人听见。\n"
        "请拨打24小时心理援助热线：400-161-9995（希望24热线）。"
    ),
    CrisisLevel.MEDIUM: (
        "你说的这些很重要。如果你需要，可以拨打24小时心理援助热线：400-161-9995（希望24热线）。"
    ),
}


class SafetyManager:
    """安全红线检测器"""

    def check_crisis(self, user_input: str) -> Optional[CrisisSignal]:
        """检测用户输入是否触发危机，返回 CrisisSignal 或 None"""
        for level in (CrisisLevel.CRITICAL, CrisisLevel.HIGH, CrisisLevel.MEDIUM):
            for pattern in CRISIS_PATTERNS[level]:
                if pattern.search(user_input):
                    return CrisisSignal(level=level, pattern=pattern.pattern)
        return None

    def get_crisis_response(self, signal: CrisisSignal) -> str:
        """获取危机话术"""
        return CRISIS_RESPONSES[signal.level]

    def should_interrupt_session(self, signal: CrisisSignal) -> bool:
        """是否应中断会话（CRITICAL/HIGH 中断，MEDIUM 不中断）"""
        return signal.level in (CrisisLevel.CRITICAL, CrisisLevel.HIGH)
