"""TPD Phase C - 时间跳跃叙事系统 单模块测试

覆盖：指令解析（直接/模糊/告知/指定日期/提前回归）、跳跃执行（时间推进/惩罚冻结/情感漂移）、
迟到庆祝扫描、回归消费、被动离开分级、调度器全流程（告别→回归）、
配置开关（tpd_skip_enabled / 上限截断）、冷落惩罚冻结、记忆写入。
"""

import datetime
import io
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from astrbot_plugin_soulsync.anniversary import AnniversaryManager
from astrbot_plugin_soulsync.tpd import (
    TPDOrchestrator,
    parse_skip_command,
)
from astrbot_plugin_soulsync.tpd.farewell_narrator import generate_farewell_context
from astrbot_plugin_soulsync.tpd.gap_detector import detect_passive_gap
from astrbot_plugin_soulsync.tpd.return_narrator import generate_return_context
from astrbot_plugin_soulsync.tpd.skip_executor import SkipExecutor

BASE = Path(__file__).resolve().parent.parent

T0 = datetime.date(2026, 8, 3)  # 周一


def make_mgr(td: str) -> AnniversaryManager:
    mgr = AnniversaryManager(Path(td))
    mgr.first_meet["u1"] = "2025-08-06"
    mgr.add_anniversary("u1", "重要纪念日", 8, 6, "anniversary")
    return mgr


# ── 1. 指令解析：直接跳跃 ────────────────────────────────
def test_parser_direct():
    cases = {
        "三天后见": 3, "明天见": 1, "后天见": 2, "一周后见": 7,
        "两周后见": 14, "一个月后见": 30, "3天后来找你": 3,
        "下个月见": 30, "下下周见": 14,
    }
    for msg, want in cases.items():
        cmd = parse_skip_command(msg)
        assert cmd is not None, f"应识别: {msg}"
        assert cmd.kind == "skip" and cmd.skip_days == want, f"{msg}: {cmd}"


# ── 2. 指令解析：模糊/告知/指定日期/提前回归 ──────────────
def test_parser_vague_inform_date_return():
    assert parse_skip_command("过几天再来").skip_days == 5, "模糊跳跃默认 5 天"
    assert parse_skip_command("过3天再来").skip_days == 3, "过N天"
    assert parse_skip_command("过些天再见").skip_days == 5, "过些天"
    assert parse_skip_command("接下来一周很忙").skip_days == 7, "告知跳跃-周"
    assert parse_skip_command("接下来3天有事").skip_days == 3, "告知跳跃-天"
    assert parse_skip_command("接下来一个月要出差").skip_days == 30, "告知跳跃-月"
    assert parse_skip_command("下周六我来找你", today=T0).skip_days == 5, "下周六 → 5 天（周一基准）"
    assert parse_skip_command("下周一见", today=T0).skip_days == 7, "下周一 → 7 天"
    assert parse_skip_command("这周日见", today=T0).skip_days == 6, "这周日 → 6 天"
    assert parse_skip_command("我提前回来了").kind == "return_early", "提前回归"
    assert parse_skip_command("我提前回来啦").kind == "return_early", "提前回归2"


# ── 3. 指令解析：非指令消息不误判 ─────────────────────────
def test_parser_noncommand():
    for msg in ["今天怎么样？", "在吗", "我想你了", "周末干嘛", "下周要考试了"]:
        assert parse_skip_command(msg) is None, f"不应识别: {msg}"


# ── 4. 跳跃执行：时间推进 + 惩罚冻结 + 情感漂移 ──────────
def test_execute_skip_effects():
    with tempfile.TemporaryDirectory() as td:
        ex = SkipExecutor(td)
        now = 1_800_000_000.0
        cmd = parse_skip_command("三天后见")
        r = ex.execute_skip("u1", cmd, now=now, real_date=T0)
        assert r["skip_days"] == 3 and r["target_date"] == "2026-08-06", r
        assert abs(r["emotion_deltas"]["anticipation"] - 5.0) < 1e-6, r["emotion_deltas"]
        assert r["frozen_until"] == now + 3 * 86400.0, r
        assert ex.get_state("u1")["offset_days"] == 3, "永久偏移累加"

        # 长跳漂移（30 天）：anticipation 5 + trust -0.4 + joy -0.2
        cmd30 = parse_skip_command("一个月后见")
        r30 = ex.execute_skip("u1", cmd30, now=now + 10, real_date=T0)
        assert r30["emotion_deltas"]["trust"] == -0.4, r30
        assert r30["emotion_deltas"]["joy"] == -0.2, r30
        assert abs(r30["emotion_deltas"]["anticipation"] - 5.0) < 1e-6, r30

        # 上限截断：400 天 → 365（2026-08-03 + 365 = 2027-08-03）
        ex2 = SkipExecutor(td)
        r400 = ex2.execute_skip("u2", parse_skip_command("400天后见"), now=now, real_date=T0)
        assert r400["skip_days"] == 365, r400
        assert r400["target_date"] == "2027-08-03", r400


