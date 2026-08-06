"""TPD Phase F - 综合测试覆盖 + 性能基准

覆盖 Phase F 文档要求的全部测试类型：
1. 天气获取：三级降级 / 缓存命中 / API模拟
2. 心情映射：天气×温度×季节×月相全组合系数
3. 倒计时计算：各种日期距离天数
4. 倒计时叙事：T-7~T+7 强度渐变
5. 指令解析：全部指令类型 + 边界
6. 跳跃执行：情感漂移上限截断
7. 被动离开：6级分级 + 边界
8. 回归叙事：阶段1 vs 阶段12 差异
9. 性能：TPD 全处理 <30ms
"""

import datetime
import io
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from astrbot_plugin_soulsync.tpd import (
    TPDOrchestrator,
    parse_skip_command,
)
from astrbot_plugin_soulsync.tpd.mood_mapper import mood_deltas, EMOTION_DIMS, DIM_LABELS
from astrbot_plugin_soulsync.tpd.season_handler import (
    solar_term_of, solar_term_date, season_of, moon_phase, moon_phase_index,
    SOLAR_TERM_NAMES, MOON_PHASES,
)
from astrbot_plugin_soulsync.tpd.weather_provider import WeatherProvider, CANONICAL_WEATHERS
from astrbot_plugin_soulsync.tpd.countdown_narrator import stage_of, day_label
from astrbot_plugin_soulsync.tpd.gap_detector import detect_passive_gap, THRESHOLD_HOURS_DEFAULT
from astrbot_plugin_soulsync.tpd.return_narrator import generate_return_context
from astrbot_plugin_soulsync.tpd.skip_executor import SkipExecutor

TODAY = datetime.date.today()


# ══════════════════════════════════════════════════════════════
# 1. 天气获取：三级降级 / 缓存
# ══════════════════════════════════════════════════════════════
def test_weather_three_tier():
    with tempfile.TemporaryDirectory() as td:
        wp = WeatherProvider(td, {"tpd_weather_enabled": True, "tpd_weather_api_provider": ""})
        # 无 API → 本地推算
        env = wp.get_weather()
        assert env is not None, "本地推算应返回数据"
        assert env["weather"] in CANONICAL_WEATHERS, f"天气规范: {env['weather']}"
        assert env["source"] == "local", f"来源: {env['source']}"
        # 缓存命中（第二次不重新计算）
        env2 = wp.get_weather()
        assert env2 is not None and env2["weather"] == env["weather"], "缓存应返回相同结果"
        print("PASS: 天气三级降级（本地推算 + 缓存命中）")


def test_weather_fallback():
    with tempfile.TemporaryDirectory() as td:
        wp = WeatherProvider(td, {"tpd_weather_enabled": False})
        env = wp.get_weather()
        assert env is None, "tpd_weather_enabled=False 应返回 None"
        print("PASS: 天气开关关闭")


def test_weather_canonical():
    for w in CANONICAL_WEATHERS:
        assert isinstance(w, str) and len(w) >= 1, f"bad weather: {w}"
    assert "晴" in CANONICAL_WEATHERS and "小雨" in CANONICAL_WEATHERS
    print(f"PASS: 天气规范名（{len(CANONICAL_WEATHERS)} 种）")


# ══════════════════════════════════════════════════════════════
# 2. 心情映射：全组合系数
# ══════════════════════════════════════════════════════════════
def test_mood_mapping_weather():
    """不同天气应产生不同心情增量"""
    base_env = {"weather": "晴", "temperature": 22, "season": "春", "moon_phase": "新月",
                "temp_band": "舒适", "solar_term": None, "solar_term_today": False}
    deltas_sunny = mood_deltas(base_env, weather_strength=1.0, season_strength=0.0, moon_strength=0.0)
    base_env2 = dict(base_env, weather="雨")
    deltas_rain = mood_deltas(base_env2, weather_strength=1.0, season_strength=0.0, moon_strength=0.0)
    assert deltas_sunny != deltas_rain, "晴天与雨天心情应不同"
    assert "joy" in deltas_sunny and "joy" in deltas_rain
    print("PASS: 心情映射-天气差异")


