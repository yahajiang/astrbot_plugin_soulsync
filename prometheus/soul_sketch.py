"""prometheus/soul_sketch.py - 离线灵魂素描（沉淀层）

Project Prometheus Layer 2。
用户静默 4h 后生成 10 条灵魂棱镜 + 1 项沟通建议。

用法:
    from prometheus.soul_sketch import SoulSketcher
    sketcher = SoulSketcher(pool, llm_analyzer)
    result = await sketcher.check_and_generate(user_id, profile, recent_turns)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

logger = logging.getLogger("soulsync.prometheus.sketch")

# 触发条件
MIN_OFFLINE_HOURS = 4      # 最少离线 4 小时
MIN_DAYS_BETWEEN = 5        # 两次素描最少间隔 5 天
MIN_RECENT_TURNS = 50       # 近 7 天最少 50 轮互动

# 沟通建议分类
COMM_STYLE_EMPATHY = "共情优先型"
COMM_STYLE_LOGIC = "逻辑清晰型"
COMM_STYLE_ENCOURAGE = "鼓励型"

SKETCH_PROMPT = """你是一位深度心理分析师。请根据以下用户的行为数据，生成一份精简的灵魂素描。

## 用户行为数据
{behavior_data}

## 任务
请生成：
1. **10 条灵魂棱镜**：每条 ≤15 字，必须揭示人格矛盾/深层信念/防御机制。
   格式：每条一行，以数字开头。
2. **1 项沟通建议**：从以下三选一（仅输出类型名称）：
   - 共情优先型
   - 逻辑清晰型
   - 鼓励型

## 输出格式
棱镜:
1. xxx
2. xxx
...

沟通建议: xxx
"""


class SoulSketcher:
    """离线灵魂素描器"""

    def __init__(self, pool, llm_analyzer=None):
        self.pool = pool
        self.llm_analyzer = llm_analyzer
        self._pending: dict = {}  # {user_id: task_info}

    async def check_and_generate(self, user_id: str, profile, recent_turns: int = 0,
                                  llm_call_func=None) -> Optional[dict]:
        """检查条件并生成素描（返回生成结果或 None）

        Args:
            user_id: 用户 ID
            profile: EmotionProfile 对象
            recent_turns: 近 7 天互动轮次
            llm_call_func: 异步 LLM 调用函数 async fn(prompt) -> str
        """
        from .psych_store import PsychStore
        store = PsychStore(self.pool)

        # 条件 1：距上次素描 ≥ 5 天
        last_gen = store.get_last_generated_at(user_id)
        days_since = (time.time() - last_gen) / 86400 if last_gen > 0 else 999
        if days_since < MIN_DAYS_BETWEEN:
            return None

        # 条件 2：近 7 天互动 ≥ 50 轮
        if recent_turns < MIN_RECENT_TURNS:
            return None

        # 条件 3：需要 LLM 调用函数
        if not llm_call_func:
            return None

        # 构建行为数据
        behavior_data = self._build_behavior_data(user_id, profile, recent_turns)

        # 生成素描
        try:
            prompt = SKETCH_PROMPT.format(behavior_data=behavior_data)
            response = await llm_call_func(prompt)
            if not response:
                return None

            prisms, comm_style = self._parse_response(response)

            # 获取当前基准线
            from .sliding_window import MessageWindow
            baseline = profile.favorability  # 或从窗口获取

            # 保存
            version = store.save(user_id, prisms, comm_style, baseline)

            result = {
                "version": version,
                "prisms": prisms,
                "comm_style": comm_style,
                "generated_at": time.time(),
            }
            logger.info(f"[SoulSketch] {user_id} 素描生成完成 v{version}，棱镜 {len(prisms)} 条")
            return result

        except Exception as e:
            logger.warning(f"[SoulSketch] {user_id} 素描生成失败: {e}")
            return None

    def _build_behavior_data(self, user_id: str, profile, recent_turns: int) -> str:
        """构建行为数据摘要"""
        lines = []
        lines.append(f"好感度: {profile.favorability:.1f}")
        lines.append(f"亲密度: {profile.intimacy:.1f}")
        lines.append(f"关系阶段: {getattr(profile, 'stage_label', '未知')}")
        lines.append(f"总互动次数: {profile.total_interactions}")
        lines.append(f"近 7 天互动轮次: {recent_turns}")

        # 情感维度
        emotions = getattr(profile, 'emotions', {})
        if emotions:
            emo_str = " / ".join(f"{k}={v:.0f}" for k, v in emotions.items())
            lines.append(f"情感维度: {emo_str}")

        # 行为模式
        lines.append(f"正面互动: {profile.positive_interactions} 次")
        lines.append(f"负面互动: {profile.negative_interactions} 次")

        return "\n".join(lines)

    def _parse_response(self, response: str) -> tuple:
        """解析 LLM 返回的棱镜和沟通建议"""
        prisms = []
        comm_style = COMM_STYLE_EMPATHY  # 默认

        lines = response.strip().split("\n")
        in_prisms = False
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if "棱镜" in line and ":" in line:
                in_prisms = True
                continue
            if "沟通建议" in line and ":" in line:
                in_prisms = False
                style_part = line.split(":", 1)[1].strip()
                if "共情" in style_part or "感性" in style_part:
                    comm_style = COMM_STYLE_EMPATHY
                elif "逻辑" in style_part or "直给" in style_part or "清晰" in style_part:
                    comm_style = COMM_STYLE_LOGIC
                elif "鼓励" in style_part:
                    comm_style = COMM_STYLE_ENCOURAGE
                continue
            if in_prisms:
                # 去掉序号前缀
                import re
                cleaned = re.sub(r'^\d+[\.\、\)\s]+', '', line).strip()
                if cleaned and len(cleaned) <= 20:
                    prisms.append(cleaned)

        # 确保最多 10 条
        prisms = prisms[:10]
        return prisms, comm_style

    def get_prisms_context(self, user_id: str) -> str:
        """获取棱镜上下文（注入 LLM 提示词）"""
        from .psych_store import PsychStore
        store = PsychStore(self.pool)
        latest = store.get_latest(user_id)
        if not latest or not latest["prisms"]:
            return ""
        prisms = latest["prisms"]
        lines = ["灵魂棱镜（深层人格洞察）："]
        for i, p in enumerate(prisms, 1):
            lines.append(f"  {i}. {p}")
        return "\n".join(lines)
