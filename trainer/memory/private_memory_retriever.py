"""SoulSync - 私人记忆：检索引擎（排序/预算裁剪/格式化）"""
import time
from ..trainer_types import PrivateMemoryStore

NEGATIVE_WORDS = ["难过", "伤心", "生气", "愤怒", "委屈", "失望", "害怕", "焦虑", "哭", "后悔", "吵架"]
SWEET_WORDS = ["幸福", "甜蜜", "开心", "快乐", "温暖", "浪漫", "心动", "美好", "喜欢", "满足"]


class PrivateMemoryRetriever:
    def retrieve(self, store: PrivateMemoryStore, context: dict = None, max_items: int = 5, budget: int = 120) -> list:
        if not store:
            return []
        all_mems = []
        for lst in [store.text, store.images, store.promises, store.emotional]:
            all_mems.extend(lst)

        scored = []
        now = time.time()
        today = time.strftime("%Y-%m-%d")
        persona = (context or {}).get("persona", {})
        grudge = persona.get("grudge_coefficient", 1.0)
        romantic = persona.get("romantic_memory_weight", 1.0)
        forget = persona.get("forget_speed", 1.0)

        for mem in all_mems:
            if mem.sensitive and not (context and context.get("exact_match")):
                continue
            score = 0
            if mem.id in store.starred:
                score += 1000
            if mem.date == today:
                score += 500
            if context:
                kw = context.get("keywords", "").lower()
                if kw and kw in mem.content.lower():
                    score += 200
                if kw and any(kw in t.lower() for t in mem.tags):
                    score += 100
            score += mem.importance * 10
            score -= mem.access_count * 2
            if mem.last_accessed > 0:
                days_since = (now - mem.last_accessed) / 86400
                score += max(0, 30 - days_since * forget)
            if mem.type == "emotional":
                tone = (mem.mood or "") + "".join(mem.emotion_tags)
                if any(w in tone for w in NEGATIVE_WORDS):
                    score += (grudge - 1.0) * 100
                if any(w in tone for w in SWEET_WORDS):
                    score += (romantic - 1.0) * 100
            scored.append((score, mem))

        scored.sort(key=lambda x: -x[0])
        results = [mem for _, mem in scored[:max_items]]
        for mem in results:
            mem.access_count += 1
            mem.last_accessed = now
        return results

    def format_for_llm(self, memories: list) -> str:
        if not memories:
            return ""
        lines = ["[私人记忆·相关片段]"]
        for mem in memories[:3]:
            star = "⭐ " if getattr(mem, 'id', '') in getattr(mem, '_starred_ids', []) else ""
            tag_str = f" [{', '.join(mem.tags[:3])}]" if mem.tags else ""
            mood_str = f" ({mem.mood})" if mem.mood else ""
            lines.append(f"  {star}{mem.date}: {mem.content[:60]}{mood_str}{tag_str}")
        return "\n".join(lines)

    @staticmethod
    def _find_by_id(store: PrivateMemoryStore, mem_id: str):
        for lst in [store.text, store.images, store.promises, store.emotional]:
            for m in lst:
                if m.id == mem_id:
                    return m
        return None