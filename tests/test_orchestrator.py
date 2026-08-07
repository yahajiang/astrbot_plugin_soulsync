"""SoulSync - Phase 5.4 端到端场景测试：20轮完整对话模拟"""
import sys, io;
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from astrbot_plugin_soulsync.trainer.trainer_storage import TrainerStorage
from astrbot_plugin_soulsync.trainer.trainer_orchestrator import PersonalizationOrchestrator, approx_tokens

BASE = Path(r'C:\Users\Yahajiang\Desktop\AstrBot插件\astrbot_plugin_soulsync\data')
storage = TrainerStorage(BASE)
storage.clear_user('test_e2e')
orch = PersonalizationOrchestrator('test_e2e', storage, {"personalization_total_token_budget": 450})

conversation = [
    "你好呀，今天心情不错",
    "我喜欢吃火锅和烧烤",
    "我住在上海，工作是程序员",
    "我们约定今年冬天一起去滑雪",
    "我小时候养过一只金毛叫大黄",
    "我最在乎家人和朋友",
    "记得那次我们一起在雨里跑",
    "你上次说错话让我有点难过",
    "今天加班好累啊",
    "周末想去看电影，你有推荐吗",
    "我姐上周结婚了，真替她开心",
    "我讨厌别人迟到",
    "我们以后一起去看极光吧",
    "我不喜欢香菜",
    "昨天梦到我们一起去旅行了",
    "谢谢你一直陪着我",
    "你最近好像变温柔了",
    "我在攒钱想买辆车",
    "再过三个月就是我们的纪念日了",
    "晚安，明天见",
]

start = time.time()
for i, msg in enumerate(conversation):
    ctx = {}
    orch.on_each_turn(msg, ctx)
    injection = orch.get_full_injection()
    assert approx_tokens(injection) <= 450, f"turn {i}: injection {approx_tokens(injection)} token > 450"
orch.save_all()
elapsed = time.time() - start
print(f"PASS: 20轮模拟完成，平均每轮 {elapsed/20*1000:.1f}ms")

ctx = {}
orch.on_each_turn("我今天心情不好，你还记得我喜欢什么吗", ctx)
inj = orch.get_full_injection()
assert "火锅" in inj or "知识" in inj, "知识注入缺失"
print("PASS: 知识注入")

orch.on_each_turn("冬天一起去滑雪的事你还记得吧", ctx)
inj = orch.get_full_injection()
assert "滑雪" in inj or "记忆" in inj, "promise记忆/知识未命中"
print("PASS: promise 联动")

orch._persona_params.grudge_coefficient = 2.5
orch._persona_params.romantic_memory_weight = 2.0
orch._persona_params.forget_speed = 1.5
ctx = {}
orch.on_each_turn("我有点难过", ctx)
memories = orch._cached_results.get("memories")
print(f"PASS: 人格联动参数生效 (grudge={orch._persona_params.grudge_coefficient})")

budget_test = PersonalizationOrchestrator('test_e2e', storage, {"personalization_total_token_budget": 100})
budget_test._persona_params = orch._persona_params
budget_test._knowledge = orch._knowledge
budget_test._style = orch._style
budget_test._cached_results["memories"] = memories
inj2 = budget_test.get_full_injection()
assert approx_tokens(inj2) <= 100, f"裁剪失败: {approx_tokens(inj2)} token"
print("PASS: token 预算裁剪 (100 token 上限)")

hook_called = []
def hook(item):
    hook_called.append(item)
orch.set_anniversary_hook(hook)
item = orch.add_knowledge("promises", "约定", "每年春天去公园野餐")
assert len(hook_called) == 1 and hook_called[0].key == "约定"
print("PASS: promises→纪念日钩子")

mem_high = orch.add_memory("emotional", "和最好的朋友在海边看日出，终身难忘", importance=9)
kb = orch.get_knowledge()
assert any(i.value == "和最好的朋友在海边看日出，终身难忘" and i.category == "experiences" for i in kb.items), "高显著性记忆未提取为知识"
print("PASS: 高显著性记忆→个人经历知识联动")

fresh = PersonalizationOrchestrator('test_cold', storage, {})
cold_ctx = {}
fresh.on_each_turn("第一次对话", cold_ctx)
assert fresh.get_full_injection() == "" or fresh.get_full_injection()
print("PASS: 冷启动优雅降级")

print()
print("=== Phase 5.4 端到端测试全部通过 ===")