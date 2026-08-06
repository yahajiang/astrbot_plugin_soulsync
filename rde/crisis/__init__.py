"""RDE 关系危机系统"""
from .crisis_definitions import (
    Choice,
    CrisisEvent,
    CRISIS_EVENTS,
    CRISIS_TYPES,
    CRISIS_TYPE_LABELS,
    get_crisis_event,
    crises_for_stage,
)
from .crisis_state import ActiveCrisis, CrisisStateStore, UserCrisisState
from .crisis_trigger import CrisisTriggerEngine
from .crisis_handler import CrisisHandler, ResolutionResult

__all__ = [
    "Choice", "CrisisEvent", "CRISIS_EVENTS", "CRISIS_TYPES", "CRISIS_TYPE_LABELS",
    "get_crisis_event", "crises_for_stage",
    "ActiveCrisis", "CrisisStateStore", "UserCrisisState",
    "CrisisTriggerEngine", "CrisisHandler", "ResolutionResult",
]
