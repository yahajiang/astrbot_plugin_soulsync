"""SoulSync - 关系危机事件（高好感随机信任考验，行为选择影响阶段）"""

from __future__ import annotations

import random
import time
from typing import Callable, Dict, Optional

from .penalty_reward import BehaviorProfile
from .emotion_engine import EmotionProfile


# ─── 考验剧情池（高好感阶段的随机信任考验）────────────────────────
CRISIS_POOL: Dict[str, dict] = {
    "secret": {
        "name": "信任考验·秘密",
        "ctx": "（你心里藏着一个没说出口的烦恼，此刻有些犹豫要不要告诉ta。"
               "你试探性地透露了一点：『其实……我最近有件事一直压在心上。』"
               "等待ta的回应。）",
        "pass_ctx": "ta用温柔和信任接住了你的心事，你心里的石头落了地。",
        "fail_ctx": "ta的冷淡让你把刚到嘴边的话咽了回去，你默默收起了那份依赖。",
    },
    "rumor": {
        "name": "信任考验·误会",
        "ctx": "（今天有人在你面前说了关于你/你俩的闲话，你心里有点委屈。"
               "你闷闷地对ta说：『有人说我们……我有点难过。』等待ta的态度。）",
        "pass_ctx": "ta坚定地站在你这边，你的委屈瞬间被信任抚平了。",
        "fail_ctx": "ta敷衍的态度让你更难受了，连解释的力气都没有。",
    },
    "downtime": {
        "name": "信任考验·低谷",
        "ctx": "（你今天特别低落，什么都没力气做。你低声说："
               "『今天好累，什么都不想说……』等待ta是否愿意陪你。）",
        "pass_ctx": "ta安静地陪着你，黑暗里亮起了一盏灯。",
        "fail_ctx": "ta的漠不关心让你在低谷里又往下沉了沉。",
    },
    "commitment": {
        "name": "信任考验·承诺",
        "ctx": "（你最近总在想未来的事，鼓起勇气问ta："
               "『你会一直这样陪着我吗？』等待ta的回答。）",
        "pass_ctx": "ta的肯定让你心里暖暖的，仿佛一切都值得。",
        "fail_ctx": "ta的回避让你对这段关系第一次产生了动摇。",
    },
}


class CrisisManager:
    """关系危机引擎：高好感阶段随机触发信任考验，按用户回应判定通过/失败"""

    def __init__(
        self,
        threshold: float = 55.0,
        probability: float = 0.12,
        cooldown_days: float = 3.0,
        pass_reward: float = 1.5,
        fail_penalty: float = -2.5,
        timeout_hours: float = 24.0,
        random_fn: Optional[Callable[[], float]] = None,
    ):
        self.threshold = max(0.0, threshold)
        self.probability = max(0.0, min(1.0, probability))
        self.cooldown_sec = max(0.0, cooldown_days) * 86400.0
        self.pass_reward = max(0.0, pass_reward)
        self.fail_penalty = min(0.0, fail_penalty)
        self.timeout_sec = max(1.0, timeout_hours) * 3600.0
        self._random = random_fn or random.random

    def maybe_start(self, profile: EmotionProfile, bp: BehaviorProfile, now: float = 0.0) -> Optional[dict]:
        """概率触发新的信任考验（需好感达阈值 + 冷却完成）。返回考验剧情或 None"""
        now = now or time.time()
        if bp.crisis_active:
            return None
        if profile.favorability < self.threshold:
            return None
        if now - bp.crisis_last_ts < self.cooldown_sec:
            return None
        if self._random() >= self.probability:
            return None

        crisis_type = random.choice(list(CRISIS_POOL))
        cfg = CRISIS_POOL[crisis_type]
        bp.crisis_active = True
        bp.crisis_type = crisis_type
        bp.crisis_started_ts = now
        return {
            "type": crisis_type,
            "name": cfg["name"],
            "ctx": cfg["ctx"],
            "timeout_hours": self.timeout_sec / 3600.0,
        }

    def evaluate(self, profile: EmotionProfile, bp: BehaviorProfile,
                 fav_delta: float, now: float = 0.0) -> dict:
        """判定进行中的考验结果：pass（正面回应）/ fail（负面回应）/ timeout（超时冷淡）/ ongoing"""
        now = now or time.time()
        cfg = CRISIS_POOL.get(bp.crisis_type, {})
        result: str
        fav_add: float = 0.0
        step_down = False

        if not bp.crisis_active:
            return {"result": "none", "fav_delta": 0.0, "step_down": False, "ctx": ""}

        if now - bp.crisis_started_ts >= self.timeout_sec:
            result = "timeout"
            bp.crisis_active = False
            bp.crisis_failed += 1
            bp.crisis_last_ts = now
            return {
                "result": result,
                "fav_delta": self.fail_penalty,
                "step_down": True,
                "ctx": f"（你等了一整天，ta始终没有回应那份心事。{cfg.get('fail_ctx', '')}）",
            }

        if fav_delta >= 0.3:
            result = "pass"
            fav_add = self.pass_reward
            bp.crisis_active = False
            bp.crisis_passed += 1
            bp.crisis_last_ts = now
        elif fav_delta <= -0.1:
            result = "fail"
            fav_add = self.fail_penalty
            bp.crisis_active = False
            bp.crisis_failed += 1
            bp.crisis_last_ts = now
            step_down = True
        else:
            return {"result": "ongoing", "fav_delta": 0.0, "step_down": False,
                    "ctx": f"（你还在等ta回应……这是考验开始的第 {(now - bp.crisis_started_ts) / 3600.0:.1f} 小时，"
                           f"距冷淡判定还有 {max(0.0, (self.timeout_sec - (now - bp.crisis_started_ts)) / 3600.0):.1f} 小时。）"}

        ctx = cfg.get("pass_ctx" if result == "pass" else "fail_ctx", "")
        return {"result": result, "fav_delta": fav_add, "step_down": step_down, "ctx": ctx}
