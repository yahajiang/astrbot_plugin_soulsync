"""TPD - 天气数据获取（三级降级 + 缓存，零第三方依赖）

三级降级策略（确保永不出错）：
1. API   ：hefeng / openweather（未配置密钥自动跳过，失败自动降级）
2. 本地推算：节气判定季节 + 日期种子确定性模拟天气 + 季节温度估算
3. 纯时间兜底：time_perception 确定性模拟（异常兜底，几乎不会触发）

缓存：data/tpd/weather_cache.json，按日期缓存，60 分钟内不重复请求 API。
"""

from __future__ import annotations

import datetime
import json
import random
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Optional

from . import season_handler

# 规范化天气类型（10 种）
CANONICAL_WEATHERS = [
    "晴", "多云", "阴", "小雨", "中雨", "大雨",
    "雷阵雨", "小雪", "大雪", "大风",
]

WEATHER_EMOJI = {
    "晴": "☀️", "多云": "⛅", "阴": "☁️", "小雨": "🌧️", "中雨": "🌧️",
    "大雨": "🌧️", "雷阵雨": "⛈️", "小雪": "🌨️", "大雪": "❄️", "大风": "🌬️",
}

# 各季节天气池（天气, 权重）
SEASONAL_WEATHER_POOL = {
    "春": [("晴", 4), ("多云", 3), ("阴", 1), ("小雨", 2), ("中雨", 1), ("大风", 1)],
    "夏": [("晴", 4), ("多云", 2), ("阴", 1), ("雷阵雨", 2), ("大雨", 1), ("中雨", 1)],
    "秋": [("晴", 4), ("多云", 3), ("阴", 2), ("小雨", 1), ("中雨", 1), ("大风", 1)],
    "冬": [("晴", 2), ("多云", 3), ("阴", 2), ("小雪", 2), ("大雪", 1), ("大风", 1)],
}

# 季节基准温度与波动（℃）
SEASON_TEMP = {
    "春": {"base": 16, "spread": 8},
    "夏": {"base": 28, "spread": 6},
    "秋": {"base": 18, "spread": 8},
    "冬": {"base": 4, "spread": 10},
}

# 天气对温度的修正（℃）
WEATHER_TEMP_OFFSET = {
    "晴": 0, "多云": -1, "阴": -2, "小雨": -4, "中雨": -5,
    "大雨": -6, "雷阵雨": -4, "小雪": -6, "大雪": -8, "大风": -4,
}

# API 文本 → 规范化天气（中英文常见表述）
API_WEATHER_MAP = {
    "晴": "晴", "clear": "晴", "sunny": "晴",
    "多云": "多云", "partly cloudy": "多云", "few clouds": "多云", "scattered clouds": "多云",
    "阴": "阴", "overcast": "阴", "broken clouds": "阴",
    "小雨": "小雨", "light rain": "小雨", "drizzle": "小雨",
    "中雨": "中雨", "moderate rain": "中雨",
    "大雨": "大雨", "heavy rain": "大雨", "rain": "中雨",
    "雷阵雨": "雷阵雨", "thunderstorm": "雷阵雨",
    "小雪": "小雪", "light snow": "小雪", "snow": "雪",
    "大雪": "大雪", "heavy snow": "大雪",
    "大风": "大风", "windy": "大风", "gale": "大风",
    "雾": "多云", "fog": "多云", "霾": "阴", "haze": "阴",
}


