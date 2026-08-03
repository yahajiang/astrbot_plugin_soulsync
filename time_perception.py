"""EmotionAI Pro - 时间/节假日/农历感知

参考 astrbot_plugin_LLMPerception 的实现方式：
- chinese_calendar / lunarcalendar 为可选依赖，懒加载，未安装自动降级；
- 节假日优先用 chinese_calendar（支持调休判断），降级为周末判断；
- 农历优先用 lunarcalendar，降级用内置换算表（anniversary.solar_to_lunar）；
- 感知信息拼为一行文本，由 main.py 作为 prompt 前缀注入。
"""

from __future__ import annotations

import datetime
from typing import List, Optional

CHINESE_CALENDAR_AVAILABLE = False
calendar_cn = None
LUNAR_CALENDAR_AVAILABLE = False
Converter = None
Solar = None


def load_calendar_dependencies() -> None:
    global calendar_cn, Converter, Solar
    global CHINESE_CALENDAR_AVAILABLE, LUNAR_CALENDAR_AVAILABLE
    try:
        import chinese_calendar as cc
        calendar_cn = cc
        CHINESE_CALENDAR_AVAILABLE = True
    except ImportError:
        calendar_cn = None
        CHINESE_CALENDAR_AVAILABLE = False
    try:
        import lunarcalendar
        Converter = lunarcalendar.Converter
        Solar = lunarcalendar.Solar
        LUNAR_CALENDAR_AVAILABLE = True
    except ImportError:
        Converter = None
        Solar = None
        LUNAR_CALENDAR_AVAILABLE = False


WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

LUNAR_MONTHS = [
    "正月", "二月", "三月", "四月", "五月", "六月",
    "七月", "八月", "九月", "十月", "冬月", "腊月",
]
LUNAR_DAYS = [
    "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
    "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
    "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十",
]
TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
SHENG_XIAO = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]


def get_time_period(dt: datetime.datetime) -> str:
    hour = dt.hour
    if 5 <= hour < 12:
        return "上午"
    if 12 <= hour < 14:
        return "中午"
    if 14 <= hour < 18:
        return "下午"
    if 18 <= hour < 22:
        return "晚上"
    return "深夜"


def build_time_info(dt: datetime.datetime) -> str:
    """发送时间 + 星期 + 时段（仿 LLMPerception）"""
    return (
        f"发送时间: {dt.strftime('%Y-%m-%d %H:%M:%S')} | "
        f"{WEEKDAY_NAMES[dt.weekday()]}, {get_time_period(dt)}"
    )


def build_holiday_info(
    dt: datetime.datetime,
    festival_names: Optional[List[str]] = None,
    holiday_country: str = "CN",
) -> str:
    """节假日信息：chinese_calendar（含调休）→ 周末降级；附加当天节日"""
    parts: List[str] = []
    weekday = dt.weekday()
    d = dt.date()
    if holiday_country == "CN" and CHINESE_CALENDAR_AVAILABLE and calendar_cn is not None:
        try:
            is_holiday = calendar_cn.is_holiday(d)
            is_workday = calendar_cn.is_workday(d)
            if is_holiday:
                detail = calendar_cn.get_holiday_detail(d)
                name = detail[1] if detail and detail[1] else "法定节假日"
                if weekday >= 5:
                    parts.append(f"周末({name})")
                else:
                    parts.append(f"法定节假日({name})")
            elif is_workday:
                parts.append("调休工作日" if weekday >= 5 else "工作日")
            else:
                parts.append("周末")
        except Exception:
            parts.append("周末" if weekday >= 5 else "工作日")
    else:
        parts.append("周末" if weekday >= 5 else "工作日")
    if festival_names:
        parts.append("节日: " + "、".join(festival_names))
    return ", ".join(parts)


def build_lunar_info(dt: datetime.datetime) -> str:
    """农历日期：lunarcalendar → 内置换算表降级"""
    if LUNAR_CALENDAR_AVAILABLE and Solar is not None and Converter is not None:
        try:
            solar = Solar(dt.year, dt.month, dt.day)
            lunar = Converter.Solar2Lunar(solar)
            month_str = LUNAR_MONTHS[lunar.month - 1]
            day_str = LUNAR_DAYS[lunar.day - 1]
            if lunar.isleap:
                month_str = "闰" + month_str
            gan = TIAN_GAN[(lunar.year - 4) % 10]
            zhi = DI_ZHI[(lunar.year - 4) % 12]
            sheng = SHENG_XIAO[(lunar.year - 4) % 12]
            return f"农历{gan}{zhi}年({sheng}年){month_str}{day_str}"
        except Exception:
            pass
    try:
        from .anniversary import solar_to_lunar
    except ImportError:
        from anniversary import solar_to_lunar
    try:
        res = solar_to_lunar(dt.year, dt.month, dt.day)
        if res:
            month_str = LUNAR_MONTHS[res["month"] - 1]
            day_str = LUNAR_DAYS[res["day"] - 1]
            if res["is_leap"]:
                month_str = "闰" + month_str
            gan = TIAN_GAN[(res["year"] - 4) % 10]
            zhi = DI_ZHI[(res["year"] - 4) % 12]
            sheng = SHENG_XIAO[(res["year"] - 4) % 12]
            return f"农历{gan}{zhi}年({sheng}年){month_str}{day_str}"
    except Exception:
        pass
    return ""
