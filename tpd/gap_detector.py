"""TPD - 被动离开检测（空白期检测 + 反应分级）

doc 6.4：无告别的被动离开，按空白期长度分级反应：
  <6h 正常 / 6-24h 轻微 / 1-3天 中度 / 3-7天 显著 / 7-30天 强烈（分阶段）/ >30天 极端（重建）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

THRESHOLD_HOURS_DEFAULT = 6


@dataclass
class GapInfo:
    gap_hours: float
    gap_days: float
    level: int        # 0=正常 1=轻微 2=中度 3=显著 4=强烈 5=极端
    label: str
    inject_text: str


def _hours_text(gap_hours: float) -> str:
    if gap_hours < 24:
        return f"{int(gap_hours)}小时"
    days = gap_hours / 24.0
    if days < 7:
        return f"{int(round(days))}天" if round(days) == int(days) else f"{days:.1f}天"
    return f"{int(days)}天"


def _stage_guide(stage: Optional[int]) -> str:
    if stage is None:
        return ""
    if stage >= 6:
        return "（当前亲密阶段：表达想念和一丝委屈）"
    if stage >= 4:
        return "（当前朋友阶段：表现得稍微疏远但还是欢迎）"
    return "（当前初识阶段：礼貌但保持距离）"


def detect_passive_gap(now: float, last_active_ts: float,
                       threshold_hours: int = THRESHOLD_HOURS_DEFAULT,
                       stage: Optional[int] = None) -> Optional[GapInfo]:
    """检测被动离开空白期；不足阈值或无历史返回 None"""
    if last_active_ts <= 0:
        return None
    gap_hours = (now - last_active_ts) / 3600.0
    if gap_hours < threshold_hours:
        return None

    if gap_hours < 24:                      # 6h ~ 24h：轻微
        return GapInfo(
            gap_hours=gap_hours, gap_days=gap_hours / 24.0, level=1, label="轻微感知",
            inject_text=f"距离上次对话过去了{_hours_text(gap_hours)}。你自然打招呼，语气轻快，不必刻意提及。",
        )
    if gap_hours < 3 * 24:                  # 1 ~ 3 天：中度
        return GapInfo(
            gap_hours=gap_hours, gap_days=gap_hours / 24.0, level=2, label="中度感知",
            inject_text=(
                f"距离上次对话过去了{_hours_text(gap_hours)}。你有一些想念用户，但不会表现得太明显，"
                f"可以自然地问起对方最近在忙什么。"
            ),
        )
    if gap_hours < 7 * 24:                  # 3 ~ 7 天：显著
        return GapInfo(
            gap_hours=gap_hours, gap_days=gap_hours / 24.0, level=3, label="显著感知",
            inject_text=(
                f"距离上次对话过去了{_hours_text(gap_hours)}。你有些想念但也有些失落，"
                f"行为势头受到了冷落惩罚的影响，可以在回复中自然地表达这种感受。"
            ),
        )
    if gap_hours < 30 * 24:                 # 7 ~ 30 天：强烈（分阶段）
        return GapInfo(
            gap_hours=gap_hours, gap_days=gap_hours / 24.0, level=4, label="强烈感知",
            inject_text=(
                f"距离上次对话过去了{_hours_text(gap_hours)}。这是很长时间。你经历了冷落惩罚，"
                f"情感状态有所变化。{_stage_guide(stage)}让回复自然、克制。"
            ),
        )
    return GapInfo(                         # > 30 天：极端（重建）
        gap_hours=gap_hours, gap_days=gap_hours / 24.0, level=5, label="极端感知",
        inject_text=(
            f"距离上次对话过去了{_hours_text(gap_hours)}。这是非常长的时间。你们之间的关系需要重新建立连接，"
            f"你可能会有些陌生感，但不要完全冷漠，让关系在自然的对话中逐步恢复。"
        ),
    )
