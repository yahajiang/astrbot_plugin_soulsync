"""astrbot_plugin_menu_image 冒烟测试

不依赖真实 AstrBot：通过 sys.modules 注入桩模块，再导入插件 main.py。
验证：
1. 指令枚举、按插件分组、内置指令归类
2. 同名指令去重（缺描述时补充）
3. exclude_plugins / show_builtin / hide_self 过滤
4. 分页逻辑（组尽量保持完整）
5. Pillow 渲染出图（PNG 尺寸、可打开）
6. 纯文本降级输出
"""

import sys
import tempfile
import types
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(PLUGIN_DIR.parent) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR.parent))


class _CmdFilter:
    """模拟 AstrBot 的 CommandFilter"""

    def __init__(self, command_name, alias=None, parent_command_names=None):
        self.command_name = command_name
        self.alias = alias or set()
        self.parent_command_names = parent_command_names or [""]

    def get_complete_command_names(self):
        names = [self.command_name, *self.alias]
        return [
            f"{parent} {n}".strip()
            for n in names
            for parent in self.parent_command_names or [""]
        ]


class _Handler:
    def __init__(self, module, name, filters, desc="", enabled=True):
        self.event_type = "adapter"
        self.handler_module_path = module
        self.handler_name = name
        self.desc = desc
        self.enabled = enabled
        self.event_filters = filters


class _StarMeta:
    def __init__(self, name=None, display_name=None, reserved=False):
        self.name = name
        self.display_name = display_name
        self.reserved = reserved


class _Registry:
    def __init__(self):
        self.handlers = []

    def __iter__(self):
        return iter(self.handlers)


def _make_logger():
    def noop(*a, **k):
        pass

    return types.SimpleNamespace(info=noop, warning=noop, error=noop, debug=noop)


def install_stubs(data_dir: Path):
    """注入 AstrBot 桩模块，返回 (registry, star_map)"""
    sys.modules.pop("astrbot_plugin_menu_image", None)
    sys.modules.pop("astrbot_plugin_menu_image.main", None)
    sys.modules.pop("astrbot_plugin_menu_image.renderer", None)
    sys.modules.pop("astrbot", None)
    sys.modules.pop("astrbot.api", None)
    sys.modules.pop("astrbot.api.event", None)
    sys.modules.pop("astrbot.api.star", None)
    sys.modules.pop("astrbot.core", None)
    sys.modules.pop("astrbot.core.utils", None)
    sys.modules.pop("astrbot.core.utils.astrbot_path", None)
    sys.modules.pop("astrbot.core.star", None)
    sys.modules.pop("astrbot.core.star.star_handler", None)
    sys.modules.pop("astrbot.core.star.filter", None)
    sys.modules.pop("astrbot.core.star.filter.command", None)
    sys.modules.pop("astrbot.core.star.star", None)

    base = types.ModuleType("astrbot")
    sys.modules["astrbot"] = base

    api = types.ModuleType("astrbot.api")
    api.logger = _make_logger()
    sys.modules["astrbot.api"] = api

    event_mod = types.ModuleType("astrbot.api.event")
    event_mod.AstrMessageEvent = type("AstrMessageEvent", (), {})
    event_mod.filter = types.SimpleNamespace(
        command=lambda name, alias=None, **kw: (lambda fn: fn)
    )
    sys.modules["astrbot.api.event"] = event_mod

    star_api = types.ModuleType("astrbot.api.star")
    star_api.Context = type("Context", (), {})
    star_api.Star = type(
        "Star", (), {"__init__": lambda self, context: None}
    )
    star_api.register = lambda *a, **k: (lambda fn: fn)
    sys.modules["astrbot.api.star"] = star_api

    core = types.ModuleType("astrbot.core")
    sys.modules["astrbot.core"] = core

    utils = types.ModuleType("astrbot.core.utils")
    sys.modules["astrbot.core.utils"] = utils

    path_mod = types.ModuleType("astrbot.core.utils.astrbot_path")
    path_mod.get_astrbot_data_path = lambda: str(data_dir)
    sys.modules["astrbot.core.utils.astrbot_path"] = path_mod

    star_pkg = types.ModuleType("astrbot.core.star")
    sys.modules["astrbot.core.star"] = star_pkg

    registry = _Registry()
    handler_mod = types.ModuleType("astrbot.core.star.star_handler")
    handler_mod.EventType = types.SimpleNamespace(AdapterMessageEvent="adapter")
    handler_mod.star_handlers_registry = registry
    sys.modules["astrbot.core.star.star_handler"] = handler_mod

    filt = types.ModuleType("astrbot.core.star.filter")
    sys.modules["astrbot.core.star.filter"] = filt

    cmd_mod = types.ModuleType("astrbot.core.star.filter.command")
    cmd_mod.CommandFilter = _CmdFilter
    sys.modules["astrbot.core.star.filter.command"] = cmd_mod

    star_mod = types.ModuleType("astrbot.core.star.star")
    star_map = {}
    star_mod.star_map = star_map
    sys.modules["astrbot.core.star.star"] = star_mod

    return registry, star_map


