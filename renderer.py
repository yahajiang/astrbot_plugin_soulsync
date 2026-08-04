# -*- coding: utf-8 -*-
"""astrbot_plugin_menu_image - 菜单图片渲染器

纯 Pillow 实现，不依赖 AstrBot，便于独立测试。
自动探测系统中文字体（Windows / Linux / macOS / WSL），找不到字体时仍可渲染（中文显示为方块）。
支持配置 custom_font_path 手动指定字体文件。
渲染前会去除 emoji（PIL 无法绘制彩色 emoji）。

v2 优化：
- 垂直渐变背景（从 bg_gradient_top 到 bg_color）
- 可选装饰光晕（右上/左下）
- 分组卡片化（圆角半透明卡片包裹每个分组）
- 指令/别名分行显示，视觉层次更清晰
- 管理员标记 badge 样式
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

_log = logging.getLogger("astrbot_plugin_menu_image.renderer")

_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF"
    "\U0001F300-\U0001F9FF"
    "\U00002600-\U000027BF"
    "\U00002B00-\U00002BFF"
    "\U00002190-\U000021FF"
    "\uFE0F\u200D]+"
)

_FONT_CANDIDATES: List[Tuple[str, str]] = [
    (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc"),
    (r"C:/Windows/Fonts/simhei.ttf", r"C:/Windows/Fonts/simhei.ttf"),
    (r"C:/Windows/Fonts/simsun.ttc", r"C:/Windows/Fonts/simhei.ttf"),
    (r"C:/Windows/Fonts/Deng.ttf", r"C:/Windows/Fonts/Dengb.ttf"),
    (r"C:/Windows/Fonts/simkai.ttf", r"C:/Windows/Fonts/simhei.ttf"),
    (r"C:/Windows/Fonts/simfang.ttf", r"C:/Windows/Fonts/simhei.ttf"),
    (r"/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
     r"/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    (r"/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
     r"/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc"),
    (r"/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
     r"/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf"),
    (r"/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
     r"/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    (r"/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
     r"/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    (r"/System/Library/Fonts/PingFang.ttc", r"/System/Library/Fonts/PingFang.ttc"),
    (r"/System/Library/Fonts/Hiragino Sans GB.ttc",
     r"/System/Library/Fonts/Hiragino Sans GB.ttc"),
]

_CJK_KEYWORDS: Tuple[str, ...] = (
    "msyh", "simhei", "simsun", "dengxian", "simkai", "simfang", "stxihei",
    "stkaiti", "stsong", "stfangsong", "noto", "wqy", "zenhei", "sourcehan",
    "sarasa", "pingfang", "heiti", "songti", "kaiti", "fangsong", "hannom",
    "harmonyos", "miui", "oppo", "alibaba",
)

_FONT_EXTENSIONS = (".ttf", ".ttc", ".otf")

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def sanitize_text(text) -> str:
    return _EMOJI_RE.sub("", str(text or ""))


def _hex(color, default: Tuple[int, int, int]) -> Tuple[int, int, int]:
    m = _HEX_RE.match(str(color or "").strip())
    if not m:
        return default
    v = int(m.group(1), 16)
    return ((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)


def _glob_candidates() -> List[Path]:
    dirs: List[Path] = []
    if sys.platform == "win32":
        windir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        dirs.append(windir)
    else:
        dirs += [
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            Path("~/.fonts").expanduser(),
            Path("~/.local/share/fonts").expanduser(),
            Path("/mnt/c/Windows/Fonts"),
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts"),
            Path("~/Library/Fonts").expanduser(),
        ]
    found: List[Path] = []
    seen: set = set()
    for d in dirs:
        if not d.is_dir():
            continue
        try:
            iterator = d.rglob("*")
        except OSError:
            continue
        for p in iterator:
            if p.suffix.lower() not in _FONT_EXTENSIONS:
                continue
            name = p.name.lower()
            if not any(k in name for k in _CJK_KEYWORDS):
                continue
            if name in seen:
                continue
            seen.add(name)
            found.append(p)
    return found


def _font_loads(path) -> bool:
    try:
        from PIL import ImageFont
        ImageFont.truetype(str(path), 12)
        return True
    except Exception:
        return False

class MenuRenderer:
    """菜单图片渲染器（Pillow）"""

    WIDTH = 1080
    PAD_X = 64
    PAD_Y = 56

    CARD_PAD_TOP = 16
    CARD_PAD_BOTTOM = 16
    CARD_PAD_SIDE = 16
    CARD_RADIUS = 16
    CARD_SPACING = 20
    ALIAS_INDENT = 24
    DESC_INDENT = 24

    def __init__(self, data_dir: Path, cfg: Optional[dict] = None):
        self.cfg = cfg or {}
        self.cache_dir = Path(data_dir) / "cache"
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        self.available: bool = False
        self._font_path: Optional[str] = None
        self._font_bold_path: Optional[str] = None
        self._fallback_paths: List[str] = []
        self._init_font()

    def _init_font(self):
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            _log.warning("Pillow 未安装，菜单图片无法渲染")
            return
        custom = str(self.cfg.get("custom_font_path") or "").strip()
        if custom:
            if Path(custom).exists() and _font_loads(custom):
                self._font_path = custom
                self._font_bold_path = custom
                self._fallback_paths = []
                self.available = True
                _log.info(f"使用自定义字体: {self.font_summary}")
                return
            _log.warning(f"custom_font_path 无效: {custom}，将尝试自动探测系统字体")
        pairs: List[Tuple[str, str]] = list(_FONT_CANDIDATES)
        for p in _glob_candidates():
            pairs.append((str(p), str(p)))
        seen: set = set()
        for regular, bold in pairs:
            if regular in seen or not Path(regular).exists():
                continue
            seen.add(regular)
            if not _font_loads(regular):
                continue
            self._font_path = regular
            if Path(bold).exists() and _font_loads(bold):
                self._font_bold_path = bold
            else:
                self._font_bold_path = regular
            self._fallback_paths = [r for r, _ in pairs if Path(r).exists() and r not in seen][:10]
            self.available = True
            _log.info(f"已自动探测到中文字体: {self.font_summary}")
            return
        self._fallback_paths = []
        self.available = True
        _log.warning("未找到可用的中文字体，菜单中的中文将显示为方框。")

    @property
    def font_summary(self) -> str:
        if not self._font_path:
            return "未找到字体"
        try:
            from PIL import ImageFont
            fam = ImageFont.truetype(self._font_path, 12).getname()
            return f"{Path(self._font_path).name} ({fam[0]} {fam[1]})"
        except Exception:
            return str(self._font_path)

    def _font(self, size: int, bold: bool = False):
        from PIL import ImageFont
        path = (self._font_bold_path if bold else self._font_path) or None
        if path:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
        for alt in self._fallback_paths:
            try:
                return ImageFont.truetype(alt, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _wrap(self, draw, text: str, font, max_width: int) -> List[str]:
        lines: List[str] = []
        cur = ""
        for ch in text:
            if draw.textlength(cur + ch, font=font) <= max_width:
                cur += ch
            else:
                if cur:
                    lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
        return lines or [""]

    def _palette(self):
        cfg = self.cfg
        return {
            "bg": _hex(cfg.get("bg_color"), (21, 26, 38)),
            "bg_top": _hex(cfg.get("bg_gradient_top"), (15, 20, 30)),
            "card_bg": _hex(cfg.get("card_bg_color"), (26, 32, 53)),
            "accent": _hex(cfg.get("accent_color"), (79, 156, 249)),
            "text": _hex(cfg.get("text_color"), (230, 233, 240)),
            "desc": _hex(cfg.get("desc_color"), (138, 147, 166)),
        }

    @staticmethod
    def _make_gradient(width: int, height: int, top_color, bottom_color):
        from PIL import Image, ImageDraw
        if top_color == bottom_color:
            return Image.new("RGB", (width, height), bottom_color)
        gradient = Image.new("L", (width, height))
        gdraw = ImageDraw.Draw(gradient)
        for y in range(height):
            ratio = y / max(height - 1, 1)
            val = int(255 * (1.0 - ratio))
            gdraw.line([(0, y), (width, y)], fill=val)
        top = Image.new("RGB", (width, height), top_color)
        bot = Image.new("RGB", (width, height), bottom_color)
        return Image.composite(top, bot, gradient)

    @staticmethod
    def _add_glow(draw, width: int, height: int, accent_color, alpha: int = 30):
        cx, cy = width - 80, -40
        for r in range(200, 0, -20):
            a = max(0, int(alpha * (1.0 - r / 200)))
            if a <= 0:
                continue
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*accent_color, a))
        cx, cy = -60, height + 40
        for r in range(180, 0, -20):
            a = max(0, int(alpha * (1.0 - r / 180)))
            if a <= 0:
                continue
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*accent_color, a))

    def render_page(self, groups: List[dict], *, page: int, total_pages: int, total_commands: int, out_path: Path) -> Optional[Path]:
        from PIL import Image, ImageDraw

        pal = self._palette()
        prefix = str(self.cfg.get("command_prefix", "/"))
        title = sanitize_text(self.cfg.get("menu_title", "功能菜单"))
        subtitle = sanitize_text(self.cfg.get("menu_subtitle", ""))
        footer = sanitize_text(self.cfg.get("menu_footer", ""))
        fs = max(14, int(self.cfg.get("font_size", 30)))
        show_glow = bool(self.cfg.get("bg_glow", True))

        f_title = self._font(fs + 22, bold=True)
        f_sub = self._font(fs - 6)
        f_group = self._font(fs + 2, bold=True)
        f_cmd = self._font(fs, bold=True)
        f_desc = self._font(fs - 6)
        f_foot = self._font(fs - 9)

        W = self.WIDTH
        X = self.PAD_X
        content_w = W - X * 2
        cmd_indent = 8

        # Measure pass
        tmp = Image.new("RGB", (W, 800), pal["bg"])
        tdraw = ImageDraw.Draw(tmp)

        y = self.PAD_Y
        y += f_title.size + 14
        if subtitle:
            y += f_sub.size + 12
        y += 10
        card_regions: List[Tuple[int, int]] = []

        for g in groups:
            card_top = y
            y += self.CARD_PAD_TOP
            y += f_group.size + 10
            for c in g.get("commands", []):
                y += f_cmd.size + 4
                if c.get("alias"):
                    y += f_sub.size + 4
                y += 8
                desc = c.get("desc") or ""
                if desc:
                    desc_max_w = content_w - cmd_indent - self.DESC_INDENT
                    lines = self._wrap(tdraw, desc, f_desc, max(40, desc_max_w))
                    y += len(lines) * (f_desc.size + 8)
            y += self.CARD_PAD_BOTTOM
            card_regions.append((card_top, y))
            y += self.CARD_SPACING

        y += 12 + f_foot.size + 8
        if footer:
            y += f_foot.size + 6
        y += self.PAD_Y

        # Gradient background + glow
        img = self._make_gradient(W, y, pal["bg_top"], pal["bg"])
        img = img.convert("RGBA")
        draw = ImageDraw.Draw(img)
        if show_glow:
            self._add_glow(draw, W, y, pal["accent"], alpha=30)

        # Card backgrounds
        card_bg_rgba = (*pal["card_bg"], 200)
        for i, g in enumerate(groups):
            if i >= len(card_regions):
                break
            cy1, cy2 = card_regions[i]
            draw.rounded_rectangle(
                [X - self.CARD_PAD_SIDE, cy1, X + content_w + self.CARD_PAD_SIDE, cy2],
                radius=self.CARD_RADIUS, fill=card_bg_rgba,
            )

        # Content
        yy = self.PAD_Y
 

        draw.text((X, yy), title, font=f_title, fill=pal["text"])
        yy += f_title.size + 14
        if subtitle:
            draw.text((X, yy), subtitle, font=f_sub, fill=pal["desc"])
            yy += f_sub.size + 12
        draw.rounded_rectangle([X, yy, X + content_w, yy + 4], radius=2, fill=pal["accent"])
        yy += 10

        for i, g in enumerate(groups):
            cy1, cy2 = card_regions[i] if i < len(card_regions) else (yy, yy + 100)
            yy = cy1 + self.CARD_PAD_TOP

            gname = sanitize_text(g.get("name", "未分类"))
            gcount = len(g.get("commands", []))
            draw.text((X, yy), gname, font=f_group, fill=pal["accent"])

            # Count badge
            count_text = str(gcount)
            cw = draw.textlength(count_text, font=f_sub)
            bp = 6
            bw = cw + bp * 2
            bh = f_sub.size + 4
            bx = X + int(draw.textlength(gname, font=f_group)) + 16
            draw.rounded_rectangle([bx, yy + 2, bx + bw, yy + 2 + bh], radius=6, fill=(*pal["accent"], 50))
            draw.text((bx + bp, yy + 3), count_text, font=f_sub, fill=pal["accent"])

            yy += f_group.size + 10

            for c in g.get("commands", []):
                main_cmd = f"{prefix}{c.get('cmd', '')}"
                cmd_aliases = c.get("alias") or []

                draw.text((X + cmd_indent, yy), main_cmd, font=f_cmd, fill=pal["text"])

                # Admin badge
                if c.get("admin") and self.cfg.get("show_admin_mark", True):
                    mark = str(self.cfg.get("admin_mark", "[管理员]"))
                    if mark:
                        mw = draw.textlength(mark, font=f_sub)
                        mb_w = mw + 10
                        mb_h = f_sub.size + 4
                        mb_x = X + cmd_indent + int(draw.textlength(main_cmd, font=f_cmd)) + 10
                        draw.rounded_rectangle([mb_x, yy, mb_x + mb_w, yy + mb_h], radius=4, fill=(*pal["accent"], 40))
                        draw.text((mb_x + 5, yy + 1), mark, font=f_sub, fill=pal["accent"])

                yy += f_cmd.size + 4

                # Alias line
                if cmd_aliases:
                    alias_text = "  ".join(f"{prefix}{a}" for a in cmd_aliases)
                    draw.text((X + cmd_indent + self.ALIAS_INDENT, yy), alias_text, font=f_sub, fill=pal["desc"])
                    yy += f_sub.size + 4

                yy += 8

                desc = c.get("desc") or ""
                if desc:
                    desc_max_w = content_w - cmd_indent - self.DESC_INDENT
                    for line in self._wrap(draw, desc, f_desc, max(40, desc_max_w)):
                        draw.text((X + cmd_indent + self.DESC_INDENT, yy), line, font=f_desc, fill=pal["desc"])
                        yy += f_desc.size + 8

            yy = cy2 + self.CARD_SPACING

        # Footer
        yy += 12
        foot_line = f"共 {total_commands} 个指令" if total_pages == 1 else f"共 {total_commands} 个指令 · 第 {page}/{total_pages} 页"
        fw = draw.textlength(foot_line, font=f_foot)
        draw.text(((W - fw) / 2, yy), foot_line, font=f_foot, fill=pal["desc"])
        yy += f_foot.size + 8
        if footer:
            fw2 = draw.textlength(footer, font=f_foot)
            draw.text(((W - fw2) / 2, yy), footer, font=f_foot, fill=pal["desc"])
            yy += f_foot.size + 6

        # Rounded corners
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1], radius=24, fill=255)
        out = Image.new("RGBA", img.size)
        out.paste(img, (0, 0), mask)

        try:
            out.save(out_path, "PNG")
        except OSError:
            return None
        self._cleanup_cache()
        return out_path

    def _cleanup_cache(self, limit: Optional[int] = None):
        if limit is None:
            try:
                limit = max(1, int(self.cfg.get("cache_max_files", 20)))
            except (TypeError, ValueError):
                limit = 20
        try:
            files = sorted(self.cache_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
            for f in files[limit:]:
                f.unlink(missing_ok=True)
        except OSError:
            pass