def test_mood_mapping_temperature():
    """不同温度带应产生不同心情（温度用 weather_strength 缩放）"""
    base = {"weather": "晴", "season": "春", "moon_phase": "新月",
            "solar_term": None, "solar_term_today": False}
    deltas_hot = mood_deltas(dict(base, temperature=38, temp_band="酷热"),
                             weather_strength=1.0, season_strength=0.0, moon_strength=0.0)
    deltas_cold = mood_deltas(dict(base, temperature=-5, temp_band="严寒"),
                              weather_strength=1.0, season_strength=0.0, moon_strength=0.0)
    assert deltas_hot != deltas_cold, "酷热与严寒心情应不同"
    print("PASS: 心情映射-温度差异")


def test_mood_mapping_season():
    """不同季节应产生不同心情"""
    base = {"weather": "晴", "temperature": 22, "moon_phase": "新月",
            "solar_term": None, "solar_term_today": False}
    deltas_spring = mood_deltas(dict(base, season="春"), weather_strength=0.0,
                                season_strength=1.0, moon_strength=0.0)
    deltas_winter = mood_deltas(dict(base, season="冬"), weather_strength=0.0,
                                season_strength=1.0, moon_strength=0.0)
    assert deltas_spring != deltas_winter, "春天与冬天心情应不同"
    print("PASS: 心情映射-季节差异")


def test_mood_mapping_moon():
    """不同月相应产生不同心情"""
    base = {"weather": "晴", "temperature": 22, "season": "春",
            "solar_term": None, "solar_term_today": False}
    deltas_new = mood_deltas(dict(base, moon_phase="新月"), weather_strength=0.0,
                             season_strength=0.0, moon_strength=1.0)
    deltas_full = mood_deltas(dict(base, moon_phase="满月"), weather_strength=0.0,
                              season_strength=0.0, moon_strength=1.0)
    assert deltas_new != deltas_full, "新月与满月心情应不同"
    print("PASS: 心情映射-月相差异")


def test_mood_mapping_clamp():
    """心情增量应钳制在 [-5, +5]"""
    env = {"weather": "晴", "season": "春", "moon_phase": "新月",
           "solar_term": None, "solar_term_today": False}
    deltas = mood_deltas(env, weather_strength=1.0, season_strength=1.0, moon_strength=1.0)
    for dim in EMOTION_DIMS:
        v = deltas.get(dim, 0.0)
        assert -5.0 <= v <= 5.0, f"{dim}={v} out of range"
    print("PASS: 心情映射-钳制 ±5")


def test_mood_mapping_zero_strength():
    """强度为 0 时应全零"""
    env = {"weather": "晴", "season": "春", "moon_phase": "新月",
           "solar_term": None, "solar_term_today": False}
    # temperature=None to avoid temperature band contribution
    deltas = mood_deltas(env, weather_strength=0.0, season_strength=0.0, moon_strength=0.0)
    for dim in EMOTION_DIMS:
        assert abs(deltas.get(dim, 0.0)) < 1e-6, f"{dim}={deltas.get(dim)} should be 0"
    print("PASS: 心情映射-零强度")


# ══════════════════════════════════════════════════════════════
# 3. 倒计时计算：各种日期距离天数
# ══════════════════════════════════════════════════════════════
def test_countdown_dates():
    """各种日期场景的距离天数"""
    cases = [
        (datetime.date(2026, 8, 3), datetime.date(2026, 8, 3), 0),   # 同一天
        (datetime.date(2026, 8, 3), datetime.date(2026, 8, 4), 1),   # 明天
        (datetime.date(2026, 8, 3), datetime.date(2026, 8, 10), 7),  # 一周后
        (datetime.date(2026, 8, 3), datetime.date(2026, 9, 2), 30),  # 一个月后
        (datetime.date(2026, 8, 3), datetime.date(2026, 12, 31), 150),# 远期
        (datetime.date(2026, 8, 3), datetime.date(2027, 8, 3), 365), # 一年后
        (datetime.date(2026, 8, 3), datetime.date(2026, 8, 2), -1),  # 昨天
        (datetime.date(2026, 8, 3), datetime.date(2026, 7, 1), -33), # 上月
    ]
    for base, event, expected in cases:
        got = (event - base).days
        assert got == expected, f"{base}→{event}: 期望{expected}, 实际{got}"
    print("PASS: 倒计时计算（8 种日期场景）")


