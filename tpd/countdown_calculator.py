"""TPD - 倒计时计算与排序（事件源扫描 + 优先级排序 + 提及规则）

优先级 = 事件权重 × (1 / 距离天数) × 历史关注度系数
- 权重：里程碑 5 / 认识周年·生日 4 / 危机纪念·私人约定 3 / 节日·自定义 2
- 关注度：近 30 天提及历史，每次 +0.1，上限 1.5
- 每轮最多提及 1 个；同一事件 freq_days 天内最多提及 1 次（提及状态持久化）

事件源（日期型）：
- 认识周年 / 用户生日 / 自定义纪念日 / 节日：anniversary.py get_countdown_sources
- 危机纪念 / 角色生日 / 关系里程碑：Provider 接口（Phase D 用真实数据接线）
"""

from __future__ import annotations

import datetime
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..anniversary import AnniversaryManager

# 事件类型权重（doc 5.5）
KIND_WEIGHTS: Dict[str, float] = {
    "milestone": 5.0,     # 关系里程碑（阶段跃迁）
    "first_meet": 4.0,    # 认识周年
    "birthday": 4.0,      # 用户/角色生日
    "crisis": 3.0,        # 危机事件纪念
    "anniversary": 2.0,   # 自定义纪念日 / 私人约定（数据层合并）
    "festival": 2.0,      # 传统节日
}

# 可提及代表日（doc 5.1：T-7 隐约提及 / T-3 主动提起 / T-1 明确倒计时 / T-0 当天 / T+1 回味 / T+4 渐淡）
MENTIONABLE_DAYS = (7, 3, 1, 0, -1, -4)


@dataclass
class CountdownEvent:
    key: str          # 唯一标识（kind:name:YYYY-MM-DD）
    name: str
    kind: str
    occurrence: datetime.date
    days_left: int    # 事件日 - 今天（正=即将到来，0=当天，负=刚过）
    weight: float
    score: float = 0.0
    attention: float = 1.0

    def as_dict(self) -> dict:
        return {
            "key": self.key, "name": self.name, "kind": self.kind,
            "occurrence": self.occurrence.isoformat(), "days_left": self.days_left,
            "weight": self.weight, "score": self.score, "attention": self.attention,
        }


