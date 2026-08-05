"""SoulSync - 纪念日/节日系统

功能：
- 用户自定义纪念日（年循环 MM-DD）、生日
- 首次互动纪念（自动记录）+ 认识天数里程碑（7/30/50/100/200/365... 天）
- 全球节日（内置公历节日 + 农历节日自动换算 + 管理员可增删）
- 触发当天给予好感/亲密度奖励，并注入 LLM 上下文提示
- 每个用户每天最多触发一次（防刷屏）
"""

from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ─── 农历数据表（1900-2100）─────────────────────────────────────
# 每个 int 的二进制位编码了该农历年的信息：
#   0x8000 起 12 位：每月（1-12 月）天数，1 = 30 天，0 = 29 天
#   低 4 位：闰月序号（0 = 无闰月）
#   0x10000：闰月是否为 30 天（1 = 闰月 30 天，0 = 29 天）
_LUNAR_INFO = [
    0x04bd8, 0x04ae0, 0x0a570, 0x054d5, 0x0d260, 0x0d950, 0x16554, 0x056a0, 0x09ad0, 0x055d2,
    0x04ae0, 0x0a5b6, 0x0a4d0, 0x0d250, 0x1d255, 0x0b540, 0x0d6a0, 0x0ada2, 0x095b0, 0x14977,
    0x04970, 0x0a4b0, 0x0b4b5, 0x06a50, 0x06d40, 0x1ab54, 0x02b60, 0x09570, 0x052f2, 0x04970,
    0x06566, 0x0d4a0, 0x0ea50, 0x06e95, 0x05ad0, 0x02b60, 0x186e3, 0x092e0, 0x1c8d7, 0x0c950,
    0x0d4a0, 0x1d8a6, 0x0b550, 0x056a0, 0x1a5b4, 0x025d0, 0x092d0, 0x0d2b2, 0x0a950, 0x0b557,
    0x06ca0, 0x0b550, 0x15355, 0x04da0, 0x0a5b0, 0x14573, 0x052b0, 0x0a9a8, 0x0e950, 0x06aa0,
    0x0aea6, 0x0ab50, 0x04b60, 0x0aae4, 0x0a570, 0x05260, 0x0f263, 0x0d950, 0x05b57, 0x056a0,
    0x096d0, 0x04dd5, 0x04ad0, 0x0a4d0, 0x0d4d4, 0x0d250, 0x0d558, 0x0b540, 0x0b5a0, 0x195a6,
    0x095b0, 0x049b0, 0x0a974, 0x0a4b0, 0x0b27a, 0x06a50, 0x06d40, 0x0af46, 0x0ab60, 0x09570,
    0x04af5, 0x04970, 0x064b0, 0x074a3, 0x0ea50, 0x06b58, 0x055c0, 0x0ab60, 0x096d5, 0x092e0,
    0x0c960, 0x0d954, 0x0d4a0, 0x0da50, 0x07552, 0x056a0, 0x0abb7, 0x025d0, 0x092d0, 0x0cab5,
    0x0a950, 0x0b4a0, 0x0baa4, 0x0ad50, 0x055d9, 0x04ba0, 0x0a5b0, 0x15176, 0x052b0, 0x0a930,
    0x07954, 0x06aa0, 0x0ad50, 0x05b52, 0x04b60, 0x0a6e6, 0x0a4e0, 0x0d260, 0x0ea65, 0x0d530,
    0x05aa0, 0x076a3, 0x096d0, 0x04afb, 0x04ad0, 0x0a4d0, 0x1d0b6, 0x0d250, 0x0d520, 0x0dd45,
    0x0b5a0, 0x056d0, 0x055b2, 0x049b0, 0x0a577, 0x0a4b0, 0x0aa50, 0x1b255, 0x06d20, 0x0ada0,
    0x14b63, 0x09370, 0x049f8, 0x04970, 0x064b0, 0x168a6, 0x0ea50, 0x06b20, 0x1a6c4, 0x0aae0,
    0x092e0, 0x0d2e3, 0x0c960, 0x0d557, 0x0d4a0, 0x0da50, 0x05d55, 0x056a0, 0x0a6d0, 0x055d4,
    0x052d0, 0x0a9b8, 0x0a950, 0x0b4a0, 0x0b6a6, 0x0ad50, 0x055a0, 0x0aba4, 0x0a5b0, 0x052b0,
    0x0b273, 0x06930, 0x07337, 0x06aa0, 0x0ad50, 0x14b55, 0x04b60, 0x0a570, 0x054e4, 0x0d160,
    0x0e968, 0x0d520, 0x0daa0, 0x16aa6, 0x056d0, 0x04ae0, 0x0a9d4, 0x0a2d0, 0x0d150, 0x0f252,
    0x0d520,
]

