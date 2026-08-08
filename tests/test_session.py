"""会话状态管理测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from astrbot_plugin_soulmirror.session import UserSession, SessionState, DialogueEntry


def test_session_creation():
    """测试会话创建"""
    session = UserSession(user_id="test_user")
    assert session.user_id == "test_user"
    assert session.state == SessionState.IDLE
    assert session.nickname == ""
    assert session.current_round == 0


def test_session_reset():
    """测试会话重置"""
    session = UserSession(user_id="test_user")
    session.nickname = "小明"
    session.current_round = 5
    session.reset()

    assert session.state == SessionState.DECLARATION
    assert session.nickname == ""
    assert session.current_round == 0


def test_add_dialogue():
    """测试添加对话"""
    session = UserSession(user_id="test_user")
    entry = DialogueEntry(
        user_input="我好累",
        mirror_response="你说你好累。",
        timestamp=1234567890.0,
        sharpness_level=2,
        reflection_type="repetition",
        mirror_type="plane",
    )
    session.add_dialogue(entry)

    assert session.current_round == 1
    assert len(session.dialogue_history) == 1
    assert session.dialogue_history[0].user_input == "我好累"


def test_word_frequency():
    """测试词频统计"""
    session = UserSession(user_id="test_user")
    session.update_word_frequency(["累", "烦", "累"])

    assert session.word_frequency["累"] == 2
    assert session.word_frequency["烦"] == 1


def test_to_dict():
    """测试序列化"""
    session = UserSession(user_id="test_user")
    session.nickname = "小明"
    data = session.to_dict()

    assert data["user_id"] == "test_user"
    assert data["nickname"] == "小明"


def test_load_from_dict():
    """测试反序列化"""
    data = {
        "user_id": "test_user",
        "state": "idle",
        "nickname": "小明",
        "current_round": 5,
    }
    session = UserSession(user_id="test_user")
    session.load_from_dict(data)

    assert session.nickname == "小明"
    assert session.current_round == 5


if __name__ == "__main__":
    test_session_creation()
    test_session_reset()
    test_add_dialogue()
    test_word_frequency()
    test_to_dict()
    test_load_from_dict()
    print("All session tests passed!")
