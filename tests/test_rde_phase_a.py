"""SoulSync RDE - Phase A 单模块测试：阶段叙事/称谓体系/跃迁处理/调度器骨架"""
import sys, io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from astrbot_plugin_soulsync.rde import (
    RDEOrchestrator, STAGE_DEFINITIONS, NEGATIVE_STAGE_DEFINITIONS,
    get_stage_definition, TransitionEvent,
)
from astrbot_plugin_soulsync.rde.narrative.stage_definitions import stage_id_from_index

orch = RDEOrchestrator({"enable_rde": True})
print("RDE Orchestrator 已初始化 (enabled)", orch.enabled)

# ── 1. 配置完整性：12正 + 4负 ─────────────────────────────
assert len(STAGE_DEFINITIONS) == 12, f"正向阶段应为12，实际 {len(STAGE_DEFINITIONS)}"
assert len(NEGATIVE_STAGE_DEFINITIONS) == 4, f"负向阶段应为4，实际 {len(NEGATIVE_STAGE_DEFINITIONS)}"
thresholds = [s.threshold for s in STAGE_DEFINITIONS]
assert thresholds == [15, 35, 55, 75, 95, 115, 135, 152, 168, 180, 185, 200], thresholds
neg_thr = [s.threshold for s in NEGATIVE_STAGE_DEFINITIONS]
assert neg_thr == [-15, -40, -70, -100], neg_thr
ids = [s.stage_id for s in STAGE_DEFINITIONS]
assert ids == [f"s{i}" for i in range(1, 13)], ids
for s in NEGATIVE_STAGE_DEFINITIONS:
    assert s.stage_id in {"n1", "n2", "n3", "n4"}, s.stage_id
print("PASS: 12正+4负阶段配置完整，阈值对齐 15~200 / -15~-100")

# ── 2. 阶段6 完整模板锚点 ────────────────────────────────
s6 = get_stage_definition("s6")
assert s6 and s6.stage_name == "暧昧萌动"
assert "暧昧萌动" in s6.style_directive
assert "宝贝" in s6.address_config["examples"]
assert "老婆" in s6.address_config["avoid"], "暧昧期应避免正式恋人称呼"
assert s6.transition_trigger and "宝贝" in s6.transition_trigger
print("PASS: 阶段6 完整模板（名称/指令/称谓/触发文案）")

# ── 3. stage_id 映射 ─────────────────────────────────────
assert stage_id_from_index(0) == "s1"
assert stage_id_from_index(11) == "s12"
assert stage_id_from_index(99) == "s12"   # 越界钳制
assert stage_id_from_index(0, "😐 冷淡") == "n1"
assert stage_id_from_index(0, "🔥 敌对") == "n4"
assert stage_id_from_index(0, "未知标签") == "n1"  # 未知负标签兜底
print("PASS: 索引→stage_id 映射（正向/负向/越界/兜底）")

# ── 4. 注入器：上下文生成 ────────────────────────────────
ctx = orch.generate_stage_context("s6", {"user_name": "小雅"})
assert "【当前关系阶段】" in ctx
assert "对方姓名：小雅" in ctx
assert "暧昧萌动" in ctx
assert "禁忌：" in ctx
unknown = orch.generate_stage_context("s99", {})
assert unknown == "", "未知阶段应返回空注入"
print("PASS: 阶段上下文注入（含姓名/模板/禁忌/未知兜底）")

# ── 5. 称谓体系 ──────────────────────────────────────────
addr = orch.address
assert addr.get_address("s1", {}) == "你"
assert addr.get_address("s2", {}) == "你"
v3 = addr.get_address("s3", {})
assert v3 in {"你啊", "傻瓜"}, v3
v5 = addr.get_address("s5", {"user_name": "小雅"})
assert "小雅" in v5 or v5 in {"傻瓜", "笨蛋", "亲爱的"}, v5
assert addr.get_address("n1", {}) == "你"
assert addr.get_address("n2", {}) == "（省略称呼）"
assert addr.get_address("n3", {}) == "那个人"
assert addr.get_address("n4", {}) == "（不愿提及名字，生硬地省略称呼）"
print("PASS: 称谓体系（低阶用你/中阶昵称/高阶专属/负向疏远化）")

# ── 6. 跃迁/退行 ─────────────────────────────────────────
ev = orch.check_transition("s5", "s6")
assert isinstance(ev, TransitionEvent) and ev.kind == "upgrade"
assert "暧昧萌动" in ev.narrative_lines[-1] or "暧昧萌动" in "\n".join(ev.narrative_lines)
assert orch.recent_transition_for("s6") is not None, "跃迁应记录 recent_transition"
ev_down = orch.check_transition("s6", "n1")
assert ev_down and ev_down.kind == "downgrade", "正向→负向应为退行"
assert "少了点什么" in ev_down.narrative_lines[0]
ev_same = orch.check_transition("s3", "s3")
assert ev_same is None, "同阶段不应产生事件"
ev_neg_down = orch.check_transition("n1", "n2")
assert ev_neg_down and ev_neg_down.kind == "downgrade", "负向加深应为退行"
ev_by_index = orch.check_transition_by_index("s6", 3)
assert ev_by_index and ev_by_index.new_stage == "s4" and ev_by_index.kind == "downgrade"
print("PASS: 跃迁/退行判定（升级/正向退行/同阶段/负向加深/索引入口）")

# ── 7. 禁用模式 ──────────────────────────────────────────
orch_off = RDEOrchestrator({})
assert not orch_off.enabled
assert orch_off.generate_stage_context("s6", {}) == "", "禁用时不应注入"
assert orch_off.check_transition("s5", "s6") is None
assert orch_off.get_address("s6", {}) == "你"
print("PASS: enable_rde=false 时全部接口静默降级")

# ── 8. 描述与命令展示 ────────────────────────────────────
desc = orch.get_stage_description("s6")
assert "暧昧萌动" in desc and "对话风格" in desc
assert orch.get_stage_description("s99") == "未知阶段"
assert len(orch.all_stages()) == 12
print("PASS: 阶段描述与命令展示接口")

print("ALL PASS: RDE Phase A 8 组断言全部通过")
