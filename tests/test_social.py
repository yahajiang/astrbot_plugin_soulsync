"""v2.0 社交测试

覆盖：
1. FavoriteStore：新增/重复/删除/列表排序/持久化/损坏回退/时钟注入
2. group_hot：空数据、多用户点赞+收藏聚合排序（likes ×1 + 收藏 ×2）、top 截断
3. 指令流程：/收藏 /我的收藏 /取消收藏 /群榜 /分享 的正常/异常分支
4. 推荐加权：收藏菜在推荐权重 +0.1
"""

import sys
import tempfile
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(PLUGIN_DIR.parent) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR.parent))

from test_bistro import _MsgEvent, _make_plugin, install_stubs  # noqa: E402


def _fav_store(path, now=None):
    from astrbot_plugin_soulsync_bistro_心旅小馆.social import FavoriteStore

    return FavoriteStore(path, now=now)


def test_fav_add_remove():
    with tempfile.TemporaryDirectory() as td:
        store = _fav_store(Path(td) / "favorites.json")
        assert store.add("u1", "番茄炒蛋") is True, "新收藏应返回 True"
        assert store.add("u1", "番茄炒蛋") is False, "重复收藏应返回 False"
        assert store.add("u1", "宫保鸡丁") is True
        assert store.names("u1") == {"番茄炒蛋", "宫保鸡丁"}
        assert store.total("u1") == 2

        assert store.remove("u1", "番茄炒蛋") is True
        assert store.remove("u1", "番茄炒蛋") is False, "重复删除应返回 False"
        assert store.names("u1") == {"宫保鸡丁"}

        assert store.add("", "  ") is False, "空菜名不应收藏"
        assert store.names("不存在用户") == set()


def test_fav_list_order_and_persistence():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "favorites.json"
        store = _fav_store(path, now=100.0)
        store.add("u1", "A")
        store._now = 200.0
        store.add("u1", "B")
        assert [d for d, _ in store.list("u1")] == ["B", "A"], "应时间降序"

        reloaded = _fav_store(path, now=200.0)
        assert reloaded.names("u1") == {"A", "B"}, "持久化后应能读回"


def test_fav_corrupt_fallback():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "favorites.json"
        path.write_text("{bad json", encoding="utf-8")
        store = _fav_store(path)
        assert store.names("u1") == set(), "损坏文件应回退空数据"
        assert store.add("u1", "番茄炒蛋") is True, "损坏后仍可正常写入"


def test_group_hot():
    from astrbot_plugin_soulsync_bistro_心旅小馆.feedback import FeedbackStore
    from astrbot_plugin_soulsync_bistro_心旅小馆.social import group_hot

    with tempfile.TemporaryDirectory() as td:
        feedback = FeedbackStore(Path(td) / "feedback.json")
        favs = _fav_store(Path(td) / "favorites.json")
        assert group_hot(feedback, favs) == [], "无数据应返回空"

        feedback.record_feedback("u1", "番茄炒蛋", "like")
        feedback.record_feedback("u1", "番茄炒蛋", "like")
        feedback.record_feedback("u2", "宫保鸡丁", "like")
        favs.add("u1", "宫保鸡丁")
        favs.add("u1", "番茄炒蛋")
        favs.add("u2", "番茄炒蛋")

        rows = group_hot(feedback, favs)
        assert rows[0]["name"] == "番茄炒蛋", "热度最高应排第一"
        assert rows[0]["hot"] == 2 + 2 * 2, "hot = likes + 2×favs"
        assert rows[1]["name"] == "宫保鸡丁"
        assert rows[1]["hot"] == 1 + 2 * 1

        rows = group_hot(feedback, favs, top=1)
        assert len(rows) == 1, "top 参数应截断"


def test_command_fav():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        plugin.favorites = _fav_store(Path(td) / "favorites.json")

        async def run():
            ev = _MsgEvent("/收藏 番茄炒蛋")
            out = [x async for x in plugin.fav_dish(ev, "番茄炒蛋")]
            assert "已收藏" in out[0] and "番茄炒蛋" in out[0]

            out = [x async for x in plugin.fav_dish(ev, "番茄炒蛋")]
            assert "已经在收藏夹" in out[0], f"重复收藏应提示: {out[0]}"

            out = [x async for x in plugin.fav_dish(ev, "zzz不存在zzz")]
            assert "没找到" in out[0] or "没有" in out[0]

            out = [x async for x in plugin.fav_dish(ev, "")]
            assert "菜名" in out[0]

        import asyncio

        asyncio.run(run())


