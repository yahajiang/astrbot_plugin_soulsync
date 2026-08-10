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
        "ing_flat": [],
        "ing_bigram": defaultdict(set),
        "ing_char1": defaultdict(set),
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
        # v1.8：食材反查索引（归一化食材名列表 + 食材名 bigram → 菜 id 集）
        ing_norm = []
        for ing in r.get("ingredients", []):
            base = _parse_ingredient(ing)
            if base is None:
                continue
            norm = _norm_ingredient_name(base)
            ing_norm.append((base, norm))
            if len(norm) == 1:
                pack["ing_char1"][norm].add(i)
            for b in _bigrams(norm):
                pack["ing_bigram"][b].add(i)
        pack["ing_flat"].append(ing_norm)

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

# 饮品名称关键词（用于识别未打「饮品」tag 的存量菜谱）
DRINK_KEYWORDS = (
    "奶茶", "咖啡", "奶昔", "果汁", "豆浆", "酸梅汤", "凉茶", "冰沙",
    "莫吉托", "mojito", "气泡水", "水果茶", "热巧克力", "姜撞奶",
    "双皮奶", "酒酿", "杨枝甘露", "糖水", "果茶", "花茶", "冬瓜茶",
    "酸奶饮料", "绿豆汤", "红豆汤", "蜂蜜柠檬", "抹茶拿铁",
)

# 解馋（零食/小吃）标签判定
SNACK_TAGS = ("小吃", "零食", "炸物", "甜品", "烧烤", "糖水", "糕点", "面包")

# 时间推荐：时段标签
TIME_TAGS = {
    "早餐": ("早餐", "早点"),
    "夜宵": ("夜宵", "宵夜", "烧烤", "小吃"),
}

# 食材反查：别名 → 规范词（精确匹配/后缀匹配，从长到短）
INGREDIENT_ALIASES = {
    "西红柿": "番茄",
    "洋芋": "土豆", "马铃薯": "土豆",
    "柿子椒": "青椒", "甜椒": "青椒", "灯笼椒": "青椒",
    "尖椒": "辣椒", "线椒": "辣椒", "小米辣": "辣椒",
    "芫荽": "香菜",
    "五花肉": "猪肉", "猪五花": "猪肉", "里脊肉": "猪肉", "猪里脊": "猪肉",
    "猪瘦肉": "猪肉", "瘦肉": "猪肉", "梅花肉": "猪肉",
    "鸡胸肉": "鸡肉", "鸡腿肉": "鸡肉", "鸡翅": "鸡肉", "鸡翅中": "鸡肉",
    "鸡翅根": "鸡肉", "鸡腿": "鸡肉",
    "牛里脊": "牛肉", "牛腩": "牛肉", "肥牛": "牛肉", "牛腱子": "牛肉",
    "鲜虾": "虾", "虾仁": "虾", "基围虾": "虾", "大明虾": "虾", "大虾": "虾",
    "小麦粉": "面粉", "中筋面粉": "面粉", "高筋面粉": "面粉", "低筋面粉": "面粉",
    "嫩豆腐": "豆腐", "老豆腐": "豆腐", "北豆腐": "豆腐", "南豆腐": "豆腐",
    "内酯豆腐": "豆腐",
    "冬菇": "香菇", "花菇": "香菇",
    "黑木耳": "木耳", "云耳": "木耳",
    "花生仁": "花生", "花生米": "花生",
    "上海青": "青菜", "油菜": "青菜", "小白菜": "青菜",
    "红萝卜": "胡萝卜",
    "生粉": "淀粉", "玉米淀粉": "淀粉", "土豆淀粉": "淀粉", "红薯淀粉": "淀粉",
    "生抽": "酱油", "老抽": "酱油",
    "陈醋": "醋", "香醋": "醋", "米醋": "醋", "白醋": "醋",
    "黄酒": "料酒", "米酒": "料酒",
    "白砂糖": "糖", "绵白糖": "糖",
    "菜籽油": "油", "花生油": "油", "橄榄油": "油", "玉米油": "油",
    "葵花籽油": "油", "大豆油": "油", "食用油": "油", "色拉油": "油",
    "香油": "芝麻油", "麻油": "芝麻油",
    "生姜": "姜", "大蒜": "蒜", "香葱": "葱", "小葱": "葱", "大葱": "葱",
    "瑶柱": "干贝", "元贝": "干贝",
    "车厘子": "樱桃",
}

