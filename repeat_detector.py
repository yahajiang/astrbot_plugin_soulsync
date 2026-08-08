"""重复词检测模块"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, List

from .session import UserSession

# 常见内容词表（简单分词用）
_COMMON_WORDS = {
    "今天", "昨天", "明天", "现在", "最近", "工作", "生活", "朋友", "家人",
    "事情", "问题", "感觉", "心情", "希望", "害怕", "开心", "难过", "生气",
    "孤独", "焦虑", "压力", "迷茫", "无聊", "喜欢", "讨厌", "累了",
    "累", "烦", "爱", "恨", "想",
}

# 排除功能词
_STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那",
    "还是", "但是", "不过", "而且", "然后", "或者", "以及",
}


@dataclass
class RepeatSignal:
    """重复信号"""
    word: str
    count: int
    threshold: int
    response: str


class RepeatDetector:
    """重复词检测器"""

    def __init__(self):
        self.window = 5  # 检测窗口
        self.threshold = 3  # 触发阈值

    def detect(self, session: UserSession, user_input: str) -> Optional[RepeatSignal]:
        """
        检测重复词

        同一实义词在5轮内出现超过3次时触发
        """
        # 提取当前输入的实义词
        current_words = self._extract_content_words(user_input)

        # 更新词频
        for word in current_words:
            session.word_frequency[word] = session.word_frequency.get(word, 0) + 1

        # 检测重复
        for word, count in session.word_frequency.items():
            if count >= self.threshold:
                response = self._generate_response(word, count)
                return RepeatSignal(
                    word=word,
                    count=count,
                    threshold=self.threshold,
                    response=response,
                )

        return None

    def _extract_content_words(self, text: str) -> List[str]:
        """提取内容词"""
        # 简单分词：英文词 + 常见中文词匹配 + 双字滑窗补充
        words = re.findall(r"[a-zA-Z]{2,}", text)

        for seg in re.findall(r"[\u4e00-\u9fa5]+", text):
            # 常见词优先
            for w in _COMMON_WORDS:
                if w in seg:
                    words.append(w)

            # 双字滑窗补充
            if len(seg) >= 2:
                for i in range(len(seg) - 1):
                    w = seg[i:i+2]
                    if w not in _STOP_WORDS:
                        words.append(w)

        # 去重保序
        seen = set()
        result = []
        for w in words:
            if w in _STOP_WORDS:
                continue
            if w not in seen:
                seen.add(w)
                result.append(w)
        return result

    def _generate_response(self, word: str, count: int) -> str:
        """生成重复提示"""
        if count == self.threshold:
            return f"'{word}'这个词，已经是第{count}次出现了。"
        elif count == self.threshold + 1:
            return f"我注意到你一直在说'{word}'。这个词背后，你想说的是什么？"
        else:
            return f"这轮对话里，'{word}'出现了{count}次。它一直在敲门。"

    def reset(self, session: UserSession):
        """重置词频"""
        session.word_frequency.clear()
