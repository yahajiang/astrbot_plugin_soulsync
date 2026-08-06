"""SoulSync - 个性化训练：全部数据结构定义"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════
#  1. 人格参数
# ═══════════════════════════════════════════════════════════════
@dataclass
class PersonaParams:
    joy_baseline: float = 0.0           # -20~+20
    sadness_sensitivity: float = 1.0     # 0.5~3.0
    anger_threshold: float = 1.0         # 0.5~3.0
    trust_baseline: float = 0.0          # -15~+15
    expectation_growth: float = 1.0      # 0.5~2.0
    proactive_topic: str = "med"         # low/med/high
    jealousy_threshold: str = "med"      # low/med/high
    conflict_style: str = "balance"      # avoid/confront/balance
    support_style: str = "gentle"        # gentle/direct/practical
    tequila_rate: float = 30.0           # 0~100
    sajiao_rate: float = 20.0            # 0~100
    emotional_express: float = 50.0      # 0~100
    humor_tone: str = "warm"             # warm/ironic/deadpan
    length_preference: str = "medium"    # short/medium/long
    grudge_coefficient: float = 1.0      # 0~3.0
    romantic_memory_weight: float = 1.0  # 0.5~3.0
    forget_speed: float = 1.0            # 0.5~2.0
    milestone_sensitivity: float = 1.0   # 0.5~2.0
    stability: float = 0.0               # 0~100
    total_training_turns: int = 0
    locked: bool = False

    last_updated: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PersonaParams":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid}
        return cls(**filtered)

    def get_emotion_offsets(self) -> Dict[str, float]:
        return {
            "joy": self.joy_baseline,
            "trust": self.trust_baseline,
        }

    def get_sensitivity(self, dimension: str) -> float:
        mapping = {
            "sadness": self.sadness_sensitivity,
            "anger": self.anger_threshold,
            "anticipation": self.expectation_growth,
        }
        return mapping.get(dimension, 1.0)


# 参数变更历史条目
@dataclass
class PersonaHistoryEntry:
    ts: float = 0.0
    param_name: str = ""
    old_value: float = 0.0
    new_value: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PersonaHistoryEntry":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid}
        return cls(**filtered)


# ═══════════════════════════════════════════════════════════════
#  2. 知识库
# ═══════════════════════════════════════════════════════════════
@dataclass
class KnowledgeItem:
    id: str = ""
    category: str = "profile"  # profile/interests/people/promises/experiences/values
    key: str = ""
    value: str = ""
    source: str = "user_direct"  # user_direct/auto_capture/batch_import
    created_ts: float = 0.0
    updated_ts: float = 0.0
    tags: List[str] = field(default_factory=list)
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeItem":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid}
        return cls(**filtered)


@dataclass
class KnowledgeBase:
    profile: Dict[str, str] = field(default_factory=dict)
    interests: Dict[str, str] = field(default_factory=dict)
    people: List[KnowledgeItem] = field(default_factory=list)
    promises: List[KnowledgeItem] = field(default_factory=list)
    experiences: List[KnowledgeItem] = field(default_factory=list)
    values: List[KnowledgeItem] = field(default_factory=list)
    items: List[KnowledgeItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeBase":
        items = [KnowledgeItem.from_dict(i) for i in d.get("items", [])]
        people = [KnowledgeItem.from_dict(i) for i in d.get("people", [])]
        promises = [KnowledgeItem.from_dict(i) for i in d.get("promises", [])]
        experiences = [KnowledgeItem.from_dict(i) for i in d.get("experiences", [])]
        values = [KnowledgeItem.from_dict(i) for i in d.get("values", [])]
        return cls(
            profile=d.get("profile", {}),
            interests=d.get("interests", {}),
            people=people,
            promises=promises,
            experiences=experiences,
            values=values,
            items=items,
        )


# ═══════════════════════════════════════════════════════════════
#  3. 语言风格
# ═══════════════════════════════════════════════════════════════
@dataclass
class LanguageProfile:
    total_turns: int = 0
    avg_length: float = 0.0
    top_particles: List[str] = field(default_factory=list)
    top_expressions: List[str] = field(default_factory=list)
    punctuation: Dict[str, int] = field(default_factory=lambda: {"~": 0, "……": 0, "！": 0})
    formality_score: float = 0.5        # 0~1
    directness_score: float = 0.5       # 0~1
    english_mix_rate: float = 0.0       # 0~1
    preferred_name: str = ""            # 用户对角色的称呼
    preferred_address: str = ""         # 角色对用户的称呼

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "LanguageProfile":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid}
        return cls(**filtered)


@dataclass
class StyleSnapshot:
    name: str = ""
    created_ts: float = 0.0
    profile: Optional[LanguageProfile] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "StyleSnapshot":
        profile = LanguageProfile.from_dict(d["profile"]) if d.get("profile") else None
        return cls(name=d.get("name", ""), created_ts=d.get("created_ts", 0.0), profile=profile)


@dataclass
class StyleState:
    phase: str = "collection"  # collection/adoption/fused
    fusion_ratio: float = 0.0
    profile: Optional[LanguageProfile] = None
    locked: bool = False
    snapshots: List[StyleSnapshot] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "StyleState":
        profile = LanguageProfile.from_dict(d["profile"]) if d.get("profile") else None
        snapshots = [StyleSnapshot.from_dict(s) for s in d.get("snapshots", [])]
        return cls(
            phase=d.get("phase", "collection"),
            fusion_ratio=d.get("fusion_ratio", 0.0),
            profile=profile,
            locked=d.get("locked", False),
            snapshots=snapshots,
        )


# ═══════════════════════════════════════════════════════════════
#  4. 私人记忆
# ═══════════════════════════════════════════════════════════════
@dataclass
class PrivateMemory:
    id: str = ""
    type: str = "text"  # text/image/promise/emotional
    content: str = ""
    date: str = ""
    tags: List[str] = field(default_factory=list)
    mood: str = ""
    importance: int = 5          # 1~10
    access_count: int = 0
    last_accessed: float = 0.0
    sensitive: bool = False
    image_path: str = ""         # 图片记忆专用
    promise_status: str = "active"  # active/fulfilled/expired
    promise_due: str = ""        # 约定专用
    emotion_tags: List[str] = field(default_factory=list)  # 情感记忆专用
    intensity: float = 0.0       # 情感记忆专用

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PrivateMemory":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid}
        return cls(**filtered)


@dataclass
class PrivateMemoryStore:
    text: List[PrivateMemory] = field(default_factory=list)
    images: List[PrivateMemory] = field(default_factory=list)
    promises: List[PrivateMemory] = field(default_factory=list)
    emotional: List[PrivateMemory] = field(default_factory=list)
    starred: List[str] = field(default_factory=list)  # 引用其他记忆的 id

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PrivateMemoryStore":
        def _list_of(cls_type, items):
            return [cls_type.from_dict(i) for i in items] if items else []
        text = _list_of(PrivateMemory, d.get("text", []))
        images = _list_of(PrivateMemory, d.get("images", []))
        promises = _list_of(PrivateMemory, d.get("promises", []))
        emotional = _list_of(PrivateMemory, d.get("emotional", []))
        starred = d.get("starred", [])
        return cls(text=text, images=images, promises=promises, emotional=emotional, starred=starred)


# ═══════════════════════════════════════════════════════════════
#  5. 记忆审计日志
# ═══════════════════════════════════════════════════════════════
@dataclass
class MemoryAuditEntry:
    memory_id: str = ""
    access_time: float = 0.0
    trigger_scene: str = ""  # peak/valley/time/topic/proactive
    conversation_context: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryAuditEntry":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid}
        return cls(**filtered)