def _populate(registry, star_map):
    """构造一份典型的指令集合"""
    star_map["astrbot_plugin_furry_zan.main"] = _StarMeta(
        name="astrbot_plugin_furry_zan", display_name="爱点赞"
    )
    star_map["astrbot_plugin_group_checkin.main"] = _StarMeta(
        name="astrbot_plugin_group_checkin", display_name="群签到"
    )
    star_map["astrbot_plugin_imgtool_cooldown.main"] = _StarMeta(
        name="astrbot_plugin_imgtool_cooldown", display_name="生图工具"
    )

    registry.handlers = [
        _Handler(
            "astrbot_plugin_furry_zan.main",
            "zan",
            [_CmdFilter("zan", alias={"点赞"})],
            desc="给朋友点赞 🎉",
        ),
        _Handler(
            "astrbot_plugin_furry_zan.main",
            "zanme",
            [_CmdFilter("赞我")],
            desc="让机器人赞我",
        ),
        _Handler(
            "astrbot.core.something",
            "help",
            [_CmdFilter("help")],
            desc="查看指令帮助",
        ),
        _Handler(
            "astrbot_plugin_group_checkin.main",
            "checkin",
            [_CmdFilter("checkin")],
            desc="",
        ),
        # 同名指令去重：imgtool_cooldown 先注册且有描述，imgtool 后注册无描述
        _Handler(
            "astrbot_plugin_imgtool_cooldown.main",
            "img",
            [_CmdFilter("img")],
            desc="生图指令",
        ),
        _Handler(
            "astrbot_plugin_imgtool.main",
            "img",
            [_CmdFilter("img")],
            desc="",
        ),
        # 本插件自身指令（默认应被隐藏）
        _Handler(
            "astrbot_plugin_menu_image.main",
            "menu",
            [_CmdFilter("menu", alias={"菜单"})],
            desc="查看功能菜单图片",
        ),
    ]


def _install_and_import(data_dir):
    registry, star_map = install_stubs(data_dir)
    from astrbot_plugin_menu_image.main import MenuImagePlugin

    return registry, star_map, MenuImagePlugin


def test_collect_and_group():
    with tempfile.TemporaryDirectory() as td:
        registry, star_map, cls = _install_and_import(Path(td))
        _populate(registry, star_map)
        plugin = cls(None, {"exclude_plugins": []})

        groups = plugin._collect_groups()
        names = [g["name"] for g in groups]
        assert names[0] == "AstrBot 内置指令", f"内置指令组应排最前: {names}"
        assert "爱点赞" in names and "群签到" in names and "生图工具" in names
        assert not any(n == "astrbot_plugin_menu_image" for n in names), (
            "默认应隐藏本插件自身"
        )

        by_name = {g["name"]: g for g in groups}
        zan_group = by_name["爱点赞"]
        cmds = [c["cmd"] for c in zan_group["commands"]]
        assert cmds == ["zan", "赞我"], f"指令应排序: {cmds}"
        zan = zan_group["commands"][0]
        assert zan["alias"] == ["点赞"], f"别名应合并到主指令: {zan['alias']}"
        assert zan["desc"] == "给朋友点赞 🎉", "收集阶段应保留原始描述（渲染时去除 emoji）"

        builtin = by_name["AstrBot 内置指令"]
        assert [c["cmd"] for c in builtin["commands"]] == ["help"]

        # 去重：img 只出现一次，且描述来自先注册的插件
        img_group = by_name["生图工具"]
        img_cmds = [c["cmd"] for c in img_group["commands"]]
        assert img_cmds == ["img"], f"同名指令应去重: {img_cmds}"
        assert img_group["commands"][0]["desc"] == "生图指令"


