"""反馈闭环（v1.4）测试：FeedbackStore 与引擎加权/去重、插件指令。

不依赖真实 AstrBot；复用 test_bistro 的桩注入方式。
"""

import asyncio
import sys
import tempfile
from collections import Counter
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(PLUGIN_DIR.parent) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR.parent))

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_bistro import _MsgEvent, _make_plugin  # noqa: E402

from astrbot_plugin_soulsync_bistro_心旅小馆.feedback import (  # noqa: E402
    FeedbackStore,
)
from astrbot_plugin_soulsync_bistro_心旅小馆.recipe_engine import (  # noqa: E402
    RecipeEngine,
)

T0 = 1_700_000_000.0


def _store(tmp: str, now: float = T0) -> FeedbackStore:
    return FeedbackStore(Path(tmp) / "feedback.json", now=now)


# ────────────────────── FeedbackStore ──────────────────────


def test_feedback_basic_score():
    with tempfile.TemporaryDirectory() as td:
        s = _store(td)
        assert s.dish_score("u1", "宫保鸡丁") == 1.0, "无反馈应返回基准分"
        s.record_feedback("u1", "宫保鸡丁", "like")
        s.record_feedback("u1", "宫保鸡丁", "like")
        assert abs(s.dish_score("u1", "宫保鸡丁") - 1.2) < 1e-9
        s.record_feedback("u1", "宫保鸡丁", "dislike")
        assert abs(s.dish_score("u1", "宫保鸡丁") - 0.9) < 1e-9
        # 其他用户互不影响
        assert s.dish_score("u2", "宫保鸡丁") == 1.0


def test_feedback_clamp_and_decay():
    with tempfile.TemporaryDirectory() as td:
        s = _store(td)
        for _ in range(30):
            s.record_feedback("u", "狂赞菜", "like")
        assert s.dish_score("u", "狂赞菜") == 3.0, "赞分应封顶 +2.0"
        for _ in range(10):
            s.record_feedback("u", "踩雷菜", "dislike")
        assert s.dish_score("u", "踩雷菜") == -1.0, "踩分应封底 -1.0"

        # 衰减：100 天后赞分向基准回归
        far = s.dish_score("u", "狂赞菜", now=T0 + 100 * 86400)
        assert 1.0 < far < 1.1, f"远期赞分应接近基准: {far}"


def test_feedback_recommendation_dedup():
    with tempfile.TemporaryDirectory() as td:
        s = _store(td)
        s.record_recommendation("u", ["菜A"], ts=T0)
        s.record_recommendation("u", ["菜B"], ts=T0 - 2.99 * 86400)
        s.record_recommendation("u", ["菜C"], ts=T0 - 3.5 * 86400)
        recent = s.recently_recommended("u", now=T0)
        assert recent == {"菜A", "菜B"}, f"3 天边界去重错误: {recent}"
        assert "菜C" not in recent, "超 3 天不应再排除"


def test_feedback_persistence_and_corrupt():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "feedback.json"
        s1 = FeedbackStore(p)
        s1.record_feedback("u", "菜A", "like")
        s1.record_recommendation("u", ["菜A", "菜B"])
        s2 = FeedbackStore(p)
        assert abs(s2.dish_score("u", "菜A") - 1.1) < 1e-6, "持久化后分数应保留"
        assert s2.last_recommended("u") == "菜B"

        bad = Path(td) / "bad.json"
        bad.write_text("{broken json", encoding="utf-8")
        s3 = FeedbackStore(bad)
        assert s3.dish_score("u", "菜A") == 1.0, "损坏文件应回退空数据"
        s3.record_feedback("u", "菜A", "like")  # 不应抛异常


def test_feedback_summary():
    with tempfile.TemporaryDirectory() as td:
        s = _store(td)
        assert "还没有" in s.summary("u")
        s.record_feedback("u", "菜A", "like")
        s.record_feedback("u", "菜A", "like")
        s.record_feedback("u", "菜B", "dislike")
        s.record_recommendation("u", ["菜C"])
        text = s.summary("u")
        assert "最爱" in text and "菜A" in text
        assert "踩雷" in text and "菜B" in text


