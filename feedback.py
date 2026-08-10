# -*- coding: utf-8 -*-
"""反馈采集与推荐记忆：本地 JSON 持久化，无第三方依赖。

- 每位用户维护：like/dislike 计数（按菜名）与最近推荐历史
- dish_score：like +0.1/次（上限 +2.0）、dislike -0.3/次（下限 -1.0），
  按距最后反馈的天数衰减 0.95^days（无反馈时保持基准分 1.0）
- recently_recommended：3 天内推荐过的菜在下次推荐时排除（推荐历史去重）
- 线程安全：内部锁保护；写入采用临时文件 + 原子替换，损坏时回退空数据
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
DEFAULT_FEEDBACK_PATH = DEFAULT_DATA_DIR / "feedback.json"

LIKE_WEIGHT = 0.1
DISLIKE_WEIGHT = 0.3
SCORE_BASE = 1.0
SCORE_MAX = SCORE_BASE + 2.0
SCORE_MIN = -1.0
DECAY_RATE = 0.95
HISTORY_LIMIT = 30
DEFAULT_DEDUP_DAYS = 3


class FeedbackStore:
    """用户反馈与推荐历史存储。"""

    def __init__(
        self, path: Optional[Path] = None, now: Optional[float] = None
    ):
        self.path = Path(path) if path else DEFAULT_FEEDBACK_PATH
        self._lock = threading.Lock()
        self._data: Dict[str, Dict] = {}
        self._now = now  # 测试注入时钟；None 表示用 time.time()
        self._load()

    # ────────────────────── 存储 ──────────────────────

    def _ts(self) -> float:
        return self._now if self._now is not None else time.time()

    def _load(self):
        if not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                self._data = raw
        except (OSError, ValueError):
            self._data = {}

    def save(self) -> None:
        """原子写：先写临时文件再替换，避免写坏主文件。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, str(self.path))
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def _user(self, user_id: str) -> Dict:
        if user_id not in self._data:
            self._data[user_id] = {"likes": {}, "dislikes": {}, "history": []}
        return self._data[user_id]

    # ────────────────────── 反馈 ──────────────────────

    def record_feedback(
        self, user_id: str, dish_name: str, kind: str
    ) -> None:
        """记录一次反馈。kind: like / dislike"""
        kind = "like" if kind == "like" else "dislike"
        dish_name = (dish_name or "").strip()
        if not dish_name:
            return
        with self._lock:
            user = self._user(user_id)
            key = "likes" if kind == "like" else "dislikes"
            user[key][dish_name] = user[key].get(dish_name, 0) + 1
            user.setdefault("last_feedback_ts", self._ts())
            self.save()

    def record_recommendation(
        self, user_id: str, dish_names: List[str], ts: Optional[float] = None
    ) -> None:
        """记录一次推荐（可多条），历史截断至 HISTORY_LIMIT。"""
        names = [str(n).strip() for n in dish_names if str(n or "").strip()]
        if not names:
            return
        with self._lock:
            user = self._user(user_id)
            ts = self._ts() if ts is None else ts
            for n in names:
                user["history"].append({"dish": n, "ts": ts})
            user["history"] = user["history"][-HISTORY_LIMIT:]
            self.save()

    # ────────────────────── 查询 ──────────────────────

    def _last_feedback_ts(self, user_id: str) -> Optional[float]:
        user = self._data.get(user_id)
        if not user:
            return None
        # 取该用户任何反馈的最新时间：扫描 likes/dislikes 无法排序，用记录值
        return user.get("last_feedback_ts")

    def dish_score(
        self,
        user_id: str,
        dish_name: str,
        now: Optional[float] = None,
    ) -> float:
        """个人反馈分：1.0 基准；赞/踩计数加权后按衰减回归基准。"""
        user = self._data.get(user_id)
        if not user:
            return SCORE_BASE
        likes = user.get("likes", {}).get(dish_name, 0)
        dislikes = user.get("dislikes", {}).get(dish_name, 0)
        raw = SCORE_BASE + LIKE_WEIGHT * likes - DISLIKE_WEIGHT * dislikes
        raw = max(SCORE_MIN, min(SCORE_MAX, raw))
        last = user.get("last_feedback_ts")
        if last is None:
            return SCORE_BASE
        now = self._ts() if now is None else now
        days = max(0.0, (now - last) / 86400.0)
        decay = DECAY_RATE ** days
        return SCORE_BASE + (raw - SCORE_BASE) * decay

    def recently_recommended(
        self, user_id: str, days: float = DEFAULT_DEDUP_DAYS,
        now: Optional[float] = None,
    ) -> set:
        """返回最近 days 天内推荐过的菜名集合（用于推荐去重）。"""
        user = self._data.get(user_id)
        if not user:
            return set()
        now = self._ts() if now is None else now
        cutoff = now - days * 86400.0
        return {
            h["dish"] for h in user.get("history", []) if h.get("ts", 0) >= cutoff
        }

    def last_recommended(self, user_id: str) -> Optional[str]:
        """最近一次推荐的主菜名（/好吃 不带菜名时使用）。"""
        user = self._data.get(user_id)
        if not user:
            return None
        history = user.get("history") or []
        if not history:
            return None
        return history[-1].get("dish")

    def summary(self, user_id: str) -> str:
        """个人统计文本（/我的口味）。"""
        user = self._data.get(user_id)
        if not user or not (user.get("likes") or user.get("dislikes") or user.get("history")):
            return "还没有反馈记录～ 吃到好吃的回复「/好吃」，踩雷了回复「/不好吃」，推荐会越来越懂你。"
        lines = []
        likes = sorted(user.get("likes", {}).items(), key=lambda x: -x[1])
        dislikes = sorted(user.get("dislikes", {}).items(), key=lambda x: -x[1])
        if likes:
            top = "、".join(f"{n}×{c}" for n, c in likes[:3])
            lines.append(f"👍 最爱：{top}")
        if dislikes:
            top = "、".join(f"{n}×{c}" for n, c in dislikes[:3])
            lines.append(f"👎 踩雷：{top}")
        history = user.get("history") or []
        if history:
            names = [h["dish"] for h in history[-3:]]
            lines.append(f"🕐 最近推荐过：{'、'.join(names)}")
        lines.append("反馈越多，推荐越准～")
        return "\n".join(lines)
