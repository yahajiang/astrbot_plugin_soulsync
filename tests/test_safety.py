"""安全红线测试"""

from astrbot_plugin_soulsync_mirror.safety import (
    SafetyManager,
    CrisisLevel,
)


class TestSafetyManager:
    """安全检测测试"""

    def setup_method(self):
        self.manager = SafetyManager()

    def test_critical_keywords(self):
        """CRITICAL 关键词触发"""
        for kw in ["自杀", "不想活了", "活着没意思", "死了算了", "跳楼", "割腕"]:
            signal = self.manager.check_crisis(kw)
            assert signal is not None, f"'{kw}' 未触发危机"
            assert signal.level == CrisisLevel.CRITICAL

    def test_high_keywords(self):
        """HIGH 关键词触发"""
        for kw in ["自残", "活不下去", "撑不下去", "崩溃了"]:
            signal = self.manager.check_crisis(kw)
            assert signal is not None, f"'{kw}' 未触发危机"
            assert signal.level in (CrisisLevel.CRITICAL, CrisisLevel.HIGH)

    def test_medium_keywords(self):
        """MEDIUM 关键词触发"""
        for kw in ["想死", "想离开", "想消失", "太累了"]:
            signal = self.manager.check_crisis(kw)
            assert signal is not None, f"'{kw}' 未触发危机"

    def test_no_trigger(self):
        """正常输入不触发"""
        assert self.manager.check_crisis("今天天气不错") is None
        assert self.manager.check_crisis("我好开心") is None
        assert self.manager.check_crisis("") is None

    def test_crisis_response(self):
        """危机话术包含热线"""
        signal = self.manager.check_crisis("自杀")
        response = self.manager.get_crisis_response(signal)
        assert "400-161-9995" in response
        assert "希望24热线" in response

    def test_should_interrupt(self):
        """CRITICAL/HIGH 中断会话"""
        critical = self.manager.check_crisis("自杀")
        assert self.manager.should_interrupt_session(critical)

        high = self.manager.check_crisis("崩溃了")
        assert self.manager.should_interrupt_session(high)

        medium = self.manager.check_crisis("想死")
        assert not self.manager.should_interrupt_session(medium)
