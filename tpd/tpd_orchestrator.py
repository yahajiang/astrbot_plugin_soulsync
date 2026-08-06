"""TPD - 调度器（骨架）

统一调度三个子系统：
- environment : 季节天气联动（Phase A 完成）
- countdown   : 倒计时事件（Phase B 接入）
- timeskip    : 时间跳跃叙事（Phase C 接入）

Phase A 只完成 environment 链路；countdown/timeskip 留有占位入口。
"""

from __future__ import annotations

import datetime
from typing import Dict, Optional

from .env_injector import build_environment_info
from .mood_mapper import mood_deltas, temperature_band
from .weather_provider import WeatherProvider

# 环境子系统配置默认值（Phase A 注册的 11 键）
ENV_CONFIG_DEFAULTS: Dict = {
    "tpd_enabled": False,
    "tpd_weather_enabled": True,
    "tpd_weather_api_provider": "",
    "tpd_weather_api_key": "",
    "tpd_weather_api_city": "",
    "tpd_weather_cache_minutes": 60,
    "tpd_weather_mood_strength": 0.3,
    "tpd_season_mood_strength": 0.2,
    "tpd_moonphase_enabled": True,
    "tpd_moonphase_mood_strength": 0.1,
    "tpd_aqi_enabled": False,
}


def _cfg(config: Optional[dict], key: str, default):
    if config is None:
        return default
    if hasattr(config, "get"):
        return config.get(key, default)
    return default


class TPDOrchestrator:
    """TPD 统一调度器（Phase A：environment 全链路）"""

    def __init__(self, config: Optional[dict] = None, data_dir: str = "data/tpd"):
        self.config = config or {}
        self.data_dir = data_dir
        self.weather_provider = WeatherProvider(data_dir, self.config)
        self._environment: Optional[dict] = None
        self._environment_deltas: Optional[Dict[str, float]] = None
        self._environment_info: str = ""

    # ── 环境子系统 ────────────────────────────────────────
    def refresh_environment(self, dt: Optional[datetime.datetime] = None) -> Optional[dict]:
        """刷新并返回环境数据（含心情映射与注入文本）"""
        env = self.weather_provider.get_weather(dt)
        if env is None:
            self._environment = None
            self._environment_deltas = None
            self._environment_info = ""
            return None
        env["temp_band"] = temperature_band(env.get("temperature"))
        moon_strength = (
            _cfg(self.config, "tpd_moonphase_mood_strength", 0.1)
            if _cfg(self.config, "tpd_moonphase_enabled", True)
            else 0.0
        )
        deltas = mood_deltas(
            env,
            weather_strength=_cfg(self.config, "tpd_weather_mood_strength", 0.3),
            season_strength=_cfg(self.config, "tpd_season_mood_strength", 0.2),
            moon_strength=moon_strength,
        )
        self._environment = env
        self._environment_deltas = deltas
        self._environment_info = build_environment_info(env, deltas)
        return dict(env)

    def get_environment(self) -> Optional[dict]:
        """最近一次环境数据（未刷新过则先刷新）"""
        if self._environment is None:
            self.refresh_environment()
        return dict(self._environment) if self._environment else None

    # ── 每轮处理入口 ──────────────────────────────────────
    def process_turn(self, uid: str, text: str = "", ctx: Optional[dict] = None) -> dict:
        """每轮对话处理：返回 {environment, inject_text, mood_deltas}

        Phase B/C 将追加 countdown / timeskip 结果。tpd_enabled=False 时全空。
        """
        ctx = ctx or {}
        result: Dict = {"environment": None, "inject_text": "", "mood_deltas": None}
        if not _cfg(self.config, "tpd_enabled", False):
            return result
        env = self.get_environment()
        if env is not None:
            deltas = self._environment_deltas or {}
            result.update(
                {
                    "environment": env,
                    "inject_text": self._environment_info,
                    "mood_deltas": deltas,
                }
            )
        result["countdown"] = self.process_countdown(uid, text, ctx)
        result["timeskip"] = self.process_timeskip(uid, text, ctx)
        return result

    # ── 子系统占位（Phase B/C 实现） ───────────────────────
    def process_countdown(self, uid: str, text: str = "", ctx: Optional[dict] = None) -> Optional[dict]:
        """倒计时事件处理（Phase B 接入）"""
        return None

    def process_timeskip(self, uid: str, text: str = "", ctx: Optional[dict] = None) -> Optional[dict]:
        """时间跳跃处理（Phase C 接入）"""
        return None

    # ── WebUI 面板数据（Phase E 使用） ─────────────────────
    def environment_panel_data(self) -> dict:
        """环境面板：当前天气/心情系数/季节信息"""
        env = self.get_environment()
        if env is None:
            return {"enabled": _cfg(self.config, "tpd_enabled", False), "environment": None}
        return {
            "enabled": _cfg(self.config, "tpd_enabled", False),
            "environment": env,
            "mood_deltas": self._environment_deltas,
            "inject_text": self._environment_info,
        }