# ────────────────────── 引擎：去重与加权 ──────────────────────


def test_engine_exclude_and_weighted():
    engine = RecipeEngine(seed=3)

    # 去重：午餐主菜不再重复推荐
    r1 = engine.recommend_by_time(12)
    main1 = r1["meal"]["main"]["name"]
    r2 = engine.recommend_by_time(12, exclude_names={main1})
    assert r2["meal"]["main"]["name"] != main1, "推荐历史去重应排除主菜"

    # 饮品去重
    d1 = engine.recommend_drink()
    d2 = engine.recommend_drink(exclude_names={d1["name"]})
    assert d2["name"] != d1["name"]

    # 加权：100:1 权重下高权菜应被高频选中
    pool = list(engine.recipes[:30])
    high = {pool[0]["name"], pool[1]["name"]}

    def wf(r):
        return 100.0 if r["name"] in high else 1.0

    counter = Counter()
    for _ in range(300):
        pick = engine._choose(pool, wf)
        counter[pick["name"]] += 1
    top2 = sum(counter[n] for n in high)
    assert top2 > 200, f"加权应显著偏向高权菜: {top2}/300"

    # 权重<=0 保底不崩溃
    wf_neg = lambda r: -5.0  # noqa: E731
    for _ in range(20):
        engine._choose(pool, wf_neg)


def test_engine_exclude_empty_pool_fallback():
    engine = RecipeEngine(seed=5)
    pool = list(engine.recipes[:1])
    out = engine._exclude(pool, {pool[0]["name"]})
    assert out == pool, "排除后池空应回退原池"


# ────────────────────── 插件指令 ──────────────────────


def test_feedback_commands():
    with tempfile.TemporaryDirectory() as td:
        plugin = _make_plugin(td)
        plugin.feedback = FeedbackStore(Path(td) / "feedback.json")

        async def run():
            # 先推荐，产生历史
            ev = _MsgEvent("/吃点啥")
            out = [x async for x in plugin.eat_what(ev)]
            assert out and "套餐" in out[0], f"推荐应成功: {out}"
            assert plugin.feedback.last_recommended("unknown") is not None

            # /好吃 不带菜名 → 标记上一道推荐
            ev2 = _MsgEvent("/好吃")
            out = [x async for x in plugin.good_feedback(ev2)]
            assert out and "好吃" in out[0], f"/好吃 应确认: {out}"
            assert "喜好分" in out[0]

            # /好吃 指定不存在的菜
            ev3 = _MsgEvent("/好吃 不存在的菜")
            out = [x async for x in plugin.good_feedback(ev3, "不存在的菜")]
            assert out and "菜谱库中没有" in out[0]

            # /不好吃 指定真实菜名
            first = plugin.engine.recipes[0]["name"]
            ev4 = _MsgEvent(f"/不好吃 {first}")
            out = [x async for x in plugin.bad_feedback(ev4, first)]
            assert out and "不合口味" in out[0]

            # /我的口味
            ev5 = _MsgEvent("/我的口味")
            out = [x async for x in plugin.my_taste(ev5)]
            assert out and "最爱" in out[0], f"/我的口味 应有统计: {out}"

            # 无任何记录时 /好吃 给出引导
            plugin.feedback = FeedbackStore(Path(td) / "empty.json")
            ev6 = _MsgEvent("/好吃")
            out = [x async for x in plugin.good_feedback(ev6)]
            assert out and "推荐记录" in out[0]

        asyncio.run(run())


def main():
    tests = [
        test_feedback_basic_score,
        test_feedback_clamp_and_decay,
        test_feedback_recommendation_dedup,
        test_feedback_persistence_and_corrupt,
        test_feedback_summary,
        test_engine_exclude_and_weighted,
        test_engine_exclude_empty_pool_fallback,
        test_feedback_commands,
    ]
    passed = 0
    for t in tests:
        t()
        passed += 1
        print(f"PASS {t.__name__}")
    print(f"\n{passed}/{len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
