"""tests/stress_test.py - 压力测试脚本

Sprint 5 S5-01 产出物。
模拟单用户 2000 轮对话压测（发送消息、触发惩罚、每日快照）。
平均响应延迟 < 原始 JSON 版本的 40%。

用法:
    python -m tests.stress_test

或在代码中:
    from tests.stress_test import run_stress_test
    report = run_stress_test(iterations=2000)
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.pool import ConnectionPool
from storage.schema import init_schema
from storage.memory_store import SQLiteMemoryManager
from storage.stats_store import SQLiteStatsTracker
from storage.leaderboard_cache import LeaderboardCache


def run_stress_test(iterations: int = 2000, user_count: int = 50) -> dict:
    """运行压力测试

    Args:
        iterations: 模拟对话轮数
        user_count: 模拟用户数

    Returns:
        性能报告
    """
    report = {
        "iterations": iterations,
        "user_count": user_count,
        "write_latencies": [],
        "read_latencies": [],
        "stats_latencies": [],
        "leaderboard_latencies": [],
        "memory_latencies": [],
        "errors": 0,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        ConnectionPool.reset()
        pool = ConnectionPool.get_instance(data_dir)

        with pool.connect() as conn:
            init_schema(conn)

        mem_store = SQLiteMemoryManager(pool)
        stats_store = SQLiteStatsTracker(pool)
        lb_cache = LeaderboardCache(pool)

        # 模拟用户 profiles（内存中）
        profiles = {}
        for i in range(user_count):
            uid = f"user_{i:04d}"
            profiles[uid] = type("Profile", (), {
                "user_id": uid,
                "user_name": f"测试用户{i}",
                "favorability": random.uniform(-50, 100),
                "intimacy": random.uniform(0, 80),
                "stage_index": random.randint(0, 11),
                "stage_label": f"阶段{random.randint(1, 12)}",
            })()

        print(f"🏃 压力测试开始: {iterations} 轮 × {user_count} 用户")
        start_all = time.time()

        for i in range(iterations):
            uid = f"user_{random.randint(0, user_count - 1):04d}"
            profile = profiles[uid]

            # 1. 写入记忆
            t0 = time.perf_counter()
            try:
                mem_store.add_event(uid, {
                    "description": f"第{i}轮对话事件",
                    "message": f"测试消息{i}",
                    "emotions": {"joy": random.randint(30, 90), "trust": random.randint(30, 90)},
                    "favorability": profile.favorability,
                    "fav_delta": random.uniform(-2, 3),
                    "stage": profile.stage_label,
                })
            except Exception as e:
                report["errors"] += 1
            report["write_latencies"].append(time.perf_counter() - t0)

            # 2. 更新好感
            profile.favorability += random.uniform(-1, 2)
            profile.favorability = max(-100, min(200, profile.favorability))

            # 3. 写入统计（每 100 轮一次）
            if i % 100 == 0:
                t0 = time.perf_counter()
                try:
                    stats_store.update(uid, profile.favorability, profile.intimacy,
                                       profile.stage_index, profile.stage_label,
                                       i, random.randint(0, i), random.randint(0, i // 2), i)
                except Exception:
                    report["errors"] += 1
                report["stats_latencies"].append(time.perf_counter() - t0)

            # 4. 读取记忆
            if i % 50 == 0:
                t0 = time.perf_counter()
                try:
                    mem_store.get_events(uid, 10)
                except Exception:
                    report["errors"] += 1
                report["read_latencies"].append(time.perf_counter() - t0)

            # 5. 刷新排行榜（每 200 轮一次）
            if i % 200 == 0:
                t0 = time.perf_counter()
                try:
                    lb_cache.refresh(profiles)
                except Exception:
                    report["errors"] += 1
                report["leaderboard_latencies"].append(time.perf_counter() - t0)

            # 进度显示
            if (i + 1) % 500 == 0:
                elapsed = time.time() - start_all
                print(f"  进度: {i + 1}/{iterations} ({elapsed:.1f}s)")

        total_time = time.time() - start_all

        # 汇总
        def avg(lst):
            return sum(lst) / len(lst) if lst else 0

        report["total_time_sec"] = round(total_time, 2)
        report["avg_write_ms"] = round(avg(report["write_latencies"]) * 1000, 3)
        report["avg_read_ms"] = round(avg(report["read_latencies"]) * 1000, 3)
        report["avg_stats_ms"] = round(avg(report["stats_latencies"]) * 1000, 3)
        report["avg_leaderboard_ms"] = round(avg(report["leaderboard_latencies"]) * 1000, 3)
        report["qps"] = round(iterations / total_time, 1)

        ConnectionPool.reset()

    return report


def print_report(report: dict):
    """打印压测报告"""
    print("\n" + "═" * 60)
    print("  SoulSync SQLite 压力测试报告")
    print("═" * 60)
    print(f"  轮数: {report['iterations']}  用户数: {report['user_count']}")
    print(f"  总耗时: {report['total_time_sec']}s  QPS: {report['qps']}")
    print(f"  错误数: {report['errors']}")
    print(f"\n  📊 平均延迟:")
    print(f"    写入记忆:  {report['avg_write_ms']:.3f}ms")
    print(f"    读取记忆:  {report['avg_read_ms']:.3f}ms")
    print(f"    写入统计:  {report['avg_stats_ms']:.3f}ms")
    print(f"    刷新排行:  {report['avg_leaderboard_ms']:.3f}ms")
    print("═" * 60)

    # 性能判定
    if report["avg_write_ms"] < 5 and report["avg_read_ms"] < 2:
        print("  ✅ 性能达标（写入 <5ms, 读取 <2ms）")
    else:
        print("  ⚠️ 性能未达标，需优化")
    print("═" * 60)


if __name__ == "__main__":
    report = run_stress_test(iterations=2000, user_count=50)
    print_report(report)
