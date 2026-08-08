"""镜像核心模块 - 三层反射算法"""

from __future__ import annotations

import re
from enum import Enum
from typing import List, Optional, Tuple

from .session import UserSession, DialogueEntry
from .sharpness import SharpnessLevel


class ReflectionType(Enum):
    """反射类型"""
    REPETITION = "repetition"  # 复述式反射（第一层）
    ATTRIBUTION = "attribution"  # 归因式反射（第二层）
    INQUIRY = "inquiry"  # 追问式反射（第三层）


class MirrorType(Enum):
    """镜面类型"""
    PLANE = "plane"  # 平面镜 - 原样反射
    CONCAVE = "concave"  # 凹面镜 - 聚焦
    CONVEX = "convex"  # 凸面镜 - 展开
    PRISM = "prism"  # 棱镜 - 折射


# ── 内容词提取（简化版）──
_CONTENT_WORDS = set()
_STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那",
    "被", "从", "把", "让", "用", "为", "以", "所", "但", "而", "却",
    "如果", "虽然", "因为", "所以", "这个", "那个", "什么", "怎么",
    "为什么", "可以", "已经", "还是", "或者", "以及", "然后", "但是",
    "不过", "而且", "或者", "或者", "以及", "然后", "但是", "不过",
}


class MirrorCore:
    """镜像核心 - 三层反射算法"""

    def __init__(self):
        pass

    def reflect(
        self,
        user_input: str,
        session: UserSession,
        sharpness: SharpnessLevel,
    ) -> str:
        """
        生成镜像反射

        根据锐度和对话深度选择反射层和镜面类型
        """
        # ── 极短输入处理 ──
        if len(user_input.strip()) <= 3:
            return self._reflect_minimal(user_input)

        # ── 省略号或空白 ──
        if user_input.strip() in ("...", "…", "。", ""):
            return "。"

        # ── 选择镜面类型 ──
        mirror_type = self._select_mirror_type(user_input, session)

        # ── 选择反射层 ──
        reflection_type = self._select_reflection_type(sharpness, session, user_input)

        # ── 生成反射 ──
        if reflection_type == ReflectionType.REPETITION:
            response = self._reflect_repetition(user_input, mirror_type)
        elif reflection_type == ReflectionType.ATTRIBUTION:
            response = self._reflect_attribution(user_input, mirror_type)
        else:
            response = self._reflect_inquiry(user_input, mirror_type)

        # ── 记录对话 ──
        entry = DialogueEntry(
            user_input=user_input,
            mirror_response=response,
            timestamp=__import__("time").time(),
            sharpness_level=sharpness.value,
            reflection_type=reflection_type.value,
            mirror_type=mirror_type.value,
        )
        session.add_dialogue(entry)

        return response

    def reflect_simple(self, user_input: str) -> str:
        """简单反射（降级处理）"""
        if len(user_input.strip()) <= 3:
            return self._reflect_minimal(user_input)
        return f"你说：{user_input}"

    def extract_content_words(self, text: str) -> List[str]:
        """提取内容词"""
        # 简单分词
        words = re.findall(r"[\u4e00-\u9fa5]+|[a-zA-Z]+", text)
        return [w for w in words if w not in _STOP_WORDS and len(w) >= 2]

    # ═══════════════════════════════════════════════════════════════
    #  镜面类型选择
    # ═══════════════════════════════════════════════════════════════

    def _select_mirror_type(self, user_input: str, session: UserSession) -> MirrorType:
        """选择镜面类型"""
        # 检测矛盾
        if self._has_contradiction(user_input):
            return MirrorType.PRISM

        # 检测模糊表达
        if self._is_vague(user_input):
            return MirrorType.CONCAVE

        # 检测多层情绪
        if self._has_multiple_layers(user_input):
            return MirrorType.CONVEX

        # 默认平面镜
        return MirrorType.PLANE

    def _has_contradiction(self, text: str) -> bool:
        """检测矛盾"""
        contradiction_patterns = [
            r"我想.*但是",
            r"我爱.*但我恨",
            r"我不是.*我只是",
            r"我之前觉得.*现在又",
            r"一方面.*另一方面",
        ]
        return any(re.search(p, text) for p in contradiction_patterns)

    def _is_vague(self, text: str) -> bool:
        """检测模糊表达"""
        vague_words = ["好像", "可能", "也许", "大概", "或许", "有点", "说不出"]
        return any(w in text for w in vague_words)

    def _has_multiple_layers(self, text: str) -> bool:
        """检测多层情绪"""
        emotion_words = ["但是", "同时", "又", "也", "还", "却", "而且"]
        return sum(1 for w in emotion_words if w in text) >= 2

    # ═══════════════════════════════════════════════════════════════
    #  反射层选择
    # ═══════════════════════════════════════════════════════════════

    def _select_reflection_type(
        self,
        sharpness: SharpnessLevel,
        session: UserSession,
        user_input: str,
    ) -> ReflectionType:
        """选择反射层"""
        # 情绪强度高 + 表达明确 → 第一层
        if sharpness.value <= 2:
            return ReflectionType.REPETITION

        # 情绪模糊 + 表述含混 → 第二层
        if sharpness.value == 3:
            if self._is_vague(user_input):
                return ReflectionType.ATTRIBUTION
            return ReflectionType.REPETITION

        # 矛盾或转折 → 棱镜模式
        if sharpness.value >= 4:
            if self._has_contradiction(user_input):
                return ReflectionType.INQUIRY
            return ReflectionType.ATTRIBUTION

        # 默认
        return ReflectionType.REPETITION

    # ═══════════════════════════════════════════════════════════════
    #  三层反射实现
    # ═══════════════════════════════════════════════════════════════

    def _reflect_repetition(self, user_input: str, mirror_type: MirrorType) -> str:
        """
        第一层：复述式反射

        将用户的「我」转换为「你」，用更直白的逻辑重新组织用户的原话
        """
        # 基础复述
        response = self._convert_i_to_you(user_input)

        # 根据镜面类型调整
        if mirror_type == MirrorType.PRISM:
            # 棱镜：呈现矛盾两端
            response = self._prism_repetition(user_input)
        elif mirror_type == MirrorType.CONCAVE:
            # 凹面镜：聚焦模糊处
            response = self._concave_repetition(user_input)

        return response

    def _reflect_attribution(self, user_input: str, mirror_type: MirrorType) -> str:
        """
        第二层：归因式反射

        提取用户话中的因果关系或模糊情绪，转化为开放式假设
        """
        # 检测情绪词
        emotion = self._extract_emotion(user_input)

        if emotion:
            # 有明确情绪 → 拆解为具体维度
            return self._attribute_emotion(user_input, emotion)
        else:
            # 无明确情绪 → 归因式追问
            return self._attribute_general(user_input)

    def _reflect_inquiry(self, user_input: str, mirror_type: MirrorType) -> str:
        """
        第三层：追问式反射

        将问题反转抛回给用户，不提供任何建议或答案
        """
        # 检测矛盾
        if self._has_contradiction(user_input):
            return self._inquiry_contradiction(user_input)

        # 检测情绪
        emotion = self._extract_emotion(user_input)
        if emotion:
            return self._inquiry_emotion(user_input, emotion)

        # 默认追问
        return self._inquiry_general(user_input)

    # ═══════════════════════════════════════════════════════════════
    #  辅助方法
    # ═══════════════════════════════════════════════════════════════

    def _reflect_minimal(self, user_input: str) -> str:
        """极简反射"""
        text = user_input.strip()
        if text in ("嗯", "哦", "啊"):
            return f"{text}。"
        if text == "算了":
            return "算了。"
        if text == "我不知道该说什么":
            return "不知道该说什么，也是一种状态。"
        return f"你说：{text}。"

    def _convert_i_to_you(self, text: str) -> str:
        """将「我」转换为「你」"""
        # 简单替换
        result = text
        if result.startswith("我"):
            result = "你" + result[1:]
        result = result.replace("我觉得", "你觉得")
        result = result.replace("我认为", "你认为")
        result = result.replace("我感觉", "你感觉")
        result = result.replace("我想", "你想")
        return f"你说{result}。"

    def _prism_repetition(self, user_input: str) -> str:
        """棱镜复述 - 呈现矛盾两端"""
        # 简单实现：检测"但是"前后内容
        if "但是" in user_input:
            parts = user_input.split("但是", 1)
            return f"一方面{parts[0].strip()}，另一方面{parts[1].strip()}。"
        if "可是" in user_input:
            parts = user_input.split("可是", 1)
            return f"一方面{parts[0].strip()}，另一方面{parts[1].strip()}。"
        return self._convert_i_to_you(user_input)

    def _concave_repetition(self, user_input: str) -> str:
        """凹面镜复述 - 聚焦模糊处"""
        return self._convert_i_to_you(user_input)

    def _extract_emotion(self, text: str) -> Optional[str]:
        """提取情绪词"""
        emotion_map = {
            "累": "fatigue",
            "烦": "annoyance",
            "开心": "joy",
            "难过": "sadness",
            "生气": "anger",
            "害怕": "fear",
            "孤独": "loneliness",
            "焦虑": "anxiety",
            "压力": "pressure",
            "迷茫": "confusion",
            "无聊": "boredom",
        }
        for word, emotion in emotion_map.items():
            if word in text:
                return emotion
        return None

    def _attribute_emotion(self, user_input: str, emotion: str) -> str:
        """归因式反射 - 情绪"""
        emotion_dimensions = {
            "fatigue": ("身体在抗议", "心里在抗拒"),
            "annoyance": ("事情太多", "事情不对"),
            "joy": ("发生了好事", "想起了什么"),
            "sadness": ("失去了什么", "想起了什么"),
            "anger": ("被触碰了底线", "事情不如意"),
            "fear": ("面对未知", "害怕失去"),
            "loneliness": ("身边没人", "心里没人"),
            "anxiety": ("对未来不确定", "对现在不满意"),
            "pressure": ("责任太重", "期望太高"),
            "confusion": ("选择太多", "没有选择"),
            "boredom": ("没有新鲜感", "找不到意义"),
        }

        dims = emotion_dimensions.get(emotion, ("这件事", "那个人"))
        return f"这种感觉，是{dims[0]}，还是{dims[1]}？"

    def _attribute_general(self, user_input: str) -> str:
        """归因式反射 - 通用"""
        return f"你说这些的时候，心里在想什么？"

    def _inquiry_contradiction(self, user_input: str) -> str:
        """追问式反射 - 矛盾"""
        if "我想" in user_input and "但是" in user_input:
            return "你想，但又有顾虑。顾虑是什么？"
        if "我爱" in user_input and "恨" in user_input:
            return "爱和恨同时指向同一个人。这种感觉，是什么样的？"
        return "你说的这两面，哪一面更接近你现在的感受？"

    def _inquiry_emotion(self, user_input: str, emotion: str) -> str:
        """追问式反射 - 情绪"""
        inquiry_map = {
            "fatigue": "如果给这个累取一个名字，它会叫什么？",
            "annoyance": "这个烦，是从什么时候开始的？",
            "joy": "这个开心，能再多说一点吗？",
            "sadness": "这个难过，你想让它离开吗？",
            "anger": "这个生气，是对别人还是对自己？",
            "fear": "你在怕什么？",
            "loneliness": "你在想谁？",
            "anxiety": "你在担心什么会发生？",
            "pressure": "这个压力，是谁给的？",
            "confusion": "如果有一个答案，你希望是什么？",
            "boredom": "如果有一件想做的事，会是什么？",
        }
        return inquiry_map.get(emotion, "你想说什么？")

    def _inquiry_general(self, user_input: str) -> str:
        """追问式反射 - 通用"""
        return "你说这些，是想被听见，还是想找到答案？"
