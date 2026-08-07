"""SoulSync - 轻量事件总线（v2.20 模块解耦基础设施）

核心层在关键节点发布事件，外围模块通过 subscribe 订阅并异步处理，
核心代码零依赖外围模块，新增功能仅需 发布/订阅，无需修改核心循环。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

EventHandler = Callable[..., Any]


class Events:
    """全局事件名常量（单一来源）"""

    FAVOR_CHANGED = "favor.changed"
    STAGE_ADVANCED = "stage.advanced"
    PERSONA_MANUALLY_SET = "persona.manually_set"
    PERSONA_LOCKED = "persona.locked"
    PERSONA_UNLOCKED = "persona.unlocked"
    ANNIVERSARY_ADDED = "anniversary.added"
    COLD_PENALTY_APPLIED = "cold_penalty.applied"


class EventBus:
    """轻量发布/订阅总线：单个订阅者异常不影响其他订阅者"""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[EventHandler]] = {}

    def subscribe(self, event: str, handler: EventHandler) -> Callable[[], None]:
        """订阅事件，返回取消订阅函数"""
        self._subscribers.setdefault(event, []).append(handler)
        return lambda: self.unsubscribe(event, handler)

    def unsubscribe(self, event: str, handler: EventHandler) -> None:
        try:
            self._subscribers.get(event, []).remove(handler)
        except ValueError:
            pass

    def publish(self, event: str, *args: Any, **kwargs: Any) -> None:
        """发布事件；遍历订阅者副本，异常隔离"""
        for handler in list(self._subscribers.get(event, [])):
            try:
                handler(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    f"SoulSync EventBus 订阅者处理 {event} 异常: {e}", exc_info=True
                )

    def clear(self, event: Optional[str] = None) -> None:
        """清除全部或指定事件的订阅"""
        if event is None:
            self._subscribers.clear()
        else:
            self._subscribers.pop(event, None)

    def count(self, event: Optional[str] = None) -> int:
        if event is None:
            return sum(len(v) for v in self._subscribers.values())
        return len(self._subscribers.get(event, []))


_event_bus = EventBus()


def get_event_bus() -> EventBus:
    """全局单例事件总线"""
    return _event_bus
