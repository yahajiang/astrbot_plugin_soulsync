"""SoulSync - Phase 6 验证：v2.16 改造 + 回归测试"""
import sys, io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# 1. llm_analyzer: personalization_context 参数
from astrbot_plugin_soulsync.llm_analyzer import LLMAnalyzer
p = LLMAnalyzer.build_analysis_prompt(50, 50, "朋友", {"joy": 60}, "无", "最近对话", "朋友")
assert "[个性化上下文]" not in p
p2 = LLMAnalyzer.build_analysis_prompt(50, 50, "朋友", {"joy": 60}, "无", "最近对话", "朋友", personalization_context="[用户知识库]测试")
assert "[个性化上下文]" in p2 and "[用户知识库]" in p2
print("PASS: llm_analyzer 个性化上下文")

# 2. anniversary: add_external_anniversary
from astrbot_plugin_soulsync.anniversary import AnniversaryManager
import tempfile
tmp = Path(tempfile.mkdtemp())
am = AnniversaryManager(tmp)
ok, msg = am.add_external_anniversary("u1", "一起去滑雪", "12-25", "anniversary")
assert ok, msg
ok2, _ = am.add_external_anniversary("u1", "生日约定", "2027-03-15", "birthday")
assert ok2
ok3, _ = am.add_external_anniversary("u1", "无效日期", "abc", "anniversary")
assert not ok3
today = __import__("datetime").date.today()
evts = am.list_user_anniversaries("u1", today)
assert any(e["name"] == "一起去滑雪" for e in evts)
assert any(e["name"] == "生日约定" and e["month"] == 3 and e["day"] == 15 for e in evts)
print("PASS: anniversary add_external_anniversary (MM-DD + YYYY-MM-DD + 非法)")

# 3. memory_manager: set_event_hook
from astrbot_plugin_soulsync.memory_manager import LongTermMemory
lm = LongTermMemory(tmp, max_events_per_user=10)
calls = []
lm.set_event_hook(lambda uid, ev: calls.append((uid, ev.get("message"))))
lm.add_event("u1", {"message": "重要的事", "significance": 9})
assert len(calls) == 1 and calls[0] == ("u1", "重要的事")
lm.set_event_hook(None)
lm.add_event("u1", {"message": "不通知"})
assert len(calls) == 1
print("PASS: memory_manager 事件钩子")

# 4. orchestrator.on_memory_write: 高显著性事件自动提取为私人记忆
from astrbot_plugin_soulsync.trainer.trainer_storage import TrainerStorage
from astrbot_plugin_soulsync.trainer.trainer_orchestrator import PersonalizationOrchestrator
BASE = Path(r'C:\Users\Yahajiang\Desktop\AstrBot插件\astrbot_plugin_soulsync\data')
storage = TrainerStorage(BASE)
storage.clear_user('test_p6')
orch = PersonalizationOrchestrator('test_p6', storage, {})
orch.on_memory_write({"message": "昨天我搬家了，累坏了", "significance": 8.5})
store = orch.get_private_memory()
assert any(m.content == "昨天我搬家了，累坏了" for m in store.text), "高显著性事件未提取"
orch.on_memory_write({"message": "昨天我搬家了，累坏了", "significance": 9})
assert sum(1 for m in store.text if m.content == "昨天我搬家了，累坏了") == 1, "重复提取"
orch.on_memory_write({"message": "琐事", "significance": 3})
assert len(orch.get_private_memory().text) == 1, "低显著性不应提取"
print("PASS: on_memory_write 高显著性提取 + 去重 + 低显著跳过")

# 5. promises 知识 → 纪念日钩子联动
hook_events = []
def hook(item):
    import re as _re
    m = _re.search(r"(\d{1,2})[-/月](\d{1,2})(?:日|号)?", item.value)
    hook_events.append((item.key, m.group(1), m.group(2) if m else None))
orch.set_anniversary_hook(hook)
orch.add_knowledge("promises", "约定", "每年12月25日一起去滑雪", "auto_capture")
assert len(hook_events) == 1 and hook_events[0] == ("约定", "12", "25")
print("PASS: promises→纪念日钩子日期解析")

# 6. 回归：enable_personalization=false 时 on_each_turn 不执行（main.py 门控逻辑已在代码层验证）
# 验证 orchestrator 模块本身可无配置运行（冷启动）
cold = PersonalizationOrchestrator('test_p6_cold', storage, {})
cold.on_each_turn("你好", {})
assert cold.get_full_injection() is not None
print("PASS: 冷启动回归")

# 7. main.py 语法检查（import 编译）
import py_compile
py_compile.compile(r'C:\Users\Yahajiang\Desktop\AstrBot插件\astrbot_plugin_soulsync\main.py', doraise=True)
py_compile.compile(r'C:\Users\Yahajiang\Desktop\AstrBot插件\astrbot_plugin_soulsync\memory_manager.py', doraise=True)
py_compile.compile(r'C:\Users\Yahajiang\Desktop\AstrBot插件\astrbot_plugin_soulsync\llm_analyzer.py', doraise=True)
py_compile.compile(r'C:\Users\Yahajiang\Desktop\AstrBot插件\astrbot_plugin_soulsync\anniversary.py', doraise=True)
print("PASS: main.py / memory_manager.py / llm_analyzer.py / anniversary.py 编译通过")

print()
print("=== Phase 6 验证全部通过 ===")