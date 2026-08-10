"""v1.5 用户口味档案测试

覆盖：
1. TasteProfile：CRUD、持久化、非法标签清洗、重置
2. dishes_to_exclude：香菜/内脏/海鲜/辣/葱姜蒜/素食 忌口排除（含鱼香肉丝不误伤）
3. preference_bonus：偏好加分命中与未命中
4. 指令流程：/口味设置 /口味查看 /口味重置 与非法标签提示
"""

import sys
import tempfile
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(PLUGIN_DIR.parent) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR.parent))

from test_bistro import _MsgEvent, _make_plugin, install_stubs  # noqa: E402


def _find_coriander(engine):
    """找一道明确含香菜的菜；找不到返回 None"""
    for r in engine.recipes:
        ings = " ".join(str(i) for i in r.get("ingredients", []))
        if "香菜" in ings or "芫荽" in ings:
            return r
    return None


def _find_spicy(engine):
    for r in engine.recipes:
        if r.get("spicy"):
            return r
    return None


def test_profile_crud_and_persistence():
    from astrbot_plugin_soulsync_bistro_心旅小馆.taste_profile import TasteProfile

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "profiles.json"
        p = TasteProfile(path)
        assert p.get_taste("u1") == []

        p.set_taste("u1", ["不吃香菜", "喜欢面食", "胡说八道"])
        assert p.get_taste("u1") == ["不吃香菜", "喜欢面食"], "非法标签应被过滤"

        p2 = TasteProfile(path)
        assert p2.get_taste("u1") == ["不吃香菜", "喜欢面食"], "应持久化"

        p2.reset("u1")
        assert p2.get_taste("u1") == []
        p3 = TasteProfile(path)
        assert p3.get_taste("u1") == [], "重置应持久化"


def test_exclude_coriander():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine
    from astrbot_plugin_soulsync_bistro_心旅小馆.taste_profile import dishes_to_exclude

    engine = RecipeEngine()
    dish = _find_coriander(engine)
    assert dish is not None, "菜谱中应存在香菜类菜品（测试前提）"

    excluded = dishes_to_exclude(engine, ["不吃香菜"])
    assert dish["name"] in excluded, f"{dish['name']} 应被香菜忌口排除"


def test_exclude_fish_fragrant_not_hit():
    """鱼香肉丝无鱼：不应被「不吃海鲜」排除"""
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine
    from astrbot_plugin_soulsync_bistro_心旅小馆.taste_profile import dishes_to_exclude

    engine = RecipeEngine()
    assert engine.find_by_name("鱼香肉丝") is not None, "测试前提：菜谱有鱼香肉丝"
    excluded = dishes_to_exclude(engine, ["不吃海鲜"])
    assert "鱼香肉丝" not in excluded, "鱼香肉丝不应被海鲜忌口排除"


def test_exclude_vegan_and_spicy():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine
    from astrbot_plugin_soulsync_bistro_心旅小馆.taste_profile import dishes_to_exclude

    engine = RecipeEngine()
    veg = engine.filter_category("素菜")
    meat = [r for r in engine.recipes if not r.get("vegetarian")]
    assert veg and meat, "测试前提：素菜与非素菜都存在"

    excluded = dishes_to_exclude(engine, ["素食"])
    names = {r["name"] for r in meat}
    assert names & excluded == names, "素食忌口应排除全部非素菜"

    spicy_dish = _find_spicy(engine)
    assert spicy_dish is not None, "测试前提：存在辣菜"
    excluded = dishes_to_exclude(engine, ["不吃辣"])
    assert spicy_dish["name"] in excluded


def test_bonus_hit_and_miss():
    from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import RecipeEngine
    from astrbot_plugin_soulsync_bistro_心旅小馆.taste_profile import preference_bonus

    engine = RecipeEngine()
    bonus = preference_bonus(engine, ["喜欢面食"])
    assert bonus({"name": "兰州拉面", "tags": ["面食"]}) == 0.15
    assert bonus({"name": "番茄炒蛋", "tags": ["家常"]}) == 0.0

    bonus2 = preference_bonus(engine, [])
    assert bonus2({"name": "兰州拉面", "tags": []}) == 0.0, "无偏好应零加分"


def test_command_set_view_reset():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)

        async def run():
            ev = _MsgEvent("/口味设置 不吃香菜,喜欢面食")
            out = [x async for x in plugin.set_taste(ev, "不吃香菜,喜欢面食")]
            assert "已保存口味" in out[0] and "不吃香菜" in out[0]

            ev2 = _MsgEvent("/口味查看")
            out = [x async for x in plugin.view_taste(ev2)]
            text = out[0]
            assert "忌口" in text and "不吃香菜" in text
            assert "偏好" in text and "喜欢面食" in text

            ev3 = _MsgEvent("/口味重置")
            out = [x async for x in plugin.reset_taste(ev3)]
            assert "已清空" in out[0]

            out = [x async for x in plugin.view_taste(ev2)]
            assert "还没设置" in out[0]

        import asyncio

        asyncio.run(run())


def test_command_invalid_tags():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)

        async def run():
            ev = _MsgEvent("/口味设置 不喜欢香菜")
            out = [x async for x in plugin.set_taste(ev, "不喜欢香菜")]
            assert "不认识" in out[0] and "可用标签" in out[0]

            out = [x async for x in plugin.set_taste(ev, "")]
            assert "用法" in out[0]

        import asyncio

        asyncio.run(run())


def test_command_taste_affects_recommend():
    """设置素食忌口后，推荐上下文应排除全部非素菜"""
    from astrbot_plugin_soulsync_bistro_心旅小馆.taste_profile import dishes_to_exclude

    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)

        async def run():
            ev = _MsgEvent("/口味设置 素食")
            await anext(plugin.set_taste(ev, "素食"))

            uid, exclude, weight = plugin._feedback_ctx(ev)
            meat = [r["name"] for r in plugin.engine.recipes if not r.get("vegetarian")]
            assert set(meat) <= exclude, "素食忌口应排除全部非素菜"
            assert weight({"name": "番茄炒蛋", "tags": []}) == 1.0, "素食无偏好加分，应等于基础分 1.0"

        import asyncio

        asyncio.run(run())


def main():
    tests = [
        test_profile_crud_and_persistence,
        test_exclude_coriander,
        test_exclude_fish_fragrant_not_hit,
        test_exclude_vegan_and_spicy,
        test_bonus_hit_and_miss,
        test_command_set_view_reset,
        test_command_invalid_tags,
        test_command_taste_affects_recommend,
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
