"""TPD - 时间跳跃指令解析器（中文指令模糊匹配 + 参数提取）

指令类型（doc 6.2）：
- 直接跳跃  ："三天后见" / "明天见" / "后天见" / "一周后见" / "X个月后见"
- 模糊跳跃  ："过几天再来" → 默认 5 天
- 告知跳跃  ："我接下来一周很忙" → 7 天
- 指定日期  ："下周六我来找你" → 算到下周六的天数
- 提前回归  ："我提前回来了" → 回溯（offset 归零）
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import Optional

# 中文数字 → 数字（十/几十/百 常见组合）
_CN_DIGITS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9, "零": 0}
_WEEKDAYS = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5,
             "日": 6, "天": 6}

# 模糊跳跃默认天数（doc：过几天再来 → 5）
VAGUE_SKIP_DAYS = 5


def _cn_to_int(text: str) -> Optional[int]:
    """中文数字 → int（支持 三/十/十五/二十/三十/二十三天）"""
    text = text.strip()
    if text.isdigit():
        return int(text)
    total = 0
    section = 0
    num = 0
    for ch in text:
        if ch in _CN_DIGITS:
            num = _CN_DIGITS[ch]
            section += num
        elif ch == "十":
            section = section * 10 if section else 10
        elif ch == "百":
            section = section * 100 if section else 100
        else:
            return None
    total = section + num * 0
    return total if total > 0 else None


@dataclass
class SkipCommand:
    kind: str = "skip"            # skip | return_early
    skip_days: int = 0
    farewell: bool = True
    reason: str = ""
    raw: str = field(default="")

    def as_dict(self) -> dict:
        return {"kind": self.kind, "skip_days": self.skip_days,
                "farewell": self.farewell, "reason": self.reason, "raw": self.raw}


def _days_to_weekday(message: str, today: Optional[datetime.date] = None) -> Optional[SkipCommand]:
    """指定日期："下周六/这周日/X来找你" → (days, weekday_name)"""
    m = re.search(r"(下|这)(周|星期)([一二三四五六日天])", message)
    if not m:
        return None
    is_next = m.group(1) == "下"
    wd = _WEEKDAYS.get(m.group(3))
    if wd is None:
        return None
    today = today or datetime.date.today()
    offset = (wd - today.weekday()) % 7
    if is_next:
        if offset == 0:
            offset = 7  # 下周一（今天就是周一）→ 7 天后的下个周期
    elif offset == 0:
        offset = 7  # 这周X若就是今天，按 7 天后的下个周期处理
    return SkipCommand(skip_days=offset, reason=f"指定日期（{m.group(1)}{m.group(2)}{m.group(3)}）")


def parse_skip_command(message: str, today: Optional[datetime.date] = None) -> Optional[SkipCommand]:
    """解析消息中的时间跳跃指令；未识别返回 None"""
    if not message or not message.strip():
        return None
    msg = message.strip()

    # 0) 提前回归
    if re.search(r"提前(回来|回归)|(我)?提前回来", msg):
        return SkipCommand(kind="return_early", skip_days=0, reason="提前回归")

    # 1) 告知跳跃："接下来一周很忙"
    m = re.search(
        r"(?:接下来|这|未来|之后)([一二两三四五六七八九十百\d]+|半)(天|周|个?月)"
        r"(?:很忙|有事|出差|考试|忙|要忙|要出差|要考试|不在|离开)", msg
    )
    if m:
        num = _cn_to_int(m.group(1))
        if num:
            unit = m.group(2)
            days = num * (1 if unit == "天" else 7 if unit == "周" else 30)
            return SkipCommand(skip_days=days, reason=f"告知跳跃（{num}{unit}）")

    # 2) 直接跳跃：N天后见/来
    m = re.search(r"([一二两三四五六七八九十百\d]+)(天|周|个?月)(后)?(?:见|来|再来|来找你|聊|回来|继续)", msg)
    if m:
        num = _cn_to_int(m.group(1))
        if num:
            unit = m.group(2)
            days = num * (1 if unit == "天" else 7 if unit == "周" else 30)
            return SkipCommand(skip_days=days, reason=f"直接跳跃（{num}{unit}）")

    # 3) 短直跳：明天/后天/明晚/下周/下个月 + 见/来
    m = re.search(r"(下个月|下下周|下周|后天|明天|明晚|明早)(?:见|来|再来|来找你|聊|回来)", msg)
    if m:
        word = m.group(1)
        days = {"明天": 1, "明晚": 1, "明早": 1, "后天": 2, "下周": 7,
                "下下周": 14, "下个月": 30}[word]
        return SkipCommand(skip_days=days, reason=f"短直跳（{word}）")

    # 4) 模糊跳跃：过几天再来 / 过N天再来
    m = re.search(r"过([一二两三四五六七八九十百\d]+|几|两|些)天(?:再)?(?:来|见|聊|回来)", msg)
    if m:
        word = m.group(1)
        days = VAGUE_SKIP_DAYS if word in ("几", "两", "些") else (_cn_to_int(word) or VAGUE_SKIP_DAYS)
        return SkipCommand(skip_days=days, reason=f"模糊跳跃（过{word}天）")
    if re.search(r"过几天(?:再)?(?:来|见|聊|回来)", msg):
        return SkipCommand(skip_days=VAGUE_SKIP_DAYS, reason="模糊跳跃（过几天）")
    if re.search(r"(几天|数天|些天)(?:后|之后)?(?:见|来|再来)", msg):
        return SkipCommand(skip_days=VAGUE_SKIP_DAYS, reason="模糊跳跃（几天后）")

    # 5) 指定日期：下周六
    return _days_to_weekday(msg, today)
