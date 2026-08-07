"""TPD Phase A - 基础设施 + 季节天气联动 单模块测试

覆盖：节气计算（1900-2100 公式）、季节判定、月相 8 阶段、
天气三级降级（本地推算路径 + 缓存）、环境→心情映射、环境叙事注入、
TPD 调度器骨架、_conf_schema.json 配置注册。
"""

import datetime
import json
import sys
import tempfile
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from astrbot_plugin_soulsync.tpd import (
    TPDOrchestrator,
    WeatherProvider,
    build_environment_info,
    build_mood_tendency_text,
    mood_deltas,
    moon_phase,
    moon_phase_index,
    season_of,
    solar_term_date,
    solar_term_of,
    temperature_band,
)
from astrbot_plugin_soulsync.tpd.season_handler import MOON_PHASES, SOLAR_TERM_NAMES

BASE = Path(__file__).resolve().parent.parent

# ── 1. 节气计算：已知日期（北京时） ─────────────────────────
def test_solar_terms():
    known = {
        (2024, "立春"): (2, 4), (2024, "春分"): (3, 20), (2024, "清明"): (4, 4),
        (2024, "夏至"): (6, 21), (2024, "秋分"): (9, 22), (2024, "冬至"): (12, 21),
        (2025, "立春"): (2, 3), (2025, "春分"): (3, 20), (2025, "夏至"): (6, 21),
        (2025, "秋分"): (9, 23), (2025, "冬至"): (12, 21),
        (2026, "小寒"): (1, 5), (2026, "大寒"): (1, 20), (2026, "立春"): (2, 4),
        (2026, "春分"): (3, 20), (2026, "清明"): (4, 5), (2026, "夏至"): (6, 21),
        (2026, "秋分"): (9, 23), (2026, "冬至"): (12, 22),
    }
    for (year, name), (exp_m, exp_d) in known.items():
        idx = SOLAR_TERM_NAMES.index(name)
        got = solar_term_date(year, idx)
        assert got == (exp_m, exp_d), f"{year} {name}: 期望 {exp_m}-{exp_d:02d}, 实际 {got}"
    assert len(SOLAR_TERM_NAMES) == 24, "节气数量应为 24"
    print(f"PASS: 节气计算（{len(known)} 个已知日期全部命中，24 节气齐备）")


# ── 2. 节气归属 + 季节判定 ────────────────────────────────
def test_season():
    assert solar_term_of(2026, 2, 5) == "立春", "清明后应为立春"
    assert solar_term_of(2026, 4, 5) == "清明", "清明节当日归属清明"
    assert solar_term_of(2026, 4, 19) == "清明", "清明与谷雨之间归属清明"
    assert solar_term_of(2026, 4, 20) == "谷雨", "谷雨当日归属谷雨"
    assert solar_term_of(2026, 12, 31) == "冬至", "年末应为冬至"
    assert solar_term_of(2026, 1, 1) == "冬至", "年初应为上一年冬至"
    assert season_of(2026, 2, 5) == "春", "立春后为春"
    assert season_of(2026, 6, 22) == "夏", "夏至后为夏"
    assert season_of(2026, 8, 8) == "秋", "立秋后为秋"
    assert season_of(2026, 11, 8) == "冬", "立冬后为冬"
    assert season_of(2026, 1, 31) == "冬", "立春前为冬"
    print("PASS: 节气归属与季节判定（含跨年边界）")


# ── 3. 月相 8 阶段 ───────────────────────────────────────
def test_moon_phase():
    assert moon_phase_index(datetime.datetime(2024, 2, 24, 12, 0)) == 4, "2024元宵应为满月"
    assert moon_phase_index(datetime.datetime(2024, 2, 10, 12, 0)) == 0, "2024春节初一应为新月"
    assert moon_phase_index(datetime.datetime(2023, 9, 29, 12, 0)) == 4, "2023中秋应为满月"
    assert moon_phase_index(datetime.datetime(2026, 2, 17, 12, 0)) == 0, "2026正月初一应为新月"
    name, emoji = moon_phase(datetime.datetime(2024, 2, 24, 12, 0))
    assert (name, emoji) == ("满月", "🌕"), f"月相名称/图标不符: {name}{emoji}"
    assert len(MOON_PHASES) == 8, "月相应为 8 阶段"
    # 8 阶段全部可达
    phases = {moon_phase_index(datetime.datetime(2024, 1, 1) + datetime.timedelta(days=i)) for i in range(240)}
    assert phases == set(range(8)), f"240 天内应覆盖全部 8 阶段: {sorted(phases)}"
    print("PASS: 月相 8 阶段（满月/新月已知日期命中，240 天全阶段覆盖）")


