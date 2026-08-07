"""TPD Phase B - 倒计时事件系统 单模块测试

覆盖：anniversary.py get_countdown_sources 扩展（认识周年/生日/自定义/节日含农历）、
六阶段映射与叙事模板、日期称谓、优先级排序（权重×1/距离×关注度）、
可提及代表日、24h 去重、每轮 1 个、状态持久化、Provider 接口（危机/角色生日/里程碑）、
注入文本（单/多事件）、调度器接入、_conf_schema.json 配置注册。
"""

import datetime
import json
import sys
import tempfile
import time
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from astrbot_plugin_soulsync.anniversary import AnniversaryManager, lunar_to_solar
from astrbot_plugin_soulsync.tpd import (
    TPDOrchestrator,
    build_countdown_info,
    day_label,
    stage_of,
)
from astrbot_plugin_soulsync.tpd.countdown_calculator import CountdownCalculator, MENTIONABLE_DAYS
from astrbot_plugin_soulsync.tpd.countdown_injector import build_countdown_info as _bi

BASE = Path(__file__).resolve().parent.parent

T0 = datetime.date(2026, 8, 3)  # 测试基准日（周一）


def make_mgr(td: str) -> AnniversaryManager:
    mgr = AnniversaryManager(Path(td))
    mgr.first_meet["u1"] = "2025-08-06"
    mgr.add_anniversary("u1", "重要纪念日", 8, 6, "anniversary")
    mgr.add_anniversary("u1", "生日", 8, 10, "birthday")
    mgr.add_anniversary("u1", "刚过的日子", 8, 1, "anniversary")
    return mgr


# ── 1. anniversary 扩展：倒计时事件源 ─────────────────────
def test_countdown_sources():
    with tempfile.TemporaryDirectory() as td:
        mgr = make_mgr(td)
        evs = mgr.get_countdown_sources("u1", T0, window_days=7)
        by_kind = {}
        for e in evs:
            by_kind.setdefault((e["kind"], e["name"]), []).append(e)
        # 认识一周年：T+3
        fm = [e for e in evs if e["kind"] == "first_meet"]
        assert fm and fm[0]["days_left"] == 3, f"认识一周年应 T+3: {fm}"
        assert fm[0]["name"] == "认识1周年", f"周年命名: {fm[0]['name']}"
        # 生日：T+7（窗口内）
        bd = [e for e in evs if e["name"] == "生日"]
        assert bd and bd[0]["days_left"] == 7, f"生日应 T+7: {bd}"
        assert bd[0]["kind"] == "birthday", "生日 kind 应为 birthday"
        # 自定义纪念日：下次 T+3 + 上次 -362（出窗排除）
        cu = [e for e in evs if e["name"] == "重要纪念日"]
        assert len(cu) == 1 and cu[0]["days_left"] == 3, f"纪念日应只剩下次 T+3: {cu}"
        # 刚过的日子：上次 -2（余韵窗内）
        passed = [e for e in evs if e["name"] == "刚过的日子"]
        assert passed and passed[0]["days_left"] == -2, f"刚过的日子应 T-2: {passed}"
        # 节日（公历 国庆 + 农历 中秋）
        today_fest = datetime.date(2026, 9, 28)
        fest = mgr.get_countdown_sources("u1", today_fest, window_days=7)
        names = {e["name"] for e in fest if e["kind"] == "festival"}
        assert "国庆节" in names, f"国庆应入窗: {names}"
        guo = [e for e in fest if e["name"] == "国庆节"][0]
        assert guo["days_left"] == 3, f"国庆应 T+3: {guo}"
        mid_autumn = lunar_to_solar(2026, 8, 15)
        assert mid_autumn, "中秋换算失败"
        md = datetime.date(*mid_autumn)
        assert "中秋节" in names, f"中秋应入窗（农历换算）: {names}"
        mid = [e for e in fest if e["name"] == "中秋节"][0]
        assert mid["days_left"] == (md - today_fest).days, f"中秋距离: {mid}"
    print("PASS: 倒计时事件源（认识周年/生日/自定义/节日公历+农历/窗口过滤）")


