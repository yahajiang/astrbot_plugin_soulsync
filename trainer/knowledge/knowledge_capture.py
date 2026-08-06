"""SoulSync - 知识库：情景捕捉（触发词/重复检测/冲突）"""
from collections import defaultdict
from ..trainer_types import KnowledgeBase


TRIGGER_WORDS = {
    "profile": ["我是", "我在", "我的生日", "我住在", "我的工作", "我的名字", "我来自"],
    "interests": ["我喜欢", "我不喜欢", "记住", "最爱", "最讨厌", "我最爱", "我超爱"],
    "people": ["我姐", "我妈", "我朋友", "我同事", "我同学", "我家人", "我男票", "我女票"],
    "promises": ["我们说好", "约定", "以后一起", "答应我", "我承诺", "约好了"],
    "experiences": ["我小时候", "我曾经", "那年", "有一次", "记得那次", "以前有"],
    "values": ["我最在乎", "我讨厌", "我相信", "我坚持", "我始终认为"],
}


class KnowledgeCapture:
    def __init__(self, manager):
        self.manager = manager
        self._recent_topics = defaultdict(int)
        self._turn_buffer = []

    def check_trigger(self, message: str, kb: KnowledgeBase = None) -> dict:
        for category, words in TRIGGER_WORDS.items():
            for w in words:
                if w in message:
                    start = message.find(w) + len(w)
                    content = message[start:].strip().rstrip("。，,!！").strip()
                    if not content:
                        content = "(未捕获)"
                    return {"triggered": True, "category": category, "word": w, "content": content}
        return {"triggered": False}

    def check_repeat(self, message: str, turn_count: int) -> dict:
        self._turn_buffer.append(message)
        if len(self._turn_buffer) > 5:
            self._turn_buffer.pop(0)
        if len(self._turn_buffer) < 3:
            return {"repeated": False}
        words = set(message.split())
        for prev in self._turn_buffer[:-1]:
            overlap = words & set(prev.split())
            if len(overlap) >= 3:
                self._recent_topics[message] += 1
        if self._recent_topics.get(message, 0) >= 2:
            return {"repeated": True, "message": message}
        return {"repeated": False}

    def check_trigger_full(self, message: str, kb: KnowledgeBase = None, turn_count: int = 0) -> dict:
        trigger = self.check_trigger(message, kb)
        if trigger["triggered"]:
            conflict = self.manager.check_conflict(trigger["category"], trigger["word"], trigger["content"])
            return {
                **trigger,
                "conflict": conflict.has_conflict,
                "conflict_items": conflict.existing,
            }
        repeat = self.check_repeat(message, turn_count)
        if repeat["repeated"]:
            return {"triggered": False, "repeat_suggested": True, "message": message}
        return {"triggered": False, "repeat_suggested": False}