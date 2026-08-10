# -*- coding: utf-8 -*-
"""用户口味档案：忌口硬排除 + 偏好软加分。

- TasteProfile：每人一份口味标签，JSON 持久化到 data/user_profiles.json
- dishes_to_exclude：按忌口把菜谱映射为排除集合（食材+名称子串匹配，无数据改动）
- preference_bonus：偏好标签命中给推荐加权（软加分）

标签体系（白名单）：
- 忌口（硬过滤）：不吃香菜 / 不吃内脏 / 不吃海鲜 / 不吃辣 / 不吃葱姜蒜
- 饮食模式（硬过滤）：素食
- 偏好（软加分）：喜欢面食 / 喜欢米饭 / 喜欢粥 / 喜欢烧烤 / 喜欢甜品 / 喜欢清淡
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
DEFAULT_PROFILE_PATH = DEFAULT_DATA_DIR / "user_profiles.json"

HARD_TAGS = ("不吃香菜", "不吃内脏", "不吃海鲜", "不吃辣", "不吃葱姜蒜", "素食")
SOFT_TAGS = (
    "喜欢面食", "喜欢米饭", "喜欢粥", "喜欢烧烤", "喜欢甜品", "喜欢清淡",
)
ALL_TAGS = HARD_TAGS + SOFT_TAGS

# 忌口 → 食材/名称关键词（子串匹配，避免单字误伤）
AVOID_KEYWORDS = {
    "不吃香菜": ("香菜", "芫荽", "胡荽"),
    "不吃内脏": (
        "肝", "腰", "胗", "肫", "脑", "肺", "杂碎",
        "肥肠", "大肠", "猪肚", "牛肚", "毛肚", "爆肚",
        "鸭血", "猪血", "羊杂", "牛杂", "卤煮", "肝尖",
    ),
    "不吃海鲜": (
        "鱼", "虾", "蟹", "蛤", "蚝", "鱿", "章鱼", "鲍", "螺",
        "扇贝", "贝柱", "海带", "海参", "海蜇", "海苔", "紫菜", "海鱼", "海虾", "海蟹",
    ),
    "不吃葱姜蒜": ("姜", "蒜", "葱"),
}

# 忌口 → 命中的豁免词（如「鱼香肉丝」无鱼，不吃海鲜不应排除）
AVOID_EXEMPT = {
    "不吃海鲜": ("鱼香",),
    "不吃葱姜蒜": ("洋葱",),
}

PREFERENCE_MATCH = {
    "喜欢面食": {"name": ("面", "饺子", "馄饨", "云吞", "馒头", "包子", "饼", "粉"), "tag": ("面食", "面条", "粉类")},
    "喜欢米饭": {"name": ("饭",), "tag": ()},
    "喜欢粥": {"name": ("粥",), "tag": ("粥",)},
    "喜欢烧烤": {"name": ("烧烤", "烤串", "串"), "tag": ("烧烤",)},
    "喜欢甜品": {"name": ("甜", "糖", "蛋糕", "布丁", "奶", "糕"), "tag": ("甜品", "甜点")},
    "喜欢清淡": {"name": ("蒸", "清", "白灼", "煮"), "tag": ("清淡",)},
}


class TasteProfile:
    """用户口味档案存储。"""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT_PROFILE_PATH
        self._lock = threading.Lock()
        self._data: Dict[str, List[str]] = {}
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                self._data = {k: v for k, v in raw.items() if isinstance(v, list)}
        except (OSError, ValueError):
            self._data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, str(self.path))
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def get_taste(self, user_id: str) -> List[str]:
        with self._lock:
            return list(self._data.get(user_id, []))

    def set_taste(self, user_id: str, tags: List[str]) -> List[str]:
        tags = [t for t in tags if t in ALL_TAGS]
        with self._lock:
            self._data[user_id] = tags
            self.save()
        return tags

    def reset(self, user_id: str) -> None:
        with self._lock:
            self._data.pop(user_id, None)
            self.save()


def _hit(recipe: Dict, keywords: tuple, exempt: tuple = ()) -> bool:
    """名称/食材任一命中关键词即 True；命中豁免词则跳过。"""
    text = " ".join(
        [
            str(recipe.get("name", "")),
            " ".join(str(i) for i in recipe.get("ingredients", [])),
        ]
    )
    if exempt and any(w in text for w in exempt):
        return False
    return any(kw in text for kw in keywords)


def dishes_to_exclude(engine, taste: List[str]) -> Set[str]:
    """按忌口标签返回应排除的菜名集合。"""
    names: Set[str] = set()
    recipes = engine.recipes
    if "素食" in taste:
        names |= {r["name"] for r in recipes if not r.get("vegetarian", False)}
    if "不吃辣" in taste:
        names |= {r["name"] for r in recipes if r.get("spicy", False)}
    for tag in HARD_TAGS:
        if tag not in taste or tag in ("素食", "不吃辣"):
            continue
        kws = AVOID_KEYWORDS.get(tag)
        if not kws:
            continue
        exempt = AVOID_EXEMPT.get(tag, ())
        names |= {r["name"] for r in recipes if _hit(r, kws, exempt)}
    return names


def preference_bonus(engine, taste: List[str]):
    """返回 (recipe -> 加分) 函数；偏好命中 +0.15/项。"""
    active = [t for t in taste if t in SOFT_TAGS]
    if not active:
        return lambda r: 0.0

    rules = []
    for t in active:
        cfg = PREFERENCE_MATCH.get(t, {"name": (), "tag": ()})
        rules.append((cfg["name"], cfg["tag"]))

    def bonus(recipe: Dict) -> float:
        name = str(recipe.get("name", ""))
        tags = [str(x) for x in recipe.get("tags", [])]
        score = 0.0
        for name_kws, tag_kws in rules:
            hit = any(kw in name for kw in name_kws) or any(
                any(k in tg for k in tag_kws) for tg in tags
            )
            if hit:
                score += 0.15
        return score

    return bonus
