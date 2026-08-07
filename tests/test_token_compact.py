"""SoulSync Token 节省优化 - P0 骨架压缩测试

覆盖：
1. 情感上下文骨架行 [情] 格式（好感/亲密/阶段/维度/势头）
2. 自定义称谓优先行仍保留
3. 张力行骨架 [张] 格式
4. TPD 环境注入去冗余词
5. 感知块 [时] 前缀与骨架格式
"""
import sys
import types
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# ── stub astrbot 依赖（main.py 顶部导入需要）────────────
_astrbot = types.ModuleType("astrbot")
_astrbot_api = types.ModuleType("astrbot.api")
_astrbot.api = _astrbot_api
_astrbot_api.AstrBotConfig = dict
_astrbot_api.logger = SimpleNamespace(debug=lambda *a, **k: None,
                                      info=lambda *a, **k: None,
                                      warning=lambda *a, **k: None,
                                      error=lambda *a, **k: None)
_astrbot.event = types.ModuleType("astrbot.event")
_astrbot.event.filter = SimpleNamespace(
    command=lambda *a, **k: (lambda f: f),
    on_llm_request=lambda *a, **k: (lambda f: f),
    on_llm_response=lambda *a, **k: (lambda f: f),
    on_decorating_result=lambda *a, **k: (lambda f: f),
    on_message=lambda *a, **k: (lambda f: f),
    command_group=lambda *a, **k: (lambda f: f),
)
_astrbot.event.AstrMessageEvent = object
_astrbot.event.filter.PermissionType = SimpleNamespace(ADMIN="ADMIN", GROUP_ADMIN="GROUP_ADMIN")
_astrbot.api.event = _astrbot.event
_astrbot.star = types.ModuleType("astrbot.star")
_astrbot.star.Context = object
_astrbot.star.Star = object
_astrbot.api.star = _astrbot.star
_astrbot.web = types.ModuleType("astrbot.web")
_astrbot.web.error_response = lambda *a, **k: None
_astrbot.web.json_response = lambda *a, **k: None
_astrbot.web.request = lambda *a, **k: None
_astrbot.api.web = _astrbot.web
_astrbot.core = types.ModuleType("astrbot.core")
_astrbot.core.agent = types.ModuleType("astrbot.core.agent")
_astrbot.core.agent.message = types.ModuleType("astrbot.core.agent.message")
_astrbot.core.agent.message.TextPart = object
_astrbot.core.utils = types.ModuleType("astrbot.core.utils")
_astrbot.core.utils.astrbot_path = types.ModuleType("astrbot.core.utils.astrbot_path")
_astrbot.core.utils.astrbot_path.get_astrbot_data_path = lambda: "."
_astrbot.api.message = _astrbot.core.agent.message
_astrbot.api.event.filter = _astrbot.event.filter
_astrbot.event.filter.PermissionType = SimpleNamespace(ADMIN="ADMIN", GROUP_ADMIN="GROUP_ADMIN")
_astrbot.api.event.filter.PermissionType = _astrbot.event.filter.PermissionType
sys.modules["astrbot"] = _astrbot
sys.modules["astrbot.api"] = _astrbot_api
sys.modules["astrbot.api.event"] = _astrbot.event
sys.modules["astrbot.api.star"] = _astrbot.star
sys.modules["astrbot.api.web"] = _astrbot.web
sys.modules["astrbot.api.message"] = _astrbot.core.agent.message
sys.modules["astrbot.event"] = _astrbot.event
sys.modules["astrbot.star"] = _astrbot.star
sys.modules["astrbot.web"] = _astrbot.web
sys.modules["astrbot.core"] = _astrbot.core
sys.modules["astrbot.core.agent"] = _astrbot.core.agent
sys.modules["astrbot.core.agent.message"] = _astrbot.core.agent.message
sys.modules["astrbot.core.utils"] = _astrbot.core.utils
sys.modules["astrbot.core.utils.astrbot_path"] = _astrbot.core.utils.astrbot_path

from astrbot_plugin_soulsync.emotion_engine import EmotionProfile
from astrbot_plugin_soulsync.penalty_reward import BehaviorProfile
from astrbot_plugin_soulsync.tpd.env_injector import build_environment_info
from astrbot_plugin_soulsync import main as main_mod
from astrbot_plugin_soulsync.main import should_inject_env, should_inject_static


def make_owner(config=None):
    cfg = {
        "global_privacy_level": 1,
        "enable_stage_styles": True,
        "enable_emotion_contagion": True,
        "tension_threshold": 85.0,
        "enable_attitude_system": True,
        "anti_manipulation_prompt": True,
        "enable_time_perception": True,
        "enable_holiday_perception": True,
        "enable_lunar_perception": True,
        "enable_weather_perception": True,
        "anniv_inject_context": True,
        "holiday_country": "CN",
    }
    if config:
        cfg.update(config)
    owner = SimpleNamespace(
        config=cfg,
        timezone=None,
        relationship_manager=SimpleNamespace(
            custom_info=lambda uid: {"attitude": "", "relationship": ""}
        ),
        long_memory=SimpleNamespace(get_summary=lambda uid: ""),
        anniversary_manager=SimpleNamespace(get_today_events=lambda uid, d: []),
    )
    owner._get_stage_label = main_mod.SoulSyncPro._get_stage_label.__get__(owner)
    owner._get_stage_style = main_mod.SoulSyncPro._get_stage_style.__get__(owner)
    owner._get_negative_stage_label = main_mod.SoulSyncPro._get_negative_stage_label.__get__(owner)
    owner._emotion_short_dims = main_mod.SoulSyncPro._emotion_short_dims
    return owner


