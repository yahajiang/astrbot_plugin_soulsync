"""TPD - 调度器（骨架）

统一调度三个子系统：
- environment : 季节天气联动（Phase A 完成）
- countdown   : 倒计时事件（Phase B 接入）
- timeskip    : 时间跳跃叙事（Phase C 接入）
"""

from __future__ import annotations

import datetime
import time
from typing import Dict, Optional

from .countdown_calculator import CountdownCalculator
from .countdown_injector import build_countdown_info
from .countdown_narrator import stage_of as stage_name_of
from .env_injector import build_environment_info
from .farewell_narrator import generate_farewell_context
from .gap_detector import detect_passive_gap
from .mood_mapper import mood_deltas, temperature_band
from .return_narrator import (
    generate_return_context,
    generate_return_early_context,
)
from .skip_executor import SkipExecutor
from .skip_parser import parse_skip_command
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

# 时间跳跃子系统配置默认值（Phase C 注册的 6 键）
TIMESKIP_CONFIG_DEFAULTS: Dict = {
    "tpd_skip_enabled": True,
    "tpd_skip_max_days": 365,
    "tpd_skip_freeze_penalty": True,
    "tpd_skip_emotion_drift": True,
    "tpd_passive_gap_threshold_hours": 6,
    "tpd_return_narrative_enabled": True,
}

# 告别/回归叙事独占本轮的 action
_EXCLUSIVE_ACTIONS = ("farewell", "return_early", "return")


def _cfg(config: Optional[dict], key: str, default):
    if config is None:
        return default
    if hasattr(config, "get"):
        return config.get(key, default)
    return default


