"""astrbot_plugin_menu_image - 菜单图片渲染器

纯 Pillow 实现，不依赖 AstrBot，便于独立测试。
自动探测系统中文字体（Windows / Linux / macOS），找不到字体时仍可渲染（中文显示为方块）。
渲染前会去除 emoji（PIL 无法绘制彩色 emoji）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF"
    "\U0001F300-\U0001F9FF"
    "\U00002600-\U000027BF"
    "\U00002B00-\U00002BFF"
    "\U00002190-\U000021FF"
    "\uFE0F\u200D]+"
)

_FONT_CANDIDATES: List[Tuple[str, str]] = [
    # (常规字体, 粗体字体) - 按优先级
    (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc"),
    (r"C:/Windows/Fonts/simhei.ttf", r"C:/Windows/Fonts/simhei.ttf"),
    (r"C:/Windows/Fonts/simsun.ttc", r"C:/Windows/Fonts/simhei.ttf"),
    (r"/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
     r"/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    (r"/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
     r"/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc"),
    (r"/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
     r"/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    (r"/System/Library/Fonts/PingFang.ttc", r"/System/Library/Fonts/PingFang.ttc"),
]

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def sanitize_text(text) -> str:
    """去除无法用普通字体渲染的 emoji 字符"""
    return _EMOJI_RE.sub("", str(text or ""))


def _hex(color, default: Tuple[int, int, int]) -> Tuple[int, int, int]:
    m = _HEX_RE.match(str(color or "").strip())
    if not m:
        return default
    v = int(m.group(1), 16)
    return ((v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF)


class MenuRenderer:
    """菜单图片渲染器（Pillow）"""

    WIDTH = 1080
    PAD_X = 64
    PAD_Y = 56

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
        self._init_font()

    def _init_font(self):
        try:
            from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        except ImportError:
            return
        for regular, bold in _FONT_CANDIDATES:
            if Path(regular).exists():
                self._font_path = regular
                self._font_bold_path = bold if Path(bold).exists() else regular
                self.available = True
                return
        # 字体不存在时仍尝试渲染（中文字符会显示为方块，但功能可用）
        self.available = True

    def _font(self, size: int, bold: bool = False):
        from PIL import ImageFont

        path = (self._font_bold_path if bold else self._font_path) or None
        try:
            return ImageFont.truetype(path, size) if path else ImageFont.load_default()
        except Exception:
            try:
                return ImageFont.truetype(self._font_path, size)
            except Exception:
                return ImageFont.load_default()

    def _wrap(self, draw, text: str, font, max_width: int) -> List[str]:
        """按字符宽度换行（兼容 CJK）"""
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
            "accent": _hex(cfg.get("accent_color"), (79, 156, 249)),
            "text": _hex(cfg.get("text_color"), (230, 233, 240)),
            "desc": _hex(cfg.get("desc_color"), (138, 147, 166)),
        }

    def render_page(
        self,
        groups: List[dict],
        *,
        page: int,
        total_pages: int,
        total_commands: int,
        out_path: Path,
    ) -> Optional[Path]:
        """把一组分组渲染成一张 PNG。成功返回 out_path，失败返回 None。"""
        from PIL import Image, ImageDraw

        pal = self._palette()
        prefix = str(self.cfg.get("command_prefix", "/"))
        title = sanitize_text(self.cfg.get("menu_title", "功能菜单"))
        subtitle = sanitize_text(self.cfg.get("menu_subtitle", ""))
        footer = sanitize_text(self.cfg.get("menu_footer", ""))
        fs = max(14, int(self.cfg.get("font_size", 30)))

        f_title = self._font(fs + 22, bold=True)
        f_sub = self._font(fs - 6)
        f_group = self._font(fs + 2, bold=True)
        f_cmd = self._font(fs, bold=True)
        f_desc = self._font(fs - 6)
        f_foot = self._font(fs - 9)

        W = self.WIDTH
        X = self.PAD_X
        content_w = W - X * 2

        # ── 第一步：用临时画布测量总高度 ──
        tmp = Image.new("RGB", (W, 800), pal["bg"])
        tdraw = ImageDraw.Draw(tmp)

        y = self.PAD_Y
        y += f_title.size + 14
        if subtitle:
            y += f_sub.size + 12
        y += 10  # 分隔线区
        for g in groups:
            y += 24 + f_group.size + 10
            for c in g.get("commands", []):
                y += f_cmd.size + 8
                desc = c.get("desc") or ""
                if desc:
                    lines = self._wrap(tdraw, desc, f_desc, content_w)
                    y += len(lines) * (f_desc.size + 8)
            y += 16
        y += 12 + f_foot.size + 8
        if footer:
            y += f_foot.size + 6
        y += self.PAD_Y

        # ── 第二步：正式绘制 ──
        img = Image.new("RGB", (W, y), pal["bg"])
        draw = ImageDraw.Draw(img)

        yy = self.PAD_Y
        # 标题
        draw.text((X, yy), title, font=f_title, fill=pal["text"])
        yy += f_title.size + 14
        if subtitle:
            draw.text((X, yy), subtitle, font=f_sub, fill=pal["desc"])
            yy += f_sub.size + 12
        # 分隔线
        draw.rounded_rectangle(
            [X, yy, X + content_w, yy + 4], radius=2, fill=pal["accent"]
        )
        yy += 10

        for g in groups:
            yy += 24
            gname = sanitize_text(g.get("name", "未分类"))
            gcount = len(g.get("commands", []))
            draw.text((X, yy), gname, font=f_group, fill=pal["accent"])
            gw = draw.textlength(gname, font=f_group)
            draw.text(
                (X + gw + 16, yy + 4), f"{gcount} 个指令", font=f_sub, fill=pal["desc"]
            )
            yy += f_group.size + 10
            for c in g.get("commands", []):
                cmd = f"{prefix}{c.get('cmd', '')}"
                for a in c.get("alias") or []:
                    cmd += f"  {prefix}{a}"
                draw.text((X + 8, yy), cmd, font=f_cmd, fill=pal["text"])
                yy += f_cmd.size + 8
                desc = c.get("desc") or ""
                if desc:
                    for line in self._wrap(draw, desc, f_desc, content_w):
                        draw.text((X + 8, yy), line, font=f_desc, fill=pal["desc"])
                        yy += f_desc.size + 8
            yy += 16

        # 页脚
        yy += 12
        if total_pages == 1:
            foot_line = f"共 {total_commands} 个指令"
        else:
            foot_line = f"共 {total_commands} 个指令 · 第 {page}/{total_pages} 页"
        fw = draw.textlength(foot_line, font=f_foot)
        draw.text(((W - fw) / 2, yy), foot_line, font=f_foot, fill=pal["desc"])
        yy += f_foot.size + 8
        if footer:
            fw2 = draw.textlength(footer, font=f_foot)
            draw.text(((W - fw2) / 2, yy), footer, font=f_foot, fill=pal["desc"])
            yy += f_foot.size + 6

        # 圆角裁剪
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, img.size[0] - 1, img.size[1] - 1], radius=24, fill=255
        )
        out = Image.new("RGBA", img.size)
        out.paste(img, (0, 0), mask)

        try:
            out.save(out_path, "PNG")
        except OSError:
            return None
        self._cleanup_cache()
        return out_path

    def _cleanup_cache(self, limit: Optional[int] = None):
        """只保留最近的 limit 张图片（默认读取配置 cache_max_files）"""
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
        except OSError:
            pass
