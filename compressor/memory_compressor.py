"""compressor/memory_compressor.py - 记忆压缩器

Sprint 3 S3-02 产出物。
当长期记忆 > 20 条时，将旧 10 条压缩成 1 条"泛化摘要"（权重置为 0.3）。

用法:
    from compressor.memory_compressor import MemoryCompressor
    comp = MemoryCompressor(pool)
    comp.check_and_compress(user_id)
"""

from __future__ import annotations

import json
import logging
import time
from typing import List

from .keyword_extractor import extract_keywords

logger = logging.getLogger("soulsync.compressor")

COMPRESS_THRESHOLD = 20    # 超过此条数触发压缩
COMPRESS_BATCH = 10        # 每次压缩的旧记忆条数
COMPRESS_SUMMARY_WEIGHT = 0.3  # 摘要权重


class MemoryCompressor:
    """记忆压缩器：将旧记忆压缩为泛化摘要"""

    def __init__(self, pool):
        self.pool = pool

    def check_and_compress(self, user_id: str) -> bool:
        """检查并压缩用户记忆，返回是否执行了压缩"""
        with self.pool.connect() as conn:
            count = conn.execute(
                "SELECT COUNT(*) as c FROM long_term_memory WHERE user_id=? AND compressed=0",
                (user_id,),
            ).fetchone()["c"]

            if count <= COMPRESS_THRESHOLD:
                return False

            # 取最旧的 COMPRESS_BATCH 条未压缩记忆
            rows = conn.execute(
                """SELECT ts, description, message, emotions, favorability, stage
                   FROM long_term_memory
                   WHERE user_id=? AND compressed=0 AND important=0
                   ORDER BY ts ASC LIMIT ?""",
                (user_id, COMPRESS_BATCH),
            ).fetchall()

            if len(rows) < 3:
                return False

            # 生成摘要
            descriptions = [r["description"] for r in rows if r["description"]]
            keywords = extract_keywords(descriptions, top_n=5)
            first_ts = rows[0]["ts"]
            last_ts = rows[-1]["ts"]
            fav_range = f"{rows[0]['favorability']:.0f}→{rows[-1]['favorability']:.0f}"
            stage_range = f"{rows[0].get('stage', '')}~{rows[-1].get('stage', '')}"
            summary_desc = f"📝 历史摘要（{len(rows)}条压缩）：关键词[{','.join(keywords)}] 好感{fav_range} 阶段{stage_range}"

            # 合并情感（取平均）
            all_emotions = {}
            for r in rows:
                em = json.loads(r["emotions"]) if isinstance(r["emotions"], str) else r["emotions"]
                for k, v in em.items():
                    all_emotions.setdefault(k, []).append(v)
            avg_emotions = {k: sum(v) / len(v) for k, v in all_emotions.items()}

            # 插入摘要记忆
            now = time.time()
            conn.execute(
                """INSERT INTO long_term_memory
                   (user_id, ts, description, message, emotions, favorability,
                    fav_delta, stage, vividness, last_recalled_ts, important, compressed, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?)""",
                (user_id, now, summary_desc, "",
                 json.dumps(avg_emotions, ensure_ascii=False),
                 rows[-1]["favorability"],
                 rows[-1]["favorability"] - rows[0]["favorability"],
                 stage_range,
                 30,  # 摘要初始清晰度较低
                 now,
                 now),
            )

            # 标记旧记忆为已压缩
            old_ts = [r["ts"] for r in rows]
            placeholders = ",".join("?" * len(old_ts))
            conn.execute(
                f"UPDATE long_term_memory SET compressed=1 WHERE user_id=? AND ts IN ({placeholders})",
                [user_id] + old_ts,
            )
            conn.commit()

        logger.info(f"[Compressor] {user_id}: 压缩 {len(rows)} 条旧记忆为摘要")
        return True

    def get_compression_stats(self, user_id: str) -> dict:
        """获取用户记忆压缩统计"""
        with self.pool.connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as c FROM long_term_memory WHERE user_id=?",
                (user_id,),
            ).fetchone()["c"]
            compressed = conn.execute(
                "SELECT COUNT(*) as c FROM long_term_memory WHERE user_id=? AND compressed=1",
                (user_id,),
            ).fetchone()["c"]
            summaries = conn.execute(
                "SELECT COUNT(*) as c FROM long_term_memory WHERE user_id=? AND compressed=1 AND vividness<=50",
                (user_id,),
            ).fetchone()["c"]
        return {
            "total": total,
            "compressed": compressed,
            "summaries": summaries,
            "active": total - compressed,
        }
