"""安全红线测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from astrbot_plugin_soulmirror.safety import SafetyManager, CrisisLevel


def test_no_crisis():
    """测试无危机信号"""
    manager = SafetyManager()
    signal = manager.check_crisis("我今天很开心")
    assert signal is None


def test_medium_crisis():
    """测试中等危机信号"""
    manager = SafetyManager()
    signal = manager.check_crisis("想死")
    assert signal is not None
    assert signal.level == CrisisLevel.MEDIUM


def test_high_crisis():
    """测试高危机信号"""
    manager = SafetyManager()
    signal = manager.check_crisis("活不下去了")
    assert signal is not None
    assert signal.level == CrisisLevel.HIGH


def test_critical_crisis():
    """测试严重危机信号"""
    manager = SafetyManager()
    signal = manager.check_crisis("我要自杀")
    assert signal is not None
    assert signal.level == CrisisLevel.CRITICAL


def test_crisis_response():
    """测试危机应答"""
    manager = SafetyManager()
    signal = manager.check_crisis("我不想活了")
    response = manager.get_crisis_response(signal)
    assert "400-161-9995" in response


def test_should_interrupt():
    """测试是否中断会话"""
    manager = SafetyManager()
    signal = manager.check_crisis("我要自杀")
    assert manager.should_interrupt_session(signal) == True

    signal = manager.check_crisis("想死")
    assert manager.should_interrupt_session(signal) == False


if __name__ == "__main__":
    test_no_crisis()
    test_medium_crisis()
    test_high_crisis()
    test_critical_crisis()
    test_crisis_response()
    test_should_interrupt()
    print("All safety tests passed!")
