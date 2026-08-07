"""SoulSync - 钩子机制（v2.20 前后置钩子注册表）

前置钩子（run_before）：意图分类、纪念日/知识自动提取、环境感知拼接等，
任一钩子返回真值 → 立即阻断后续流程（如静默命令已输出卡片，阻止 LLM 聊天）。
后置钩子（run_after）：回复修饰、主动提示等，全部顺序执行，不阻断。

设计：优先级数字小先执行；同优先级按注册顺序；单钩子异常隔离，
不影响主流程；支持同步/异步回调；可按需 enable/disable。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, List, Optional, Tuple

logger = logging.getLogger("soulsync.hooks")


class HookBus:
    """前后置钩子注册表（线程安全不保证；单事件循环内使用）"""

    def __init__(self):
        self._before: List[Tuple[str, Callable, int, int]] = []  # (name, fn, priority, seq)
        self._after: List[Tuple[str, Callable, int, int]] = []
        self._disabled: set = set()
        self._seq = 0

    # ── 注册 ──
    def register_before(self, name: str, fn: Callable, priority: int = 100,
                        *, enabled: bool = True) -> "HookBus":
        """注册前置钩子。调用 run_before 时若返回真值则阻断后续流程。"""
        self._before.append((name, fn, priority, self._seq))
        self._seq += 1
        if not enabled:
            self._disabled.add(f"before:{name}")
        return self

    def register_after(self, name: str, fn: Callable, priority: int = 100,
                       *, enabled: bool = True) -> "HookBus":
        """注册后置钩子。全部顺序执行，返回值被忽略。"""
        self._after.append((name, fn, priority, self._seq))
        self._seq += 1
        if not enabled:
            self._disabled.add(f"after:{name}")
        return self

    # ── 启停 ──
    def enable(self, name: str, stage: str = "before"):
        self._disabled.discard(f"{stage}:{name}")

    def disable(self, name: str, stage: str = "before"):
        self._disabled.add(f"{stage}:{name}")

    def is_enabled(self, name: str, stage: str = "before") -> bool:
        return f"{stage}:{name}" not in self._disabled

    def count(self, stage: str = "before") -> int:
        items = self._before if stage == "before" else self._after
        return sum(1 for name, _, _, _ in items if self.is_enabled(name, stage))

    # ── 执行 ──
    async def run_before(self, *args, **kwargs) -> bool:
        """依优先级运行全部启用中的前置钩子；任一返回真值 → 立即阻断（返回 True）。"""
        hooks = sorted(self._before, key=lambda h: (h[2], h[3]))
        for name, fn, _, _ in hooks:
            if not self.is_enabled(name, "before"):
                continue
            try:
                result = fn(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
            except Exception as e:
                logger.debug(f"SoulSync 前置钩子 {name} 异常已隔离: {e}", exc_info=True)
                continue
            if result:
                logger.info(f"SoulSync 前置钩子 {name} 阻断流程")
                return True
        return False

    async def run_after(self, *args, **kwargs) -> None:
        """依优先级运行全部启用中的后置钩子；异常隔离，不阻断主流程。"""
        hooks = sorted(self._after, key=lambda h: (h[2], h[3]))
        for name, fn, _, _ in hooks:
            if not self.is_enabled(name, "after"):
                continue
            try:
                result = fn(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.debug(f"SoulSync 后置钩子 {name} 异常已隔离: {e}", exc_info=True)
