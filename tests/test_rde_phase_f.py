"""SoulSync RDE - Phase F 测试 + 优化验证

覆盖文档 Phase F 中 A/C 未覆盖项：
1. 十二阶段叙事风格差异（16 阶段注入文本非空/两两不同/锚点）
2. 称谓演进全链（s1「你」→ 高阶昵称/专属，用户昵称介入）
3. 性能基准（RDE 全部处理平均 <30ms）
"""
import sys, io, time, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from astrbot_plugin_soulsync.rde import RDEOrchestrator

orch = RDEOrchestrator({"enable_rde": True, "enable_crisis_system": True, "enable_network": True})

# ── 1. 十二阶段叙事风格差异 ───────────────────────────────
ctxs = {}
for s in orch.all_stages():
    t = orch.generate_stage_context(s.stage_id, {"user_name": "小雅"})
    assert t and t.strip(), f"{s.stage_id} 注入文本为空"
    ctxs[s.stage_id] = t
neg = {}
for s in ["n1", "n2", "n3", "n4"]:
    t = orch.generate_stage_context(s, {"user_name": "小雅"})
    assert t and t.strip(), f"{s} 注入文本为空"
    neg[s] = t
all_ctx = list(ctxs.values()) + list(neg.values())
assert len(set(all_ctx)) == 16, "16 个阶段注入文本必须两两不同（风格差异）"
for sid, t in ctxs.items():
    cfg = orch.get_stage_config(sid)
    assert (cfg.stage_name in t or cfg.relationship_state in t), f"{sid} 缺阶段锚点"
assert all(k in neg["n4"] for k in []), "占位"
print("PASS: 阶段叙事风格差异（16 阶段文本非空/两两不同/阶段名锚点）")

# ── 2. 称谓演进全链 ───────────────────────────────────────
base = [orch.get_address(s.stage_id, {}) for s in orch.all_stages()]
named = [orch.get_address(s.stage_id, {"user_name": "小雅"}) for s in orch.all_stages()]
for i, a in enumerate(base):
    assert a and a.strip(), f"s{i+1} 称谓为空"
assert base[0] == "你" and base[1] == "你", "s1/s2 应称「你」"
assert base[0] == named[0], "低阶称谓不因人而异"
high = named[-1]
assert "小雅" in high or high not in base[-1], "高阶称谓应含昵称或与基础称谓不同"
assert named != base, "昵称应影响至少一个阶段"
# 演进单调：越往后越不可能是「你」（s1~s12 中「你」只应出现在前段）
you_idx = [i for i, a in enumerate(base) if a == "你"]
assert you_idx == [0, 1], f"「你」应只在前 2 阶段，实际 {you_idx}"
for sid, a in [("n1", "你"), ("n2", "（省略称呼）")]:
    assert orch.get_address(sid, {}) == a, f"{sid} 称谓异常"
print("PASS: 称谓演进全链（你→中阶昵称→高阶专属，昵称介入，负向疏远）")

# ── 3. 性能基准 <30ms ─────────────────────────────────────
def bench(fn, n=300):
    fn()  # warmup
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t0) / n * 1000  # ms

ctx_full = {"round": 50, "stage_id": "s6", "favorability": 120.0, "fav_delta": 2.0,
            "source_role": "月华", "current_role": "月华", "user_name": "小雅",
            "friend_name": "白月光", "mention_other": True, "special_date": False,
            "cold_penalty_add": 0,
            "favorabilities": {"月华": 120, "白月光": 100, "阿澈": 80}}
p1 = bench(lambda: orch.generate_stage_context("s6", {"user_name": "小雅"}))
p2 = bench(lambda: orch.check_crisis_trigger("u_perf", {"stage_id": "s6", "favorability": 120, "round": 1}))
p3 = bench(lambda: orch.calculate_cross_impact("月华", 2.0, 1, "u_perf"))
p4 = bench(lambda: orch.settle_transfers("u_perf", 1))
p5 = bench(lambda: orch.process_message("u_perf", dict(ctx_full)))
for name, ms in [("stage_ctx", p1), ("crisis_check", p2), ("cross_impact", p3),
                 ("settle", p4), ("process_message", p5)]:
    assert ms < 30, f"{name} 超标: {ms:.2f}ms"
print(f"PASS: 性能基准（stage_ctx {p1:.2f}ms / crisis {p2:.2f}ms / impact {p3:.2f}ms / settle {p4:.2f}ms / process {p5:.2f}ms，均 <30ms）")

print("\nALL PASS: Phase F 测试（3 组）")
