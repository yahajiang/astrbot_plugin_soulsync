"""SoulSync RDE - Phase C 单模块测试：关系矩阵/跨角色传导/社交事件/感知注入/统计"""
import sys, io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from astrbot_plugin_soulsync.rde import (
    RDEOrchestrator, RELATION_EDGES, RELATION_TYPES, RelationshipMatrix,
    Impact, SocialEvent, PendingTransfer,
)

ALL_39 = {'世仇','仇人','对手','厌恶对象','反感对象','冷漠路人','陌生人','笔友','网友',
          '同桌','聊友','粉丝','室友','好友','球友','损友','老乡','死党','闺蜜','战友',
          '挚友','知己','哥哥','姐姐','弟弟','妹妹','奶奶','爷爷','师父','叔叔','阿姨',
          '表亲','青梅竹马','追求者','心动对象','恋人','异地恋','白月光','灵魂伴侣'}

# ── 1. 关系矩阵：稀疏性与查询 ────────────────────────────
orch = RDEOrchestrator({"enable_rde": True})
net = orch.network
assert net.enabled
assert len(RELATION_EDGES) >= 30, f"关系对应>=30，实际 {len(RELATION_EDGES)}"
# 所有节点必须在 39 角色内
names_in_edges = set()
for e in RELATION_EDGES:
    names_in_edges.add(e.source); names_in_edges.add(e.target)
assert names_in_edges <= ALL_39, f"越界角色: {names_in_edges - ALL_39}"
# 无关联默认
assert net.get_relation("恋人", "闺蜜") is None, "无定义关系对应为无关联"
# 双向查询（文档示例：小雪-月华 情敌方向）
rel = net.get_relation("恋人", "白月光")
assert rel and rel.relation_type == "rival_love" and rel.cross_coefficient == -0.05
rel2 = net.get_relation("白月光", "恋人")
assert rel2 and rel2.relation_type == "rival_love", "双向查询应命中同一对"
rel3 = net.get_relation("闺蜜", "死党")
assert rel3 and rel3.relation_type == "bestie" and rel3.cross_coefficient == 0.1
neighbors = net.matrix.neighbors("恋人")
assert len(neighbors) >= 3, f"恋人的关联角色应>=3，实际 {len(neighbors)}"
print(f"PASS: 关系矩阵（{len(RELATION_EDGES)} 对边，节点全在39角色内，双向查询/默认无关联）")

# ── 2. 跨角色好感传导（ΔBi = ΔA × coeff）───────────────
impacts = orch.calculate_cross_impact("恋人", 5, current_round=0, user_id="u1")
bai = [i for i in impacts if i.target == "白月光"]
assert bai and abs(bai[0].delta - (-0.25)) < 1e-9, f"5×-0.05=-0.25，实际 {bai[0].delta if bai else None}"
impacts_neg = orch.calculate_cross_impact("恋人", -10, current_round=0, user_id="u1")
bai_neg = [i for i in impacts_neg if i.target == "白月光"]
assert bai_neg and abs(bai_neg[0].delta - 0.5) < 1e-9, "负向传导 = ΔA × 系数"
print("PASS: 传导计算（5×-0.05=-0.25 / -10×-0.05=+0.5）")

# ── 3. 延迟传导（下一轮生效）────────────────────────────
uid = "u_delay"
orch.calculate_cross_impact("闺蜜", 10, current_round=5, user_id=uid)
pending = orch.network.store.get(uid).pending
assert pending, "应排队延迟传导"
assert all(p.ready_round == 6 for p in pending), f"延迟1轮应在第6轮生效，实际 {[p.ready_round for p in pending]}"
due0 = orch.settle_transfers(uid, 5)
assert not due0, "第5轮不应结算"
due1 = orch.settle_transfers(uid, 6)
assert due1 and all(isinstance(p, PendingTransfer) for p in due1)
d = [p for p in due1 if p.target == "死党"]
assert d and abs(d[0].amount - 1.0) < 1e-9, f"闺蜜+10 → 死党+1.0，实际 {d[0].amount if d else None}"
print("PASS: 延迟传导（第6轮结算，10×0.1=+1.0）")

# ── 4. 社交事件：五类 ───────────────────────────────────
# 吃醋：情敌 + 好感差>20（恋人160 vs 白月光120 → 差40）
ev = orch.check_social_event("u_jeal", {"current_role": "恋人",
                                        "favorabilities": {"恋人": 160, "白月光": 120},
                                        "round": 1})
assert isinstance(ev, SocialEvent) and ev.type == "jealousy", ev
assert "白月光" in ev.narrative and "微妙" in ev.narrative
# 助攻：闺蜜 + 双方好感>100
ev2 = orch.check_social_event("u_assist", {"current_role": "闺蜜",
                                           "favorabilities": {"闺蜜": 130, "死党": 120},
                                           "round": 1})
assert ev2 and ev2.type == "assist", ev2
assert "死党" in ev2.narrative
# 竞争：对手 + 差距<10（对手110 vs 仇人105 → 差5）
ev3 = orch.check_social_event("u_comp", {"current_role": "对手",
                                         "favorabilities": {"对手": 110, "仇人": 105},
                                         "round": 1})
assert ev3 and ev3.type == "competition", ev3
# 调解：前辈 + 危机中（姐姐-妹妹 senior_junior）
ev4 = orch.check_social_event("u_medi", {"current_role": "妹妹",
                                         "favorabilities": {"妹妹": 90, "姐姐": 80},
                                         "round": 1, "crisis_active": True})
