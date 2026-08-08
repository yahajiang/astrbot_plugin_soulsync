"""金句引用测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from astrbot_plugin_soulmirror.quote import QuoteManager, Quote
from astrbot_plugin_soulmirror.session import UserSession, SessionState, DialogueEntry


def test_quote_creation():
    """测试金句创建"""
    quote = Quote(
        content="我今天真的很累",
        timestamp=1234567890.0,
        source="user",
    )
    assert quote.content == "我今天真的很累"
    assert quote.source == "user"


def test_high_density_detection():
    """测试高密度表达检测"""
    manager = QuoteManager()
    assert manager._is_high_density("我今天真的很累，身心俱疲") == True
    assert manager._is_high_density("哈哈") == False


def test_save_session():
    """测试保存会话"""
    manager = QuoteManager()
    session = UserSession(user_id="test_user")
    session.dialogue_history.append(DialogueEntry(
        user_input="我今天真的很累，身心俱疲",
        mirror_response="你说你很累。",
        timestamp=1234567890.0,
        sharpness_level=2,
        reflection_type="repetition",
        mirror_type="plane",
    ))

    manager.save_session("test_user", session)
    quotes = manager.get_quotes("test_user")
    assert len(quotes) == 1
    assert "累" in quotes[0].content


def test_remove_quote():
    """测试移除金句"""
    manager = QuoteManager()
    manager.quotes["test_user"] = [
        Quote(content="我今天很开心", timestamp=1234567890.0, source="user"),
        Quote(content="我今天很累", timestamp=1234567891.0, source="user"),
    ]

    manager.remove_quote("test_user", "开心")
    quotes = manager.get_quotes("test_user")
    assert len(quotes) == 1
    assert "累" in quotes[0].content


def test_clear_all():
    """测试清空金句"""
    manager = QuoteManager()
    manager.quotes["test_user"] = [
        Quote(content="test", timestamp=1234567890.0, source="user"),
    ]

    manager.clear_all("test_user")
    quotes = manager.get_quotes("test_user")
    assert len(quotes) == 0


def test_related_detection():
    """测试相关性检测"""
    manager = QuoteManager()
    assert manager._is_related("我今天真的很累", "今天好累啊") == True
    assert manager._is_related("我今天很开心", "今天天气不错") == False


if __name__ == "__main__":
    test_quote_creation()
    test_high_density_detection()
    test_save_session()
    test_remove_quote()
    test_clear_all()
    test_related_detection()
    print("All quote tests passed!")
