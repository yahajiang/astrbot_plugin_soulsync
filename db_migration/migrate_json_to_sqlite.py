"""db_migration/migrate_json_to_sqlite.py - 全量数据迁移脚本

Sprint 1 S1-05 产出物。
读取 JSON 文件，批量插入 SQLite，每 500 条 commit 一次，防内存溢出。
迁移 10 万条记录耗时 < 5 分钟。

用法:
    python -m db_migration.migrate_json_to_sqlite /path/to/data_dir

或在代码中:
    from db_migration.migrate_json_to_sqlite import run_migration
    report = run_migration(data_dir)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
import time
from datetime import date
from pathlib import Path

logger = logging.getLogger("soulsync.migration")

BATCH_SIZE = 500  # 每批提交条数


def run_migration(data_dir: Path, db_path: Path | None = None) -> dict:
    """执行全量迁移：JSON → SQLite

    Args:
        data_dir: 插件数据目录（包含 profiles.json 等）
        db_path: SQLite 数据库路径（默认 data_dir/soulsync.db）

    Returns:
        迁移报告 dict
    """
    if db_path is None:
        db_path = data_dir / "soulsync.db"

    report = {
        "tables": {},
        "total_rows": 0,
        "elapsed_sec": 0,
        "errors": [],
    }

    start = time.time()

    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA synchronous=NORMAL")

    # 建表
    _init_tables(conn)

    # 逐表迁移
    report["tables"]["user_profile"] = _migrate_profiles(conn, data_dir)
    report["tables"]["behavior_profile"] = _migrate_behavior(conn, data_dir)
    report["tables"]["show_status"] = _migrate_kv_dict(conn, data_dir, "show_status.json", "show_status")
    report["tables"]["image_mode"] = _migrate_kv_dict(conn, data_dir, "image_mode.json", "image_mode")
    report["tables"]["anniversaries"] = _migrate_anniversaries(conn, data_dir)
    report["tables"]["relationship_role"] = _migrate_relationship_roles(conn, data_dir)
    report["tables"]["long_term_memory"] = _migrate_long_term_memory(conn, data_dir)
    report["tables"]["stats_history"] = _migrate_stats(conn, data_dir)

    report["total_rows"] = sum(t.get("rows", 0) for t in report["tables"].values())
    report["elapsed_sec"] = round(time.time() - start, 2)

    conn.close()
    logger.info(f"迁移完成: {report['total_rows']} 行, 耗时 {report['elapsed_sec']}s")
    return report


def _init_tables(conn: sqlite3.Connection):
    """建表（幂等）"""
    from storage.schema import init_schema
    init_schema(conn)


# ─── profiles.json → user_profile ─────────────────────────────

def _migrate_profiles(conn: sqlite3.Connection, data_dir: Path) -> dict:
    f = data_dir / "profiles.json"
    if not f.exists():
        return {"rows": 0, "skipped": 0}
    data = json.loads(f.read_text(encoding="utf-8"))
    rows = 0
    skipped = 0
    batch = []
    for uid, profile in data.items():
        try:
            # EmotionProfile 字段映射
            fav = profile.get("favorability", 0)
            intimacy = profile.get("intimacy", 0)
            stage_index = profile.get("stage_index", 0)
            stage_label = profile.get("stage_label", "")
            batch.append((
                uid, fav, intimacy, stage_index, stage_label,
                profile.get("attitude_text", ""),
                profile.get("relationship_text", ""),
                profile.get("total_interactions", 0),
                profile.get("positive_interactions", 0),
                profile.get("negative_interactions", 0),
                profile.get("conversation_turns", 0),
                profile.get("first_interaction_ts", 0),
                profile.get("last_interaction_ts", 0),
                profile.get("created_at", 0),
                profile.get("updated_at", 0),
            ))
            rows += 1
        except Exception as e:
            skipped += 1
            logger.warning(f"跳过 profile {uid}: {e}")
        if len(batch) >= BATCH_SIZE:
            conn.executemany(
                "INSERT OR REPLACE INTO user_profile VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                batch,
            )
            conn.commit()
            batch.clear()
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO user_profile VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            batch,
        )
        conn.commit()
    logger.info(f"user_profile: {rows} 行迁移, {skipped} 跳过")
    return {"rows": rows, "skipped": skipped}


# ─── behavior_profiles.json → behavior_profile ────────────────

def _migrate_behavior(conn: sqlite3.Connection, data_dir: Path) -> dict:
    f = data_dir / "behavior_profiles.json"
    if not f.exists():
        return {"rows": 0, "skipped": 0}
    data = json.loads(f.read_text(encoding="utf-8"))
    rows = 0
    skipped = 0
    batch = []
    for uid, bp in data.items():
        try:
            batch.append((
                uid,
                bp.get("current_streak_type", ""),
                bp.get("current_streak_count", 0),
                bp.get("total_reward_accumulated", 0),
                bp.get("total_penalty_accumulated", 0),
                bp.get("betrayal_count", 0),
                bp.get("apology_count", 0),
                bp.get("comeback_count", 0),
                bp.get("last_interaction_ts", 0),
                bp.get("last_betrayal_ts", 0),
                bp.get("last_apology_ts", 0),
                bp.get("last_comeback_ts", 0),
                bp.get("last_active_date", ""),
                bp.get("cold_days", 0),
                bp.get("penalty_last_date", ""),
                bp.get("penalty_frozen_until", 0),
                json.dumps(bp.get("achieved_milestones", []), ensure_ascii=False),
                bp.get("crisis_active", 0),
                bp.get("crisis_type", ""),
                bp.get("crisis_started_ts", 0),
                bp.get("crisis_last_event_ts", 0),
                bp.get("crisis_resolved_count", 0),
                bp.get("crisis_cooldown_until", 0),
                bp.get("crisis_protection_until", 0),
                json.dumps(bp.get("pending_effects", []), ensure_ascii=False),
                bp.get("countdown_last_date", ""),
                bp.get("monthly_report_last", ""),
                bp.get("role_report_last_ts", 0),
                bp.get("time_jump_last_ts", 0),
                bp.get("rde_stage_ctx_last_round", 0),
                json.dumps({k: v for k, v in bp.items()
                           if k not in _BP_FIXED_KEYS}, ensure_ascii=False),
                bp.get("created_at", 0),
                bp.get("updated_at", 0),
            ))
            rows += 1
        except Exception as e:
            skipped += 1
            logger.warning(f"跳过 behavior {uid}: {e}")
        if len(batch) >= BATCH_SIZE:
            conn.executemany(
                "INSERT OR REPLACE INTO behavior_profile VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                batch,
            )
            conn.commit()
            batch.clear()
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO behavior_profile VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            batch,
        )
        conn.commit()
    logger.info(f"behavior_profile: {rows} 行迁移, {skipped} 跳过")
    return {"rows": rows, "skipped": skipped}


_BP_FIXED_KEYS = {
    "current_streak_type", "current_streak_count",
    "total_reward_accumulated", "total_penalty_accumulated",
    "betrayal_count", "apology_count", "comeback_count",
    "last_interaction_ts", "last_betrayal_ts", "last_apology_ts", "last_comeback_ts",
    "last_active_date", "cold_days", "penalty_last_date", "penalty_frozen_until",
    "achieved_milestones", "crisis_active", "crisis_type",
    "crisis_started_ts", "crisis_last_event_ts", "crisis_resolved_count",
    "crisis_cooldown_until", "crisis_protection_until", "pending_effects",
    "countdown_last_date", "monthly_report_last", "role_report_last_ts",
    "time_jump_last_ts", "rde_stage_ctx_last_round",
    "created_at", "updated_at",
}


# ─── KV dict → show_status / image_mode ───────────────────────

def _migrate_kv_dict(conn: sqlite3.Connection, data_dir: Path,
                      filename: str, table: str) -> dict:
    f = data_dir / filename
    if not f.exists():
        return {"rows": 0}
    data = json.loads(f.read_text(encoding="utf-8"))
    batch = [(uid, 1 if enabled else 0) for uid, enabled in data.items()]
    if batch:
        conn.executemany(
            f"INSERT OR REPLACE INTO {table} VALUES (?, ?)",
            batch,
        )
        conn.commit()
    logger.info(f"{table}: {len(batch)} 行迁移")
    return {"rows": len(batch)}


# ─── anniversaries.json → anniversaries ────────────────────────

def _migrate_anniversaries(conn: sqlite3.Connection, data_dir: Path) -> dict:
    f = data_dir / "anniversaries.json"
    if not f.exists():
        return {"rows": 0}
    data = json.loads(f.read_text(encoding="utf-8"))
    rows = 0
    batch = []
    for uid, annivs in data.items():
        if isinstance(annivs, list):
            for a in annivs:
                batch.append((
                    uid,
                    a.get("id", a.get("anniv_id", "")),
                    a.get("name", ""),
                    a.get("date", a.get("date_str", "")),
                    a.get("type", a.get("anniv_type", "")),
                    a.get("created_at", 0),
                ))
                rows += 1
        elif isinstance(annivs, dict):
            for aid, a in annivs.items():
                batch.append((
                    uid, aid,
                    a.get("name", ""),
                    a.get("date", a.get("date_str", "")),
                    a.get("type", a.get("anniv_type", "")),
                    a.get("created_at", 0),
                ))
                rows += 1
        if len(batch) >= BATCH_SIZE:
            conn.executemany(
                "INSERT OR REPLACE INTO anniversaries VALUES (?, ?, ?, ?, ?, ?)",
                batch,
            )
            conn.commit()
            batch.clear()
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO anniversaries VALUES (?, ?, ?, ?, ?, ?)",
            batch,
        )
        conn.commit()
    logger.info(f"anniversaries: {rows} 行迁移")
    return {"rows": rows}


# ─── relationship_roles.json → relationship_role ──────────────

def _migrate_relationship_roles(conn: sqlite3.Connection, data_dir: Path) -> dict:
    f = data_dir / "relationship_roles.json"
    if not f.exists():
        return {"rows": 0}
    data = json.loads(f.read_text(encoding="utf-8"))
    batch = []
    for uid, role in data.items():
        if isinstance(role, dict):
            batch.append((
                uid,
                role.get("role_id", ""),
                role.get("role_name", ""),
                1 if role.get("unlocked") else 0,
                1 if role.get("switched") else 0,
                role.get("custom_attitude", ""),
                role.get("custom_relationship", ""),
                json.dumps({k: v for k, v in role.items()
                           if k not in {"role_id", "role_name", "unlocked", "switched",
                                         "custom_attitude", "custom_relationship"}},
                           ensure_ascii=False),
                role.get("updated_at", 0),
            ))
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO relationship_role VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        conn.commit()
    logger.info(f"relationship_role: {len(batch)} 行迁移")
    return {"rows": len(batch)}


# ─── long_term_memory/*.json → long_term_memory ───────────────

def _migrate_long_term_memory(conn: sqlite3.Connection, data_dir: Path) -> dict:
    ltm_dir = data_dir / "long_term_memory"
    if not ltm_dir.exists():
        return {"rows": 0, "files": 0}
    rows = 0
    files = 0
    batch = []
    for f in ltm_dir.glob("*.json"):
        uid = f.stem
        files += 1
        try:
            events = json.loads(f.read_text(encoding="utf-8"))
            for e in events:
                emotions = e.get("emotions", {})
                if isinstance(emotions, dict):
                    emotions = json.dumps(emotions, ensure_ascii=False)
                batch.append((
                    uid,
                    e.get("ts", 0),
                    e.get("description", ""),
                    e.get("message", ""),
                    emotions,
                    e.get("favorability", 0),
                    e.get("fav_delta", 0),
                    e.get("stage", ""),
                    e.get("vividness", 100),
                    e.get("last_recalled_ts", 0),
                    1 if e.get("important") else 0,
                    0,  # compressed
                    e.get("ts", 0),  # created_at
                ))
                rows += 1
        except Exception as e:
            logger.warning(f"跳过 long_term_memory/{uid}: {e}")
        if len(batch) >= BATCH_SIZE:
            conn.executemany(
                "INSERT OR REPLACE INTO long_term_memory VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                batch,
            )
            conn.commit()
            batch.clear()
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO long_term_memory VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        conn.commit()
    logger.info(f"long_term_memory: {rows} 行迁移, {files} 文件")
    return {"rows": rows, "files": files}


# ─── stats_history.json → daily_snapshot_YYYYMM ────────────────

def _migrate_stats(conn: sqlite3.Connection, data_dir: Path) -> dict:
    f = data_dir / "stats_history.json"
    if not f.exists():
        return {"rows": 0}
    data = json.loads(f.read_text(encoding="utf-8"))
    rows = 0
    batch = []
    for uid, entries in data.items():
        for e in entries:
            d = e.get("date", "")
            if not d:
                continue
            try:
                dt = date.fromisoformat(d)
                table = f"daily_snapshot_{dt.year:04d}{dt.month:02d}"
                # 确保表存在
                conn.execute(
                    f"""CREATE TABLE IF NOT EXISTS {table} (
                        user_id TEXT NOT NULL, date TEXT NOT NULL,
                        fav REAL DEFAULT 0, int REAL DEFAULT 0,
                        stage INTEGER DEFAULT 0, stage_label TEXT DEFAULT '',
                        interactions INTEGER DEFAULT 0, positive INTEGER DEFAULT 0,
                        negative INTEGER DEFAULT 0, turns INTEGER DEFAULT 0,
                        PRIMARY KEY (user_id, date)
                    )"""
                )
                batch.append((
                    uid, d,
                    e.get("fav", 0), e.get("int", 0),
                    e.get("stage", 0), e.get("stage_label", ""),
                    e.get("interactions", 0), e.get("positive", 0),
                    e.get("negative", 0), e.get("turns", 0),
                    table,
                ))
                rows += 1
            except Exception as e:
                logger.warning(f"跳过 stats {uid}/{d}: {e}")
        if len(batch) >= BATCH_SIZE:
            _insert_snapshots(conn, batch)
            batch.clear()
    if batch:
        _insert_snapshots(conn, batch)
    logger.info(f"stats_history: {rows} 行迁移")
    return {"rows": rows}


def _insert_snapshots(conn: sqlite3.Connection, batch: list):
    """按表名分组插入快照"""
    by_table: dict[str, list] = {}
    for item in batch:
        table = item[-1]
        by_table.setdefault(table, []).append(item[:-1])
    for table, rows in by_table.items():
        conn.executemany(
            f"INSERT OR REPLACE INTO {table} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    conn.commit()


# ─── CLI 入口 ─────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) < 2:
        print("用法: python -m db_migration.migrate_json_to_sqlite <data_dir>")
        sys.exit(1)
    data_dir = Path(sys.argv[1])
    report = run_migration(data_dir)
    print(f"\n📊 迁移报告:")
    print(f"  总行数: {report['total_rows']}")
    print(f"  耗时: {report['elapsed_sec']}s")
    for table, info in report["tables"].items():
        print(f"  {table}: {info.get('rows', 0)} 行")
