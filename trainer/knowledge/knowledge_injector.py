"""SoulSync - 知识库：LLM上下文注入"""
from ..trainer_types import KnowledgeBase


class KnowledgeInjector:
    def generate(self, kb: KnowledgeBase, max_tokens: int = 150) -> str:
        if not kb or not kb.items:
            return ""
        items = kb.items[:5]
        lines = ["[用户知识库]"]
        for item in items:
            lines.append(f"  {item.key}: {item.value}")
        return "\n".join(lines)