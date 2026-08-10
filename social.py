# -*- coding: utf-8 -*-
"""v2.0 社交：个人收藏夹与群热度榜。本地 JSON 持久化，无第三方依赖。

- FavoriteStore：每用户收藏 {菜名: 收藏时间戳}，data/favorites.json
- group_hot：聚合全用户点赞（feedback likes）+ 收藏 → 群热度榜
  （likes ×1 + 收藏 ×2；feedback 计数无菜级时间戳，故为全时热度）
- 线程安全：内部锁保护；写入临时文件 + 原子替换，损坏时回退空数据
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_FAVORITES_PATH = BASE_DIR / "data" / "favorites.json"

FAV_BONUS = 0.1       # 推荐加权：收藏菜 +0.1
FAV_HOT_WEIGHT = 2    # 群榜计分：收藏 ×2
FAV_LIST_SHOW = 10    # /我的收藏 单次展示条数
GROUP_HOT_TOP = 10    # 群榜条数


class FavoriteStore:
    """个人收藏夹存储。"""

    def __init__(self, path: Optional[Path] = None, now: Optional[float] = None):
        self.path = Path(path) if path else DEFAULT_FAVORITES_PATH
        self._lock = threading.Lock()
        self._data: Dict[str, Dict[str, float]] = {}
        self._now = now  # 测试注入时钟；None 表示用 time.time()
        self._load()

    # ────────────────────── 存储 ──────────────────────

    def _ts(self) -> float:
        return self._now if self._now is not None else time.time()

    def _load(self):
        if not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                self._data = raw
        except (OSError, ValueError):
            self._data = {}

    def save(self) -> None:
        """原子写：先写临时文件再替换，避免写坏主文件。"""
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

    def _dishes(self, user_id: str) -> Dict[str, float]:
        if user_id not in self._data:
            self._data[user_id] = {}
        return self._data[user_id]

    # ────────────────────── 操作 ──────────────────────

    def add(self, user_id: str, dish_name: str) -> bool:
        """收藏一道菜；返回是否为新收藏（已收藏返回 False）。"""
        dish_name = (dish_name or "").strip()
        if not dish_name:
            return False
        with self._lock:
            dishes = self._dishes(user_id)
            if dish_name in dishes:
                return False
            dishes[dish_name] = self._ts()
            self.save()
            return True

    def remove(self, user_id: str, dish_name: str) -> bool:
        """取消收藏；返回是否删除成功。"""
        dish_name = (dish_name or "").strip()
        with self._lock:
            dishes = self._dishes(user_id)
            if dish_name not in dishes:
                return False
            del dishes[dish_name]
            self.save()
            return True

    def names(self, user_id: str) -> Set[str]:
        return set(self._data.get(user_id, {}))

    def list(self, user_id: str) -> List[Tuple[str, float]]:
        """收藏列表（时间降序）。"""
        return sorted(self._data.get(user_id, {}).items(), key=lambda x: -x[1])

    def total(self, user_id: str) -> int:
        return len(self._data.get(user_id, {}))


def group_hot(feedback, favorites, top: int = GROUP_HOT_TOP) -> List[dict]:
    """聚合全用户点赞与收藏 → 群热度榜（likes ×1 + 收藏 ×2，全时累计）。

    返回 [{"name", "likes", "favs", "hot"}]，按热度降序、并列按点赞数/菜名。
    """
    likes: Dict[str, int] = {}
    for user in getattr(feedback, "_data", {}).values():
        for dish, count in (user.get("likes") or {}).items():
            likes[dish] = likes.get(dish, 0) + count
    favs: Dict[str, int] = {}
    for dishes in getattr(favorites, "_data", {}).values():
        for dish in dishes:
            favs[dish] = favs.get(dish, 0) + 1
    rows = [
        {
            "name": dish,
            "likes": likes.get(dish, 0),
            "favs": favs.get(dish, 0),
            "hot": likes.get(dish, 0) + FAV_HOT_WEIGHT * favs.get(dish, 0),
        }
        for dish in set(likes) | set(favs)
    ]
    rows.sort(key=lambda r: (-r["hot"], -r["likes"], r["name"]))
    return rows[:top]