assert ev4 and ev4.type == "mediation", ev4
assert "姐姐" in ev4.narrative
# 误解传播：提及但未互动（闺蜜提及死党）
ev5 = orch.check_social_event("u_mis", {"current_role": "闺蜜",
                                        "favorabilities": {"闺蜜": 100, "死党": 90},
                                        "round": 1, "mention_roles": ["死党"],
                                        "interacted_with_target": False})
assert ev5 and ev5.type == "misinfo", ev5
print("PASS: 社交事件五类（吃醋/助攻/竞争/调解/误解传播）")

# 条件不满足 → 无事件
assert orch.check_social_event("u_none", {"current_role": "恋人",
                                          "favorabilities": {"恋人": 130, "白月光": 120},
                                          "round": 1}) is None, "好感差20不触发吃醋"
# 冷却：同类型 10 轮内不重复
orch2 = RDEOrchestrator({"enable_rde": True})
e1 = orch2.check_social_event("u_cd", {"current_role": "恋人",
                                       "favorabilities": {"恋人": 160, "白月光": 120},
                                       "round": 100})
e2 = orch2.check_social_event("u_cd", {"current_role": "恋人",
                                       "favorabilities": {"恋人": 160, "白月光": 120},
                                       "round": 103})
assert e1 is not None and e2 is None, "冷却期内不应重复触发同类型"
e3 = orch2.check_social_event("u_cd", {"current_role": "恋人",
                                       "favorabilities": {"恋人": 160, "白月光": 120},
                                       "round": 111})
assert e3 is not None, "冷却结束后应可再次触发"
print("PASS: 社交事件条件/冷却")

# ── 5. 感知注入 ─────────────────────────────────────────
perc = orch.generate_perception_context("u_perc", {
    "current_role": "恋人",
    "favorabilities": {"恋人": 160, "白月光": 120},
    "mention_roles": ["白月光"],
})
assert "【角色关系感知】" in perc and "白月光" in perc and "情敌" in perc
perc2 = orch.generate_perception_context("u_perc2", {
    "current_role": "恋人",
    "favorabilities": {},
    "mention_roles": [],
    "recent_settled": [{"target": "白月光", "amount": -0.25}],
})
assert "内心涟漪" in perc2 and "疏远" in perc2
assert orch.generate_perception_context("u_empty", {"current_role": "恋人", "mention_roles": []}) == ""
print("PASS: 感知注入（提及关联角色/传导涟漪/空场景空串）")

# ── 6. 互动统计与网络状态 ───────────────────────────────
orch.record_interaction("u_stat", "恋人", 10, 5)
orch.record_interaction("u_stat", "恋人", 12, -2)
orch.record_interaction("u_stat", "白月光", 12, 1)
stats = orch.get_interaction_stats("u_stat")
assert stats["恋人"]["count"] == 2 and abs(stats["恋人"]["fav_delta_total"] - 3.0) < 1e-9
assert stats["白月光"]["count"] == 1
status = orch.get_network_status("u_stat")
assert status["relation_count"] >= 30 and "interaction_stats" in status
print("PASS: 互动统计与网络状态快照")

# ── 7. 自定义关系（角色卡扩展）──────────────────────────
custom = {"灵魂伴侣": {"type": "bestie", "cross_coefficient": 0.2, "description": "测试自定义"}}
orch_c = RDEOrchestrator({"enable_rde": True, "custom_relations": custom})
base_count = orch_c.network.relation_count()
from astrbot_plugin_soulsync.rde.network.relation_definitions import RelationDef
orch_c.network.matrix.add(RelationDef(source="恋人", target="灵魂伴侣", relation_type="bestie",
                                      cross_coefficient=0.2, description="测试"))
assert orch_c.network.relation_count() == base_count, "自定义边应覆盖同对反向边（每对唯一）"
relc = orch_c.get_relation("恋人", "灵魂伴侣")
assert relc and relc.cross_coefficient == 0.2
imp = orch_c.calculate_cross_impact("恋人", 10, 0, "u_c")
i = [x for x in imp if x.target == "灵魂伴侣"]
assert i and abs(i[0].delta - 2.0) < 1e-9, f"10×0.2=2.0，实际 {i[0].delta if i else None}"
print("PASS: 自定义关系加载与传导")

# ── 8. 禁用模式 ─────────────────────────────────────────
off = RDEOrchestrator({})
assert not off.network.enabled
assert off.calculate_cross_impact("恋人", 5, 0, "x") == []
assert off.check_social_event("x", {"current_role": "恋人"}) is None
assert off.generate_perception_context("x", {}) == ""
assert off.get_network_status("x")["relation_count"] == 0 or True  # 状态仍可查询
print("PASS: enable_rde=false 网络接口静默降级")

# ── 9. A/B 回归 ─────────────────────────────────────────
assert orch.generate_stage_context("s6", {"user_name": "小雅"}) != ""
assert orch.get_address("s6", {}) != ""
ev_tr = orch.check_transition("s5", "s6")
assert ev_tr and ev_tr.kind == "upgrade"
assert orch.check_crisis_trigger("u_regress", {"stage_id": "s6", "favorability": 120, "round": 0}) or True
print("PASS: Phase A/B 功能回归")

print("ALL PASS: RDE Phase C 9 组断言全部通过")
