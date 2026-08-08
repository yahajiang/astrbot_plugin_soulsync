"""锐度管理模块 - 五级锐度系统"""

from __future__ import annotations

import time
from enum import IntEnum
from typing import Optional

from .session import UserSession


class SharpnessLevel(IntEnum):
    """锐度等级"""
    WATER = 1  # 水面 - 最轻的反射
    STILL = 2  # 静镜 - 默认起点
    FOCUS = 3  # 聚焦 - 凹面镜
    SHARP = 4  # 锐面 - 棱镜
    ABYSS = 5  # 深渊 - 最锐利


class SharpnessManager:
    """锐度管理器"""

    def __init__(self, auto_mode: bool = True):
        self.auto_mode = auto_mode
        self.manual_level: Optional[SharpnessLevel] = None
        self.history: list[dict] = []  # 锐度变化轨迹

    def get_current_level(self, session: Optional[UserSession] = None) -> SharpnessLevel:
        """获取当前锐度等级"""
        if not self.auto_mode and self.manual_level:
            return self.manual_level
        if session is not None:
            try:
                return SharpnessLevel(session.current_sharpness)
            except (ValueError, TypeError):
                return SharpnessLevel.STILL
        return SharpnessLevel.STILL

    def set_manual_level(self, level: SharpnessLevel):
        """手动设置锐度等级"""
        self.auto_mode = False
        self.manual_level = level

    def set_auto_mode(self, enabled: bool):
        """设置自动模式"""
        self.auto_mode = enabled
        if enabled:
            self.manual_level = None

    def auto_adjust(self, session: UserSession, user_input: str):
        """
        自动调锐

        根据五类信号调整锐度：
        1. 情绪密度
        2. 表达清晰度
        3. 对话深度
        4. 矛盾信号
        5. 用户主动调节
        """
        if not self.auto_mode:
            return

        current = SharpnessLevel(session.current_sharpness)
        new_level = current

        # ── 信号1：用户主动调节 ──
        user_initiated = any(
            k in user_input for k in ("直接点", "别绕弯子", "慢一点", "轻一点", "算了", "不想说了")
        )
        if user_initiated:
            if "直接点" in user_input or "别绕弯子" in user_input:
                new_level = SharpnessLevel(min(current.value + 1, SharpnessLevel.ABYSS.value))
            elif "慢一点" in user_input or "轻一点" in user_input:
                new_level = SharpnessLevel(max(current.value - 1, SharpnessLevel.WATER.value))
            elif "算了" in user_input or "不想说了" in user_input:
                new_level = SharpnessLevel(max(current.value - 2, SharpnessLevel.WATER.value))

        # ── 信号2：矛盾信号 ──
        elif self._has_contradiction_signal(user_input):
            if current.value < SharpnessLevel.SHARP.value:
                new_level = SharpnessLevel.SHARP

        # ── 信号3：情绪密度 ──
        elif self._is_high_emotion(user_input):
            if current.value > SharpnessLevel.STILL.value:
                new_level = SharpnessLevel.STILL

        # ── 信号4：表达清晰度 ──
        elif self._is_vague(user_input):
            if current.value < SharpnessLevel.FOCUS.value:
                new_level = SharpnessLevel.FOCUS

        # ── 信号5：对话深度 ──
        else:
            depth_factor = self._calculate_depth_factor(session)
            if depth_factor > 0.7 and current.value < SharpnessLevel.FOCUS.value:
                new_level = SharpnessLevel.FOCUS
            elif depth_factor < 0.3 and current.value > SharpnessLevel.STILL.value:
                new_level = SharpnessLevel.STILL

        # ── 应用变化（单轮最大变化限制；用户主动调节除外）──
        if new_level != current:
            change = new_level.value - current.value
            if user_initiated or abs(change) <= 1:  # 单轮最大变化1级
                session.current_sharpness = new_level.value
                session.sharpness_last_change = time.time()

                # 记录锐度变化轨迹
                self.history.append({
                    "round": session.current_round,
                    "from": current.value,
                    "to": new_level.value,
                    "reason": self._get_change_reason(new_level, current, user_input),
                    "timestamp": time.time(),
                })

                # 连续升锐计数
                if change > 0:
                    session.sharpness_consecutive_rise += 1
                else:
                    session.sharpness_consecutive_rise = 0

                # 连续升锐限制（3轮后强制暂停）
                if session.sharpness_consecutive_rise >= 3:
                    session.current_sharpness = current.value
                    session.sharpness_consecutive_rise = 0

    def _has_contradiction_signal(self, text: str) -> bool:
        """检测矛盾信号"""
        contradiction_words = ["但是", "可是", "然而", "却", "不过", "另一方面"]
        return any(w in text for w in contradiction_words)

    def _is_high_emotion(self, text: str) -> bool:
        """检测高情绪密度"""
        high_emotion_words = [
            "非常", "特别", "极其", "太", "真的", "实在",
            "崩溃", "受不了", "受不了了", "烦死了", "累死了",
        ]
        return any(w in text for w in high_emotion_words)

    def _is_vague(self, text: str) -> bool:
        """检测模糊表达"""
        vague_words = ["好像", "可能", "也许", "大概", "或许", "有点", "说不出"]
        return any(w in text for w in vague_words)

    def _calculate_depth_factor(self, session: UserSession) -> float:
        """计算对话深度因子"""
        if session.current_round == 0:
            return 0.0

        # 基于轮次
        round_factor = min(session.current_round / 10, 1.0)

        # 基于输出长度变化
        if len(session.dialogue_history) >= 2:
            recent_lengths = [
                len(e.user_input) for e in session.dialogue_history[-3:]
            ]
            avg_recent = sum(recent_lengths) / len(recent_lengths)
            if session.dialogue_history:
                first_length = len(session.dialogue_history[0].user_input)
                if first_length > 0:
                    length_factor = min(avg_recent / first_length, 2.0) / 2.0
                else:
                    length_factor = 0.5
            else:
                length_factor = 0.5
        else:
            length_factor = 0.5

        return (round_factor + length_factor) / 2

    def _get_change_reason(
        self, new_level: SharpnessLevel, old_level: SharpnessLevel, user_input: str
    ) -> str:
        """获取锐度变化原因"""
        if "直接点" in user_input or "别绕弯子" in user_input:
            return "用户主动升锐"
        elif "慢一点" in user_input or "轻一点" in user_input:
            return "用户主动降锐"
        elif "算了" in user_input or "不想说了" in user_input:
            return "用户退缩降锐"
        elif self._has_contradiction_signal(user_input):
            return "检测到矛盾信号"
        elif self._is_high_emotion(user_input):
            return "情绪洪峰降锐"
        elif self._is_vague(user_input):
            return "表达模糊升锐"
        else:
            return "对话深度调整"

    def get_history(self) -> list[dict]:
        """获取锐度变化轨迹"""
        return self.history

    def get_trajectory_summary(self) -> str:
        """获取锐度变化轨迹摘要"""
        if not self.history:
            return "暂无锐度变化记录。"

        lines = ["=== 锐度变化轨迹 ===\n"]
        for record in self.history[-10:]:  # 最近10条
            lines.append(
                f"第{record['round']}轮: {record['from']}→{record['to']} ({record['reason']})"
            )
        return "\n".join(lines)
