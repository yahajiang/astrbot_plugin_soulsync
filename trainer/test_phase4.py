import sys, io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import sys; sys.path.insert(0, r'C:\Users\Yahajiang\Desktop\AstrBot插件\astrbot_plugin_soulsync\..')
from pathlib import Path
from astrbot_plugin_soulsync.trainer.trainer_storage import TrainerStorage
from astrbot_plugin_soulsync.trainer.memory.private_memory_manager import PrivateMemoryManager
from astrbot_plugin_soulsync.trainer.memory.private_memory_retriever import PrivateMemoryRetriever
from astrbot_plugin_soulsync.trainer.memory.private_memory_auditor import MemoryAuditor
from astrbot_plugin_soulsync.trainer.memory.private_memory_export import PrivateMemoryExport

storage = TrainerStorage(Path(r'C:\Users\Yahajiang\Desktop\AstrBot插件\astrbot_plugin_soulsync\data'))
mgr = PrivateMemoryManager(storage, 'test_m4')
retriever = PrivateMemoryRetriever()
auditor = MemoryAuditor(storage, 'test_m4')
export = PrivateMemoryExport(storage, 'test_m4')

mem = mgr.add('text', '第一次一起淋雨', tags=['浪漫', '雨天'], mood='幸福')
assert mem.id.startswith('pm_')
print('PASS: add text memory')

mem2 = mgr.add('promise', '每年秋天看银杏', promise_due='2027-10-01')
assert mem2.type == 'promise'
print('PASS: add promise memory')

mem3 = mgr.add('emotional', '那天你安慰了我', emotion_tags=['温暖'], intensity=8.0)
assert mem3.intensity == 8.0
print('PASS: add emotional memory')

store = mgr.get()
all_mems = mgr.all_memories(store)
assert len(all_mems) == 3
print('PASS: get all memories')

mgr.star(mem.id)
store2 = mgr.get()
assert mem.id in store2.starred
print('PASS: star memory')

mgr.mark_sensitive(mem2.id)
print('PASS: mark sensitive')

context = {"keywords": "淋雨"}
results = retriever.retrieve(store2, context, max_items=5)
assert len(results) >= 1
assert results[0].id == mem.id
print('PASS: retrieve with context')

mgr.remove(mem3.id)
store3 = mgr.get()
assert len(mgr.all_memories(store3)) == 2
print('PASS: remove memory')

fmt = retriever.format_for_llm([mem, mem2])
assert '私人记忆' in fmt
print('PASS: format_for_llm')

auditor.log(mem.id, 'topic', 'user mentioned rain')
logs = auditor.get_logs()
assert len(logs) >= 1
assert logs[-1]['memory_id'] == mem.id
print('PASS: audit log')

json_str = export.export()
data = export.import_data(json_str)
assert data['ok']
print('PASS: export/import')

from astrbot_plugin_soulsync.trainer.trainer_orchestrator import PersonalizationOrchestrator
orch = PersonalizationOrchestrator('test_m4', storage)
orch.on_each_turn('今天又下雨了，记得那次淋雨', {})
injection = orch.get_full_injection()
assert '私人记忆' in injection or '记忆' in injection
print('PASS: orchestrator memory injection')

print()
print('=== All Phase 4 tests passed ===')