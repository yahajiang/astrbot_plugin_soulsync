"""prometheus/sliding_window.py - 25窗滑动权重漂移（感知层 + 决策层）

Project Prometheus Layer 1。
实时感知用户沟通习惯，动态调整 LLM 分析权重。

核心机制：
- 25窗环形队列：存储消息长度评分（0~1）
- S型长尾加权：近5条陡坡/中15条高原/旧5条缓降
- 离群值剔除：±2σ
- 权重漂移：目标 = 基准线 + (L - 0.5) × 1.2，截断[0.25, 0.75]
- 动量平滑：最终权重 = 旧 × 0.85 + 目标 × 0.15

用法:
    from prometheus.sliding_window import MessageWindow
    window = MessageWindow(capacity=25)
    window.push(len(text))
    weight = window.get_weight()
"""

from __future__ import annotations

import math
import time
from collections import deque
from typing import List, Optional


def length_score(text_len: int) -> float:
    """消息长度评分：≤10字→0.1 / 11-30字→0.5 / ≥31字→0.9"""
    if text_len <= 10:
        return 0.1
    elif text_len <= 30:
        return 0.5
    else:
        return 0.9


# S型长尾加权系数（25个位置）
def _build_s_curve_weights(n: int = 25) -> List[float]:
    """构建S型长尾加权系数数组（最新→最旧）"""
    weights = []
    for i in range(n):
        if i < 5:
            # 最新5条：1.0 → 0.9（陡坡）
            w = 1.0 - i * 0.02
        elif i < 20:
            # 中间15条：0.85 → 0.6（平缓高原）
            w = 0.85 - (i - 5) * 0.017
        else:
            # 最旧5条：0.5 → 0.3（缓降尾）
            w = 0.5 - (i - 20) * 0.04
        weights.append(round(w, 3))
    return weights


_S_CURVE_WEIGHTS = _build_s_curve_weights()


class MessageWindow:
    """25窗滑动窗口：感知用户沟通习惯，动态输出 LLM 权重"""

    def __init__(self, capacity: int = 25, baseline: float = 0.4, momentum: float = 0.15):
        self.capacity = capacity
        self.baseline = baseline
        self.momentum = momentum
        self._scores: deque = deque(maxlen=capacity)
        self._current_weight: float = baseline
        self._last_active_ts: float = time.time()
        self._fill_count: int = 0  # 已填充条数

    def push(self, text_len: int):
        """推入一条消息的长度，自动计算评分"""
        score = length_score(text_len)
        self._scores.append(score)
        self._fill_count = min(self._fill_count + 1, self.capacity)
        self._last_active_ts = time.time()

    def get_weight(self) -> float:
        """获取当前 LLM 权重（每轮调用）"""
        return self._current_weight

    def recalculate(self):
        """重算权重（每轮对话结束后调用）"""
        if self._fill_count < self.capacity:
            # 填充期：使用默认权重
            return

        scores = list(self._scores)
        n = len(scores)

        # 离群值剔除：±2σ
        if n >= 20:
            mean = sum(scores) / n
            variance = sum((s - mean) ** 2 for s in scores) / n
            sigma = math.sqrt(variance) if variance > 0 else 0
            if sigma > 0:
                filtered = [s for s in scores if abs(s - mean) <= 2 * sigma]
                if len(filtered) >= n * 0.8:
                    scores = filtered
                    n = len(scores)

        # 加权平均
        weights = _S_CURVE_WEIGHTS[:n]
        weighted_sum = sum(s * w for s, w in zip(scores, weights))
        weight_sum = sum(weights)
        L = weighted_sum / weight_sum if weight_sum > 0 else 0.5

        # 权重漂移公式
        target = self.baseline + (L - 0.5) * 1.2
        target = max(0.25, min(0.75, target))

        # 动量平滑
        self._current_weight = self._current_weight * (1 - self.momentum) + target * self.momentum

    def handle_offline_return(self, offline_hours: float):
        """处理离线回归：窗口衰减 + 前5条2倍权重"""
        if offline_hours >= 48:
            # 窗口内所有历史权重衰减30%
            self._scores = deque(
                [s * 0.7 for s in self._scores],
                maxlen=self.capacity
            )
        self._last_active_ts = time.time()

    def get_baseline(self) -> float:
        return self.baseline

    def set_baseline(self, value: float):
        """设置基准线（由素描闭环调用）"""
        self.baseline = max(0.25, min(0.75, value))

    def to_dict(self) -> dict:
        """序列化为 dict（存入 extra_json）"""
        return {
            "scores": list(self._scores),
            "baseline": self.baseline,
            "current_weight": self._current_weight,
            "fill_count": self._fill_count,
            "last_active_ts": self._last_active_ts,
        }

    @classmethod
    def from_dict(cls, data: dict, capacity: int = 25, momentum: float = 0.15) -> MessageWindow:
        """从 dict 反序列化"""
        w = cls(capacity=capacity, baseline=data.get("baseline", 0.4), momentum=momentum)
        w._scores = deque(data.get("scores", []), maxlen=capacity)
        w._current_weight = data.get("current_weight", 0.4)
        w._fill_count = data.get("fill_count", 0)
        w._last_active_ts = data.get("last_active_ts", time.time())
        return w

    def get_stats(self) -> dict:
        """获取窗口统计信息"""
        scores = list(self._scores)
        n = len(scores)
        return {
            "window_size": n,
            "capacity": self.capacity,
            "is_filling": n < self.capacity,
            "current_weight": round(self._current_weight, 3),
            "baseline": self.baseline,
            "avg_score": round(sum(scores) / n, 3) if n > 0 else 0,
            "last_active": self._last_active_ts,
        }
