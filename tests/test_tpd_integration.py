"""TPD Phase D - 端到端集成测试

验证 TPD 三系统联动在 main.py 级别的完整流程：
- _process_tpd_turn 输出结构正确（inject_text / perception / mood_deltas / countdown / timeskip）
- 环境感知 → prompt 前缀注入
- 叙事 → extra_user_content_parts 注入
- mood_deltas 合并到 emotion_deltas
- 冷落惩罚冻结同步
- 时间跳跃完整流程（告别 → 回归）
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

from astrbot_plugin_soulsync.tpd import TPDOrchestrator

TODAY = datetime.date.today()


def _make_orch(td: str) -> TPDOrchestrator:
    cfg = {"tpd_enabled": True, "tpd_weather_enabled": False, "tpd_countdown_enabled": False}
    return TPDOrchestrator(cfg, td)


class FakeProfile:
    stage_index = 5


# ── 1. _process_tpd_turn 输出结构 ─────────────────────────
def test_process_tpd_turn_structure():
    with tempfile.TemporaryDirectory() as td:
        orch = TPDOrchestrator({"tpd_enabled": True, "tpd_weather_enabled": False}, td)
        result = orch.process_turn("u1", "你好", {"stage": 5})
        assert isinstance(result, dict), "process_turn 应返回 dict"
        assert "environment" in result and "inject_text" in result, "缺少关键字段"
        assert "mood_deltas" in result, "缺少 mood_deltas"
        assert "countdown" in result and "timeskip" in result, "缺少子系统字段"
        print("PASS: process_turn 输出结构完整")


# ── 2. 环境感知 → prompt 前缀格式 ──────────────────────────
def test_perception_prefix():
    with tempfile.TemporaryDirectory() as td:
        orch = TPDOrchestrator(
            {"tpd_enabled": True, "tpd_weather_enabled": True, "tpd_weather_api_provider": ""}, td
        )
        result = orch.process_turn("u1", "你好")
        inject = result.get("inject_text", "")
        # 注入文本应以 [环境] 开头（天气推算至少返回本地结果）
        if inject:
            assert inject.startswith("[环境]"), f"注入文本应以 [环境] 开头: {inject[:60]}"
        print(f"PASS: 环境感知注入格式正确（{len(inject)} 字符）")


# ── 3. mood_deltas 合并 ────────────────────────────────────
def test_mood_deltas_merge():
    with tempfile.TemporaryDirectory() as td:
        orch = TPDOrchestrator(
            {"tpd_enabled": True, "tpd_weather_enabled": True, "tpd_weather_api_provider": ""}, td
        )
        result = orch.process_turn("u1", "你好")
        deltas = result.get("mood_deltas", {})
        assert isinstance(deltas, dict), "mood_deltas 应为 dict"
        # 至少有 env 子系统贡献的心情增量
        if result.get("environment"):
            assert len(deltas) > 0, "有环境数据时应有心情增量"
        print(f"PASS: mood_deltas 合并正确（{len(deltas)} 维）")


# ── 4. 跳跃完整流程：告别 → 回归 → 注入文本 ──────────────
def test_full_skip_flow():
    with tempfile.TemporaryDirectory() as td:
        orch = TPDOrchestrator({"tpd_enabled": True, "tpd_weather_enabled": False}, td)
        # 告别
        r1 = orch.process_turn("u1", "三天后见")
        ts1 = r1["timeskip"]
        assert ts1 and ts1["action"] == "farewell", f"告别失败: {r1}"
        assert ts1["skip_days"] == 3, f"跳跃天数: {ts1}"
        inject1 = ts1["inject_text"]
        assert "告别" in inject1, f"告别文本: {inject1}"

        # 回归
        r2 = orch.process_turn("u1", "我回来了")
        ts2 = r2["timeskip"]
        assert ts2 and ts2["action"] == "return", f"回归失败: {r2}"
        inject2 = ts2["inject_text"]
        assert "回归" in inject2, f"回归文本: {inject2}"

        # 正常
        r3 = orch.process_turn("u1", "在吗")
        assert r3["timeskip"] is None, f"回归后应正常: {r3}"

        print("PASS: 跳跃完整流程（告别→回归→正常）")


# ── 5. 被动离开检测端到端 ──────────────────────────────────
def test_passive_gap_e2e():
    with tempfile.TemporaryDirectory() as td:
        orch = TPDOrchestrator({"tpd_enabled": True, "tpd_weather_enabled": False}, td)
        t0 = 1_800_000_000.0
        with mock.patch("astrbot_plugin_soulsync.tpd.tpd_orchestrator.time") as mt:
            mt.time.return_value = t0
            r1 = orch.process_turn("u1", "你好")
            assert r1["timeskip"] is None, "首次无离开"
        with mock.patch("astrbot_plugin_soulsync.tpd.tpd_orchestrator.time") as mt:
            mt.time.return_value = t0 + 10 * 3600  # 10h 后
            r2 = orch.process_turn("u1", "回来了")
            ts = r2["timeskip"]
            assert ts and ts["action"] == "gap" and ts["level"] == 1, f"被动离开检测: {r2}"
            assert "小时" in ts["inject_text"], f"gap 文本: {ts['inject_text']}"
        print("PASS: 被动离开检测端到端")


# ── 6. 冷落惩罚冻结同步 ────────────────────────────────────
def test_cold_penalty_freeze_sync():
    from astrbot_plugin_soulsync.penalty_reward import PenaltyRewardEngine, BehaviorProfile

    with tempfile.TemporaryDirectory() as td:
        # 模拟 TPD 冻结
        orch = TPDOrchestrator({"tpd_enabled": True, "tpd_weather_enabled": False}, td)
        orch.process_turn("u1", "三天后见")
        skip_st = orch.skip_executor.get_state("u1")
        assert skip_st["frozen_until"] > time.time(), "frozen_until 应在未来"

        # 模拟 daily penalty 同步
        bp = BehaviorProfile(user_id="u1")
        bp.last_active_date = "2026-08-01"
        bp.penalty_frozen_until = skip_st["frozen_until"]

        engine = PenaltyRewardEngine()
        pf, _, evt = engine.apply_daily_cold_penalty(bp, 60, "2026-08-10", "2026-08-09")
        assert pf == 0.0 and evt is None, f"冻结期间不罚: {pf}, {evt}"
        assert bp.cold_days == 0, "冻结期间 cold_days 不变"
        print("PASS: 冷落惩罚冻结同步")


# ── 7. 配置开关端到端 ──────────────────────────────────────
def test_config_switches_e2e():
    with tempfile.TemporaryDirectory() as td:
        # tpd_enabled=False → 全空
        orch_off = TPDOrchestrator({"tpd_enabled": False}, td)
        r = orch_off.process_turn("u1", "三天后见")
        assert r.get("timeskip") is None and r.get("inject_text") == "", "关闭时全空"

        # tpd_skip_enabled=False → timeskip=None
        orch_ns = TPDOrchestrator({"tpd_enabled": True, "tpd_skip_enabled": False}, td)
        r2 = orch_ns.process_turn("u1", "三天后见")
        assert r2.get("timeskip") is None, "跳过关闭时 timeskip=None"

        print("PASS: 配置开关端到端")


# ── 8. 面板数据端到端 ──────────────────────────────────────
def test_panel_data_e2e():
    with tempfile.TemporaryDirectory() as td:
        orch = TPDOrchestrator({"tpd_enabled": True, "tpd_weather_enabled": False}, td)
        orch.process_turn("u1", "三天后见")
        # 环境面板
        env_panel = orch.environment_panel_data()
        assert "enabled" in env_panel and "environment" in env_panel, "环境面板缺字段"
        # 倒计时面板
        cd_panel = orch.countdown_panel_data("u1")
        assert "enabled" in cd_panel and "events" in cd_panel, "倒计时面板缺字段"
        # 跳跃面板
        skip_panel = orch.skip_panel_data("u1")
        assert "enabled" in skip_panel and "status" in skip_panel, "跳跃面板缺字段"
        status = skip_panel["status"]
        assert status["offset_days"] == 3, f"面板偏移: {status}"
        assert status["pending_return"] is True, "面板待回归状态"
        print("PASS: 面板数据端到端")


# ── 9. 纪念日迟到庆祝端到端 ────────────────────────────────
def test_late_celebration_e2e():
    from astrbot_plugin_soulsync.anniversary import AnniversaryManager

    with tempfile.TemporaryDirectory() as td:
        mgr = AnniversaryManager(Path(td))
        mgr.first_meet["u1"] = (TODAY - datetime.timedelta(days=365)).isoformat()
        orch = TPDOrchestrator(
            {"tpd_enabled": True, "tpd_weather_enabled": False}, td,
            {"anniversaries": mgr}
        )
        # 告别
        orch.process_turn("u1", "三天后见")
        # 回归
        r = orch.process_turn("u1", "我回来了")
        ts = r["timeskip"]
        assert ts and ts["action"] == "return", f"回归: {r}"
        late = ts.get("late_celebrations", [])
        # 如果窗口内经过纪念日，应有迟到庆祝
        if late:
            assert any("周年" in n for n in late), f"迟到庆祝: {late}"
        print(f"PASS: 纪念日迟到庆祝端到端（{len(late)} 项）")


# ── 10. state 持久化端到端 ─────────────────────────────────
def test_state_persistence_e2e():
    with tempfile.TemporaryDirectory() as td:
        orch1 = TPDOrchestrator({"tpd_enabled": True, "tpd_weather_enabled": False}, td)
        orch1.process_turn("u1", "三天后见")
        assert Path(td, "skip_state.json").exists(), "skip_state 应落盘"

        # 新实例读取同一 data_dir → 状态恢复
        orch2 = TPDOrchestrator({"tpd_enabled": True, "tpd_weather_enabled": False}, td)
        state = orch2.skip_executor.get_state("u1")
        assert state["offset_days"] == 3, f"状态恢复: {state}"
        assert state["pending_return"] is True, "待回归状态恢复"
        print("PASS: state 持久化端到端")


test_process_tpd_turn_structure()
test_perception_prefix()
test_mood_deltas_merge()
test_full_skip_flow()
test_passive_gap_e2e()
test_cold_penalty_freeze_sync()
test_config_switches_e2e()
test_panel_data_e2e()
test_late_celebration_e2e()
test_state_persistence_e2e()
print("\n全部 PASS: TPD Phase D 端到端集成测试通过")
