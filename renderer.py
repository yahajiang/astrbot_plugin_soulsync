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

v3 优化：
- 标题左侧 accent 圆点 + 分隔线改渐变（左实右渐隐）
- 组标题左侧 accent 竖条，层级更清晰
- 指令行左侧空心圆点，别名以 ↳ 前缀引导
- 卡片加深 + 1px accent 描边
- 双层背景光晕（accent + 深蓝紫）
- 多页时底部页码圆点指示器（当前页高亮）
- 修复测量/绘制偏移（分隔线高度计入测量）

v3.1：
- 毛玻璃卡片（frost_glass，默认开）：卡片区域贴入高斯模糊背景 + 轻微提亮，可配置关闭
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
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

    CARD_PAD_TOP = 18
    CARD_PAD_BOTTOM = 18
    CARD_PAD_SIDE = 18
    CARD_RADIUS = 16
    CARD_SPACING = 24
    ALIAS_INDENT = 24
    DESC_INDENT = 24
    HEADER_LINE_H = 4
    GROUP_BAR_W = 4
    CMD_DOT_R = 5
    PAGE_DOT_R = 6

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
        self._font_cache: dict = {}
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
        key = (size, bold)
        cached = self._font_cache.get(key)
        if cached is not None:
            return cached
        from PIL import ImageFont
        path = (self._font_bold_path if bold else self._font_path) or None
        font = None
        if path:
            try:
                font = ImageFont.truetype(path, size)
            except Exception:
                pass
        if font is None:
            for alt in self._fallback_paths:
                try:
                    font = ImageFont.truetype(alt, size)
                    break
                except Exception:
                    continue
        if font is None:
            font = ImageFont.load_default()
        self._font_cache[key] = font
        return font

    def _wrap(self, draw, text: str, font, max_width: int) -> List[str]:
        """二分断点换行：textlength 单调非减，每行 O(log n) 次调用（逐字符为 O(n)）"""
        lines: List[str] = []
        n = len(text)
        i = 0
        while i < n:
            lo, hi = i + 1, n
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if draw.textlength(text[i:mid], font=font) <= max_width:
                    lo = mid
                else:
                    hi = mid - 1
            lines.append(text[i:lo])
            i = lo
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
    def _apply_frost(
        img,
        card_rects,
        radius: int = 2,
        scale: int = 4,
        lighten: int = 18,
    ):
        """毛玻璃：卡片区域贴入高斯模糊后的背景（磨砂质感 + 轻微提亮）

        背景缩至 1/scale 后模糊（等效大半径模糊），卡片区域从小图提取放大；
        提亮用 Image.eval 通道平移，避免整张全白 blend 的开销。
        """
        from PIL import Image, ImageDraw, ImageFilter

        W, H = img.size
        ext = 48
        small = img.resize((max(1, W // scale), max(1, H // scale)), Image.BILINEAR)
        small = small.filter(ImageFilter.GaussianBlur(radius))
        sw, sh = small.size
        for x1, y1, x2, y2 in card_rects:
            cw, ch = x2 - x1, y2 - y1
            sx1 = max(0, (x1 - ext) // scale)
            sy1 = max(0, (y1 - ext) // scale)
            sx2 = min(sw, (x2 + ext + scale - 1) // scale)
            sy2 = min(sh, (y2 + ext + scale - 1) // scale)
            src = small.crop((sx1, sy1, sx2, sy2))
            card = src.resize((cw + ext * 2, ch + ext * 2), Image.BILINEAR)
            card = card.crop((ext, ext, ext + cw, ext + ch))
            if lighten:
                card = Image.eval(card, lambda v: min(255, v + lighten))
            mask = Image.new("L", (cw, ch), 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                [0, 0, cw - 1, ch - 1], radius=MenuRenderer.CARD_RADIUS, fill=255
            )
            img.paste(card, (x1, y1), mask)

    @staticmethod
    def _make_glow_layer(
        width: int,
        height: int,
        accent_color,
        alpha: int = 55,
        second_color=(34, 44, 88),
        second_alpha: int = 70,
    ):
        """双层光晕图层：1/4 尺寸绘制后放大合成，大圆填充量减 16 倍

        右上 accent 光晕 + 左下深蓝紫光晕，BILINEAR 放大自带柔化。
        """
        from PIL import Image, ImageDraw

        scale = 4
        sw, sh = max(1, width // scale), max(1, height // scale)
        layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        ldraw = ImageDraw.Draw(layer)
        cx, cy = sw - 20, -10
        for r in range(60, 0, -6):
            a = max(0, int(alpha * (1.0 - r / 60)))
            if a <= 0:
                continue
            ldraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*accent_color, a))
        cx, cy = -18, sh + 15
        for r in range(55, 0, -5):
            a = max(0, int(second_alpha * (1.0 - r / 55)))
            if a <= 0:
                continue
            ldraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*second_color, a))
        return layer.resize((width, height), Image.BILINEAR)

    def render_page(self, groups: List[dict], *, page: int, total_pages: int, total_commands: int, out_path: Path) -> Optional[Path]:
        from PIL import Image, ImageDraw

        pal = self._palette()
        prefix = str(self.cfg.get("command_prefix", "/"))
        title = sanitize_text(self.cfg.get("menu_title", "功能菜单"))
        subtitle = sanitize_text(self.cfg.get("menu_subtitle", ""))
        footer = sanitize_text(self.cfg.get("menu_footer", ""))
        try:
            fs = max(14, int(self.cfg.get("font_size", 30)))
        except (TypeError, ValueError):
            fs = 30
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
        cmd_indent = self.CMD_DOT_R * 2 + 8

        # Measure pass
        tmp = Image.new("RGB", (W, 800), pal["bg"])
        tdraw = ImageDraw.Draw(tmp)

        y = self.PAD_Y
        y += f_title.size + 14
        if subtitle:
            y += f_sub.size + 12
        y += self.HEADER_LINE_H + 10
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

        if total_pages > 1:
            y += 4 + self.PAGE_DOT_R * 2 + 16
        y += 12 + f_foot.size + 8
        if footer:
            y += f_foot.size + 6
        y += self.PAD_Y

        # Gradient background + glow
        img = self._make_gradient(W, y, pal["bg_top"], pal["bg"])
        img = img.convert("RGBA")
        if show_glow:
            img = Image.alpha_composite(img, self._make_glow_layer(W, y, pal["accent"]))
        draw = ImageDraw.Draw(img)

        # Card backgrounds（frost_glass 开启时卡片区域改贴模糊背景，实现毛玻璃）
        card_bg_rgba = (*pal["card_bg"], 220)
        card_stroke_rgba = (*pal["accent"], 30)
        card_rects: List[Tuple[int, int, int, int]] = []
        for i, g in enumerate(groups):
            if i >= len(card_regions):
                break
            cy1, cy2 = card_regions[i]
            rect = (X - self.CARD_PAD_SIDE, cy1, X + content_w + self.CARD_PAD_SIDE, cy2)
            card_rects.append(rect)
            draw.rounded_rectangle(
                rect,
                radius=self.CARD_RADIUS, fill=card_bg_rgba,
                outline=card_stroke_rgba, width=1,
            )
        if bool(self.cfg.get("frost_glass", True)) and card_rects:
            self._apply_frost(img, card_rects)

        # Content
        yy = self.PAD_Y

        # 标题左侧 accent 圆点装饰
        dot_r = 7
        draw.ellipse(
            [X, yy + (f_title.size - dot_r * 2) / 2,
             X + dot_r * 2, yy + (f_title.size - dot_r * 2) / 2 + dot_r * 2],
            fill=pal["accent"],
        )
        draw.text((X + dot_r * 2 + 14, yy), title, font=f_title, fill=pal["text"])
        yy += f_title.size + 14
        if subtitle:
            draw.text((X + dot_r * 2 + 14, yy), subtitle, font=f_sub, fill=pal["desc"])
            yy += f_sub.size + 12
        # 渐变分隔线：accent 左实右渐隐
        seg_w = max(1, content_w // 8)
        for i, a in enumerate((150, 120, 90, 60, 35, 15)):
            draw.rectangle(
                [X + i * seg_w, yy, X + (i + 1) * seg_w, yy + self.HEADER_LINE_H],
                fill=(*pal["accent"], a),
            )
        yy += self.HEADER_LINE_H + 10

        for i, g in enumerate(groups):
            cy1, cy2 = card_regions[i] if i < len(card_regions) else (yy, yy + 100)
            yy = cy1 + self.CARD_PAD_TOP

            gname = sanitize_text(g.get("name", "未分类"))
            gcount = len(g.get("commands", []))
            draw.rounded_rectangle(
                [X, yy, X + self.GROUP_BAR_W, yy + f_group.size],
                radius=2, fill=pal["accent"],
            )
            gname_x = X + self.GROUP_BAR_W + 12
            draw.text((gname_x, yy), gname, font=f_group, fill=pal["accent"])

            # Count badge
            count_text = str(gcount)
            cw = draw.textlength(count_text, font=f_sub)
            bp = 6
            bw = cw + bp * 2
            bh = f_sub.size + 4
            bx = gname_x + int(draw.textlength(gname, font=f_group)) + 16
            card_right_limit = X + content_w - self.CARD_PAD_SIDE - 4
            if bx + bw > card_right_limit:
                bx = card_right_limit - bw
                bx = max(bx, X)
            draw.rounded_rectangle([bx, yy + 2, bx + bw, yy + 2 + bh], radius=6, fill=(*pal["accent"], 50))
            draw.text((bx + bp, yy + 3), count_text, font=f_sub, fill=pal["accent"])

            yy += f_group.size + 10

            for c in g.get("commands", []):
                main_cmd = f"{prefix}{c.get('cmd', '')}"
                cmd_aliases = c.get("alias") or []

                # 指令左侧圆点（accent 描边空心圆）
                dot_cy = yy + (f_cmd.size + 2) / 2
                draw.ellipse(
                    [X + 2 - self.CMD_DOT_R, dot_cy - self.CMD_DOT_R,
                     X + 2 + self.CMD_DOT_R, dot_cy + self.CMD_DOT_R],
                    outline=(*pal["accent"], 110), width=2,
                )
                draw.text((X + cmd_indent, yy), main_cmd, font=f_cmd, fill=pal["text"])

                # Admin badge
                if c.get("admin") and self.cfg.get("show_admin_mark", True):
                    mark = str(self.cfg.get("admin_mark", "[管理员]"))
                    if mark:
                        mw = draw.textlength(mark, font=f_sub)
                        mb_w = mw + 10
                        mb_h = f_sub.size + 4
                        mb_x = X + cmd_indent + int(draw.textlength(main_cmd, font=f_cmd)) + 10
                        card_right_limit = X + content_w - self.CARD_PAD_SIDE - 4
                        if mb_x + mb_w > card_right_limit:
                            mb_x = card_right_limit - mb_w
                            mb_x = max(mb_x, X)
                        draw.rounded_rectangle([mb_x, yy, mb_x + mb_w, yy + mb_h], radius=4, fill=(*pal["accent"], 40))
                        draw.text((mb_x + 5, yy + 1), mark, font=f_sub, fill=pal["accent"])

                yy += f_cmd.size + 4

                # Alias line
                if cmd_aliases:
                    alias_text = "  ".join(f"↳ {prefix}{a}" for a in cmd_aliases)
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

        # Page dots + Footer
        yy += 4
        if total_pages > 1:
            dot_d = self.PAGE_DOT_R * 2
            total_w = total_pages * dot_d + (total_pages - 1) * 14
            dx = (W - total_w) / 2
            dy = yy + self.PAGE_DOT_R
            for i in range(total_pages):
                c = pal["accent"] if i + 1 == page else (*pal["accent"], 55)
                draw.ellipse(
                    [dx - self.PAGE_DOT_R, dy - self.PAGE_DOT_R,
                     dx + self.PAGE_DOT_R, dy + self.PAGE_DOT_R],
                    fill=c,
                )
                dx += dot_d + 14
            yy += dot_d + 16
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
            out.save(out_path, "PNG", compress_level=1)
        except OSError:
            return None
        self._cleanup_cache()
        return out_path

    def _cleanup_cache(self, limit: Optional[int] = None):
        """清理缓存：保留最近 limit 个文件，超过 TTL（默认 30s）的旧文件一律删除。"""
        if limit is None:
            try:
                limit = max(1, int(self.cfg.get("cache_max_files", 20)))
            except (TypeError, ValueError):
                limit = 20
        try:
            files = sorted(
                self.cache_dir.glob("*.png"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for f in files[limit:]:
                f.unlink(missing_ok=True)
            try:
                ttl = max(1.0, float(self.cfg.get("cache_file_ttl", 30.0)))
            except (TypeError, ValueError):
                ttl = 30.0
            now = time.monotonic()
            for f in files:
                if now - f.stat().st_mtime > ttl:
                    f.unlink(missing_ok=True)
        except OSError:
            pass
