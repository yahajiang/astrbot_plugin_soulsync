"""SoulSync v2.20 - P5 钩子机制测试

覆盖：注册/优先级顺序/阻断语义/异常隔离/启停/同步异步混用/空总线，
以及 dispatch 与钩子协作（意图识别作为前置钩子阻断聊天）。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from astrbot_plugin_soulsync.hook_bus import HookBus


# ── 1. 注册与顺序 ───────────────────────────────────────
def test_before_priority_order():
    bus = HookBus()
    order = []

    def p100(*a):
        order.append("p100")

    def p0(*a):
        order.append("p0")

    bus.register_before("later", p100, priority=100)
    bus.register_before("first", p0, priority=0)

    async def run():
        assert await bus.run_before() is False

    asyncio.run(run())
    assert order == ["p0", "p100"], "低数字优先级应先执行"


def test_same_priority_keeps_registration_order():
    bus = HookBus()
    order = []

    def a(*x):
        order.append("a")

    def b(*x):
        order.append("b")

    bus.register_before("a", a)
    bus.register_before("b", b)
    asyncio.run(bus.run_before())
    assert order == ["a", "b"]


# ── 2. 阻断语义 ─────────────────────────────────────────
def test_before_blocking_stops_later():
    bus = HookBus()
    order = []

    def blocker(*x):
        order.append("blocker")
        return True

    def later(*x):
        order.append("later")

    bus.register_before("blocker", blocker, priority=0)
    bus.register_before("later", later, priority=1)
    asyncio.run(bus.run_before())
    assert order == ["blocker"], "返回真值应阻断后续钩子"
    bus.register_before("later", later, priority=1)


# ── 3. 异常隔离 ─────────────────────────────────────────
def test_exception_isolation():
    bus = HookBus()
    order = []

    def bad(*x):
        raise RuntimeError("boom")

    def good(*x):
        order.append("good")

    bus.register_before("bad", bad, priority=0)
    bus.register_before("good", good, priority=1)
    assert asyncio.run(bus.run_before()) is False, "坏钩子异常应被隔离，流程继续"

    bus2 = HookBus()

    def bad_after(*x):
        raise RuntimeError("boom2")

    def good_after(*x):
        order.append("good_after")

    bus2.register_after("bad", bad_after)
    bus2.register_after("good", good_after)
    asyncio.run(bus2.run_after())
    assert order == ["good", "good_after"]


# ── 4. 同步/异步混用 ───────────────────────────────────
def test_mixed_sync_async():
    bus = HookBus()
    order = []

    def sync_fn(*x):
        order.append("sync")
        return True

    async def async_fn(*x):
        order.append("async")
        return True

    bus.register_before("sync", sync_fn, priority=0)
    bus.register_before("async", async_fn, priority=1)
    assert asyncio.run(bus.run_before()) is True
    assert order == ["sync"]


def test_async_after_runs_all():
    bus = HookBus()
    order = []

    async def a(*x):
        order.append("a")

    async def b(*x):
        order.append("b")

    bus.register_after("a", a)
    bus.register_after("b", b)
    asyncio.run(bus.run_after())
    assert order == ["a", "b"]


# ── 5. enable / disable / count ─────────────────────────
def test_enable_disable():
    bus = HookBus()
    calls = []

    def fn(*x):
        calls.append(1)
        return True

    bus.register_before("toggle", fn)
    assert bus.is_enabled("toggle")
    bus.disable("toggle")
    assert not bus.is_enabled("toggle")
    assert bus.count("before") == 0
    assert asyncio.run(bus.run_before()) is False, "禁用钩子不执行"
    assert calls == []
    bus.enable("toggle")
    assert asyncio.run(bus.run_before()) is True
    assert calls == [1]


def test_register_disabled_by_default():
    bus = HookBus()

    def fn(*x):
        return True

    bus.register_before("off", fn, enabled=False)
    assert not bus.is_enabled("off")
    assert asyncio.run(bus.run_before()) is False


# ── 6. 空总线 ───────────────────────────────────────────
def test_empty_bus():
    bus = HookBus()
    assert asyncio.run(bus.run_before()) is False
    asyncio.run(bus.run_after())


# ── 7. 与意图识别协作：前置钩子阻断 ─────────────────────
def test_intent_hook_via_bus():
    from astrbot_plugin_soulsync.intent_router import (
        IntentRouter,
        dispatch_intent_query,
    )

    class _Event:
        def __init__(self, text):
            self.message_str = text
            self.sent = []
            self.stopped = False

        def plain_result(self, t):
            return ("plain", t)

        async def send(self, res):
            self.sent.append(res)

        def stop_event(self):
            self.stopped = True

    class _Owner:
        def __init__(self):
            self.intent_router = IntentRouter()
            self.hook_bus = HookBus()
            self.hook_bus.register_before("intent_query", self._hook, priority=0)

        async def _hook(self, event):
            return await dispatch_intent_query(self, event, self.intent_router)

        async def cmd_favorability(self, event):
            yield event.plain_result("📊 状态卡片")

    async def run():
        owner = _Owner()
        ev = _Event("我们之间现在算什么关系？")
        blocked = await owner.hook_bus.run_before(ev)
        assert blocked is True, "意图钩子应阻断聊天"
        assert ev.sent and ev.stopped
        # 闲聊不阻断
        ev2 = _Event("今天吃什么")
        blocked2 = await owner.hook_bus.run_before(ev2)
        assert blocked2 is False and ev2.sent == [] and not ev2.stopped

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
