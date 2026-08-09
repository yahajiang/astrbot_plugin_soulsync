"""astrbot_plugin_soulsync_bistro_心旅小馆 测试

不依赖真实 AstrBot：通过 sys.modules 注入桩模块后导入插件 main.py。
覆盖：
1. emotion_analyzer：五类情绪识别、否定词翻转、平静回退、置信度
2. recipe_engine：933 道菜谱加载、搜索、分类过滤、情绪匹配、随机推荐含情绪特调
3. main 插件：on_llm_response 钩子缓存情绪快照、命令处理、TTL 过期
"""

import re
import sys
import tempfile
import time
import types
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(PLUGIN_DIR.parent) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR.parent))


def _make_logger():
    def noop(*a, **k):
        pass

    return types.SimpleNamespace(info=noop, warning=noop, error=noop, debug=noop)


def install_stubs():
    """注入 AstrBot 桩模块"""
    for mod in list(sys.modules):
        if mod == "astrbot_plugin_soulsync_bistro_心旅小馆" or mod.startswith(
            "astrbot_plugin_soulsync_bistro_心旅小馆."
        ) or mod == "astrbot" or mod.startswith("astrbot."):
            sys.modules.pop(mod, None)

    base = types.ModuleType("astrbot")
    sys.modules["astrbot"] = base

    api = types.ModuleType("astrbot.api")
    api.logger = _make_logger()
    sys.modules["astrbot.api"] = api

    event_mod = types.ModuleType("astrbot.api.event")
    event_mod.AstrMessageEvent = type("AstrMessageEvent", (), {})

    class _CmdFilter:
        def __init__(self, name, alias=None, parent_command_names=None, **kw):
            self.command_name = name
            self.alias = alias or set()
            self.parent_command_names = parent_command_names or [""]

    event_mod.filter = types.SimpleNamespace(
        command=lambda name, alias=None, **kw: (lambda fn: fn),
        on_llm_response=lambda: (lambda fn: fn),
        regex=lambda pattern: (lambda fn: fn),
    )
    sys.modules["astrbot.api.event"] = event_mod

    star_api = types.ModuleType("astrbot.api.star")
    star_api.Context = type("Context", (), {})
    star_api.Star = type("Star", (), {"__init__": lambda self, context: None})
    sys.modules["astrbot.api.star"] = star_api


class _FakeEnum:
    """模拟枚举成员（如 ComponentType.Plain），仅暴露 name"""

    def __init__(self, name):
        self.name = name


class _MsgEvent:
    """模拟 AstrMessageEvent"""

    def __init__(self, text, private=False, first_type="plain", first_text=None):
        self.message_str = text
        self._private = private
        self._first = types.SimpleNamespace(
            type=first_type,
            text=first_text if first_text is not None else text,
        )

    def plain_result(self, text):
        return text

    def is_private_chat(self):
        return self._private

    def get_messages(self):
        return [self._first]

    def get_message_str(self):
        return self.message_str


class _FakeResponse:
    """模拟带 result_chain 的 LLM 回复"""

    def __init__(self, text):
        comp = types.SimpleNamespace(text=text)
        self.result_chain = types.SimpleNamespace(chain=[comp])


# ────────────────────── emotion_analyzer ──────────────────────


def test_emotion_detection():
    from astrbot_plugin_soulsync_bistro_心旅小馆.emotion_analyzer import analyze

    cases = {
        "今天太开心了，哈哈哈哈！": "喜悦",
        "呜呜呜我好难过，想哭": "悲伤",
        "气死我了！这个傻逼！": "愤怒",
        "好焦虑，明天考试怎么办": "焦虑",
        "好期待周末的旅行！": "期待",
    }
    for text, expect in cases.items():
        r = analyze(text)
        assert r.emotion == expect, f"{text!r} -> {r.emotion}，期望 {expect}"


def test_emotion_negation():
    from astrbot_plugin_soulsync_bistro_心旅小馆.emotion_analyzer import analyze

    r = analyze("我不难过，只是有点累")
    assert r.emotion != "悲伤", f"否定词应抵消: {r.emotion}"

    r = analyze("今天天气不错")
    assert r.emotion == "平静", f"弱情绪低分应回退平静: {r.emotion}"