# ── 5. 跳跃执行：迟到庆祝扫描 ────────────────────────────
def test_execute_late_celebration():
    with tempfile.TemporaryDirectory() as td:
        mgr = make_mgr(td)
        ex = SkipExecutor(td)
        # 从 8/3 跳 3 天 → 8/6，窗口内经过「重要纪念日」「认识1周年」（8/6）
        r = ex.execute_skip("u1", parse_skip_command("三天后见"),
                            now=1_800_000_000.0, real_date=T0, anniversaries=mgr)
        names = r["late_celebrations"]
        assert "重要纪念日" in names, names
        assert any("周年" in n for n in names), names


# ── 6. 跳跃执行：回归消费 ────────────────────────────────
def test_consume_return():
    with tempfile.TemporaryDirectory() as td:
        ex = SkipExecutor(td)
        ex.execute_skip("u1", parse_skip_command("三天后见"),
                        now=1_800_000_000.0, real_date=T0)
        assert ex.get_state("u1")["pending_return"] is True
        ret = ex.consume_return("u1")
        assert ret["last_days"] == 3, ret
        st = ex.get_state("u1")
        assert st["pending_return"] is False
        assert st["frozen_until"] == 0.0, "回归后解冻"
        # 提前回归：offset 归零
        ex.execute_skip("u1", parse_skip_command("我提前回来了"), now=1_800_000_000.0)
        assert ex.get_state("u1")["offset_days"] == 0


# ── 7. 被动离开检测：反应分级 ────────────────────────────
def test_gap_detector_levels():
    now = 1_800_000_000.0
    assert detect_passive_gap(now, now - 5 * 3600, 6) is None, "5h 不足阈值"
    g1 = detect_passive_gap(now, now - 10 * 3600, 6)
    assert g1 is not None and g1.level == 1, g1
    g2 = detect_passive_gap(now, now - 2 * 86400.0, 6)
    assert g2.level == 2, g2
    g3 = detect_passive_gap(now, now - 5 * 86400.0, 6)
    assert g3.level == 3, g3
    g4 = detect_passive_gap(now, now - 15 * 86400.0, 6)
    assert g4.level == 4, g4
    g5 = detect_passive_gap(now, now - 40 * 86400.0, 6)
    assert g5.level == 5, g5
    assert detect_passive_gap(now, 0.0, 6) is None, "无历史不检测"
    assert detect_passive_gap(now, now - 10 * 3600, 6, stage=2).inject_text, "stage 注入"


# ── 8. 调度器全流程：告别 → 回归（独占叙事 + 情感合并） ──
def test_orchestrator_farewell_return():
    with tempfile.TemporaryDirectory() as td:
        # 关闭天气子系统，隔离环境心情系数，便于精确断言
        cfg = {"tpd_enabled": True, "tpd_weather_enabled": False}
        orch = TPDOrchestrator(cfg, td)
        r1 = orch.process_turn("u1", "三天后见")
        ts = r1["timeskip"]
        assert ts is not None and ts["action"] == "farewell", r1
        assert ts["skip_days"] == 3, ts
        assert "告别" in ts["inject_text"], ts["inject_text"]
        assert abs(ts["emotion_deltas"]["anticipation"] - 5.0) < 1e-6, ts
        assert r1["inject_text"] == ts["inject_text"], "告别独占本轮叙事"
        assert abs(r1["mood_deltas"]["anticipation"] - 5.0) < 1e-6, "情感合并"

        # 告别后的下一次对话 = 回归（约定离开后的第一次对话）
        r2 = orch.process_turn("u1", "在吗")
        ts2 = r2["timeskip"]
        assert ts2 is not None and ts2["action"] == "return", r2
        assert ts2["skip_days"] == 3, ts2
        assert "回归" in ts2["inject_text"], ts2["inject_text"]
        assert r2["inject_text"] == ts2["inject_text"], "回归独占本轮叙事"

        # 回归后再对话：恢复正常
        r3 = orch.process_turn("u1", "想你了")
        assert r3["timeskip"] is None, r3


