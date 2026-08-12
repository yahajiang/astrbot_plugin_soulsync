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
    _fallback_guide_reply,
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

    def test_empty_shows_list(self):
        """空参数显示图鉴列表"""
        getter, _ = _make_session_getter()
        msgs = handle_message("", "u1", getter)
        assert len(msgs) == 1
        assert "157" in msgs[0]

    def test_empty_exit_guide(self):
        """探索中空参数退出"""
        getter, sessions = _make_session_getter()
        s = sessions.setdefault("u1", UserSession(user_id="u1"))
        s.activate_guide("mbti_16")
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

    def test_guide_no_match(self):
        """未匹配"""
        getter, _ = _make_session_getter()
        msgs = handle_message("不存在的图鉴", "u1", getter)
        assert "未找到" in msgs[0]

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


class TestFallbackGuideReply:
    """图鉴降级反问测试"""

    def test_guide_fallback(self):
        guide = {"dims": ["E/I：能量来源", "S/N：信息获取"]}
        reply = _fallback_guide_reply(guide, 0)
        assert "？" in reply

    def test_no_dims(self):
        reply = _fallback_guide_reply({}, 0)
        assert "具体" in reply
