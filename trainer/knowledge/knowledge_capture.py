"""SoulSync - 知识库：情景捕捉"""
from ..trainer_types import KnowledgeBase


TRIGGER_WORDS = {
    "profile": ["我是", "我在", "我的生日", "我住在", "我的工作"],
    "interests": ["我喜欢", "我不喜欢", "记住", "最爱", "最讨厌"],
    "people": ["我姐", "我妈", "我朋友", "我同事", "我同学"],
    "promises": ["我们说好", "约定", "以后一起", "答应我"],
    "experiences": ["我小时候", "我曾经", "那年", "有一次"],
    "values": ["我最在乎", "我讨厌", "我相信", "我坚持"],
}


class KnowledgeCapture:
    def __init__(self, manager):
        self.manager = manager

    def check_trigger(self, message: str) -> dict:
        for category, words in TRIGGER_WORDS.items():
            for w in words:
                if w in message:
                    return {"triggered": True, "category": category, "word": w}
        return {"triggered": False}