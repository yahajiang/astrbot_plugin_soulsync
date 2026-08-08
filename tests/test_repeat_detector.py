"""重复词检测测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from astrbot_plugin_soulmirror.repeat_detector import RepeatDetector
from astrbot_plugin_soulmirror.session import UserSession, SessionState


def test_no_repeat():
    """测试无重复"""
    detector = RepeatDetector()
    session = UserSession(user_id="test_user")
    session.state = SessionState.MIRROR_MODE

    signal = detector.detect(session, "我今天很开心")
    assert signal is None


def test_repeat_detection():
    """测试重复检测"""
    detector = RepeatDetector()
    session = UserSession(user_id="test_user")
    session.state = SessionState.MIRROR_MODE

    # 模拟多轮输入同一词
    for _ in range(3):
        detector.detect(session, "累")

    signal = detector.detect(session, "还是累")
    assert signal is not None
    assert signal.word == "累"
    assert signal.count >= 3


def test_extract_content_words():
    """测试内容词提取"""
    detector = RepeatDetector()
    words = detector._extract_content_words("我今天好累啊")
    assert "今天" in words or "累" in words


def test_generate_response():
    """测试生成重复提示"""
    detector = RepeatDetector()
    response = detector._generate_response("累", 3)
    assert "累" in response
    assert "3" in response


def test_reset():
    """测试重置"""
    detector = RepeatDetector()
    session = UserSession(user_id="test_user")
    session.word_frequency["累"] = 5

    detector.reset(session)
    assert len(session.word_frequency) == 0


if __name__ == "__main__":
    test_no_repeat()
    test_repeat_detection()
    test_extract_content_words()
    test_generate_response()
    test_reset()
    print("All repeat_detector tests passed!")