_BASE_DATE = date(1900, 1, 31)  # 1900-01-31 = 农历1900年正月初一


def _leap_month(year: int) -> int:
    """返回农历年的闰月序号（0 = 无闰月）"""
    return _LUNAR_INFO[year - 1900] & 0xF


def _leap_days(year: int) -> int:
    """闰月天数"""
    if _leap_month(year) == 0:
        return 0
    return 30 if _LUNAR_INFO[year - 1900] & 0x10000 else 29


def _month_days(year: int, month: int) -> int:
    """农历某年某月（非闰月）的天数"""
    return 30 if _LUNAR_INFO[year - 1900] & (0x10000 >> month) else 29


def _year_days(year: int) -> int:
    """农历年总天数"""
    info = _LUNAR_INFO[year - 1900]
    total = 348
    for m in range(1, 13):
        if info & (0x10000 >> m):
            total += 1
    return total + _leap_days(year)


def lunar_to_solar(
    lunar_year: int, lunar_month: int, lunar_day: int, is_leap: bool = False
) -> Optional[Tuple[int, int, int]]:
    """农历转公历，返回 (year, month, day)；超出范围返回 None"""
    if not (1900 <= lunar_year <= 2100):
        return None
    if not (1 <= lunar_month <= 12 and 1 <= lunar_day <= 30):
        return None
    leap = _leap_month(lunar_year)
    offset = 0
    for y in range(1900, lunar_year):
        offset += _year_days(y)
    for m in range(1, lunar_month):
        offset += _month_days(lunar_year, m)
        if leap and m == leap and not is_leap:
            offset += _leap_days(lunar_year)
    if is_leap and leap == lunar_month:
        offset += _leap_days(lunar_year)
    offset += lunar_day - 1
    dt = _BASE_DATE + timedelta(days=offset)
    return dt.year, dt.month, dt.day


def solar_to_lunar(
    solar_year: int, solar_month: int, solar_day: int
) -> Optional[dict]:
    """公历转农历，返回 {year, month, day, is_leap}；超出范围返回 None"""
    try:
        target = date(solar_year, solar_month, solar_day)
    except ValueError:
        return None
    if target < _BASE_DATE:
        return None
    offset = (target - _BASE_DATE).days
    ly = 1900
    while offset >= _year_days(ly):
        offset -= _year_days(ly)
        ly += 1
    if ly > 2100:
        return None
    leap = _leap_month(ly)
    is_leap = False
    i = 1
    while i <= 12:
        if leap > 0 and i == leap + 1 and not is_leap:
            i -= 1
            is_leap = True
            days = _leap_days(ly)
        else:
            days = _month_days(ly, i)
        if offset < days:
            return {"year": ly, "month": i, "day": offset + 1, "is_leap": is_leap}
        offset -= days
        if is_leap and i == leap + 1:
            is_leap = False
        i += 1
    return None


def parse_month_day(text: str) -> Optional[Tuple[int, int]]:
    """解析日期文本（支持 05-20 / 5-20 / 5月20日 / 05/20），返回 (month, day)"""
    m = re.fullmatch(
        r"\s*(\d{1,2})\s*[-/年月.]\s*(\d{1,2})\s*(?:日|号)?\s*", text.strip()
    )
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return month, day


