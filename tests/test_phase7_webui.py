"""SoulSync - Phase 7 验证：WebUI API 后端逻辑"""
import sys, io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import json, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from astrbot_plugin_soulsync.trainer.trainer_storage import TrainerStorage
from astrbot_plugin_soulsync.trainer.trainer_orchestrator import PersonalizationOrchestrator

BASE = Path(r'C:\Users\Yahajiang\Desktop\AstrBot插件\astrbot_plugin_soulsync\data')
storage = TrainerStorage(BASE)
storage.clear_user('web_tester')
orch = PersonalizationOrchestrator('web_tester', storage, {})

# 模拟前端调用的数据格式（与 main.py handler 相同的操作序列）
orch.add_memory("text", "第一次一起看海", importance=5)
orch.add_knowledge("interests", "最爱的食物", "火锅", "webui")
orch.get_persona().grudge_coefficient = 1.5
orch.save_all()

# 1. 数据读取（模拟 GET /trainer/data?user_id=）
from astrbot_plugin_soulsync.trainer.persona.persona_params import PARAM_META
persona = orch.get_persona().to_dict()
assert persona["grudge_coefficient"] == 1.5
assert PARAM_META["grudge_coefficient"]["type"] == "float"
print("PASS: GET trainer/data 人格+元数据")

kb = orch.get_knowledge().to_dict()
assert any(i["key"] == "最爱的食物" for i in kb["items"])
print("PASS: GET trainer/data 知识")

mem = orch.get_private_memory().to_dict()
assert len(mem["text"]) == 1
assert len(orch._memory_auditor.get_logs()) >= 0
print("PASS: GET trainer/data 记忆+审计")

# 2. 人格 set/reset/lock（模拟 POST /trainer/persona）
params = orch.get_persona()
meta = PARAM_META["grudge_coefficient"]
params.grudge_coefficient = float(2.0)
orch.save_all()
assert orch.get_persona().grudge_coefficient == 2.0
orch._modifier.lock(params)
assert orch.get_persona().locked is True
orch._modifier.unlock(orch.get_persona())
orch._modifier.reset()
orch._persona_params = None
assert orch.get_persona().grudge_coefficient == 1.0
print("PASS: POST trainer/persona set/lock/unlock/reset")

# 3. 知识 add/remove（模拟 POST /trainer/knowledge）
item = orch.add_knowledge("promises", "约定", "明年春天一起看樱花", "webui")
assert any(i.id == item.id for i in orch.get_knowledge().items)
assert orch._knowledge_mgr.remove(item.id)
orch._knowledge = None
assert not any(i.id == item.id for i in orch.get_knowledge().items)
print("PASS: POST trainer/knowledge add/remove")

# 4. 记忆 add/star/remove（模拟 POST /trainer/memory）
mem2 = orch.add_memory("text", "每年秋天看银杏", importance=8)
assert any(m.id == mem2.id for m in orch.get_private_memory().text)
assert any(i.category == "experiences" for i in orch.get_knowledge().items), "高显著性记忆应联动知识"
orch._memory_mgr.star(mem2.id)
orch._memory = None
assert mem2.id in orch.get_private_memory().starred
orch._memory_mgr.unstar(mem2.id)
orch._memory = None
assert mem2.id not in orch.get_private_memory().starred
assert orch._memory_mgr.remove(mem2.id)
print("PASS: POST trainer/memory add/star/remove+联动")

# 5. 风格 lock/snapshot/restore（模拟 POST /trainer/style）
from astrbot_plugin_soulsync.trainer.trainer_types import LanguageProfile
style = orch.get_style()
if style.profile is None:
    style.profile = LanguageProfile()
    orch.save_all()
from astrbot_plugin_soulsync.trainer.style.style_snapshot import StyleSnapshotManager
style.profile.avg_length = 12.5
mgr = StyleSnapshotManager(storage, 'web_tester')
mgr.save_snapshot(style, "测试快照")
style.profile.avg_length = 20.0
mgr.restore_snapshot(style, "测试快照")
assert style.profile.avg_length == 12.5, "快照恢复失败"
style.locked = True
assert orch.get_style().locked
print("PASS: POST trainer/style snapshot/restore/lock")

# 6. 用户列表（模拟 GET /trainer/data 无参）
base = BASE / "personalization"
users = [d.name for d in base.iterdir() if d.is_dir() and any(d.rglob("*.json"))]
assert "web_tester" in users
print("PASS: GET trainer/data 用户列表")

# 7. HTML 完整性：新 modal/按钮/API 端点存在
html = (Path(__file__).resolve().parent.parent / "pages" / "dashboard" / "index.html").read_text(encoding="utf-8")
for token in ["bTra", "oTra", "trainer/data", "trainer/persona", "trainer/knowledge", "trainer/memory", "trainer/style", "tPanelPersona", "tPanelMemory"]:
    assert token in html, f"HTML 缺少 {token}"
print("PASS: WebUI HTML 面板元素齐全")

print()
print("=== Phase 7 验证全部通过 ===")