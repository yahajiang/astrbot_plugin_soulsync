"""rebirth/rebirth_engine.py - 转生系统引擎

Sprint 4 S4-01~S4-04 产出物。
好感 >= 200 时触发转生，好感重置为 20 + 段位×5，获得永久 buff。
每转关键词敏感度 +5%，冷落抗性 +3%（递增式无限轮回）。

用法:
    from rebirth.rebirth_engine import RebirthEngine
    engine = RebirthEngine(pool)
    result = engine.check_and_rebirth(user_id, current_favor)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

logger = logging.getLogger("soulsync.rebirth")

# 转生配置
FAV_CAP = 200              # 好感封顶值
BASE_RESET_FAVOR = 20      # 转生后基础好感
RESET_FAVOR_PER_LEVEL = 5  # 每转额外好感
SENSITIVITY_BONUS = 0.05   # 每转关键词敏感度 +5%
COLD_RESISTANCE_BONUS = 0.03  # 每转冷落抗性 +3%

# 中文数字映射
_CN_NUMS = "零一二三四五六七八九十百千万亿"


def _to_cn_level(n: int) -> str:
    """将数字转为中文（1~10 用中文数字，超出用阿拉伯）"""
    if 0 <= n <= 10:
        return _CN_NUMS[n] if n <= 10 else str(n)
    return str(n)


class RebirthEngine:
    """转生系统引擎"""

    def __init__(self, pool):
        self.pool = pool

    def check_and_rebirth(self, user_id: str, current_favor: float) -> Optional[dict]:
        """检查并执行转生，返回转生结果（无则 None）

        Returns:
            {
                "rebirth_count": int,
                "old_favor": float,
                "new_favor": float,
                "sensitivity_bonus": float,
                "cold_resistance_bonus": float,
                "title": str,  # 如 "轮回·三"
            }
        """
        state = self._get_state(user_id)
        if state is None:
            state = {"prestige_level": 0, "total_rebirths": 0, "permanent_buffs": {}}

        # 计算当前转生需要的好感阈值（递增式）
        level = state["prestige_level"]
        required_favor = FAV_CAP + level * 50  # 每转阈值递增 50

        if current_favor < required_favor:
            return None

        # 执行转生
        new_level = level + 1
        new_favor = BASE_RESET_FAVOR + new_level * RESET_FAVOR_PER_LEVEL
        sens_bonus = round(SENSITIVITY_BONUS * new_level, 4)
        cold_bonus = round(COLD_RESISTANCE_BONUS * new_level, 4)

        state["prestige_level"] = new_level
        state["total_rebirths"] = state.get("total_rebirths", 0) + 1
        state["permanent_buffs"] = {
            "sensitivity_bonus": sens_bonus,
            "cold_resistance_bonus": cold_bonus,
        }
        state["last_rebirth_ts"] = time.time()

        self._save_state(user_id, state)

        title = f"轮回·{_to_cn_level(new_level)}"
        result = {
            "rebirth_count": new_level,
            "old_favor": current_favor,
            "new_favor": new_favor,
            "sensitivity_bonus": sens_bonus,
            "cold_resistance_bonus": cold_bonus,
            "title": title,
        }
        logger.info(f"[Rebirth] {user_id} 转生至 {title}！好感 {current_favor:.0f} → {new_favor}")
        return result

    def get_state(self, user_id: str) -> dict:
        """获取转生状态"""
        return self._get_state(user_id) or {
            "prestige_level": 0,
            "total_rebirths": 0,
            "permanent_buffs": {},
        }

    def get_next_rebirth_info(self, user_id: str, current_favor: float) -> dict:
        """获取下次转生信息"""
        state = self._get_state(user_id) or {"prestige_level": 0}
        level = state["prestige_level"]
        required = FAV_CAP + level * 50
        remaining = max(0, required - current_favor)
        return {
            "current_level": level,
            "next_level": level + 1,
            "required_favor": required,
            "current_favor": current_favor,
            "remaining": remaining,
            "title": f"轮回·{_to_cn_level(level + 1)}",
        }

    def _get_state(self, user_id: str) -> Optional[dict]:
        """从数据库读取转生状态"""
        with self.pool.connect() as conn:
            row = conn.execute(
                "SELECT extra_json FROM behavior_profile WHERE user_id=?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        extra = json.loads(row["extra_json"]) if row["extra_json"] else {}
        return extra.get("rebirth_state")

    def _save_state(self, user_id: str, state: dict):
        """保存转生状态到 behavior_profile.extra_json"""
        with self.pool.connect() as conn:
            row = conn.execute(
                "SELECT extra_json FROM behavior_profile WHERE user_id=?",
                (user_id,),
            ).fetchone()
            extra = json.loads(row["extra_json"]) if row and row["extra_json"] else {}
            extra["rebirth_state"] = state
            conn.execute(
                "UPDATE behavior_profile SET extra_json=? WHERE user_id=?",
                (json.dumps(extra, ensure_ascii=False), user_id),
            )
            conn.commit()