# ── 9. 调度器：被动离开检测（时间戳推进） ─────────────────
def test_orchestrator_passive_gap():
    with tempfile.TemporaryDirectory() as td:
        orch = TPDOrchestrator({"tpd_enabled": True}, td)
        t0 = 1_800_000_000.0
        with mock.patch("astrbot_plugin_soulsync.tpd.tpd_orchestrator.time") as mt:
            mt.time.return_value = t0
            r1 = orch.process_turn("u1", "你好")
            assert r1["timeskip"] is None, r1
        with mock.patch("astrbot_plugin_soulsync.tpd.tpd_orchestrator.time") as mt:
            mt.time.return_value = t0 + 10 * 3600
            r2 = orch.process_turn("u1", "回来了")
            ts = r2["timeskip"]
            assert ts is not None and ts["action"] == "gap" and ts["level"] == 1, r2
            assert ts["inject_text"] in r2["inject_text"], "gap 文本合并进本轮"


# ── 10. 调度器：配置开关 ─────────────────────────────────
def test_orchestrator_switches():
    with tempfile.TemporaryDirectory() as td:
        orch = TPDOrchestrator({"tpd_enabled": True, "tpd_skip_enabled": False}, td)
        assert orch.process_turn("u1", "三天后见")["timeskip"] is None, "tpd_skip_enabled=False"
        orch2 = TPDOrchestrator({"tpd_enabled": False}, td)
        assert orch2.process_turn("u1", "三天后见").get("timeskip") is None, "tpd_enabled=False"
        orch3 = TPDOrchestrator({"tpd_enabled": True, "tpd_skip_max_days": 30}, td)
        ts = orch3.process_turn("u1", "一百天后见")["timeskip"]
        assert ts["skip_days"] == 30, "上限截断生效"
        # 状态持久化落盘
        f = Path(td) / "skip_state.json"
        assert f.exists(), "skip_state.json 应落盘"
        data = json.loads(f.read_text(encoding="utf-8"))
        assert "u1" in data and data["u1"]["offset_days"] == 30, data


# ── 11. 冷落惩罚冻结（C.6 接入 penalty_reward） ───────────
def test_cold_penalty_freeze():
    from astrbot_plugin_soulsync.penalty_reward import PenaltyRewardEngine, BehaviorProfile

    engine = PenaltyRewardEngine()
    bp = BehaviorProfile(user_id="u1")
    bp.last_active_date = "2026-08-01"
    today, yesterday = "2026-08-05", "2026-08-04"
    # 冻结中：不累积
    bp.penalty_frozen_until = time.time() + 86400 * 3
    pf, pi, evt = engine.apply_daily_cold_penalty(bp, 60, today, yesterday)
    assert pf == 0.0 and evt is None and bp.cold_days == 0, "冻结期间不罚"
    # 解冻后：正常结算
    bp.penalty_frozen_until = 0.0
    pf, pi, evt = engine.apply_daily_cold_penalty(bp, 60, today, yesterday)
    assert pf < 0 and evt is not None and bp.cold_days == 1, "解冻后恢复结算"
    # 默认值向后兼容：新档案不带该字段
    bp2 = BehaviorProfile(user_id="u2")
    bp2.last_active_date = "2026-08-01"
    pf2, _, evt2 = engine.apply_daily_cold_penalty(bp2, 60, today, yesterday)
    assert pf2 < 0, "默认未冻结应正常结算"


# ── 12. 记忆写入（C.7：memory 源存在时写日志） ───────────
def test_memory_write():
    class FakeMemory:
        def __init__(self):
            self.events = []

        def add_event(self, uid, event):
            self.events.append((uid, event))

    with tempfile.TemporaryDirectory() as td:
        mem = FakeMemory()
        orch = TPDOrchestrator({"tpd_enabled": True}, td, {"memory": mem})
        orch.process_turn("u1", "三天后见")
        assert len(mem.events) == 1, mem.events
        assert "时间跳跃3天" in mem.events[0][1]["description"], mem.events


# ── 13. 叙事生成函数独立验证 ────────────────────────────
def test_narrators():
    fc = generate_farewell_context(parse_skip_command("三天后见"), "2026-08-06", ["重要纪念日"])
    assert "告别" in fc and "重要纪念日" in fc, fc
    rc = generate_return_context(3, "2026-08-06", ["重要纪念日"])
    assert "回归" in rc and "迟到" in rc, rc


test_parser_direct()
test_parser_vague_inform_date_return()
test_parser_noncommand()
test_execute_skip_effects()
test_execute_late_celebration()
test_consume_return()
test_gap_detector_levels()
test_orchestrator_farewell_return()
test_orchestrator_passive_gap()
test_orchestrator_switches()
test_cold_penalty_freeze()
test_memory_write()
test_narrators()
print("\n全部 PASS: TPD Phase C 单模块测试通过")
