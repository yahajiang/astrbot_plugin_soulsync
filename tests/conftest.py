# 目录名含中文后缀，注册无后缀模块别名以便测试导入
import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

_MOD_NAME = "astrbot_plugin_soulsync_mirror"
_PLUGIN_DIR = Path(__file__).resolve().parent.parent

if _MOD_NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        _MOD_NAME,
        _PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(_PLUGIN_DIR)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MOD_NAME] = module
    spec.loader.exec_module(module)


def make_mock_context():
    """创建 AstrBot context mock"""
    ctx = MagicMock()
    ctx.get_current_chat_provider_id = AsyncMock(return_value="test_provider")
    ctx.llm_generate = AsyncMock(return_value=MagicMock(completion_text="mock reply"))
    return ctx


def make_mock_event(message_str: str, sender_id: str = "test_user"):
    """创建 AstrMessageEvent mock"""
    event = MagicMock()
    event.message_str = message_str
    event.get_sender_id.return_value = sender_id
    event.unified_msg_origin = f"test_{sender_id}"
    event.plain_result = MagicMock(side_effect=lambda x: x)
    event.send = AsyncMock()
    event.stop_event = MagicMock()
    return event