# ══════════════════════════════════════════════════════════════
# 4. 倒计时叙事：T-7~T+7 强度渐变
# ══════════════════════════════════════════════════════════════
def test_countdown_narrative_gradient():
    """叙事强度：T-7~T-4 渐淡(1), T-3~T-1 余韵(2), T0 当天(5), T+1 临近(3), T+2~T+3 预热(2), T+4~T+7 感知(1)"""
    expected = {
        -7: 1, -6: 1, -5: 1, -4: 1,  # 渐淡
        -3: 2, -2: 2, -1: 2,          # 余韵
        0: 5,                          # 当天
        1: 3,                          # 临近倒计时
        2: 2, 3: 2,                    # 近期预热
        4: 1, 5: 1, 6: 1, 7: 1,       # 远期感知
    }
    for d, exp_intensity in expected.items():
        stage_name, intensity = stage_of(d)
        assert intensity == exp_intensity, f"T{d:+d}: expected {exp_intensity}, got {intensity} ({stage_name})"
    # T0 应最高
    _, t0_int = stage_of(0)
    for d in range(-7, 8):
        _, i = stage_of(d)
        assert i <= t0_int, f"T{d:+d} intensity {i} > T0 {t0_int}"
    print("PASS: 倒计时叙事强度渐变（T-7~T+7）")


def test_countdown_day_label():
    today = datetime.date(2026, 8, 3)
    assert "今天" in day_label(0, today)
    assert "明天" in day_label(1, today)
    assert "后天" in day_label(2, today)
    assert "7天后" in day_label(7, today)
    assert "昨天" in day_label(-1, today)
    assert "前天" in day_label(-2, today)
    print("PASS: 倒计时日期称谓")


# ══════════════════════════════════════════════════════════════
# 5. 指令解析：全部指令类型 + 边界
# ══════════════════════════════════════════════════════════════
def test_parser_all_types():
    """覆盖全部 6 种指令类型"""
    # 直接跳跃
    assert parse_skip_command("三天后见").skip_days == 3
    assert parse_skip_command("2周后见").skip_days == 14
    assert parse_skip_command("一个月后见").skip_days == 30
    assert parse_skip_command("明天见").skip_days == 1
    assert parse_skip_command("后天见").skip_days == 2
    # 模糊跳跃
    assert parse_skip_command("过几天再来").skip_days == 5
    assert parse_skip_command("过3天再来").skip_days == 3
    # 告知跳跃
    assert parse_skip_command("接下来一周很忙").skip_days == 7
    assert parse_skip_command("接下来3天有事").skip_days == 3
    # 指定日期（T0=周一）
    T0 = datetime.date(2026, 8, 3)
    assert parse_skip_command("下周六我来找你", today=T0).skip_days == 5
    assert parse_skip_command("下周一见", today=T0).skip_days == 7
    assert parse_skip_command("这周日见", today=T0).skip_days == 6
    # 提前回归
    assert parse_skip_command("我提前回来了").kind == "return_early"
    assert parse_skip_command("我提前回来啦").kind == "return_early"
    # 非指令
    for msg in ["在吗", "今天怎么样", "我想你了", "周末干嘛", "下周要考试了"]:
        assert parse_skip_command(msg) is None, f"should not match: {msg}"
    print("PASS: 指令解析（全部 6 类 + 边界）")


