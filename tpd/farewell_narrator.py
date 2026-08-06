"""TPD - 告别叙事生成（跳跃指令确认后的 LLM 注入文本）"""

from __future__ import annotations

from typing import List

from .skip_parser import SkipCommand


def generate_farewell_context(cmd: SkipCommand, target_date: str,
                              late_celebrations: List[str]) -> str:
    """告别注入文本（doc 6.3 Step3）"""
    days = cmd.skip_days
    lines = [
        "[时间跳跃·告别]",
        f"用户即将离开{days}天（回来时是 {target_date}）。",
        "你要做一个自然的告别：表达期待但也有些不舍。",
        "不要过于夸张，保持你的性格。",
    ]
    if late_celebrations:
        names = "、".join(late_celebrations)
        lines.append(f"注意：离开期间会经过「{names}」，可以在告别时自然提醒，约定回来后补庆。")
    return "\n".join(lines)
