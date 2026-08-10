"""v1.7 时间感知测试

覆盖：
1. today_context：2026 节假日日期、节日菜命中（元宵汤圆）、候选落空（端午无粽子）
2. 季节：春夏秋冬月份归属与加权、season_hit 命中
3. is_fast_dish：快手/懒人标签判断
4. 指令：/今天 输出、/吃点啥 节日附加文案（monkeypatch 假日期）
"""

import sys
import tempfile
import time
from datetime import date
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(PLUGIN_DIR.parent) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR.parent))

from test_bistro import _MsgEvent, _make_plugin, install_stubs  # noqa: E402


def _ctx(engine, y, m, d):
    from astrbot_plugin_soulsync_bistro_心旅小馆.time_sense import today_context

    return today_context(engine, date(y, m, d))


def test_festival_dates_and_dishes():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()

    ctx = _ctx(engine, 2026, 2, 17)
    assert ctx["festival"] == "春节", f"2/17 应为春节: {ctx['festival']}"
    assert ctx["festival_dish"], f"春节应有节日菜: {ctx['festival_dish']}"

    ctx = _ctx(engine, 2026, 3, 3)
    assert ctx["festival"] == "元宵节"
    dish = ctx["festival_dish"]
    assert dish and "汤圆" in dish, f"元宵节应推荐汤圆: {dish}"

    ctx = _ctx(engine, 2026, 12, 21)
    assert ctx["festival"] == "冬至"

    ctx = _ctx(engine, 2026, 9, 25)
    assert ctx["festival"] == "中秋节"

    ctx = _ctx(engine, 2026, 6, 19)
    assert ctx["festival"] == "端午节"
    dish = ctx["festival_dish"]
    assert dish and "粽" in dish, f"端午应推荐粽子菜: {dish}"

    ctx = _ctx(engine, 2026, 7, 1)
    assert ctx["festival"] is None, "普通日期应无节日"


def test_festival_no_dish_fallback():
    """候选菜全落空时：只祝福不推菜"""
    from astrbot_plugin_soulsync_bistro_心旅小馆 import time_sense
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()
    orig = time_sense.FESTIVALS
    time_sense.FESTIVALS = orig + ((6, 20, "测试节", ("不存在的菜xyz",), "测试祝福"),)
    try:
        ctx = _ctx(engine, 2026, 6, 20)
        assert ctx["festival"] == "测试节"
        assert ctx["festival_dish"] is None, "候选落空应无推荐菜"
    finally:
        time_sense.FESTIVALS = orig


def test_seasons():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()
    cases = [(3, "春", 0.1), (6, "夏", 0.2), (10, "秋", 0.1), (1, "冬", 0.2), (12, "冬", 0.2)]
    for month, season, bonus in cases:
        ctx = _ctx(engine, 2026, month, 15)
        assert ctx["season"] == season, f"{month}月应为{season}: {ctx['season']}"
        assert ctx["season_bonus"] == bonus


def test_season_hit():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine
    from astrbot_plugin_soulsync_bistro_心旅小馆.time_sense import season_hit

    engine = RecipeEngine()
    ctx = _ctx(engine, 2026, 7, 15)
    assert ctx["season"] == "夏"
    lvdou = [r for r in engine.recipes if "绿豆" in str(r.get("name", ""))]
    assert lvdou, "测试前提：存在绿豆菜"
    assert season_hit(lvdou[0], ctx), "夏季绿豆菜应命中季节"

    assert not season_hit({"name": "鱼香肉丝", "ingredients": [], "tags": []}, ctx)
    assert not season_hit(lvdou[0], _ctx(engine, 2026, 1, 15)), "冬季不应命中夏季关键词"