# 食材反查：基础调味料豁免（默认家家有，缺了不算缺）
BASIC_CONDIMENTS = frozenset(
    (
        "盐", "白糖", "白砂糖", "绵白糖", "红糖", "冰糖",
        "酱油", "生抽", "老抽", "蚝油", "味极鲜",
        "料酒", "黄酒", "米酒", "醋", "陈醋", "香醋", "米醋", "白醋",
        "油", "食用油", "菜籽油", "花生油", "橄榄油", "玉米油", "葵花籽油",
        "大豆油", "猪油", "黄油", "芝麻油", "香油", "麻油", "辣椒油", "花椒油",
        "淀粉", "生粉", "玉米淀粉", "土豆淀粉", "红薯淀粉",
        "鸡精", "味精", "鸡粉", "胡椒粉", "白胡椒粉", "黑胡椒",
        "花椒", "花椒粉", "八角", "桂皮", "香叶", "草果", "丁香", "孜然", "茴香",
        "姜", "生姜", "蒜", "大蒜", "葱", "小葱", "大葱", "香葱",
        "水", "清水", "热水", "温水", "开水", "纯净水", "高汤",
        "芝麻", "白芝麻", "黑芝麻", "豆瓣酱", "甜面酱", "番茄酱", "豆豉",
    )
)


def _norm_ingredient_name(name: str) -> str:
    """食材别名归一到规范词（精确/后缀匹配，长别名优先）。"""
    for alias in sorted(INGREDIENT_ALIASES, key=len, reverse=True):
        if name == alias or name.endswith(alias):
            return INGREDIENT_ALIASES[alias]
    return name


