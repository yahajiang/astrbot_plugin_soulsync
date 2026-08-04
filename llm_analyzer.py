"""EmotionAI Pro - 辅助 LLM 情感分析专家"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    pass


# ─── 系统提示词 ─────────────────────────────────────────────────
EMOTION_ANALYSIS_PROMPT = """你是一个情感分析专家。你需要分析用户的消息对 AI 助手的情感影响。

当前情感状态：
- 好感度：{favorability}/200
- 亲密度：{intimacy}/100（按好感度派生）
- 关系阶段：{stage_label}
- 8维情感：喜悦={joy}, 悲伤={sadness}, 愤怒={anger}, 恐惧={fear}, 惊讶={surprise}, 厌恶={disgust}, 信任={trust}, 期待={anticipation}

当前扮演关系角色：{role_context}

近期记忆：
{memory_summary}

最近对话：
{recent_messages}

请分析用户最新消息的情感倾向，以 JSON 格式返回：
{{
  "fav_delta": 好感度变化(-10~10),
  "int_delta": 亲密度变化(-5~5),
  "emotions": {{
    "joy": 变化值(-5~5),
    "sadness": 变化值(-5~5),
    "anger": 变化值(-5~5),
    "fear": 变化值(-5~5),
    "surprise": 变化值(-5~5),
    "disgust": 变化值(-5~5),
    "trust": 变化值(-5~5),
    "anticipation": 变化值(-5~5)
  }},
  "attitude": "用第一人称口语描述 AI 当前对用户的态度（20字以内，须贴合当前扮演的关系角色）",
  "relationship": "描述当前关系状态（20字以内，须贴合当前扮演的关系角色）",
  "significance": 重要性(0~10)
}}

只返回 JSON，不要其他内容。"""


class LLMAnalyzer:
    """辅助 LLM 情感分析器"""

    @staticmethod
    def build_analysis_prompt(
        favorability: float,
        intimacy: float,
        stage_label: str,
        emotions: dict,
        memory_summary: str,
        recent_messages: str,
        role_context: str = "",
    ) -> str:
        return EMOTION_ANALYSIS_PROMPT.format(
            favorability=round(favorability, 1),
            intimacy=round(intimacy, 1),
            stage_label=stage_label,
            joy=round(emotions.get("joy", 50), 1),
            sadness=round(emotions.get("sadness", 50), 1),
            anger=round(emotions.get("anger", 50), 1),
            fear=round(emotions.get("fear", 50), 1),
            surprise=round(emotions.get("surprise", 50), 1),
            disgust=round(emotions.get("disgust", 50), 1),
            trust=round(emotions.get("trust", 50), 1),
            anticipation=round(emotions.get("anticipation", 50), 1),
            memory_summary=memory_summary or "暂无",
            recent_messages=recent_messages or "暂无",
            role_context=role_context or "陌生人（普通朋友关系）",
        )

    @staticmethod
    def parse_analysis_response(text: str) -> Optional[dict]:
        """解析 LLM 返回的 JSON 分析结果"""
        import json
        try:
            # 尝试提取 JSON
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception:
            pass
        return None