# ── 2. 六阶段映射 ───────────────────────────────────────
def test_stage_mapping():
    expect = {
        7: ("远期感知", 1), 6: ("远期感知", 1), 5: ("远期感知", 1), 4: ("远期感知", 1),
        3: ("近期预热", 2), 2: ("近期预热", 2),
        1: ("临近倒计时", 3),
        0: ("当天", 5),
        -1: ("余韵", 2), -2: ("余韵", 2), -3: ("余韵", 2),
        -4: ("渐淡", 1), -5: ("渐淡", 1), -6: ("渐淡", 1), -7: ("渐淡", 1),
    }
    for dl, (stage, intensity) in expect.items():
        got = stage_of(dl)
        assert got == (stage, intensity), f"T{dl}: 期望 {stage}/{intensity}, 实际 {got}"
    assert MENTIONABLE_DAYS == (7, 3, 1, 0, -1, -4), f"可提及代表日: {MENTIONABLE_DAYS}"
    print("PASS: 六阶段映射（T-7~T+7 全部 15 档强度正确）")


# ── 3. 日期称谓 ─────────────────────────────────────────
def test_day_label():
    assert day_label(0, T0) == "今天（周一）", day_label(0, T0)
    assert day_label(1, T0) == "明天（周二）", day_label(1, T0)
    assert day_label(2, T0) == "后天（周三）", day_label(2, T0)
    assert day_label(3, T0) == "3天后（周四）", day_label(3, T0)
    assert day_label(-1, T0) == "昨天（周日）", day_label(-1, T0)
    assert day_label(-2, T0) == "前天（周六）", day_label(-2, T0)
    assert day_label(-4, T0) == "4天前（周四）", day_label(-4, T0)
    print("PASS: 日期称谓（今天/明天/后天/N天前/星期推算）")


# ── 4. 优先级排序 + 24h 去重 + 每轮 1 个 ──────────────────
def test_priority_and_dedup():
    with tempfile.TemporaryDirectory() as td:
        mgr = make_mgr(td)
        calc = CountdownCalculator(td, {"anniversaries": mgr})
        now = 1754200000.0
        # 候选：认识1周年 T+3(w4) vs 重要纪念日 T+3(w2) vs 生日 T+7(w4)
        # 同距权重优先 → 认识1周年
        e1 = calc.select_for_mention("u1", T0, now=now)
        assert e1 is not None and e1.name == "认识1周年", f"应选权重更高的周年: {e1}"
        calc.mark_mentioned("u1", e1, now)
        # 24h 内：认识1周年冷却，转选重要纪念日（T+3 可提及，得分 0.667 > 生日 0.571）
        e2 = calc.select_for_mention("u1", T0, now=now + 3600)
        assert e2 is not None and e2.name == "重要纪念日", f"24h 内应换事件: {e2}"
        # 25h 后：认识1周年恢复（得分最高）
        e3 = calc.select_for_mention("u1", T0, now=now + 25 * 3600)
        assert e3 is not None and e3.key == e1.key, f"25h 后应恢复原事件: {e3}"
        # 得分：权重×1/距离 排序验证
        events = calc.get_active_events("u1", T0, now=now)
        by_name = {e.name: e for e in events}
        assert by_name["重要纪念日"].weight == 2.0
        assert by_name["生日"].weight == 4.0
        assert by_name["认识1周年"].weight == 4.0
        # 关注度：提及 3 次后 attention 提升 → 得分上升
        s0 = by_name["重要纪念日"].score
        for _ in range(3):
            calc.mark_mentioned("u1", by_name["重要纪念日"], now)
        events2 = calc.get_active_events("u1", T0, now=now)
        s1 = [e for e in events2 if e.name == "重要纪念日"][0].score
        assert s1 > s0, f"关注度应提升得分: {s0} -> {s1}"
        assert [e for e in events2 if e.name == "重要纪念日"][0].attention <= 1.5, "attention 上限 1.5"
    print("PASS: 优先级排序（权重×1/距离×关注度）+ 24h 去重 + 每轮 1 个")


