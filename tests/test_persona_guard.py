"""SoulSync v2.20 - P3 人格护栏测试

覆盖：自动锁定（50 轮稳定）、震荡回滚（24h 3 次剧变）、极端事件自动解锁、
管理员 2h 临时锁定、orchestrator 每轮护栏集成（auto_paused 时跳过隐式训练）。
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from astrbot_plugin_soulsync.trainer.persona.persona_guard import PersonaGuard
from astrbot_plugin_soulsync.trainer.persona.persona_modifier import PersonaModifier
from astrbot_plugin_soulsync.trainer.persona.persona_params import default_params
from astrbot_plugin_soulsync.trainer.trainer_storage import TrainerStorage


def _setup():
    tmp = tempfile.TemporaryDirectory()
    storage = TrainerStorage(Path(tmp.name))
    uid = "guard_test"
    modifier = PersonaModifier(storage, uid)
    guard = PersonaGuard(storage, uid, modifier)
    return tmp, storage, modifier, guard


# ── 1. 自动锁定 ─────────────────────────────────────────
def test_auto_lock_after_stable_turns():
    tmp, storage, modifier, guard = _setup()
    try:
        params = default_params()
        params.stability = 75.0  # 达标线 70
        for i in range(PersonaGuard.AUTO_LOCK_STABLE_TURNS):
            ev = guard.on_turn(params)
        assert params.locked, "50 轮稳定应自动锁定"
        assert ev.get("locked") is True
        assert storage.load("guard_test", "persona.json")["locked"] is True
    finally:
        tmp.cleanup()


def test_no_lock_when_stability_low():
    tmp, storage, modifier, guard = _setup()
    try:
        params = default_params()
        params.stability = 50.0
        for i in range(PersonaGuard.AUTO_LOCK_STABLE_TURNS + 5):
            guard.on_turn(params)
        assert not params.locked, "稳定度不达标不应锁定"
    finally:
        tmp.cleanup()


def test_no_lock_when_oscillating():
    tmp, storage, modifier, guard = _setup()
    try:
        params = default_params()
        params.stability = 75.0
        for i in range(PersonaGuard.AUTO_LOCK_STABLE_TURNS):
            params.grudge_coefficient += 5.0
            guard.on_turn(params)
        assert not params.locked, "持续波动不应触发自动锁定"
    finally:
        tmp.cleanup()


# ── 2. 震荡回滚 ─────────────────────────────────────────
def test_oscillation_rollback():
    tmp, storage, modifier, guard = _setup()
    try:
        params = default_params()
        base = params.grudge_coefficient
        # 首轮：建立稳定快照（参数未动）
        guard.on_turn(params)
        # 连续 3 次剧烈变化（每次 ≥3.0）→ 回滚至首轮快照
        for i in range(PersonaGuard.OSCILLATION_COUNT):
            params.grudge_coefficient += 5.0
            guard.on_turn(params)
        assert params.grudge_coefficient == base, "震荡 3 次应回滚到稳定快照"
        state = guard.get_state()
        assert any(e["kind"] == "rollback" for e in state["log"]), "应记录回滚日志"
        assert state["oscillation_count_24h"] == 0, "回滚后震荡计数应清零"
    finally:
        tmp.cleanup()


def test_oscillation_window_expiry():
    tmp, storage, modifier, guard = _setup()
    try:
        params = default_params()
        guard.on_turn(params)
        # 注入窗口外的旧时间戳（25h 前），不应触发回滚
        old_ts = [123456.0] * 3
        guard._state["oscillation_ts"] = old_ts
        guard._save()
        params.grudge_coefficient += 5.0
        ev = guard.on_turn(params)
        assert "rollback" not in ev, "窗口外旧计数不应触发回滚"
        assert params.grudge_coefficient == 6.0
    finally:
        tmp.cleanup()


# ── 3. 极端事件自动解锁 ─────────────────────────────────
def test_extreme_event_unlocks():
    tmp, storage, modifier, guard = _setup()
    try:
        params = default_params()
        modifier.lock(params)
        assert params.locked
        ok = guard.on_extreme_event(params, "betrayal")
        assert ok is True
        assert not params.locked, "极端事件应自动解锁"
        assert storage.load("guard_test", "persona.json")["locked"] is False
        state = guard.get_state()
        assert any(e["kind"] == "extreme_unlock" for e in state["log"])
    finally:
        tmp.cleanup()


def test_extreme_event_noop_when_unlocked():
    tmp, storage, modifier, guard = _setup()
    try:
        params = default_params()
        assert not params.locked
        ok = guard.on_extreme_event(params, "cold_72h")
        assert ok is False, "未锁定状态无需解锁"
    finally:
        tmp.cleanup()


# ── 4. 管理员 2h 临时锁定 ───────────────────────────────
def test_manual_lock_pauses_auto():
    tmp, storage, modifier, guard = _setup()
    try:
        params = default_params()
        guard.apply_manual_lock(params)
        assert guard.is_auto_paused(params), "管理员设置后 2h 内自动化应暂停"
        assert guard.manual_lock_remaining() > 0
    finally:
        tmp.cleanup()


def test_manual_lock_expires():
    tmp, storage, modifier, guard = _setup()
    try:
        params = default_params()
        guard.apply_manual_lock(params, duration_sec=0.01)
        import time
        time.sleep(0.05)
        assert not guard.is_auto_paused(params), "临时锁定过期后自动化恢复"
        assert guard.manual_lock_remaining() == 0
    finally:
        tmp.cleanup()


# ── 5. orchestrator 集成：锁定/暂停时跳过隐式训练 ───────
def test_orchestrator_skips_training_when_paused():
    from astrbot_plugin_soulsync.trainer.trainer_orchestrator import (
        PersonalizationOrchestrator,
    )
    tmp = tempfile.TemporaryDirectory()
    try:
        storage = TrainerStorage(Path(tmp.name))
        orch = PersonalizationOrchestrator("orch_guard", storage, {})
        params = orch.get_persona()
        modifier = orch._modifier
        calls = []
        orig = orch._trainer.check_feedback
        orch._trainer.check_feedback = lambda *a, **k: (calls.append(1), orig(*a, **k))[1]
        # 锁定 → is_auto_paused True → 隐式训练跳过（check_feedback 不执行）
        modifier.lock(params)
        orch.on_each_turn("你好呀", {})
        assert calls == [], "锁定期间不应执行隐式训练"
        # 极端事件解锁 → 恢复训练
        orch._guard.on_extreme_event(orch.get_persona(), "betrayal")
        orch.on_each_turn("今天心情不错", {})
        assert len(calls) == 1, "解锁后应恢复隐式训练"
        # 管理员临时锁定 → 暂停；过期后恢复
        orch._guard.apply_manual_lock(orch.get_persona(), duration_sec=0.01)
        orch.on_each_turn("锁定期再来一句", {})
        assert len(calls) == 1, "管理员临时锁定期间不应训练"
        import time
        time.sleep(0.05)
        orch.on_each_turn("过期后再说一句", {})
        assert len(calls) == 2, "临时锁定过期后应恢复训练"
    finally:
        tmp.cleanup()


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
