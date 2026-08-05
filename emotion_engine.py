"""EmotionAI Pro - 8 维情感模型 + 好感/亲密度双核引擎（十二阶段版）"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

# ─── 8 维情感模型 ───────────────────────────────────────────────
EMOTION_DIMENSIONS = [
    "joy",        # 喜悦
    "sadness",    # 悲伤
    "anger",      # 愤怒
    "fear",       # 恐惧
    "surprise",   # 惊讶
    "disgust",    # 厌恶
    "trust",      # 信任
    "anticipation",  # 期待
]

# 8 维情感中文名/图标（单一来源，供 main/llm_analyzer 引用）
DIM_LABELS = {
    "joy": "喜悦", "sadness": "悲伤", "anger": "愤怒", "fear": "恐惧",
    "surprise": "惊讶", "disgust": "厌恶", "trust": "信任", "anticipation": "期待",
}
DIM_ICONS = {
    "joy": "😊", "sadness": "😢", "anger": "😠", "fear": "😨",
    "surprise": "😲", "disgust": "🤢", "trust": "🤗", "anticipation": "✨",
}

# ─── 复合情绪标签（双维达到阈值即激活）────────────────────────────
COMPOUND_EMOTIONS = {
    "感动": {"joy": 60, "trust": 60},
    "失望": {"sadness": 55, "disgust": 50},
    "醋意": {"anger": 50, "fear": 50},
    "忐忑": {"anticipation": 50, "fear": 50},
    "依恋": {"trust": 60, "anticipation": 50},
}


def detect_compound_emotions(emotions: Optional[dict]) -> list:
    """返回当前激活的复合情绪标签列表（如 ["感动", "依恋"]）"""
    if not emotions:
        return []
    out = []
    for label, conds in COMPOUND_EMOTIONS.items():
        if all(emotions.get(d, 0) >= t for d, t in conds.items()):
            out.append(label)
    return out


# ─── 情绪传染模型（张力积累 → 延迟爆发）──────────────────────────
TENSION_MAX = 100.0
TENSION_STATES = [
    ("calm", 30),      # 平静
    ("uneasy", 60),    # 阴郁
    ("strained", 85),  # 临界
    ("bursting", 101), # 即将爆发
]


def tension_state(tension: float, threshold: float = 85.0) -> str:
    """按张力值返回情绪状态：calm / uneasy / strained / bursting"""
    t = max(0.0, min(TENSION_MAX, tension))
    th = max(30.0, min(TENSION_MAX, threshold))
    if t < 30:
        return "calm"
    if t < 60:
        return "uneasy"
    if t < th:
        return "strained"
    return "bursting"

# ─── 关系阶段定义（十二阶段，好感上限 200 后阈值加大间距）────────
@dataclass
class StageConfig:
    name: str
    label: str
    composite_threshold: float  # 进入该阶段的复合评分阈值
    hysteresis_buffer: float    # 滞后带缓冲分

STAGES: List[StageConfig] = [
    StageConfig("initial",      "🌱 初识期", 15,   2),
    StageConfig("favorable",    "🌿 好感期", 35,   3),
    StageConfig("trust",        "🤝 信任期", 55,   3),
    StageConfig("familiar",     "🍀 熟悉期", 75,   4),
    StageConfig("intimate_talk","💬 交心期", 95,   4),
    StageConfig("deepening",    "💛 深化期", 115,  4),
    StageConfig("heartbeat",    "🧡 心动期", 135,  5),
    StageConfig("tacit",        "💜 默契期", 152,  5),
    StageConfig("attachment",   "💖 依恋期", 168,  6),
    StageConfig("entangled",    "💞 缠绵期", 180,  6),
    StageConfig("commitment",   "🌳 承诺期", 185,  6),
    StageConfig("symbiosis",    "🌸 共生期", 200,  8),
]

# 负好感专属阶段（好感 < 0）
NEGATIVE_STAGES = [
    (-15, "😐 冷淡"),
    (-40, "😠 反感"),
    (-70, "💢 厌恶"),
    (-100, "🔥 敌对"),
]

# ─── 关键词情绪映射（已下调 15%）────────────────────────────────
POSITIVE_KEYWORDS = {  # 正面下调 15%
    "喜欢": 3, "爱你": 4, "开心": 3, "高兴": 2, "感谢": 3,
    "谢谢": 2, "棒": 2, "厉害": 2, "可爱": 3, "漂亮": 2,
    "有趣": 2, "温暖": 3, "陪伴": 3, "想念": 3, "想你": 3,
    "加油": 2, "支持": 2, "信任": 3, "感动": 3, "幸福": 3,
    "甜": 3, "心动": 3, "拥抱": 3, "亲亲": 3, "宝贝": 3,
    "亲爱的": 3, "最好的": 3, "太好了": 2, "哈哈哈": 2, "嘻嘻": 2,
}

NEGATIVE_KEYWORDS = {  # 负面上调 8%
    "讨厌": -3, "恨": -5, "生气": -3, "烦": -2, "滚": -5,
    "无聊": -2, "无语": -2, "失望": -3, "难过": -3, "伤心": -3,
    "冷漠": -3, "忽视": -3, "欺骗": -5, "背叛": -5, "恶心": -5,
    "垃圾": -4, "废物": -4, "笨": -2, "丑": -3, "吵": -2,
    "闭嘴": -3, "别烦我": -3, "不想理你": -3, "走开": -3,
}

INTIMACY_KEYWORDS = {  # 正面下调 15%
    "秘密": 3, "私密": 3, "只有你知道": 3, "告诉你一件事": 3,
    "私下": 2, "悄悄话": 3, "内心话": 3, "真心话": 3,
    "一起": 2, "我们": 2, "约定": 3, "永远": 3,
}


# ─── 数值边界 ──────────────────────────────────────────────────
FAVORABILITY_MIN: float = -100.0   # 好感度下限（负向不变）
FAVORABILITY_MAX: float = 200.0    # 好感度上限（由 100 调高至 200）
EMOTION_BONUS_MAX: float = 15.0    # 情感加成上限（参与复合评分）
FAV_GROWTH_RATE: float = 0.5       # 好感正向增长速率（v2.13 放缓 50%；仅作用于正向，负向不变）


def intimacy_from_favorability(fav: float) -> float:
    """亲密度按好感度百分比派生：-100~200 好感映射到 0~100 亲密度"""
    return round(max(0.0, min(100.0, (fav + 100.0) / 3.0)), 1)


# ─── 用户情感档案 ───────────────────────────────────────────────
@dataclass
class EmotionProfile:
    """单个用户的情感档案"""
    user_id: str = ""
    user_name: str = ""

    # 好感度 -100 ~ 200
    favorability: float = 0.0
    # 亲密度 0 ~ 100（按好感度派生：intimacy = (fav + 100) / 3）
    intimacy: float = 0.0

    # 8 维情感值 (0~100)
    emotions: Dict[str, float] = field(default_factory=lambda: {d: 50.0 for d in EMOTION_DIMENSIONS})

    # 关系阶段索引 (0~11)，负好感用 -1
    stage_index: int = 0
    # 阶段内进度百分比
    stage_progress: float = 0.0

    # 互动统计
    positive_interactions: int = 0
    negative_interactions: int = 0
    total_interactions: int = 0

    # 复合评分
    composite_score: float = 0.0

    # 情绪张力（情绪传染模型）：0~100，负面情绪积累、正面情绪缓解
    tension: float = 0.0
    # 最近一次情绪爆发时间戳（供 LLM 上下文提示"刚刚爆发"）
    last_eruption_ts: float = 0.0

    # 最近更新时间戳
    last_update_ts: float = 0.0
    # 对话轮数计数
    conversation_turns: int = 0
    # 自上次智能更新后的轮数
    turns_since_update: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EmotionProfile":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid}
        return cls(**filtered)


# ─── 核心引擎 ───────────────────────────────────────────────────
class EmotionEngine:
    """情感计算核心：负责好感/亲密度变更、阶段判定、复合评分"""

    def __init__(self, sensitivity: float = 1.0, fav_growth_rate: float = FAV_GROWTH_RATE):
        self.sensitivity = max(0.5, min(2.0, sensitivity))
        self.fav_growth_rate = max(0.05, min(1.0, fav_growth_rate))

    def update_config(self, fav_growth_rate: Optional[float] = None):
        """热更新引擎参数（WebUI 保存配置后调用）；仅支持正向增长速率"""
        if fav_growth_rate is not None:
            self.fav_growth_rate = max(0.05, min(1.0, float(fav_growth_rate)))

    # ── 关键词情绪分析 ──
    def analyze_keywords(self, text: str) -> dict:
        """返回 {fav_delta, int_delta, emotion_deltas, matched_keywords}"""
        fav_delta = 0.0
        int_delta = 0.0
        matched = []

        for kw, val in POSITIVE_KEYWORDS.items():
            if kw in text:
                fav_delta += val * self.sensitivity
                matched.append((kw, val))

        for kw, val in NEGATIVE_KEYWORDS.items():
            if kw in text:
                fav_delta += val * self.sensitivity  # val is negative
                matched.append((kw, val))

        for kw, val in INTIMACY_KEYWORDS.items():
            if kw in text:
                int_delta += val * self.sensitivity * 0.5
                matched.append((kw, val))

        # 情感维度微调（正面下调 15%，负面上调 8%）
        emotion_deltas = {}
        if any(kw in text for kw in ["开心", "高兴", "哈哈", "嘻嘻", "太好了"]):
            emotion_deltas["joy"] = min(3, abs(fav_delta) * 0.6)       # 正面 -15%
        if any(kw in text for kw in ["难过", "伤心", "失望", "哭"]):
            emotion_deltas["sadness"] = min(4, abs(fav_delta) * 0.76)  # 负面 +8%
        if any(kw in text for kw in ["生气", "愤怒", "烦", "恨"]):
            emotion_deltas["anger"] = min(4, abs(fav_delta) * 0.76)    # 负面 +8%
        if any(kw in text for kw in ["信任", "相信", "依靠"]):
            emotion_deltas["trust"] = min(3, abs(fav_delta) * 0.4)     # 正面 -15%
        if any(kw in text for kw in ["期待", "希望", "盼"]):
            emotion_deltas["anticipation"] = min(3, abs(fav_delta) * 0.34)  # 正面 -15%

        return {
            "fav_delta": round(fav_delta, 2),
            "int_delta": round(int_delta, 2),
            "emotion_deltas": emotion_deltas,
            "matched_keywords": matched,
        }

    # ── 情绪传染模型（张力积累 → 延迟爆发）──
    def accumulate_tension(
        self,
        profile: EmotionProfile,
        emotion_deltas: dict,
        accumulate_rate: float = 2.0,
        release_rate: float = 3.0,
    ) -> float:
        """按本轮情感变化积累/缓解情绪张力（0~100）。
        负面维度上升按 accumulate_rate 积累；正面维度上升按 release_rate 缓解。
        返回更新后的张力值。"""
        neg = sum(v for d, v in emotion_deltas.items()
                  if isinstance(v, (int, float)) and v > 0 and d in ("anger", "sadness", "disgust", "fear"))
        pos = sum(v for d, v in emotion_deltas.items()
                  if isinstance(v, (int, float)) and v > 0 and d in ("joy", "trust", "anticipation", "surprise"))
        profile.tension = max(0.0, min(
            TENSION_MAX,
            profile.tension + neg * accumulate_rate - pos * release_rate,
        ))
        return profile.tension

    @staticmethod
    def check_eruption(profile: EmotionProfile, threshold: float = 85.0) -> bool:
        """张力达到阈值 → 触发爆发：张力归零并记录爆发时刻。返回是否爆发"""
        if profile.tension >= max(30.0, min(TENSION_MAX, threshold)):
            profile.tension = 0.0
            profile.last_eruption_ts = time.time()
            return True
        return False

    # ── 复合评分（情感画像计算系统 v2）──
    def calc_composite(self, profile: EmotionProfile) -> float:
        """复合评分：
        - 负好感：直接以好感值为准（负向阶段不变）
        - 非负好感：好感值 + 情感加成（喜悦/信任/期待均值 × EMOTION_BONUS_MAX，0~15）
          好感上限 200 + 情感加成 15 → 复合评分上限 215
        """
        if profile.favorability < 0:
            return round(profile.favorability, 2)
        bonus = self._emotion_bonus(profile)
        return round(profile.favorability + bonus, 2)

    @staticmethod
    def _emotion_bonus(profile: EmotionProfile) -> float:
        """正向情感加成：喜悦/信任/期待三项均值映射到 0~EMOTION_BONUS_MAX"""
        avg = (
            profile.emotions.get("joy", 50.0)
            + profile.emotions.get("trust", 50.0)
            + profile.emotions.get("anticipation", 50.0)
        ) / 3.0
        return avg / 100.0 * EMOTION_BONUS_MAX

    # ── 阶段判定（带滞后带保护）──
    def evaluate_stage(self, profile: EmotionProfile) -> int:
        """返回应处于的阶段索引 (0~11)，负好感返回 -1"""
        if profile.favorability < 0:
            return -1

        composite = profile.composite_score
        current = profile.stage_index

        # 从低到高检查是否达到阈值（含滞后带）
        for i in range(len(STAGES) - 1, -1, -1):
            stage = STAGES[i]
            if i > current:
                # 上升需要超过 阈值 + 滞后带
                if composite >= stage.composite_threshold + stage.hysteresis_buffer:
                    return i
            else:
                # 已在该阶段或更低，只需超过阈值
                if composite >= stage.composite_threshold:
                    return max(current, i)

        return 0

    # ── 阶段进度 ──
    def calc_stage_progress(self, profile: EmotionProfile) -> float:
        """计算当前阶段内的进度百分比 (0~100)"""
        if profile.favorability < 0:
            return 0.0

        stage = self._get_stage_config(profile)
        idx = profile.stage_index

        # 当前阶段的起始阈值
        lower = STAGES[idx].composite_threshold
        # 下一阶段的阈值（如果是最终阶段则 +15）
        upper = STAGES[min(idx + 1, len(STAGES) - 1)].composite_threshold
        if idx == len(STAGES) - 1:
            upper = lower + 15

        if upper <= lower:
            return 100.0

        progress = (profile.composite_score - lower) / (upper - lower) * 100
        return round(max(0, min(100, progress)), 1)

    # ── 应用情感变更 ──
    def apply_change(
        self,
        profile: EmotionProfile,
        fav_delta: float,
        int_delta: float,
        emotion_deltas: Dict[str, float],
        llm_emotion_adjust: Optional[Dict[str, float]] = None,
    ) -> EmotionProfile:
        """应用情感变更，含边界保护和阶段跃迁"""
        old_stage = profile.stage_index

        # 正向增长放缓：仅对正向增量乘 fav_growth_rate（默认 0.5），负向（惩罚）不变
        effective_delta = fav_delta * self.fav_growth_rate if fav_delta > 0 else fav_delta

        # 好感度变更（上限 200，下限 -100）
        profile.favorability = max(
            FAVORABILITY_MIN, min(FAVORABILITY_MAX, profile.favorability + effective_delta)
        )

        # 亲密度按好感度百分比派生（int_delta 不再累积，仅用于记忆/日志展示）
        profile.intimacy = intimacy_from_favorability(profile.favorability)

        # 8 维情感变更
        if llm_emotion_adjust:
            for dim, adj in llm_emotion_adjust.items():
                if dim in profile.emotions:
                    profile.emotions[dim] = max(0, min(100, profile.emotions[dim] + adj))

        for dim, delta in emotion_deltas.items():
            if dim in profile.emotions:
                profile.emotions[dim] = max(0, min(100, profile.emotions[dim] + delta))

        # 互动统计
        profile.total_interactions += 1
        if fav_delta > 0:
            profile.positive_interactions += 1
        elif fav_delta < 0:
            profile.negative_interactions += 1

        # 复合评分
        profile.composite_score = self.calc_composite(profile)

        # 阶段评估
        new_stage = self.evaluate_stage(profile)

        # 过渡保护：阶段下降时检查保护分
        if new_stage < old_stage and new_stage >= 0:
            protected_min = STAGES[old_stage].composite_threshold - STAGES[old_stage].hysteresis_buffer
            if profile.composite_score < protected_min:
                pass

        profile.stage_index = new_stage
        profile.stage_progress = self.calc_stage_progress(profile)

        return profile

    # ── 负好感描述 ──
    @staticmethod
    def get_negative_stage_label(favorability: float) -> str:
        for threshold, label in NEGATIVE_STAGES:
            if favorability >= threshold:
                return label
        return NEGATIVE_STAGES[-1][1]

    # ── 内部辅助 ──
    def _get_stage_config(self, profile: EmotionProfile) -> StageConfig:
        idx = max(0, min(profile.stage_index, len(STAGES) - 1))
        return STAGES[idx]