# ── 5. 状态持久化 ──────────────────────────────────────
def test_persistence():
    with tempfile.TemporaryDirectory() as td:
        mgr = make_mgr(td)
        now = 1754200000.0
        calc1 = CountdownCalculator(td, {"anniversaries": mgr})
        e = calc1.select_for_mention("u1", T0, now=now)
        assert e is not None
        calc1.mark_mentioned("u1", e, now)
        state_file = Path(td) / "countdown_state.json"
        assert state_file.exists(), "状态应落盘"
        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert "u1" in data and e.key in data["u1"], "状态应含提及记录"
        # 新实例读到状态：24h 内仍被冷却
        calc2 = CountdownCalculator(td, {"anniversaries": mgr})
        e2 = calc2.select_for_mention("u1", T0, now=now + 3600)
        assert e2 is None or e2.key != e.key, "新实例应命中冷却"
        e3 = calc2.select_for_mention("u1", T0, now=now + 25 * 3600)
        assert e3 is not None and e3.key == e.key, "冷却解除后恢复"
    print("PASS: 提及状态持久化（落盘/新实例加载/冷却跨实例生效）")


# ── 6. Provider 接口：危机/角色生日/里程碑 ───────────────
def test_providers():
    with tempfile.TemporaryDirectory() as td:
        mgr = make_mgr(td)
        crisis_ts = datetime.datetime(2025, 9, 1, 12, 0).timestamp()
        sources = {
            "anniversaries": mgr,
            "crisis": lambda uid: [{"title": "信任考验", "resolved_at_ts": crisis_ts}],
            "role_birthday": lambda: {"name": "AI酱", "month": 9, "day": 15},
            "milestone": lambda uid: [{"name": "下一阶段", "days_left": 1}],
        }
        calc = CountdownCalculator(td, sources)
        today = datetime.date(2026, 9, 1)
        events = calc.get_active_events("u1", today)
        kinds = {(e.kind, e.name): e for e in events}
        # 危机纪念：今天正好周年 T0，权重 3
        c = kinds[("crisis", "信任考验")]
        assert c.days_left == 0 and c.weight == 3.0, f"危机纪念: {c}"
        # 角色生日：9-15 → T+14 出 30 天窗？不，9-01 +14 = 9-15 ✓
        rb = kinds[("birthday", "AI酱")]
        assert rb.days_left == 14 and rb.weight == 4.0, f"角色生日: {rb}"
        # 里程碑：T+1 权重 5，可提及代表日
        ms = kinds[("milestone", "下一阶段")]
        assert ms.days_left == 1 and ms.weight == 5.0, f"里程碑: {ms}"
        # 选择：里程碑 T+1 得分 5 > 危机 T0 3 > 其余
        sel = calc.select_for_mention("u1", today, now=1754200000.0)
        assert sel is not None and sel.kind == "milestone", f"应选里程碑: {sel}"
    print("PASS: Provider 接口（危机纪念/角色生日/里程碑 权重与选择）")


