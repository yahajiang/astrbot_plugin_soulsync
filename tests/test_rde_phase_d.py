"""SoulSync RDE - Phase D 集成测试：RDEOrchestrator.process_message 每轮 6 步完整流程

覆盖：基础流程 / 危机触发与叙事注入 / 选择与自动解决 / 跨角色传导 / 阶段跃迁 /
冷落惩罚累计 / 社交事件联动 / 禁用模式
"""
import sys, io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from astrbot_plugin_soulsync.rde import RDEOrchestrator

class _Zero:
    def random(self): return 0.0
    def choice(self, seq): return seq[0]

class _PickConditional:
    TYPES = {"cold", "secret", "external", "jealousy"}
    def random(self): return 0.0
    def choice(self, seq):
        for c in seq:
            if c.type in self.TYPES:
                return c
        return seq[0]

# ── 1. 基础流程：六段返回 + 阶段叙事注入 ─────────────────
orch = RDEOrchestrator({"enable_rde": True})
r = orch.process_message("u_base", {
    "round": 1, "stage_id": "s6", "favorability": 120, "fav_delta": 0,
    "current_role": "恋人", "user_name": "阿澈",
})
assert isinstance(r, dict)
for k in ("stage_id", "context_text", "stage_ctx", "crisis_ctx", "perception_ctx",
          "crisis_triggered", "crisis_resolved", "transition", "impacts", "settled",
          "social_event"):
    assert k in r, f"缺少返回键 {k}"
assert r["stage_id"] == "s6"
assert r["crisis_triggered"] is None and r["crisis_resolved"] is None
assert r["transition"] is None, "首轮无旧阶段不应产生跃迁"
assert "暧昧" in r["stage_ctx"] or "心动" in r["stage_ctx"] or "好感" in r["stage_ctx"], r["stage_ctx"]
assert r["context_text"] == r["stage_ctx"], "无危机/无感知时注入文本=阶段叙事"
print("PASS: 基础流程（六段返回齐全，阶段叙事注入，首轮无跃迁）")

# ── 2. 危机触发并注入 ─────────────────────────────────────
c = RDEOrchestrator({"enable_rde": True})
c.crisis_trigger.rng = _Zero()
r2 = c.process_message("u_trig", {
    "round": 10, "stage_id": "s6", "favorability": 120, "fav_delta": 0,
    "current_role": "恋人", "user_name": "阿澈",
})
ev = r2["crisis_triggered"]
assert ev is not None, "随机命中应触发危机"
assert ev.id and ev.type in {"misunderstanding", "trust", "growth"}
assert "关系危机" in r2["crisis_ctx"] or "危机" in r2["crisis_ctx"], r2["crisis_ctx"]
assert "危机" in r2["context_text"]
active = c.get_active_crisis("u_trig")
assert active is not None and active.id == ev.id
print(f"PASS: 危机触发并注入叙事（本次命中 {ev.id}）")

# ── 3. 危机选择：结果应用与冷却 ───────────────────────────
sel = RDEOrchestrator({"enable_rde": True})
sel.crisis_trigger.rng = _Zero()
sev = sel.check_crisis_trigger("u_sel", {"stage_id": "s8", "favorability": 160, "round": 0})
assert sev is not None
res = sel.resolve_choice("u_sel", sev.id, "a", {"char_name": "小雪", "friend_name": "小雅"})
assert res is not None and res.resolved
assert isinstance(res.favorability_delta, (int, float))
assert isinstance(res.stage_delta, int) and -1 <= res.stage_delta <= 1
assert sel.get_active_crisis("u_sel") is None, "选择后危机应解决"
cd = sel.get_cooldown("u_sel", current_round=1)
assert cd["in_cooldown"], "解决后应进入冷却"
assert len(sel.get_crisis_history("u_sel")) == 1
print(f"PASS: 危机选择应用（fav_delta={res.favorability_delta} stage_delta={res.stage_delta}，进入冷却，历史记录）")

# ── 4. 自动解决（期限耗尽）────────────────────────────────
au = RDEOrchestrator({"enable_rde": True})
au.crisis_trigger.rng = _Zero()
r0 = au.process_message("u_auto", {"round": 10, "stage_id": "s6", "favorability": 120})
assert r0["crisis_triggered"] is not None, "第10轮应触发危机"
for rn in (11, 12, 13):
    rr = au.process_message("u_auto", {"round": rn, "stage_id": "s6", "favorability": 120})
    assert rr["crisis_ctx"], f"第{rn}轮危机应持续注入"
r14 = au.process_message("u_auto", {"round": 14, "stage_id": "s6", "favorability": 120})
assert r14["crisis_resolved"] is not None, "期限耗尽应自动解决"
assert r14["crisis_triggered"] is None, "冷却期内不应立即再触发"
assert not r14["crisis_ctx"], "解决后不再注入危机叙事"
hist = au.get_crisis_history("u_auto")
assert hist and hist[-1]["choice_id"] == "__auto__"
print("PASS: 危机期限耗尽自动解决（rounds_left 递减→auto_resolve，冷却拦截重触发）")