def test_emotion_confidence():
    from astrbot_plugin_soulsync_bistro_心旅小馆.emotion_analyzer import analyze

    r = analyze("我好开心好开心好开心！")
    assert r.emotion == "喜悦"
    assert 0 < r.confidence <= 1.0
    assert r.matched, "应记录命中的触发词"


def test_emotion_empty_text():
    from astrbot_plugin_soulsync_bistro_心旅小馆.emotion_analyzer import analyze

    assert analyze("").emotion == "平静"
    assert analyze(None).emotion == "平静"


# ────────────────────── recipe_engine ──────────────────────


def test_engine_loads_recipes():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()
    assert engine.total() >= 900, f"菜谱应 >= 900 道，实际 {engine.total()}"
    assert engine.mood_mapping, "mood_mapping 应已加载"
    sample = engine.recipes[0]
    for key in ("name", "category", "ingredients", "steps"):
        assert sample.get(key) is not None, f"菜谱字段缺失: {key}"


def test_engine_search_and_category():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()
    hits = engine.search("番茄炒蛋")
    assert hits, "应搜到番茄炒蛋"
    assert hits[0]["name"] == "番茄炒蛋"

    cats = engine.filter_category("素菜")
    assert cats and all(r.get("vegetarian") for r in cats), "素菜过滤应全部为素"
    assert engine.filter_category("不存在的分类") == []

    r = engine.find_by_name("宫保鸡丁")
    assert r is not None and r["name"] == "宫保鸡丁"
    assert engine.find_by_name("根本不存在这道菜xyz") is None


def test_engine_mood_recommend():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()
    r = engine.recommend_for_mood("悲伤")
    assert r is not None
    r2 = engine.recommend_for_mood("悲伤", category="甜品")
    assert r2 is not None and r2["category"] == "甜品零食"

    picks = engine.random_recommend(3, emotion="愤怒")
    assert len(picks) == 3
    assert any(engine.is_mood_match(p, "愤怒") for p in picks), (
        "随机推荐应至少混入一道情绪特调"
    )


def test_engine_format_steps():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()
    r = engine.find_by_name("番茄炒蛋")
    text = engine.format_steps(r)
    assert text.startswith("1."), f"步骤应从 1 编号: {text[:10]!r}"
    assert "\n2." in text, "应有多步"


def test_engine_drink_snack_meal():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()
    drinks = engine.drink_pool()
    assert len(drinks) >= 10, f"饮品池应 >= 10，实际 {len(drinks)}"
    assert all(engine.is_drink(r) for r in drinks)
    d = engine.recommend_drink("悲伤")
    assert d is not None and engine.is_drink(d)

    snacks = engine.snack_pool()
    assert len(snacks) >= 50, f"解馋池应 >= 50，实际 {len(snacks)}"
    picks = engine.recommend_snacks(3, emotion="愤怒")
    assert len(picks) == 3 and all(engine.is_snack(r) for r in picks)

    meal = engine.recommend_meal("愤怒")
    assert meal is not None and "main" in meal
    assert meal["main"]["name"] and meal["staple"]["name"], "套餐应含主菜与主食"
    assert meal["side"]["name"] and meal["dessert"]["name"], "套餐应含配菜与甜品"


# ────────────────────── main 插件 ──────────────────────


def _make_plugin(tmp_dir):
    install_stubs()
    from astrbot_plugin_soulsync_bistro_心旅小馆.main import SoulSyncBistroPlugin

    return SoulSyncBistroPlugin(None, {})


def test_plugin_init():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        assert plugin.engine.total() >= 900, "插件应加载菜谱库"
        assert plugin.mood_ttl == 30 * 60


def test_llm_response_hook_caches_mood():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)

        class _Resp:
            result_chain = types.SimpleNamespace(chain=[types.SimpleNamespace(text="今天好开心呀！")])

        import asyncio

        async def run():
            await plugin.on_llm_response(None, _Resp())
            mood = plugin._current_mood()
            assert mood is not None
            assert mood["emotion"] == "喜悦"
            assert mood["snippet"].startswith("今天好开心")

        asyncio.run(run())


def test_mood_ttl_expiry():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        plugin._mood_cache["last"] = ("喜悦", 0.9, "测试", time.time() - 3600)
        assert plugin._current_mood() is None, "过期快照应返回 None"


