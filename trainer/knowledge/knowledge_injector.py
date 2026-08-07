"""SoulSync - 知识库：LLM上下文注入（token预算 + 分类注入 + v2.21 文本相关性排序）"""
from ..trainer_types import KnowledgeBase


CATEGORY_LABELS = {
    "profile": "基本信息", "interests": "兴趣偏好", "people": "人物关系",
    "promises": "私密约定", "experiences": "个人经历", "values": "价值观",
}
# 常驻权重：基本信息/私密约定/人物关系即使未命中也保留高优先级
_CATEGORY_BASE = {
    "profile": 3, "promises": 2, "people": 2,
    "interests": 1, "experiences": 1, "values": 1,
}


def _char_grams(text: str) -> set:
    """中文 2-gram 集合，用于条目与用户消息的相关性判定"""
    return {text[i:i + 2] for i in range(len(text) - 1)} if text else set()


class KnowledgeInjector:
    def generate(self, kb: KnowledgeBase, max_tokens: int = 150, max_items_per_cat: int = 3,
                 text: str = "") -> str:
        if not kb or not kb.items:
            return ""
        if text:
            return self._generate_relevant(kb, max_tokens, max_items_per_cat, text)
        return self._generate_by_category(kb, max_tokens, max_items_per_cat)

    def _generate_relevant(self, kb: KnowledgeBase, max_tokens: int, max_items_per_cat: int, text: str) -> str:
        """相关性裁剪：命中用户消息 2-gram 的条目优先；有命中时只注入命中条目"""
        grams = _char_grams(text)

        def hit_of(item) -> int:
            hay = (item.key or "") + (item.value or "")
            return len([g for g in grams if g in hay])

        hits = [(hit_of(i), i) for i in kb.items if hit_of(i) > 0]
        if hits:
            hits.sort(key=lambda x: (-x[0], -_CATEGORY_BASE.get(x[1].category, 0)))
            items = [i for _, i in hits[:max_items_per_cat]]
        else:
            ranked = sorted(kb.items,
                            key=lambda i: (-_CATEGORY_BASE.get(i.category, 0), -i.created_ts))
            items = ranked[: min(max_items_per_cat, 2)]
        used = 0
        out = []
        for cat in ["profile", "promises", "people", "interests", "experiences", "values"]:
            cat_items = [i for i in items if i.category == cat]
            if not cat_items:
                continue
            out.append(f"· {CATEGORY_LABELS.get(cat, cat)}")
            for item in cat_items:
                txt = f"  {item.key}: {item.value}"
                if len(txt) + used > max_tokens * 4:
                    break
                out.append(txt)
                used += len(txt)
        if not out:
            return ""
        return "\n".join(["[用户知识库]"] + out)

    def _generate_by_category(self, kb: KnowledgeBase, max_tokens: int, max_items_per_cat: int) -> str:
        lines = ["[用户知识库]"]
        used = 0
        for cat in ["profile", "interests", "people", "promises", "experiences", "values"]:
            items = [i for i in kb.items if i.category == cat][:max_items_per_cat]
            if not items:
                continue
            label = CATEGORY_LABELS.get(cat, cat)
            cat_lines = []
            for item in items:
                txt = f"  {item.key}: {item.value}"
                if len(txt) + used > max_tokens * 4:
                    break
                cat_lines.append(txt)
                used += len(txt)
            if cat_lines:
                lines.append(f"· {label}")
                lines.extend(cat_lines)
        if len(lines) <= 1:
            return ""
        return "\n".join(lines)
