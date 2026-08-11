"""storage/stats_store.py - SQLite 情感数据统计存储

Sprint 1 S1-04 产出物。
替代 stats_tracker.py 的 JSON 后端，使用月度分表 + 窗口函数。
保留与 StatsTracker 完全相同的公开 API。

用法:
    from storage.stats_store import SQLiteStatsTracker
    st = SQLiteStatsTracker(pool)
    st.update(uid, fav, intimacy, ...)
    entries = st.trend(uid, days=14)
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

from .pool import ConnectionPool
from .schema import ensure_snapshot_table, get_snapshot_table, list_snapshot_tables

logger = logging.getLogger("soulsync.storage.stats")


class SQLiteStatsTracker:
    """SQLite 每日情感数据快照追踪器（与 StatsTracker 同 API）"""

    def __init__(self, pool: ConnectionPool, max_days: int = 30):
        self.pool = pool
        self.max_days = max(7, int(max_days))

    # ─── 写入 ─────────────────────────────────────────────────

    def update(self, uid: str, favorability: float, intimacy: float,
               stage_index: int, stage_label: str,
               total_interactions: int, positive: int, negative: int,
               conversation_turns: int):
        """更新今日快照（每天每用户一条，INSERT OR REPLACE）"""
        today = date.today()
        today_str = today.isoformat()
        table = get_snapshot_table(today.year, today.month)

        with self.pool.connect() as conn:
            # 确保当月表存在
            ensure_snapshot_table(conn, today.year, today.month)
            conn.execute(
                f"""INSERT OR REPLACE INTO {table}
                    (user_id, date, fav, int, stage, stage_label,
                     interactions, positive, negative, turns)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (uid, today_str,
                 round(favorability, 2), round(intimacy, 2),
                 stage_index, stage_label,
                 total_interactions, positive, negative, conversation_turns),
            )
            conn.commit()

    def force_save(self):
        """兼容旧 API：SQLite 实时写入，此方法为空操作"""
        pass

    # ─── 查询 ─────────────────────────────────────────────────

    def trend(self, uid: str, days: Optional[int] = None) -> List[dict]:
        """获取最近 N 天趋势数据"""
        limit = days or self.max_days
        cutoff = (date.today() - timedelta(days=limit)).isoformat()

        with self.pool.connect() as conn:
            # 跨月度分表查询
            all_entries = []
            for tbl in list_snapshot_tables(conn):
                rows = conn.execute(
                    f"SELECT * FROM {tbl} WHERE user_id=? AND date>=? ORDER BY date",
                    (uid, cutoff),
                ).fetchall()
                all_entries.extend([dict(r) for r in rows])

        all_entries.sort(key=lambda e: e["date"])
        return all_entries[-limit:]

    def summary(self, uid: str, days: int = 14) -> dict:
        """概览统计：最高/最低/平均/涨跌天数/净变化"""
        entries = self.trend(uid, days)
        if not entries:
            return {"has_data": False, "days": 0}
        favs = [e["fav"] for e in entries]
        ints = [e["int"] for e in entries]
        deltas = [favs[i] - favs[i - 1] for i in range(1, len(favs))]
        first, last = entries[0], entries[-1]
        return {
            "has_data": True,
            "days": len(entries),
            "first_date": first["date"],
            "last_date": last["date"],
            "start_fav": first["fav"],
            "end_fav": last["fav"],
            "max_fav": max(favs),
            "min_fav": min(favs),
            "avg_fav": round(sum(favs) / len(favs), 2),
            "max_int": max(ints),
            "min_int": min(ints),
            "avg_int": round(sum(ints) / len(ints), 2),
            "delta": round(last["fav"] - first["fav"], 2),
            "up_days": sum(1 for d in deltas if d > 0.01),
            "down_days": sum(1 for d in deltas if d < -0.01),
            "total_interactions": last["interactions"],
        }

    # ─── 文本图表 ─────────────────────────────────────────────

    def build_text_chart(self, uid: str, days: int = 14) -> List[str]:
        """好感度/亲密度趋势文本图表"""
        entries = self.trend(uid, days)
        if not entries:
            return ["暂无统计数据。", "用户发送消息后开始自动记录（每天一条快照）。"]
        lines = []
        w = 20
        for e in entries:
            md = e["date"][5:]  # MM-DD
            fav = e["fav"]
            it = e["int"]
            fav_n = max(0, min(w, int((fav + 100) / 200 * w)))
            int_n = max(0, min(w, int(it / 100 * w)))
            bar = "█" * fav_n + "░" * (w - fav_n)
            i_bar = "█" * int_n + "░" * (w - int_n)
            fav_s = f"{fav:+.1f}"
            lines.append(f"{md} 好感 {fav_s:>7} {bar}")
            lines.append(f"{md} 亲密 {it:>6.1f} {i_bar}")
        return lines

    def to_web(self, uid: str, days: int = 7) -> dict:
        entries = self.trend(uid, days)
        return {
            "dates": [e["date"][5:] for e in entries],
            "fav": [e["fav"] for e in entries],
            "int": [e["int"] for e in entries],
            "stages": [e["stage_label"] for e in entries],
        }
