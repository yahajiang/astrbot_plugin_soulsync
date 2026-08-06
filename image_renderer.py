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
    "C:/Windows/Fonts/Deng.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
]
_BOLD_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]

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


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _tint(base: tuple[int, int, int], color: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    return _lerp(base, color, alpha)


class ImageRenderer:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.available = False
        self._body_path: Optional[str] = None
        self._bold_path: Optional[str] = None
        try:
            from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        except ImportError:
            return
        body = _find_font(_BODY_FONT_CANDIDATES)
        if body is None:
            return
        self._body_path = body
        self._bold_path = _find_font(_BOLD_FONT_CANDIDATES) or body
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
        pills_h = 118
        meta_h = 64
        section_h = 46
        entry_h = 108
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

        # ── 数据胶囊 ──
        labels = [("blocked", "拦截"), ("sanitized", "剥离"), ("warned", "告警")]
        pill_w = (WIDTH - PAD * 2 - 24 * 2) // 3
        for i, (key, label) in enumerate(labels):
            x0 = PAD + i * (pill_w + 24)
            color = MODE_COLORS.get(key, (255, 255, 255))
            base = _tint(BG_TOP, color, 0.12)
            draw.rounded_rectangle((x0, header_h, x0 + pill_w, header_h + pills_h - 26),
                                   radius=18, fill=base)
            num = str(counters.get(key, 0))
            draw.text((x0 + 26, header_h + 20), num, font=font_num, fill=color)
            draw.text((x0 + 26, header_h + pills_h - 62), label, font=font_chip, fill=DIM_FILL)

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

            # 预览（单行，超出省略）
            preview = _EMOJI_RE.sub("□", str(item.get("preview", "")).replace("\n", " "))[:58]
            pw = draw.textlength(preview, font=font_small)
            while pw > content_w - 36 and len(preview) > 6:
                preview = preview[:-1]
                pw = draw.textlength(preview + "…", font=font_small)
            draw.text((x0 + 18, y + 50), preview[: -1] + "…" if pw > content_w - 36 else preview,
                      font=font_small, fill=DIM_FILL)

            # 底部小字：时间 · 用户
            meta = f"{item.get('time', '')} · {item.get('user_id', '')}"
            draw.text((x0 + 18, y + entry_h - 40), meta, font=font_tiny, fill=(118, 128, 160))

            y += entry_h

        # ── 页脚 ──
        footer = f"心旅知音 · 注入防护盾  |  生成于 {time.strftime('%Y-%m-%d %H:%M')}"
        draw.line((PAD, y + 6, WIDTH - PAD, y + 6), fill=HAIRLINE)
        draw.text((PAD, y + 22), footer, font=font_tiny, fill=(110, 120, 150))

        out = self.data_dir / fname
        img.save(out, "PNG")
        return str(out)