# ── 7. 注入文本：单/多事件 ─────────────────────────────
def test_injector():
    from astrbot_plugin_soulsync.tpd.countdown_calculator import CountdownEvent

    top = CountdownEvent(
        key="first_meet:认识一周年:2026-08-06", name="认识一周年", kind="first_meet",
        occurrence=datetime.date(2026, 8, 6), days_left=3, weight=4.0, score=1.33,
    )
    other = CountdownEvent(
        key="festival:国庆节:2026-10-01", name="国庆节", kind="festival",
        occurrence=datetime.date(2026, 10, 1), days_left=29, weight=2.0, score=0.07,
    )
    single = _bi(top, today=T0)
    assert "[倒计时感知]" in single, single
    assert "还有 3 天" in single, single
    assert "认识一周年" in single, single
    assert "明天" not in single, "T+3 不应说明天"
    multi = _bi(top, [other], today=T0)
    assert "[倒计时感知 - 多事件]" in multi, multi
    assert "当前活跃倒计时" in multi and "优先提及" in multi, multi
    assert "国庆节" in multi and "📅" in multi, "应含其他事件与图标"
    # 里程碑/临近阶段模板
    ms = CountdownEvent(
        key="milestone:下一阶段:2026-08-04", name="下一阶段", kind="milestone",
        occurrence=datetime.date(2026, 8, 4), days_left=1, weight=5.0,
    )
    near = _bi(ms, today=T0)
    assert "还有 1 天" in near and "明天" in near, f"T-1 应明确倒计时: {near}"
    print("PASS: 注入文本（单事件/多事件列表/优先提及/阶段模板）")


# ── 8. 调度器接入 ──────────────────────────────────────
def test_orchestrator_countdown():
    with tempfile.TemporaryDirectory() as td:
        mgr = make_mgr(td)
        cfg = {
            "tpd_enabled": True, "tpd_countdown_enabled": True,
            "tpd_countdown_mention_start_days": 7, "tpd_countdown_mention_freq_days": 1,
            "tpd_countdown_max_per_turn": 1, "tpd_countdown_auto_greet": True,
            "tpd_weather_enabled": True, "tpd_weather_api_provider": "",
        }
        orch = TPDOrchestrator(cfg, td, {"anniversaries": mgr})
        r = orch.process_turn("u1", "在吗")
        assert r["countdown"] is not None, "开启时应返回倒计时"
        cd = r["countdown"]
        assert cd["inject_text"].startswith("[倒计时感知]"), cd["inject_text"]
        assert cd["event"]["days_left"] in MENTIONABLE_DAYS, cd["event"]
        assert cd["stage"] in ("远期感知", "近期预热", "临近倒计时", "当天", "余韵", "渐淡")
        panel = orch.countdown_panel_data("u1")
        assert panel["enabled"] is True and len(panel["events"]) >= 1, panel
        assert panel["events"][0]["score"] >= panel["events"][-1]["score"], "面板应按得分降序"
        # 关闭
        orch_off = TPDOrchestrator(dict(cfg, tpd_countdown_enabled=False), td, {"anniversaries": mgr})
        assert orch_off.process_turn("u1")["countdown"] is None, "关闭时应为 None"
        # 无数据源
        orch_none = TPDOrchestrator(cfg, td)
        assert orch_none.process_turn("u1")["countdown"] is None, "无纪念日源应静默 None"
    print("PASS: 调度器接入（开启/关闭/无源静默/面板数据）")


# ── 9. 配置 schema 注册 ────────────────────────────────
def test_schema():
    schema = json.loads((BASE / "_conf_schema.json").read_text(encoding="utf-8"))
    keys = [
        "tpd_countdown_enabled", "tpd_countdown_mention_start_days",
        "tpd_countdown_mention_freq_days", "tpd_countdown_max_per_turn",
        "tpd_countdown_auto_greet",
    ]
    miss = [k for k in keys if k not in schema]
    assert not miss, f"schema 缺失: {miss}"
    assert schema["tpd_countdown_enabled"]["default"] is True
    assert schema["tpd_countdown_mention_start_days"]["default"] == 7
    assert schema["tpd_countdown_mention_freq_days"]["default"] == 1
    assert schema["tpd_countdown_max_per_turn"]["default"] == 1
    assert schema["tpd_countdown_auto_greet"]["default"] is True
    print(f"PASS: 配置注册（5 个 countdown 键，schema 共 {len(schema)} 键）")


test_countdown_sources()
test_stage_mapping()
test_day_label()
test_priority_and_dedup()
test_persistence()
test_providers()
test_injector()
test_orchestrator_countdown()
test_schema()
print("\n全部 PASS: TPD Phase B 单模块测试通过")