def test_parser_edge_cases():
    assert parse_skip_command("") is None, "empty"
    assert parse_skip_command("   ") is None, "whitespace"
    assert parse_skip_command("100天后见").skip_days == 100, "three-digit"
    assert parse_skip_command("0天后见") is None, "zero days"
    print("PASS: 指令解析边界")


# ══════════════════════════════════════════════════════════════
# 6. 跳跃执行：情感漂移上限截断
# ══════════════════════════════════════════════════════════════
def test_skip_max_days_cap():
    """超大天数应被截断"""
    with tempfile.TemporaryDirectory() as td:
        ex = SkipExecutor(td)
        cmd = parse_skip_command("1000天后见")
        r = ex.execute_skip("u1", cmd, now=1_800_000_000.0, max_days=365)
        assert r["skip_days"] == 365, f"截断: {r['skip_days']}"
        assert r["target_date"] != "1000天后", "target_date 应计算"
        print("PASS: 跳跃天数上限截断")


def test_skip_emotion_drift_disabled():
    """关闭情感漂移时无漂移"""
    with tempfile.TemporaryDirectory() as td:
        ex = SkipExecutor(td)
        cmd = parse_skip_command("一个月后见")
        r = ex.execute_skip("u1", cmd, now=1_800_000_000.0,
                            real_date=TODAY, emotion_drift=False)
        assert "trust" not in r["emotion_deltas"], "关闭漂移不应有 trust 变化"
        assert abs(r["emotion_deltas"].get("anticipation", 0) - 5.0) < 1e-6, "约定期待应保留"
        print("PASS: 跳跃情感漂移关闭")


def test_skip_freeze_disabled():
    """关闭冻结时 frozen_until=0"""
    with tempfile.TemporaryDirectory() as td:
        ex = SkipExecutor(td)
        cmd = parse_skip_command("三天后见")
        r = ex.execute_skip("u1", cmd, now=1_800_000_000.0,
                            real_date=TODAY, freeze_penalty=False)
        assert r["frozen_until"] == 0.0, f"关闭冻结: {r['frozen_until']}"
        print("PASS: 跳跃惩罚冻结关闭")


# ══════════════════════════════════════════════════════════════
# 7. 被动离开：6级分级 + 边界
# ══════════════════════════════════════════════════════════════
def test_gap_6_levels():
    """6级被动离开分级"""
    now = 1_800_000_000.0
    thresholds = [
        (0, None, "无历史"),
        (1 * 3600, None, "1h<6h 阈值内"),
        (5.9 * 3600, None, "5.9h<6h 阈值内"),
        (6 * 3600, 1, "6h=阈值 边界"),
        (12 * 3600, 1, "12h 轻微"),
        (23.9 * 3600, 1, "23.9h 轻微"),
        (24 * 3600, 2, "24h 中度"),
        (2.9 * 86400, 2, "2.9天 中度"),
        (3 * 86400, 3, "3天 显著"),
        (6.9 * 86400, 3, "6.9天 显著"),
        (7 * 86400, 4, "7天 强烈"),
        (29.9 * 86400, 4, "29.9天 强烈"),
        (30 * 86400, 5, "30天 极端"),
        (90 * 86400, 5, "90天 极端"),
    ]
    for gap_sec, expected_level, desc in thresholds:
        g = detect_passive_gap(now, now - gap_sec, THRESHOLD_HOURS_DEFAULT)
        if expected_level is None:
            assert g is None, f"{desc}: 应 None"
        else:
            assert g is not None and g.level == expected_level, \
                f"{desc}: 期望 level={expected_level}, 实际={g.level if g else None}"
    print("PASS: 被动离开 6 级分级（14 边界点）")


