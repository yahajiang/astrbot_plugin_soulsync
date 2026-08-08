"""SoulSync WebUI 配置板块完整性测试

校验 dashboard 配置面板 secs 分组与 _conf_schema.json 全量互覆盖，
防止新增配置键后 WebUI 缺项（历史问题：曾缺 49 键）。
"""
import sys, json, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
PKG = Path(__file__).resolve().parent.parent

# ── 1. 读取 schema 与面板 secs ──────────────────────────────
schema = json.loads((PKG / "_conf_schema.json").read_text(encoding="utf-8"))
html = (PKG / "pages/dashboard/index.html").read_text(encoding="utf-8")
m = re.search(r"const secs=(\{.*?\});\n", html, re.S)
assert m, "未找到 secs 定义"
secs_js = m.group(1).replace("'", '"')
secs = json.loads(secs_js)
assert isinstance(secs, dict) and len(secs) == 16, f"预期 16 个模块组, 实际 {len(secs)}"
for g, ks in secs.items():
    assert isinstance(ks, list) and ks, f"组 {g} 无键"

# ── 2. 全量互覆盖：schema 配置键 ⊆ 面板组键 ⊆ schema 键 ────
schema_keys = set(k for k in schema if not k.startswith("_"))
panel_keys = set(k for ks in secs.values() for k in ks)
missing = schema_keys - panel_keys
assert not missing, f"面板缺失配置键: {sorted(missing)}"
extra = panel_keys - schema_keys
assert not extra, f"面板含非法键: {sorted(extra)}"
assert panel_keys == schema_keys
print(f"PASS: 面板覆盖 schema 全部 {len(schema_keys)} 键 / 16 组")

# ── 3. 模块分类：RDE 键归入 _section_rde 之后 ───────────────
RDE = ["enable_rde", "rde_stage_inject_every_n", "enable_crisis_system", "enable_network",
       "crisis_trigger_probability", "crisis_max_probability", "crisis_min_stage",
       "crisis_min_cold_penalties", "crisis_min_rounds_secret", "crisis_protection_hours",
       "network_transmission_delay_turns", "social_event_cooldown_rounds",
       "jealousy_gap_threshold", "assist_min_fav", "competition_gap_threshold"]
assert "_section_rde" in schema, "缺 _section_rde 分组标记"
ks = list(schema)
rde_pos = [ks.index(k) for k in RDE]
sec_rde_pos = ks.index("_section_rde")
assert min(rde_pos) > sec_rde_pos, "RDE 键未归入 _section_rde 之后"
assert set(RDE) <= panel_keys, "面板缺 RDE 键"

# ── 4. 版本号 ───────────────────────────────────────────────
hdr = schema["_info_header"]["description"]
assert "v2.22" in hdr, f"_info_header 版本未更新: {hdr}"

# ── 5. 控制台按钮文案与组数一致 ─────────────────────────────
assert "141 项参数" in html and "16 个模块组" in html, "控制台按钮文案未同步"
print("PASS: 模块分类（_section_rde 分组）+ v2.22 + 按钮文案")
