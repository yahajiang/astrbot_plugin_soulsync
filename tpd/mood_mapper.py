"""TPD - 环境→心情映射（8 维情感基础层叠加）

天气/温度/季节/月相 各自映射到 8 维情感增量，按配置强度缩放后合并。
每维增量钳制在 ±5 内（强度默认 0.1~0.3，防止环境喧宾夺主、角色性格失真）。
"""

from __future__ import annotations

from typing import Dict, List

EMOTION_DIMS: List[str] = [
    "joy", "sadness", "anger", "fear", "surprise", "disgust", "trust", "anticipation",
]

DIM_LABELS: Dict[str, str] = {
    "joy": "喜悦", "sadness": "悲伤", "anger": "愤怒", "fear": "恐惧",
    "surprise": "惊讶", "disgust": "厌恶", "trust": "信任", "anticipation": "期待",
}

# 天气 → 情感增量（10 种规范化天气）
WEATHER_MOOD: Dict[str, Dict[str, float]] = {
    "晴": {"joy": 5, "trust": 3, "anticipation": 2},
    "多云": {"joy": 2, "anticipation": 2},
    "阴": {"sadness": 3, "anger": 1},
    "小雨": {"sadness": 3, "trust": 5},
    "中雨": {"sadness": 4, "joy": -2},
    "大雨": {"sadness": 5, "fear": 2},
    "雷阵雨": {"fear": 3, "anger": 2, "surprise": 1},
    "小雪": {"joy": 3, "trust": 2, "anticipation": 1},
    "大雪": {"joy": 5, "anticipation": 3, "trust": 2},
    "大风": {"fear": 2, "anger": 2},
}

# 温度 6 档 → 情感增量
TEMPERATURE_BANDS: Dict[str, tuple] = {
    "严寒": (-1000, 0, {"joy": -3, "fear": 2}),
    "寒冷": (0, 10, {"joy": -2, "trust": 1}),
    "凉爽": (10, 18, {"joy": 1}),
    "舒适": (18, 26, {"joy": 3, "trust": 2, "anger": -1}),
    "炎热": (26, 33, {"anger": 3, "joy": -2}),
    "酷热": (33, 1000, {"anger": 4, "joy": -3, "fear": 1}),
}

# 季节 → 情感增量
SEASON_MOOD: Dict[str, Dict[str, float]] = {
    "春": {"joy": 3, "anticipation": 2, "trust": 1},
    "夏": {"joy": 2, "surprise": 1, "anger": 1},
    "秋": {"sadness": 2, "trust": 2, "anticipation": 1},
    "冬": {"joy": -1, "trust": 2, "anticipation": 2},
}

# 月相 8 阶段 → 情感增量（索引与 season_handler.MOON_PHASES 对齐）
MOON_MOOD: List[Dict[str, float]] = [
    {"surprise": 1, "anticipation": 1},  # 新月
    {"anticipation": 1},                 # 蛾眉月
    {"trust": 1, "anticipation": 1},     # 上弦月
    {"joy": 1},                          # 盈凸月
    {"joy": 3, "surprise": 2},           # 满月
    {"sadness": 1, "trust": 1},          # 亏凸月
    {"sadness": 1, "anticipation": 1},   # 下弦月
    {"sadness": 2, "trust": 1},          # 残月
]

MAX_DIM_DELTA = 5.0  # 单维钳制上限（防环境喧宾夺主）


def temperature_band(temp: Optional[float]) -> Optional[str]:
    """温度 → 6 档名称；None（未知温度）返回 None 不参与映射"""
    if temp is None:
        return None
    for name, (lo, hi, _) in TEMPERATURE_BANDS.items():
        if lo <= temp < hi:
            return name
    return "舒适"


def _merge(deltas: Dict[str, float], factor: Dict[str, float], strength: float) -> None:
    if strength <= 0:
        return
    for dim, v in factor.items():
        deltas[dim] = deltas.get(dim, 0.0) + v * strength


def mood_deltas(
    env: dict,
    weather_strength: float = 0.3,
    season_strength: float = 0.2,
    moon_strength: float = 0.1,
) -> Dict[str, float]:
    """环境数据 → 8 维情感增量（已按强度缩放并钳制）"""
    deltas: Dict[str, float] = {d: 0.0 for d in EMOTION_DIMS}
    weather = env.get("weather")
    if weather in WEATHER_MOOD:
        _merge(deltas, WEATHER_MOOD[weather], weather_strength)
    band = temperature_band(env.get("temperature"))
    if band:
        _merge(deltas, TEMPERATURE_BANDS[band][2], weather_strength)
    season = env.get("season")
    if season in SEASON_MOOD:
        _merge(deltas, SEASON_MOOD[season], season_strength)
    moon = env.get("moon_phase")
    if moon:
        from .season_handler import MOON_PHASES

        for idx, (name, _) in enumerate(MOON_PHASES):
            if name == moon:
                _merge(deltas, MOON_MOOD[idx], moon_strength)
                break
    for dim in EMOTION_DIMS:
        deltas[dim] = max(-MAX_DIM_DELTA, min(MAX_DIM_DELTA, deltas[dim]))
        deltas[dim] = round(deltas[dim], 2)
    return deltas


def combine_mood(
    env: dict,
    weather_strength: float = 0.3,
    season_strength: float = 0.2,
    moon_strength: float = 0.1,
) -> Dict[str, float]:
    """mood_deltas 别名（与文档命名一致）"""
    return mood_deltas(env, weather_strength, season_strength, moon_strength)
