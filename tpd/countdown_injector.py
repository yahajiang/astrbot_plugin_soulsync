"""TPD - 倒计时注入（生成 LLM 注入文本）

doc 5.4 格式：
- 单事件：[倒计时感知] 距离「认识一周年」还有 3 天。行为指导…
- 多事件：[倒计时感知 - 多事件] 当前活跃倒计时列表 + 优先提及
"""

from __future__ import annotations

import datetime
from typing import List, Optional

from .countdown_calculator import CountdownEvent
from .countdown_narrator import KIND_ICONS, day_label, stage_hint, stage_of


def build_countdown_info(top: CountdownEvent, others: Optional[List[CountdownEvent]] = None,
                         today: Optional[datetime.date] = None) -> str:
    """生成倒计时注入文本；others 为可顺带带出的其他事件（≤3 个）"""
    today = today or datetime.date.today()
    stage, _ = stage_of(top.days_left)
    icon = KIND_ICONS.get(top.kind, "📌")
    if top.days_left == 0:
        when = "就是今天"
    elif top.days_left == 1:
        when = "还有 1 天"
    elif top.days_left > 0:
        when = f"还有 {top.days_left} 天"
    else:
        when = f"已经过去 {-top.days_left} 天"
    lines = [f"[倒计时感知] {icon}距离「{top.name}」{when}（{day_label(top.days_left, today)}）。"]
    hint = stage_hint(top.kind, stage)
    if hint:
        lines.append(hint)

    others = [o for o in (others or []) if o.key != top.key][:3]
    if others:
        lines.append("[倒计时感知 - 多事件] 当前活跃倒计时：")
        entries = []
        for o in others:
            label = day_label(o.days_left, today)
            entries.append(f"  {KIND_ICONS.get(o.kind, '📌')} {o.name}：T{o.days_left:+.0f}（{label}）")
        lines.extend(entries)
        lines.append(f"优先提及：{top.name}（最近且最重要）")
        lines.append("其他倒计时：在合适话题中自然带出，不要生硬堆砌。")
    return "\n".join(lines)
