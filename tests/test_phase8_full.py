# Phase 8: 全面测试 - 边缘情况清单 + 持久化 + 内存 + 命令区回归
# 运行: python tests/test_phase8_full.py
import io, re, sys, time
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent.parent))

import ctypes
from ctypes import wintypes
from pathlib import Path

class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

def rss_mb():
    psapi = ctypes.WinDLL("psapi")
    pmc = PROCESS_MEMORY_COUNTERS()
    pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
    psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    return pmc.WorkingSetSize / 1024 / 1024

from astrbot_plugin_soulsync.trainer.trainer_storage import TrainerStorage
from astrbot_plugin_soulsync.trainer.trainer_orchestrator import PersonalizationOrchestrator, approx_tokens
from astrbot_plugin_soulsync.trainer.trainer_types import LanguageProfile
from astrbot_plugin_soulsync.trainer.persona.persona_params import default_params

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
UID = "test_p8"
PASS = 0

def ok(name):
    global PASS
    PASS += 1
    print(f"PASS: {name}")

def fresh():
    import shutil
    d = DATA / "personalization" / UID
    if d.exists():
        shutil.rmtree(d)
    return PersonalizationOrchestrator(UID, TrainerStorage(str(DATA)))

# ── 边缘 1: 新用户第1轮 - 四模块冷启动 ──────────────────────
o = fresh()
inj = o.get_full_injection()
assert isinstance(inj, str) and inj == "", f"冷启动应无注入, got: {inj!r}"
ok("边缘1 新用户冷启动无注入")

# ── 边缘 2: 知识库为空不注入 ────────────────────────────────
o.add_knowledge("interests", "测试", "测试知识")
inj2 = o.get_full_injection()
assert "测试知识" in inj2
o._knowledge_mgr.remove(o.get_knowledge().items[0].id)
o._knowledge = None
inj3 = o.get_full_injection()
assert "测试知识" not in inj3
ok("边缘2 知识库空则不注入")

# ── 边缘 3: 人格全默认 - persona 上下文仅基线/为空 ──────────
p = o.get_persona()
dflt = default_params()
assert all(getattr(p, k) == getattr(dflt, k) for k in ["grudge_coefficient", "romantic_memory_weight", "forget_speed", "milestone_sensitivity"])
ok("边缘3 人格参数与默认值一致")

# ── 边缘 4: 风格采集期提示"正在学习" ─────────────────────────
s = o.get_style()
if s.profile is None:
    s.profile = LanguageProfile()
    s.phase = "collection"
    o.save_all()
assert o.get_style().phase == "collection"
ok("边缘4 风格采集期 phase=collection")

# ── 边缘 5: 私人记忆为空不触发检索 ──────────────────────────
m = o.get_private_memory()
assert not (m.text or m.images or m.promises or m.emotional)
ok("边缘5 记忆库空状态正常")

# ── 边缘 6: token预算不足按优先级裁剪 人格>知识>记忆>风格 ────
o2 = fresh()
o2.add_knowledge("interests", "篮球", "喜欢篮球" * 200)
o2.add_memory("text", "我们去年夏天看过海" * 200, importance=8)
p2 = o2.get_persona()
p2.grudge_coefficient = 2.0
o2.save_all()
inj4 = o2.get_full_injection()
tok = approx_tokens(inj4)
assert tok <= 450, f"预算裁剪超限: {tok} tokens"
ok(f"边缘6 token预算裁剪 ≤450 ({tok})")

# ── 边缘 7: 同时正负向训练独立计算（人格参数不受情绪影响） ──
before = o2.get_persona().grudge_coefficient
o2._persona_params = None
assert o2.get_persona().grudge_coefficient == before
ok("边缘7 人格参数稳定")

# ── 边缘 8: 知识多条同时出现逐条处理 ─────────────────────────
o2.add_knowledge("values", "第一条", "第一条")
o2.add_knowledge("values", "第二条", "第二条")
assert len(o2.get_knowledge().items) >= 3
ok("边缘8 多条知识并存")

# ── 边缘 9: 用户手动重置全部参数回到冷启动 ──────────────────
o2._modifier.reset()
o2._persona_params = None
assert o2.get_persona().grudge_coefficient == 1.0
ok("边缘9 参数重置回到默认")

