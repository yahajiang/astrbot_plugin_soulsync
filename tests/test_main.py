"""主入口测试 - 命令路由（纯函数，不依赖 AstrBot）"""

import sys
from unittest.mock import MagicMock

# 模拟 astrbot 模块（测试环境无 AstrBot）
astrbot_mock = MagicMock()
sys.modules["astrbot"] = astrbot_mock
sys.modules["astrbot.api"] = astrbot_mock.api
sys.modules["astrbot.api.event"] = astrbot_mock.api.event
sys.modules["astrbot.api.star"] = astrbot_mock.api.star
sys.modules["astrbot.core"] = astrbot_mock.core
sys.modules["astrbot.core.utils"] = astrbot_mock.core.utils
sys.modules["astrbot.core.utils.astrbot_path"] = astrbot_mock.core.utils.astrbot_path
astrbot_mock.api.AstrBotConfig = dict
astrbot_mock.api.logger = MagicMock()
astrbot_mock.api.event.filter = MagicMock()
astrbot_mock.api.event.AstrMessageEvent = MagicMock
astrbot_mock.api.star.Context = MagicMock
astrbot_mock.api.star.Star = MagicMock
astrbot_mock.core.utils.astrbot_path.get_astrbot_data_path = MagicMock(return_value="/tmp/test")

from astrbot_plugin_soulsync_mirror.session import UserSession, SessionMode
from astrbot_plugin_soulsync_mirror.main import (
    handle_message,
    _is_end_input,
    _fallback_general_reply,
    _fallback_guide_reply,
    _generate_general_summary,
)


def _make_session_getter():
    sessions = {}

    def getter(user_id):
        if user_id not in sessions:
            sessions[user_id] = UserSession(user_id=user_id)
        return sessions[user_id]

    return getter, sessions


class TestHandleMessage:
    """命令路由测试"""

    def test_empty_toggle_general(self):
        """空参数进入通用模式"""
        getter, _ = _make_session_getter()
        msgs = handle_message("", "u1", getter)
        assert len(msgs) == 1
        assert "启明镜已亮" in msgs[0]

    def test_empty_toggle_off(self):
        """已在通用模式时关闭"""
        getter, sessions = _make_session_getter()
        s = sessions.setdefault("u1", UserSession(user_id="u1"))
        s.activate_general()
        msgs = handle_message("", "u1", getter)
        assert "__EXIT__" in msgs[0]

    def test_guide_list(self):
        """列表命令"""
        getter, _ = _make_session_getter()
        msgs = handle_message("列表", "u1", getter)
        assert "157" in msgs[0]

    def test_guide_match(self):
        """图鉴匹配"""
        getter, sessions = _make_session_getter()
        msgs = handle_message("mbti", "u1", getter)
        assert "MBTI" in msgs[0]
        assert len(msgs) == 2
        assert sessions["u1"].mode == SessionMode.GUIDE
        assert sessions["u1"].guide_key == "mbti_16"

    def test_guide_match_case_insensitive(self):
        """大小写不敏感"""
        getter, _ = _make_session_getter()
        msgs = handle_message("MBTI", "u1", getter)
        assert "MBTI" in msgs[0]

    def test_guide_no_match_fallback(self):
        """未匹配降级通用"""
        getter, sessions = _make_session_getter()
        msgs = handle_message("不存在的图鉴", "u1", getter)
        assert "未找到" in msgs[0]
        assert sessions["u1"].mode == SessionMode.GENERAL

    def test_guide_no_match_no_fallback(self):
        """未匹配不降级"""
        getter, _ = _make_session_getter()
        msgs = handle_message("不存在", "u1", getter, fallback_to_general=False)
        assert "未找到" in msgs[0]
        assert len(msgs) == 1

    def test_guide_list_disabled(self):
        """列表功能禁用"""
        getter, _ = _make_session_getter()
        msgs = handle_message("列表", "u1", getter, enable_guide_list=False)
        assert "未启用" in msgs[0]


class TestIsEndInput:
    """结束检测测试"""

    def test_end_keywords(self):
        assert _is_end_input("结束", ["结束", "再见"])
        assert _is_end_input("拜拜", ["结束", "拜拜"])
        assert _is_end_input("今天就到这", ["今天就到这"])

    def test_not_end(self):
        assert not _is_end_input("继续聊聊", ["结束", "再见"])


class TestFallbackReplies:
    """降级反问测试"""

    def test_general_fallback(self):
        reply = _fallback_general_reply("我想聊聊人生")
        assert "？" in reply

    def test_guide_fallback(self):
        guide = {"dims": ["E/I：能量来源", "S/N：信息获取"]}
        reply = _fallback_guide_reply(guide, 0)
        assert "？" in reply


class TestGeneralSummary:
    """通用模式总结测试"""

    def test_empty_history(self):
        s = UserSession(user_id="u1")
        summary = _generate_general_summary(s)
        assert "镜子只是静静待了一会儿" in summary

    def test_with_history(self):
        s = UserSession(user_id="u1")
        s.add_turn("我好累", "反问")
        summary = _generate_general_summary(s)
        assert "镜子已收" in summary
