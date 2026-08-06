"""图片卡片渲染器（可选依赖 Pillow）。

- 无 Pillow 或找不到中文字体时 available = False，插件自动降级为文本输出。
- 参考主插件 astrbot_plugin_soulsync 的 ImageRenderer 精简而来，仅保留卡片渲染。
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

# 中文字体候选路径（Windows / macOS / Linux 常见字体）
_FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/Deng.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
]

# Pillow 渲染不支持的 emoji / 装饰字符替换为 □，避免豆腐块
_EMOJI_RE = re.compile(
    r"[\U0001F000-\U0001FAFF\U0001F680-\U0001F6FF\u2600-\u27BF\uFE0F\u200D\u20E3]"
)

_BG = (28, 32, 48)          # 卡片背景
_HEADER = (108, 92, 231)    # 标题条
_LINE = (60, 66, 92)        # 分隔线
_TEXT = (232, 234, 244)     # 正文
_DIM = (158, 164, 190)      # 次要文本


def _font_path() -> Optional[str]:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return None


class ImageRenderer:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.available = False
        self._font_path = None
        try:
            from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        except ImportError:
            return
        path = _font_path()
        if path is None:
            return
        self._font_path = path
        self.available = True

    def render_card(self, title: str, lines: list[str], fname: str) -> Optional[str]:
        """把标题 + 文本行渲染为深色圆角卡片 PNG，返回文件路径。"""
        from PIL import Image, ImageDraw, ImageFont

        font_title = ImageFont.truetype(self._font_path, 34)
        font_body = ImageFont.truetype(self._font_path, 22)
        font_small = ImageFont.truetype(self._font_path, 19)

        width = 920
        padding = 44
        title_h = 78
        row_h = 40
        body = [_EMOJI_RE.sub("□", ln) for ln in (lines or [])]
        body = [ln[:46] for ln in body]
        height = title_h + max(1, len(body)) * row_h + padding * 2

        img = Image.new("RGB", (width, height), _BG)
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=18, fill=_BG)
        draw.rectangle((0, 0, width - 1, title_h), fill=_HEADER)
        draw.rectangle((0, title_h - 4, width - 1, title_h), fill=(90, 76, 200))

        draw.text((padding, 24), _EMOJI_RE.sub("□", title), font=font_title, fill=(255, 255, 255))

        y = title_h + padding
        for ln in body:
            if ln.startswith("🛡"):
                fill = (255, 255, 255)
            elif ln.startswith("最近命中"):
                fill = (255, 214, 102)
            else:
                fill = _TEXT
            draw.text((padding, y), ln, font=font_body if len(ln) < 40 else font_small, fill=fill)
            y += row_h

        draw.text((padding, height - padding), f"生成于 {time.strftime('%Y-%m-%d %H:%M')}", font=font_small, fill=_DIM)
        out = self.data_dir / fname
        img.save(out, "PNG")
        return str(out)