class TPDOrchestrator:
    """TPD 统一调度器（Phase B：environment + countdown）"""

    def __init__(self, config: Optional[dict] = None, data_dir: str = "data/tpd",
                 sources: Optional[dict] = None):
        self.config = config or {}
        self.data_dir = data_dir
        self.sources = sources or {}
        self.weather_provider = WeatherProvider(data_dir, self.config)
        self.countdown_calculator = CountdownCalculator(data_dir, self.sources)
        self.skip_executor = SkipExecutor(data_dir)
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
        ts = result["timeskip"]
        if ts:
            action = ts.get("action", "")
            if action in _EXCLUSIVE_ACTIONS:
                # 告别/回归叙事独占本轮（doc 6.3）
                result["inject_text"] = ts["inject_text"]
            elif action == "gap":
                gap_text = ts["inject_text"]
                result["inject_text"] = (
                    (result["inject_text"] + "\n" + gap_text).strip()
                    if result["inject_text"] else gap_text
                )
            td = ts.get("emotion_deltas") or {}
            if td:
                merged = dict(result.get("mood_deltas") or {})
                for k, v in td.items():
                    merged[k] = merged.get(k, 0.0) + v
                result["mood_deltas"] = merged
        return result

    # ── 子系统：倒计时（Phase B） ────────────────────────
    def process_countdown(self, uid: str, text: str = "", ctx: Optional[dict] = None) -> Optional[dict]:
        """倒计时事件处理：选择可提及事件 → 记录提及 → 生成注入文本

        依赖 sources["anniversaries"]（AnniversaryManager）；缺失时静默返回 None。
        """
        if not _cfg(self.config, "tpd_enabled", False):
            return None
        if not _cfg(self.config, "tpd_countdown_enabled", True):
            return None
        if not isinstance(self.sources.get("anniversaries"), object) or \
                not hasattr(self.sources.get("anniversaries"), "get_countdown_sources"):
            return None
        start_days = _cfg(self.config, "tpd_countdown_mention_start_days", 7)
        freq_days = _cfg(self.config, "tpd_countdown_mention_freq_days", 1)
        max_per_turn = _cfg(self.config, "tpd_countdown_max_per_turn", 1)
        today = datetime.date.today()
        event = self.countdown_calculator.select_for_mention(
            uid, today, start_days=max(7, start_days), freq_hours=freq_days * 24.0
        )
        if event is None:
            return None
        self.countdown_calculator.mark_mentioned(uid, event)
        # 顺带列出的其他事件（即将到来，按得分取前 N 个）
        upcoming = [
            e for e in self.countdown_calculator.get_active_events(uid, today, window_days=30)
            if e.days_left >= 1 and e.key != event.key
        ]
        upcoming.sort(key=lambda e: -e.score)
        others = upcoming[: min(3, max(1, max_per_turn))]
        inject = build_countdown_info(event, others, today)
        return {"event": event.as_dict(), "inject_text": inject,
                "stage": stage_name_of(event.days_left)[0]}

    # ── 子系统：时间跳跃（Phase C） ─────────────────────
    def process_timeskip(self, uid: str, text: str = "", ctx: Optional[dict] = None) -> Optional[dict]:
        """时间跳跃处理（Phase C，doc 6.3）：

        优先级：跳跃指令（告别/提前回归）→ 待回归 → 被动离开检测。
        每轮更新 last_active_ts（供被动离开检测）。tpd_skip_enabled=False 时全空。
        """
        if not _cfg(self.config, "tpd_enabled", False):
            return None
        if not _cfg(self.config, "tpd_skip_enabled", True):
            return None
        now = time.time()
        state = self.skip_executor.get_state(uid)
        prev_offset = state["offset_days"]
        cmd = parse_skip_command(text) if text else None
        max_days = _cfg(self.config, "tpd_skip_max_days", 365)
        freeze = _cfg(self.config, "tpd_skip_freeze_penalty", True)
        drift = _cfg(self.config, "tpd_skip_emotion_drift", True)
        ann_mgr = self.sources.get("anniversaries")
        if not (isinstance(ann_mgr, object) and hasattr(ann_mgr, "get_countdown_sources")):
            ann_mgr = None

        result = None
        if cmd is not None:
            if cmd.kind == "return_early":
                self.skip_executor.execute_skip(uid, cmd, now, max_days, freeze, drift, ann_mgr)
                self.skip_executor.consume_return(uid)
                if _cfg(self.config, "tpd_return_narrative_enabled", True):
                    inject = generate_return_early_context(prev_offset)
                else:
                    inject = ""
                result = {"action": "return_early", "skip_days": 0,
                          "inject_text": inject, "emotion_deltas": {},
                          "memory_event": f"用户提前回归（原跳跃{prev_offset}天）"}
            else:
                res = self.skip_executor.execute_skip(uid, cmd, now, max_days, freeze, drift, ann_mgr)
                inject = generate_farewell_context(cmd, res["target_date"],
                                                   res["late_celebrations"])
                result = {"action": "farewell", "skip_days": res["skip_days"],
                          "target_date": res["target_date"], "inject_text": inject,
                          "emotion_deltas": res["emotion_deltas"],
                          "frozen_until": res["frozen_until"],
                          "late_celebrations": res["late_celebrations"],
                          "memory_event": f"时间跳跃{res['skip_days']}天（{cmd.reason or '告别'}）"}
        elif state["pending_return"]:
            ret = self.skip_executor.consume_return(uid)
            if _cfg(self.config, "tpd_return_narrative_enabled", True):
                inject = generate_return_context(ret["last_days"], ret["last_target"],
                                                 ret["late_celebrations"])
            else:
                inject = ""
            result = {"action": "return", "skip_days": ret["last_days"],
                      "inject_text": inject, "emotion_deltas": {},
                      "late_celebrations": ret["late_celebrations"],
                      "memory_event": f"跳跃回归（{ret['last_days']}天）"}
        else:
            th = _cfg(self.config, "tpd_passive_gap_threshold_hours", 6)
            stage = ctx.get("stage") if ctx else None
            gap = detect_passive_gap(now, state["last_active_ts"], th, stage)
            if gap is not None:
                result = {"action": "gap", "gap_hours": gap.gap_hours,
                          "level": gap.level, "label": gap.label,
                          "inject_text": gap.inject_text, "emotion_deltas": {}}

        # 每轮更新活跃时间戳（被动离开检测依据）
        state["last_active_ts"] = now
        self.skip_executor.save_uid(uid)

        # 时间跳跃日志写入长期记忆（C.7；memory 源缺失时静默跳过）
        mem = self.sources.get("memory")
        if result and result.get("memory_event") and mem is not None and hasattr(mem, "add_event"):
            try:
                mem.add_event(uid, {"description": result["memory_event"], "message": ""})
            except Exception:
                pass
        return result

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

    def countdown_panel_data(self, uid: str) -> dict:
        """倒计时面板：活跃倒计时列表 + 提及状态"""
        today = datetime.date.today()
        events = self.countdown_calculator.get_active_events(uid, today, window_days=30)
        events.sort(key=lambda e: -e.score)
        return {
            "enabled": _cfg(self.config, "tpd_countdown_enabled", True),
            "events": [e.as_dict() for e in events[:10]],
        }

    def skip_panel_data(self, uid: str) -> dict:
        """跳跃面板：当前偏移/冻结/跳跃历史"""
        return {
            "enabled": _cfg(self.config, "tpd_skip_enabled", True),
            "status": self.skip_executor.get_skip_status(uid),
        }