class CountdownCalculator:
    """倒计时计算器：事件源扫描 + 优先级排序 + 提及状态"""

    def __init__(self, data_dir: str, sources: Optional[dict] = None):
        self.data_dir = Path(data_dir)
        self.state_file = self.data_dir / "countdown_state.json"
        self.sources = sources or {}
        self._state: Dict[str, Dict[str, dict]] = {}  # uid -> key -> {last, history:[]}

    # ── 事件源 ──────────────────────────────────────────
    def get_active_events(self, uid: str, today: Optional[datetime.date] = None,
                          window_days: int = 30, now: Optional[float] = None) -> List[CountdownEvent]:
        """窗口 [-window_days, +window_days] 内全部倒计时事件（已算分，未排序）"""
        today = today or datetime.date.today()
        events: List[CountdownEvent] = []

        anniv = self.sources.get("anniversaries")
        if isinstance(anniv, AnniversaryManager):
            for s in anniv.get_countdown_sources(uid, today, window_days):
                events.append(self._make_event(s["name"], s["kind"], s["occurrence"], today))
        # 危机纪念：resolved_at 周年（Provider: uid -> [{title, resolved_at_ts}]）
        crisis_provider = self.sources.get("crisis")
        if callable(crisis_provider):
            for item in (crisis_provider(uid) or []):
                title = item.get("title") or "危机纪念日"
                try:
                    ts = float(item.get("resolved_at_ts") or item.get("resolved_at") or 0)
                except (TypeError, ValueError):
                    continue
                if ts <= 0:
                    continue
                rd = datetime.datetime.fromtimestamp(ts).date()
                for occ in self._occurrences(rd.month, rd.day, today, window_days):
                    events.append(self._make_event(title, "crisis", occ, today))
        # 角色生日（Provider: () -> {name, month, day} 或 None）
        role_birthday = self.sources.get("role_birthday")
        if callable(role_birthday):
            rb = role_birthday()
            if rb and rb.get("month") and rb.get("day"):
                for occ in self._occurrences(int(rb["month"]), int(rb["day"]), today, window_days):
                    events.append(self._make_event(rb.get("name", "角色生日"), "birthday", occ, today))
        # 关系里程碑（Provider: uid -> [{name, days_left}]，无日期，按估算距离）
        milestone_provider = self.sources.get("milestone")
        if callable(milestone_provider):
            for item in (milestone_provider(uid) or []):
                days = int(item.get("days_left", 0))
                occ = today + datetime.timedelta(days=days)
                events.append(self._make_event(item.get("name", "里程碑"), "milestone", occ, today))

        for e in events:
            e.score = self._score(e, uid, today, now)
        return events

    def _make_event(self, name: str, kind: str, occurrence: datetime.date,
                    today: datetime.date) -> CountdownEvent:
        days_left = (occurrence - today).days
        return CountdownEvent(
            key=f"{kind}:{name}:{occurrence.isoformat()}",
            name=name, kind=kind, occurrence=occurrence, days_left=days_left,
            weight=KIND_WEIGHTS.get(kind, 2.0),
        )

    def _occurrences(self, month: int, day: int, today: datetime.date,
                     window_days: int) -> List[datetime.date]:
        """日期型事件的 下次/上次 出现（窗口内）"""
        result = []
        for year in (today.year, today.year + 1):
            try:
                d = datetime.date(year, month, day)
            except ValueError:
                continue
            if today <= d <= today + datetime.timedelta(days=window_days):
                result.append(d)
        for year in (today.year, today.year - 1):
            try:
                d = datetime.date(year, month, day)
            except ValueError:
                continue
            if today - datetime.timedelta(days=window_days) <= d < today:
                result.append(d)
        return result

    # ── 排序 ────────────────────────────────────────────
    def _attention(self, uid: str, key: str, now: Optional[float] = None) -> float:
        self._load()
        now = now or time.time()
        history = self._state.get(uid, {}).get(key, {}).get("history", [])
        recent = [t for t in history if now - t <= 30 * 86400]
        return min(1.5, 1.0 + 0.1 * len(recent))

    def _score(self, event: CountdownEvent, uid: str, today: datetime.date,
               now: Optional[float] = None) -> float:
        dist = max(1.0, abs(event.days_left))
        return event.weight * (1.0 / dist) * self._attention(uid, event.key, now)

    # ── 提及选择 ────────────────────────────────────────
    def select_for_mention(self, uid: str, today: Optional[datetime.date] = None,
                           now: Optional[float] = None, start_days: int = 7,
                           freq_hours: float = 24) -> Optional[CountdownEvent]:
        """选择本轮应提及的倒计时事件（可提及代表日 + 未在 freq 内提及 + 得分最高）"""
        today = today or datetime.date.today()
        now = now or time.time()
        candidates = [
            e for e in self.get_active_events(uid, today, window_days=max(7, start_days), now=now)
            if e.days_left in MENTIONABLE_DAYS
        ]
        candidates.sort(key=lambda e: -e.score)
        for e in candidates:
            last = self._state.get(uid, {}).get(e.key, {}).get("last", 0)
            if now - last >= freq_hours * 3600:
                return e
        return None

    def mark_mentioned(self, uid: str, event: CountdownEvent, ts: Optional[float] = None):
        """记录提及（更新冷却与近 30 天关注度历史）"""
        self._load()
        ts = ts or time.time()
        uid_state = self._state.setdefault(uid, {})
        entry = uid_state.setdefault(event.key, {"last": 0, "history": []})
        entry["last"] = ts
        entry["history"] = [t for t in entry["history"] if ts - t <= 30 * 86400][-49:]
        entry["history"].append(ts)
        self._save()

    # ── 持久化 ──────────────────────────────────────────
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
            tmp.write_text(json.dumps(self._state, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.state_file)
        except Exception:
            pass