# ── 4. 天气获取：本地推算（无 API 配置） ────────────────────
def test_weather_local():
    with tempfile.TemporaryDirectory() as td:
        cfg = {"tpd_weather_enabled": True, "tpd_weather_api_provider": "", "tpd_weather_cache_minutes": 60}
        p = WeatherProvider(td, cfg)
        dt1 = datetime.datetime(2026, 8, 6, 14, 0)
        w1 = p.get_weather(dt1)
        assert w1 is not None, "本地推算不应返回 None"
        w2 = p.get_weather(dt1)
        assert w1["weather"] == w2["weather"], "同日天气应确定性一致"
        assert w1["source"] == "local", f"无 API 应走本地推算: {w1['source']}"
        for field in ("date", "weather", "temperature", "season", "season_desc",
                      "solar_term", "moon_phase", "moon_emoji", "source", "fetched_at"):
            assert field in w1, f"环境字段缺失: {field}"
        assert w1["weather"] in (
            "晴", "多云", "阴", "小雨", "中雨", "大雨", "雷阵雨", "小雪", "大雪", "大风"
        ), f"天气应为规范化 10 种之一: {w1['weather']}"
        assert isinstance(w1["temperature"], int), "本地推算应有温度"
    print("PASS: 天气本地推算（确定性/字段齐全/规范化天气）")


# ── 5. 天气缓存：命中与落盘 ───────────────────────────────
def test_weather_cache():
    with tempfile.TemporaryDirectory() as td:
        cfg = {"tpd_weather_enabled": True, "tpd_weather_api_provider": "", "tpd_weather_cache_minutes": 60}
        dt1 = datetime.datetime(2026, 8, 6, 14, 0)
        p1 = WeatherProvider(td, cfg)
        w1 = p1.get_weather(dt1)
        cache_file = Path(td) / "weather_cache.json"
        assert cache_file.exists(), "缓存文件应落盘"
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        assert "2026-08-06" in data, "缓存应含当日记录"
        p2 = WeatherProvider(td, cfg)
        w2 = p2.get_weather(dt1)
        assert w2["weather"] == w1["weather"], "新实例应命中缓存"
        assert w2["fetched_at"] == w1["fetched_at"], "缓存命中应返回原记录"
        w3 = p2.get_weather(dt1, force_refresh=True)
        assert w3["weather"] == w1["weather"], "强制刷新结果应一致（确定性）"
    print("PASS: 天气缓存（落盘/新实例命中/强制刷新）")


# ── 6. 天气开关 ─────────────────────────────────────────
def test_weather_disabled():
    with tempfile.TemporaryDirectory() as td:
        p = WeatherProvider(td, {"tpd_weather_enabled": False})
        assert p.get_weather(datetime.datetime(2026, 8, 6)) is None, "关闭时应返回 None"
    print("PASS: 天气开关（关闭返回 None）")


# ── 7. 环境→心情映射 ─────────────────────────────────────
def test_mood_mapper():
    # 晴 → 喜悦/信任上升
    d = mood_deltas({"weather": "晴", "temperature": 22, "season": "春", "moon_phase": "上弦月"})
    assert d["joy"] > 0 and d["trust"] > 0, f"晴天应有积极倾向: {d}"
    # 雷阵雨 → 恐惧
    d2 = mood_deltas({"weather": "雷阵雨", "temperature": 28, "season": "夏", "moon_phase": "满月"})
    assert d2["fear"] > 0, f"雷阵雨应有恐惧倾向: {d2}"
    # 严寒 → 喜悦下降（用阴天排除天气正向抵消）
    d3 = mood_deltas({"weather": "阴", "temperature": -5, "season": "冬", "moon_phase": "新月"})
    assert d3["joy"] < 0 and d3["fear"] > 0, f"严寒应压低喜悦、提升恐惧: {d3}"
    # 强度为 0 → 全 0
    d4 = mood_deltas({"weather": "晴", "temperature": 22, "season": "春", "moon_phase": "满月"},
                     weather_strength=0.0, season_strength=0.0, moon_strength=0.0)
    assert all(v == 0.0 for v in d4.values()), f"强度 0 应无影响: {d4}"
    # 强度 1.0 + 钳制 ±5
    d5 = mood_deltas({"weather": "晴", "temperature": 22, "season": "春", "moon_phase": "满月"},
                     weather_strength=1.0, season_strength=1.0, moon_strength=1.0)
    assert all(abs(v) <= 5.0 for v in d5.values()), f"单维应钳制 ±5: {d5}"
    # 温度分档边界
    assert temperature_band(-5) == "严寒" and temperature_band(5) == "寒冷"
    assert temperature_band(15) == "凉爽" and temperature_band(22) == "舒适"
    assert temperature_band(30) == "炎热" and temperature_band(35) == "酷热"
    assert temperature_band(None) is None, "未知温度不参与映射"
    print("PASS: 环境→心情映射（积极/消极/强度缩放/钳制/温度分档）")


