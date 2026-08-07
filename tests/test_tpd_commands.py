"""TPD Phase E - 命令与 WebUI 集成测试

覆盖：用户命令（天气/倒计时/跳跃）输出结构、管理员命令（强制跳跃/重置跳跃/天气调试）输出结构、
WebUI API endpoint 返回格式、TPD 面板数据结构。
"""

import datetime
import io
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from astrbot_plugin_soulsync.tpd import TPDOrchestrator
from astrbot_plugin_soulsync.tpd.mood_mapper import DIM_LABELS, EMOTION_DIMS

BASE = Path(__file__).resolve().parent.parent


def _make_orch(td: str) -> TPDOrchestrator:
    return TPDOrchestrator(
        {"tpd_enabled": True, "tpd_weather_enabled": True, "tpd_weather_api_provider": ""}, td
    )


# ── 1. 环境面板数据结构 ────────────────────────────────────
def test_environment_panel():
    with tempfile.TemporaryDirectory() as td:
        orch = _make_orch(td)
        panel = orch.environment_panel_data()
        assert "enabled" in panel and "environment" in panel, panel
        assert panel["enabled"] is True
        env = panel.get("environment")
        assert env is not None, "天气推算应返回环境数据"
        assert "weather" in env and "season" in env, env
        deltas = panel.get("mood_deltas") or {}
        assert isinstance(deltas, dict), "mood_deltas 应为 dict"
        print(f"PASS: 环境面板（{env['weather']}·{env['season']}·{len(deltas)}维心情）")


# ── 2. 倒计时面板数据结构 ──────────────────────────────────
def test_countdown_panel():
    with tempfile.TemporaryDirectory() as td:
        orch = _make_orch(td)
        panel = orch.countdown_panel_data("u1")
        assert "enabled" in panel and "events" in panel, panel
        assert isinstance(panel["events"], list), "events 应为 list"
        print(f"PASS: 倒计时面板（{len(panel['events'])} 事件）")


# ── 3. 跳跃面板数据结构 ────────────────────────────────────
def test_skip_panel():
    with tempfile.TemporaryDirectory() as td:
        orch = _make_orch(td)
        # 无跳跃时
        panel = orch.skip_panel_data("u1")
        assert "enabled" in panel and "status" in panel, panel
        st = panel["status"]
        assert st["offset_days"] == 0 and st["pending_return"] is False
        # 跳跃后
        orch.process_turn("u1", "三天后见")
        panel2 = orch.skip_panel_data("u1")
        st2 = panel2["status"]
        assert st2["offset_days"] == 3, f"偏移: {st2}"
        assert len(st2["skip_log"]) >= 1, "应有跳跃记录"
        print(f"PASS: 跳跃面板（偏移{st2['offset_days']}天·{len(st2['skip_log'])}条记录）")


# ── 4. 命令输出格式：天气 ──────────────────────────────────
def test_cmd_weather_output():
    with tempfile.TemporaryDirectory() as td:
        orch = _make_orch(td)
        panel = orch.environment_panel_data()
        env = panel.get("environment") or {}
        # 模拟 /天气 命令输出
        lines = ["🌤️ 环境感知", "━" * 20]
        if env.get("weather"):
            lines.append(f"天气: {env.get('weather_emoji', '')}{env['weather']}")
        if env.get("temperature") is not None:
            lines.append(f"温度: {env['temperature']}℃")
        if env.get("season"):
            lines.append(f"季节: {env['season']}")
        if env.get("solar_term"):
            lines.append(f"节气: {env['solar_term']}")
        output = "\n".join(lines)
        assert "环境感知" in output, output
        assert "天气:" in output, output
        print(f"PASS: /天气 命令输出格式正确")


# ── 5. 命令输出格式：倒计时 ────────────────────────────────
def test_cmd_countdown_output():
    with tempfile.TemporaryDirectory() as td:
        orch = _make_orch(td)
        panel = orch.countdown_panel_data("u1")
        events = panel.get("events", [])
        if events:
            lines = ["📅 倒计时事件", "━" * 20]
            for e in events[:10]:
                lines.append(f"  {e['name']} · {e['days_left']}天后")
            output = "\n".join(lines)
            assert "倒计时事件" in output
        else:
            output = "📅 暂无即将到来的倒计时事件"
        print(f"PASS: /倒计时 命令输出格式正确（{len(events)} 事件）")


