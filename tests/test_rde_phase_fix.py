"""SoulSync RDE - 断链修复验证测试

覆盖整体关联性检查发现的修复：
1. state_key 一致性（危机/冷落/查询同 key）
2. 社交事件在生产参数下触发（jealousy/mediation/misinfo）
3. 持久化 roundtrip（save_state → load_state 状态完整恢复）
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from astrbot_plugin_soulsync.rde import RDEOrchestrator

CFG = {"enable_rde": True, "enable_crisis_system": True, "enable_network": True}

class _Zero:
    def random(self): return 0.0
    def choice(self, seq): return seq[0]

# ── 1. state_key 一致性（修复 A：process_message 用 state_key）──
orch = RDEOrchestrator(CFG)
key = "uid1::cidX"
orch.crisis_trigger.rng = _Zero()
r = orch.process_message(key, {"round": 1, "stage_id": "s6", "favorability": 130.0})
assert r["crisis_triggered"] is not None, "应触发危机（写入 state_key）"
assert orch.get_active_crisis(key) is not None, "同 key 查询应可见未决危机"
cd = orch.get_cooldown(key)
assert cd["in_cooldown"] and cd["cold_penalties"] == 0
# 冷落惩罚加在同一 key（修复 main 的 add_cold_penalty 联动）
orch2 = RDEOrchestrator(CFG)
orch2.add_cold_penalty(key, 3)
assert orch2.get_cooldown(key)["cold_penalties"] == 3
ch = orch2.crisis_trigger.compute_chance({"user_id": key, "stage_id": "s6",
                                          "favorability": 130, "round": 0})
base = orch2.crisis_trigger.compute_chance({"user_id": "other_key", "stage_id": "s6",
                                            "favorability": 130, "round": 0})
assert ch > base, "冷落惩罚应提升同 key 触发概率"
# raw uid 与 state_key 分离：raw uid 无状态
assert orch2.get_cooldown("uid1")["cold_penalties"] == 0, "raw uid 不应有冷落状态"
print("PASS: state_key 一致性（危机/冷落/查询同 key，raw uid 隔离）")

# ── 2. 社交事件在生产参数下触发（修复 C/D）───────────────
o3 = RDEOrchestrator(CFG)
ctx3 = {"round": 5, "stage_id": "s6", "favorability": 160.0,
        "current_role": "恋人", "source_role": "恋人",
        "favorabilities": {"恋人": 160.0, "白月光": 120.0},
        "mention_roles": [], "user_name": "小雅"}
r3 = o3.process_message("u_social", dict(ctx3))
assert r3["social_event"] is not None and r3["social_event"].type == "jealousy", \
    f"吃醋应触发，实际 {r3['social_event']}"
assert r3["social_event"].target == "白月光"
# 无 favorabilities 数据时保守跳过（target 不在 favs）
o3b = RDEOrchestrator(CFG)
r3b = o3b.process_message("u_social2", {**ctx3, "favorabilities": {}})
assert r3b["social_event"] is None, "无邻居好感数据不应误触发"
# mediation：crisis_active 由 process_message 写入（修复 B）
o3c = RDEOrchestrator(CFG)
o3c.crisis_trigger.rng = _Zero()
r3c = o3c.process_message("u_med", {**ctx3, "current_role": "姐姐", "favorabilities": {}})
assert r3c["crisis_triggered"] is not None, "危机应先触发"
r3d = o3c.process_message("u_med", {"round": 6, "stage_id": "s6", "favorability": 160.0,
                                    "current_role": "姐姐", "source_role": "姐姐",
                                    "favorabilities": {"姐姐": 160.0, "妹妹": 150.0},
                                    "mention_roles": []})
assert r3d["social_event"] is not None and r3d["social_event"].type == "mediation", \
    f"调解应触发（危机中+前辈关系），实际 {r3d['social_event']}"
# misinfo：mention_roles 含邻居目标 + 未互动（闺蜜-死党 bestie 边，死党好感<100 避免助攻先触发）
o3e = RDEOrchestrator(CFG)
r3e = o3e.process_message("u_mis", {**ctx3, "current_role": "闺蜜",
                                    "favorabilities": {"闺蜜": 160.0, "死党": 90.0},
                                    "mention_roles": ["死党"]})
assert r3e["social_event"] is not None and r3e["social_event"].type == "misinfo", \
    f"误解传播应触发，实际 {r3e['social_event']}"
print("PASS: 社交事件接线（吃醋/调解/误解传播，空数据保守跳过）")

# ── 3. 持久化 roundtrip（修复：状态落盘恢复）──────────────
o4 = RDEOrchestrator(CFG)
u4 = "u_persist"
# 制造危机 + 历史 + 冷落 + 传导 + 互动统计
o4.crisis_trigger.rng = _Zero()
o4.process_message(u4, {"round": 1, "stage_id": "s6", "favorability": 130.0})
o4.process_message(u4, {"round": 2, "stage_id": "s6", "favorability": 130.0,
                        "current_role": "恋人", "source_role": "恋人",
                        "favorabilities": {"恋人": 130.0, "白月光": 110.0}})
o4.resolve_choice(u4, o4.get_active_crisis(u4).id,
                  o4.get_active_crisis(u4).choices[0].id)
o4.add_cold_penalty(u4, 2)
o4.record_interaction(u4, "恋人", 3, 1.0)
saved = o4.save_state(u4)
assert saved["crisis"], "导出应含危机状态"
assert saved["network"], "导出应含网络状态"
# 新实例恢复
o5 = RDEOrchestrator(CFG)
o5.load_state(u4, saved)
st5 = o5.get_cooldown(u4)
assert st5["cold_penalties"] == 2 and st5["total_rounds"] == 2, f"恢复轮次/冷落: {st5}"
assert len(o5.get_crisis_history(u4)) == 1, "历史应恢复"
assert o5.get_network_status(u4)["interaction_stats"].get("恋人", {}).get("count") == 1, \
    "互动统计应恢复"
r5 = o5.process_message(u4, {"round": 3, "stage_id": "s6", "favorability": 130.0,
                             "current_role": "恋人", "source_role": "恋人",
                             "favorabilities": {"恋人": 130.0, "白月光": 110.0}})
assert r5["transition"] is None, "恢复 _last_stage 后同阶段不应误报跃迁"
# pending 传导恢复：制造一条 pending 并结算
o6 = RDEOrchestrator(CFG)
o6.process_message("u_pend", {"round": 1, "stage_id": "s6", "favorability": 130.0,
                              "fav_delta": 2.0, "current_role": "恋人",
                              "source_role": "恋人",
                              "favorabilities": {"恋人": 130.0, "白月光": 110.0}})
pend = o6.save_state("u_pend")["network"].get("pending")
assert pend, "传导应入队"
o7 = RDEOrchestrator(CFG)
o7.load_state("u_pend", o6.save_state("u_pend"))
settled = o7.process_message("u_pend", {"round": 2, "stage_id": "s6",
                                        "favorability": 130.0})["settled"]
assert len(settled) >= 1, "恢复的 pending 应按时结算"
# JSON 可序列化性（落盘前提）
json.dumps(o4.save_state(u4), ensure_ascii=False)
print("PASS: 持久化 roundtrip（危机/历史/冷落/统计/pending/_last_stage 恢复一致）")

print("\nALL PASS: 断链修复测试（3 组）")
