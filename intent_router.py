"""SoulSync - 自然语言意图识别（v2.20 静默命令路由）

将查询类自然语言消息映射为内部查询意图（view_status / view_memory 等），
命中后由 dispatch_intent_query 直接输出状态卡片或记忆摘要并阻断聊天，
用户无需输入命令。非查询消息返回 None（聊天意图），不影响正常 LLM 流程。

规则设计原则：仅匹配强查询词（关系/好感/阶段/回忆/天气/排行/纪念日等），
避免误杀"今天吃什么""我觉得我们像朋友"等闲聊。
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("soulsync.intent")

# (意图名, 正则) 规则表；顺序即优先级（先命中先返回）
_INTENT_RULES: List[Tuple[str, str]] = [
    # ── view_anniversary：纪念日 / 相识时长 ──
    ("view_anniversary", r"我们(认识|在一起)(多久|多长|多长时间|多少天|多少年)"),
    ("view_anniversary", r"我们(的)?(认识|相遇|在一起)纪念日(是|在)?(哪天|哪一天|几号|什么时候)"),
    ("view_anniversary", r"我们(是)?什么时候(认识|在一起)的?"),
    # ── view_ranking：好感排行 ──
    ("view_ranking", r"(好感|亲密|亲密度)(排行|排名|榜)"),
    ("view_ranking", r"(谁|谁们|群友)(的)?好感(最高|排第一|第一|领先)"),
    ("view_ranking", r"排行榜"),
    # ── view_environment：环境感知 ──
    ("view_environment", r"(现在|今天|此刻)?(是)?什么(天气|季节|节气|月相)"),
    ("view_environment", r"(现在|今天|外面)(天气|气温)怎么(样)?[？?]?"),
    ("view_environment", r"现在(是)?(什么|哪个)(季节|节气|月相)"),
    # ── view_status：关系 / 好感 / 阶段 / 态度 ──
    ("view_status", r"(我们|咱|你和我|我?和你).{0,8}(什么关系|啥关系)"),
    ("view_status", r"(现在|目前)?对我的?(好感|好感度)(是)?(多少|咋样|怎么样|如何)"),
    ("view_status", r"你(对我|和我的)?好感(度)?(现在|目前)?(是)?(多少|多少了)"),
    ("view_status", r"我们(现在|目前)?(到|进展|处于)?到?(什么|哪个|啥)(阶段|程度)"),
    ("view_status", r"你(现在|目前)?对我(是)?(什么|啥)态度"),
    ("view_status", r"(我在你心里|你心里我)(算|是)?(什么|啥)"),
    # ── view_memory：记忆回顾（放最后，覆盖面最宽）──
    ("view_memory", r"(你还?记得)(.{1,40}?)(吗|么)"),
    ("view_memory", r"(我们|咱)(之间|俩)?(有什么|有没有|有啥)(回忆|记忆|过往|故事)"),
    ("view_memory", r"回顾(一下|看看|看看)?(我们|咱)?(的)?(回忆|记忆|过往|相处)"),
    ("view_memory", r"我们(是)?怎么(认识|相遇)的"),
    ("view_memory", r"(回忆起|记起)(我们|咱)?(第一次|初次)(见面|相遇)"),
]

# 查询意图 → 插件查询命令（静默执行后阻断聊天）
INTENT_QUERY_CMD: Dict[str, str] = {
    "view_status": "cmd_favorability",      # 状态卡片（好感/阶段/画像）
    "view_memory": "cmd_memory",            # 私人记忆库摘要
    "view_environment": "cmd_tpd_weather",  # 环境感知（天气/季节/节气/月相）
    "view_ranking": "cmd_leaderboard",      # 好感排行榜
    "view_anniversary": "cmd_anniversary",  # 纪念日 / 相识时长
}


class IntentRouter:
    """轻量正则意图分类器：match(text) → 意图名，未命中返回 None。"""

    def __init__(self, rules: Optional[List[Tuple[str, str]]] = None):
        self.rules = [(name, re.compile(pattern)) for name, pattern in (rules or _INTENT_RULES)]

    def match(self, text: str) -> Optional[str]:
        if not text or not text.strip():
            return None
        text = text.strip()
        # 命令消息（/指令 或 ／指令）不参与意图识别，交给命令路由
        if text.startswith(("/", "／")):
            return None
        for name, pattern in self.rules:
            if pattern.search(text):
                return name
        return None

    def rule_count(self) -> int:
        return len(self.rules)

    def intents(self) -> List[str]:
        return list(dict.fromkeys(name for name, _ in self.rules))


async def dispatch_intent_query(owner, event, router: IntentRouter) -> bool:
    """意图命中 → 调用 owner 上对应查询命令输出卡片并阻断聊天。返回是否阻断。

    owner：插件实例（提供 config 之外的查询命令方法，如 cmd_favorability）；
    event：AstrMessageEvent 鸭子类型（message_str / plain_result / send / stop_event）。
    """
    text = (event.message_str or "").strip()
    if not text:
        return False
    intent = router.match(text)
    if not intent:
        return False
    cmd_name = INTENT_QUERY_CMD.get(intent)
    if not cmd_name:
        return False
    cmd = getattr(owner, cmd_name, None)
    if cmd is None:
        return False
    sent_any = False
    async for res in cmd(event):
        try:
            await event.send(res)
            sent_any = True
        except Exception as e:
            logger.warning(f"SoulSync 意图卡片发送失败 [{intent}]: {e}")
    if sent_any:
        try:
            event.stop_event()
        except Exception:
            pass
        logger.info(f"SoulSync 意图路由 [{intent}] → {cmd_name}，阻断聊天")
    return sent_any