def test_extract_text_variants():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        assert plugin._extract_text("直接文本") == "直接文本"
        assert plugin._extract_text(_FakeResponse("链式文本")) == "链式文本"
        assert plugin._extract_text(None) == ""
        assert plugin._extract_text(_FakeResponse("")) == ""


def test_command_eat_what():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        plugin._mood_cache["last"] = ("愤怒", 0.9, "气死我了", time.time())

        async def run():
            ev = _MsgEvent("/吃点啥")
            out = [x async for x in plugin.eat_what(ev, "")]
            assert len(out) == 1
            text = out[0]
            assert "愤怒" in text and "为你推荐" in text

            out = [x async for x in plugin.eat_what(ev, "甜品")]
            text = out[0]
            assert "甜品" in text

            out = [x async for x in plugin.eat_what(ev, "不存在的分类")]
            assert "不认识" in out[0]

        import asyncio

        asyncio.run(run())


def test_command_eat_what_no_mood():
    """无情绪快照（平静）时 /吃点啥 应回退随机推荐，而非报错"""
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        assert plugin._current_mood() is None, "测试前提：无情绪快照"

        async def run():
            ev = _MsgEvent("/吃点啥")
            out = [x async for x in plugin.eat_what(ev, "")]
            assert len(out) == 1
            text = out[0]
            assert "为你推荐" in text, f"应回退随机推荐: {text}"
            assert "平静" in text or "随缘" in text

            out = [x async for x in plugin.eat_what(ev, "素菜")]
            assert "为你推荐" in out[0], f"素菜请求应正常推荐: {out[0]}"

            engine = plugin.engine
            r = engine.recommend_for_mood("平静")
            assert r is not None, "平静情绪应回退随机"
            r = engine.recommend_for_mood("平静", category="素菜")
            assert r is not None and r.get("vegetarian"), (
                f"素菜请求应返回素食菜: {r['name'] if r else None}"
            )
            r = engine.recommend_for_mood("平静", category="甜品")
            assert r is not None and r["category"] == "甜品零食"
            assert engine.recommend_for_mood("未知情绪xyz") is not None, "未知情绪也应回退随机"

        import asyncio

        asyncio.run(run())


def test_command_search():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        plugin._mood_cache["last"] = ("喜悦", 0.9, "太棒了", time.time())

        async def run():
            ev = _MsgEvent("/菜谱搜索 土豆")
            out = [x async for x in plugin.search_recipe(ev, "土豆")]
            assert len(out) == 1
            assert "土豆" in out[0] and "找到" in out[0]

            out = [x async for x in plugin.search_recipe(ev, "")]
            assert "搜什么" in out[0]

            out = [x async for x in plugin.search_recipe(ev, "zzz不存在的菜zzz")]
            assert "没找到" in out[0]

        import asyncio

        asyncio.run(run())


def test_command_how_to_cook():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)

        async def run():
            ev = _MsgEvent("/怎么做 宫保鸡丁")
            out = [x async for x in plugin.how_to_cook(ev, "宫保鸡丁")]
            assert len(out) == 1
            text = out[0]
            assert "宫保鸡丁" in text and "做法" in text and "1." in text

            out = [x async for x in plugin.how_to_cook(ev, "番茄炒蛋")]
            assert "番茄炒蛋" in out[0]

            out = [x async for x in plugin.how_to_cook(ev, "")]
            assert "菜名" in out[0]

            out = [x async for x in plugin.how_to_cook(ev, "zzz不存在zzz")]
            assert "没有" in out[0] or "试试" in out[0]

        import asyncio

        asyncio.run(run())


def test_command_random():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        plugin._mood_cache["last"] = ("期待", 0.9, "好期待", time.time())

        async def run():
            ev = _MsgEvent("/随机推荐 3")
            out = [x async for x in plugin.random_dish(ev, 3)]
            assert len(out) == 1
            assert "3 道" in out[0]

        import asyncio

        asyncio.run(run())


def test_command_status():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)

        async def run():
            ev = _MsgEvent("/心馆 状态")
            out = [x async for x in plugin.status(ev, "状态")]
            assert "还没有情绪快照" in out[0]

        import asyncio

        asyncio.run(run())

        plugin._mood_cache["last"] = ("焦虑", 0.8, "好焦虑", time.time())

        async def run2():
            ev = _MsgEvent("/心馆 状态")
            out = [x async for x in plugin.status(ev, "状态")]
            assert "焦虑" in out[0] and "置信度" in out[0]

        import asyncio

        asyncio.run(run2())


