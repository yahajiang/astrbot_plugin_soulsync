"""心镜 · 启明 - 图片渲染器

将列表和轮廓卡渲染为 PNG 图片（Pillow）。
- 自动探测系统 CJK 字体（Windows / Linux / macOS）
- 无 Pillow 或字体时优雅降级：返回 None，调用方回退为纯文本输出
- 渲染前会去除 emoji（PIL 无法渲染彩色 emoji），保留中文与特殊符号
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 需要剔除的 emoji（保留几何形状 █░ 用于进度条）
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF"
    "\U0001F300-\U0001F9FF"
    "\U00002600-\U000027BF"
    "\U00002B00-\U00002BFF"
    "\U00002190-\U000021FF"
    "\uFE0F\u200D]+"
)

# 分类图标映射（去除 emoji 后的替代文本）
_CATEGORY_LABELS = {
    "科学量表": "[科学]",
    "关系情感": "[关系]",
    "情绪状态": "[情绪]",
    "社交与职场": "[职场]",
    "网络玩梗与趣味": "[玩梗]",
}

_FONT_CANDIDATES: List[Tuple[str, str]] = [
    # Windows
    (r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/msyhbd.ttc"),
    (r"C:/Windows/Fonts/simhei.ttf", r"C:/Windows/Fonts/simhei.ttf"),
    (r"C:/Windows/Fonts/simsun.ttc", r"C:/Windows/Fonts/simhei.ttf"),
    # Linux - Noto CJK
    (r"/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
     r"/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    (r"/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
     r"/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc"),
    (r"/usr/share/fonts/noto/NotoSansCJK-Regular.ttc",
     r"/usr/share/fonts/noto/NotoSansCJK-Bold.ttc"),
    # Linux - WenQuanYi
    (r"/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
     r"/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    (r"/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
     r"/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    (r"/usr/share/fonts/wqy-microhei/wqy-microhei.ttc",
     r"/usr/share/fonts/wqy-microhei/wqy-microhei.ttc"),
    # Linux - Droid Sans
    (r"/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
     r"/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
    # Linux - Arphic
    (r"/usr/share/fonts/truetype/arphic/uming.ttc",
     r"/usr/share/fonts/truetype/arphic/uming.ttc"),
    # macOS
    (r"/System/Library/Fonts/PingFang.ttc", r"/System/Library/Fonts/PingFang.ttc"),
    (r"/System/Library/Fonts/Hiragino Sans GB.ttc",
     r"/System/Library/Fonts/Hiragino Sans GB.ttc"),
    (r"/Library/Fonts/Arial Unicode.ttf", r"/Library/Fonts/Arial Unicode.ttf"),
]


def sanitize_text(text: str) -> str:
    """去除无法用普通字体渲染的 emoji 字符"""
    return _EMOJI_RE.sub("", text)


class ImageRenderer:
    """图片渲染器（Pillow）"""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir) / "images"
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self.available: bool = False
        self._font_path: Optional[str] = None
        self._font_bold_path: Optional[str] = None
        self._init()

    def _init(self):
        try:
            from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        except ImportError:
            return

        # 1. 检查插件自带字体
        plugin_font = Path(__file__).parent / "fonts" / "NotoSansSC-Regular.ttf"
        plugin_font_bold = Path(__file__).parent / "fonts" / "NotoSansSC-Bold.ttf"
        if plugin_font.exists():
            self._font_path = str(plugin_font)
            self._font_bold_path = str(plugin_font_bold) if plugin_font_bold.exists() else str(plugin_font)
            self.available = True
            return

        # 2. 检查系统字体
        for regular, bold in _FONT_CANDIDATES:
            if Path(regular).exists():
                self._font_path = regular
                self._font_bold_path = bold if Path(bold).exists() else regular
                self.available = True
                return

        # 3. 动态搜索（fc-list）
        try:
            import subprocess
            result = subprocess.run(
                ["fc-list", ":lang=zh", "file"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.strip().split("\n"):
                path = line.split(":")[0].strip()
                if path and Path(path).exists():
                    self._font_path = path
                    self._font_bold_path = path
                    self.available = True
                    return
        except Exception:
            pass

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

    def _new_image(self, width: int, height: int):
        from PIL import Image
        return Image.new("RGB", (width, height), (21, 26, 38))

    def _round_corners(self, img, radius: int = 20):
        from PIL import Image, ImageDraw
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, img.size[0] - 1, img.size[1] - 1], radius=radius, fill=255
        )
        out = Image.new("RGBA", img.size)
        out.paste(img, (0, 0), mask)
        return out

    def _add_shadow(self, img, margin: int = 14, blur: int = 10, alpha: int = 110):
        from PIL import Image, ImageFilter, ImageDraw
        w, h = img.size
        canvas = Image.new("RGBA", (w + margin * 2, h + margin * 2), (0, 0, 0, 0))
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            [margin, margin, w + margin - 1, h + margin - 1],
            radius=20, fill=(0, 0, 0, alpha),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
        canvas.paste(shadow, (0, 0), shadow)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        canvas.paste(img, (margin, margin), img)
        return canvas

    def _paint_background(self, img, accent: Tuple[int, int, int] = (91, 141, 239)):
        """深色渐变背景 + 光晕 + 星光粒子"""
        from PIL import Image, ImageDraw
        import random as _rnd
        w, h = img.size
        d = ImageDraw.Draw(img)

        # 分段渐变
        bands = 72
        for i in range(bands):
            t = i / max(1, bands - 1)
            if t < 0.45:
                tt = t / 0.45
                base = (round(30 - 8 * tt), round(25 - 7 * tt), round(56 - 16 * tt))
            elif t < 0.75:
                tt = (t - 0.45) / 0.3
                base = (round(22 - 6 * tt), round(18 - 5 * tt), round(40 - 12 * tt))
            else:
                tt = (t - 0.75) / 0.25
                base = (round(16 - 4 * tt), round(13 - 3 * tt), round(28 - 6 * tt))
            d.rectangle([0, int(h * i / bands), w, int(h * (i + 1) / bands) + 1], fill=base)

        # 光晕层
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for cx, cy, gr, col, peak in [
            (w // 2, -60, int(w * 0.62), accent, 34),
            (int(w * 0.94), int(h * 0.86), int(w * 0.44), (86, 108, 230), 24),
            (int(w * 0.04), int(h * 0.08), int(w * 0.24), (255, 190, 120), 18),
        ]:
            for r in range(gr, 0, -4):
                a = int(peak * (1 - r / gr))
                gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (a,))
        img = img.convert("RGBA")
        img.alpha_composite(glow)

        # 星光粒子
        rnd = _rnd.Random(20260812)
        stars = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stars)
        for _ in range(48):
            x, y = rnd.randint(0, w - 1), rnd.randint(0, h - 1)
            r = rnd.choice((1, 1, 2))
            a = rnd.randint(40, 95)
            col = rnd.choice(((255, 255, 255), accent, (170, 195, 255)))
            sd.ellipse([x - r, y - r, x + r, y + r], fill=col + (a,))
        img.alpha_composite(stars)

        # 顶部细线 + 底部渐隐高光
        d2 = ImageDraw.Draw(img)
        d2.rectangle([0, 0, w, 1], fill=(130, 140, 170, 56))
        for i in range(w):
            t = abs(i - w / 2) / max(1, w / 2)
            a = int(46 * (1 - t * 0.55))
            d2.line([i, h - 1, i, h - 1], fill=accent + (a,))
        return img

    @staticmethod
    def _wrap_text(text: str, font, body_w: int) -> List[str]:
        text = sanitize_text(text)
        if not text:
            return [""]
        lines_out = []
        for raw in text.split("\n"):
            cur = ""
            for ch in raw:
                if font.getlength(cur + ch) > body_w and cur:
                    lines_out.append(cur)
                    cur = ch
                else:
                    cur += ch
            if cur:
                lines_out.append(cur)
        return lines_out or [""]

    def _save(self, img, file_name: str) -> str:
        if not file_name.lower().endswith(".png"):
            file_name += ".png"
        path = self.data_dir / file_name
        img.save(path, "PNG")
        self._cleanup()
        return str(path)

    def _cleanup(self, keep: int = 30):
        try:
            files = sorted(
                self.data_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True
            )
            for old in files[keep:]:
                old.unlink()
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    #  图鉴列表卡片
    # ═══════════════════════════════════════════════════════════════
    def render_guide_list(
        self,
        guide_data: Dict[str, dict],
        category_order: List[str],
        category_icons: Dict[str, str],
        total: int,
        file_name: str = "guide_list.png",
    ) -> Optional[str]:
        """渲染图鉴列表卡片，返回 PNG 路径；失败返回 None"""
        if not self.available:
            return None
        try:
            from PIL import ImageDraw

            width = 800
            pad = 34
            title_h = 104
            cat_h = 48
            row_h = 38
            footer_h = 80
            body_w = width - pad * 2

            title_font = self._font(27, bold=True)
            cat_font = self._font(21, bold=True)
            guide_font = self._font(17)
            alias_font = self._font(15)
            footer_font = self._font(14)
            date_font = self._font(14)

            # 预计算高度
            categories_data = []
            for cat in category_order:
                items = [g for g in guide_data.values() if g["category"] == cat]
                categories_data.append((cat, items))

            height = title_h + pad * 2
            for cat, items in categories_data:
                height += cat_h
                height += len(items) * row_h
                height += 8  # category bottom margin
            height += footer_h

            img = self._paint_background(self._new_image(width, height), accent=(91, 141, 239))
            draw = ImageDraw.Draw(img)

            # 标题区
            draw.rectangle([0, 0, width, title_h], fill=(24, 30, 46))
            for i in range(body_w):
                t = i / max(1, body_w - 1)
                c = (round(91 + 120 * t), round(141 - 30 * t), round(239 - 80 * t))
                draw.line([pad + i, 6, pad + i, 8], fill=c)
            draw.rounded_rectangle([pad - 14, 30, pad - 8, 66], radius=3, fill=(91, 141, 239))
            draw.text((pad + 1, 27), "心镜 · 启明", font=title_font, fill=(0, 0, 0))
            draw.text((pad, 26), "心镜 · 启明", font=title_font, fill=(255, 236, 190))
            subtitle = f"可用图鉴（{total}个）"
            draw.text((pad, 62), subtitle, font=footer_font, fill=(150, 160, 186))
            date_str = time.strftime("%Y-%m-%d %H:%M")
            draw.text((width - pad - date_font.getlength(date_str), title_h - 26),
                      date_str, font=date_font, fill=(140, 152, 180))

            y = title_h + 20

            # 分类渲染
            accent_colors = {
                "科学量表": (91, 141, 239),
                "关系情感": (240, 101, 149),
                "情绪状态": (247, 183, 49),
                "社交与职场": (80, 200, 180),
                "网络玩梗与趣味": (167, 139, 250),
            }

            for cat, items in categories_data:
                accent = accent_colors.get(cat, (91, 141, 239))
                label = _CATEGORY_LABELS.get(cat, cat)
                cat_text = f"{label} {cat} ({len(items)})"
                cat_text = sanitize_text(cat_text)
                seg_w = cat_font.getlength(cat_text)

                # 分类徽章
                draw.rounded_rectangle(
                    [pad, y, pad + seg_w + 36, y + 36], radius=8,
                    fill=accent + (60,))
                draw.rounded_rectangle(
                    [pad + 8, y + 6, pad + 12, y + 30], radius=2, fill=accent)
                draw.text((pad + 20, y + 5), cat_text, font=cat_font,
                          fill=(255, 214, 130))
                y += cat_h

                # 图鉴行
                for item in items:
                    name = sanitize_text(item["name"])
                    aliases = item.get("aliases", [])[:3]
                    alias_str = " / ".join(sanitize_text(a) for a in aliases)

                    draw.text((pad + 16, y + 6), name, font=guide_font,
                              fill=(226, 232, 244))
                    if alias_str:
                        name_w = guide_font.getlength(name)
                        draw.text((pad + 24 + name_w, y + 8), alias_str,
                                  font=alias_font, fill=(150, 160, 186))
                    y += row_h

                y += 8

            # 底部分隔线
            cx = pad + body_w // 2
            for i in range(-10, 11):
                a = max(20, 130 - abs(i) * 10)
                draw.rounded_rectangle(
                    [cx + i * 6, y + 3, cx + i * 6 + 4, y + 5],
                    radius=2, fill=(91, 141, 239, a))
            y += 14

            # 底部提示
            tips = [
                "输入 /心镜 [名称] 直接开启对应图鉴（不区分大小写）",
                "例如：/心镜 mbti、/心镜 攻受、/心镜 班味",
            ]
            for tip in tips:
                draw.text((pad + 6, y), sanitize_text(tip), font=footer_font,
                          fill=(160, 170, 196))
                y += 22

            rounded = self._round_corners(img)
            return self._save(self._add_shadow(rounded), file_name)
        except Exception:
            return None

    # ═══════════════════════════════════════════════════════════════
    #  轮廓卡卡片
    # ═══════════════════════════════════════════════════════════════
    def render_profile_card(
        self,
        content: str,
        file_name: str = "profile.png",
    ) -> Optional[str]:
        """渲染轮廓卡，返回 PNG 路径；失败返回 None"""
        if not self.available:
            return None
        try:
            from PIL import ImageDraw

            width = 800
            pad = 34
            title_h = 104
            line_h = 44
            body_w = width - pad * 2

            title_font = self._font(25, bold=True)
            dim_font = self._font(19, bold=True)
            body_font = self._font(17)
            arrow_font = self._font(17, bold=True)
            footer_font = self._font(15)
            date_font = self._font(14)

            # 预分类行
            body_lines = []
            for line in content.split("\n"):
                stripped = line.strip()
                if not stripped:
                    body_lines.append(("", "gap"))
                elif stripped.startswith("●"):
                    body_lines.append((stripped, "dimension"))
                elif stripped.startswith("→"):
                    body_lines.append((stripped, "arrow"))
                elif stripped.startswith("✦"):
                    body_lines.append((stripped, "footer"))
                elif stripped.startswith("─") or stripped.startswith("━"):
                    body_lines.append((stripped, "div"))
                elif stripped.startswith('"') or stripped.startswith('"') or stripped.startswith("「"):
                    body_lines.append((stripped, "quote"))
                else:
                    for piece in self._wrap_text(stripped, body_font, body_w):
                        body_lines.append((piece, "plain"))

            # 计算高度
            height = title_h + pad * 2
            for text, kind in body_lines:
                if kind == "gap":
                    height += line_h // 2
                elif kind == "div":
                    height += line_h // 2 + 6
                elif kind == "dimension":
                    height += line_h + 4
                elif kind == "arrow":
                    height += line_h
                elif kind == "footer":
                    height += line_h + 8
                else:
                    height += line_h

            img = self._paint_background(self._new_image(width, height), accent=(91, 141, 239))
            draw = ImageDraw.Draw(img)

            # 标题区
            draw.rectangle([0, 0, width, title_h], fill=(24, 30, 46))
            for i in range(body_w):
                t = i / max(1, body_w - 1)
                c = (round(91 + 120 * t), round(141 - 30 * t), round(239 - 80 * t))
                draw.line([pad + i, 6, pad + i, 8], fill=c)
            draw.rounded_rectangle([pad - 14, 30, pad - 8, 66], radius=3, fill=(91, 141, 239))
            draw.text((pad + 1, 27), "镜面轮廓 · 回响", font=title_font, fill=(0, 0, 0))
            draw.text((pad, 26), "镜面轮廓 · 回响", font=title_font, fill=(255, 236, 190))
            draw.text((pad, 62), "仅供自我探索，不替代诊断", font=footer_font, fill=(150, 160, 186))
            date_str = time.strftime("%Y-%m-%d %H:%M")
            draw.text((width - pad - date_font.getlength(date_str), title_h - 26),
                      date_str, font=date_font, fill=(140, 152, 180))

            y = title_h + 20

            for text, kind in body_lines:
                if kind == "gap":
                    y += line_h // 2
                    continue

                if kind == "div":
                    cx = pad + body_w // 2
                    for i in range(-10, 11):
                        a = max(20, 130 - abs(i) * 10)
                        draw.rounded_rectangle(
                            [cx + i * 6, y + line_h // 2 - 1, cx + i * 6 + 4, y + line_h // 2 + 1],
                            radius=2, fill=(91, 141, 239, a))
                    y += line_h // 2 + 6
                    continue

                if kind == "dimension":
                    # 维度标题：蓝色背景 + 白色文字
                    dim_text = sanitize_text(text.lstrip("● ").strip())
                    draw.rounded_rectangle(
                        [pad, y, pad + body_w, y + line_h], radius=10,
                        fill=(91, 141, 239, 30))
                    draw.rounded_rectangle(
                        [pad, y + 6, pad + 4, y + line_h - 6], radius=2,
                        fill=(91, 141, 239))
                    draw.text((pad + 16, y + 10), dim_text, font=dim_font,
                              fill=(200, 220, 255))
                    y += line_h + 4
                    continue

                if kind == "arrow":
                    arrow_text = sanitize_text(text)
                    draw.text((pad + 16, y + 8), arrow_text, font=arrow_font,
                              fill=(122, 192, 255))
                    y += line_h
                    continue

                if kind == "footer":
                    footer_text = sanitize_text(text)
                    # 琥珀色背景
                    draw.rounded_rectangle(
                        [pad, y, pad + body_w, y + line_h + 8], radius=10,
                        fill=(247, 183, 49, 26))
                    draw.rounded_rectangle(
                        [pad, y + 8, pad + 4, y + line_h], radius=2,
                        fill=(247, 183, 49))
                    # 按行绘制
                    flines = self._wrap_text(footer_text, footer_font, body_w - 30)
                    for i, fl in enumerate(flines):
                        draw.text((pad + 16, y + 10 + i * 24), fl, font=footer_font,
                                  fill=(255, 214, 130))
                    y += line_h + 8 + max(0, len(flines) - 1) * 24
                    continue

                if kind == "quote":
                    quote_text = sanitize_text(text)
                    qh = line_h + 4
                    draw.rounded_rectangle(
                        [pad, y, pad + body_w, y + qh], radius=10,
                        fill=(91, 141, 239, 26))
                    draw.rounded_rectangle(
                        [pad, y + 6, pad + 4, y + qh - 6], radius=2,
                        fill=(91, 141, 239))
                    draw.text((pad + 16, y + 8), quote_text, font=body_font,
                              fill=(222, 230, 246))
                    y += qh + 10
                    continue

                # 普通行
                plain_text = sanitize_text(text)
                draw.text((pad + 16, y + 8), plain_text, font=body_font,
                          fill=(226, 232, 244))
                y += line_h

            rounded = self._round_corners(img)
            return self._save(self._add_shadow(rounded), file_name)
        except Exception:
            return None
