# -*- coding: utf-8 -*-
"""菜谱引擎：搜索、分类过滤、情绪映射推荐、随机推荐。

数据源为插件内置 recipes.json（本地，无网络）。所有方法不依赖 AstrBot 环境，
便于单元测试。

性能设计（933 道全量数据）：
- 模块级 _read_json 缓存 JSON 解析结果，重复构造引擎不重复解析
- 加载时构建字符 bigram 倒排索引（名称/全文），搜索先取交集候选再精确校验
- 情绪索引（emotion -> id 集）、mood_mapping 关键词命中集、标签索引均预计算
- search / match_mood 结果 LRU 缓存（纯函数，随机方法不缓存）
"""

from __future__ import annotations

import json
import random
import re
from collections import OrderedDict, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RECIPES_PATH = BASE_DIR / "recipes.json"
DEFAULT_MOOD_PATH = BASE_DIR / "mood_mapping.json"

SEARCH_CACHE_MAX = 512


@lru_cache(maxsize=16)
def _read_json(path: str) -> object:
    """带缓存的 JSON 读取；返回共享只读对象，调用方不得修改。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=16)
def _build_index_pack(recipes_key: str, mood_key: str) -> Dict:
    """一次性构建索引包（倒排 bigram / 情绪 / 关键词 / 标签）。

    键为数据文件路径；同一路径的引擎实例共享同一份只读索引。
    """
    recipes = _read_json(recipes_key)
    mood_mapping = _read_json(mood_key)
    pack: Dict = {
        "names": [],
        "tags_texts": [],
        "ing_texts": [],
        "search_texts": [],
        "name_bigram": defaultdict(set),
        "text_bigram": defaultdict(set),
        "char_index": defaultdict(set),
        "tag_index": defaultdict(set),
        "mood_hint_index": defaultdict(set),
        "id2idx": {},
        "mood_keyword_hits": {},
    }

    for i, r in enumerate(recipes):
        pack["id2idx"][id(r)] = i
        name = str(r.get("name", "")).lower()
        tags = [str(x).lower() for x in r.get("tags", [])]
        ingredients = [str(x) for x in r.get("ingredients", [])]
        tags_t = " ".join(tags)
        ing_t = " ".join(ingredients)
        text = (name + " " + tags_t + " " + ing_t).lower()
        pack["names"].append(name)
        pack["tags_texts"].append(tags_t)
        pack["ing_texts"].append(ing_t)
        pack["search_texts"].append(text)
        for c in text:
            pack["char_index"][c].add(i)
        for b in _bigrams(name):
            pack["name_bigram"][b].add(i)
        for b in _bigrams(text):
            pack["text_bigram"][b].add(i)
        for t in tags:
            pack["tag_index"][t].add(i)
        for m in r.get("mood_hint") or []:
            pack["mood_hint_index"][m].add(i)

    # mood_mapping 关键词 -> 命中 id 集（与 match_mood 的判定完全一致）
    if isinstance(mood_mapping, dict):
        for emotion, cfg in mood_mapping.items():
            for kw in cfg.get("keywords", []):
                kw_l = str(kw).lower()
                if not kw_l:
                    continue
                hits = {
                    i for i, t in enumerate(pack["search_texts"]) if kw_l in t
                }
                pack["mood_keyword_hits"][(emotion, kw_l)] = hits
    return pack


def _bigrams(text: str) -> List[str]:
    return [text[k:k + 2] for k in range(len(text) - 1)]

# 素菜关键词判定（辅助，数据中已有 vegetarian 字段）
VEGETARIAN_CATEGORIES = ("素菜",)

# 分类别名 → 引擎内部分类
CATEGORY_ALIASES = {
    "素菜": "素菜",
    "蔬菜": "素菜",
    "素食": "素菜",
    "荤菜": "荤菜",
    "肉菜": "荤菜",
    "肉": "荤菜",
    "主食": "主食",
    "饭": "主食",
    "面": "主食",
    "汤": "汤羹",
    "汤羹": "汤羹",
    "粥": "粥羹",
    "粥羹": "粥羹",
    "甜品": "甜品零食",
    "零食": "甜品零食",
    "甜点": "甜品零食",
    "凉菜": "凉菜",
    "冷菜": "凉菜",
    "小吃": "甜品零食",
    "早餐": "早餐",
    "早饭": "早餐",
}

NON_FOOD_KEYWORDS = (
    "的做法", "怎么做", "如何做", "家常做法", "菜谱", "食谱", "大全",
    "配方", "教程", "视频", "做法大全", "怎么弄", "怎么烧", "怎么煮",
    "做法步骤", "详细做法", "最正宗",
)


class RecipeEngine:
    """菜谱加载、检索与推荐引擎"""

    def __init__(
        self,
        recipes_path: Optional[Path] = None,
        mood_path: Optional[Path] = None,
        seed: Optional[int] = None,
    ):
        self.recipes: List[Dict] = []
        self.mood_mapping: Dict[str, Dict] = {}
        self._rng = random.Random(seed) if seed is not None else random
        recipes_key = str(recipes_path or DEFAULT_RECIPES_PATH)
        mood_key = str(mood_path or DEFAULT_MOOD_PATH)
        self._load(recipes_key, mood_key)
        pack = _build_index_pack(recipes_key, mood_key)
        self._names: List[str] = pack["names"]
        self._tags_texts: List[str] = pack["tags_texts"]
        self._ing_texts: List[str] = pack["ing_texts"]
        self._search_texts: List[str] = pack["search_texts"]
        self._name_bigram = pack["name_bigram"]
        self._text_bigram = pack["text_bigram"]
        self._char_index = pack["char_index"]
        self._tag_index = pack["tag_index"]
        self._mood_hint_index = pack["mood_hint_index"]
        self._id2idx = pack["id2idx"]
        self._mood_keyword_hits = pack["mood_keyword_hits"]
        self._search_cache: "OrderedDict[str, Tuple]" = OrderedDict()
        self._mood_cache: Dict[str, Tuple] = {}

    def _load(self, recipes_key: str, mood_key: str):
        try:
            data = _read_json(recipes_key)
            self.recipes = data if isinstance(data, list) else data.get("recipes", [])
        except Exception:
            self.recipes = []
        try:
            self.mood_mapping = _read_json(mood_key)
        except Exception:
            self.mood_mapping = {}

    # ────────────────────── 候选集 ──────────────────────

    def _candidate_ids(self, kw: str) -> Set[int]:
        """bigram 交集得到候选 id 集；候选为空（兜底）回退全量。"""
        if len(kw) == 1:
            return set(self._char_index.get(kw, ()))
        bgs = _bigrams(kw)
        name_cand = set(self._name_bigram.get(bgs[0], ()))
        for b in bgs[1:]:
            name_cand &= set(self._name_bigram.get(b, ()))
        text_cand = set(self._text_bigram.get(bgs[0], ()))
        for b in bgs[1:]:
            text_cand &= set(self._text_bigram.get(b, ()))
        cand = name_cand | text_cand
        return cand or set(range(len(self.recipes)))

    def _cache_search(self, key: str, value: Tuple):
        self._search_cache[key] = value
        self._search_cache.move_to_end(key)
        while len(self._search_cache) > SEARCH_CACHE_MAX:
            self._search_cache.popitem(last=False)

    # ────────────────────── 基础查询 ──────────────────────

    def total(self) -> int:
        return len(self.recipes)

    def search(self, keyword: str, limit: int = 10) -> List[Dict]:
        """按名称/食材/标签/分类模糊搜索，返回前 limit 条。"""
        kw = self._clean_keyword(keyword)
        if not kw:
            return []
        cached = self._search_cache.get(kw)
        if cached is not None:
            self._search_cache.move_to_end(kw)
            return list(cached[:limit])
        hits = []
        for i in sorted(self._candidate_ids(kw)):
            r = self.recipes[i]
            name = self._names[i]
            if name.strip() == kw:
                hits.append((3, r))
                continue
            if kw in name:
                hits.append((2, r))
                continue
            if kw in self._ing_texts[i] or kw in self._tags_texts[i]:
                hits.append((1, r))
        hits.sort(key=lambda x: -x[0])
        result = tuple(r for _, r in hits)
        self._cache_search(kw, result)
        return list(result[:limit])

    def find_by_name(self, name: str) -> Optional[Dict]:
        """精确（或近似）查找一道菜。"""
        target = name.strip().lower()
        if not target:
            return None
        for r in self.recipes:
            if str(r.get("name", "")).strip().lower() == target:
                return r
        # 模糊：包含关系
        for r in self.recipes:
            rn = str(r.get("name", "")).strip().lower()
            if target in rn or rn in target:
                return r
        return None

    def filter_category(self, category: str) -> List[Dict]:
        """按分类/别名过滤，返回全部匹配。"""
        cat = CATEGORY_ALIASES.get(category.strip().lower())
        if cat is None:
            return []
        if cat in VEGETARIAN_CATEGORIES:
            return [r for r in self.recipes if r.get("vegetarian", False)]
        return [r for r in self.recipes if r.get("category") == cat]

    # ────────────────────── 情绪推荐 ──────────────────────

    def is_mood_match(self, recipe: Dict, emotion: str) -> bool:
        """判断一道菜是否标注了给定情绪（索引 O(1)，未索引对象回退线性）。"""
        if not emotion:
            return False
        idx = self._id2idx.get(id(recipe))
        if idx is not None:
            return idx in self._mood_hint_index.get(emotion, ())
        return emotion in (recipe.get("mood_hint") or [])

    def match_mood(self, emotion: str) -> List[Dict]:
        """根据情绪返回候选菜（按 mood_hint 字段 + mood_mapping 关键词打分）。"""
        mood_cfg = self.mood_mapping.get(emotion)
        if not mood_cfg:
            return []
        cached = self._mood_cache.get(emotion)
        if cached is not None:
            return list(cached)
        keywords = [str(k).lower() for k in mood_cfg.get("keywords", [])]
        tags = [str(t).lower() for t in mood_cfg.get("tags", [])]

        hint_ids = self._mood_hint_index.get(emotion, ())
        candidates: Set[int] = set(hint_ids)
        for kw in keywords:
            candidates |= self._mood_keyword_hits.get((emotion, kw), set())
        for t in tags:
            candidates |= self._tag_index.get(t, set())

        scored = []
        for i in sorted(candidates):
            r = self.recipes[i]
            score = 3 if i in hint_ids else 0
            text = self._search_texts[i]
            for kw in keywords:
                if kw in text:
                    score += 1
            for t in tags:
                if i in self._tag_index.get(t, ()):
                    score += 2
            if score > 0:
                scored.append((score, r))
        scored.sort(key=lambda x: -x[0])
        result = tuple(r for _, r in scored)
        self._mood_cache[emotion] = result
        return list(result)

    def recommend_for_mood(self, emotion: str, category: Optional[str] = None) -> Optional[Dict]:
        """按情绪推荐一道菜，可附加分类限制；无匹配（如平静/未知情绪）时回退随机。"""
        pool = self.match_mood(emotion)
        if category:
            pool = [r for r in pool if self._in_category(r, category)] or self.filter_category(category)
        if not pool:
            pool = self.filter_category(category) if category else self.recipes
        if not pool:
            return None
        return self._rng.choice(pool)

    def random_recommend(
        self, count: int, emotion: Optional[str] = None
    ) -> List[Dict]:
        """随机推荐 count 道；若给定情绪，保证至少一道为该情绪适配菜。"""
        count = max(1, min(int(count), 10))
        mood_pick = None
        if emotion:
            pool = [self.recipes[i] for i in self._mood_hint_index.get(emotion, ())]
            if not pool:
                pool = self.match_mood(emotion)
            if pool:
                mood_pick = self._rng.choice(pool)
        others = [r for r in self.recipes if r is not mood_pick]
        picks = self._rng.sample(others, min(count - (1 if mood_pick else 0), len(others)))
        result = ([mood_pick] if mood_pick else []) + picks
        return result[:count]

    # ────────────────────── 辅助 ──────────────────────

    @staticmethod
    def _clean_keyword(kw: str) -> str:
        kw = (kw or "").strip().lower()
        for token in NON_FOOD_KEYWORDS:
            kw = kw.replace(token, "")
        return kw.strip()

    @staticmethod
    def _in_category(r: Dict, category: str) -> bool:
        cat = CATEGORY_ALIASES.get(category.strip().lower())
        if cat is None:
            return False
        if cat in VEGETARIAN_CATEGORIES:
            return bool(r.get("vegetarian", False))
        return r.get("category") == cat

    def format_steps(self, recipe: Dict) -> str:
        steps = recipe.get("steps") or []
        lines = []
        for i, s in enumerate(steps, 1):
            s = str(s).strip()
            if not s:
                continue
            s = re.sub(r"^步骤\s*\d+[\.、:：]?\s*", "", s)
            lines.append(f"{i}. {s}")
        return "\n".join(lines)
