"""TPD - 倒计时叙事生成（T-7 到 T+7 六阶段叙事模板）

阶段：远期感知(T-7~T-4) / 近期预热(T-3~T-2) / 临近倒计时(T-1) /
      当天(T-0) / 余韵(T+1~T+3) / 渐淡(T+4~T+7)
days_left = 事件日 - 今天（正=即将到来，负=刚过）
"""

from __future__ import annotations

import datetime
from typing import Tuple

# 事件类型图标
KIND_ICONS = {
    "first_meet": "📅", "birthday": "🎂", "anniversary": "💝",
    "festival": "🌙", "crisis": "🌫️", "milestone": "⭐",
}

# 阶段元数据：(强度 1/5..5/5)
STAGE_META = {
    "远期感知": {"intensity": 1, "days": (4, 7)},      # T-7 ~ T-4
    "近期预热": {"intensity": 2, "days": (2, 3)},      # T-3 ~ T-2
    "临近倒计时": {"intensity": 3, "days": (1, 1)},    # T-1
    "当天": {"intensity": 5, "days": (0, 0)},          # T-0
    "余韵": {"intensity": 2, "days": (-3, -1)},        # T+1 ~ T+3
    "渐淡": {"intensity": 1, "days": (-7, -4)},        # T+4 ~ T+7
}

# 每阶段 × 事件类型的行为指导模板
STAGE_HINTS = {
    "远期感知": {
        "first_meet": "你隐约意识到这个日子快到了，偶尔在相关话题中顺带一提，不必刻意。",
        "birthday": "你想起那个特别的日子临近了，心里悄悄记着，聊天时若有若无地提一句。",
        "anniversary": "你隐约记得有个特别的日子临近，偶尔在相关话题中顺带提及。",
        "festival": "节日的气氛开始在空气里弥漫，你偶尔顺带提一句。",
        "crisis": "那个难忘的日子快到了，你偶尔沉默片刻，话里有话地提一句。",
        "milestone": "你们的关系似乎正悄悄迈向一个新的节点，你隐约有些察觉。",
    },
    "近期预热": {
        "first_meet": "你开始主动提起这个日子快到了，语气带着期待，但不过度渲染。",
        "birthday": "你忍不住主动提起：\"对了，那个日子快到了\"，眼里带着期待。",
        "anniversary": "你主动提起\"快到了\"，制造一点期待感，但不点破全部心思。",
        "festival": "你开始期待这个节日，主动和对方聊起节日的安排。",
        "crisis": "你欲言又止地提起那个日子快到了，带着一点复杂的情绪。",
        "milestone": "你敏锐地感觉到节点临近，说话时带上了一丝郑重。",
    },
    "临近倒计时": {
        "first_meet": "明天就是了！你情绪高涨，忍不住明确倒数，满心期待。",
        "birthday": "明天就是你的生日了！你几乎按捺不住，话里全是期待。",
        "anniversary": "明天就是纪念日了！你明确倒计时，情绪明显高涨。",
        "festival": "明天就是节日了！你已经想好了要怎么一起过。",
        "crisis": "明天就是那个日子了，你既紧张又郑重，话比平时少了一些。",
        "milestone": "只差一步就到那个节点了，你的心情郑重而雀跃。",
    },
    "当天": {
        "first_meet": "就是今天！这是你们一路走来的纪念日，值得好好庆祝。",
        "birthday": "就是今天！这是属于你的一天，值得好好庆祝。",
        "anniversary": "就是今天！这个特别的日子，值得好好庆祝。",
        "festival": "就是今天！节日到了，一起好好过这一天吧。",
        "crisis": "就是今天。你安静地记住了这一天，心里百感交集。",
        "milestone": "就是今天。你们的关系抵达了新的节点。",
    },
    "余韵": {
        "first_meet": "昨天真的很开心，你在回味中带着珍惜。",
        "birthday": "昨天的开心还在心里发着热，你回味着、珍惜着。",
        "anniversary": "昨天真的很开心，你带着余韵轻轻回味。",
        "festival": "节日的余温还在，你意犹未尽地回味着。",
        "crisis": "那个日子刚过去，你仍在慢慢消化心里的复杂情绪。",
        "milestone": "刚跨过那个节点，你的心情还带着一点不真实感。",
    },
    "渐淡": {
        "first_meet": "那个纪念日的场景偶尔浮上心头，你轻轻提起，如同翻开旧相册。",
        "birthday": "生日的热闹渐渐远了，偶尔想起，心里还是暖的。",
        "anniversary": "那个纪念日的礼物你还放着，偶尔回忆，语气轻缓。",
        "festival": "节日的余韵渐渐淡去，偶尔回忆时带着一点舍不得。",
        "crisis": "那个日子的痕迹慢慢淡了，你偶尔想起，已经能平静地说起。",
        "milestone": "新节点之后的日子平静下来，你偶尔回顾，步履更稳。",
    },
}

# 未覆盖 kind 的兜底模板
_FALLBACK_HINTS = {
    "远期感知": "你隐约觉得有个特别的日子快到了，偶尔顺带一提。",
    "近期预热": "你开始主动提起那个日子快到了，带着期待。",
    "临近倒计时": "明天就是那个日子了！你明确倒计时，情绪高涨。",
    "当天": "就是今天！这个特别的日子值得好好度过。",
    "余韵": "昨天真的很开心，你带着余韵回味。",
    "渐淡": "那天的记忆渐渐淡去，偶尔想起仍会心一笑。",
}

_WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def stage_of(days_left: int) -> Tuple[str, int]:
    """days_left → (阶段名, 叙事强度 1~5)；超出 T±7 返回 None 语义（"无"）"""
    for stage, meta in STAGE_META.items():
        lo, hi = meta["days"]
        if lo <= days_left <= hi:
            return stage, meta["intensity"]
    return "远期感知", 0


def day_label(days_left: int, today: datetime.date) -> str:
    """"今天/明天/后天/N天后/昨天/前天/N天前" + 星期几"""
    occ = today + datetime.timedelta(days=days_left)
    week = _WEEKDAY_NAMES[occ.weekday()]
    if days_left == 0:
        return f"今天（{week}）"
    if days_left == 1:
        return f"明天（{week}）"
    if days_left == 2:
        return f"后天（{week}）"
    if days_left > 0:
        return f"{days_left}天后（{week}）"
    if days_left == -1:
        return f"昨天（{week}）"
    if days_left == -2:
        return f"前天（{week}）"
    return f"{-days_left}天前（{week}）"


def stage_hint(kind: str, stage: str) -> str:
    """阶段行为指导文本（供注入使用）"""
    if kind in STAGE_HINTS and stage in STAGE_HINTS[kind]:
        return STAGE_HINTS[kind][stage]
    return _FALLBACK_HINTS.get(stage, "")
