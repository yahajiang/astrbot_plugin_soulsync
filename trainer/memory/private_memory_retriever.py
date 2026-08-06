"""SoulSync - 私人记忆：检索引擎"""
from ..trainer_types import PrivateMemoryStore


class PrivateMemoryRetriever:
    def retrieve(self, store: PrivateMemoryStore, context: dict = None, max_items: int = 5, budget: int = 120) -> list:
        if not store:
            return []
        results = []
        seen = set()
        for mem_id in store.starred:
            mem = self._find_by_id(store, mem_id)
            if mem:
                results.append(mem)
                seen.add(mem_id)
        for lst in [store.text, store.emotional, store.promises, store.images]:
            for mem in lst:
                if mem.id not in seen and not mem.sensitive:
                    results.append(mem)
                    seen.add(mem.id)
                    if len(results) >= max_items:
                        break
        return results[:max_items]

    def format_for_llm(self, memories: list) -> str:
        if not memories:
            return ""
        lines = ["[私人记忆·相关片段]"]
        for mem in memories[:3]:
            lines.append(f"  {mem.date} {mem.content}")
        return "\n".join(lines)

    @staticmethod
    def _find_by_id(store: PrivateMemoryStore, mem_id: str):
        for lst in [store.text, store.images, store.promises, store.emotional]:
            for m in lst:
                if m.id == mem_id:
                    return m
        return None