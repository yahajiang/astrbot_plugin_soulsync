"""TPD - 时间跳跃执行器（虚拟时钟 / 惩罚冻结 / 情感漂移 / 跳跃日志）

虚拟时钟：每用户 offset_days 永久偏移，用户的"今天" = 真实日期 + offset。
执行规则（doc 6.5 边界）：
- 最大跳跃天数：365（超限按 365）
- 冷落惩罚冻结：约定离开期间冻结（frozen_until 真实时间戳）
- 情感漂移：约定 +5 期待；长跳（≥14 天）按 forget_speed 自然衰减
- 跳跃日志：skip_log 持久化（供 Phase D 写入长期记忆）
- 迟到庆祝：跳跃窗口内经过的 T-0 纪念日/节日在回归时补充庆祝
"""

from __future__ import annotations

import datetime
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from ..anniversary import AnniversaryManager
from .skip_parser import SkipCommand

MAX_SKIP_DAYS = 365
DRIFT_PER_30_DAYS = {"trust": -0.4, "joy": -0.2}  # 情感自然衰减（长跳）
PROMISE_ANTICIPATION = 5.0                          # 有约定的期待增量


class SkipExecutor:
    """时间跳跃执行器 + 状态持久化（data/tpd/skip_state.json）"""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.state_file = self.data_dir / "skip_state.json"
        self._state: Dict[str, dict] = {}

    # ── 状态 ──────────────────────────────────────────
    def _load(self):
        if self._state:
            return
        try:
            if self.state_file.exists():
                self._state = json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception:
            self._state = {}

    def _save(self):
        self._load()
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.state_file.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.state_file)
        except Exception:
            pass

    def get_state(self, uid: str) -> dict:
        self._load()
        return self._state.setdefault(uid, {
            "offset_days": 0,
            "pending_return": False,
            "frozen_until": 0.0,
            "last_active_ts": 0.0,
            "skip_log": [],
            "late_celebrations": [],
        })

    def save_uid(self, uid: str):
        self._save()

    # ── 虚拟时钟 ──────────────────────────────────────
    def skip_today(self, uid: str, real_date: Optional[datetime.date] = None) -> datetime.date:
        """用户的"今天"（真实日期 + 跳跃偏移）"""
        real_date = real_date or datetime.date.today()
        return real_date + datetime.timedelta(days=self.get_state(uid)["offset_days"])

    # ── 执行跳跃 ──────────────────────────────────────
    def execute_skip(self, uid: str, cmd: SkipCommand, now: Optional[float] = None,
                     max_days: int = MAX_SKIP_DAYS, freeze_penalty: bool = True,
                     emotion_drift: bool = True,
                     anniversaries: Optional[AnniversaryManager] = None,
                     real_date: Optional[datetime.date] = None) -> dict:
        """执行跳跃，返回 SkipResult：
        {kind, skip_days, target_date, emotion_deltas, late_celebrations, frozen_until}"""
        now = now or time.time()
        state = self.get_state(uid)
        real_today = real_date or datetime.date.today()

        if cmd.kind == "return_early":
            state["offset_days"] = 0
            state["pending_return"] = True
            state["frozen_until"] = 0.0
            self.save_uid(uid)
            return {
                "kind": "return_early", "skip_days": 0,
                "target_date": real_today.isoformat(),
                "emotion_deltas": {}, "late_celebrations": [], "frozen_until": 0.0,
            }

        days = min(max_days, max(1, cmd.skip_days))
        start = real_today
        end = real_today + datetime.timedelta(days=days)

        # 时间推进（永久偏移）
        state["offset_days"] += days
        # 冷落惩罚冻结
        state["frozen_until"] = now + days * 86400.0 if freeze_penalty else 0.0
        # 情感漂移（约定期待 + 长跳衰减）
        deltas: Dict[str, float] = {"anticipation": PROMISE_ANTICIPATION}
        if emotion_drift and days >= 14:
            k = days / 30.0
            for dim, v in DRIFT_PER_30_DAYS.items():
                deltas[dim] = deltas.get(dim, 0.0) + v * k
        # 迟到庆祝素材：窗口 (start, end] 内的 T-0 事件
        late = self._late_celebration_scan(uid, start, end, anniversaries)
        # 跳跃日志
        state["skip_log"].append({
            "cmd": cmd.raw or cmd.reason, "days": days,
            "ts": now, "target_date": end.isoformat(),
        })
        state["skip_log"] = state["skip_log"][-20:]
        state["late_celebrations"] = late
        state["pending_return"] = True
        self.save_uid(uid)
        return {
            "kind": "skip", "skip_days": days,
            "target_date": end.isoformat(),
            "emotion_deltas": {k: round(v, 2) for k, v in deltas.items()},
            "late_celebrations": late,
            "frozen_until": state["frozen_until"],
        }

    def _late_celebration_scan(self, uid: str, start: datetime.date, end: datetime.date,
                               anniversaries: Optional[AnniversaryManager]) -> List[str]:
        """跳跃窗口内经过的 T-0 事件（纪念日/节日）"""
        if not isinstance(anniversaries, AnniversaryManager):
            return []
        names: List[str] = []
        window = max(7, (end - start).days)
        for s in anniversaries.get_countdown_sources(uid, end, window_days=window):
            occ = s["occurrence"]
            if start < occ <= end:
                names.append(s["name"])
        return names

    def consume_return(self, uid: str) -> dict:
        """消费回归：清除 pending/冻结，返回跳跃信息 {late_celebrations, last_target}"""
        state = self.get_state(uid)
        state["pending_return"] = False
        state["frozen_until"] = 0.0          # 回归时重新激活冷落惩罚
        late = list(state.get("late_celebrations", []))
        state["late_celebrations"] = []
        last = state["skip_log"][-1] if state["skip_log"] else {}
        self.save_uid(uid)
        return {"late_celebrations": late,
                "last_target": last.get("target_date", ""),
                "last_days": last.get("days", 0)}

    def get_skip_status(self, uid: str) -> dict:
        """当前跳跃状态（查询用）"""
        state = self.get_state(uid)
        return {
            "offset_days": state["offset_days"],
            "pending_return": state["pending_return"],
            "frozen_until": state["frozen_until"],
            "skip_log": state["skip_log"][-10:],
        }