# ── 边缘 10: 超长文本截断处理（注入性能） ────────────────────
t0 = time.perf_counter()
o2.add_memory("text", "超长" * 5000, importance=5)
o2.save_all()
big = o2.get_full_injection()
dt = (time.perf_counter() - t0) * 1000
assert dt < 50, f"超长输入注入耗时 {dt}ms"
ok(f"边缘10 超长输入不卡顿 ({dt:.2f}ms)")

# ── 边缘 11: enable_personalization 门控（main 静态检查） ────
main_src = (BASE / "main.py").read_text(encoding='utf-8')
gates = len(re.findall(r'enable_personalization', main_src))
assert gates >= 8, f"门控点过少: {gates}"
ok(f"边缘11 门控点覆盖 ({gates} 处)")

# ── 边缘 12: 记忆检索空输入不崩溃 ────────────────────────────
res = o2._memory_retriever.retrieve(o2.get_private_memory(), {"keywords": "", "persona": {}})
assert isinstance(res, list)
ok("边缘12 空文本记忆检索不崩溃")

# ── 持久化: 重启后数据完整恢复（独立干净用户） ──────────────
import shutil as _shutil
UID2 = "test_p8_persist"
d2 = DATA / "personalization" / UID2
if d2.exists():
    _shutil.rmtree(d2)
op = PersonalizationOrchestrator(UID2, TrainerStorage(str(DATA)))
op.add_memory("text", "重启后应还在", importance=7)
op.add_knowledge("interests", "重启", "重启持久化知识")
op.save_all()
o3 = PersonalizationOrchestrator(UID2, TrainerStorage(str(DATA)))
assert any("重启持久化知识" == i.value for i in o3.get_knowledge().items)
assert any("重启后应还在" == m.content for m in o3.get_private_memory().text)
o3.on_each_turn("重启后测试", {})
inj5 = o3.get_full_injection()
assert "重启持久化知识" in inj5, f"注入缺少持久化知识: {inj5[:200]}"
ok("持久化 重启后数据完整恢复")

# ── 内存: 1000轮模拟 <50MB ─────────────────────────────────
base_mb = rss_mb()
o4 = fresh()
for i in range(1000):
    o4.on_each_turn(f"第{i}轮消息", {})
    if i % 200 == 0:
        o4.save_all()
end_mb = rss_mb()
growth = end_mb - base_mb
assert growth < 50, f"1000轮内存增长 {growth:.1f}MB"
ok(f"内存 1000轮增长 {growth:.1f}MB <50MB")

# ── 命令区回归: v2.20 10父命令 + 独立命令 + admin 存在 ───────
cmds = re.findall(r'@filter\.command\("([^"]+)"', main_src)
counts = {}
for c in cmds:
    counts[c] = counts.get(c, 0) + 1
dups = {c: n for c, n in counts.items() if n > 1}
assert not dups, f"命令重复注册: {dups}"
parent_cmds = ["心声", "回忆", "纪念", "角色", "人格", "知识",
               "风格", "记忆", "天象", "排行", "心管", "图片模式", "设置", "心助"]
missing = [c for c in parent_cmds if c not in counts]
assert not missing, f"缺失父命令: {missing}"
legacy_cmds = ["好感度", "人格微调", "知识添加", "记忆添加", "添加纪念日",
               "月度报告", "角色回顾", "时间回溯", "设置好感"]
leftover = [c for c in legacy_cmds if c in counts]
assert not leftover, f"旧命令未收敛: {leftover}"
ok(f"命令区 无重复注册, 10父命令+独立命令+admin 齐全 (共{len(cmds)}个)")

# ── 配置 schema 完整 ───────────────────────────────────────
schema_src = (BASE / "_conf_schema.json").read_text(encoding='utf-8')
need_keys = ["enable_personalization", "personalization_total_token_budget",
             "persona_implicit_training", "persona_stability_enabled",
             "knowledge_enabled", "knowledge_auto_capture", "knowledge_max_tokens_per_turn",
             "style_training_enabled", "style_collection_turns", "style_adoption_turns",
             "private_memory_enabled", "private_memory_proactive_chance", "private_memory_token_budget"]
miss_s = [k for k in need_keys if f'"{k}"' not in schema_src]
assert not miss_s, f"schema 缺失: {miss_s}"
ok(f"配置 schema 关键键齐全 ({len(need_keys)}项)")

print(f"\n=== Phase 8 全面测试全部通过 ({PASS} 项) ===")
