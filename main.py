"""astrbot_plugin_menu_image - 根据 Bot 全部已注册指令自动生成菜单图片

特性：
- 自动读取 AstrBot 所有已注册指令（含子指令与别名），无需手动维护列表
- 按插件自动分组，指令自带描述注释
- Pillow 渲染深色卡片风格图片，自动探测中文字体，Pillow 缺失时降级为纯文本
- 指令过多时自动分页：/menu [页码]
- 触发词：/menu 与 /菜单
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Dict, List, Tuple

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

from .renderer import MenuRenderer

try:
    from astrbot.core.star.filter.command import CommandFilter
    from astrbot.core.star.filter.permission import (
        PermissionType,
        PermissionTypeFilter,
    )
    from astrbot.core.star.star import star_map
    from astrbot.core.star.star_handler import EventType, star_handlers_registry

    _CORE_IMPORT_OK = True
except Exception as e:  # 核心模块导入失败时菜单功能不可用，指令直接提示
    _CORE_IMPORT_OK = False
    logger.warning(f"menu_image: 核心模块导入失败，菜单功能不可用: {e}")

_BUILTIN_LABEL = "AstrBot 内置指令"
_SELF_MODULE_PREFIX = "astrbot_plugin_menu_image"


class MenuImagePlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self.config = config or {}
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        self.data_dir = (
            Path(get_astrbot_data_path())
            / "plugin_data"
            / "astrbot_plugin_menu_image"
        )
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        self.renderer = MenuRenderer(self.data_dir, dict(self.config))
        self._groups_cache: Dict[bool, Tuple[float, str, List[Dict]]] = {}
        self._cache_fingerprint: str = ""
        self._groups_ttl = 60.0
        self._page_ttl = 30.0
        logger.info(
            f"菜单图片插件已加载 | 渲染={'可用' if self.renderer.available else '降级文本'} "
            f"| 字体={self.renderer.font_summary} | 触发词: /menu /菜单"
        )

    # ────────────────────── 指令枚举与分组 ──────────────────────

    def _resolve_group(self, module_path: str) -> Tuple[str, bool, object]:
        """根据 handler 模块路径解析插件元数据，返回 (名称, 是否内置, StarMetadata 或 None)"""
        parts = module_path.split(".")
        for i in range(len(parts), 0, -1):
            md = star_map.get(".".join(parts[:i]))
            if md is not None:
                if getattr(md, "reserved", False):
                    return _BUILTIN_LABEL, True, md
                name = (
                    getattr(md, "display_name", None)
                    or getattr(md, "name", None)
                    or parts[0]
                )
                return str(name), False, md
        if parts and parts[0] == "astrbot":
            return _BUILTIN_LABEL, True, None
        return parts[0] if parts else "未分类", False, None

    @staticmethod
    def _handler_requires_admin(handler) -> bool:
        """判断 handler 是否要求管理员权限（event_filters 中含 ADMIN 权限过滤器）"""
        for f in getattr(handler, "event_filters", []) or []:
            if isinstance(f, PermissionTypeFilter) and getattr(
                f, "permission_type", None
            ) == PermissionType.ADMIN:
                return True
        return False

    def _fingerprint(self) -> str:
        """轻量状态指纹：插件元数据 + 已注册 handler 概要。

        任何指令增删、插件启停、插件重载都会改变指纹，
        用于实时失效 _groups_cache 与已渲染的图片缓存。
        """
        parts = []
        for path, md in star_map.items():
            parts.append(
                f"{path}|{getattr(md, 'activated', True)}|"
                f"{getattr(md, 'version', '')}|{getattr(md, 'display_name', '')}"
            )
        for handler in star_handlers_registry:
            parts.append(
                f"{getattr(handler, 'handler_module_path', '')}|"
                f"{getattr(handler, 'handler_name', '')}|"
                f"{getattr(handler, 'enabled', True)}"
            )
        return hashlib.sha1(
            "|".join(sorted(parts)).encode("utf-8", "ignore")
        ).hexdigest()[:10]

    def _collect_groups(self, for_admin: bool = False) -> List[Dict]:
        """遍历 AstrBot 全部已注册 handler，收集指令并按插件分组。

        for_admin=True（管理员视图）：包含全部指令，管理员指令带 admin 标记；
        for_admin=False（普通用户视图）：只包含非管理员权限指令。

        缓存策略：状态指纹变化时立即失效（WebUI 变更插件状态实时可见）；
        指纹未变时按 60s TTL 强制刷新兜底（handler 描述等未纳入指纹的改动）。
        """
        fingerprint = self._fingerprint()
        cached = self._groups_cache.get(for_admin)
        if (
            cached is not None
            and time.monotonic() - cached[0] < self._groups_ttl
            and cached[1] == fingerprint
        ):
            self._cache_fingerprint = fingerprint
            return cached[2]
        self._cache_fingerprint = fingerprint
        exclude_plugins = [str(x) for x in (self.config.get("exclude_plugins") or [])]
        show_builtin = bool(self.config.get("show_builtin", True))
        hide_self = bool(self.config.get("hide_self", True))
        try:
            max_desc_len = max(0, int(self.config.get("max_desc_length", 60)))
        except (TypeError, ValueError):
            max_desc_len = 60

        groups: Dict[str, Dict] = {}
        seen: Dict[str, Dict] = {}

        for handler in star_handlers_registry:
            if handler.event_type != EventType.AdapterMessageEvent:
                continue
            if not getattr(handler, "enabled", True):
                continue
            requires_admin = self._handler_requires_admin(handler)
            # 普通用户视图：跳过管理员权限指令
            if not for_admin and requires_admin:
                continue
            module_path = getattr(handler, "handler_module_path", "") or ""
            if hide_self and module_path.startswith(_SELF_MODULE_PREFIX):
                continue
            name, is_builtin, plugin_md = self._resolve_group(module_path)
            # 仅展示已启用插件的指令（插件在 WebUI 中停用后 activated 为 False）
            if plugin_md is not None and not getattr(plugin_md, "activated", True):
                continue
            if is_builtin and not show_builtin:
                continue
            if any(
                name == x or module_path == x or module_path.startswith(x + ".")
                for x in exclude_plugins
            ):
                continue

            desc = (getattr(handler, "desc", "") or "").strip()
            desc = " ".join(desc.split())
            if len(desc) > max_desc_len:
                desc = desc[:max_desc_len] + "…"

            for f in getattr(handler, "event_filters", []) or []:
                if not isinstance(f, CommandFilter):
                    continue
                try:
                    names = f.get_complete_command_names()
                except Exception:
                    names = []
                if not names:
                    continue
                # names[0] 为主指令全路径，其余为别名（与主指令合并显示在同一行）
                cmd0 = str(names[0]).strip().lstrip("/")
                if not cmd0:
                    continue
                aliases = [
                    str(n).strip().lstrip("/") for n in names[1:]
                ]
                item = seen.get(cmd0)
                if item is None:
                    item = {
                        "cmd": cmd0,
                        "alias": [],
                        "desc": desc,
                        "admin": requires_admin,
                    }
                    seen[cmd0] = item
                    group = groups.setdefault(
                        module_path, {"name": name, "commands": []}
                    )
                    group["commands"].append(item)
                else:
                    # 同名指令（如多个插件拦截同一指令）：保留第一个，缺描述时补充
                    if desc and not item["desc"]:
                        item["desc"] = desc
                    if not item.get("admin") and requires_admin:
                        item["admin"] = True
                for a in aliases:
                    if not a or a in seen:
                        continue
                    seen[a] = item
                    if a not in item["alias"]:
                        item["alias"].append(a)

        # 排序：内置指令组优先，其余按名称排序；组内指令按名称排序
        ordered = sorted(
            groups.values(),
            key=lambda g: (
                0 if g["name"] == _BUILTIN_LABEL else 1,
                g["name"],
            ),
        )
        for g in ordered:
            g["commands"].sort(key=lambda c: c["cmd"])
        self._groups_cache[for_admin] = (time.monotonic(), fingerprint, ordered)
        return ordered

    def _cached_page(self, key: str):
        """同键渲染结果在 30s TTL 内直接复用（键含状态指纹，指令变更后旧图不再命中）"""
        try:
            now = time.monotonic()
            for p in self.renderer.cache_dir.glob(f"{key}_*.png"):
                if now - p.stat().st_mtime < self._page_ttl:
                    return p
        except OSError:
            pass
        return None

    @staticmethod
    def _paginate(groups: List[Dict], per_page: int) -> List[List[Dict]]:
        """按每页指令数分页，尽量保持插件分组完整（跨页的分组整体顺延到下一页）"""
        pages: List[List[Dict]] = []
        cur: List[Dict] = []
        count = 0
        for g in groups:
            n = len(g["commands"])
            if cur and count + n > per_page:
                pages.append(cur)
                cur = []
                count = 0
            cur.append(g)
            count += n
        if cur:
            pages.append(cur)
        return pages

    # ────────────────────── 输出 ──────────────────────

    @staticmethod
    def _is_admin(event: AstrMessageEvent) -> bool:
        """判断消息发送者是否为 AstrBot 管理员"""
        try:
            if hasattr(event, "is_admin"):
                return bool(event.is_admin())
        except Exception:
            pass
        return getattr(event, "role", "") == "admin"

    def _admin_mark(self, c: Dict) -> str:
        """管理员指令在文本降级输出中的标记"""
        if c.get("admin") and bool(self.config.get("show_admin_mark", True)):
            return str(self.config.get("admin_mark", "[管理员]"))
        return ""

    def _text_menu(
        self,
        page_groups: List[Dict],
        page: int,
        total_pages: int,
        total_commands: int,
    ) -> str:
        """Pillow 不可用时的纯文本降级输出"""
        lines = [str(self.config.get("menu_title", "功能菜单")), "=" * 24]
        for g in page_groups:
            lines.append(f"【{g['name']}】({len(g['commands'])} 个指令)")
            for c in g["commands"]:
                cmd = f"/{c['cmd']}"
                for a in c.get("alias") or []:
                    cmd += f" /{a}"
                mark = self._admin_mark(c)
                if mark:
                    cmd += f" {mark}"
                lines.append(f"  {cmd}" + (f" - {c['desc']}" if c["desc"] else ""))
        lines.append("=" * 24)
        lines.append(f"共 {total_commands} 个指令 · 第 {page}/{total_pages} 页")
        return "\n".join(lines)

    @filter.command("menu", alias={"菜单"})
    async def menu(self, event: AstrMessageEvent, page: int = 1):
        """查看功能菜单图片：自动汇总全部已注册指令。用法：/menu [页码]"""
        if not _CORE_IMPORT_OK:
            yield event.plain_result("菜单插件核心模块加载失败，请查看 AstrBot 日志。")
            return
        is_admin = self._is_admin(event)
        try:
            groups = self._collect_groups(for_admin=is_admin)
        except Exception as e:
            logger.error(f"menu_image: 收集指令失败: {e}")
            yield event.plain_result(f"菜单生成失败：{e}")
            return
        if not groups:
            yield event.plain_result("当前没有任何已注册的指令。")
            return

        total_commands = sum(len(g["commands"]) for g in groups)
        try:
            per_page = max(1, int(self.config.get("max_commands_per_page", 40)))
        except (TypeError, ValueError):
            per_page = 40
        pages = self._paginate(groups, per_page)
        total_pages = len(pages)
        if page < 1 or page > total_pages:
            page = 1
        page_groups = pages[page - 1]

        if not self.renderer.available:
            yield event.plain_result(
                self._text_menu(page_groups, page, total_pages, total_commands)
            )
            return

        cache_key = f"menu_{'a' if is_admin else 'u'}_p{page}_{self._cache_fingerprint}"
        rendered = self._cached_page(cache_key)
        if rendered is None:
            out_path = self.renderer.cache_dir / f"{cache_key}_{int(time.time())}.png"
            try:
                rendered = self.renderer.render_page(
                    page_groups,
                    page=page,
                    total_pages=total_pages,
                    total_commands=total_commands,
                    out_path=out_path,
                )
            except Exception as e:
                logger.error(f"menu_image: 渲染菜单图片失败: {e}")
                rendered = None
        if rendered is None or not Path(rendered).exists():
            yield event.plain_result(
                self._text_menu(page_groups, page, total_pages, total_commands)
            )
            return

        yield event.image_result(str(rendered))
        if total_pages > 1:
            yield event.plain_result(
                f"共 {total_pages} 页，当前第 {page} 页。发送 /menu 页码 查看其它页，例如 /menu 2"
            )
