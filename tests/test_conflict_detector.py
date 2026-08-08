"""矛盾检测测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from astrbot_plugin_soulmirror.conflict_detector import ConflictDetector, ConflictType
from astrbot_plugin_soulmirror.session import UserSession, SessionState


def test_will_conflict():
    """测试意愿矛盾"""
    detector = ConflictDetector()
    session = UserSession(user_id="test_user")
    session.state = SessionState.MIRROR_MODE

    conflict = detector.detect(session, "我想去但是不想动")
    assert conflict is not None
    assert conflict.type == ConflictType.WILL


def test_emotion_conflict():
    """测试情感矛盾"""
    detector = ConflictDetector()
    session = UserSession(user_id="test_user")
    session.state = SessionState.MIRROR_MODE

    conflict = detector.detect(session, "我爱他但我恨他")
    assert conflict is not None
    assert conflict.type == ConflictType.EMOTION


def test_self_conflict():
    """测试自我矛盾"""
    detector = ConflictDetector()
    session = UserSession(user_id="test_user")
    session.state = SessionState.MIRROR_MODE

    conflict = detector.detect(session, "我不是在意我只是随便问问")
    assert conflict is not None
    assert conflict.type == ConflictType.SELF


def test_temporal_conflict():
    """测试时序矛盾"""
    detector = ConflictDetector()
    session = UserSession(user_id="test_user")
    session.state = SessionState.MIRROR_MODE

    conflict = detector.detect(session, "我之前觉得还行现在又觉得不行")
    assert conflict is not None
    assert conflict.type == ConflictType.TEMPORAL


def test_no_conflict():
    """测试无矛盾"""
    detector = ConflictDetector()
    session = UserSession(user_id="test_user")
    session.state = SessionState.MIRROR_MODE

    conflict = detector.detect(session, "我今天很开心")
    assert conflict is None


def test_conflict_response():
    """测试矛盾应答"""
    detector = ConflictDetector()
    from conflict_detector import Conflict
    import time

    conflict = Conflict(
        type=ConflictType.WILL,
        content="我想去但是不想动",
        timestamp=time.time(),
    )
    response = detector.get_conflict_response(conflict)
    assert "顾虑" in response or "想" in response


if __name__ == "__main__":
    test_will_conflict()
    test_emotion_conflict()
    test_self_conflict()
    test_temporal_conflict()
    test_no_conflict()
    test_conflict_response()
    print("All conflict_detector tests passed!")
