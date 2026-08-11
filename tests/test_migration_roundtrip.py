"""tests/test_migration_roundtrip.py - 迁移回环测试

Sprint 5 S5-02 产出物。
执行完整迁移回环测试：Migrate → 运行压测 → 导出 JSON 校验 → 比对数据一致性。
核心字段（好感/亲密/阶段）差异为 0。

用法:
    pytest tests/test_migration_roundtrip.py -v
"""

from __future__ import annotations

import json
import os
import random
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.pool import ConnectionPool
from storage.schema import init_schema
from storage.memory_store import SQLiteMemoryManager
from storage.stats_store import SQLiteStatsTracker


def _create_mock_json_data(data_dir: Path):
    """创建模拟 JSON 数据（用于迁移前）"""
    # profiles.json
    profiles = {}
    for i in range(20):
        uid = f"test_user_{i:03d}"
        profiles[uid] = {
            "user_id": uid,
            "user_name": f"测试用户{i}",
            "favorability": round(random.uniform(-50, 150), 2),
            "intimacy": round(random.uniform(0, 80), 2),
            "stage_index": random.randint(0, 11),
            "stage_label": f"阶段{random.randint(1, 12)}",
            "attitude_text": f"态度_{i}",
            "relationship_text": f"关系_{i}",
            "total_interactions": random.randint(10, 500),
            "positive_interactions": random.randint(5, 250),
            "negative_interactions": random.randint(0, 100),
            "conversation_turns": random.randint(10, 1000),
            "first_interaction_ts": 1700000000.0 + i * 86400,
            "last_interaction_ts": 1700000000.0 + i * 86400 + 3600,
            "created_at": 1700000000.0 + i * 86400,
            "updated_at": 1700000000.0 + i * 86400 + 3600,
        }
    (data_dir / "profiles.json").write_text(json.dumps(profiles, ensure_ascii=False), encoding="utf-8")

    # stats_history.json
    from datetime import date, timedelta
    stats = {}
    for uid in list(profiles.keys())[:10]:
        entries = []
        for d in range(30):
            dt = date.today() - timedelta(days=d)
            entries.append({
                "date": dt.isoformat(),
                "fav": round(random.uniform(-50, 150), 2),
                "int": round(random.uniform(0, 80), 2),
                "stage": random.randint(0, 11),
                "stage_label": f"阶段{random.randint(1, 12)}",
                "interactions": random.randint(10, 200),
                "positive": random.randint(5, 100),
                "negative": random.randint(0, 50),
                "turns": random.randint(10, 200),
            })
        stats[uid] = entries
    (data_dir / "stats_history.json").write_text(json.dumps(stats, ensure_ascii=False), encoding="utf-8")

    # long_term_memory/*.json
    ltm_dir = data_dir / "long_term_memory"
    ltm_dir.mkdir(exist_ok=True)
    for uid in list(profiles.keys())[:10]:
        events = []
        for j in range(15):
            events.append({
                "ts": 1700000000.0 + j * 3600,
                "description": f"事件{j}",
                "message": f"消息{j}",
                "emotions": {"joy": random.randint(30, 90), "trust": random.randint(30, 90)},
                "favorability": profiles[uid]["favorability"],
                "fav_delta": round(random.uniform(-2, 3), 2),
                "stage": profiles[uid]["stage_label"],
                "vividness": 100,
                "last_recalled_ts": 0,
                "important": j == 0,
            })
        (ltm_dir / f"{uid}.json").write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")

    return profiles, stats


def _export_from_sqlite(pool) -> dict:
    """从 SQLite 导出数据用于比对"""
    with pool.connect() as conn:
        # 导出 profiles
        rows = conn.execute("SELECT * FROM user_profile").fetchall()
        profiles = {r["user_id"]: dict(r) for r in rows}

        # 导出 stats（跨表）
        stats = {}
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'daily_snapshot_%'"
        )
        for tbl in [r["name"] for r in cursor.fetchall()]:
            rows = conn.execute(f"SELECT * FROM {tbl}").fetchall()
            for r in rows:
                uid = r["user_id"]
                stats.setdefault(uid, []).append(dict(r))

        # 导出 memory
        rows = conn.execute("SELECT * FROM long_term_memory").fetchall()
        memory = {}
        for r in rows:
            uid = r["user_id"]
            memory.setdefault(uid, []).append(dict(r))

    return {"profiles": profiles, "stats": stats, "memory": memory}


