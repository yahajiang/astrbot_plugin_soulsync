"""后处理器模块（文档 6.4）"""

from __future__ import annotations

from typing import Optional

from .safety import SafetyManager, CrisisSignal


# ── 建议检测词 ──
_SUGGESTION_PATTERNS = ["你应该", "我建议", "最好", "可以试试", "推荐"]
_SUGGESTION_REPLACEMENT = "有没有想过"


def ensure_question_mark(reply: str) -> str:
    """确保回复以 ？ 结尾（文档 F-10：每轮回复 100% 以？结尾）"""
    if not reply:
        return reply
    if reply.endswith(("？", "?")):
        return reply
    # 句末标点替换为问号
    for sep in ["。", "！", ".", "!"]:
        if reply.endswith(sep):
            return reply[:-1] + "？"
    return reply + "？"


def truncate(reply: str, user_input: str, max_ratio: float = 0) -> str:
    """截断回复（max_ratio=0 时不限制）"""
    if max_ratio <= 0:
        return reply
    max_len = int(len(user_input) * max_ratio)
    if len(reply) <= max_len:
        return reply

    # 在最后一个句号/问号处截断
    truncated = reply[:max_len]
    for sep in ["。", "？", "！", ".", "?", "!"]:
        if sep in truncated:
            truncated = truncated[:truncated.rfind(sep) + 1]
            break

    return truncated


def replace_suggestions(reply: str) -> str:
    """替换建议性措辞"""
    for pattern in _SUGGESTION_PATTERNS:
        if pattern in reply:
            reply = reply.replace(pattern, _SUGGESTION_REPLACEMENT)
    return reply


def process(
    reply: str,
    user_input: str,
    safety_manager: SafetyManager,
    max_output_ratio: float = 0,
) -> str:
    """后处理管道（文档 6.4 完整流程）"""
    if not reply:
        return reply

    # 安全过滤（优先级最高）
    crisis = safety_manager.check_crisis(user_input)
    if crisis:
        return safety_manager.get_crisis_response(crisis)

    # 强制截断
    reply = truncate(reply, user_input, max_ratio=max_output_ratio)

    # 建议替换
    reply = replace_suggestions(reply)

    # 强制补问号
    reply = ensure_question_mark(reply)

    return reply
