"""SoulSync - 人格护栏（v2.20 自动化安全机制）

- 自动锁定：连续 50 轮无显著波动且稳定度达标 → 自动锁定，防止噪声数据干扰
- 自动解锁：极端情感事件（背叛、连续冷落 72h+）→ 自动解锁，允许角色重新适应
- 震荡保护：24h 内 ≥3 次剧烈变化 → 回滚至最近稳定快照并记录日志
- 管理员临时锁定：/人格 设置 后 2h 内自动化微调暂停，保护管理意图
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ..trainer_storage import TrainerStorage
from ..trainer_types import PersonaParams
from .persona_modifier import PersonaModifier
from .persona_params import PARAM_META

# 参数快照里排除的元字段
_SKIP_KEYS = ("stability", "total_training_turns", "locked", "last_updated")


class PersonaGuard:
    FILE = "persona_guard.json"

    # 自动锁定
    AUTO_LOCK_STABLE_TURNS = 50        # 连续无显著波动轮数
    AUTO_LOCK_MIN_STABILITY = 70.0     # 稳定度达标线
    TOTAL_SIGNIFICANT_CHANGE = 3.0     # 单轮总变化 ≥ 此值视为显著波动

    # 震荡保护
    OSCILLATION_WINDOW_SEC = 86400     # 24h
    OSCILLATION_COUNT = 3              # 24h 内剧烈变化 ≥3 次
    OSCILLATION_MIN_CHANGE = 3.0       # 单轮总变化 ≥ 此值视为剧烈变化

    # 管理员临时锁定
    MANUAL_LOCK_SEC = 7200             # 2h

    LOG_LIMIT = 20

    def __init__(self, storage: TrainerStorage, user_id: str, modifier: PersonaModifier):
        self.storage = storage
        self.user_id = user_id
        self.modifier = modifier
        self._state: dict = self.storage.load(self.user_id, self.FILE, default={}) or {}

    # ── 状态持久化 ──
    def _save(self):
        self.storage.save(self.user_id, self.FILE, self._state)

    def _log(self, kind: str, detail: str):
        log = self._state.setdefault("log", [])
        log.append({"ts": time.time(), "kind": kind, "detail": detail})
        self._state["log"] = log[-self.LOG_LIMIT:]

    # ── 快照辅助 ──
    @staticmethod
    def _snapshot(params: PersonaParams) -> Dict[str, float]:
        out = {}
        for name in PARAM_META:
            if name in _SKIP_KEYS or name == "locked":
                continue
            v = getattr(params, name, None)
            if isinstance(v, (int, float)):
                out[name] = float(v)
        return out

    @staticmethod
    def _diff(now_snap: Dict[str, float], prev_snap: Dict[str, float]) -> Dict[str, float]:
        diff = {}
        for name, v in now_snap.items():
            pv = prev_snap.get(name)
            if pv is not None:
                d = v - pv
                if abs(d) >= 1e-9:
                    diff[name] = d
        return diff

    # ── 每轮处理 ──
    def on_turn(self, params: PersonaParams) -> dict:
        """每轮对话后调用：波动统计 + 自动锁定 + 震荡回滚。返回事件 dict。"""
        now = time.time()
        events: dict = {}
        snap = self._snapshot(params)
        prev = self._state.get("last_snapshot")

        total_change = 0.0
        if isinstance(prev, dict):
            total_change = sum(abs(v) for v in self._diff(snap, prev).values())
        significant = total_change >= self.TOTAL_SIGNIFICANT_CHANGE

        # 1. 连续无显著波动轮数
        if not isinstance(prev, dict) or not significant:
            streak = int(self._state.get("stable_streak", 0)) + 1
        else:
            streak = 0
        self._state["stable_streak"] = streak
        self._state["last_snapshot"] = snap

        # 2. 震荡保护：24h 窗口内剧烈变化计数
        if total_change >= self.OSCILLATION_MIN_CHANGE:
            window = [t for t in self._state.get("oscillation_ts", [])
                      if now - t < self.OSCILLATION_WINDOW_SEC]
            window.append(now)
            self._state["oscillation_ts"] = window[-self.OSCILLATION_COUNT:]
            if len(window) >= self.OSCILLATION_COUNT:
                rollback = self._rollback(params)
                if rollback:
                    events["rollback"] = rollback
                    self._state["stable_streak"] = 0
                    self._state["oscillation_ts"] = []
        else:
            # 无剧烈变化轮次（含首轮 prev=None）：更新稳定快照（震荡回滚目标）
            self.refresh_stable_snapshot(params)

        # 3. 自动锁定：连续 50 轮无显著波动 + 稳定度达标 + 未锁定
        if (not params.locked
                and streak >= self.AUTO_LOCK_STABLE_TURNS
                and params.stability >= self.AUTO_LOCK_MIN_STABILITY):
            self.modifier.lock(params)
            self._log("auto_lock", f"连续 {streak} 轮无显著波动，稳定度 {params.stability:.0f}%，自动锁定")
            events["locked"] = True

        self._save()
        return events

    def _rollback(self, params: PersonaParams) -> Optional[dict]:
        """震荡回滚：恢复最近稳定快照（最近一次无显著变化轮次的状态）"""
        stable = self._state.get("stable_snapshot")
        if not isinstance(stable, dict) or not stable:
            return None
        restored = []
        for name, val in stable.items():
            meta = PARAM_META.get(name)
            if not meta or not hasattr(params, name):
                continue
            cur = getattr(params, name)
            if not isinstance(cur, (int, float)):
                continue
            if meta["type"] == "float":
                setattr(params, name, float(val))
            elif meta["type"] == "int":
                setattr(params, name, int(val))
            restored.append(name)
        # 同时回滚字符串参数（仅当快照存在）
        stable_str = self._state.get("stable_snapshot_str") or {}
        for name in PARAM_META:
            if name in _SKIP_KEYS or name == "locked":
                continue
            if name in stable_str and hasattr(params, name):
                cur = getattr(params, name)
                if isinstance(cur, str):
                    setattr(params, name, stable_str[name])
        self._log("rollback", f"24h 内 {self.OSCILLATION_COUNT} 次剧烈变化，回滚 {len(restored)} 项参数")
        return {"restored": len(restored), "params": restored}

    def refresh_stable_snapshot(self, params: PersonaParams):
        """在无显著波动轮次更新稳定快照（供震荡回滚使用）"""
        snap = self._snapshot(params)
        self._state["stable_snapshot"] = snap
        self._state["stable_snapshot_str"] = {
            name: getattr(params, name)
            for name in PARAM_META
            if isinstance(getattr(params, name, None), str)
        }
        self._save()

    # ── 极端事件 → 自动解锁 ──
    def on_extreme_event(self, params: PersonaParams, kind: str):
        """极端情感事件（背叛 / 连续冷落 72h+）：解锁人格参数并记录"""
        if not params.locked:
            return False
        self.modifier.unlock(params)
        self._log("extreme_unlock", f"极端事件 {kind}，自动解锁")
        self._save()
        return True

    # ── 管理员手动设置 → 2h 临时锁定 ──
    def apply_manual_lock(self, params: PersonaParams, duration_sec: Optional[float] = None):
        """/人格 设置（管理员）成功后调用：期限内自动化微调暂停"""
        now = time.time()
        self._state["manual_lock_until"] = now + (duration_sec or self.MANUAL_LOCK_SEC)
        self._state["manual_lock_reason"] = "admin_set"
        self._log("manual_lock", f"管理员手动设置，暂停自动化微调 {self.MANUAL_LOCK_SEC // 3600}h")
        self._save()

    def is_auto_paused(self, params: PersonaParams) -> bool:
        """自动化微调是否暂停（人格锁定 / 管理员临时锁定中）"""
        if params.locked:
            return True
        until = float(self._state.get("manual_lock_until", 0) or 0)
        return time.time() < until

    def manual_lock_remaining(self) -> int:
        """管理员临时锁定剩余秒数（0 表示未锁定）"""
        until = float(self._state.get("manual_lock_until", 0) or 0)
        remaining = int(until - time.time())
        return max(0, remaining)

    # ── 查询 ──
    def get_state(self) -> dict:
        return {
            "stable_streak": int(self._state.get("stable_streak", 0)),
            "oscillation_count_24h": len(self._state.get("oscillation_ts", [])),
            "manual_lock_remaining": self.manual_lock_remaining(),
            "log": self._state.get("log", [])[-self.LOG_LIMIT:],
        }
