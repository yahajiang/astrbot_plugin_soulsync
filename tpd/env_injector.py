"""TPD - 环境叙事注入（生成 LLM 注入文本）

把环境数据（天气/温度/季节/节气/月相）与心情倾向拼成一行注入文本，
由 main.py（Phase D）以 temp TextPart 前缀注入 system prompt。
"""

from __future__ import annotations

from typing import Dict, Optional

from .mood_mapper import DIM_LABELS, EMOTION_DIMS


def build_mood_tendency_text(deltas: Optional[Dict[str, float]]) -> str:
    """心情倾向文本：取非零维度，"喜悦↑1.5 悲伤↓0.9" 形式，最多 4 个"""
    if not deltas:
        return ""
    items = []
    for dim in EMOTION_DIMS:
        v = deltas.get(dim, 0.0)
        if abs(v) < 0.05:
            continue
        arrow = "↑" if v > 0 else "↓"
        items.append(f"{DIM_LABELS.get(dim, dim)}{arrow}{abs(v):g}")
    if not items:
        return ""
    return " · 心情倾向: " + " ".join(items[:4])


def build_environment_info(env: dict, deltas: Optional[Dict[str, float]] = None) -> str:
    """环境注入文本（骨架缩写，示例）：
    [环境] ☀️晴 24℃ · 春 · 清明 · 🌒蛾眉月 · 心情: 喜悦↑1.5
    """
    parts = []
    weather = env.get("weather")
    if weather:
        emoji = env.get("weather_emoji", "")
        parts.append(f"{emoji}{weather}" if emoji else weather)
    temp = env.get("temperature")
    if temp is not None:
        parts.append(f"{temp}℃")
    season = env.get("season")
    if season:
        parts.append(season)
    term = env.get("solar_term")
    if term:
        parts.append(term + ("今" if env.get("solar_term_today") else ""))
    moon = env.get("moon_phase")
    if moon:
        parts.append(f"{env.get('moon_emoji', '')}{moon}")
    if not parts:
        return ""
    text = " · ".join(parts)
    tendency = build_mood_tendency_text(deltas)
    if tendency:
        tendency = tendency.replace(" · 心情倾向: ", " · 心情: ")
    return f"[环境] {text}{tendency}"
