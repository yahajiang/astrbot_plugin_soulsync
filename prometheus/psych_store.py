"""prometheus/psych_store.py - 心理画像 SQLite 存储

Project Prometheus Layer 2。
存取灵魂素描生成的棱镜和沟通建议。

用法:
    from prometheus.psych_store import PsychStore
    store = PsychStore(pool)
    store.save(user_id, version, prisms, comm_style, baseline)
    latest = store.get_latest(user_id)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger("soulsync.prometheus.psych")

MAX_VERSIONS = 3  # 保留最近 3 个历史版本


class PsychStore:
    """心理画像存储（user_psych_profile 表）"""

    def __init__(self, pool):
        self.pool = pool

    def save(self, user_id: str, prisms: List[str], comm_style: str,
             baseline: float = 0.4) -> int:
        """保存一条素描记录，返回版本号"""
        with self.pool.connect() as conn:
            # 获取当前最大版本号
            row = conn.execute(
                "SELECT MAX(version) as max_ver FROM user_psych_profile WHERE user_id=?",
                (user_id,),
            ).fetchone()
            max_ver = row["max_ver"] if row and row["max_ver"] else 0
            new_ver = max_ver + 1

            conn.execute(
                """INSERT INTO user_psych_profile
                   (user_id, version, prism_json, comm_style, generated_at, baseline)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, new_ver, json.dumps(prisms, ensure_ascii=False),
                 comm_style, time.time(), baseline),
            )

            # 清理旧版本，保留最近 MAX_VERSIONS 个
            conn.execute(
                """DELETE FROM user_psych_profile
                   WHERE user_id=? AND version NOT IN (
                       SELECT version FROM user_psych_profile
                       WHERE user_id=?
                       ORDER BY version DESC LIMIT ?
                   )""",
                (user_id, user_id, MAX_VERSIONS),
            )
            conn.commit()

        logger.info(f"[PsychStore] {user_id} 保存素描 v{new_ver}，棱镜 {len(prisms)} 条")
        return new_ver

    def get_latest(self, user_id: str) -> Optional[dict]:
        """获取最新的素描记录"""
        with self.pool.connect() as conn:
            row = conn.execute(
                """SELECT * FROM user_psych_profile
                   WHERE user_id=? ORDER BY version DESC LIMIT 1""",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def get_history(self, user_id: str, limit: int = 3) -> List[dict]:
        """获取历史素描记录（最近 N 条）"""
        with self.pool.connect() as conn:
            rows = conn.execute(
                """SELECT * FROM user_psych_profile
                   WHERE user_id=? ORDER BY version DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_last_generated_at(self, user_id: str) -> float:
        """获取上次素描生成时间"""
        latest = self.get_latest(user_id)
        return latest["generated_at"] if latest else 0.0

    def _row_to_dict(self, row) -> dict:
        return {
            "user_id": row["user_id"],
            "version": row["version"],
            "prisms": json.loads(row["prism_json"]) if isinstance(row["prism_json"], str) else row["prism_json"],
            "comm_style": row["comm_style"],
            "generated_at": row["generated_at"],
            "baseline": row["baseline"],
        }