# ── 8. 环境叙事注入 ─────────────────────────────────────
def test_env_injector():
    env = {"weather": "晴", "weather_emoji": "☀️", "temperature": 24, "temp_band": "舒适",
           "season": "春", "solar_term": "清明", "solar_term_today": True,
           "moon_phase": "蛾眉月", "moon_emoji": "🌒"}
    deltas = mood_deltas(env, weather_strength=0.3, season_strength=0.2, moon_strength=0.1)
    text = build_environment_info(env, deltas)
    for key in ("天气", "温度", "季节", "节气", "月相", "心情倾向", "清明", "今日"):
        assert key in text, f"注入文本应含「{key}」: {text}"
    assert "喜悦↑" in text, f"应有喜悦上升倾向: {text}"
    tendency = build_mood_tendency_text({})
    assert tendency == "", "无影响时应为空"
    print(f"PASS: 环境叙事注入（文本完整，示例: {text}）")


# ── 9. TPD 调度器骨架 ───────────────────────────────────
def test_orchestrator():
    with tempfile.TemporaryDirectory() as td:
        cfg = {
            "tpd_enabled": True, "tpd_weather_enabled": True,
            "tpd_weather_api_provider": "", "tpd_weather_api_key": "",
            "tpd_weather_api_city": "", "tpd_weather_cache_minutes": 60,
            "tpd_weather_mood_strength": 0.3, "tpd_season_mood_strength": 0.2,
            "tpd_moonphase_enabled": True, "tpd_moonphase_mood_strength": 0.1,
            "tpd_aqi_enabled": False,
        }
        orch = TPDOrchestrator(cfg, td)
        # 开启时：每轮返回环境
        result = orch.process_turn("u1", "今天怎么样？")
        assert result["environment"] is not None, "开启时应返回环境数据"
        assert result["inject_text"].startswith("[环境]"), f"注入文本格式: {result['inject_text']}"
        assert result["mood_deltas"], "应有心情映射"
        assert result["countdown"] is None and result["timeskip"] is None, "占位子系统应返回 None"
        # 面板数据
        panel = orch.environment_panel_data()
        assert panel["enabled"] is True and panel["environment"] is not None
        # 关闭时：全空
        orch_off = TPDOrchestrator(dict(cfg, tpd_enabled=False), td)
        r_off = orch_off.process_turn("u1", "hi")
        assert r_off["environment"] is None and r_off["inject_text"] == "", f"关闭应全空: {r_off}"
        # 默认配置兜底
        orch_default = TPDOrchestrator(None, td)
        assert orch_default.process_turn("u1")["inject_text"] == "", "默认 tpd_enabled=False 应全空"
    print("PASS: TPD 调度器骨架（开启/关闭/默认配置/面板数据/占位子系统）")


# ── 10. 配置 schema 注册 ────────────────────────────────
def test_schema():
    schema = json.loads((BASE / "_conf_schema.json").read_text(encoding="utf-8"))
    keys = [
        "tpd_enabled", "tpd_weather_enabled", "tpd_weather_api_provider",
        "tpd_weather_api_key", "tpd_weather_api_city", "tpd_weather_cache_minutes",
        "tpd_weather_mood_strength", "tpd_season_mood_strength",
        "tpd_moonphase_enabled", "tpd_moonphase_mood_strength", "tpd_aqi_enabled",
    ]
    miss = [k for k in keys if k not in schema]
    assert not miss, f"schema 缺失 TPD 键: {miss}"
    assert "_section_tpd" in schema, "缺 TPD 分组节"
    assert schema["tpd_enabled"]["default"] is False, "TPD 总开关默认应关闭"
    assert schema["tpd_weather_mood_strength"]["default"] == 0.3, "天气强度默认 0.3"
    assert schema["tpd_weather_api_provider"]["type"] == "string", "type 应用 string"
    print(f"PASS: 配置注册（{len(keys)} 个 TPD 键 + 分组节，schema 共 {len(schema)} 键）")


test_solar_terms()
test_season()
test_moon_phase()
test_weather_local()
test_weather_cache()
test_weather_disabled()
test_mood_mapper()
test_env_injector()
test_orchestrator()
test_schema()
print("\n全部 PASS: TPD Phase A 单模块测试通过")
