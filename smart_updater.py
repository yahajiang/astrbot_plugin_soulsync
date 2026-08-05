"""SoulSync - 智能更新决策引擎（四维判断）"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Tuple

from .emotion_engine import POSITIVE_KEYWORDS, NEGATIVE_KEYWORDS


@dataclass
class UpdateDecision:
    """智能更新决策结果"""
    should_update: bool
    reason: str
    keyword_score: float      # 关键词维度得分
    time_pressure: float      # 时间压力（0~1）
    counter_trigger: bool     # 计数器是否触发
    llm_marker: bool          # LLM 是否标记
    confidence: float         # 决策置信度 0~1


class SmartUpdater:
    """
    四维智能更新决策器：
    1. 关键词情绪强度 — 消息中情绪关键词的累计分数
    2. 时间阈值 — 距上次更新的时间间隔
    3. 强制计数器 — 每 N 轮强制更新一次
    4. 主 LLM 标记 — LLM 请求中是否检测到情感标记
    """

    def __init__(
        self,
        force_interval: int = 5,
        keyword_threshold: float = 2.0,
        time_threshold_sec: float = 120.0,
        sensitivity: float = 1.0,
    ):
        self.force_interval = max(2, force_interval)
        self.keyword_threshold = max(0.5, keyword_threshold)
        self.time_threshold_sec = max(30.0, time_threshold_sec)
        self.sensitivity = max(0.5, min(2.0, sensitivity))

    def evaluate(
        self,
        text: str,
        turns_since_update: int,
        last_update_ts: float,
        llm_marker_detected: bool = False,
    ) -> UpdateDecision:
        """四维决策：返回是否应触发深度情感更新（辅助LLM）"""

        # ── 维度 1: 关键词情绪强度 ──
        keyword_score = self._calc_keyword_score(text)

        # ── 维度 2: 时间压力 ──
        elapsed = time.time() - last_update_ts if last_update_ts > 0 else self.time_threshold_sec
        time_pressure = min(1.0, elapsed / self.time_threshold_sec)

        # ── 维度 3: 强制计数器 ──
        counter_trigger = turns_since_update >= self.force_interval

        # ── 维度 4: LLM 标记 ──
        llm_marker = llm_marker_detected

        # ── 决策逻辑 ──
        reasons = []
        score = 0.0

        # 关键词得分超过阈值
        if keyword_score >= self.keyword_threshold:
            score += 0.4
            reasons.append(f"关键词({keyword_score:.1f}≥{self.keyword_threshold})")

        # 时间压力满
        if time_pressure >= 1.0:
            score += 0.3
            reasons.append("时间阈值")

        # 任何情绪关键词命中（降低门槛）
        if keyword_score > 0:
            score += 0.2
            reasons.append(f"情绪词({keyword_score:.1f})")

        # 计数器触发
        if counter_trigger:
            score += 0.3
            reasons.append(f"计数器({turns_since_update}≥{self.force_interval})")

        # LLM 标记
        if llm_marker:
            score += 0.5
            reasons.append("LLM标记")

        # 触发条件：任一强触发 或 累计足够
        should_update = (
            llm_marker
            or counter_trigger
            or keyword_score >= self.keyword_threshold
            or (keyword_score > 0 and time_pressure > 0.5)
            or score >= 0.4
        )
        confidence = min(1.0, score)

        return UpdateDecision(
            should_update=should_update,
            reason=" + ".join(reasons) if reasons else "无触发",
            keyword_score=keyword_score,
            time_pressure=time_pressure,
            counter_trigger=counter_trigger,
            llm_marker=llm_marker,
            confidence=confidence,
        )

    def check_llm_marker(self, text: str) -> bool:
        """检查消息中是否包含 LLM 情感标记"""
        markers = [
            "[emotion_update]", "[情感更新]", "[EMOTION_UPDATE]",
            "<emotion>", "</emotion>", "【情感更新】",
        ]
        return any(m in text for m in markers)

    def _calc_keyword_score(self, text: str) -> float:
        """计算消息中情绪关键词的累计分数"""
        score = 0.0
        for kw, val in {**POSITIVE_KEYWORDS, **NEGATIVE_KEYWORDS}.items():
            if kw in text:
                score += abs(val) * self.sensitivity
        return round(score, 2)
