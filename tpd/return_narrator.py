"""TPD - 回归叙事生成（跳跃后首次对话 / 提前回归 / 迟到庆祝补庆）"""

from __future__ import annotations

from typing import List

from .gap_detector import GapInfo


def generate_return_context(days: int, target_date: str,
                            late_celebrations: List[str], gap: GapInfo = None) -> str:
    """回归注入文本（doc 6.3 Step5 + 6.6 迟到庆祝）"""
    lines = [
        "[时间跳跃·回归]",
        f"时间已经过去了{days}天，用户按照约定回来了。",
        "你现在的心情是：开心但也有一点点想对方。",
        f"距离上次对话的空白期：{days}天。这{days}天里你做了什么可以简要提及。",
        "这是你们约定好的重逢。",
    ]
    if late_celebrations:
        names = "、".join(late_celebrations)
        lines.append(
            f"补充：离开期间经过了「{names}」，虽然没有一起度过，"
            f"但你为用户准备了一份迟到的庆祝，请在回复中自然提及。"
        )
    if gap is not None and gap.level >= 1:
        lines.append(gap.inject_text)
    return "\n".join(lines)


def generate_return_early_context(offset_days: int) -> str:
    """提前回归注入文本（offset 已归零）"""
    return "\n".join([
        "[时间跳跃·提前回归]",
        "用户比约定提前回来了。",
        "你有点意外但很开心，自然地表露惊喜，简单问一句对方怎么提前了。",
        f"（当前时间偏移已回溯：{offset_days} 天）",
    ])