def test_eat_what_bare():
    """群聊纯文本含「吃点啥/吃什么/吃啥」无斜杠触发；斜杠/@/私聊场景不重复触发"""
    from astrbot_plugin_soulsync_bistro_心旅小馆.main import EAT_WHAT_BARE_PATTERN

    assert re.search(EAT_WHAT_BARE_PATTERN, "咱们晚上吃点啥")
    assert re.search(EAT_WHAT_BARE_PATTERN, "吃什么好呢"), "「吃什么」应匹配"
    assert re.search(EAT_WHAT_BARE_PATTERN, "吃啥")
    assert re.search(EAT_WHAT_BARE_PATTERN, "今天吃什么"), "「今天吃什么」也应匹配"

    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        plugin._mood_cache["last"] = ("期待", 0.9, "好期待", time.time())

        async def run():
            ev = _MsgEvent("咱们晚上吃点啥")
            out = [x async for x in plugin.eat_what_bare(ev)]
            assert len(out) == 1 and "为你推荐" in out[0], f"群聊纯文本应触发: {out}"

            ev_what = _MsgEvent("吃什么好呢")
            out = [x async for x in plugin.eat_what_bare(ev_what)]
            assert len(out) == 1 and "为你推荐" in out[0], f"无前缀「吃什么」应触发: {out}"

            ev_ha = _MsgEvent("吃啥")
            out = [x async for x in plugin.eat_what_bare(ev_ha)]
            assert len(out) == 1 and "为你推荐" in out[0], f"无前缀「吃啥」应触发: {out}"

            ev_slash = _MsgEvent("/吃点啥", first_text="/吃点啥")
            out = [x async for x in plugin.eat_what_bare(ev_slash)]
            assert len(out) == 0, "带斜杠应由命令处理器负责，不应重复触发"

            ev_at = _MsgEvent("吃点啥", first_type="at")
            out = [x async for x in plugin.eat_what_bare(ev_at)]
            assert len(out) == 0, "@ 机器人触发不应走无前缀分支"

            ev_enum = _MsgEvent("吃点啥", first_type=_FakeEnum("Plain"))
            out = [x async for x in plugin.eat_what_bare(ev_enum)]
            assert len(out) == 1 and "为你推荐" in out[0], "枚举类型 Plain 组件应视为纯文本: {out}"

            ev_private = _MsgEvent("吃点啥", private=True)
            out = [x async for x in plugin.eat_what_bare(ev_private)]
            assert len(out) == 0, "私聊已由命令处理器覆盖，不应重复触发"

        import asyncio

        asyncio.run(run())


def test_engine_time_recommend():
    """时间推荐：5 个时段各自返回时段名与合理的套餐结构"""
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()

    cases = {
        "夜宵": 23, "早餐": 8, "午餐": 12,
        "下午茶": 15, "晚餐": 19, "夜宵": 2,
    }
    for period, hour in cases.items():
        res = engine.recommend_by_time(hour)
        assert res is not None, f"{hour} 点应有推荐"
        assert res["period"] == period, f"{hour} 点应为{period}: {res['period']}"
        assert "main" in res["meal"], f"{period} 应有主项"

    assert engine.period_by_hour(6) == "早餐"
    assert engine.period_by_hour(12) == "午餐"
    assert engine.period_by_hour(16) == "下午茶"
    assert engine.period_by_hour(20) == "晚餐"
    assert engine.period_by_hour(23) == "夜宵"
    assert engine.period_by_hour(3) == "夜宵"

    res = engine.recommend_by_time(19, emotion="期待")
    assert res is not None and res["period"] == "晚餐"
    main = res["meal"]["main"]
    assert main["category"] == "荤菜", "晚餐主菜应为荤菜"