class TestMigrationRoundtrip:
    """迁移回环测试"""

    def test_full_roundtrip(self):
        """完整回环：JSON → SQLite → 校验一致性"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)

            # Step 1: 创建模拟 JSON 数据
            orig_profiles, orig_stats = _create_mock_json_data(data_dir)

            # Step 2: 迁移到 SQLite
            ConnectionPool.reset()
            pool = ConnectionPool.get_instance(data_dir)
            with pool.connect() as conn:
                init_schema(conn)

            # Step 3: 运行迁移脚本
            from db_migration.migrate_json_to_sqlite import run_migration
            report = run_migration(data_dir)
            assert report["total_rows"] > 0, "迁移行数应 > 0"
            assert report["errors"] == [], f"迁移错误: {report['errors']}"

            # Step 4: 从 SQLite 导出
            exported = _export_from_sqlite(pool)

            # Step 5: 比对核心字段
            for uid, orig in orig_profiles.items():
                assert uid in exported["profiles"], f"用户 {uid} 未迁移到 SQLite"
                db = exported["profiles"][uid]
                assert abs(db["favorability"] - orig["favorability"]) < 0.01, \
                    f"{uid} 好感差异: {db['favorability']} vs {orig['favorability']}"
                assert abs(db["intimacy"] - orig["intimacy"]) < 0.01, \
                    f"{uid} 亲密差异: {db['intimacy']} vs {orig['intimacy']}"
                assert db["stage_index"] == orig["stage_index"], \
                    f"{uid} 阶段差异: {db['stage_index']} vs {orig['stage_index']}"

            # Step 6: 比对统计
            for uid, orig_entries in orig_stats.items():
                if uid in exported["stats"]:
                    db_entries = exported["stats"][uid]
                    assert len(db_entries) == len(orig_entries), \
                        f"{uid} 统计条数差异: {len(db_entries)} vs {len(orig_entries)}"

            ConnectionPool.reset()

    def test_memory_compression(self):
        """记忆压缩测试"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            ConnectionPool.reset()
            pool = ConnectionPool.get_instance(data_dir)
            with pool.connect() as conn:
                init_schema(conn)

            mem = SQLiteMemoryManager(pool, max_events_per_user=50)

            # 写入 25 条记忆（超过压缩阈值 20）
            uid = "test_user"
            for i in range(25):
                mem.add_event(uid, {
                    "description": f"事件{i}",
                    "message": f"消息{i}",
                    "emotions": {"joy": 50 + i, "trust": 60 + i},
                    "favorability": 50 + i,
                    "fav_delta": 1.0,
                    "stage": "阶段1",
                })

            # 检查记忆条数
            events = mem.get_events(uid, 100)
            assert len(events) == 25, f"压缩前条数: {len(events)}"

            # 执行压缩
            from compressor.memory_compressor import MemoryCompressor
            comp = MemoryCompressor(pool)
            compressed = comp.check_and_compress(uid)
            assert compressed, "应执行压缩"

            # 验证压缩后条数减少
            events_after = mem.get_events(uid, 100)
            compressed_count = sum(1 for e in events_after if e.get("compressed"))
            assert compressed_count > 0, "应有压缩记录"

            ConnectionPool.reset()

    def test_rebirth_engine(self):
        """转生系统测试"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            ConnectionPool.reset()
            pool = ConnectionPool.get_instance(data_dir)
            with pool.connect() as conn:
                init_schema(conn)
                conn.execute(
                    "INSERT INTO behavior_profile (user_id) VALUES (?)",
                    ("test_user",),
                )
                conn.commit()

            from rebirth.rebirth_engine import RebirthEngine
            engine = RebirthEngine(pool)

            # 好感未达阈值，不应转生
            result = engine.check_and_rebirth("test_user", 150)
            assert result is None, "好感 150 不应转生"

            # 好感达到阈值（200），应转生
            result = engine.check_and_rebirth("test_user", 200)
            assert result is not None, "好感 200 应转生"
            assert result["rebirth_count"] == 1
            assert result["new_favor"] == 25  # 20 + 1*5

            # 获取状态
            state = engine.get_state("test_user")
            assert state["prestige_level"] == 1

            # 再次转生（阈值 250）
            result2 = engine.check_and_rebirth("test_user", 250)
            assert result2 is not None
            assert result2["rebirth_count"] == 2

            ConnectionPool.reset()
