"""SoulSync - Phase 5.5 性能测试：四模块同时运行延迟<50ms"""
import sys, io;
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from astrbot_plugin_soulsync.trainer.trainer_storage import TrainerStorage
from astrbot_plugin_soulsync.trainer.trainer_orchestrator import PersonalizationOrchestrator

BASE = Path(r'C:\Users\Yahajiang\Desktop\AstrBot插件\astrbot_plugin_soulsync\data')
storage = TrainerStorage(BASE)
storage.clear_user('test_perf')
orch = PersonalizationOrchestrator('test_perf', storage, {})

for i in range(5):
    orch.add_memory("text", f"测试记忆{i}：用户喜欢分享日常琐事", importance=6)
    orch.add_knowledge("interests", "测试", f"用户喜欢话题{i}", "batch_import")

msg = "我喜欢火锅，今天和朋友去吃了，很开心"
latencies = []
for _ in range(200):
    ctx = {}
    t0 = time.perf_counter()
    orch.on_each_turn(msg, ctx)
    orch.get_full_injection()
    latencies.append((time.perf_counter() - t0) * 1000)

avg = sum(latencies) / len(latencies)
p95 = sorted(latencies)[int(len(latencies) * 0.95)]
print(f"平均延迟: {avg:.2f}ms, P95: {p95:.2f}ms")
assert avg < 50, f"平均延迟 {avg:.2f}ms 超限"
assert p95 < 100, f"P95 延迟 {p95:.2f}ms 超限"
print("PASS: 四模块同时运行平均延迟 < 50ms")
print("=== Phase 5.5 性能测试通过 ===")