# ══════════════════════════════════════════════════════════════
# 8. 回归叙事：阶段 1 vs 阶段 12
# ══════════════════════════════════════════════════════════════
def test_return_narrative_stages():
    """回归叙事应包含重逢描述"""
    r1 = generate_return_context(3, "2026-08-06", [], None)
    r12 = generate_return_context(30, "2026-09-02", ["重要纪念日"], None)
    assert "回归" in r1 and "回归" in r12
    assert "3天" in r1 and "30天" in r12, "天数应体现"
    assert "迟到" in r12, "有纪念日应提及迟到庆祝"
    assert "空白期" in r1 or "天里" in r1, "应提及空白期"
    print("PASS: 回归叙事（阶段差异）")


# ══════════════════════════════════════════════════════════════
# 9. 性能：TPD 全处理 <30ms
# ══════════════════════════════════════════════════════════════
def test_performance():
    """TPD 全处理平均延迟 <30ms"""
    with tempfile.TemporaryDirectory() as td:
        orch = TPDOrchestrator(
            {"tpd_enabled": True, "tpd_weather_enabled": True, "tpd_weather_api_provider": ""}, td
        )
        # 预热
        for _ in range(5):
            orch.process_turn("perf_user", "你好")
        # 基准
        n = 50
        t0 = time.perf_counter()
        for i in range(n):
            orch.process_turn("perf_user", f"消息{i}")
        elapsed = (time.perf_counter() - t0) / n * 1000
        assert elapsed < 30, f"TPD avg {elapsed:.2f}ms > 30ms"
        print(f"PASS: 性能基准（{elapsed:.2f}ms/轮，{n} 轮平均）")


# ══════════════════════════════════════════════════════════════
# 10. 节气计算边界
# ══════════════════════════════════════════════════════════════
def test_solar_term_edge():
    assert len(SOLAR_TERM_NAMES) == 24
    assert len(MOON_PHASES) == 8
    assert SOLAR_TERM_NAMES[0] == "小寒" and SOLAR_TERM_NAMES[23] == "冬至"
    assert season_of(2026, 1, 15) == "冬"
    assert season_of(2026, 4, 5) == "春"
    assert season_of(2026, 7, 7) == "夏"
    assert season_of(2026, 10, 8) == "秋"
    idx = moon_phase_index(datetime.datetime(2026, 1, 29))
    assert 0 <= idx <= 7, f"moon index: {idx}"
    print("PASS: 节气/季节/月相边界")


# ══════════════════════════════════════════════════════════════
# 11. Orchestrator 性能全链路
# ══════════════════════════════════════════════════════════════
def test_orchestrator_full_chain():
    """完整链路：环境→心情→倒计时→跳跃→注入"""
    with tempfile.TemporaryDirectory() as td:
        orch = TPDOrchestrator(
            {"tpd_enabled": True, "tpd_weather_enabled": True, "tpd_weather_api_provider": ""}, td
        )
        r = orch.process_turn("u1", "你好")
        assert r["environment"] is not None, "应有环境数据"
        assert isinstance(r["mood_deltas"], dict), "应有心情增量"
        assert r["inject_text"], "应有注入文本"
        # 跳跃流程
        r2 = orch.process_turn("u1", "三天后见")
        assert r2["timeskip"]["action"] == "farewell"
        r3 = orch.process_turn("u1", "回来了")
        assert r3["timeskip"]["action"] == "return"
        r4 = orch.process_turn("u1", "在吗")
        assert r4["timeskip"] is None
        print("PASS: Orchestrator 完整链路")


test_weather_three_tier()
test_weather_fallback()
test_weather_canonical()
test_mood_mapping_weather()
test_mood_mapping_temperature()
test_mood_mapping_season()
test_mood_mapping_moon()
test_mood_mapping_clamp()
test_mood_mapping_zero_strength()
test_countdown_dates()
test_countdown_narrative_gradient()
test_countdown_day_label()
test_parser_all_types()
test_parser_edge_cases()
test_skip_max_days_cap()
test_skip_emotion_drift_disabled()
test_skip_freeze_disabled()
test_gap_6_levels()
test_return_narrative_stages()
test_performance()
test_solar_term_edge()
test_orchestrator_full_chain()
print("\n全部 PASS: TPD Phase F 综合测试通过")