def build_ctx(profile, bp=None, config=None):
    return main_mod.SoulSyncPro._build_emotion_context(make_owner(config), profile, bp)


# ── 1. 骨架行格式 ─────────────────────────────────────────
def test_emotion_skeleton_line():
    prof = EmotionProfile(user_id="u1", favorability=75.3, intimacy=58.4,
                          stage_index=5, tension=0.0)
    prof.emotions.update({"joy": 81, "trust": 72, "anticipation": 65,
                          "sadness": 12, "anger": 9})
    bp = BehaviorProfile(user_id="u1", current_streak_count=3,
                         current_streak_type="positive")
    ctx = build_ctx(prof, bp)
    assert "[情]❤+75.3💜58" in ctx, ctx
    assert "悦81" in ctx and "信72" in ctx and "期65" in ctx, "应含 top3 高维"
    assert "势+3" in ctx, "应含势头缩写"
    assert "悲12" not in ctx, "低于阈值的维度不应注入"
    assert "怒9" not in ctx
    assert "/200" not in ctx and "亲密度：" not in ctx, "冗余描述应被移除"


# ── 2. 自定义称谓优先仍保留 ───────────────────────────────
def test_preferred_address_kept():
    prof = EmotionProfile(user_id="u1", favorability=100.0, intimacy=66.0,
                          stage_index=11, preferred_address="哥哥")
    ctx = build_ctx(prof)
    assert "「哥哥」" in ctx and "不得擅自换" in ctx, ctx


# ── 3. 张力骨架 ───────────────────────────────────────────
def test_tension_skeleton():
    prof = EmotionProfile(user_id="u1", favorability=30.0, intimacy=43.0,
                          stage_index=2, tension=88.0)
    ctx = build_ctx(prof)
    assert "[张]88% " in ctx, ctx
    assert "一触即发" in ctx, "bursting 提示应存在"


# ── 4. 长度上限（无记忆无态度时）─────────────────────────
def test_length_budget():
    prof = EmotionProfile(user_id="u1", favorability=50.0, intimacy=50.0, stage_index=3)
    ctx = build_ctx(prof)
    assert len(ctx) < 260, f"骨架化后应显著缩短: {len(ctx)} 字"


# ── 5. TPD 环境注入去冗余词 ──────────────────────────────
def test_environment_skeleton():
    env = {
        "weather": "晴", "weather_emoji": "☀️", "temperature": 24,
        "season": "春", "solar_term": "清明", "solar_term_today": True,
        "moon_phase": "蛾眉月", "moon_emoji": "🌒",
    }
    text = build_environment_info(env, {"joy": 1.5})
    assert text.startswith("[环境]"), text
    assert "天气:" not in text and "温度:" not in text and "季节:" not in text, text
    assert "节气:" not in text and "月相:" not in text, text
    assert "☀️晴" in text and "24℃" in text and "清明" in text
    assert "喜悦↑1.5" in text


# ── 6. 感知块 [时] 骨架 ───────────────────────────────────
def test_perception_skeleton():
    owner = make_owner()
    import datetime as _dt
    owner.timezone = _dt.timezone.utc
    block = main_mod.SoulSyncPro._build_perception_block(owner, "u1", ["我的生日"])
    assert block.startswith("[时] "), block
    assert "发送时间" not in block, "时间行应骨架化"
    assert "特别日子: 我的生日" in block
    assert "心情" not in block, "天气行不应带 mood 描述"


# ── 7. 按需注入判定（P1 相关性过滤）─────────────────────
def test_should_inject_env():
    assert should_inject_env("你好", 0, [], 5) is True, "首次轮次应注入"
    assert should_inject_env("你好", 3, [], 5) is False, "非命中轮不注入"
    assert should_inject_env("你好", 5, [], 5) is True, "每 5 轮注入"
    assert should_inject_env("今天天气怎么样", 3, [], 5) is True, "提及天气强制注入"
    assert should_inject_env("随便聊聊", 4, ["生日"], 5) is True, "特殊日子强制注入"
    assert should_inject_env("你好", 2, [], 0) is True, "every_n=0 表示每轮注入"
    assert should_inject_env("你好", 2, [], 7) is False


