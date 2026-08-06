"""SoulSync - 知识库：LLM上下文注入（token预算 + 分类注入）"""
from ..trainer_types import KnowledgeBase


CATEGORY_LABELS = {
    "profile": "基本信息", "interests": "兴趣偏好", "people": "人物关系",
    "promises": "私密约定", "experiences": "个人经历", "values": "价值观",
}


class KnowledgeInjector:
    def generate(self, kb: KnowledgeBase, max_tokens: int = 150, max_items_per_cat: int = 3) -> str:
        if not kb or not kb.items:
            return ""
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