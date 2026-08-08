"""LLM 镜像反射测试"""

import pytest

from astrbot_plugin_soulmirror.llm_mirror import LLMMirror, MIRROR_SYSTEM_PROMPT


class TestLLMMirror:
    def test_init_no_context(self):
        """无 context 时反射直接返回 None"""
        mirror = LLMMirror()
        result = mirror._is_valid_mirror("你说你好累。", "我好累")
        assert result is True

    def test_valid_mirror(self):
        """合格的镜像回复应通过验证"""
        mirror = LLMMirror()
        assert mirror._is_valid_mirror("你说你好累。", "我好累")
        assert mirror._is_valid_mirror("你说你觉得自己很孤独。", "我觉得自己很孤独")
        assert mirror._is_valid_mirror("你说那聊什么。", "那聊什么")

    def test_reject_advice(self):
        """含建议的回复应被拒绝"""
        mirror = LLMMirror()
        assert not mirror._is_valid_mirror("我建议你好好休息一下。", "我好累")
        assert not mirror._is_valid_mirror("你应该多出去走走。", "我好累")

    def test_reject_empathy(self):
        """含共情的回复应被拒绝"""
        mirror = LLMMirror()
        assert not mirror._is_valid_mirror("我理解你的感受。", "我好累")
        assert not mirror._is_valid_mirror("我感受到你的难过。", "我很难过")

    def test_reject_analysis(self):
        """含分析的回复应被拒绝"""
        mirror = LLMMirror()
        assert not mirror._is_valid_mirror("这是因为你太累了。", "我好累")

    def test_reject_too_long(self):
        """过长的回复应被拒绝"""
        mirror = LLMMirror()
        long_response = "你说你好累。" + "补充一些额外的内容。" * 10
        assert not mirror._is_valid_mirror(long_response, "我好累")

    def test_system_prompt_contains_rules(self):
        """System prompt 应包含镜像规则"""
        assert "只反射" in MIRROR_SYSTEM_PROMPT
        assert "不建议" in MIRROR_SYSTEM_PROMPT
        assert "不共情" in MIRROR_SYSTEM_PROMPT
        assert "不分析" in MIRROR_SYSTEM_PROMPT
