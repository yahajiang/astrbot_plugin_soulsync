"""SoulSync RDE - Phase E 配置/命令/WebUI 面板验证测试

覆盖 _conf_schema.json 注册、_build_rde_panel 依赖的 orchestrator 数据形状、
main.py 命令与路由的静态接线（字符串级检查，无需 astrbot 运行时）。
"""
import sys, io, json, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

PKG = Path(__file__).resolve().parent.parent.parent / "astrbot_plugin_soulsync"
from astrbot_plugin_soulsync.rde import RDEOrchestrator

# ── 1. 配置项注册（E.1）────────────────────────────────────
schema = json.loads((PKG / "_conf_schema.json").read_text(encoding="utf-8"))
assert isinstance(schema, dict) and len(schema) >= 126, f"schema 键数异常: {len(schema)}"
assert "_info_header" in schema, "缺元信息键"
RDE_KEYS = {
    "enable_rde": False, "enable_crisis_system": True, "enable_network": True,
    "crisis_trigger_probability": 0.02, "crisis_max_probability": 0.10,
    "crisis_min_stage": "s3", "crisis_min_cold_penalties": 3,
    "crisis_min_rounds_secret": 500, "crisis_protection_hours": 72,
    "network_transmission_delay_turns": 1, "social_event_cooldown_rounds": 10,
    "jealousy_gap_threshold": 20, "assist_min_fav": 100, "competition_gap_threshold": 10,
}
by_key = schema
for k, default in RDE_KEYS.items():
    assert k in by_key, f"缺少 RDE 配置键: {k}"
    item = by_key[k]
    assert item["default"] == default, f"{k} 默认值错误: {item['default']} != {default}"
    assert item["type"], f"{k} 缺 type"
assert "enable_multi_role" in by_key, "既有键被破坏"
assert by_key["enable_rde"].get("group") == "RDE 关系深度演进" or "RDE" in str(by_key["enable_rde"].get("group", "")) or by_key["enable_rde"].get("group") is None, "enable_rde 分组"
print(f"PASS: 配置注册（{len(RDE_KEYS)} 个 RDE 键，schema 共 {len(schema)} 键）")

# ── 2. 面板数据形状（E.2 的 _build_rde_panel 依赖）────────
orch = RDEOrchestrator({"enable_rde": True, "enable_crisis_system": True, "enable_network": True})
stages = orch.all_stages()
assert len(stages) == 12, "正向阶段叙事配置 12 个"
s0 = stages[0]
for attr in ("stage_id", "stage_name", "positive", "threshold", "relationship_state",
             "dialogue_style", "address_changes", "interaction_features"):
    assert hasattr(s0, attr), f"阶段字段缺失: {attr}"
assert s0.stage_id == "s1" and s0.positive
cfg = orch.get_stage_config("s1")
assert cfg and cfg.stage_id == "s1" and cfg.positive, "get_stage_config 异常"
assert isinstance(orch.get_stage_description("s1"), str) and orch.get_stage_description("s1")
assert isinstance(orch.get_address("s1", {"user_name": ""}), str)
crisis = orch.get_cooldown("u_panel")
assert {"in_cooldown", "rounds_remaining", "cold_penalties", "total_rounds",
        "in_protection", "last_crisis_round"}.issubset(crisis.keys()), f"cooldown 字段缺失: {crisis.keys()}"
assert orch.get_active_crisis("u_panel") is None
assert isinstance(orch.get_crisis_history("u_panel"), list)
print("PASS: 面板数据形状（12 正向阶段 / current / cooldown / crisis）")

# ── 3. 关系网数据形状（E.5，dashboard 渲染依赖 edges）─────
net = orch.get_network_status("u_panel")
assert net["relation_count"] >= 30 and isinstance(net["edges"], list), f"edges 缺失: {net.keys()}"
assert "interaction_stats" in net and "pending_transfers" in net
for e in net["edges"][:3]:
    assert {"source", "target", "relation_type", "cross_coefficient"}.issubset(e.keys()), f"edge 字段缺失: {e.keys()}"
print(f"PASS: 关系网数据形状（{net['relation_count']} 条，edge 字段完整）")

# ── 4. main.py 命令与路由静态接线（E.2 / E.3）──────────────
main_src = (PKG / "main.py").read_text(encoding="utf-8")
for cmd, fn in [("RDE阶段", "cmd_rde_stage"), ("危机记录", "cmd_rde_crisis_log"), ("角色关系网", "cmd_rde_network")]:
    assert f'"{cmd}"' in main_src, f"缺少命令 {cmd}"
    assert f"def {fn}" in main_src, f"缺少处理函数 {fn}"
    assert "def _build_rde_panel" in main_src and "def _rde_target" in main_src
assert "rde/data" in main_src and "self._web_rde_data" in main_src, "缺少 rde/data 路由注册"
assert "def _web_rde_data" in main_src, "缺少 _web_rde_data 处理函数"
assert "def _web_trainer_data" in main_src, "既有 trainer 路由被破坏"
assert "_build_rde_panel(key)" in main_src, "_web_rde_data 未调用面板构建"
print("PASS: main.py 静态接线（3 命令 + rde/data 路由 + handler）")

# ── 5. 面板组合（模拟 _build_rde_panel 的拼装语义）────────
rel = {"小雪": {"type": "bestie", "cross_coefficient": 0.1, "description": "好友"}}
orch2 = RDEOrchestrator({"enable_rde": True, "custom_relations": rel})
net2 = orch2.get_network_status("u_panel")
assert len(net2["edges"]) > len(rel), "自定义关系应与默认网叠加"
assert any(e["target"] == "小雪" and e["source"] == "" and e["relation_type"] == "bestie"
           for e in net2["edges"]), "自定义关系边缺失"
stages = [s.stage_id for s in orch2.all_stages()]
assert "s1" in stages and "s12" in stages, "阶段列表不完整"
neg = orch2.get_stage_config("n1")
assert neg and not neg.positive, "负向阶段配置可查"
print("PASS: 面板组合语义（自定义关系 + 阶段列表 + 负向阶段）")

print("\nALL PASS: Phase E 测试（5 组）")
