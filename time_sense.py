# -*- coding: utf-8 -*-
"""v1.7 时间感知：节假日 + 季节 + 时段提示。

- FESTIVALS：节假日表（公历日期，候选菜关键词；候选落空则仅祝福语，不强推）
- SEASONS：月份 → 季节提示与关键词（命中推荐加权）
- today_context：一次调用返回今日节日/季节上下文
- season_hit / is_fast_dish：单道菜匹配判断
"""

from __future__ import annotations

from datetime import date
from typing import Dict, Optional

# (月, 日, 节日名, 候选菜关键词, 祝福语)
FESTIVALS = (
    (1, 1, "元旦", ("年糕", "饺子"), "新年第一天，吃顿好的"),
    (2, 17, "春节", ("饺子", "年糕", "年夜饭"), "春节快乐，阖家团圆"),
    (3, 3, "元宵节", ("汤圆", "元宵"), "正月十五闹元宵"),
    (6, 19, "端午节", ("粽子", "咸鸭蛋"), "端午安康"),
    (9, 25, "中秋节", ("月饼",), "中秋团圆夜"),
    (12, 21, "冬至", ("饺子", "汤圆"), "冬至大如年"),
)

# 季节: 名 → 月份 / 提示语 / 关键词 / 加权
SEASONS: Dict[str, dict] = {
    "春": {"months": (3, 4, 5), "hint": "春日尝尝时鲜", "keywords": ("春笋", "荠菜", "香椿", "马兰头"), "bonus": 0.1},
    "夏": {"months": (6, 7, 8), "hint": "天热来点解暑的", "keywords": ("绿豆", "酸梅", "凉粉", "冰粉", "西瓜", "冷面"), "bonus": 0.2},
    "秋": {"months": (9, 10, 11), "hint": "秋燥宜润", "keywords": ("银耳", "百合", "雪梨", "莲藕"), "bonus": 0.1},
    "冬": {"months": (12, 1, 2), "hint": "天冷吃点暖身的", "keywords": ("羊肉", "火锅", "砂锅", "炖", "煲"), "bonus": 0.2},
}

FAST_TAGS = ("快手", "快手菜", "懒人")


def _text_of(recipe: dict) -> str:
    parts = [str(recipe.get("name", ""))]
    parts.extend(str(i) for i in recipe.get("ingredients", []))
    parts.extend(str(t) for t in recipe.get("tags", []))
    return " ".join(parts)


def _find_dish(engine, keyword: str) -> Optional[dict]:
    for r in engine.recipes:
        if keyword in _text_of(r):
            return r
    return None


def today_context(engine, now=None) -> dict:
    """今日上下文：{festival, festival_dish, festival_hint, season, season_hint,
    season_bonus, season_keywords}。now 支持 date/datetime/struct_time/时间戳。"""
    if now is None:
        today = date.today()
    elif isinstance(now, (int, float)):
        today = date.fromtimestamp(now)
    elif isinstance(now, tuple):
        today = date(now[0], now[1], now[2])
    elif isinstance(now, date):
        today = now
    else:
        try:
            today = date(now.tm_year, now.tm_mon, now.tm_mday)
        except AttributeError:
            today = date.today()

    ctx = {
        "festival": None,
        "festival_dish": None,
        "festival_hint": "",
        "season": None,
        "season_hint": "",
        "season_bonus": 0.0,
        "season_keywords": (),
    }
    for m, d, name, kws, wish in FESTIVALS:
        if today.month == m and today.day == d:
            ctx["festival"] = name
            ctx["festival_hint"] = wish
            for kw in kws:
                dish = _find_dish(engine, kw)
                if dish is not None:
                    ctx["festival_dish"] = dish["name"]
                    break
            break
    for sname, cfg in SEASONS.items():
        if today.month in cfg["months"]:
            ctx["season"] = sname
            ctx["season_hint"] = cfg["hint"]
            ctx["season_bonus"] = cfg["bonus"]
            ctx["season_keywords"] = cfg["keywords"]
            break
    return ctx


def season_hit(recipe: dict, ctx: dict) -> bool:
    """该菜是否命中当前季节关键词（命中才加权）。"""
    if not ctx.get("season_keywords"):
        return False
    text = _text_of(recipe)
    return any(kw in text for kw in ctx["season_keywords"])


def is_fast_dish(recipe: dict) -> bool:
    """是否快手/懒人菜（tags 含快手/懒人）。"""
    tags = [str(t) for t in recipe.get("tags", [])]
    return any(t in FAST_TAGS for t in tags)
