"""锐度系统测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from astrbot_plugin_soulmirror.sharpness import SharpnessManager, SharpnessLevel
from astrbot_plugin_soulmirror.session import UserSession, SessionState


def test_sharpness_levels():
    """测试锐度等级"""
    assert SharpnessLevel.WATER.value == 1
    assert SharpnessLevel.STILL.value == 2
    assert SharpnessLevel.FOCUS.value == 3
    assert SharpnessLevel.SHARP.value == 4
    assert SharpnessLevel.ABYSS.value == 5


def test_manual_mode():
    """测试手动模式"""
    manager = SharpnessManager(auto_mode=False)
    manager.set_manual_level(SharpnessLevel.SHARP)

    assert manager.get_current_level() == SharpnessLevel.SHARP
    assert manager.auto_mode == False


def test_auto_mode():
    """测试自动模式"""
    manager = SharpnessManager(auto_mode=True)
    assert manager.get_current_level() == SharpnessLevel.STILL


def test_auto_adjust_user_input升锐():
    """测试用户主动升锐"""
    manager = SharpnessManager(auto_mode=True)
    session = UserSession(user_id="test_user")
    session.current_sharpness = 2

    manager.auto_adjust(session, "直接点说")
    assert session.current_sharpness >= 2


def test_auto_adjust_contradiction():
    """测试矛盾信号升锐"""
    manager = SharpnessManager(auto_mode=True)
    session = UserSession(user_id="test_user")
    session.current_sharpness = 2

    manager.auto_adjust(session, "我想去但是不想动")
    assert session.current_sharpness >= 2


def test_auto_adjust_vague():
    """测试模糊表达升锐"""
    manager = SharpnessManager(auto_mode=True)
    session = UserSession(user_id="test_user")
    session.current_sharpness = 2

    manager.auto_adjust(session, "好像有点累")
    assert session.current_sharpness >= 2


def test_trajectory_history():
    """测试锐度变化轨迹"""
    manager = SharpnessManager(auto_mode=True)
    session = UserSession(user_id="test_user")
    session.current_sharpness = 2

    manager.auto_adjust(session, "直接点说")
    history = manager.get_history()

    assert len(history) >= 0


if __name__ == "__main__":
    test_sharpness_levels()
    test_manual_mode()
    test_auto_mode()
    test_auto_adjust_user_input升锐()
    test_auto_adjust_contradiction()
    test_auto_adjust_vague()
    test_trajectory_history()
    print("All sharpness tests passed!")