def test_should_inject_static():
    assert should_inject_static("你好", 0, 20) is True, "首次应注入静态层"
    assert should_inject_static("你好", 10, 20) is False, "中间轮不注入"
    assert should_inject_static("你好", 20, 20) is True, "每 20 轮注入"
    assert should_inject_static("我叫小明", 10, 20) is True, "身份信息强制注入"
    assert should_inject_static("记得我吗", 10, 20) is True, "身份类关键词强制注入"
    assert should_inject_static("你好", 10, 0) is True, "every_n=0 表示每轮注入"
    assert should_inject_static("你好", 10, 20, transitioned=True) is True, "阶段跃迁强制注入静态层"


# ── 8. P2 动态裁剪（trainer 注入器 + RDE 叙事瘦身）────────
def test_persona_relevance_cut():
    from astrbot_plugin_soulsync.trainer.persona.persona_injector import PersonaInjector
    from astrbot_plugin_soulsync.trainer.trainer_types import PersonaParams
    inj = PersonaInjector()
    p = PersonaParams()
    full = inj.generate(p)
    assert "悲伤敏感" in full and "表达风格" in full, "无文本时应全量注入"
    hit = inj.generate(p, "我有点难过，心情好差")
    assert "悲伤敏感" in hit and "愤怒门槛" in hit, "负面词应保留情感维度"
    assert "表达风格" not in hit and "记忆偏好" not in hit, "无关维度应裁剪"
    miss = inj.generate(p, "嗯")
    assert "悲伤敏感" not in miss and "表达风格" not in miss, "无命中仅基础行"
    assert "训练阶段" in miss and len(miss.splitlines()) == 2


def test_knowledge_relevance_topn():
    from astrbot_plugin_soulsync.trainer.knowledge.knowledge_injector import KnowledgeInjector
    from astrbot_plugin_soulsync.trainer.trainer_types import KnowledgeBase, KnowledgeItem
    kb = KnowledgeBase(items=[
        KnowledgeItem(id="1", category="interests", key="篮球", value="每周三打篮球"),
        KnowledgeItem(id="2", category="interests", key="滑雪", value="冬天去滑雪"),
        KnowledgeItem(id="3", category="profile", key="生日", value="6月1日出生"),
        KnowledgeItem(id="4", category="values", key="态度", value="认真生活"),
    ])
    inj = KnowledgeInjector()
    out = inj.generate(kb, text="周末一起去滑雪吧")
    assert "滑雪" in out, "命中条目应优先注入"
    assert "篮球" not in out and "生日" not in out, "未命中条目应裁剪"
    assert "[用户知识库]" in out


def test_memory_star_full_text():
    from astrbot_plugin_soulsync.trainer.memory.private_memory_retriever import PrivateMemoryRetriever
    from astrbot_plugin_soulsync.trainer.trainer_types import PrivateMemory
    star = PrivateMemory(id="pm_1", date="2026-08-01", content="我们约定每年秋天一起看银杏，那是我们的秘密" * 3)
    normal = PrivateMemory(id="pm_2", date="2026-08-02", content="一起吃过的火锅" * 5)
    r = PrivateMemoryRetriever()
    fmt = r.format_for_llm([star, normal], starred_ids={"pm_1"})
    assert "⭐ " in fmt, "星标记忆应有标记"
    assert "我们约定" in fmt and "秘密" in fmt, "星标记忆保留全文"
    assert "吃过的火锅" in fmt, "普通记忆应注入"
    assert "⭐ " not in r.format_for_llm([normal]), "未传星标集合时普通记忆无标记"


def test_style_fused_skip():
    from astrbot_plugin_soulsync.trainer.style.style_injector import StyleInjector
    from astrbot_plugin_soulsync.trainer.trainer_types import StyleState, LanguageProfile
    inj = StyleInjector()
    fused = StyleState(phase="fused", fusion_ratio=1.0, profile=LanguageProfile())
    assert inj.generate(fused) == "", "融合度100%应跳过风格注入"
    adopting = StyleState(phase="adoption", fusion_ratio=0.5, profile=LanguageProfile())
    out = inj.generate(adopting)
    assert out and "融合度" in out, "融合中应正常注入"


def test_stage_ctx_compact():
    from astrbot_plugin_soulsync.rde.narrative.stage_injector import StageInjector
    orch = StageInjector(enabled=True)
    ctx = orch.generate_stage_context("s6", {"user_name": "小雅"})
    assert "【当前关系阶段】" in ctx and "禁忌：" in ctx
    assert "阶段：暧昧萌动" in ctx, "压缩格式应含阶段名锚点"
    assert "保持此阶段特征" in ctx and "勿超前或滞后" in ctx
    assert "你正处于" not in ctx, "模板外壳应被移除"
    ctx12 = orch.generate_stage_context("s12", {})
    assert "每轮回复 1~2 次即可" in ctx12, "s12 降频措辞保留"
    ctx12f = orch.generate_stage_context("s12", {}, recent_transition=None)
    forced = StageInjector(enabled=True, s12_forced_address=True)
    ctx12h = forced.generate_stage_context("s12", {})
    assert "100% 使用最深情的称呼" in ctx12h, "强制措辞开关仍生效"


print("ALL PASS: Token 节省 P0 骨架压缩 + P1 按需注入 + P2 动态裁剪 8 组断言")