def test_command_eat_what_meal():
    """/吃点啥 无分类应按时段推荐套餐；指定分类仍推荐单菜"""
    from astrbot_plugin_soulsync_bistro_心旅小馆 import main as main_mod

    orig = main_mod.time.localtime
    main_mod.time.localtime = lambda: time.struct_time(
        (2026, 8, 9, 12, 30, 0, 0, 0, 0)
    )
    try:
        with tempfile.TemporaryDirectory() as td:
            plugin = _make_plugin(td)
            plugin._mood_cache["last"] = ("期待", 0.9, "好期待", time.time())

            async def run():
                ev = _MsgEvent("/吃点啥")
                out = [x async for x in plugin.eat_what(ev, "")]
                text = out[0]
                assert "为你推荐套餐" in text, f"应推荐套餐: {text}"
                assert "主菜" in text and "主食" in text, "套餐应含主菜与主食"
                assert "时段" in text, "应标注时间时段"

                out = [x async for x in plugin.eat_what(ev, "甜品")]
                assert "为你推荐" in out[0] and "甜品" in out[0]

            import asyncio

            asyncio.run(run())
    finally:
        main_mod.time.localtime = orig


def test_command_drink_what():
    """/喝点啥 应推荐饮品，含情绪信息"""
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        plugin._mood_cache["last"] = ("悲伤", 0.9, "好难过", time.time())

        async def run():
            ev = _MsgEvent("/喝点啥")
            out = [x async for x in plugin.drink_what(ev)]
            assert len(out) == 1
            text = out[0]
            assert "为你推荐饮品" in text, f"应推荐饮品: {text}"
            assert "悲伤" in text, "应带情绪信息"
            name = text.split("饮品：")[1].split("\n")[0]
            r = plugin.engine.find_by_name(name)
            assert r is not None and plugin.engine.is_drink(r)

        import asyncio

        asyncio.run(run())


def test_command_snack_craving():
    """/解馋 应推荐零食小吃"""
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        plugin._mood_cache["last"] = ("愤怒", 0.9, "气死了", time.time())

        async def run():
            ev = _MsgEvent("/解馋 3")
            out = [x async for x in plugin.snack_craving(ev, 3)]
            assert len(out) == 1
            text = out[0]
            assert "解馋推荐 3 样" in text, f"应推荐 3 样零食: {text}"

        import asyncio

        asyncio.run(run())


def test_drink_snack_bare():
    """群聊纯文本「喝点啥/解馋」无斜杠触发；斜杠/私聊不重复触发"""
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)

        async def run():
            ev = _MsgEvent("晚上喝点啥好呢")
            out = [x async for x in plugin.drink_what_bare(ev)]
            assert len(out) == 1 and "饮品" in out[0], f"群聊纯文本应触发饮品: {out}"

            ev_slash = _MsgEvent("/喝点啥", first_text="/喝点啥")
            out = [x async for x in plugin.drink_what_bare(ev_slash)]
            assert len(out) == 0, "带斜杠不应重复触发"

            ev_private = _MsgEvent("喝点啥", private=True)
            out = [x async for x in plugin.drink_what_bare(ev_private)]
            assert len(out) == 0, "私聊不应重复触发"

            ev2 = _MsgEvent("好馋啊想吃零食")
            out = [x async for x in plugin.snack_craving_bare(ev2)]
            assert len(out) == 1 and "解馋" in out[0], f"群聊纯文本应触发解馋: {out}"

            ev2_slash = _MsgEvent("/解馋", first_text="/解馋")
            out = [x async for x in plugin.snack_craving_bare(ev2_slash)]
            assert len(out) == 0, "带斜杠不应重复触发"

        import asyncio

        asyncio.run(run())


def main():
    tests = [
        test_emotion_detection,
        test_emotion_negation,
        test_emotion_confidence,
        test_emotion_empty_text,
        test_engine_loads_recipes,
        test_engine_search_and_category,
        test_engine_mood_recommend,
        test_engine_format_steps,
        test_plugin_init,
        test_llm_response_hook_caches_mood,
        test_mood_ttl_expiry,
        test_extract_text_variants,
        test_command_eat_what,
        test_command_eat_what_no_mood,
        test_eat_what_bare,
        test_command_eat_what_meal,
        test_command_drink_what,
        test_command_snack_craving,
        test_drink_snack_bare,
        test_command_search,
        test_command_how_to_cook,
        test_command_random,
        test_command_status,
        test_engine_drink_snack_meal,
    ]
    passed = 0
    for t in tests:
        t()
        passed += 1
        print(f"PASS {t.__name__}")
    print(f"\n{passed}/{len(tests)} tests passed")
    return 0


# 模块导入即注入桩，保证 pytest 模式与直接运行模式一致
install_stubs()

if __name__ == "__main__":
    sys.exit(main())