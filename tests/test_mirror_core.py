"""镜像核心测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from astrbot_plugin_soulmirror.mirror_core import MirrorCore, ReflectionType, MirrorType
from astrbot_plugin_soulmirror.session import UserSession, SessionState
from astrbot_plugin_soulmirror.sharpness import SharpnessLevel


def test_reflection_repetition():
    """测试复述式反射"""
    core = MirrorCore()
    session = UserSession(user_id="test_user")
    session.state = SessionState.MIRROR_MODE

    response = core.reflect("我好累", session, SharpnessLevel.STILL)
    assert "你说" in response or "累" in response


def test_reflection_attribution():
    """测试归因式反射"""
    core = MirrorCore()
    session = UserSession(user_id="test_user")
    session.state = SessionState.MIRROR_MODE

    response = core.reflect("我好累", session, SharpnessLevel.FOCUS)
    assert "身体" in response or "心里" in response or "累" in response


def test_extract_content_words():
    """测试内容词提取"""
    core = MirrorCore()
    words = core.extract_content_words("我今天好累啊")
    assert "今天" in words or "累" in words


def test_minimal_reflection():
    """测试极简反射"""
    core = MirrorCore()
    response = core._reflect_minimal("嗯")
    assert "嗯" in response


def test_contradiction_detection():
    """测试矛盾检测"""
    core = MirrorCore()
    assert core._has_contradiction("我想去但是不想动") == True
    assert core._has_contradiction("我今天很开心") == False


def test_emotion_extraction():
    """测试情绪提取"""
    core = MirrorCore()
    assert core._extract_emotion("我好累") == "fatigue"
    assert core._extract_emotion("我好烦") == "annoyance"
    assert core._extract_emotion("今天天气不错") is None


if __name__ == "__main__":
    test_reflection_repetition()
    test_reflection_attribution()
    test_extract_content_words()
    test_minimal_reflection()
    test_contradiction_detection()
    test_emotion_extraction()
    print("All mirror_core tests passed!")
