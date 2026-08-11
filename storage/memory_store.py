"""storage/memory_store.py - SQLite 长期记忆存储

Sprint 1 S1-03 产出物。
替代 memory_manager.py 的 JSON 后端，使用 SQLite 存储。
保留与 LongTermMemory 完全相同的公开 API。

用法:
    from storage.memory_store import SQLiteMemoryManager
    mem = SQLiteMemoryManager(pool)
    mem.add_event(uid, event)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Dict, List, Optional

from ..emotion_engine import DIM_ICONS, DIM_LABELS
from .pool import ConnectionPool

logger = logging.getLogger("soulsync.storage.memory")


def emotion_anchor(emotions: Optional[dict], top_n: int = 2) -> str:
    """从 8 维情感快照提取情感锚点文本"""
    if not emotions:
        return ""
    dims = sorted(
        ((v, d) for d, v in emotions.items() if isinstance(v, (int, float))),
        reverse=True,
    )
    parts = [
        f"{DIM_ICONS.get(d, '•')}{DIM_LABELS.get(d, d)}{v:.0f}"
        for v, d in dims[:top_n]
    ]
    return " · ".join(parts)


class SQLiteMemoryManager:
    """SQLite 长期记忆管理器（与 LongTermMemory 同 API）"""

    def __init__(self, pool: ConnectionPool, max_events_per_user: int = 50, half_life_days: float = 30.0):
        self.pool = pool
        self.max_events = max_events_per_user
        self.half_life_days = max(1.0, float(half_life_days))
        self._event_hook = None
        # 内存缓存（热数据）
        self._cache: Dict[str, List[dict]] = {}
        self._load_all_to_cache()

    def set_half_life(self, days: float):
        self.half_life_days = max(1.0, float(days))

    def set_event_hook(self, callback):
        """注册事件写入回调 callback(user_id, event)"""
        self._event_hook = callback

    # ─── 写入 ─────────────────────────────────────────────────

    def add_event(self, user_id: str, event: dict):
        """添加一条重要情感事件"""
        ts = time.time()
        event["ts"] = ts
        event.setdefault("vividness", 100)
        event.setdefault("last_recalled_ts", 0)
        event.setdefault("important", False)

        with self.pool.connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO long_term_memory
                   (user_id, ts, description, message, emotions, favorability,
                    fav_delta, stage, vividness, last_recalled_ts, important, compressed, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (user_id, ts,
                 event.get("description", ""),
                 event.get("message", ""),
                 json.dumps(event.get("emotions", {}), ensure_ascii=False),
                 event.get("favorability", 0),
                 event.get("fav_delta", 0),
                 event.get("stage", ""),
                 event.get("vividness", 100),
                 event.get("last_recalled_ts", 0),
                 1 if event.get("important") else 0,
                 ts),
            )
            # 超过上限则淘汰最旧的
            count = conn.execute(
                "SELECT COUNT(*) as c FROM long_term_memory WHERE user_id=?", (user_id,)
            ).fetchone()["c"]
            if count > self.max_events:
                conn.execute(
                    """DELETE FROM long_term_memory WHERE user_id=? AND ts NOT IN
                       (SELECT ts FROM long_term_memory WHERE user_id=?
                        ORDER BY ts DESC LIMIT ?)""",
                    (user_id, user_id, self.max_events),
                )
            conn.commit()

        # 更新缓存
        if user_id not in self._cache:
            self._cache[user_id] = []
        self._cache[user_id].append(event)
        if len(self._cache[user_id]) > self.max_events:
            self._cache[user_id] = self._cache[user_id][-self.max_events:]

        if self._event_hook:
            try:
                self._event_hook(user_id, event)
            except Exception:
                pass

    # ─── 遗忘曲线 ─────────────────────────────────────────────

    @staticmethod
    def vividness_of(event: dict, half_life_days: float = 30.0, now: float = 0.0) -> int:
        if event.get("important"):
            return 100
        now = now or time.time()
        base = float(event.get("vividness", 100))
        anchor = event.get("last_recalled_ts") or event.get("ts") or now
        days = max(0.0, (now - anchor) / 86400.0)
        return max(5, min(100, round(base * 0.5 ** (days / max(1.0, half_life_days)))))

    @staticmethod
    def _vividness_tone(event: dict) -> str:
        em = event.get("emotions") or {}
        if isinstance(em, str):
            try:
                em = json.loads(em)
            except Exception:
                em = {}
        if em.get("joy", 0) >= 60 or em.get("trust", 0) >= 60:
            return "温暖的"
        if em.get("sadness", 0) >= 55 or em.get("anger", 0) >= 55 or em.get("disgust", 0) >= 55:
            return "苦涩的"
        if em.get("surprise", 0) >= 55 or em.get("anticipation", 0) >= 55:
            return "难忘的"
        return "久远的"

    @staticmethod
    def _format_event(event: dict, vividness: int) -> str:
        ts_str = time.strftime("%m-%d %H:%M", time.localtime(event.get("ts", 0)))
        fav = event.get("favorability", "?")
        stage = event.get("stage", "")
        if vividness >= 60:
            return f"[{ts_str}] 好感={fav} {stage} | {event.get('description', '')}"
        tone = SQLiteMemoryManager._vividness_tone(event)
        return f"[{ts_str}] 好感={fav} {stage} | 模糊的回忆（{tone}一段记忆 · 清晰度{vividness}%）"

    # ─── 查询 ─────────────────────────────────────────────────

    def get_events(self, user_id: str, limit: int = 10) -> List[dict]:
        """获取最近 N 条事件（优先缓存）"""
        if user_id in self._cache:
            return self._cache[user_id][-limit:]
        # 回源
        with self.pool.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM long_term_memory WHERE user_id=? ORDER BY ts DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        events = [self._row_to_event(r) for r in reversed(rows)]
        self._cache[user_id] = events
        return events

    def get_summary(self, user_id: str) -> str:
        events = self.get_events(user_id, 5)
        if not events:
            return "暂无长期记忆。"
        lines = []
        for e in events:
            v = self.vividness_of(e, self.half_life_days)
            lines.append(self._format_event(e, v))
        return "\n".join(lines)

    def get_faded_events(self, user_id: str, limit: int = 3, max_vividness: int = 80) -> List[dict]:
        events = [e for e in self.get_events(user_id, 50)
                  if not e.get("important")
                  and self.vividness_of(e, self.half_life_days) < max_vividness]
        events.sort(key=lambda e: self.vividness_of(e, self.half_life_days))
        return events[:limit]

    def recall(self, user_id: str, ts: float) -> Optional[dict]:
        now = time.time()
        with self.pool.connect() as conn:
            conn.execute(
                "UPDATE long_term_memory SET last_recalled_ts=?, vividness=100 WHERE user_id=? AND ts=?",
                (now, user_id, ts),
            )
            conn.commit()
        # 更新缓存
        for e in self._cache.get(user_id, []):
            if e.get("ts") == ts:
                e["last_recalled_ts"] = now
                e["vividness"] = 100
                return e
        return None

    def mark_important(self, user_id: str, ts: float) -> Optional[dict]:
        with self.pool.connect() as conn:
            conn.execute(
                "UPDATE long_term_memory SET important=1, vividness=100 WHERE user_id=? AND ts=?",
                (user_id, ts),
            )
            conn.commit()
        for e in self._cache.get(user_id, []):
            if e.get("ts") == ts:
                e["important"] = True
                e["vividness"] = 100
                return e
        return None

    def forget(self, user_id: str, ts: float) -> bool:
        with self.pool.connect() as conn:
            cur = conn.execute(
                "DELETE FROM long_term_memory WHERE user_id=? AND ts=?",
                (user_id, ts),
            )
            conn.commit()
        if cur.rowcount > 0:
            self._cache.pop(user_id, None)
            return True
        return False

    def get_timeline(self, user_id: str, limit: int = 15) -> List[dict]:
        events = self.get_events(user_id, limit)
        out = []
        for e in events:
            anchor = emotion_anchor(e.get("emotions") if isinstance(e.get("emotions"), dict) else {})
            out.append({
                "ts": e.get("ts", 0),
                "ts_str": time.strftime("%m-%d %H:%M", time.localtime(e.get("ts", 0))),
                "favorability": e.get("favorability"),
                "stage": e.get("stage", ""),
                "fav_delta": e.get("fav_delta"),
                "anchor": anchor,
                "vividness": self.vividness_of(e, self.half_life_days),
                "important": bool(e.get("important")),
                "description": e.get("description", ""),
                "message": e.get("message", ""),
            })
        return out

    def get_key_memories(self, user_id: str, limit: int = 5) -> List[dict]:
        events = self.get_events(user_id, 50)
        keys = []
        for e in events:
            fav = abs(float(e.get("fav_delta", 0.0)))
            desc = e.get("description", "")
            score = 0
            if e.get("important"):
                score += 1000
            if fav >= 2:
                score += int(fav * 50)
            if any(m in desc for m in ("🌱", "💔", "🌫️")):
                score += 300
            if "🎉" in desc:
                score += 200
            if score > 0:
                keys.append((score, e))
        keys.sort(key=lambda x: (-x[0], -float(x[1].get("ts", 0))))
        return [e for _, e in keys][:limit]

    def clear_user(self, user_id: str):
        with self.pool.connect() as conn:
            conn.execute("DELETE FROM long_term_memory WHERE user_id=?", (user_id,))
            conn.commit()
        self._cache.pop(user_id, None)

    def clear_all(self):
        with self.pool.connect() as conn:
            conn.execute("DELETE FROM long_term_memory")
            conn.commit()
        self._cache.clear()

    def save_all(self):
        """兼容旧 API：SQLite 实时写入，此方法为空操作"""
        pass

    # ─── 内部方法 ─────────────────────────────────────────────

    def _row_to_event(self, row) -> dict:
        """将 sqlite3.Row 转为 event dict"""
        d = dict(row)
        d["emotions"] = json.loads(d.get("emotions", "{}")) if isinstance(d.get("emotions"), str) else d.get("emotions", {})
        d["important"] = bool(d.get("important", 0))
        d["compressed"] = bool(d.get("compressed", 0))
        return d

    def _load_all_to_cache(self):
        """启动时加载全部到缓存"""
        with self.pool.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM long_term_memory ORDER BY user_id, ts"
            ).fetchall()
        for row in rows:
            uid = row["user_id"]
            if uid not in self._cache:
                self._cache[uid] = []
            self._cache[uid].append(self._row_to_event(row))
        logger.info(f"[SQLiteMemory] 加载 {sum(len(v) for v in self._cache.values())} 条记忆")
