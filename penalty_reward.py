"""EmotionAI Pro - 情感惩罚奖励机制

行为模式追踪 + 递增惩罚/奖励 + 衰减系统 + 事件触发器

核心思路：
- 用户的每条消息不仅产生即时的情感变化，还会被纳入行为模式分析
- 连续的正面/负面行为会形成"势头"（momentum），带来递增的奖惩
- 特殊事件（冷落、回归、里程碑）触发额外的情感冲击
- 所有奖惩效果随时间自然衰减，防止永久锁定
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

from .emotion_engine import POSITIVE_KEYWORDS, NEGATIVE_KEYWORDS

# ─── 行为模式定义 ───────────────────────────────────────────────
BEHAVIOR_POSITIVE = "positive"
BEHAVIOR_NEGATIVE = "negative"
BEHAVIOR_NEUTRAL = "neutral"

# ─── 惩罚奖励配置常量 ─────────────────────────────────────────
# 连续行为势头
MAX_MOMENTUM = 10                    # 势头最大层数
MOMENTUM_REWARD_PER_LEVEL = 0.34     # 每层正面势头额外奖励（正面再下调 15%）
MOMENTUM_PENALTY_PER_LEVEL = -0.76   # 每层负面势头额外惩罚（负面上调 8%）

# 冷落检测
COLD_THRESHOLD_HOURS = 24            # 超过此时间未互动视为冷落
COLD_PENALTY_BASE = -1.8             # 冷落基础惩罚（负面上调 8%）
COLD_PENALTY_PER_DAY = -0.43         # 每多冷落一天额外惩罚（负面上调 8%）
COLD_MAX_PENALTY = -14.0             # 冷落惩罚上限（负面上调 8%）

# 回归奖励
COMEBACK_THRESHOLD_HOURS = 48        # 冷落超过此时长后回归给予奖励
COMEBACK_REWARD_BASE = 2.1           # 回归基础奖励（正面再下调 15%）
COMEBACK_BONUS_PER_DAY = 0.34        # 每多冷落一天回归额外奖励（正面再下调 15%）
COMEBACK_MAX_REWARD = 8.5            # 回归奖励上限（正面再下调 15%）

# 关系里程碑
MILESTONES = {  # 正面再下调 15%
    10:  ("first_positive", "首次正面互动", 1.4),
    50:  ("fifty_interactions", "50次互动", 2.1),
    100: ("hundred_interactions", "100次互动", 3.6),
    200: ("two_hundred", "200次互动", 5.8),
}

# 背叛检测关键词
BETRAYAL_KEYWORDS = ["背叛", "欺骗", "骗我", "不信任", "再也不信", "假的", "虚伪"]
BETRAYAL_PENALTY = -7.3             # 负面上调 8%
BETRAYAL_COOLDOWN_SEC = 3600         # 背叛惩罚冷却时间（防止短时间内重复触发）

# 道歉检测关键词
APOLOGY_KEYWORDS = ["对不起", "抱歉", "不好意思", "我错了", "原谅我", "sorry", "道歉"]
APOLOGY_RECOVERY = 1.4               # 道歉恢复量（正面再下调 15%）
APOLOGY_COOLDOWN_SEC = 600           # 道歉冷却时间

# 衰减
DECAY_HALF_LIFE_HOURS = 72           # 惩罚/奖励效果的半衰期（小时）


# ─── 用户行为档案 ───────────────────────────────────────────────
@dataclass
class BehaviorProfile:
    """用户行为模式追踪数据"""
    user_id: str = ""

    # 行为势头
    current_streak_type: str = BEHAVIOR_NEUTRAL  # 当前连续行为类型
    current_streak_count: int = 0                 # 连续次数
    max_positive_streak: int = 0                  # 历史最长正面连续
    max_negative_streak: int = 0                  # 历史最长负面连续

    # 累计统计
    total_reward_accumulated: float = 0.0         # 累计获得的奖励总量
    total_penalty_accumulated: float = 0.0        # 累计获得的惩罚总量
    betrayal_count: int = 0                       # 背叛事件次数
    apology_count: int = 0                        # 道歉次数
    comeback_count: int = 0                       # 回归次数

    # 时间戳
    last_interaction_ts: float = 0.0              # 上次互动时间
    last_betrayal_ts: float = 0.0                 # 上次背叛时间
    last_apology_ts: float = 0.0                  # 上次道歉时间
    last_comeback_ts: float = 0.0                 # 上次回归时间

    # 已达成的里程碑
    achieved_milestones: List[str] = field(default_factory=list)

    # 待衰减的奖惩队列 [(apply_ts, delta_fav, delta_int, reason), ...]
    pending_effects: List[Tuple[float, float, float, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BehaviorProfile":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid}
        return cls(**filtered)


# ─── 惩罚奖励引擎 ───────────────────────────────────────────────
class PenaltyRewardEngine:
    """
    情感惩罚奖励引擎

    调用流程：
    1. analyze_and_apply() — 每轮消息调用，分析行为模式并计算奖惩
    2. check_special_events() — 检测冷落/回归/里程碑等特殊事件
    3. get_pending_deltas() — 获取累积的待应用情感变化（含衰减）
    """

    def __init__(
        self,
        cold_threshold_hours: float = COLD_THRESHOLD_HOURS,
        comeback_threshold_hours: float = COMEBACK_THRESHOLD_HOURS,
        decay_half_life_hours: float = DECAY_HALF_LIFE_HOURS,
        momentum_reward_per_level: float = MOMENTUM_REWARD_PER_LEVEL,
        momentum_penalty_per_level: float = MOMENTUM_PENALTY_PER_LEVEL,
        enable_cold_penalty: bool = True,
        enable_comeback_reward: bool = True,
        enable_milestone_reward: bool = True,
        enable_betrayal_penalty: bool = True,
        enable_apology_recovery: bool = True,
        enable_momentum: bool = True,
    ):
        self.cold_threshold_sec = cold_threshold_hours * 3600
        self.comeback_threshold_sec = comeback_threshold_hours * 3600
        self.decay_half_life_sec = decay_half_life_hours * 3600
        self.momentum_reward_per_level = momentum_reward_per_level
        self.momentum_penalty_per_level = momentum_penalty_per_level
        self.enable_cold_penalty = enable_cold_penalty
        self.enable_comeback_reward = enable_comeback_reward
        self.enable_milestone_reward = enable_milestone_reward
        self.enable_betrayal_penalty = enable_betrayal_penalty
        self.enable_apology_recovery = enable_apology_recovery
        self.enable_momentum = enable_momentum

    def update_config(
        self,
        cold_threshold_hours: float = COLD_THRESHOLD_HOURS,
        comeback_threshold_hours: float = COMEBACK_THRESHOLD_HOURS,
        decay_half_life_hours: float = DECAY_HALF_LIFE_HOURS,
        momentum_reward_per_level: float = MOMENTUM_REWARD_PER_LEVEL,
        momentum_penalty_per_level: float = MOMENTUM_PENALTY_PER_LEVEL,
        enable_cold_penalty: bool = True,
        enable_comeback_reward: bool = True,
        enable_milestone_reward: bool = True,
        enable_betrayal_penalty: bool = True,
        enable_apology_recovery: bool = True,
        enable_momentum: bool = True,
    ):
        """热更新引擎参数（WebUI 保存配置后调用）"""
        self.cold_threshold_sec = float(cold_threshold_hours) * 3600
        self.comeback_threshold_sec = float(comeback_threshold_hours) * 3600
        self.decay_half_life_sec = float(decay_half_life_hours) * 3600
        self.momentum_reward_per_level = float(momentum_reward_per_level)
        self.momentum_penalty_per_level = float(momentum_penalty_per_level)
        self.enable_cold_penalty = bool(enable_cold_penalty)
        self.enable_comeback_reward = bool(enable_comeback_reward)
        self.enable_milestone_reward = bool(enable_milestone_reward)
        self.enable_betrayal_penalty = bool(enable_betrayal_penalty)
        self.enable_apology_recovery = bool(enable_apology_recovery)
        self.enable_momentum = bool(enable_momentum)

    def analyze_and_apply(
        self,
        bp: BehaviorProfile,
        text: str,
        fav_delta: float,
        int_delta: float,
        current_favorability: float,
        total_interactions: int,
    ) -> Tuple[float, float, List[str]]:
        """
        分析当前消息的行为模式，计算惩罚/奖励增量。

        返回: (extra_fav_delta, extra_int_delta, event_descriptions)
        """
        extra_fav = 0.0
        extra_int = 0.0
        events = []
        now = time.time()

        # ── 1. 判断当前消息的行为类型 ──
        behavior = self._classify_behavior(text, fav_delta)

        # ── 2. 更新行为势头 ──
        if self.enable_momentum:
            momentum_fav, momentum_int, streak_event = self._update_momentum(bp, behavior)
            extra_fav += momentum_fav
            extra_int += momentum_int
            if streak_event:
                events.append(streak_event)

        # ── 3. 冷落检测 ──
        if self.enable_cold_penalty and bp.last_interaction_ts > 0:
            cold_fav, cold_int, cold_event = self._check_cold(bp, now, current_favorability + extra_fav)
            extra_fav += cold_fav
            extra_int += cold_int
            if cold_event:
                events.append(cold_event)

        # ── 4. 回归奖励 ──
        if self.enable_comeback_reward and bp.last_interaction_ts > 0:
            comeback_fav, comeback_int, comeback_event = self._check_comeback(bp, now)
            extra_fav += comeback_fav
            extra_int += comeback_int
            if comeback_event:
                events.append(comeback_event)

        # ── 5. 背叛检测 ──
        if self.enable_betrayal_penalty:
            betrayal_fav, betrayal_int, betrayal_event = self._check_betrayal(bp, text, now)
            extra_fav += betrayal_fav
            extra_int += betrayal_int
            if betrayal_event:
                events.append(betrayal_event)

        # ── 6. 道歉恢复 ──
        if self.enable_apology_recovery:
            apology_fav, apology_int, apology_event = self._check_apology(bp, text, now, current_favorability)
            extra_fav += apology_fav
            extra_int += apology_int
            if apology_event:
                events.append(apology_event)

        # ── 7. 里程碑检测 ──
        if self.enable_milestone_reward:
            milestone_fav, milestone_int, milestone_events = self._check_milestones(bp, total_interactions)
            extra_fav += milestone_fav
            extra_int += milestone_int
            events.extend(milestone_events)

        # ── 8. 记录待衰减效果 ──
        if extra_fav != 0 or extra_int != 0:
            bp.pending_effects.append((now, extra_fav, extra_int, "; ".join(events) if events else "常规"))

        # ── 更新时间戳 ──
        bp.last_interaction_ts = now

        return round(extra_fav, 2), round(extra_int, 2), events

    def get_pending_deltas(self, bp: BehaviorProfile) -> Tuple[float, float]:
        """
        获取所有待应用的情感变化（含时间衰减）。

        效果随时间按半衰期衰减：effect(t) = base * 0.5^(t_elapsed / half_life)
        """
        now = time.time()
        total_fav = 0.0
        total_int = 0.0
        alive_effects = []

        for apply_ts, fav, int_val, reason in bp.pending_effects:
            elapsed = now - apply_ts
            if elapsed < 0:
                # 未来时间戳，直接应用
                total_fav += fav
                total_int += int_val
                alive_effects.append((apply_ts, fav, int_val, reason))
            else:
                # 计算衰减
                decay_factor = 0.5 ** (elapsed / self.decay_half_life_sec)
                if decay_factor > 0.01:  # 衰减到 1% 以下则丢弃
                    total_fav += fav * decay_factor
                    total_int += int_val * decay_factor
                    alive_effects.append((apply_ts, fav, int_val, reason))

        # 清理已衰减完毕的效果
        bp.pending_effects = alive_effects

        return round(total_fav, 2), round(total_int, 2)

    def cleanup_expired_effects(self, bp: BehaviorProfile):
        """清理已完全衰减的效果（定期调用）"""
        now = time.time()
        bp.pending_effects = [
            (ts, fav, int_val, reason)
            for ts, fav, int_val, reason in bp.pending_effects
            if 0.5 ** ((now - ts) / self.decay_half_life_sec) > 0.01
        ]

    # ═══════════════════════════════════════════════════════════════
    #  内部方法
    # ═══════════════════════════════════════════════════════════════

    def _classify_behavior(self, text: str, fav_delta: float) -> str:
        """根据关键词和好感变化判断行为类型（复用 emotion_engine 权威词表）"""
        # 检测关键词
        has_positive = any(kw in text for kw in POSITIVE_KEYWORDS)
        has_negative = any(kw in text for kw in NEGATIVE_KEYWORDS)

        if has_positive and not has_negative:
            return BEHAVIOR_POSITIVE
        elif has_negative and not has_positive:
            return BEHAVIOR_NEGATIVE
        elif fav_delta > 0.5:
            return BEHAVIOR_POSITIVE
        elif fav_delta < -0.5:
            return BEHAVIOR_NEGATIVE
        else:
            return BEHAVIOR_NEUTRAL

    def _update_momentum(
        self, bp: BehaviorProfile, behavior: str
    ) -> Tuple[float, float, Optional[str]]:
        """更新行为势头，返回额外情感变化"""
        event = None

        if behavior == BEHAVIOR_NEUTRAL:
            # 中性行为不改变势头，但也不重置
            return 0.0, 0.0, None

        if behavior == bp.current_streak_type:
            # 同类行为，势头+1
            bp.current_streak_count = min(bp.current_streak_count + 1, MAX_MOMENTUM)
        else:
            # 行为类型切换，重置势头
            bp.current_streak_type = behavior
            bp.current_streak_count = 1

        # 更新历史记录
        if behavior == BEHAVIOR_POSITIVE:
            bp.max_positive_streak = max(bp.max_positive_streak, bp.current_streak_count)
        elif behavior == BEHAVIOR_NEGATIVE:
            bp.max_negative_streak = max(bp.max_negative_streak, bp.current_streak_count)

        # 计算势头效果
        level = bp.current_streak_count - 1  # 第一次不算势头
        if level <= 0:
            return 0.0, 0.0, None

        if behavior == BEHAVIOR_POSITIVE:
            fav_bonus = level * self.momentum_reward_per_level
            int_bonus = level * 0.2
            if level >= 3:
                event = f"🔥 正面势头 ×{level}（好感+{fav_bonus:.1f}）"
            return fav_bonus, int_bonus, event
        else:
            fav_penalty = level * self.momentum_penalty_per_level  # 负值
            int_penalty = level * -0.3
            if level >= 3:
                event = f"⚡ 负面势头 ×{level}（好感{fav_penalty:.1f}）"
            return fav_penalty, int_penalty, event

    def _check_cold(
        self, bp: BehaviorProfile, now: float, current_fav: float
    ) -> Tuple[float, float, Optional[str]]:
        """检测冷落（长时间未互动）"""
        elapsed = now - bp.last_interaction_ts
        if elapsed < self.cold_threshold_sec:
            return 0.0, 0.0, None

        # 冷落天数
        cold_days = (elapsed - self.cold_threshold_sec) / 86400

        # 好感越高，冷落惩罚越重（在乎才会受伤）
        favor_factor = max(0.5, min(2.0, (current_fav + 50) / 100))

        fav_penalty = COLD_PENALTY_BASE + cold_days * COLD_PENALTY_PER_DAY
        fav_penalty *= favor_factor
        fav_penalty = max(fav_penalty, COLD_MAX_PENALTY)

        int_penalty = fav_penalty * 0.3  # 亲密也会下降，但幅度较小

        event = f"❄️ 冷落{cold_days:.1f}天（好感{fav_penalty:.1f}）"
        return fav_penalty, int_penalty, event

    def _check_comeback(
        self, bp: BehaviorProfile, now: float
    ) -> Tuple[float, float, Optional[str]]:
        """检测回归（长时间冷落后重新互动）"""
        elapsed = now - bp.last_interaction_ts
        if elapsed < self.comeback_threshold_sec:
            return 0.0, 0.0, None

        # 冷落天数
        cold_days = (elapsed - self.comeback_threshold_sec) / 86400

        fav_reward = COMEBACK_REWARD_BASE + cold_days * COMEBACK_BONUS_PER_DAY
        fav_reward = min(fav_reward, COMEBACK_MAX_REWARD)

        int_reward = fav_reward * 0.5

        bp.comeback_count += 1
        bp.last_comeback_ts = now

        event = f"💫 回归奖励（好感+{fav_reward:.1f}，第{bp.comeback_count}次回归）"
        return fav_reward, int_reward, event

    def _check_betrayal(
        self, bp: BehaviorProfile, text: str, now: float
    ) -> Tuple[float, float, Optional[str]]:
        """检测背叛关键词"""
        if now - bp.last_betrayal_ts < BETRAYAL_COOLDOWN_SEC:
            return 0.0, 0.0, None

        matched = [kw for kw in BETRAYAL_KEYWORDS if kw in text]
        if not matched:
            return 0.0, 0.0, None

        bp.betrayal_count += 1
        bp.last_betrayal_ts = now

        # 累犯加重
        repeat_factor = min(2.0, 1.0 + (bp.betrayal_count - 1) * 0.25)
        fav_penalty = BETRAYAL_PENALTY * repeat_factor
        int_penalty = fav_penalty * 0.6  # 亲密受背叛影响更大

        event = f"💔 背叛检测「{'、'.join(matched[:3])}」（好感{fav_penalty:.1f}，第{bp.betrayal_count}次）"
        return fav_penalty, int_penalty, event

    def _check_apology(
        self, bp: BehaviorProfile, text: str, now: float, current_fav: float
    ) -> Tuple[float, float, Optional[str]]:
        """检测道歉关键词"""
        if now - bp.last_apology_ts < APOLOGY_COOLDOWN_SEC:
            return 0.0, 0.0, None

        matched = [kw for kw in APOLOGY_KEYWORDS if kw in text]
        if not matched:
            return 0.0, 0.0, None

        bp.apology_count += 1
        bp.last_apology_ts = now

        # 好感越低，道歉效果越明显（雪中送炭）
        need_factor = max(0.5, min(2.0, (50 - current_fav) / 50))
        fav_recovery = APOLOGY_RECOVERY * need_factor
        int_recovery = fav_recovery * 0.4

        event = f"🕊️ 道歉恢复「{'、'.join(matched[:3])}」（好感+{fav_recovery:.1f}）"
        return fav_recovery, int_recovery, event

    def _check_milestones(
        self, bp: BehaviorProfile, total_interactions: int
    ) -> Tuple[float, float, List[str]]:
        """检测关系里程碑"""
        fav_total = 0.0
        int_total = 0.0
        events = []

        for threshold, (key, label, reward) in MILESTONES.items():
            if key in bp.achieved_milestones:
                continue
            if total_interactions >= threshold:
                bp.achieved_milestones.append(key)
                fav_total += reward
                int_total += reward * 0.5
                events.append(f"🏆 里程碑「{label}」达成！（好感+{reward:.1f}）")

        return fav_total, int_total, events
