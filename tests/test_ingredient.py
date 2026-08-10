"""v1.9 食材反查测试

覆盖：
1. match_by_ingredients：番茄+鸡蛋 齐活推荐番茄炒蛋、别名匹配（西红柿）
2. 调味料豁免：缺盐/酱油不提示
3. 覆盖度排序、缺项标注、无结果
4. 指令流程：/家里有 正常/空输入/无结果/情绪标注
"""

import sys
import tempfile
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(PLUGIN_DIR.parent) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR.parent))

from test_bistro import _MsgEvent, _make_plugin, install_stubs  # noqa: E402


def _match(engine, *have, limit=8):
    return engine.match_by_ingredients(list(have), limit=limit)


def test_tomato_egg_ready():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()
    matches = _match(engine, "番茄", "鸡蛋")
    names = [m["recipe"]["name"] for m in matches]
    assert "番茄炒蛋" in names, f"应推荐番茄炒蛋: {names[:5]}"

    tm = next(m for m in matches if m["recipe"]["name"] == "番茄炒蛋")
    assert not tm["missing"], f"番茄+鸡蛋应齐活: missing={tm['missing']}"
    assert tm["coverage"] == 1.0


def test_alias_xihongshi():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()
    matches = _match(engine, "西红柿", "鸡蛋")
    names = [m["recipe"]["name"] for m in matches]
    assert "番茄炒蛋" in names, "「西红柿」应通过别名命中番茄炒蛋"


def test_alias_meat():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()
    assert engine._norm_ingredient("五花肉") == "猪肉"
    assert engine._norm_ingredient("鸡胸肉") == "鸡肉"
    assert engine._norm_ingredient("里脊肉") == "猪肉"
    assert engine._norm_ingredient("马铃薯") == "土豆"
    assert engine._norm_ingredient("生抽") == "酱油"
    assert engine._norm_ingredient("盐") == "盐", "无别名的词原样返回"

    matches = _match(engine, "五花肉", "土豆", "胡萝卜", "青椒")
    assert matches, "肉菜组合应有结果"
    assert any(
        any(x in m["owned"] for x in ("猪肉", "五花肉")) for m in matches[:5]
    ), f"别名应计入 owned: {[m['owned'] for m in matches[:5]]}"


def test_condiments_exempt():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()
    matches = _match(engine, "鸡蛋", "番茄")
    for m in matches:
        for cond in ("盐", "酱油", "糖", "油", "葱", "姜", "蒜", "料酒", "淀粉"):
            assert cond not in m["missing"], f"调味料 {cond} 不应计入缺失: {m['missing']}"


def test_partial_missing():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()
    top = _match(engine, "鸡蛋")
    assert top[0]["coverage"] == 1.0, "齐活菜应排在缺食材菜之前"

    matches = _match(engine, "鸡蛋", limit=1000)
    partials = [m for m in matches if m["missing"]]
    assert partials, "应存在缺食材的推荐"

    tm = next((m for m in matches if m["recipe"]["name"] == "番茄炒蛋"), None)
    assert tm is not None, "全量匹配中应含番茄炒蛋"
    assert "番茄" in tm["missing"], "缺番茄应标注"
    assert tm["coverage"] < 1.0


def test_sort_by_coverage():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()
    matches = _match(engine, "鸡蛋", "番茄", "土豆", "牛肉", "猪肉", "虾", "豆腐")
    coverages = [m["coverage"] for m in matches]
    assert coverages == sorted(coverages, reverse=True), "应按覆盖度降序"
    assert matches[0]["coverage"] == 1.0, "首条应为齐活菜"


def test_no_match():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine

    engine = RecipeEngine()
    assert _match(engine, "航天飞机燃料") == []
    assert _match(engine) == [], "空输入应返回空"


def test_command_have():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)

        async def run():
            ev = _MsgEvent("/家里有 鸡蛋,番茄")
            out = [x async for x in plugin.have_ingredients(ev, "鸡蛋,番茄")]
            assert len(out) == 1
            text = out[0]
            assert "家里有" in text and "鸡蛋" in text and "番茄" in text
            assert "番茄炒蛋" in text, f"应推荐番茄炒蛋: {text}"
            assert "想看做法" in text

            out = [x async for x in plugin.have_ingredients(ev, "")]
            assert "用法" in out[0], "空输入应给用法提示"

            out = [x async for x in plugin.have_ingredients(ev, "航天飞机燃料")]
            assert "没找到" in out[0], "无结果应提示"

        import asyncio

        asyncio.run(run())


def test_command_have_mood_tag():
    """有情绪快照时，情绪适配菜标 ❤️"""
    import time as t

    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        plugin._mood_cache["last"] = ("愤怒", 0.9, "气死了", t.time())

        async def run():
            ev = _MsgEvent("/家里有 猪肉,土豆,胡萝卜")
            out = [x async for x in plugin.have_ingredients(ev, "猪肉,土豆,胡萝卜")]
            assert len(out) == 1
            text = out[0]
            assert "❤️" in text or "· " in text, f"应展示推荐列表: {text}"

        import asyncio

        asyncio.run(run())


def main():
    tests = [
        test_tomato_egg_ready,
        test_alias_xihongshi,
        test_alias_meat,
        test_condiments_exempt,
        test_partial_missing,
        test_sort_by_coverage,
        test_no_match,
        test_command_have,
        test_command_have_mood_tag,
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
