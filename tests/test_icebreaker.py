"""破冰握手测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from astrbot_plugin_soulmirror.icebreaker import IcebreakerManager, FIXED_QUESTIONS, WARM_QUESTIONS, COLD_QUESTIONS
from astrbot_plugin_soulmirror.session import UserSession, SessionState


def test_fixed_questions():
    """测试固定三问"""
    assert len(FIXED_QUESTIONS) == 3
    assert "名字" in FIXED_QUESTIONS[0]


def test_warm_questions():
    """测试暖区问题"""
    assert len(WARM_QUESTIONS) >= 8


def test_cold_questions():
    """测试冷区问题"""
    assert len(COLD_QUESTIONS) >= 8


def test_process_nickname():
    """测试称呼处理"""
    manager = IcebreakerManager()
    session = UserSession(user_id="test_user")
    session.icebreaker_stage = 0

    response = manager.process_response(session, "小明")
    assert "小明" in response
    assert session.nickname == "小明"


def test_process_skip():
    """测试跳过"""
    manager = IcebreakerManager()
    session = UserSession(user_id="test_user")
    session.icebreaker_stage = 0

    response = manager.process_response(session, "跳过")
    assert "直接开始" in response
    assert session.nickname == "你"


def test_get_next_question():
    """测试获取下一个问题"""
    manager = IcebreakerManager()
    session = UserSession(user_id="test_user")
    session.icebreaker_stage = 0

    question = manager.get_next_question(session)
    assert question is not None
    assert "名字" in question


def test_is_complete():
    """测试破冰完成检查"""
    manager = IcebreakerManager()
    session = UserSession(user_id="test_user")
    session.icebreaker_stage = 6

    assert manager.is_complete(session) == True


def test_random_questions():
    """测试随机问题选择"""
    manager = IcebreakerManager()
    questions = manager._select_random_questions()
    assert len(questions) == 3


if __name__ == "__main__":
    test_fixed_questions()
    test_warm_questions()
    test_cold_questions()
    test_process_nickname()
    test_process_skip()
    test_get_next_question()
    test_is_complete()
    test_random_questions()
    print("All icebreaker tests passed!")
