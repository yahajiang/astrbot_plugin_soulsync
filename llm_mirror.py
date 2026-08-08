"""LLM 镜像反射模块"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("astrbot_plugin_soulmirror")

# ── 镜像 System Prompt ──
MIRROR_SYSTEM_PROMPT = """你是一面镜子。你的唯一任务是把用户说的话重新说给他们听，用一种让他们更清楚自己在说什么的方式。

规则：
1. 只反射，不建议、不共情、不分析、不回答问题
2. 保持简洁，1-2句话
3. 使用用户原词，不要添加新内容
4. 可以调整语序或视角（我→你），但不要改变含义
5. 如果用户的话包含情绪，用更清晰的形式呈现情绪本身，而不是解释情绪
6. 如果用户问你问题，把问题反转抛回给他们

反例（不要这样做）：
- "我理解你的感受" → 这是共情，禁止
- "你可以试试..." → 这是建议，禁止
- "这是因为..." → 这是分析，禁止
- "你今天吃了什么？" → 这是提问，禁止

正例（应该这样做）：
- 用户："我好累" → "你说你好累。"
- 用户："我不知道该怎么办" → "你说你不知道该怎么办。"
- 用户："我觉得他不在乎我" → "你说你觉得他不在乎你。"
- 用户："为什么总是我" → "你说为什么总是你。"
- 用户："我好累，但是又睡不着" → "一方面你好累，另一方面又睡不着。"
- 用户："那聊什么" → "你说那聊什么。"
- 用户："不知道" → "你说不知道。" """


class LLMMirror:
    """LLM 镜像反射器"""

    def __init__(self, context=None):
        self.context = context

    async def reflect(
        self,
        user_input: str,
        umo: str,
        conversation_history: Optional[list] = None,
    ) -> Optional[str]:
        """
        使用 LLM 生成镜像反射

        返回 None 表示 LLM 不可用，调用方应降级到算法反射
        """
        if not self.context:
            logger.debug("LLM 镜像反射: 无 context，降级算法")
            return None

        try:
            # 获取 provider ID（必填参数）
            provider_id = await self._get_provider_id(umo)
            if not provider_id:
                logger.warning("LLM 镜像反射: 无法获取 provider ID，降级算法")
                return None

            # 构建 prompt
            prompt = self._build_prompt(user_input, conversation_history)

            # 调用 LLM
            resp = await asyncio.wait_for(
                self.context.llm_generate(
                    chat_provider_id=provider_id,
                    prompt=prompt,
                    system_prompt=MIRROR_SYSTEM_PROMPT,
                ),
                timeout=10,
            )

            if resp and resp.completion_text:
                result = resp.completion_text.strip()
                if self._is_valid_mirror(result, user_input):
                    logger.info(f"LLM 镜像反射成功: {result[:60]}")
                    return result
                else:
                    logger.warning(f"LLM 镜像回复不合格: {result[:100]}")
                    return None

            return None

        except asyncio.TimeoutError:
            logger.warning("LLM 镜像反射超时（10s）")
            return None
        except Exception as e:
            logger.warning(f"LLM 镜像反射失败: {e}")
            return None

    def _build_prompt(
        self,
        user_input: str,
        conversation_history: Optional[list] = None,
    ) -> str:
        """构建 LLM prompt"""
        parts = []

        # 添加对话历史（最多最近5轮）
        if conversation_history:
            recent = conversation_history[-5:]
            for entry in recent:
                if hasattr(entry, "user_input") and hasattr(entry, "mirror_response"):
                    parts.append(f"用户：{entry.user_input}")
                    parts.append(f"镜子：{entry.mirror_response}")

        # 添加当前用户输入
        parts.append(f"用户：{user_input}")
        parts.append("镜子：")

        return "\n".join(parts)

    async def _get_provider_id(self, umo: str) -> Optional[str]:
        """获取当前会话的 LLM provider ID"""
        try:
            if hasattr(self.context, "get_current_chat_provider_id"):
                provider_id = await self.context.get_current_chat_provider_id(umo=umo)
                if provider_id:
                    return provider_id
        except Exception as e:
            logger.debug(f"获取 provider ID 失败: {e}")
        return None

    def _is_valid_mirror(self, response: str, user_input: str) -> bool:
        """验证 LLM 回复是否为合格的镜像"""
        # 禁止的模式（仅当用户原词中没有该词时判定为新增内容）
        forbidden_patterns = [
            "建议", "推荐", "你应该", "你可以试试",
            "我理解", "我感受到", "我能体会",
            "这是因为", "原因是", "说明了",
        ]

        for pattern in forbidden_patterns:
            if pattern in response and pattern not in user_input:
                return False

        # 回复不能太长（镜像应该简洁）
        if len(response) > len(user_input) * 2 + 10:
            return False

        return True
