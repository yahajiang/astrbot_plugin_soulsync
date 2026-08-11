"""storage/leaderboard_cache.py - 排行榜缓存管理器

Sprint 2 S2-01/S2-02/S2-03 产出物。
好感变更后异步刷新排行榜缓存，/排行 命令优先读缓存。

用法:
    from storage.leaderboard_cache import LeaderboardCache
    cache = LeaderboardCache(pool)
    cache.refresh()  # 异步刷新
    top = cache.get_top("favorability", n=10)
"""

from __future__ import annotations

import logging
import threading
import time
from typing import List, Optional

from .pool import ConnectionPool

logger = logging.getLogger("soulsync.storage.leaderboard")

TOP_N = 20  # 缓存最多 20 名


class LeaderboardCache:
    """排行榜 SQLite 缓存"""

    def __init__(self, pool: ConnectionPool):
        self.pool = pool
        self._refresh_lock = threading.Lock()
        self._last_refresh = 0.0
        self._min_interval = 3.0  # 最小刷新间隔（秒）

    def refresh(self, profiles: dict = None):
        """刷新排行榜缓存（线程安全，最小间隔 3s）

        Args:
            profiles: {uid: EmotionProfile} 字典，传入时从内存刷新（更快）
        """
        now = time.time()
        if now - self._last_refresh < self._min_interval:
            return
        with self._refresh_lock:
            if now - self._last_refresh < self._min_interval:
                return
            self._last_refresh = now
            try:
                self._do_refresh(profiles)
            except Exception as e:
                logger.warning(f"刷新排行榜缓存失败: {e}")

    def _do_refresh(self, profiles: dict = None):
        """执行刷新"""
        if profiles:
            # 从内存刷新（快速路径）
            items = []
            for uid, p in profiles.items():
                items.append({
                    "user_id": uid,
                    "user_name": getattr(p, "user_name", "") or uid,
                    "favorability": getattr(p, "favorability", 0),
                    "intimacy": getattr(p, "intimacy", 0),
                    "stage_label": getattr(p, "stage_label", ""),
                })
        else:
            # 从数据库刷新
            with self.pool.connect() as conn:
                rows = conn.execute(
                    "SELECT user_id, user_name, favorability, intimacy, stage_label FROM user_profile"
                ).fetchall()
            items = [dict(r) for r in rows]

        now = time.time()

        # 正向排行（好感从高到低）
        items.sort(key=lambda x: x["favorability"], reverse=True)
        self._write_cache("favorability", items[:TOP_N], now)

        # 负向排行（好感从低到高）
        items.sort(key=lambda x: x["favorability"])
        self._write_cache("negative_favorability", items[:TOP_N], now)

    def _write_cache(self, rank_type: str, items: list, now: float):
        """写入缓存表"""
        with self.pool.connect() as conn:
            conn.execute("DELETE FROM leaderboard_cache WHERE rank_type=?", (rank_type,))
            batch = [
                (rank_type, i + 1, item["user_id"], item["user_name"],
                 item["favorability"], item["intimacy"], item["stage_label"], now)
                for i, item in enumerate(items)
            ]
            conn.executemany(
                "INSERT INTO leaderboard_cache VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                batch,
            )
            conn.commit()

    def get_top(self, rank_type: str, n: int = 10) -> List[dict]:
        """获取排行榜 TOP n（优先缓存，缓存为空时回退实时查询）"""
        n = max(1, min(20, n))
        with self.pool.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM leaderboard_cache WHERE rank_type=? AND rank<=? ORDER BY rank",
                (rank_type, n),
            ).fetchall()
        if rows:
            return [dict(r) for r in rows]

        # 缓存为空，回退实时查询
        self._do_refresh()
        with self.pool.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM leaderboard_cache WHERE rank_type=? AND rank<=? ORDER BY rank",
                (rank_type, n),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_count(self) -> int:
        """获取缓存中的用户总数"""
        with self.pool.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT user_id) as c FROM leaderboard_cache"
            ).fetchone()
        return row["c"] if row else 0
