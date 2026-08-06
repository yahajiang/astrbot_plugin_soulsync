"""TPD - 节气与月相计算（零依赖，纯数学公式）

节气：太阳黄经法。地球绕日运行中太阳视黄经每 15° 一个节气，
返回北京时间日界（00:00-24:00）内首次越界的日期，精度可靠。
月相：朔望月周期法，以 2000-01-06 18:14 UTC 为已知新月历元。
"""

from __future__ import annotations

import datetime
import math
from typing import Optional, Tuple

# 二十四节气：名称 / 太阳黄经 / 出现月份
SOLAR_TERM_NAMES = [
    "小寒", "大寒", "立春", "雨水", "惊蛰", "春分",
    "清明", "谷雨", "立夏", "小满", "芒种", "夏至",
    "小暑", "大暑", "立秋", "处暑", "白露", "秋分",
    "寒露", "霜降", "立冬", "小雪", "大雪", "冬至",
]
SOLAR_TERM_LONGITUDE = [
    285, 300, 315, 330, 345, 0,
    15, 30, 45, 60, 75, 90,
    105, 120, 135, 150, 165, 180,
    195, 210, 225, 240, 255, 270,
]
SOLAR_TERM_MONTH = [
    1, 1, 2, 2, 3, 3,
    4, 4, 5, 5, 6, 6,
    7, 7, 8, 8, 9, 9,
    10, 10, 11, 11, 12, 12,
]

# 季节分界节气索引（立春/立夏/立秋/立冬）
SEASON_START_INDEX = {"春": 2, "夏": 8, "秋": 14, "冬": 20}

# 月相 8 阶段（名称, 图标）
MOON_PHASES = [
    ("新月", "🌑"), ("蛾眉月", "🌒"), ("上弦月", "🌓"), ("盈凸月", "🌔"),
    ("满月", "🌕"), ("亏凸月", "🌖"), ("下弦月", "🌗"), ("残月", "🌘"),
]

NEW_MOON_EPOCH = datetime.datetime(2000, 1, 6, 18, 14)
SYNODIC_MONTH = 29.530588853  # 朔望月平均长度（天）


def _sun_longitude(jd: float) -> float:
    """太阳视黄经（度，0~360），j2000 儒略日"""
    n = jd - 2451545.0
    l = (280.460 + 0.9856474 * n) % 360.0
    g = math.radians((357.528 + 0.9856003 * n) % 360.0)
    return (l + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360.0


def _to_jd(year: int, month: int, day: int, hour: float) -> float:
    """公历 (year,month,day) 的 hour 点（UTC）→ 儒略日"""
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return (
        day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
        + (hour - 12.0) / 24.0
    )


def _shortest_arc(lon: float, target: float) -> float:
    """黄经与目标的短弧差（-180, 180]：负=未到，正=已过"""
    d = (lon - target) % 360.0
    return d - 360.0 if d > 180.0 else d


def solar_term_date(year: int, index: int) -> Tuple[int, int]:
    """返回第 index 个节气在 year 年的 (月, 日)（北京时间日界判定）

    节气日 = 当天 00:00（北京时间）尚未越过目标黄经、24:00 已越过的日期。
    """
    target = SOLAR_TERM_LONGITUDE[index]
    month = SOLAR_TERM_MONTH[index]
    for day in range(1, 32):
        start = _shortest_arc(_sun_longitude(_to_jd(year, month, day - 1, 16.0)), target)
        end = _shortest_arc(_sun_longitude(_to_jd(year, month, day, 16.0)), target)
        if start < 0 <= end:
            return month, day
    raise ValueError(f"节气 {SOLAR_TERM_NAMES[index]} 在 {year} 年未找到（数据越界）")


def solar_term_of(year: int, month: int, day: int) -> Optional[str]:
    """日期所属节气（该日期之前最近一次节气，含当日）"""
    today = (year, month, day)
    best: Optional[Tuple[int, int, int, str]] = None  # (年, 月, 日, 名称)
    for y in (year - 1, year):
        for idx, name in enumerate(SOLAR_TERM_NAMES):
            m, d = solar_term_date(y, idx)
            if (y, m, d) <= today and (best is None or (y, m, d) > best[:3]):
                best = (y, m, d, name)
    return best[3] if best is not None else None


def season_of(year: int, month: int, day: int) -> str:
    """按节气判定季节（立春起为春，立夏起为夏，立秋起为秋，立冬起为冬）"""
    today = (month, day)
    best: Optional[Tuple[int, str]] = None  # (月, 日) 最近的季节起点
    for season, idx in (("春", 2), ("夏", 8), ("秋", 14), ("冬", 20)):
        m, d = solar_term_date(year, idx)
        if (m, d) <= today and (best is None or (m, d) > best[0]):
            best = ((m, d), season)
    return best[1] if best is not None else "冬"


def moon_phase_index(dt: datetime.datetime) -> int:
    """月相 8 阶段索引 0~7（0=新月, 2=上弦月, 4=满月, 6=下弦月）"""
    delta = (dt - NEW_MOON_EPOCH).total_seconds() / 86400.0
    age = delta % SYNODIC_MONTH
    return int(round(age / SYNODIC_MONTH * 8)) % 8


def moon_phase(dt: datetime.datetime) -> Tuple[str, str]:
    """返回 (月相名称, 图标)"""
    return MOON_PHASES[moon_phase_index(dt)]