class WeatherProvider:
    """天气提供器：API → 本地推算 → 纯时间兜底"""

    def __init__(self, data_dir: str, config: Optional[Dict] = None):
        self.data_dir = Path(data_dir)
        self.cache_file = self.data_dir / "weather_cache.json"
        self.config = config or {}
        self._cache: Dict = {}

    # ── 对外主入口 ──────────────────────────────────────────
    def get_weather(self, dt: Optional[datetime.datetime] = None, force_refresh: bool = False) -> Optional[dict]:
        """获取当天环境数据；tpd_weather_enabled=False 或异常时返回 None"""
        if not self.config.get("tpd_weather_enabled", True):
            return None
        dt = dt or datetime.datetime.now()
        date_str = dt.strftime("%Y-%m-%d")
        if not force_refresh:
            cached = self._read_cache(date_str)
            if cached is not None:
                return cached
        env = self._fetch_api(dt)
        if env is None:
            env = self._local_estimate(dt)
        if env is None:
            env = self._time_fallback(dt)
        if env is not None:
            self._write_cache(date_str, env)
        return env

    # ── 缓存 ──────────────────────────────────────────────
    def _read_cache(self, date_str: str) -> Optional[dict]:
        self._load_cache()
        entry = self._cache.get(date_str)
        if not entry:
            return None
        fresh_minutes = self.config.get("tpd_weather_cache_minutes", 60)
        if time.time() - entry.get("fetched_at", 0) <= fresh_minutes * 60:
            return dict(entry)
        return None

    def _load_cache(self) -> None:
        if self._cache:
            return
        try:
            if self.cache_file.exists():
                self._cache = json.loads(self.cache_file.read_text(encoding="utf-8"))
        except Exception:
            self._cache = {}

    def _write_cache(self, date_str: str, env: dict) -> None:
        self._load_cache()
        self._cache[date_str] = env
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.cache_file.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._cache, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.cache_file)
        except Exception:
            pass

    # ── 一级：API ─────────────────────────────────────────
    def _fetch_api(self, dt: datetime.datetime) -> Optional[dict]:
        provider = (self.config.get("tpd_weather_api_provider") or "").strip().lower()
        key = (self.config.get("tpd_weather_api_key") or "").strip()
        city = (self.config.get("tpd_weather_api_city") or "").strip()
        if not provider or provider == "none" or not key or not city:
            return None
        try:
            if provider == "hefeng":
                payload = self._fetch_hefeng(city, key)
            elif provider == "openweather":
                payload = self._fetch_openweather(city, key)
            else:
                return None
        except Exception:
            return None
        if payload is None:
            return None
        return self._build_env(dt, weather=payload["weather"], temperature=payload["temperature"], source="api")

    def _fetch_hefeng(self, city: str, key: str) -> Optional[dict]:
        url = f"https://devapi.qweather.com/v7/weather/now?location={urllib.parse.quote(city)}&key={key}"
        data = self._get_json(url)
        if not data or data.get("code") != "200":
            return None
        now = data.get("now") or {}
        text = (now.get("text") or "").lower()
        temp = now.get("temp")
        return {
            "weather": API_WEATHER_MAP.get(text, "多云"),
            "temperature": int(float(temp)) if temp is not None else None,
        }

    def _fetch_openweather(self, city: str, key: str) -> Optional[dict]:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather?q={urllib.parse.quote(city)}"
            f"&appid={key}&units=metric"
        )
        data = self._get_json(url)
        if not data or data.get("cod") != 200:
            return None
        weather = (data.get("weather") or [{}])[0]
        desc = (weather.get("description") or "").lower()
        main_id = weather.get("id")
        text = API_WEATHER_MAP.get(desc, "多云")
        if text == "多云" and main_id is not None:
            text = API_WEATHER_MAP.get(str(main_id), "多云")
        temp = (data.get("main") or {}).get("temp")
        return {
            "weather": text,
            "temperature": int(round(float(temp))) if temp is not None else None,
        }

    def _get_json(self, url: str) -> Optional[dict]:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 soulsync-tpd"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8", errors="ignore"))

    # ── 二级：本地推算 ─────────────────────────────────────
    def _local_estimate(self, dt: datetime.datetime) -> dict:
        season = season_handler.season_of(dt.year, dt.month, dt.day)
        rng = random.Random(dt.year * 10000 + dt.month * 100 + dt.day)
        pool = SEASONAL_WEATHER_POOL[season]
        weather = rng.choices([w for w, _ in pool], weights=[wgt for _, wgt in pool])[0]
        temp_info = SEASON_TEMP[season]
        temp = temp_info["base"] + (rng.random() * 2 - 1) * temp_info["spread"]
        temp += WEATHER_TEMP_OFFSET[weather]
        return self._build_env(dt, weather=weather, temperature=int(round(temp)), source="local")

    # ── 三级：纯时间兜底 ───────────────────────────────────
    def _time_fallback(self, dt: datetime.datetime) -> Optional[dict]:
        try:
            from ..time_perception import get_weather as legacy_get_weather

            legacy = legacy_get_weather(dt)
            weather = legacy.get("weather", "多云")
            if weather not in CANONICAL_WEATHERS:
                weather = "多云"
            return self._build_env(dt, weather=weather, temperature=None, source="fallback")
        except Exception:
            return None

    # ── 组装 ──────────────────────────────────────────────
    def _build_env(self, dt: datetime.datetime, weather: str, temperature: Optional[int], source: str) -> dict:
        moon_name, moon_emoji = season_handler.moon_phase(dt)
        term = season_handler.solar_term_of(dt.year, dt.month, dt.day)
        season = season_handler.season_of(dt.year, dt.month, dt.day)
        season_desc = {"春": "万物复苏，生机盎然", "夏": "暑气蒸腾，热烈躁动", "秋": "天高气爽，落叶知秋", "冬": "寒风凛冽，天寒地冻"}[season]
        solar_term_today = False
        if term:
            m, d = season_handler.solar_term_date(
                dt.year, season_handler.SOLAR_TERM_NAMES.index(term)
            )
            solar_term_today = (dt.month, dt.day) == (m, d)
        return {
            "date": dt.strftime("%Y-%m-%d"),
            "weather": weather,
            "weather_emoji": WEATHER_EMOJI.get(weather, ""),
            "temperature": temperature,
            "season": season,
            "season_desc": season_desc,
            "solar_term": term,
            "solar_term_today": solar_term_today,
            "moon_phase": moon_name,
            "moon_emoji": moon_emoji,
            "source": source,
            "fetched_at": time.time(),
        }
