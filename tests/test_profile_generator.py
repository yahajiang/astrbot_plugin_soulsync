"""轮廓卡生成器测试"""

from astrbot_plugin_soulsync_mirror.profile_generator import (
    validate_profile,
    render_profile,
    generate_fallback_profile,
    PROFILE_HEADER,
    PROFILE_FOOTER,
)


class TestValidateProfile:
    """轮廓卡校验测试"""

    def test_valid_profile(self):
        """合格轮廓卡"""
        content = (
            "● 能量流向\n"
            "  你提到\"独处比聚会更让你恢复\"。\n"
            "  世界很吵，你在安静里充电。\n"
            "  → 偏 I\n\n"
            "✦ 这些信号拼在一起，隐约指向：INFP\n"
            "  但镜子照出的只是影子。\n\n"
            "✦ 你觉得呢？"
        )
        result = validate_profile(content)
        assert result["valid"]

    def test_forbidden_pattern(self):
        """禁止词检测"""
        content = (
            "● 测试\n"
            "  你是INFP型\n"
            "  → 偏 I\n"
            "✦ 这些信号拼在一起，隐约指向：INFP\n"
            "  但镜子照出的只是影子。\n\n"
            "✦ 你觉得呢？"
        )
        result = validate_profile(content)
        assert not result["valid"]

    def test_missing_dimension(self):
        """缺少维度标记"""
        content = "一些文字没有维度标记"
        result = validate_profile(content)
        assert not result["valid"]

    def test_render_profile(self):
        """渲染加线框"""
        content = "● 测试\n→ 偏 X"
        rendered = render_profile(content)
        assert PROFILE_HEADER in rendered
        assert PROFILE_FOOTER in rendered
        assert "● 测试" in rendered


class TestFallbackProfile:
    """降级轮廓卡测试"""

    def test_with_signals(self):
        """有信号时生成降级卡"""
        signals = {"E/I": "偏 I", "S/N": "偏 N"}
        history = [("独处更自在", "反问")]
        result = generate_fallback_profile(signals, history, "INFP")
        assert "隐约指向" in result
        assert "偏 I" in result
        assert "偏 N" in result

    def test_without_signals(self):
        """无信号时生成通用卡"""
        result = generate_fallback_profile({}, [], "待辨认")
        assert "隐约指向" in result
        assert "待辨认" in result
