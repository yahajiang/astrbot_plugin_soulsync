"""SoulSync v2.20 - P1 事件总线测试

覆盖：EventBus 订阅/取消订阅/发布/异常隔离/清除，
emotion_engine.apply_change 触发 favor.changed 与 stage.advanced 事件。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from astrbot_plugin_soulsync.emotion_engine import (
    EmotionEngine,
    EmotionProfile,
    STAGES,
)
from astrbot_plugin_soulsync.event_bus import EventBus, Events, get_event_bus


# ── 1. EventBus 基础 ─────────────────────────────────────
def test_subscribe_and_publish():
    bus = EventBus()
    got = []
    bus.subscribe("test.evt", lambda *a: got.append(a))
    bus.publish("test.evt", 1, 2)
    assert got == [(1, 2)]


def test_unsubscribe():
    bus = EventBus()
    got = []
    def h(*a):
        got.append(a)
    cancel = bus.subscribe("test.evt", h)
    bus.publish("test.evt", 1)
    cancel()
    bus.publish("test.evt", 2)
    assert got == [(1,)]


def test_exception_isolation():
    bus = EventBus()
    got = []

    def bad(*a):
        raise RuntimeError("boom")

    def good(*a):
        got.append(a)

    bus.subscribe("test.evt", bad)
    bus.subscribe("test.evt", good)
    bus.publish("test.evt", 42)
    assert got == [(42,)]


def test_clear_and_count():
    bus = EventBus()
    bus.subscribe("a", lambda *_: None)
    bus.subscribe("a", lambda *_: None)
    bus.subscribe("b", lambda *_: None)
    assert bus.count() == 3
    assert bus.count("a") == 2
    bus.clear("a")
    assert bus.count("a") == 0
    bus.clear()
    assert bus.count() == 0


# ── 2. 事件名常量唯一性 ─────────────────────────────────
def test_event_names_unique():
    names = [v for k, v in vars(Events).items() if k.isupper()]
    assert len(names) == len(set(names))
    assert "favor.changed" in names
    assert "stage.advanced" in names


# ── 3. emotion_engine 埋点 ──────────────────────────────
def _fresh_profile():
    return EmotionProfile(user_id="u1", user_name="测试")


def test_favor_changed_event():
    bus = get_event_bus()
    bus.clear()
    events = []
    bus.subscribe(Events.FAVOR_CHANGED, lambda old, new, profile: events.append((old, new)))
    engine = EmotionEngine()
    profile = _fresh_profile()
    engine.apply_change(profile, fav_delta=10.0, int_delta=0.0, emotion_deltas={})
    assert len(events) == 1
    old, new = events[0]
    assert new - old == 5.0  # 正向增长放缓 0.5


def test_stage_advanced_event():
    bus = get_event_bus()
    bus.clear()
    events = []
    bus.subscribe(Events.STAGE_ADVANCED, lambda old, new, profile: events.append((old, new)))
    engine = EmotionEngine()
    profile = _fresh_profile()
    threshold = STAGES[1].composite_threshold
    profile.composite_score = threshold
    engine.apply_change(profile, fav_delta=200.0, int_delta=0.0, emotion_deltas={})
    assert len(events) == 1
    old, new = events[0]
    assert new > old


def test_no_event_when_unchanged():
    bus = get_event_bus()
    bus.clear()
    fav_events = []
    stage_events = []
    bus.subscribe(Events.FAVOR_CHANGED, lambda o, n, p: fav_events.append((o, n)))
    bus.subscribe(Events.STAGE_ADVANCED, lambda o, n, p: stage_events.append((o, n)))
    engine = EmotionEngine()
    profile = _fresh_profile()
    engine.apply_change(profile, fav_delta=0.0, int_delta=0.0, emotion_deltas={})
    assert fav_events == []
    assert stage_events == []


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
