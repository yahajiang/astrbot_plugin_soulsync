"""SoulSync RDE - Phase B 单模块测试：危机事件池/触发引擎/选择处理/阶段倒退/调度器集成"""
import sys, io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from astrbot_plugin_soulsync.rde import (
    RDEOrchestrator, CRISIS_EVENTS, CRISIS_TYPES, ResolutionResult,
    get_stage_definition,
)

# ── 1. 事件池完整性：7 类型 × 2 = 14 个 ──────────────────
assert len(CRISIS_EVENTS) == 14, f"应为14个事件，实际 {len(CRISIS_EVENTS)}"
ids = [c.id for c in CRISIS_EVENTS]
assert len(ids) == len(set(ids)), "事件 id 不能重复"
from collections import Counter
type_counts = Counter(c.type for c in CRISIS_EVENTS)
assert set(type_counts) == set(CRISIS_TYPES), type_counts
assert all(v == 2 for v in type_counts.values()), type_counts
for c in CRISIS_EVENTS:
    assert 2 <= len(c.choices) <= 3, f"{c.id} 应有2~3个选择"
    assert c.narrative and c.stage_requirement.startswith("s")
    assert c.favorability_requirement >= 0
    for ch in c.choices:
        assert ch.id in {"a", "b", "c"} and ch.text
print("PASS: 14 事件（7类型×2），id 唯一，选择 2~3 个，字段完整")

# ── 2. 触发引擎：概率计算 ────────────────────────────────
orch = RDEOrchestrator({"enable_rde": True})
eng = orch.crisis_trigger
base = eng.compute_chance({"user_id": "u1", "stage_id": "s3", "favorability": 60, "round": 0})
assert abs(base - 0.02) < 1e-9, f"基础概率应为2%，实际 {base}"
s6 = eng.compute_chance({"user_id": "u1", "stage_id": "s6", "favorability": 60, "round": 0})
assert abs(s6 - 0.025) < 1e-9, f"s6应+0.5% → 2.5%，实际 {s6}"
s10 = eng.compute_chance({"user_id": "u1", "stage_id": "s10", "favorability": 60, "round": 0})
assert abs(s10 - 0.04) < 1e-9, f"s10应+2% → 4%，实际 {s10}"
high_fav = eng.compute_chance({"user_id": "u1", "stage_id": "s6", "favorability": 160, "round": 0})
assert abs(high_fav - 0.035) < 1e-9, f"好感>150应+1% → 3.5%，实际 {high_fav}"
orch.add_cold_penalty("u1", 2)
cold = eng.compute_chance({"user_id": "u1", "stage_id": "s6", "favorability": 60, "round": 0})
assert abs(cold - 0.035) < 1e-9, f"冷落2次应+1% → 3.5%，实际 {cold}"
cap = eng.compute_chance({"user_id": "u1", "stage_id": "s12", "favorability": 200,
                          "round": 10000, "special_date": True})
assert cap <= 0.10 + 1e-9, f"概率上限10%，实际 {cap}"
print("PASS: 概率计算（基础2%/阶段修正/好感/冷落/节日/上限10%）")

# ── 3. 触发引擎：前置检查与命中 ──────────────────────────
orch_off = RDEOrchestrator({})
assert orch_off.check_crisis_trigger("u_off", {"stage_id": "s6", "favorability": 120, "round": 0}) is None
print("PASS: enable_rde=false 不触发")

rng = random.Random(42)
hit = RDEOrchestrator({"enable_rde": True})
hit.crisis_trigger.rng = rng
ev = hit.check_crisis_trigger("u_hit", {"stage_id": "s6", "favorability": 120, "round": 0})
if ev is None:  # seed 下未命中则强制命中一次
    class _Zero:
        def random(self): return 0.0
        def choice(self, seq): return seq[0]
    hit.crisis_trigger.rng = _Zero()
    ev = hit.check_crisis_trigger("u_hit", {"stage_id": "s6", "favorability": 120, "round": 0})
assert ev is not None, "随机命中失败"
assert ev.type in CRISIS_TYPES
print("PASS: 概率命中后写入状态，返回事件")

# 冷却期：触发后下一轮不能再触发
hit.crisis_trigger.rng = _Zero()
assert hit.check_crisis_trigger("u_hit", {"stage_id": "s6", "favorability": 120, "round": 1}) is None
print("PASS: 未解决危机/冷却期内不重复触发")

# 阶段下限：min_stage=s3，s2 不触发
low = RDEOrchestrator({"enable_rde": True})
class _Zero:
    def random(self):
        return 0.0
    def choice(self, seq):
        return seq[0]
low.crisis_trigger.rng = _Zero()
assert low.check_crisis_trigger("u_low", {"stage_id": "s2", "favorability": 50, "round": 0}) is None
print("PASS: 低于 min_stage 不触发")

# ── 4. 类型附加条件 ──────────────────────────────────────
cond = RDEOrchestrator({"enable_rde": True})
class _PickConditional:
    TYPES = {"cold", "secret", "external", "jealousy"}
    def random(self):
        return 0.0
    def choice(self, seq):
        for c in seq:
            if c.type in self.TYPES:
                return c
        return seq[0]
cond.crisis_trigger.rng = _PickConditional()
cond.add_cold_penalty("u_cond", 5)
cond.crisis_store.get("u_cond").total_rounds = 600  # 满足秘密型轮次条件
for _ in range(200):
    ev = cond.check_crisis_trigger("u_cond", {"stage_id": "s8", "favorability": 160,
                                              "round": 0, "mention_other": True,
                                              "special_date": True})
    if ev and ev.type in {"cold", "secret", "external", "jealousy"}:
        break
    cond.crisis_store.clear_active("u_cond")
    cond.crisis_store.get("u_cond").cooldown_until_round = 0