def _next_occurrence(month: int, day: int, today: date) -> Optional[date]:
    """下一个 MM-DD 日期（含今天）"""
    for year in (today.year, today.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            continue
        if d >= today:
            return d
    return None


# ─── 内置节日 ────────────────────────────────────────────────────
# (名称, 月, 日, 是否农历)
DEFAULT_FESTIVALS: List[Tuple[str, int, int, bool]] = [
    ("元旦", 1, 1, False),
    ("情人节", 2, 14, False),
    ("妇女节", 3, 8, False),
    ("植树节", 3, 12, False),
    ("愚人节", 4, 1, False),
    ("劳动节", 5, 1, False),
    ("青年节", 5, 4, False),
    ("儿童节", 6, 1, False),
    ("建党节", 7, 1, False),
    ("建军节", 8, 1, False),
    ("教师节", 9, 10, False),
    ("国庆节", 10, 1, False),
    ("万圣节", 10, 31, False),
    ("双十一", 11, 11, False),
    ("平安夜", 12, 24, False),
    ("圣诞节", 12, 25, False),
    ("春节", 1, 1, True),
    ("元宵节", 1, 15, True),
    ("龙抬头", 2, 2, True),
    ("端午节", 5, 5, True),
    ("七夕节", 7, 7, True),
    ("中元节", 7, 15, True),
    ("中秋节", 8, 15, True),
    ("重阳节", 9, 9, True),
    ("腊八节", 12, 8, True),
    ("小年", 12, 23, True),
    ("除夕", 12, 30, True),
]

# 认识天数里程碑（达到当天触发奖励）
DAY_MILESTONES = [7, 30, 50, 100, 200, 365, 500, 1000, 1500, 2000, 3000]


class AnniversaryManager:
    """纪念日/节日管理器（落盘存储）"""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.anniversaries: Dict[str, List[dict]] = {}   # uid -> [{name, month, day, kind, created_ts}]
        self.first_meet: Dict[str, str] = {}             # uid -> "YYYY-MM-DD"
        self.festivals: List[dict] = []                  # [{name, month, day, lunar}]
        self.last_bonus_date: Dict[str, str] = {}        # uid -> "YYYY-MM-DD"（当日已发过奖励）
        self._load()

    # ── 数据加载/保存 ──
    def _load(self):
        f = self.data_dir / "anniversaries.json"
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                self.anniversaries = data.get("anniversaries", {})
                self.first_meet = data.get("first_meet", {})
                self.festivals = data.get("festivals", [])
                self.last_bonus_date = data.get("last_bonus_date", {})
            except Exception:
                pass
        if not self.festivals:
            self.festivals = [
                {"name": n, "month": m, "day": d, "lunar": l}
                for n, m, d, l in DEFAULT_FESTIVALS
            ]

    def save(self):
        f = self.data_dir / "anniversaries.json"
        try:
            data = {
                "anniversaries": self.anniversaries,
                "first_meet": self.first_meet,
                "festivals": self.festivals,
                "last_bonus_date": self.last_bonus_date,
            }
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ── 首次互动 ──
    def ensure_first_meet(self, uid: str, ts: Optional[float] = None):
        """确保用户有首次互动记录"""
        if uid in self.first_meet:
            return
        d = date.fromtimestamp(ts or time.time())
        self.first_meet[uid] = d.isoformat()
        self.save()

    # ── 用户纪念日 ──
    def add_anniversary(
        self, uid: str, name: str, month: int, day: int, kind: str = "anniversary"
    ) -> Tuple[bool, str]:
        if not name.strip():
            return False, "纪念日名称不能为空"
        items = self.anniversaries.setdefault(uid, [])
        if any(a["name"] == name for a in items):
            return False, f"已存在同名纪念日「{name}」"
        items.append({
            "name": name.strip(),
            "month": month,
            "day": day,
            "kind": kind,
            "created_ts": time.time(),
        })
        self.save()
        label = "生日" if kind == "birthday" else "纪念日"
        return True, f"✅ 已记录{label}「{name}」（{month:02d}-{day:02d}）"

    def remove_anniversary(self, uid: str, name: str) -> Tuple[bool, str]:
        items = self.anniversaries.get(uid, [])
        for a in items:
            if a["name"] == name:
                items.remove(a)
                self.save()
                return True, f"✅ 已删除纪念日「{name}」"
        return False, f"未找到纪念日「{name}」"

    # ── 全球节日 ──
    def add_festival(self, name: str, month: int, day: int, lunar: bool = False) -> Tuple[bool, str]:
        if not name.strip():
            return False, "节日名称不能为空"
        if any(f["name"] == name for f in self.festivals):
            return False, f"已存在节日「{name}」"
        self.festivals.append({
            "name": name.strip(), "month": month, "day": day, "lunar": lunar,
        })
        self.save()
        kind = "农历" if lunar else "公历"
        return True, f"✅ 已添加{kind}节日「{name}」"

    def remove_festival(self, name: str) -> Tuple[bool, str]:
        for f in self.festivals:
            if f["name"] == name:
                self.festivals.remove(f)
                self.save()
                return True, f"✅ 已删除节日「{name}」"
        return False, f"未找到节日「{name}」"

    def get_festivals(self) -> List[dict]:
        return list(self.festivals)

    # ── 触发判断 ──
    def is_bonus_granted_today(self, uid: str, today: date) -> bool:
        return self.last_bonus_date.get(uid) == today.isoformat()

    def mark_bonus_granted(self, uid: str, today: date):
        self.last_bonus_date[uid] = today.isoformat()
        self.save()

    def get_today_events(self, uid: str, today: date) -> List[dict]:
        """返回今天的纪念日/节日事件列表"""
        events: List[dict] = []
        # 用户自定义纪念日 + 生日
        for a in self.anniversaries.get(uid, []):
            if (a["month"], a["day"]) == (today.month, today.day):
                events.append({
                    "name": a["name"], "kind": a.get("kind", "anniversary"),
                    "days": None, "description": f"今天是「{a['name']}」！",
                })
        # 首次互动周年 + 认识天数里程碑
        fm = self.first_meet.get(uid)
        if fm:
            try:
                fy, fm_, fd = map(int, fm.split("-"))
                first = date(fy, fm_, fd)
            except Exception:
                first = None
            if first:
                if (fm_, fd) == (today.month, today.day):
                    years = today.year - fy
                    events.append({
                        "name": f"认识{years}周年", "kind": "first_meet", "days": None,
                        "description": f"今天是你们认识{years}周年纪念日！",
                    })
                days = (today - first).days
                if days > 0 and days in DAY_MILESTONES:
                    events.append({
                        "name": f"认识{days}天", "kind": "day_milestone", "days": days,
                        "description": f"你们已经认识{days}天了，值得庆祝！",
                    })
        # 节日（含农历换算 + 除夕跨年处理）
        for name, fd in self._festival_dates(today.year):
            if fd == today:
                events.append({
                    "name": name, "kind": "festival", "days": None,
                    "description": f"今天是「{name}」！",
                })
        return events

    def _festival_dates(self, solar_year: int) -> List[Tuple[str, date]]:
        """生成指定公历年附近三年的节日日期（覆盖除夕跨年）"""
        dates: List[Tuple[str, date]] = []
        for y in (solar_year - 1, solar_year, solar_year + 1):
            for f in self.festivals:
                if f["lunar"] and f["month"] == 12 and f["day"] == 30:
                    continue  # 除夕单独处理
                if f["lunar"]:
                    s = lunar_to_solar(y, f["month"], f["day"])
                    if s:
                        dates.append((f["name"], date(*s)))
                else:
                    try:
                        dates.append((f["name"], date(y, f["month"], f["day"])))
                    except ValueError:
                        pass
            spring = lunar_to_solar(y + 1, 1, 1)
            if spring:
                dates.append(("除夕", date(*spring) - timedelta(days=1)))
        return dates

    # ── 展示 ──
    def list_user_anniversaries(self, uid: str, today: date) -> List[dict]:
        """用户纪念日列表（含下次日期与倒计时）"""
        rows = []
        for a in self.anniversaries.get(uid, []):
            nxt = _next_occurrence(a["month"], a["day"], today)
            rows.append({
                "name": a["name"],
                "month": a["month"], "day": a["day"],
                "kind": a.get("kind", "anniversary"),
                "next_date": nxt.isoformat() if nxt else "",
                "days_left": (nxt - today).days if nxt else -1,
                "is_today": nxt == today if nxt else False,
            })
        fm = self.first_meet.get(uid)
        if fm:
            try:
                fy, fm_, fd = map(int, fm.split("-"))
                first = date(fy, fm_, fd)
                nxt = _next_occurrence(fm_, fd, today)
                rows.append({
                    "name": "初次相识",
                    "month": fm_, "day": fd,
                    "kind": "first_meet",
                    "next_date": nxt.isoformat() if nxt else "",
                    "days_left": (nxt - today).days if nxt else -1,
                    "is_today": nxt == today if nxt else False,
                })
            except Exception:
                pass
        return rows

    def get_next_countdown(self, uid: str, today: date, window_days: int = 7) -> Optional[dict]:
        """倒计时事件：返回未来 window_days 天内最近的用户纪念日/生日/初次相识
        （days_left 1~window_days），无则 None。供角色主动提及制造期待。"""
        best = None
        for r in self.list_user_anniversaries(uid, today):
            d = r["days_left"]
            if 1 <= d <= max(1, window_days):
                if best is None or d < best["days_left"]:
                    best = r
        return best

    def list_festivals_with_dates(self, today: date) -> List[dict]:
        """节日列表（含本年内下次日期与倒计时）"""
        rows = []
        for name, fd in self._festival_dates(today.year):
            if fd < today:
                continue  # 已过的节日（今天的仍显示）
            if fd > today.replace(year=today.year + 1):
                continue
            rows.append({
                "name": name, "date": fd.isoformat(),
                "days_left": (fd - today).days,
                "is_today": fd == today,
            })
        # 去重（三年窗口可能重复）
        seen = set()
        uniq = []
        for r in rows:
            if r["name"] in seen:
                continue
            seen.add(r["name"])
            uniq.append(r)
        uniq.sort(key=lambda r: r["days_left"])
        return uniq