# ── 5. 跨角色传导（延迟一轮到账）──────────────────────────
nw = RDEOrchestrator({"enable_rde": True})
r5 = nw.process_message("u_net", {
    "round": 5, "stage_id": "s6", "favorability": 120, "fav_delta": 10,
    "source_role": "闺蜜", "current_role": "闺蜜",
    "favorabilities": {"闺蜜": 120, "死党": 100},
})
assert r5["impacts"], "好感变化应产生跨角色影响"
d = [i for i in r5["impacts"] if i.target == "死党"]
assert d and abs(d[0].delta - 1.0) < 1e-9, f"闺蜜+10 → 死党+1.0，实际 {d[0].delta if d else None}"
assert not r5["settled"], "第5轮排队，不应立即到账"
r6 = nw.process_message("u_net", {
    "round": 6, "stage_id": "s6", "favorability": 120, "fav_delta": 0,
    "source_role": "闺蜜", "current_role": "闺蜜",
})
st = [p for p in r6["settled"] if p.target == "死党"]
assert st and abs(st[0].amount - 1.0) < 1e-9, "第6轮应结算死党+1.0"
print("PASS: 跨角色传导（round5 排队 → round6 到账 +1.0）")

# ── 6. 阶段跃迁事件 ──────────────────────────────────────
tr = RDEOrchestrator({"enable_rde": True})
tr.process_message("u_tr", {"round": 1, "stage_id": "s5", "favorability": 100})
tr.process_message("u_tr", {"round": 2, "stage_id": "s6", "favorability": 120})
r_t = tr.process_message("u_tr", {"round": 3, "stage_id": "s6", "favorability": 120})
assert r_t["transition"] is None, "阶段未变不应有跃迁"
r_t2 = tr.process_message("u_tr", {"round": 4, "stage_id": "s7", "favorability": 140})
assert r_t2["transition"] is not None, "阶段变化应产生跃迁事件"
assert r_t2["transition"].new_stage == "s7"
assert r_t2["transition"].kind == "upgrade"
print("PASS: 阶段跃迁事件（s6→s7 upgrade，同阶段无重复事件）")

# ── 7. 冷落惩罚累计 → 冷落型危机 ──────────────────────────
cold = RDEOrchestrator({"enable_rde": True})
cold.crisis_trigger.rng = _Zero()
rc = cold.process_message("u_cold", {
    "round": 1, "stage_id": "s6", "favorability": 120, "cold_penalty_add": 3,
})
assert cold.get_cooldown("u_cold", current_round=1)["cold_penalties"] == 3, "冷落惩罚应累计"
cold.crisis_store.clear_active("u_cold")
cold.crisis_store.get("u_cold").cooldown_until_round = 0
cold.crisis_trigger.rng = _PickConditional()
rc2 = cold.process_message("u_cold", {
    "round": 2, "stage_id": "s6", "favorability": 120,
})
assert rc2["crisis_triggered"] is not None and rc2["crisis_triggered"].type == "cold", \
    f"冷落累积3次应触发冷落型，实际 {rc2['crisis_triggered']}"
print("PASS: 冷落惩罚累计3次触发冷落型危机")

# ── 8. 社交事件联动（process_message 内自动检测）─────────
se = RDEOrchestrator({"enable_rde": True})
r8 = se.process_message("u_ev", {
    "round": 1, "stage_id": "s6", "favorability": 130, "fav_delta": 0,
    "current_role": "恋人",
    "favorabilities": {"恋人": 160, "白月光": 120},
    "mention_roles": ["白月光"],
})
assert r8["social_event"] is not None and r8["social_event"].type == "jealousy", r8["social_event"]
assert "白月光" in r8["perception_ctx"] and "情敌" in r8["perception_ctx"], r8["perception_ctx"]
# 无事件时为空
r8b = se.process_message("u_ev", {
    "round": 1, "stage_id": "s6", "favorability": 130, "fav_delta": 0,
    "current_role": "恋人",
    "favorabilities": {"恋人": 130, "白月光": 120},
})
assert r8b["social_event"] is None
print("PASS: 社交事件在每轮流程中自动检测，感知注入联动")

# ── 9. 禁用模式：全链路无输出 ─────────────────────────────
off = RDEOrchestrator({"enable_rde": False})
off.crisis_trigger.rng = _Zero()
r9 = off.process_message("u_off", {
    "round": 1, "stage_id": "s6", "favorability": 120, "fav_delta": 10,
    "source_role": "闺蜜", "current_role": "恋人",
    "favorabilities": {"恋人": 160, "白月光": 120},
})
assert not r9["context_text"], "禁用时不应注入任何文本"
assert r9["crisis_triggered"] is None and r9["transition"] is None
assert not r9["impacts"] and not r9["settled"]
assert r9["social_event"] is None
print("PASS: 禁用模式全链路无输出")

print("\n全部 Phase D 集成测试通过 ✔")