def _parse_ingredient(ing) -> Optional[str]:
    """食材项（如「里脊肉 200.0g」）→ 食材名；空/调味料返回 None。"""
    name = str(ing).strip().split()[0].strip()
    if not name or name in BASIC_CONDIMENTS:
        return None
    return name


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
        self._ing_flat: List[List[Tuple[str, str]]] = pack["ing_flat"]
        self._ing_bigram = pack["ing_bigram"]
        self._ing_char1 = pack["ing_char1"]
        self._name_hits_cache: Dict[str, Set[int]] = {}
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

    def _exclude(self, pool: List[Dict], exclude_names: Optional[set]) -> List[Dict]:
        """从候选池剔除近期推荐过的菜名；剔除后为空则回退原池。"""
        if not exclude_names:
            return pool
        kept = [r for r in pool if r.get("name") not in exclude_names]
        return kept or pool

    def _choose(self, pool: List[Dict], weight_func=None) -> Dict:
        """从池中选一道：无权重时均匀随机；有权重时按权重抽样（分数<=0 时给 0.01 保底）。"""
        if not pool:
            raise ValueError("empty pool")
        if weight_func is None:
            return self._rng.choice(pool)
        weights = [max(weight_func(r), 0.01) for r in pool]
        return self._rng.choices(pool, weights=weights, k=1)[0]

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

    def recommend_for_mood(
        self,
        emotion: str,
        category: Optional[str] = None,
        exclude_names: Optional[set] = None,
        weight_func=None,
    ) -> Optional[Dict]:
        """按情绪推荐一道菜，可附加分类限制；无匹配（如平静/未知情绪）时回退随机。

        exclude_names: 近期推荐去重；weight_func: 按个人反馈分加权抽样。
        """
        pool = self.match_mood(emotion)
        if category:
            pool = [r for r in pool if self._in_category(r, category)] or self.filter_category(category)
        pool = self._exclude(pool, exclude_names)
        if not pool:
            pool = self.filter_category(category) if category else self.recipes
        if not pool:
            return None
        return self._choose(pool, weight_func)

    def random_recommend(
        self, count: int, emotion: Optional[str] = None,
        exclude_names: Optional[set] = None, weight_func=None,
    ) -> List[Dict]:
        """随机推荐 count 道；若给定情绪，保证至少一道为该情绪适配菜。"""
        count = max(1, min(int(count), 10))
        pool_all = self._exclude(self.recipes, exclude_names)
        mood_pick = None
        if emotion:
            pool = [r for r in pool_all if self.is_mood_match(r, emotion)]
            if not pool:
                pool = [r for r in self.match_mood(emotion) if r in pool_all]
            if pool:
                mood_pick = self._choose(pool, weight_func)
        others = [r for r in pool_all if r is not mood_pick]
        picks = self._rng.sample(others, min(count - (1 if mood_pick else 0), len(others)))
        result = ([mood_pick] if mood_pick else []) + picks
        return result[:count]

    # ────────────────────── 饮品 / 解馋 / 套餐 ──────────────────────

    def is_drink(self, recipe: Dict) -> bool:
        """判断是否饮品：优先「饮品」tag，兜底按名称关键词。"""
        if any(str(t) == "饮品" for t in recipe.get("tags") or []):
            return True
        name = str(recipe.get("name", "")).lower()
        return any(kw in name for kw in DRINK_KEYWORDS)

    def drink_pool(self) -> List[Dict]:
        """全部饮品候选（分类限甜品零食类，排除主食/菜肴误判）。"""
        return [r for r in self.recipes if self.is_drink(r)]

    def recommend_drink(
        self, emotion: Optional[str] = None,
        exclude_names: Optional[set] = None, weight_func=None,
    ) -> Optional[Dict]:
        """按情绪推荐饮品；无情绪或未命中时回退随机饮品。"""
        pool = self._exclude(self.drink_pool(), exclude_names)
        if not pool:
            return None
        if emotion:
            mood_pool = [r for r in pool if self.is_mood_match(r, emotion)]
            if mood_pool:
                return self._choose(mood_pool, weight_func)
        return self._choose(pool, weight_func)

    def is_snack(self, recipe: Dict) -> bool:
        """判断是否解馋零食：甜品零食分类或命中零食标签。"""
        if recipe.get("category") == "甜品零食":
            return True
        tags = [str(t).lower() for t in recipe.get("tags") or []]
        return any(t in SNACK_TAGS for t in tags)

    def snack_pool(self) -> List[Dict]:
        return [r for r in self.recipes if self.is_snack(r)]

    def recommend_snacks(
        self, count: int, emotion: Optional[str] = None,
        exclude_names: Optional[set] = None, weight_func=None,
    ) -> List[Dict]:
        """随机推荐 count 样解馋零食；给定情绪时优先情绪适配。"""
        pool = self._exclude(self.snack_pool(), exclude_names)
        if not pool:
            return []
        count = max(1, min(int(count), 6))
        if emotion:
            mood_pool = [r for r in pool if self.is_mood_match(r, emotion)]
            if mood_pool:
                first = self._choose(mood_pool, weight_func)
                rest = [r for r in pool if r is not first]
                picks = self._rng.sample(rest, min(count - 1, len(rest)))
                return [first] + picks
        return self._rng.sample(pool, min(count, len(pool)))

    def recommend_meal(
        self, emotion: Optional[str] = None,
        exclude_names: Optional[set] = None, weight_func=None,
    ) -> Optional[Dict]:
        """推荐套餐：情绪主菜 + 主食 + 配菜（汤/凉菜）+ 甜品。"""
        meal = {}
        main = self.recommend_for_mood(emotion or "平静", exclude_names=exclude_names, weight_func=weight_func)
        if main is None:
            return None
        meal["main"] = main

        staple_pool = self._exclude(
            [r for r in self.recipes if r.get("category") == "主食"], exclude_names
        )
        if staple_pool:
            meal["staple"] = self._choose(staple_pool, weight_func)

        side_pool = self._exclude(
            [
                r for r in self.recipes
                if r.get("category") in ("汤羹", "凉菜") and r is not main
            ],
            exclude_names,
        )
        if side_pool:
            meal["side"] = self._choose(side_pool, weight_func)

        dessert_pool = self._exclude(
            [
                r for r in self.recipes
                if r.get("category") == "甜品零食" and r is not main
            ],
            exclude_names,
        )
        if dessert_pool:
            meal["dessert"] = self._choose(dessert_pool, weight_func)
        return meal

    # ────────────────────── 时间推荐 ──────────────────────

    @staticmethod
    def period_by_hour(hour: int) -> str:
        """按小时（0-23）返回时段名：早餐/午餐/下午茶/晚餐/夜宵。"""
        h = hour % 24
        if 5 <= h < 11:
            return "早餐"
        if 11 <= h < 14:
            return "午餐"
        if 14 <= h < 17:
            return "下午茶"
        if 17 <= h < 21:
            return "晚餐"
        return "夜宵"

    def _pick_mood(
        self, pool: List[Dict], emotion: Optional[str],
        exclude_names: Optional[set] = None, weight_func=None,
    ) -> Dict:
        """从候选池挑一道：情绪适配优先，否则随机；支持去重与加权。"""
        if emotion:
            mood_pool = self._exclude(
                [r for r in pool if self.is_mood_match(r, emotion)], exclude_names
            )
            if mood_pool:
                return self._choose(mood_pool, weight_func)
        return self._choose(self._exclude(pool, exclude_names), weight_func)

    def _tag_pool(self, tags: Tuple[str, ...]) -> List[Dict]:
        lowered = {t.lower() for t in tags}
        return [
            r for r in self.recipes
            if any(str(t).lower() in lowered for t in (r.get("tags") or []))
        ]

    def recommend_by_time(
        self, hour: int, emotion: Optional[str] = None,
        exclude_names: Optional[set] = None, weight_func=None,
    ) -> Optional[Dict]:
        """按小时推荐：返回 {"period": 时段名, "meal": {main/staple/side/soup}}。

        早餐→粥面早餐池；午餐/晚餐→荤素主食汤套餐；下午茶→甜品饮品；
        夜宵→夜宵小吃烧烤池。标签优先、分类兜底、情绪参与。
        """
        period = self.period_by_hour(hour)
        meal = {}

        if period == "早餐":
            pool = self._tag_pool(TIME_TAGS["早餐"])
            if not pool:
                pool = [
                    r for r in self.recipes
                    if r.get("category") in ("主食", "粥羹", "汤羹")
                ]
            if not pool:
                return None
            meal["main"] = self._pick_mood(pool, emotion, exclude_names, weight_func)
            staple = self._exclude(
                [r for r in self.recipes if r.get("category") in ("主食", "粥羹")],
                exclude_names,
            )
            if staple and staple[0] is not meal["main"]:
                meal["staple"] = self._choose(staple, weight_func)
            drinks = self._exclude(self.drink_pool(), exclude_names)
            if drinks and drinks[0] is not meal["main"]:
                meal["side"] = self._choose(drinks, weight_func)

        elif period in ("午餐", "晚餐"):
            mains = self._exclude(
                [r for r in self.recipes if r.get("category") == "荤菜"], exclude_names
            )
            if not mains:
                return None
            meal["main"] = self._pick_mood(mains, emotion, exclude_names, weight_func)
            staples = self._exclude(
                [r for r in self.recipes if r.get("category") == "主食"], exclude_names
            )
            if staples:
                meal["staple"] = self._choose(staples, weight_func)
            sides = self._exclude(
                [
                    r for r in self.recipes
                    if r.get("category") in ("素菜", "凉菜") and r is not meal["main"]
                ],
                exclude_names,
            )
            if sides:
                meal["side"] = self._choose(sides, weight_func)
            soups = self._exclude(
                [
                    r for r in self.recipes
                    if r.get("category") == "汤羹" and r is not meal["main"]
                ],
                exclude_names,
            )
            if soups:
                meal["soup"] = self._choose(soups, weight_func)

        elif period == "下午茶":
            sweets = [r for r in self.recipes if r.get("category") == "甜品零食"]
            drinks = self.drink_pool()
            pool = self._exclude(sweets + drinks, exclude_names)
            if not pool:
                return None
            meal["main"] = self._pick_mood(pool, emotion, exclude_names, weight_func)
            others = self._exclude([r for r in pool if r is not meal["main"]], exclude_names)
            if others:
                meal["side"] = self._choose(others, weight_func)

        else:  # 夜宵
            pool = self._tag_pool(TIME_TAGS["夜宵"])
            if not pool:
                pool = [
                    r for r in self.recipes
                    if r.get("category") in ("甜品零食", "主食", "汤羹")
                ]
            if not pool:
                return None
            meal["main"] = self._pick_mood(pool, emotion, exclude_names, weight_func)

        return {"period": period, "meal": meal}

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

    # ────────────────────── 食材反查 ──────────────────────

    @staticmethod
    def _norm_ingredient(name: str) -> str:
        """食材别名归一到规范词（精确/后缀匹配，长别名优先）。"""
        return _norm_ingredient_name(name)

    def name_hits(self, kw: str) -> Set[int]:
        """按关键词返回命中菜索引集（名称+食材全文，与忌口判定口径一致，懒缓存）。"""
        cache = self._name_hits_cache
        hits = cache.get(kw)
        if hits is None:
            hits = {
                i
                for i in range(len(self._names))
                if kw in self._names[i] or kw in self._ing_texts[i]
            }
            cache[kw] = hits
        return hits

    def _ingredient_candidates(self, have_norm: List[str]) -> Set[int]:
        """手头食材 → 候选菜索引集：bigram 并集 + 1 字食材补充（1 字查询回落字符索引）。

        并集 + ing_char1 保证不因候选缩窄漏收（如「山楂干」需召回仅含「山楂」的菜、
        「面粉」需召回仅含 1 字食材「面」的菜）；候选多收无害，由判定兜底过滤。
        """
        cand: Set[int] = set()
        for hn in have_norm:
            if len(hn) >= 2:
                for b in _bigrams(hn):
                    cand |= self._ing_bigram.get(b, set())
                for c in hn:
                    cand |= self._ing_char1.get(c, set())
            else:
                cand |= self._char_index.get(hn, set())
                cand |= self._ing_char1.get(hn, set())
        if not cand:
            return set(range(len(self.recipes)))
        return cand

    def match_by_ingredients(
        self, have: List[str], limit: int = 8
    ) -> List[Dict]:
        """按手头食材反查可做菜：返回按覆盖度降序的匹配列表。

        每项 {"recipe", "owned", "missing", "coverage"}；基础调味料不计入
        缺失，缺 >3 项或覆盖度 <0.5 的菜不展示。
        """
        have = [h.strip() for h in have if h and h.strip()]
        if not have:
            return []
        have_norm = [self._norm_ingredient(h) for h in have]
        results = []
        for i in sorted(self._ingredient_candidates(have_norm)):
            needed = self._ing_flat[i]
            if not needed:
                continue
            owned, missing = [], []
            for name, norm in needed:
                if any(norm == hn or hn in norm or norm in hn for hn in have_norm):
                    owned.append(name)
                else:
                    missing.append(name)
            if not owned or len(missing) > 3:
                continue
            coverage = len(owned) / len(needed)
            if coverage < 0.5:
                continue
            results.append(
                {
                    "recipe": self.recipes[i],
                    "owned": owned,
                    "missing": missing,
                    "coverage": coverage,
                }
            )
        results.sort(key=lambda m: (-m["coverage"], len(m["missing"]), -len(m["owned"])))
        return results[:limit]
