"""动态修正机制模块"""

from __future__ import annotations

import time
from enum import Enum
from dataclasses import dataclass
from typing import Optional

from .session import UserSession


class CorrectionType(Enum):
    """修正类型"""
    NICKNAME = "nickname"  # 称呼修正
    CONTENT = "content"  # 内容修正


class CorrectionStrength(Enum):
    """修正强度"""
    STRONG = "strong"  # 强修正（改变情绪方向）
    WEAK = "weak"  # 弱修正（同义强化或程度变化）
    FUZZY = "fuzzy"  # 模糊修正


@dataclass
class Correction:
    """修正记录"""
    type: CorrectionType
    strength: CorrectionStrength
    old_value: str
    new_value: str
    timestamp: float


class CorrectionManager:
    """修正管理器"""

    def __init__(self):
        self.max_annotations_per_session = 3

    def detect(self, session: UserSession, user_input: str) -> Optional[Correction]:
        """
        检测修正信号

        两条独立路径：
        1. 称呼修正（仅限显式命令）
        2. 内容修正（显式+隐式）
        """
        # ── 称呼修正检测 ──
        nickname_correction = self._detect_nickname_correction(session, user_input)
        if nickname_correction:
            return nickname_correction

        # ── 内容修正检测 ──
        content_correction = self._detect_content_correction(session, user_input)
        if content_correction:
            return content_correction

        return None

    def _detect_nickname_correction(
        self, session: UserSession, user_input: str
    ) -> Optional[Correction]:
        """
        称呼修正检测

        仅限显式命令：「叫我XX」「以后叫XX」
        """
        patterns = [
            "叫我",
            "以后叫",
            "请叫我",
            "你可以叫我",
            "我的名字是",
            "我是",
        ]

        for pattern in patterns:
            if pattern in user_input:
                # 提取新称呼
                idx = user_input.index(pattern) + len(pattern)
                new_nickname = user_input[idx:].strip()

                # 清理标点
                for punct in ["。", "！", "？", "，", "；", "："]:
                    new_nickname = new_nickname.replace(punct, "")

                if new_nickname and len(new_nickname) <= 8:
                    return Correction(
                        type=CorrectionType.NICKNAME,
                        strength=CorrectionStrength.STRONG,
                        old_value=session.nickname,
                        new_value=new_nickname,
                        timestamp=time.time(),
                    )

        return None

    def _detect_content_correction(
        self, session: UserSession, user_input: str
    ) -> Optional[Correction]:
        """
        内容修正检测

        检测用户是否在修正之前的说法
        """
        if not session.dialogue_history:
            return None

        last_entry = session.dialogue_history[-1]
        last_input = last_entry.user_input

        # ── 强修正信号 ──
        strong_patterns = [
            ("不是", "是"),  # 不是A，是B
            ("其实不是", ""),
            ("换个词", ""),
            ("准确说", ""),
            ("应该说是", ""),
        ]

        for pattern, replacement in strong_patterns:
            if pattern in user_input:
                # 显式否定句式（不是A，是B）应走强修正
                if pattern == "不是" and "也不是" in user_input:
                    continue
                # 提取新词
                idx = user_input.index(pattern) + len(pattern)
                new_value = user_input[idx:].strip()

                # 清理标点
                for punct in ["。", "！", "？", "，", "；", "："]:
                    new_value = new_value.replace(punct, "")

                if new_value:
                    # 提取旧词（从上一轮输入）
                    old_value = self._extract_last_emotion(last_input)

                    # 判断修正强度
                    if pattern == "不是":
                        strength = CorrectionStrength.STRONG
                    elif self._is_direction_change(old_value, new_value):
                        strength = CorrectionStrength.STRONG
                    else:
                        strength = CorrectionStrength.WEAK

                    return Correction(
                        type=CorrectionType.CONTENT,
                        strength=strength,
                        old_value=old_value,
                        new_value=new_value,
                        timestamp=time.time(),
                    )

        # ── 弱修正信号 ──
        weak_patterns = [
            "也不是",
            "也不是吧",
            "其实",
            "更准确说",
        ]

        for pattern in weak_patterns:
            if pattern in user_input:
                idx = user_input.index(pattern) + len(pattern)
                new_value = user_input[idx:].strip()

                for punct in ["。", "！", "？", "，", "；", "："]:
                    new_value = new_value.replace(punct, "")

                if new_value:
                    old_value = self._extract_last_emotion(last_input)
                    return Correction(
                        type=CorrectionType.CONTENT,
                        strength=CorrectionStrength.WEAK,
                        old_value=old_value,
                        new_value=new_value,
                        timestamp=time.time(),
                    )

        return None

    def _extract_last_emotion(self, text: str) -> str:
        """从上一轮输入提取情绪词"""
        emotion_words = [
            "累", "烦", "开心", "难过", "生气", "害怕",
            "孤独", "焦虑", "压力", "迷茫", "无聊",
        ]
        for word in emotion_words:
            if word in text:
                return word
        return ""

    def _is_direction_change(self, old: str, new: str) -> bool:
        """判断是否改变情绪方向"""
        # 简单实现：检查是否从正面变负面，或反之
        positive = {"开心", "高兴", "快乐", "兴奋", "期待"}
        negative = {"累", "烦", "难过", "生气", "害怕", "孤独", "焦虑"}

        old_is_positive = old in positive
        new_is_positive = new in positive

        return old_is_positive != new_is_positive

    def get_annotation(
        self, session: UserSession, correction: Correction
    ) -> Optional[str]:
        """
        生成标注文本

        大修正：自然语言同时提及新旧两个词
        小修正：静默不标注
        模糊修正：新词反射末尾加轻追问
        """
        # 检查标注次数限制
        if session.correction_count >= self.max_annotations_per_session:
            return None

        # 连续两轮都触发修正时只标注第一次
        if session.correction_count > 0:
            time_since_last = time.time() - session.last_correction_time
            if time_since_last < 120:  # 2分钟内
                return None

        if correction.type == CorrectionType.NICKNAME:
            # 称呼修正：直接确认
            return f"好，之后叫你 {correction.new_value}。"

        if correction.strength == CorrectionStrength.STRONG:
            # 大修正：三种句式随机轮转
            annotations = [
                f"你说是{correction.new_value}，不是{correction.old_value}。",
                f"{correction.new_value}。你换了一个更准的词。",
                f"{correction.new_value}。这个词出来之前，你说的是{correction.old_value}。",
            ]
            import random
            return random.choice(annotations)

        if correction.strength == CorrectionStrength.FUZZY:
            # 模糊修正：轻追问
            return f"{correction.old_value}和{correction.new_value}，是同一件事吗？"

        # 小修正：静默
        return None