def test_filters():
    with tempfile.TemporaryDirectory() as td:
        registry, star_map, cls = _install_and_import(Path(td))
        _populate(registry, star_map)

        plugin = cls(None, {"show_builtin": False})
        names = [g["name"] for g in plugin._collect_groups()]
        assert "AstrBot 内置指令" not in names

        plugin = cls(None, {"exclude_plugins": ["爱点赞"], "hide_self": False})
        names = [g["name"] for g in plugin._collect_groups()]
        assert "爱点赞" not in names
        assert "astrbot_plugin_menu_image" in names


def test_pagination():
    with tempfile.TemporaryDirectory() as td:
        registry, star_map, cls = _install_and_import(Path(td))
        groups = [
            {"name": f"插件{i}", "commands": [{"cmd": f"c{j}", "desc": ""} for j in range(n)]}
            for i, n in enumerate([30, 20, 10])
        ]
        pages = cls(None, {})._paginate(groups, 50)
        assert len(pages) == 2, f"应分 2 页: {len(pages)}"
        assert len(pages[0]) == 2 and len(pages[1]) == 1
        assert sum(len(g["commands"]) for g in pages[0]) == 50
        assert sum(len(g["commands"]) for g in pages[1]) == 10


def test_render_png():
    with tempfile.TemporaryDirectory() as td:
        from astrbot_plugin_menu_image.renderer import MenuRenderer

        cfg = {
            "menu_title": "功能菜单",
            "menu_subtitle": "AstrBot 指令汇总",
            "menu_footer": "发送 /menu 页码 查看更多",
            "command_prefix": "/",
            "font_size": 30,
        }
        renderer = MenuRenderer(Path(td), cfg)
        groups = [
            {
                "name": "AstrBot 内置指令",
                "commands": [
                    {"cmd": "help", "desc": "查看指令帮助"},
                    {"cmd": "reset", "desc": "重置会话上下文"},
                ],
            },
            {
                "name": "爱点赞",
                "commands": [
                    {"cmd": "zan", "desc": "给朋友点赞"},
                    {"cmd": "赞我", "desc": "让机器人赞我"},
                ],
            },
        ]
        out = Path(td) / "cache" / "test.png"
        result = renderer.render_page(
            groups, page=1, total_pages=1, total_commands=4, out_path=out
        )
        assert result is not None and out.exists(), "应成功生成 PNG"
        from PIL import Image

        with Image.open(out) as img:
            img.load()
            assert img.size[0] == 1080, f"宽度应为 1080: {img.size}"
            assert img.size[1] > 300, f"高度应合理: {img.size}"
        from astrbot_plugin_menu_image.renderer import sanitize_text

        assert sanitize_text("赞🎉") == "赞", "emoji 应被去除"


def test_text_fallback():
    with tempfile.TemporaryDirectory() as td:
        registry, star_map, cls = _install_and_import(Path(td))
        plugin = cls(None, {"menu_title": "功能菜单"})
        text = plugin._text_menu(
            [{"name": "爱点赞", "commands": [{"cmd": "zan", "desc": "给朋友点赞"}]}],
            page=1,
            total_pages=1,
            total_commands=1,
        )
        assert "/zan" in text and "给朋友点赞" in text and "第 1/1 页" in text


def main():
    tests = [
        test_collect_and_group,
        test_filters,
        test_pagination,
        test_render_png,
        test_text_fallback,
    ]
    passed = 0
    for t in tests:
        t()
        passed += 1
        print(f"PASS {t.__name__}")
    print(f"\n{passed}/{len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