def test_command_my_favorites():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        plugin.favorites = _fav_store(Path(td) / "favorites.json")

        async def run():
            ev = _MsgEvent("/我的收藏")
            out = [x async for x in plugin.my_favorites(ev)]
            assert "空空如也" in out[0], f"空收藏应提示: {out[0]}"

            plugin.favorites.add(plugin._user_id(ev), "番茄炒蛋")
            plugin.favorites.add(plugin._user_id(ev), "宫保鸡丁")
            out = [x async for x in plugin.my_favorites(ev)]
            assert "2 道" in out[0] and "番茄炒蛋" in out[0] and "宫保鸡丁" in out[0]

        import asyncio

        asyncio.run(run())


def test_command_unfav():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        plugin.favorites = _fav_store(Path(td) / "favorites.json")

        async def run():
            ev = _MsgEvent("/取消收藏 番茄炒蛋")
            uid = plugin._user_id(ev)
            plugin.favorites.add(uid, "番茄炒蛋")

            out = [x async for x in plugin.unfav_dish(ev, "番茄炒蛋")]
            assert "已取消收藏" in out[0]
            assert plugin.favorites.names(uid) == set()

            out = [x async for x in plugin.unfav_dish(ev, "番茄炒蛋")]
            assert "没有" in out[0], f"重复取消应提示: {out[0]}"

            out = [x async for x in plugin.unfav_dish(ev, "")]
            assert "菜名" in out[0]

        import asyncio

        asyncio.run(run())


def test_command_group_rank():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        plugin.favorites = _fav_store(Path(td) / "favorites.json")

        async def run():
            ev = _MsgEvent("/群榜")
            out = [x async for x in plugin.group_rank(ev)]
            assert "还没有热度数据" in out[0], f"空榜应提示: {out[0]}"

            plugin.feedback.record_feedback("u1", "番茄炒蛋", "like")
            plugin.feedback.record_feedback("u2", "番茄炒蛋", "like")
            plugin.favorites.add("u1", "宫保鸡丁")

            out = [x async for x in plugin.group_rank(ev)]
            text = out[0]
            assert "群热度榜" in text and "番茄炒蛋" in text, f"应有榜单: {text}"
            assert "宫保鸡丁" in text
            assert "👍2" in text, f"应显示点赞数: {text}"
            idx_fan = text.index("番茄炒蛋")
            idx_gong = text.index("宫保鸡丁")
            assert idx_fan < idx_gong, "热度高的应排前面"

        import asyncio

        asyncio.run(run())


def test_command_share():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)

        async def run():
            ev = _MsgEvent("/分享 宫保鸡丁")
            out = [x async for x in plugin.share_recipe(ev, "宫保鸡丁")]
            text = out[0]
            assert "分享 · 宫保鸡丁" in text and "做法" in text and "1." in text
            assert "来自「心旅小馆」" in text

            out = [x async for x in plugin.share_recipe(ev, "")]
            assert "菜名" in out[0]

            out = [x async for x in plugin.share_recipe(ev, "zzz不存在zzz")]
            assert "没找到" in out[0] or "没有" in out[0]

        import asyncio

        asyncio.run(run())


def test_fav_bonus_weight():
    """收藏的菜在推荐权重中 +0.1"""
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        plugin.favorites = _fav_store(Path(td) / "favorites.json")

        ev = _MsgEvent("/吃点啥")
        uid = plugin._user_id(ev)
        plugin.favorites.add(uid, "番茄炒蛋")

        uid, _exclude, weight = plugin._feedback_ctx(ev)
        fav_score = weight({"name": "番茄炒蛋"})
        other_score = weight({"name": "宫保鸡丁"})
        assert abs(fav_score - other_score - 0.1) < 1e-9, (
            f"收藏菜应多 0.1: fav={fav_score} other={other_score}"
        )


def main():
    tests = [
        test_fav_add_remove,
        test_fav_list_order_and_persistence,
        test_fav_corrupt_fallback,
        test_group_hot,
        test_command_fav,
        test_command_my_favorites,
        test_command_unfav,
        test_command_group_rank,
        test_command_share,
        test_fav_bonus_weight,
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
