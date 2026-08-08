# -*- coding: utf-8 -*-
"""astrbot_plugin_soulsync_bistro - 心旅小馆：根据 SoulSync 情绪推荐美食

特性：
- 通过 AstrBot on_llm_response 钩子截取 LLM 回复文本，本地词典分析情绪并缓存快照
- /吃点啥 /菜谱搜索 /怎么做 /随机推荐 /心馆 状态 五个命令
- 全部菜谱本地存储（933 道，含详细步骤），运行时零网络
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, Optional

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

from .emotion_analyzer import analyze
from .recipe_engine import RecipeEngine

EMOTION_EMOJI = {
    "喜悦": "😊",
    "悲伤": "😢",
    "愤怒": "😠",
    "焦虑": "😟",
    "期待": "🤩",
    "平静": "😌",
}

EAT_WHAT_BARE_PATTERN = r"吃点啥|吃啥|吃什么"

HELP_TEXT = """🍽️ 心旅小馆 · 情绪美食推荐

/吃点啥 [分类]      推荐一份套餐（或指定分类的单菜）
/喝点啥             推荐一杯饮品
/解馋               推荐解馋小食（小吃/甜品/炸鸡）
/菜谱搜索 关键词    搜索菜谱库，标出「❤️此刻适配」
/怎么做 菜名        查看详细做法步骤
/随机推荐 [数量]    随机推荐，至少一道情绪特调
/心馆 状态          查看当前情绪快照

