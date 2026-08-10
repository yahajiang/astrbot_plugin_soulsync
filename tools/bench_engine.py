# -*- coding: utf-8 -*-
"""引擎性能基准：v1.8 索引优化后复测热点耗时（目标：match_by_ingredients <10ms、dishes_to_exclude <1ms）"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from recipe_engine import RecipeEngine
from taste_profile import dishes_to_exclude


def bench(label, fn, repeat=5):
    times = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    print(f"{label:<46} {min(times):>8.2f} ms")
    return min(times)


def main():
    t0 = time.perf_counter()
    engine = RecipeEngine("recipes.json")
    cold = (time.perf_counter() - t0) * 1000
    print(f"引擎初始化(冷)                              {cold:>8.2f} ms")
    t0 = time.perf_counter()
    RecipeEngine("recipes.json")
    warm = (time.perf_counter() - t0) * 1000
    print(f"引擎初始化(缓存)                            {warm:>8.2f} ms")
    print()

    queries = [
        ["鸡蛋"],
        ["番茄", "鸡蛋"],
        ["土豆", "胡萝卜", "鸡胸肉"],
        ["五花肉", "青椒"],
        ["豆腐", "青菜"],
        ["虾", "冬瓜"],
        ["牛肉", "洋葱"],
        ["面粉", "鸡蛋", "糖"],
    ]
    bench("match_by_ingredients x8 查询(累计)", lambda: [engine.match_by_ingredients(q) for q in queries])

    tastes = [["素食"], ["不吃辣"], ["不吃海鲜"], ["不吃猪肉"], ["不吃羊肉"], ["不吃狗肉"], ["素食", "不吃辣"]]
    bench("dishes_to_exclude x7 忌口(累计)", lambda: [dishes_to_exclude(engine, t) for t in tastes])
    n = len(dishes_to_exclude(engine, ["不吃海鲜"]))
    print(f"   不吃海鲜排除 {n} 道 / {len(engine.recipes)} 道")
    print()

    bench("search('红烧肉')", lambda: engine.search("红烧肉"))
    bench("search('豆腐')", lambda: engine.search("豆腐"))
    bench("recommend_for_mood('开心')", lambda: engine.recommend_for_mood("开心"))
    bench("recommend_by_time(18时)", lambda: engine.recommend_by_time(18))


if __name__ == "__main__":
    main()
