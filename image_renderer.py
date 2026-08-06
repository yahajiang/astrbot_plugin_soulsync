"""图片卡片渲染器（可选依赖 Pillow）。

- 无 Pillow 或找不到中文字体时 available = False，插件自动降级为文本输出。
- 结构化统计卡片：渐变背景 + 数据胶囊 + 命中条目卡片，参考主插件
  astrbot_plugin_soulsync 的图片输出风格精简而来。
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

# 中文字体候选路径（Windows / macOS / Linux 常见字体）
_BODY_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/simkai.ttf",
    "C:/Windows/Fonts/simfang.ttf",
    "C:/Windows/Fonts/Deng.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
_BOLD_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]

# 字体目录扫描兜底：按文件名关键词匹配中文字体
_FONT_DIRS = [
    "C:/Windows/Fonts",
    "/System/Library/Fonts",
    "/Library/Fonts",
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    "~/.local/share/fonts",
    "~/.fonts",
]
_FONT_KEYWORDS = (
    "msyh", "simhei", "simsun", "simkai", "simfang", "deng",
    "notosanscjk", "notoserifcjk", "sourcehansans", "wqy",
    "droid", "pingfang", "hiragino", "malgun", "nanum",
    "arialunicodems", "yahei", "microsoftyahei",
)
_BOLD_KEYWORDS = ("bd", "bold", "heavy", "semibold")

# Pillow 渲染不支持的 emoji / 装饰字符替换为 □，避免豆腐块
_EMOJI_RE = re.compile(
    r"[\U0001F000-\U0001FAFF\U0001F680-\U0001F6FF\u2600-\u27BF\uFE0F\u200D\u20E3]"
)

WIDTH = 960
PAD = 48

# 配色
BG_TOP = (17, 21, 36)
BG_BOTTOM = (30, 38, 62)
ACCENT = (124, 92, 255)
ACCENT2 = (255, 106, 152)
TITLE_FILL = (247, 249, 255)
BODY_FILL = (225, 229, 244)
DIM_FILL = (152, 162, 196)
HAIRLINE = (52, 62, 94)

MODE_COLORS = {
    "blocked": (255, 105, 105),
    "sanitized": (88, 168, 255),
    "warned": (255, 199, 92),
}
MODE_TINTS = {
    "blocked": (255, 105, 105, 0.14),
    "sanitized": (88, 168, 255, 0.14),
    "warned": (255, 199, 92, 0.14),
}
MODE_LABELS = {"blocked": "拦截", "sanitized": "剥离", "warned": "告警"}


def _find_font(candidates: list[str]) -> Optional[str]:
    for path in candidates:
        if Path(path).exists():
            return path
    return None


def _scan_font_dirs(bold: bool = False) -> Optional[str]:
    """兜底：递归扫描常见字体目录，按文件名关键词找中文字体。"""
    best: Optional[str] = None
    for raw_dir in _FONT_DIRS:
        dir_path = Path(raw_dir).expanduser()
        if not dir_path.is_dir():
            continue
        try:
            for f in dir_path.rglob("*.[tToO][tTfF][cCfF]"):
                name = f.name.lower()
                if not any(k in name for k in _FONT_KEYWORDS):
                    continue
                if bold and not any(k in name for k in _BOLD_KEYWORDS):
                    continue
                return str(f)
        except Exception:
            continue
    return best


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _tint(base: tuple[int, int, int], color: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    return _lerp(base, color, alpha)


def _wrap_text(draw, font, text: str, max_w: int) -> list[str]:
    """按像素宽度折行（保留原有换行）。"""
    lines: list[str] = []
    for raw in str(text).split("\n"):
        cur = ""
        for ch in raw:
            if cur and draw.textlength(cur + ch, font=font) > max_w:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        lines.append(cur)
    return lines


class ImageRenderer:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.available = False
        self.reason = ""  # "pillow" = 缺 Pillow；"font" = 缺中文字体
        self._body_path: Optional[str] = None
        self._bold_path: Optional[str] = None
        try:
            from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        except ImportError:
            self.reason = "pillow"
            return
        body = _find_font(_BODY_FONT_CANDIDATES) or _scan_font_dirs(bold=False)
        if body is None:
            self.reason = "font"
            return
        self._body_path = body
        self._bold_path = _find_font(_BOLD_FONT_CANDIDATES) or _scan_font_dirs(bold=True) or body
        self.available = True

    def render_stats_card(
        self,
        title: str,
        date_str: str,
        counters: dict,
        mode_label: str,
        recent_count: int,
        recent: list[dict],
        fname: str,
    ) -> Optional[str]:
        """渲染注入防护统计卡片 PNG，返回文件路径（失败返回 None）。"""
        from PIL import Image, ImageDraw, ImageFont

        font_title = ImageFont.truetype(self._bold_path, 36)
        font_num = ImageFont.truetype(self._bold_path, 46)
        font_chip = ImageFont.truetype(self._body_path, 21)
        font_body = ImageFont.truetype(self._body_path, 20)
        font_small = ImageFont.truetype(self._body_path, 17)
        font_tiny = ImageFont.truetype(self._body_path, 14)

        entries = [r for r in (recent or []) if isinstance(r, dict)][:5]

        # ── 排版：先计算内容高度 ──
        header_h = 110
        pills_h = 140
        meta_h = 60
        section_h = 46
        entry_h = 112
        footer_h = 64
        height = (
            header_h + pills_h + meta_h + section_h
            + max(1, len(entries)) * entry_h + 24
            + footer_h
        )

        img = Image.new("RGB", (WIDTH, height), BG_TOP)
        draw = ImageDraw.Draw(img)

        # ── 渐变背景 ──
        for y in range(height):
            draw.line((0, y, WIDTH, y), fill=_lerp(BG_TOP, BG_BOTTOM, y / height))

        # ── 装饰：右上角两个半透明圆 ──
        for cx, cy, r, color in [(WIDTH - 120, 20, 140, (124, 92, 255, 26)),
                                 (WIDTH - 40, 90, 90, (255, 106, 152, 20))]:
            overlay = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        # ── 头部：标题 + 日期 ──
        draw.text((PAD, 34), title, font=font_title, fill=TITLE_FILL)
        date_w = draw.textlength(date_str, font=font_chip)
        draw.text((WIDTH - PAD - date_w, 52), date_str, font=font_chip, fill=DIM_FILL)
        # 标题下渐变强调线
        for i in range(4):
            t = i / 3
            draw.line((PAD, header_h - 14 + i, WIDTH - PAD, header_h - 14 + i),
                      fill=_lerp(ACCENT, ACCENT2, t))

        # ── 数据胶囊（数字在上、标签在下，互不重叠）──
        labels = [("blocked", "拦截"), ("sanitized", "剥离"), ("warned", "告警")]
        pill_w = (WIDTH - PAD * 2 - 24 * 2) // 3
        for i, (key, label) in enumerate(labels):
            x0 = PAD + i * (pill_w + 24)
            color = MODE_COLORS.get(key, (255, 255, 255))
            base = _tint(BG_TOP, color, 0.12)
            draw.rounded_rectangle((x0, header_h, x0 + pill_w, header_h + pills_h - 18),
                                   radius=18, fill=base)
            num = str(counters.get(key, 0))
            draw.text((x0 + 26, header_h + 18), num, font=font_num, fill=color)
            draw.text((x0 + 26, header_h + pills_h - 48), label, font=font_chip, fill=DIM_FILL)

        # ── 元信息行：处置模式 + 记录数 ──
        chip_w = draw.textlength(mode_label, font=font_chip) + 44
        chip_base = _tint(BG_TOP, ACCENT, 0.16)
        draw.rounded_rectangle((PAD, header_h + pills_h - 6,
                                PAD + chip_w, header_h + pills_h + 34),
                               radius=13, fill=chip_base)
        draw.text((PAD + 22, header_h + pills_h + 4), mode_label, font=font_chip, fill=(198, 184, 255))
        draw.text((PAD + chip_w + 24, header_h + pills_h + 4),
                  f"最近记录 {recent_count} 条", font=font_chip, fill=DIM_FILL)

        # ── 最近命中 ──
        y = header_h + pills_h + meta_h
        draw.line((PAD, y, WIDTH - PAD, y), fill=HAIRLINE)
        y += 20
        draw.text((PAD, y), "最近命中", font=font_chip, fill=(255, 214, 130))
        y += section_h - 6

        content_w = WIDTH - PAD * 2
        for idx, item in enumerate(entries):
            mode = str(item.get("mode", "blocked"))
            color = MODE_COLORS.get(mode, (255, 255, 255))
            tint = _tint(BG_TOP, color, 0.10)
            x0, x1 = PAD, WIDTH - PAD
            draw.rounded_rectangle((x0, y, x1, y + entry_h - 16), radius=14, fill=tint)

            # 模式徽标
            badge = MODE_LABELS.get(mode, mode)
            bw = draw.textlength(badge, font=font_tiny) + 26
            draw.rounded_rectangle((x0 + 18, y + 18, x0 + 18 + bw, y + 42),
                                   radius=9, fill=color)
            draw.text((x0 + 18 + 13, y + 22), badge, font=font_tiny, fill=(20, 22, 34))

            # 命中规则
            matched = _EMOJI_RE.sub("□", str(item.get("matched", "")))[:46]
            draw.text((x0 + 18 + bw + 16, y + 20), matched, font=font_body, fill=BODY_FILL)

            # 预览（单行，超出省略；与底部小字留足间距）
            preview = _EMOJI_RE.sub("□", str(item.get("preview", "")).replace("\n", " "))[:58]
            pw = draw.textlength(preview, font=font_small)
            while pw > content_w - 36 and len(preview) > 6:
                preview = preview[:-1]
                pw = draw.textlength(preview + "…", font=font_small)
            draw.text((x0 + 18, y + 46), preview[: -1] + "…" if pw > content_w - 36 else preview,
                      font=font_small, fill=DIM_FILL)

            # 底部小字：时间 · 用户
            meta = f"{item.get('time', '')} · {item.get('user_id', '')}"
            draw.text((x0 + 18, y + entry_h - 36), meta, font=font_tiny, fill=(118, 128, 160))

            y += entry_h

        # ── 页脚 ──
        footer = f"心旅知音 · 注入防护盾  |  生成于 {time.strftime('%Y-%m-%d %H:%M')}"
        draw.line((PAD, y + 6, WIDTH - PAD, y + 6), fill=HAIRLINE)
        draw.text((PAD, y + 22), footer, font=font_tiny, fill=(110, 120, 150))

        out = self.data_dir / fname
        img.save(out, "PNG")
        return str(out)

    def render_notify_card(
        self,
        title: str,
        date_str: str,
        rows: list[dict],
        fname: str,
    ) -> Optional[str]:
        """渲染管理员拦截通知卡片 PNG，返回文件路径（失败返回 None）。

        rows: [{time, user_id, mode, matched, content}]，最多展示 5 条。
        """
        from PIL import Image, ImageDraw, ImageFont

        font_title = ImageFont.truetype(self._bold_path, 36)
        font_chip = ImageFont.truetype(self._body_path, 21)
        font_body = ImageFont.truetype(self._body_path, 20)
        font_small = ImageFont.truetype(self._body_path, 17)
        font_tiny = ImageFont.truetype(self._body_path, 14)

        entries = [r for r in (rows or []) if isinstance(r, dict)][:5]

        # 先算每条内容的折行行数，确定总高度
        probe = Image.new("RGB", (8, 8))
        pdraw = ImageDraw.Draw(probe)
        content_w = WIDTH - PAD * 2 - 36
        entry_heights: list[int] = []
        for item in entries:
            text = _EMOJI_RE.sub("□", str(item.get("content", "")).replace("\r", " "))
            wrapped = _wrap_text(pdraw, font_small, text, content_w)
            max_lines = 5
            entry_heights.append(104 + min(len(wrapped), max_lines) * 24)

        header_h = 110
        footer_h = 64
        height = header_h + 26 + sum(entry_heights) + footer_h

        img = Image.new("RGB", (WIDTH, height), BG_TOP)
        draw = ImageDraw.Draw(img)

        # ── 渐变背景 ──
        for y in range(height):
            draw.line((0, y, WIDTH, y), fill=_lerp(BG_TOP, BG_BOTTOM, y / height))

        # ── 装饰：右上角两个半透明圆 ──
        for cx, cy, r, color in [(WIDTH - 120, 20, 140, (124, 92, 255, 26)),
                                 (WIDTH - 40, 90, 90, (255, 106, 152, 20))]:
            overlay = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        # ── 头部 ──
        draw.text((PAD, 34), title, font=font_title, fill=TITLE_FILL)
        date_w = draw.textlength(date_str, font=font_chip)
        draw.text((WIDTH - PAD - date_w, 52), date_str, font=font_chip, fill=DIM_FILL)
        for i in range(4):
            t = i / 3
            draw.line((PAD, header_h - 14 + i, WIDTH - PAD, header_h - 14 + i),
                      fill=_lerp(ACCENT, ACCENT2, t))

        # ── 命中条目卡片 ──
        y = header_h + 26
        for item in entries:
            mode = str(item.get("mode", "blocked"))
            color = MODE_COLORS.get(mode, (255, 255, 255))
            tint = _tint(BG_TOP, color, 0.10)
            h = entry_heights.pop(0)
            x0, x1 = PAD, WIDTH - PAD
            draw.rounded_rectangle((x0, y, x1, y + h), radius=14, fill=tint)

            badge = MODE_LABELS.get(mode, mode)
            bw = draw.textlength(badge, font=font_tiny) + 26
            draw.rounded_rectangle((x0 + 18, y + 16, x0 + 18 + bw, y + 40),
                                   radius=9, fill=color)
            draw.text((x0 + 18 + 13, y + 20), badge, font=font_tiny, fill=(20, 22, 34))

            matched = _EMOJI_RE.sub("□", str(item.get("matched", "")))[:46]
            draw.text((x0 + 18 + bw + 16, y + 18), matched, font=font_body, fill=BODY_FILL)

            meta = f"{item.get('time', '')} · 用户 {item.get('user_id', '')}"
            draw.text((x0 + 18, y + 54), meta, font=font_tiny, fill=(118, 128, 160))

            text = _EMOJI_RE.sub("□", str(item.get("content", "")).replace("\r", " "))
            wrapped = _wrap_text(draw, font_small, text, content_w)
            wrapped = wrapped[:5]
            if len(wrapped) > 0 and len(wrapped) == 5 and draw.textlength(wrapped[-1] + "…", font=font_small) <= content_w:
                wrapped[-1] = wrapped[-1] + "…"
            ty = y + 78
            for ln in wrapped:
                draw.text((x0 + 18, ty), ln, font=font_small, fill=DIM_FILL)
                ty += 24

            y += h + 14

        # ── 页脚 ──
        footer = f"心旅知音 · 注入防护盾  |  生成于 {time.strftime('%Y-%m-%d %H:%M')}"
        draw.line((PAD, y + 6, WIDTH - PAD, y + 6), fill=HAIRLINE)
        draw.text((PAD, y + 22), footer, font=font_tiny, fill=(110, 120, 150))

        out = self.data_dir / fname
        img.save(out, "PNG")
        return str(out)
