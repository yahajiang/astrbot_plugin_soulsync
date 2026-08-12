"""后处理器测试"""

from astrbot_plugin_soulsync_mirror.postprocessor import (
    ensure_question_mark,
    truncate,
    replace_suggestions,
    process,
)
from astrbot_plugin_soulsync_mirror.safety import SafetyManager


class TestEnsureQuestionMark:
    """补问号测试"""

    def test_already_has_question_mark(self):
        assert ensure_question_mark("你好？") == "你好？"

    def test_no_question_mark(self):
        result = ensure_question_mark("你好")
        assert result.endswith("？")

    def test_ends_with_period(self):
        result = ensure_question_mark("你好。")
        assert result.endswith("？")
        assert "你好？" == result

    def test_empty_string(self):
        assert ensure_question_mark("") == ""


class TestTruncate:
    """截断测试"""

    def test_short_reply(self):
        assert truncate("短回复", "很长的用户输入" * 10) == "短回复"

    def test_long_reply_truncated(self):
        user_input = "短"
        reply = "很长的回复" * 20
        result = truncate(reply, user_input, max_ratio=1.5)
        assert len(result) <= int(len(user_input) * 1.5) + 10  # 允许标点

    def test_truncate_at_sentence(self):
        reply = "第一句。第二句。第三句。"
        user_input = "短回复"
        result = truncate(reply, user_input, max_ratio=1.5)
        assert len(result) <= int(len(user_input) * 1.5) + 10
        assert result.endswith("。") or result.endswith("？")


class TestReplaceSuggestions:
    """建议替换测试"""

    def test_replace_you_should(self):
        result = replace_suggestions("你应该试试")
        assert "应该" not in result
        assert "有没有想过" in result

    def test_no_suggestion(self):
        assert replace_suggestions("没问题") == "没问题"


class TestProcess:
    """后处理管道测试"""

    def setup_method(self):
        self.manager = SafetyManager()

    def test_crisis_bypasses(self):
        """危机输入直接返回安全话术"""
        result = process("回复", "自杀", self.manager)
        assert "400-161-9995" in result

    def test_normal_reply(self):
        """正常回复经过后处理"""
        result = process("回复", "用户输入", self.manager)
        assert result.endswith("？")

    def test_long_reply_truncated(self):
        """长回复被截断"""
        user_input = "短"
        reply = "很长的回复" * 50
        result = process(reply, user_input, self.manager, max_output_ratio=1.5)
        assert len(result) <= int(len(user_input) * 1.5) + 20
