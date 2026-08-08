"""修正机制测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from astrbot_plugin_soulmirror.correction import CorrectionManager, CorrectionType, CorrectionStrength, Correction
from astrbot_plugin_soulmirror.session import UserSession, SessionState, DialogueEntry


def test_nickname_correction():
    """测试称呼修正"""
    manager = CorrectionManager()
    session = UserSession(user_id="test_user")
    session.nickname = "你"

    correction = manager.detect(session, "叫我小明")
    assert correction is not None
    assert correction.type == CorrectionType.NICKNAME
    assert correction.new_value == "小明"


def test_content_correction_strong():
    """测试内容修正（强）"""
    manager = CorrectionManager()
    session = UserSession(user_id="test_user")
    session.state = SessionState.MIRROR_MODE
    entry = session.dialogue_history
    entry.append(DialogueEntry(
        user_input="我好累",
        mirror_response="你说你好累。",
        timestamp=1234567890.0,
        sharpness_level=2,
        reflection_type="repetition",
        mirror_type="plane",
    ))

    correction = manager.detect(session, "不是累，是烦")
    assert correction is not None
    assert correction.type == CorrectionType.CONTENT
    assert correction.strength == CorrectionStrength.STRONG


def test_content_correction_weak():
    """测试内容修正（弱）"""
    manager = CorrectionManager()
    session = UserSession(user_id="test_user")
    session.state = SessionState.MIRROR_MODE
    session.dialogue_history.append(DialogueEntry(
        user_input="我好累",
        mirror_response="你说你好累。",
        timestamp=1234567890.0,
        sharpness_level=2,
        reflection_type="repetition",
        mirror_type="plane",
    ))

    correction = manager.detect(session, "其实也不是累")
    assert correction is not None
    assert correction.type == CorrectionType.CONTENT


def test_no_correction():
    """测试无修正"""
    manager = CorrectionManager()
    session = UserSession(user_id="test_user")

    correction = manager.detect(session, "我今天很开心")
    assert correction is None


def test_get_annotation():
    """测试标注生成"""
    manager = CorrectionManager()
    session = UserSession(user_id="test_user")
    import time

    correction = Correction(
        type=CorrectionType.CONTENT,
        strength=CorrectionStrength.STRONG,
        old_value="累",
        new_value="烦",
        timestamp=time.time(),
    )

    annotation = manager.get_annotation(session, correction)
    assert annotation is not None
    assert "烦" in annotation or "累" in annotation


if __name__ == "__main__":
    test_nickname_correction()
    test_content_correction_strong()
    test_content_correction_weak()
    test_no_correction()
    test_get_annotation()
    print("All correction tests passed!")