分类可用：素菜 / 荤菜 / 主食 / 汤 / 甜品 / 凉菜"""


class SoulSyncBistroPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}
        try:
            self.mood_ttl = max(1, int(self.config.get("mood_ttl_minutes", 30))) * 60
        except (TypeError, ValueError):
            self.mood_ttl = 30 * 60
        self.enable_mood = bool(self.config.get("enable_mood_link", True))
        self.max_search = self._clamp_int(self.config.get("max_search_results", 8), 1, 20)
        self.engine = RecipeEngine()
        self._mood_cache: Dict[str, tuple] = {}
        logger.info(
            f"心旅小馆已加载 | 菜谱 {self.engine.total()} 道 | "
            f"情绪联动={'开' if self.enable_mood else '关'} | 快照有效期 {self.mood_ttl // 60} 分钟"
        )

    @staticmethod
    def _clamp_int(v, lo, hi):
        try:
            return max(lo, min(hi, int(v)))
        except (TypeError, ValueError):
            return lo

    # ────────────────────── 钩子：截取 LLM 回复 ──────────────────────

    @filter.on_llm_response()
    async def on_llm_response(self, event: AstrMessageEvent, response):
        """截取 LLM 回复文本，分析情绪并缓存快照（线程安全足够：单写者）。"""
        if not self.enable_mood:
            return
        try:
            text = self._extract_text(response)
            if not text or len(text) < 2:
                return
            result = analyze(text)
            if result.emotion == "平静" and result.confidence < 0.3:
                return
            now = time.time()
            self._mood_cache["last"] = (
                result.emotion,
                result.confidence,
                text[:200],
                now,
            )
            logger.debug(f"心旅小馆: 情绪快照 {result.emotion} conf={result.confidence:.2f}")
        except Exception as e:
            logger.debug(f"心旅小馆: 情绪分析失败，跳过: {e}")

    @staticmethod
    def _extract_text(response) -> str:
        """从 AstrBot 的 LLM response 对象提取纯文本。"""
        if response is None:
            return ""
        if isinstance(response, str):
            return response
        chain = getattr(response, "result_chain", None)
        if chain is not None:
            texts = []
            for comp in getattr(chain, "chain", []) or []:
                t = getattr(comp, "text", None)
                if t:
                    texts.append(str(t))
            return "\n".join(texts)
        for attr in ("result", "text", "content", "message"):
            v = getattr(response, attr, None)
            if isinstance(v, str) and v:
                return v
        return str(response) if response else ""

    def _current_mood(self) -> Optional[dict]:
        """取最近一次情绪快照（含 TTL 检查）。"""
        cached = self._mood_cache.get("last")
        if not cached:
            return None
        emotion, confidence, snippet, ts = cached
        if time.time() - ts > self.mood_ttl:
            return None
        return {"emotion": emotion, "confidence": confidence, "snippet": snippet}

    # ────────────────────── 命令 ──────────────────────

    @filter.command("吃点啥", alias={"吃啥", "吃什么", "今天吃什么"})
    async def eat_what(self, event: AstrMessageEvent, category: str = ""):
        """按最近情绪推荐套餐（或指定分类的单菜）。用法：/吃点啥 [素菜|荤菜|主食|汤|甜品]"""
        mood = self._current_mood() if self.enable_mood else None
        emotion = mood["emotion"] if mood else "平静"
        category = category.strip()

        if category and category not in ("素菜", "荤菜", "主食", "汤", "甜品", "凉菜", "粥"):
            yield event.plain_result(
                f"分类「{category}」不认识哦，可用：素菜 / 荤菜 / 主食 / 汤 / 甜品 / 凉菜"
            )
            return

        mood_cfg = self.engine.mood_mapping.get(emotion, {})
        emoji = EMOTION_EMOJI.get(emotion, "")
        lines = [f"{emoji} 今日心情：{emotion}（{mood_cfg.get('label', '随缘')}）"]
        if mood and mood["snippet"]:
            lines.append(f"  SoulSync 说：「{mood['snippet'][:50]}…」")
        lines.append("")

        if category:
            recipe = self.engine.recommend_for_mood(emotion, category)
            if recipe is None:
                yield event.plain_result("菜谱库好像空了，请检查插件数据。")
                return
            lines.append(f"🍽️ 为你推荐：{recipe['name']}")
            lines.append(f"  分类：{recipe['category']} | 难度：{recipe['difficulty']}")
            ingredients = "、".join(recipe.get("ingredients", [])[:8])
            lines.append(f"  食材：{ingredients}")
            if recipe.get("spicy"):
                lines.append("  🌶️ 这道有点辣，正好")
            lines.append(f"  想看做法？发送 /怎么做 {recipe['name']}")
            yield event.plain_result("\n".join(lines))
            return

        meal = self.engine.recommend_meal(emotion)
        if meal is None:
            yield event.plain_result("菜谱库好像空了，请检查插件数据。")
            return

        lines.append("🍽️ 为你推荐套餐：")
        main = meal["main"]
        spicy = " 🌶️" if main.get("spicy") else ""
        lines.append(f"  主菜：{main['name']}（{main['category']}）{spicy}")
        if meal.get("staple"):
            lines.append(f"  主食：{meal['staple']['name']}（{meal['staple']['category']}）")
        if meal.get("side"):
            lines.append(f"  配菜：{meal['side']['name']}（{meal['side']['category']}）")
        if meal.get("dessert"):
            lines.append(f"  甜品：{meal['dessert']['name']}（{meal['dessert']['category']}）")
        if mood_cfg.get("reply"):
            lines.append(f"  {mood_cfg['reply']}")
        lines.append("  想看做法？发送 /怎么做 菜名")
        yield event.plain_result("\n".join(lines))

    def _bare_group_text(self, event: AstrMessageEvent) -> bool:
        """是否是无斜杠、不 @ 的群聊纯文本消息（用于无前缀触发）。"""
        if event.is_private_chat():
            return False
        messages = event.get_messages()
        if not messages:
            return False
        first = messages[0]
        first_type = getattr(first, "type", None)
        type_name = (getattr(first_type, "name", None) or str(first_type)).lower()
        if type_name != "plain":
            return False
        if str(getattr(first, "text", "") or "").lstrip().startswith("/"):
            return False
        return True

    @filter.regex(EAT_WHAT_BARE_PATTERN)
    async def eat_what_bare(self, event: AstrMessageEvent):
        """群聊中不带斜杠、不 @ 机器人时说「吃点啥/吃什么/吃啥」也能触发推荐。"""
        logger.info(
            f"心旅小馆: 无前缀触发命中 | 私聊={event.is_private_chat()} "
            f"消息={event.get_message_str()!r} 组件={getattr(event.get_messages()[0], 'type', '?') if event.get_messages() else '?'}"
        )
        if not self._bare_group_text(event):
            logger.info("心旅小馆: 无前缀触发被 _bare_group_text 拦截")
            return
        logger.info("心旅小馆: 无前缀触发放行，执行推荐")
        async for r in self.eat_what(event):
            yield r

    @filter.command("喝点啥", alias={"喝啥", "喝什么", "喝点什么", "想喝点啥"})
    async def drink_what(self, event: AstrMessageEvent):
        """按最近情绪推荐一杯饮品。用法：/喝点啥"""
        mood = self._current_mood() if self.enable_mood else None
        emotion = mood["emotion"] if mood else "平静"
        drink = self.engine.recommend_drink(emotion if emotion != "平静" else None)
        if drink is None:
            yield event.plain_result("饮品库好像空了，请检查插件数据。")
            return

        mood_cfg = self.engine.mood_mapping.get(emotion, {})
        emoji = EMOTION_EMOJI.get(emotion, "")
        lines = [f"{emoji} 今日心情：{emotion}（{mood_cfg.get('label', '随缘')}）"]
        if mood and mood["snippet"]:
            lines.append(f"  SoulSync 说：「{mood['snippet'][:50]}…」")
        lines.append("")
        lines.append(f"🥤 为你推荐饮品：{drink['name']}")
        ingredients = "、".join(drink.get("ingredients", [])[:8])
        lines.append(f"  食材：{ingredients}")
        if mood_cfg.get("reply"):
            lines.append(f"  {mood_cfg['reply']}")
        lines.append(f"  想看做法？发送 /怎么做 {drink['name']}")
        yield event.plain_result("\n".join(lines))

    @filter.regex(r"喝点啥|喝什么|喝啥")
    async def drink_what_bare(self, event: AstrMessageEvent):
        """群聊纯文本说「喝点啥/喝什么」也能触发饮品推荐。"""
        if not self._bare_group_text(event):
            return
        async for r in self.drink_what(event):
            yield r

    @filter.command("解馋", alias={"馋了", "嘴馋", "解解馋", "想吃零食"})
    async def snack_craving(self, event: AstrMessageEvent, count: int = 2):
        """按最近情绪推荐解馋小食（小吃/甜品/炸鸡）。用法：/解馋 [数量]"""
        mood = self._current_mood() if self.enable_mood else None
        emotion = mood["emotion"] if mood else "平静"
        picks = self.engine.recommend_snacks(
            count, emotion if emotion != "平静" else None
        )
        if not picks:
            yield event.plain_result("零食库好像空了，请检查插件数据。")
            return

        mood_cfg = self.engine.mood_mapping.get(emotion, {})
        emoji = EMOTION_EMOJI.get(emotion, "")
        lines = [f"{emoji} 今日心情：{emotion}（{mood_cfg.get('label', '随缘')}）"]
        if mood and mood["snippet"]:
            lines.append(f"  SoulSync 说：「{mood['snippet'][:50]}…」")
        lines.append("")
        lines.append(f"🍟 解馋推荐 {len(picks)} 样：")
        for r in picks:
            spicy = " 🌶️" if r.get("spicy") else ""
            lines.append(f"  · {r['name']}（{r['category']}）{spicy}")
        if mood_cfg.get("reply"):
            lines.append(f"  {mood_cfg['reply']}")
        lines.append("  想吃哪个？发送 /怎么做 名字")
        yield event.plain_result("\n".join(lines))

    @filter.regex(r"解馋|馋了|嘴馋")
    async def snack_craving_bare(self, event: AstrMessageEvent):
        """群聊纯文本说「解馋/馋了/嘴馋」也能触发小食推荐。"""
        if not self._bare_group_text(event):
            return
        async for r in self.snack_craving(event):
            yield r

    @filter.command("菜谱搜索", alias={"找菜"})
    async def search_recipe(self, event: AstrMessageEvent, keyword: str = ""):
        """搜索本地菜谱库。用法：/菜谱搜索 土豆"""
        keyword = keyword.strip()
        if not keyword:
            yield event.plain_result("告诉我搜什么，例如 /菜谱搜索 土豆")
            return
        results = self.engine.search(keyword, limit=self.max_search)
        if not results:
            yield event.plain_result(f"没找到和「{keyword}」相关的菜谱…试试别的关键词？")
            return

        mood = self._current_mood() if self.enable_mood else None
        emotion = mood["emotion"] if mood else "平静"
        mood_hit_names = {
            r["name"] for r in self.engine.match_mood(emotion)
        }

        lines = [f"🔍 找到 {len(results)} 道与「{keyword}」相关的菜："]
        for r in results:
            star = "❤️此刻适配" if r["name"] in mood_hit_names else ""
            mark = "（素）" if r.get("vegetarian") else ""
            lines.append(f"  · {r['name']}{mark} {star}")
        if mood and emotion != "平静":
            lines.append(f"（当前情绪：{emotion}，标❤️的与此刻情绪契合）")
        yield event.plain_result("\n".join(lines))

    @filter.command("怎么做", alias={"做法", "菜谱"})
    async def how_to_cook(self, event: AstrMessageEvent, name: str = ""):
        """显示一道菜的详细做法步骤。用法：/怎么做 宫保鸡丁"""
        name = name.strip()
        if not name:
            yield event.plain_result("告诉我菜名，例如 /怎么做 宫保鸡丁")
            return
        recipe = self.engine.find_by_name(name)
        if recipe is None:
            similar = self.engine.search(name, limit=3)
            if similar:
                names = "、".join(s["name"] for s in similar)
                yield event.plain_result(f"没找到「{name}」，要不要试试：{names}")
            else:
                yield event.plain_result(f"菜谱库中没有「{name}」这道菜。")
            return

        mood = self._current_mood() if self.enable_mood else None
        emotion = mood["emotion"] if mood else "平静"
        mood_cfg = self.engine.mood_mapping.get(emotion, {})

        lines = [f"👨‍🍳 {recipe['name']}"]
        lines.append(f"难度：{recipe['difficulty']} | 分类：{recipe['category']}")
        ingredients = "、".join(recipe.get("ingredients", []))
        lines.append(f"🛒 食材：{ingredients}")
        lines.append("")
        lines.append("📋 做法：")
        lines.append(self.engine.format_steps(recipe))
        lines.append("")
        if mood_cfg.get("reply"):
            lines.append(f"💬 {mood_cfg['reply']}")
        bv = recipe.get("bv")
        if bv:
            lines.append(f"🎬 视频参考：https://www.bilibili.com/video/{bv}")
        yield event.plain_result("\n".join(lines))

    @filter.command("随机推荐", alias={"随机菜", "吃什么好"})
    async def random_dish(self, event: AstrMessageEvent, count: int = 1):
        """随机推荐 N 道菜，至少一道为情绪特调。用法：/随机推荐 [数量]"""
        mood = self._current_mood() if self.enable_mood else None
        emotion = mood["emotion"] if mood else None
        picks = self.engine.random_recommend(count, emotion if emotion != "平静" else None)
        if not picks:
            yield event.plain_result("菜谱库为空。")
            return

        lines = [f"🎲 随机推荐 {len(picks)} 道："]
        for r in picks:
            star = " ⭐心选之作" if emotion and self.engine.is_mood_match(r, emotion) else ""
            lines.append(f"  · {r['name']}（{r['category']}）{star}")
        if emotion and emotion != "平静":
            lines.append(f"（情绪 {emotion} 适配的「心选之作」已混入其中）")
        lines.append("想看做法？发送 /怎么做 菜名")
        yield event.plain_result("\n".join(lines))

    @filter.command("心馆", alias={"心馆状态", "心情状态"})
    async def status(self, event: AstrMessageEvent, sub: str = "状态"):
        """查看 SoulSync 最近一次情绪快照与推荐摘要。用法：/心馆 状态"""
        mood = self._current_mood() if self.enable_mood else None
        if not mood:
            yield event.plain_result(
                "😌 还没有情绪快照。让 SoulSync 说句话，30 分钟内我都会记得～\n"
                "也可以直接 /吃点啥，我会随机推荐。"
            )
            return
        emotion = mood["emotion"]
        mood_cfg = self.engine.mood_mapping.get(emotion, {})
        lines = [
            f"{EMOTION_EMOJI.get(emotion, '')} 心馆状态",
            f"  当前情绪：{emotion}（置信度 {mood['confidence']:.0%}）",
            f"  情绪解读：{mood_cfg.get('label', '随缘')}",
            f"  SoulSync 原话：「{mood['snippet'][:80]}」",
        ]
        if mood_cfg.get("reply"):
            lines.append(f"  心选方向：{mood_cfg['reply']}")
        recipe = self.engine.recommend_for_mood(emotion)
        if recipe:
            lines.append(f"  此刻适配：{recipe['name']}")
            lines.append(f"  想看做法？发送 /怎么做 {recipe['name']}")
        yield event.plain_result("\n".join(lines))
