"""EmotionAI Pro - 指令输出图片渲染器

将文本指令输出渲染为卡片/趋势图 PNG 图片（Pillow）。
- 自动探测系统 CJK 字体（Windows / Linux / macOS）
- 无 Pillow 或字体时优雅降级：返回 None，调用方回退为纯文本输出
- 渲染前会去除 emoji（PIL 无法渲染彩色 emoji），保留中文与进度条符号
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import List, Optional, Tuple

# 需要剔除的 emoji / 变体选择符 / 零宽连接符（保留几何形状 █░ 用于进度条）
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
    (r"/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
     r"/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    (r"/System/Library/Fonts/PingFang.ttc", r"/System/Library/Fonts/PingFang.ttc"),
    (r"/System/Library/Fonts/Hiragino Sans GB.ttc",
     r"/System/Library/Fonts/Hiragino Sans GB.ttc"),
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

    def _new_image(self, width: int, height: int):
        from PIL import Image
        img = Image.new("RGB", (width, height), (21, 26, 38))
        return img

    def _round_corners(self, img, radius: int = 20):
        """给图片裁剪圆角（返回 RGBA）"""
        from PIL import Image, ImageDraw
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, img.size[0] - 1, img.size[1] - 1], radius=radius, fill=255
        )
        out = Image.new("RGBA", img.size)
        out.paste(img, (0, 0), mask)
        return out

    def _add_shadow(self, img: "Image", margin: int = 14, blur: int = 10,
                    alpha: int = 110) -> "Image":
        """给卡片加柔和投影（画布放大 margin，返回 RGBA）"""
        from PIL import Image, ImageFilter
        w, h = img.size
        canvas = Image.new("RGBA", (w + margin * 2, h + margin * 2), (0, 0, 0, 0))
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        from PIL import ImageDraw
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

    def _paint_background(self, img: "Image",
                          accent: Tuple[int, int, int] = (232, 96, 140)) -> "Image":
        """深色渐变背景 + 顶部光晕 + 底部微光，返回 RGBA 图"""
        from PIL import Image, ImageDraw
        w, h = img.size
        d = ImageDraw.Draw(img)
        # 垂直渐变（上深下略浅）
        bands = 48
        for i in range(bands):
            t = i / max(1, bands - 1)
            d.rectangle([0, int(h * i / bands), w, int(h * (i + 1) / bands) + 1],
                        fill=(round(18 - 6 * t), round(23 - 8 * t), round(34 - 11 * t)))
        # 顶部中心光晕（主题色泛光）
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        cx, cy, gr = w // 2, -40, w // 2
        for r in range(gr, 0, -3):
            a = int(26 * (1 - r / gr))
            gd.ellipse([cx - r, cy - r, cx + r, cy + r],
                       fill=(accent[0], accent[1], accent[2], a))
        img = img.convert("RGBA")
        img.alpha_composite(glow)
        # 底部细边高光
        ImageDraw.Draw(img).rectangle(
            [0, h - 2, w, h], fill=(accent[0], accent[1], accent[2], 46))
        return img

    def _draw_progress_bar(self, draw, x: int, y: int, filled: int, total: int,
                           color: Tuple[int, int, int], bar_w: int = 300,
                           bar_h: int = 12):
        """绘制圆角进度条（filled/total）"""
        from PIL import ImageDraw
        track = (46, 56, 80)
        r = bar_h // 2
        draw.rounded_rectangle([x, y, x + bar_w, y + bar_h], radius=r, fill=track)
        if filled > 0:
            fw = max(bar_h, int(bar_w * min(1.0, filled / max(1, total))))
            draw.rounded_rectangle([x, y, x + fw, y + bar_h], radius=r, fill=color)

    def _bar_color_for(self, text: str) -> Tuple[int, int, int]:
        """根据行前缀推断进度条颜色"""
        if "好感" in text:
            return (240, 101, 149)
        if "亲密" in text:
            return (167, 139, 250)
        if "进度" in text or "阶段" in text:
            return (80, 200, 180)
        return (91, 141, 239)

    # ═══════════════════════════════════════════════════════════════
    #  文本卡片
    # ═══════════════════════════════════════════════════════════════
    def render_card(self, title: str, lines: List[str],
                    file_name: str = "card.png") -> Optional[str]:
        """把文本行渲染成深色卡片图片，返回 PNG 路径；失败返回 None"""
        if not self.available:
            return None
        try:
            from PIL import ImageDraw

            width = 760
            pad = 32
            title_h = 84
            line_h = 40
            body_w = width - pad * 2

            # 预计算行高（支持多行文本自动换行）
            title_font = self._font(26, bold=True)
            body_font = self._font(20)
            label_font = self._font(20, bold=True)

            def wrap(text: str, font) -> List[str]:
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

            body_lines: List[str] = []
            for line in lines:
                body_lines.extend(wrap(line, body_font))

            height = title_h + len(body_lines) * line_h + pad * 2
            img = self._paint_background(self._new_image(width, height))
            draw = ImageDraw.Draw(img)

            # 标题区（半透明遮罩 + 顶部渐变强调条 + 标题文字阴影）
            draw.rectangle([0, 0, width, title_h], fill=(24, 30, 46))
            grad_w = width
            for i in range(grad_w):
                t = i / max(1, grad_w - 1)
                c = (round(120 - 40 * t), round(70 - 20 * t), round(160 - 60 * t))
                draw.line([i, 0, i, 5], fill=c)
            # 标题描边阴影（增强可读性）
            draw.text((pad + 1, 27), sanitize_text(title), font=title_font, fill=(0, 0, 0))
            draw.text((pad, 26), sanitize_text(title), font=title_font, fill=(255, 224, 130))
            # 分隔线
            draw.rectangle([pad, title_h - 8, width - pad, title_h - 7], fill=(70, 82, 116))

            div_re = re.compile(r"^[━─═·]{6,}$")
            bar_re = re.compile(r"^(.*?)([█░]{4,})$")
            sec_re = re.compile(r"^.{0,14}：$")

            y = title_h + 18
            for line in body_lines:
                if div_re.match(line):
                    draw.rounded_rectangle(
                        [pad, y + line_h // 2 - 1, width - pad, y + line_h // 2 + 1],
                        radius=2, fill=(66, 78, 110),
                    )
                    y += line_h
                    continue

                # 进度条行：`前缀 ████░░`
                mb = bar_re.match(line)
                if mb and ("█" in mb.group(2) or "░" in mb.group(2)):
                    pre, bar_chars = mb.group(1), mb.group(2)
                    filled = bar_chars.count("█")
                    total = len(bar_chars)
                    # 前缀（标签高亮）+ 右侧进度条
                    pre = sanitize_text(pre)
                    col_i = pre.find("：")
                    pre_fill = (226, 232, 244)
                    if 0 < col_i <= 12:
                        draw.text((pad, y + 2), pre[:col_i + 1], font=label_font,
                                  fill=(122, 192, 255))
                        rest = pre[col_i + 1:]
                        if rest:
                            draw.text((pad + label_font.getlength(pre[:col_i + 1]), y + 2),
                                      rest, font=body_font, fill=pre_fill)
                        pre_w = pad + label_font.getlength(pre[:col_i + 1]) + body_font.getlength(rest)
                    else:
                        draw.text((pad, y + 2), pre, font=body_font, fill=pre_fill)
                        pre_w = pad + body_font.getlength(pre)
                    bar_x = pre_w + 16
                    bar_w = min(300, width - bar_x - pad)
                    if bar_w > 40:
                        self._draw_progress_bar(
                            draw, bar_x, y + 6, filled, total,
                            self._bar_color_for(pre), bar_w=bar_w, bar_h=14,
                        )
                    y += line_h
                    continue

                # 分节标题（短行且以「：」结尾）：左侧强调条 + 琥珀加粗
                if sec_re.match(line):
                    seg = sanitize_text(line.rstrip("："))
                    draw.rounded_rectangle([pad, y + 8, pad + 4, y + line_h - 16],
                                           radius=2, fill=(232, 96, 140))
                    draw.text((pad + 14, y), seg, font=label_font, fill=(255, 210, 120))
                    y += line_h
                    continue

                # 普通行 / 标签行
                col_i = line.find("：")
                if 0 < col_i <= 12 and len(line) > col_i + 1 and not line[:1].isspace():
                    pre = line[:col_i + 1]
                    draw.text((pad, y), pre, font=label_font, fill=(122, 192, 255))
                    draw.text((pad + label_font.getlength(pre), y), line[col_i + 1:],
                              font=body_font, fill=(226, 232, 244))
                else:
                    draw.text((pad, y), line, font=body_font, fill=(226, 232, 244))
                y += line_h

            # 圆角 + 投影
            rounded = self._round_corners(img)
            return self._save(self._add_shadow(rounded), file_name)
        except Exception:
            return None

    # ═══════════════════════════════════════════════════════════════
    #  排行榜卡片
    # ═══════════════════════════════════════════════════════════════
    def render_leaderboard(self, title: str, entries: List[Tuple[str, str]],
                           subtitle: str = "",
                           file_name: str = "leaderboard.png") -> Optional[str]:
        """渲染排行榜卡片：彩色名次徽章 + 加粗姓名 + 灰色副行，返回 PNG 路径"""
        if not self.available:
            return None
        try:
            from PIL import ImageDraw

            width = 760
            pad = 32
            title_h = 92
            row_h = 64
            title_font = self._font(26, bold=True)
            sub_font = self._font(15)
            name_font = self._font(19, bold=True)
            desc_font = self._font(15)
            rank_font = self._font(15, bold=True)

            img = self._paint_background(
                self._new_image(width, title_h + len(entries) * row_h + pad),
                accent=(247, 183, 49))
            draw = ImageDraw.Draw(img)

            # 标题区
            draw.rectangle([0, 0, width, title_h], fill=(24, 30, 46))
            draw.text((pad + 1, 23), sanitize_text(title), font=title_font, fill=(0, 0, 0))
            draw.text((pad, 22), sanitize_text(title), font=title_font, fill=(255, 224, 130))
            if subtitle:
                draw.text((pad, 58), sanitize_text(subtitle), font=sub_font, fill=(150, 160, 186))
            draw.rectangle([pad, title_h - 8, width - pad, title_h - 7], fill=(70, 82, 116))

            colors = [(247, 183, 49), (165, 177, 194), (227, 160, 110)]
            y = title_h + 8
            for i, (name, desc) in enumerate(entries):
                if i % 2 == 0:
                    draw.rectangle([pad, y, width - pad, y + row_h], fill=(24, 30, 44))
                if i < 3:
                    # 前三名左侧渐变色条
                    draw.rectangle([pad, y + 6, pad + 4, y + row_h - 6], fill=colors[i])
                cx, cy = pad + 19, y + row_h // 2
                if i < 3:
                    draw.ellipse([cx - 15, cy - 15, cx + 15, cy + 15], fill=colors[i])
                    draw.ellipse([cx - 15, cy - 15, cx + 15, cy + 15],
                                 outline=(255, 255, 255), width=1)
                else:
                    draw.ellipse([cx - 15, cy - 15, cx + 15, cy + 15],
                                 outline=(72, 84, 112), width=2)
                draw.text((cx, cy), str(i + 1), font=rank_font, fill=(24, 26, 34) if i < 3 else (255, 255, 255), anchor="mm")
                draw.text((pad + 48, y + 11), sanitize_text(name), font=name_font,
                          fill=(238, 243, 255))
                draw.text((pad + 48, y + 37), sanitize_text(desc), font=desc_font,
                          fill=(150, 160, 186))
                y += row_h

            rounded = self._round_corners(img)
            return self._save(rounded, file_name)
        except Exception:
            return None

    # ═══════════════════════════════════════════════════════════════
    #  趋势折线图
    # ═══════════════════════════════════════════════════════════════
    def render_trend_chart(self, title: str, dates: List[str],
                           favs: List[float], ints: List[float],
                           file_name: str = "trend.png") -> Optional[str]:
        """渲染好感/亲密双线趋势图，返回 PNG 路径；失败返回 None"""
        if not self.available or len(favs) < 2:
            return None
        try:
            from PIL import Image, ImageDraw

            width, height = 760, 460
            pad_l, pad_r, pad_t, pad_b = 56, 56, 96, 44
            cw = width - pad_l - pad_r
            ch = height - pad_t - pad_b

            img = self._paint_background(self._new_image(width, height), accent=(91, 141, 239))
            draw = ImageDraw.Draw(img)
            title_font = self._font(26, bold=True)
            label_font = self._font(16)
            tick_font = self._font(15)

            # 标题
            draw.rectangle([0, 0, width, 84], fill=(24, 30, 46))
            draw.text((pad_l + 1, 27), sanitize_text(title), font=title_font, fill=(0, 0, 0))
            draw.text((pad_l, 26), sanitize_text(title), font=title_font, fill=(255, 224, 130))
            # 图例
            draw.rounded_rectangle([width - 246, 26, width - 232, 42], radius=3, fill=(91, 141, 239))
            draw.text((width - 222, 26), "好感", font=label_font, fill=(226, 232, 244))
            draw.rounded_rectangle([width - 166, 26, width - 152, 42], radius=3, fill=(240, 101, 149))
            draw.text((width - 142, 26), "亲密", font=label_font, fill=(226, 232, 244))

            def y_of_fav(v: float) -> float:
                return pad_t + (100 - v) / 200 * ch

            def y_of_int(v: float) -> float:
                return pad_t + (100 - v) / 100 * ch

            # 网格 + Y 轴刻度（好感：-100~100；亲密：0~100）
            for v in (-100, -50, 0, 50, 100):
                y = y_of_fav(v)
                draw.line([pad_l, y, width - pad_r, y], fill=(42, 50, 72), width=1)
                draw.text((8, y - 9), f"{v}", font=tick_font, fill=(122, 134, 158))
            # 零线强调
            zy = y_of_fav(0)
            draw.line([pad_l, zy, width - pad_r, zy], fill=(70, 82, 112), width=2)
            for v in (25, 75):
                y = y_of_int(v)
                draw.text((width - pad_r + 10, y - 9), f"{v}", font=tick_font,
                          fill=(122, 134, 158))

            n = len(favs)
            step = max(1, cw / max(1, n - 1))
            x_pts = [pad_l + i * step for i in range(n)]

            # X 轴日期标签（间隔显示）
            label_every = max(1, n // 8)
            for i in range(0, n, label_every):
                x = x_pts[i]
                if x > width - pad_r - 30:
                    break
                label = str(dates[i])[-5:]
                draw.text((x - 12, height - pad_b + 8), label, font=tick_font,
                          fill=(122, 134, 158))

            # 面积填充（RGBA 半透明渐变）
            area = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            ad = ImageDraw.Draw(area)
            for color, ys in [((91, 141, 239), [y_of_fav(f) for f in favs]),
                              ((240, 101, 149), [y_of_int(v) for v in ints])]:
                if n >= 2:
                    ad.polygon(
                        [(x_pts[0], pad_t + ch)] + [(x, y) for x, y in zip(x_pts, ys)]
                        + [(x_pts[-1], pad_t + ch)],
                        fill=color + (34,),
                    )
            img.alpha_composite(area)

            # 好感线（蓝）
            pts = [(x, y_of_fav(f)) for x, f in zip(x_pts, favs)]
            if len(pts) > 1:
                draw.line(pts, fill=(91, 141, 239), width=3, joint="curve")
            for x, (_, f) in zip(x_pts, zip(pts, favs)):
                y = y_of_fav(f)
                draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(91, 141, 239))

            # 亲密线（粉）
            pts2 = [(x, y_of_int(v)) for x, v in zip(x_pts, ints)]
            if len(pts2) > 1:
                draw.line(pts2, fill=(240, 101, 149), width=3, joint="curve")
            for x, v in zip(x_pts, ints):
                y = y_of_int(v)
                draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(240, 101, 149))

            # 首尾数值标注
            if n >= 2:
                f0, f1 = favs[0], favs[-1]
                draw.text((pad_l, y_of_fav(f0) - 26), f"{f0:+.1f}", font=label_font,
                          fill=(150, 185, 245))
                draw.text((x_pts[-1] - 40, y_of_fav(f1) - 26), f"{f1:+.1f}",
                          font=label_font, fill=(150, 185, 245))

            rounded = self._round_corners(img)
            return self._save(self._add_shadow(rounded), file_name)
        except Exception:
            return None

    # ═══════════════════════════════════════════════════════════════
    #  内部工具
    # ═══════════════════════════════════════════════════════════════
    def _save(self, img, file_name: str) -> str:
        if not file_name.lower().endswith(".png"):
            file_name += ".png"
        path = self.data_dir / file_name
        img.save(path, "PNG")
        self._cleanup()
        return str(path)

    def _cleanup(self, keep: int = 30):
        """清理过旧的渲染图片，防止无限积累"""
        try:
            files = sorted(
                self.data_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True
            )
            for old in files[keep:]:
                old.unlink()
        except Exception:
            pass
