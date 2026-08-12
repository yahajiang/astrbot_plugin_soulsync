"""会话管理测试"""

from astrbot_plugin_soulsync_mirror.session import UserSession, SessionMode


class TestUserSession:
    """会话状态测试"""

    def test_default_state(self):
        """默认状态为 OFF"""
        s = UserSession(user_id="u1")
        assert s.mode == SessionMode.OFF
        assert s.history == []
        assert s.guide_key is None
        assert s.guide_round == 0

    def test_activate_guide(self):
        """激活图鉴模式"""
        s = UserSession(user_id="u1")
        s.activate_guide("mbti_16")
        assert s.mode == SessionMode.GUIDE
        assert s.guide_key == "mbti_16"

    def test_add_turn(self):
        """添加对话轮次"""
        s = UserSession(user_id="u1")
        s.add_turn("hello", "hi")
        assert len(s.history) == 1
        assert s.history[0] == ("hello", "hi")

    def test_history_limit(self):
        """历史轮次限制"""
        s = UserSession(user_id="u1")
        for i in range(10):
            s.add_turn(f"q{i}", f"a{i}", max_rounds=6)
        assert len(s.history) == 6
        assert s.history[0] == ("q4", "a4")

    def test_add_signal(self):
        """添加维度信号"""
        s = UserSession(user_id="u1")
        s.add_signal("E/I", "偏 I")
        assert s.signals["E/I"] == "偏 I"

    def test_get_full_history_text(self):
        """获取完整对话记录"""
        s = UserSession(user_id="u1")
        s.add_turn("q1", "a1")
        s.add_turn("q2", "a2")
        text = s.get_full_history_text()
        assert "q1" in text
        assert "q2" in text

    def test_get_signals_text(self):
        """获取信号文本"""
        s = UserSession(user_id="u1")
        assert s.get_signals_text() == "暂无"
        s.add_signal("E/I", "偏 I")
        assert "E/I" in s.get_signals_text()

    def test_reset(self):
        """重置清空所有状态"""
        s = UserSession(user_id="u1")
        s.activate_guide("mbti_16")
        s.add_turn("q", "a")
        s.add_signal("dim", "sig")
        s.reset()
        assert s.mode == SessionMode.OFF
        assert s.history == []
        assert s.guide_key is None
        assert s.signals == {}

    def test_to_dict_and_load(self):
        """序列化与反序列化"""
        s = UserSession(user_id="u1")
        s.activate_guide("mbti_16")
        s.add_turn("q", "a")
        d = s.to_dict()

        s2 = UserSession(user_id="u1")
        s2.load_from_dict(d)
        assert s2.mode == SessionMode.GUIDE
        assert len(s2.history) == 1
