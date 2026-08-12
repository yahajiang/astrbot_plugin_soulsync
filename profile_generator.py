"""轮廓卡生成器模块（文档 7）"""

from __future__ import annotations

import re
from typing import Optional


# ── 轮廓卡格式模板（文档 7.1）──
PROFILE_HEADER = """╔═══════════════════════════════════════╗
║         📋 镜面轮廓 · 回响             ║
╚═══════════════════════════════════════╝"""

PROFILE_FOOTER = """
─────────────────────────"""


# ── 校验规则 ──
_FORBIDDEN_PATTERNS = [
    re.compile(r"你是.{0,5}型"),  # 禁止"你是XX型"
    re.compile(r"你应该"),        # 禁止建议
    re.compile(r"我建议"),
    re.compile(r"诊断"),
]

_DIMENSION_PATTERN = re.compile(r"●\s*(.+)")
_DIRECTION_PATTERN = re.compile(r"→\s*(.+)")
_TYPE_REF_PATTERN = re.compile(r"隐约指向[：:](.+)")
_CLOSING_QUESTION = re.compile(r"✦\s*.+[？?]$")


def validate_profile(content: str, max_length: int = 0) -> dict:
    """校验轮廓卡内容

    Args:
        content: 轮廓卡文本
        max_length: 最大字数限制，0=不限制

    Returns:
        {"valid": bool, "errors": list[str]}
    """
    errors = []

    # 检查禁止词
    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.search(content):
            errors.append(f"包含禁止词：{pattern.pattern}")

    # 检查字数（0=不限制）
    if max_length > 0:
        clean = re.sub(r"[╔╗║╚═●✦→\s\n]", "", content)
        if len(clean) > max_length:
            errors.append(f"字数超限：{len(clean)} > {max_length}")

    # 检查是否有维度
    if not _DIMENSION_PATTERN.search(content):
        errors.append("缺少维度标记 ●")

    # 检查是否有方向标记
    if not _DIRECTION_PATTERN.search(content):
        errors.append("缺少方向标记 →")

    # 检查是否有类型参考
    if not _TYPE_REF_PATTERN.search(content):
        errors.append("缺少类型参考（隐约指向）")

    # 检查是否有反问收尾
    if not _CLOSING_QUESTION.search(content):
        errors.append("缺少反问收尾 ✦")

    return {"valid": len(errors) == 0, "errors": errors}


def render_profile(content: str) -> str:
    """渲染轮廓卡（加线框标题 + 底部）"""
    return f"{PROFILE_HEADER}\n\n{content}{PROFILE_FOOTER}"


def generate_fallback_profile(
    signals: dict[str, str],
    history: list[tuple[str, str]],
    type_refs: str,
) -> str:
    """降级轮廓卡模板（LLM 不可用时使用）

    仅引用用户原话 + 方向待辨认 + 反问收尾，不出类型结论。
    """
    if not signals:
        # 无信号，给出通用总结
        recent_users = [u for u, a in history[-3:]]
        refs = "、".join([f'"{u}"' for u in recent_users[:3]]) if recent_users else "你刚才说的话"
        return (
            f"● 对话回顾\n"
            f"  你提到了：{refs}\n"
            f"  这些话里藏着你对自己的某种感知。\n"
            f"  → 信号待你辨认\n"
            f"\n"
            f"─────────────────────────\n"
            f"\n"
            f"✦ 这些信号拼在一起，隐约指向：{type_refs}\n"
            f"  但镜子照出的只是影子，轮廓的真相只有你认得。\n"
            f"\n"
            f"✦ 你觉得刚才这些话里，最能代表你的是哪一句？"
        )

    # 有信号，逐维度引用
    lines = []
    for dim, signal in signals.items():
        lines.append(f"● {dim}")
        lines.append(f"  你提到了关于「{dim}」的感受。")
        lines.append(f"  镜子捕捉到一个方向，但轮廓只有你能辨认。")
        lines.append(f"  → {signal}")
        lines.append("")

    lines.append("─────────────────────────")
    lines.append("")
    lines.append(f"✦ 这些信号拼在一起，隐约指向：{type_refs}")
    lines.append("  但镜子照出的只是影子，轮廓的真相只有你认得。")
    lines.append("")
    lines.append("✦ 你觉得刚才这些话里，最能代表你的是哪一句？")

    return "\n".join(lines)
