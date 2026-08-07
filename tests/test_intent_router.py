"""SoulSync v2.20 - P4 意图识别测试

覆盖：查询类自然语言意图命中、闲聊不误杀、命令不参与识别、
dispatch_intent_query 静默卡片输出 + 阻断聊天、意图-命令映射完整性。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from astrbot_plugin_soulsync.intent_router import (
    INTENT_QUERY_CMD,
    IntentRouter,
    dispatch_intent_query,
)


router = IntentRouter()


# ── 1. 查询意图命中 ─────────────────────────────────────
def test_view_status_cases():
    for text in [
        "我们之间现在算什么关系？",
        "我们是什么关系",
        "你现在对我的好感是多少",
        "你对我的好感度如何",
        "我们到哪个阶段了",
        "我们现在进展到什么程度",
        "你对我什么态度",
        "我在你心里算什么",
    ]:
        assert router.match(text) == "view_status", f"应识别 view_status: {text}"


def test_view_memory_cases():
    for text in [
        "你还记得我们第一次见面吗",
        "你记得我喜欢吃什么吗",
        "我们之间有什么回忆",
        "回顾一下我们的记忆",
        "我们是怎么认识的",
        "回忆起我们初次见面",
    ]:
        assert router.match(text) == "view_memory", f"应识别 view_memory: {text}"


def test_view_environment_cases():
    for text in [
        "现在是什么天气",
        "今天天气怎么样",
        "现在什么季节",
        "外面气温怎么样",
        "现在是什么节气",
        "此刻是什么月相",
    ]:
        assert router.match(text) == "view_environment", f"应识别 view_environment: {text}"


def test_view_ranking_cases():
    for text in [
        "好感排行",
        "谁的好感最高",
        "排行榜",
    ]:
        assert router.match(text) == "view_ranking", f"应识别 view_ranking: {text}"


def test_view_anniversary_cases():
    for text in [
        "我们认识多久了",
        "我们在一起多少天了",
        "我们认识纪念日是哪天",
        "我们是什么时候认识的",
    ]:
        assert router.match(text) == "view_anniversary", f"应识别 view_anniversary: {text}"


# ── 2. 闲聊不误杀 ──────────────────────────────────────
def test_chat_not_matched():
    for text in [
        "今天吃什么",
        "哈哈哈",
        "我们什么时候去吃饭",
        "我觉得我们像朋友",
        "你是我好感最高的人",
        "今天天气真好",
        "你还记得吗",
        "今天晚饭吃火锅吧",
        "晚安",
    ]:
        assert router.match(text) is None, f"闲聊不应命中: {text}"


# ── 3. 命令/空消息不参与 ────────────────────────────────
def test_command_and_empty_not_matched():
    assert router.match("") is None
    assert router.match("  ") is None
    assert router.match("/状态") is None
    assert router.match("／状态 好感") is None
    assert router.match("你好") is None


# ── 4. 意图-命令映射完整性 ──────────────────────────────
def test_mapping_covers_all_intents():
    router_intents = set(router.intents())
    mapped = set(INTENT_QUERY_CMD)
    assert router_intents == mapped, f"规则意图与映射不一致: {router_intents ^ mapped}"


# ── 5. dispatch 集成：静默卡片 + 阻断聊天 ───────────────
class _Event:
    def __init__(self, text):
        self.message_str = text
        self.sent = []
        self.stopped = False

    def plain_result(self, text):
        return ("plain", text)

    async def send(self, res):
        self.sent.append(res)

    def stop_event(self):
        self.stopped = True


class _Owner:
    def __init__(self):
        self.intent_router = IntentRouter()

    async def cmd_favorability(self, event):
        yield event.plain_result("📊 状态卡片")

    async def cmd_memory(self, event):
        yield event.plain_result("🧠 记忆摘要")


def test_dispatch_query_card_and_stop():
    async def run():
        ev = _Event("我们之间现在算什么关系？")
        blocked = await dispatch_intent_query(_Owner(), ev, router)
        assert blocked is True
        assert len(ev.sent) == 1 and ev.sent[0][0] == "plain"
        assert ev.stopped is True, "命中查询意图应阻断聊天"

    asyncio.run(run())


def test_dispatch_memory_card():
    async def run():
        ev = _Event("你还记得我们第一次见面吗")
        blocked = await dispatch_intent_query(_Owner(), ev, router)
        assert blocked is True
        assert ev.sent[0][1] == "🧠 记忆摘要"
        assert ev.stopped is True

    asyncio.run(run())


def test_dispatch_chat_does_not_block():
    async def run():
        ev = _Event("今天吃什么")
        blocked = await dispatch_intent_query(_Owner(), ev, router)
        assert blocked is False
        assert ev.sent == []
        assert ev.stopped is False

    asyncio.run(run())


def test_dispatch_missing_cmd_does_not_block():
    async def run():
        class NoStatus(_Owner):
            cmd_favorability = None

        ev = _Event("我们之间现在算什么关系？")
        blocked = await dispatch_intent_query(NoStatus(), ev, router)
        assert blocked is False, "命令缺失时应安全放行"
        assert ev.sent == [] and ev.stopped is False

    asyncio.run(run())


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS: {fn.__name__}")
            ok += 1
        except Exception:
            print(f"FAIL: {fn.__name__}")
            traceback.print_exc()
    print(f"全部 {ok}/{len(fns)} 通过")