def test_is_fast_dish():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine
    from astrbot_plugin_soulsync_bistro_心旅小馆.time_sense import is_fast_dish

    engine = RecipeEngine()
    fast = [r for r in engine.recipes if any(
        t in ("快手", "快手菜", "懒人") for t in r.get("tags", [])
    )]
    assert fast, "测试前提：存在快手菜"
    assert is_fast_dish(fast[0])

    slow = [r for r in engine.recipes if not any(
        t in ("快手", "快手菜", "懒人") for t in r.get("tags", [])
    )][0]
    assert not is_fast_dish(slow)
    assert not is_fast_dish({"name": "x", "tags": []})


def test_command_today():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)

        async def run():
            ev = _MsgEvent("/今天")
            out = [x async for x in plugin.today_info(ev)]
            assert len(out) == 1
            text = out[0]
            assert "星期" in text and "时段" in text

        import asyncio

        asyncio.run(run())


def test_command_eat_what_festival():
    """元宵节 /吃点啥 应附加节日推荐文案"""
    from astrbot_plugin_soulsync_bistro_心旅小馆 import main as main_mod

    orig = main_mod.time.localtime
    main_mod.time.localtime = lambda: time.struct_time(
        (2026, 3, 3, 12, 30, 0, 0, 0, 0)
    )
    try:
        with tempfile.TemporaryDirectory() as td:
            plugin = _make_plugin(td)
            plugin._mood_cache["last"] = ("期待", 0.9, "好期待", time.time())
            plugin._today_key = ""

            async def run():
                ev = _MsgEvent("/吃点啥")
                out = [x async for x in plugin.eat_what(ev, "")]
                text = out[0]
                assert "元宵节" in text and "汤圆" in text, f"应附加节日推荐: {text}"
                assert "春" in text, f"应显示季节: {text}"

            import asyncio

            asyncio.run(run())
    finally:
        main_mod.time.localtime = orig


def test_command_eat_what_festival_zongzi():
    """端午 /吃点啥 应附加粽子推荐（tags 命中）"""
    from astrbot_plugin_soulsync_bistro_心旅小馆 import main as main_mod

    orig = main_mod.time.localtime
    main_mod.time.localtime = lambda: time.struct_time(
        (2026, 6, 19, 12, 30, 0, 0, 0, 0)
    )
    try:
        with tempfile.TemporaryDirectory() as td:
            plugin = _make_plugin(td)
            plugin._today_key = ""

            async def run():
                ev = _MsgEvent("/吃点啥 甜品")
                out = [x async for x in plugin.eat_what(ev, "甜品")]
                text = out[0]
                assert "端午节" in text and "端午安康" in text, f"应显示端午祝福: {text}"
                assert "粽" in text, f"应附加粽子推荐: {text}"

            import asyncio

            asyncio.run(run())
    finally:
        main_mod.time.localtime = orig


def test_command_eat_what_festival_no_dish():
    """候选落空的节日：只祝福语、不附加推荐（注入假上下文，避免模块重导入干扰）"""
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        plugin._today_key = time.strftime("%Y-%m-%d")
        plugin._today_ctx = {
            "festival": "测试节",
            "festival_dish": None,
            "festival_hint": "测试祝福",
            "season": None,
            "season_hint": "",
            "season_bonus": 0.0,
            "season_keywords": (),
        }

        async def run():
            ev = _MsgEvent("/吃点啥 甜品")
            out = [x async for x in plugin.eat_what(ev, "甜品")]
            text = out[0]
            assert "测试节" in text and "测试祝福" in text, f"应显示祝福: {text}"
            assert "来份" not in text, f"候选落空不应附加推荐: {text}"

        import asyncio

        asyncio.run(run())


def main():
    tests = [
        test_festival_dates_and_dishes,
        test_festival_no_dish_fallback,
        test_seasons,
        test_season_hit,
        test_is_fast_dish,
        test_command_today,
        test_command_eat_what_festival,
        test_command_eat_what_festival_zongzi,
        test_command_eat_what_festival_no_dish,
    ]
    passed = 0
    for t in tests:
        t()
        passed += 1
        print(f"PASS {t.__name__}")
    print(f"\n{passed}/{len(tests)} tests passed")
    return 0


install_stubs()

if __name__ == "__main__":
    sys.exit(main())
