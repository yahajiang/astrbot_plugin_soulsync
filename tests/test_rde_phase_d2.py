"""SoulSync RDE - Phase D2 接线验证测试

覆盖 main.py 接入所依赖的接口假设：
stage_id 映射 / llm_analyzer RDE 叙事参数 / 角色卡 relations / 危机结果应用序列（模拟 main 调用方式）
"""
import sys, io, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from astrbot_plugin_soulsync.rde import RDEOrchestrator
from astrbot_plugin_soulsync.rde.narrative.stage_definitions import stage_id_from_index
from astrbot_plugin_soulsync.llm_analyzer import LLMAnalyzer
from astrbot_plugin_soulsync.character_manager import CharacterManager
from astrbot_plugin_soulsync.emotion_engine import EmotionEngine, EmotionProfile

class _Zero:
    def random(self): return 0.0
    def choice(self, seq): return seq[0]

# ── 1. 阶段映射（main._run_rde_turn 的调用方式）────────────
assert stage_id_from_index(0, None) == "s1"
assert stage_id_from_index(5, None) == "s6"
assert stage_id_from_index(11, None) == "s12"
assert stage_id_from_index(99, None) == "s12", "越界钳制"
assert stage_id_from_index(0, "😐 冷淡") == "n1"
assert stage_id_from_index(0, "🔥 敌对") == "n4"
assert stage_id_from_index(0, "未知标签") == "n1", "未知负标签兜底"
print("PASS: 阶段映射（正向索引/越界钳制/负向标签/未知兜底）")

# ── 2. LLM 分析 prompt 追加 RDE 叙事（D.4）────────────────
p = LLMAnalyzer.build_analysis_prompt(
    favorability=120.0, intimacy=60.0, stage_label="暧昧萌动",
    emotions={}, memory_summary="", recent_messages="",
    rde_context="【当前关系阶段】暧昧萌动\n（悸动与试探）",
)
assert "[RDE 关系叙事]" in p and "暧昧萌动" in p
p2 = LLMAnalyzer.build_analysis_prompt(
    favorability=120.0, intimacy=60.0, stage_label="暧昧萌动",
    emotions={}, memory_summary="", recent_messages="",
)
assert "[RDE 关系叙事]" not in p2, "无叙事时不追加"
print("PASS: llm_analyzer rde_context 参数（有则追加，无则跳过）")

# ── 3. 角色卡 relations（D.5）─────────────────────────────
tmp = Path(tempfile.mkdtemp(prefix="soulsync_rde_"))
cm = CharacterManager(tmp)
cid, _ = cm.create("u1", "月华", relations={
    "小雪": {"type": "bestie", "cross_coefficient": 0.1, "description": "从小一起长大的好友"},
    "阿澈": {"type": "rival_love", "cross_coefficient": -0.05},
})
assert cid
rels = cm.get_relations("u1", cid)
assert rels["小雪"]["type"] == "bestie" and rels["阿澈"]["type"] == "rival_love"
assert cm.get_relations("u1") == rels, "默认读当前激活角色"
assert cm.get_relations("u_other") == {}, "无角色卡返回空"
cid2, _ = cm.create("u1", "无关系角色")
assert cm.get_relations("u1", cid2) == {}
# 角色卡 → RDE 自定义关系（main._get_rde_orchestrator 的用法：source 缺省=用户）
orch = RDEOrchestrator({"enable_rde": True, "custom_relations": rels})
rel0 = orch.get_relation("", "小雪")
assert rel0 is not None and rel0.relation_type == "bestie", "用户↔小雪 自定义边"
assert orch.get_relation("小雪", "") is not None, "双向查询命中同一条边"
assert orch.get_relation("", "阿澈").cross_coefficient == -0.05
imp = orch.calculate_cross_impact("", 10, 0, "u_c")
ti = [x for x in imp if x.target == "小雪"]
assert ti and abs(ti[0].delta - 1.0) < 1e-9, f"10×0.1=1.0，实际 {ti[0].delta if ti else None}"
print("PASS: 角色卡 relations 存取 + 载入 RDE 矩阵（用户↔角色边+传导）")

# ── 4. main 接线序列模拟：apply_change → RDE → 自动解决应用 ──
eng = EmotionEngine()
prof = EmotionProfile(user_id="u2")
for _ in range(160):
    eng.apply_change(prof, 2.0, 0.0, {}, None)   # 每轮净 +1.0，到 120~150 停下
    if 118 <= prof.favorability <= 150:
        break
print("   (stage_index =", prof.stage_index, ", fav =", prof.favorability, ")")
assert 118 <= prof.favorability <= 150, "需要好感 118~150（s6-s8 有候选事件）"
rde = RDEOrchestrator({"enable_rde": True})
rde.crisis_trigger.rng = _Zero()

def main_turn(round_no):
    """模拟 main：apply_change → process_message → 应用自动解决结果"""
    result = rde.process_message(prof.user_id, {
        "round": round_no,
        "stage_id": stage_id_from_index(prof.stage_index, None),
        "favorability": prof.favorability,
        "fav_delta": 0.0,
        "cold_penalty_add": 0,
        "current_role": "", "source_role": "",
        "special_date": False, "mention_other": False,
        "favorabilities": {}, "user_name": "",
    })
    resolved = result.get("crisis_resolved")
    if resolved is not None:
        prof.favorability = max(-100.0, min(200.0, prof.favorability + resolved.favorability_delta))
        if resolved.stage_delta < 0 and prof.stage_index > 0:
            prof.stage_index = max(0, prof.stage_index - 1)
            prof.stage_progress = eng.calc_stage_progress(prof)
    return result

t = main_turn(1)
assert t["crisis_triggered"] is not None, "第1轮应触发危机"
for rn in range(2, 5):
    rr = main_turn(rn)
    assert rr["crisis_ctx"], f"第{rn}轮危机进行中"
    assert rr["context_text"], "注入文本非空"
r = main_turn(5)
assert r["crisis_resolved"] is not None, "第5轮应自动解决"
old_fav = prof.favorability - r["crisis_resolved"].favorability_delta
assert prof.favorability == old_fav + r["crisis_resolved"].favorability_delta
assert prof.favorability < 200.0 or r["crisis_resolved"].favorability_delta >= 0
print(f"PASS: 接线序列（触发→4轮注入→自动解决应用，fav {old_fav:+.1f} → {prof.favorability:+.1f}）")

# ── 5. 冷落联动（每日结算 → add_cold_penalty）─────────────
class _PickCold:
    def random(self): return 0.0
    def choice(self, seq):
        for c in seq:
            if c.type == "cold":
                return c
        return seq[0]

rde2 = RDEOrchestrator({"enable_rde": True})
rde2.add_cold_penalty("u3", 1)
rde2.add_cold_penalty("u3", 1)
rde2.add_cold_penalty("u3", 1)
assert rde2.get_cooldown("u3")["cold_penalties"] == 3
rde2.crisis_trigger.rng = _PickCold()
ev = rde2.process_message("u3", {
    "round": 10, "stage_id": "s6", "favorability": 120,
    "cold_penalty_add": 0,
})["crisis_triggered"]
assert ev is not None and ev.type == "cold", f"冷落累计应触发冷落型，实际 {ev}"
print("PASS: 冷落累计联动（每日结算 3 次 → 触发冷落型危机）")

print("\n全部 Phase D2 接线验证通过 ✔")
