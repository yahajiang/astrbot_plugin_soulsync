"""命令路由测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from astrbot_plugin_soulmirror.commands import CommandRouter


def test_parse_empty():
    """测试空命令"""
    router = CommandRouter()
    action, args = router.parse("")
    assert action == "toggle"
    assert args == ""


def test_parse_toggle():
    """测试toggle命令"""
    router = CommandRouter()
    action, args = router.parse("退出")
    assert action == "toggle"


def test_parse_reset():
    """测试reset命令"""
    router = CommandRouter()
    action, args = router.parse("重置")
    assert action == "reset"


def test_parse_remember():
    """测试remember命令"""
    router = CommandRouter()
    action, args = router.parse("记住")
    assert action == "remember"


def test_parse_forget():
    """测试forget命令"""
    router = CommandRouter()
    action, args = router.parse("忘记 关键词")
    assert action == "forget"
    assert args == "关键词"


def test_parse_status():
    """测试status命令"""
    router = CommandRouter()
    action, args = router.parse("状态")
    assert action == "status"


def test_parse_depth():
    """测试depth命令"""
    router = CommandRouter()
    action, args = router.parse("深度 3")
    assert action == "depth"
    assert args == "3"


def test_parse_silent():
    """测试silent命令"""
    router = CommandRouter()
    action, args = router.parse("静默")
    assert action == "silent"


def test_parse_export():
    """测试export命令"""
    router = CommandRouter()
    action, args = router.parse("导出")
    assert action == "export"


def test_parse_help():
    """测试help命令"""
    router = CommandRouter()
    action, args = router.parse("帮助")
    assert action == "help"


def test_get_help():
    """测试获取帮助"""
    router = CommandRouter()
    help_text = router.get_help()
    assert "/心镜" in help_text
    assert "深度" in help_text


if __name__ == "__main__":
    test_parse_empty()
    test_parse_toggle()
    test_parse_reset()
    test_parse_remember()
    test_parse_forget()
    test_parse_status()
    test_parse_depth()
    test_parse_silent()
    test_parse_export()
    test_parse_help()
    test_get_help()
    print("All commands tests passed!")