assert ev is not None, "条件满足时应能触发"
assert ev.type in {"cold", "secret", "external", "jealousy"}, f"应触发条件类事件，实际 {ev.type}"
print(f"PASS: 附加条件事件可触发（本次命中 {ev.type}）")

# 未满足条件时回退池仍可触发（无附加条件事件）
plain = RDEOrchestrator({"enable_rde": True})
plain.crisis_trigger.rng = _Zero()
ev2 = plain.check_crisis_trigger("u_plain", {"stage_id": "s6", "favorability": 120, "round": 0})
assert ev2 is not None and ev2.type in {"misunderstanding", "trust", "growth"}
print(f"PASS: 无条件回退池可触发（本次命中 {ev2.type}）")

# ── 5. 选择处理：效果应用与好感缩放 ──────────────────────
orch2 = RDEOrchestrator({"enable_rde": True})
orch2.crisis_trigger.rng = _Zero()
ev3 = orch2.check_crisis_trigger("u_sel", {"stage_id": "s8", "favorability": 160, "round": 0})
assert ev3 is not None
r = orch2.resolve_choice("u_sel", ev3.id, "a", {"char_name": "小雪", "friend_name": "小雅"})
assert isinstance(r, ResolutionResult)
assert r.favorability_delta >= 0 and r.favorability_delta <= 7.6, f"正向应按0.5缩放，实际 {r.favorability_delta}"
assert r.crisis_id == ev3.id
assert "小雪" in r.response_text, f"占位符应替换，实际 {r.response_text}"
assert orch2.get_active_crisis("u_sel") is None, "解决后应清除 active"
assert len(orch2.get_crisis_history("u_sel")) == 1, "历史应记录1条"
print("PASS: 选择处理（好感缩放/占位符/清除状态/历史记录）")

# 错误输入
assert orch2.resolve_choice("u_sel", "nonexist", "a", {}) is None
assert orch2.resolve_choice("u_sel", ev3.id, "z", {}) is None
print("PASS: 错误 crisis_id/choice_id 返回 None")

# ── 6. 阶段倒退与保护期 ──────────────────────────────────
back = RDEOrchestrator({"enable_rde": True})
back.crisis_trigger.rng = _Zero()
ev4 = back.check_crisis_trigger("u_back", {"stage_id": "s8", "favorability": 160, "round": 0})
# 找一个带负向阶段变化的事件（misunderstanding_2 / secret_1 的 C 选项）
target = None
for c in CRISIS_EVENTS:
    if any(ch.stage_delta < 0 for ch in c.choices):
        target = c
        break
assert target is not None, "事件池中应存在阶段倒退选项"
neg_choice = next(ch for ch in target.choices if ch.stage_delta < 0)
back.crisis_store.set_active("u_back", target, 0, target.duration_rounds)
res = back.resolve_choice("u_back", target.id, neg_choice.id, {})
assert res.stage_delta == -1, f"首次倒退应生效 -1，实际 {res.stage_delta}"
assert back.crisis_store.in_protection("u_back"), "倒退后应进入保护期"
# 保护期内再退 → 被钳制
back.crisis_store.set_active("u_back", target, 0, target.duration_rounds)
res2 = back.resolve_choice("u_back", target.id, neg_choice.id, {})
assert res2.stage_delta == 0 and res2.downgrade_protected, \
    f"保护期内应钳制为0并标记，实际 {res2.stage_delta}/{res2.downgrade_protected}"
print("PASS: 阶段倒退（首次-1/保护期钳制0/标记）")

# ── 7. 超时自动解决 ──────────────────────────────────────
auto = RDEOrchestrator({"enable_rde": True})
auto.crisis_store.set_active("u_auto", target, 0, 1)
assert auto.auto_resolve("u_auto", {}) is None, "期限未耗尽不应自动解决"
auto.crisis_store.tick_round("u_auto")
r3 = auto.auto_resolve("u_auto", {})
assert r3 is not None and r3.choice_id == "__auto__"
assert auto.get_active_crisis("u_auto") is None
print("PASS: 超时自动解决（期限判定/结果/清除）")

# ── 8. 危机上下文注入与冷却查询 ──────────────────────────
ctx_sys = RDEOrchestrator({"enable_rde": True})
ctx_sys.crisis_store.set_active("u_ctx", target, 5, 3)
inj = ctx_sys.generate_crisis_context("u_ctx")
assert "【正在进行的关系危机事件】" in inj and "[A]" in inj
assert ctx_sys.generate_crisis_context("u_none") == ""
cd = ctx_sys.get_cooldown("u_ctx", current_round=5)
assert cd["in_cooldown"] and cd["rounds_remaining"] == target.cooldown_rounds
cd2 = ctx_sys.get_cooldown("u_fresh", current_round=0)
assert not cd2["in_cooldown"]
print("PASS: 危机上下文注入/冷却查询/无危机空串")

# ── 9. 叙事阶段完整性（B 依赖 A）─────────────────────────
for sid in ["s1", "s6", "s12", "n4"]:
    d = get_stage_definition(sid)
    assert d is not None and d.style_directive
print("PASS: 阶段叙事定义完整（B 依赖 A 回归）")

print("ALL PASS: RDE Phase B 9 组断言全部通过")