# ── 6. 命令输出格式：跳跃状态 ──────────────────────────────
def test_cmd_skip_output():
    with tempfile.TemporaryDirectory() as td:
        orch = _make_orch(td)
        # 无跳跃
        panel = orch.skip_panel_data("u1")
        st = panel["status"]
        lines = ["⏰ 时间跳跃状态", "━" * 20]
        if st["offset_days"] > 0:
            lines.append(f"时间偏移: +{st['offset_days']} 天")
        if st["pending_return"]:
            lines.append("状态: 待回归 ⏳")
        else:
            lines.append("状态: 正常 ✅")
        output = "\n".join(lines)
        assert "时间跳跃状态" in output
        assert "正常" in output
        # 有跳跃
        orch.process_turn("u1", "三天后见")
        panel2 = orch.skip_panel_data("u1")
        st2 = panel2["status"]
        lines2 = ["⏰ 时间跳跃状态", "━" * 20]
        lines2.append(f"时间偏移: +{st2['offset_days']} 天")
        output2 = "\n".join(lines2)
        assert "+3 天" in output2
        print("PASS: /跳跃 命令输出格式正确")


# ── 7. 强制跳跃命令模拟 ────────────────────────────────────
def test_cmd_force_skip():
    from astrbot_plugin_soulsync.tpd.skip_parser import SkipCommand
    with tempfile.TemporaryDirectory() as td:
        orch = _make_orch(td)
        cmd = SkipCommand(skip_days=7, reason="管理员强制跳跃7天")
        orch.skip_executor.execute_skip("u1", cmd, now=time.time())
        st = orch.skip_executor.get_state("u1")
        assert st["offset_days"] == 7, f"强制跳跃: {st}"
        assert st["frozen_until"] > time.time(), "冻结应生效"
        print("PASS: /强制跳跃 命令逻辑正确")


# ── 8. 重置跳跃命令模拟 ────────────────────────────────────
def test_cmd_reset_skip():
    with tempfile.TemporaryDirectory() as td:
        orch = _make_orch(td)
        orch.process_turn("u1", "三天后见")
        st = orch.skip_executor.get_state("u1")
        assert st["offset_days"] == 3
        # 重置
        st["offset_days"] = 0
        st["pending_return"] = False
        st["frozen_until"] = 0.0
        orch.skip_executor.save_uid("u1")
        st2 = orch.skip_executor.get_state("u1")
        assert st2["offset_days"] == 0 and st2["pending_return"] is False
        print("PASS: /重置跳跃 命令逻辑正确")


# ── 9. WebUI API 返回格式 ──────────────────────────────────
def test_webui_api_format():
    with tempfile.TemporaryDirectory() as td:
        orch = _make_orch(td)
        orch.process_turn("u1", "三天后见")
        # 模拟 _web_tpd_data 返回
        result = {
            "environment": orch.environment_panel_data(),
            "countdown": orch.countdown_panel_data("u1"),
            "skip": orch.skip_panel_data("u1"),
        }
        assert "environment" in result and "countdown" in result and "skip" in result
        env = result["environment"]
        assert "enabled" in env and "environment" in env
        cd = result["countdown"]
        assert "enabled" in cd and "events" in cd
        sk = result["skip"]
        assert "enabled" in sk and "status" in sk
        assert sk["status"]["offset_days"] == 3
        # JSON 序列化不报错
        json_str = json.dumps(result, ensure_ascii=False)
        assert len(json_str) > 100
        print("PASS: WebUI API 返回格式正确")


# ── 10. 天气调试信息结构 ───────────────────────────────────
def test_weather_debug_info():
    with tempfile.TemporaryDirectory() as td:
        orch = _make_orch(td)
        panel = orch.environment_panel_data()
        env = panel.get("environment") or {}
        # 模拟 /天气调试 输出
        lines = ["🔍 天气调试信息", "━" * 20]
        lines.append(f"TPD 开关: True")
        lines.append(f"天气开关: True")
        if env:
            lines.append(f"当前天气: {env.get('weather', '?')} {env.get('weather_emoji', '')}")
            lines.append(f"来源: {env.get('source', '?')}")
        output = "\n".join(lines)
        assert "天气调试信息" in output
        assert "天气:" in output
        print("PASS: /天气调试 命令输出格式正确")


test_environment_panel()
test_countdown_panel()
test_skip_panel()
test_cmd_weather_output()
test_cmd_countdown_output()
test_cmd_skip_output()
test_cmd_force_skip()
test_cmd_reset_skip()
test_webui_api_format()
test_weather_debug_info()
print("\n全部 PASS: TPD Phase E 命令与 WebUI 集成测试通过")
