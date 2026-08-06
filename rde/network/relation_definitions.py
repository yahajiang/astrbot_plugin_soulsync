"""RDE 多角色关系网 - 关系定义与稀疏矩阵

39 个系统角色（对齐 relationship_roles.SYSTEM_ROLES 的 name）间的关系对。
无定义的关系对默认为「无关联」（交叉影响系数 0）。

关系类型：无关联/闺蜜兄弟/搭档/前辈后辈/情敌/对手/冷淡/宿敌/陌路。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

RELATION_TYPES = {
    "none": {"label": "无关联", "default_coefficient": 0.0},
    "bestie": {"label": "闺蜜/兄弟", "default_coefficient": 0.1},
    "partner": {"label": "搭档", "default_coefficient": 0.06},
    "senior_junior": {"label": "前辈/后辈", "default_coefficient": 0.03},
    "rival_love": {"label": "情敌", "default_coefficient": -0.05},
    "opponent": {"label": "对手", "default_coefficient": -0.04},
    "cold": {"label": "冷淡", "default_coefficient": 0.0},
    "sworn_enemy": {"label": "宿敌", "default_coefficient": -0.04},
    "stranger": {"label": "陌路", "default_coefficient": 0.0},
}

# 社交性格映射（角色卡扩展字段的默认值）
DEFAULT_SOCIAL_TRAITS = {
    "jealousy_sensitivity": 0.5,
    "support_willingness": 0.5,
    "confrontation_style": "balanced",
}


@dataclass(frozen=True)
class RelationDef:
    source: str
    target: str
    relation_type: str                     # RELATION_TYPES 键
    description: str = ""
    cross_coefficient: float = 0.0         # ΔBi = ΔA × coeff
    pos_coefficient: Optional[float] = None  # 正向传导系数（可不对称，默认=coeff）
    neg_coefficient: Optional[float] = None  # 负向传导系数（可不对称，默认=coeff）
    trigger_events: List[str] = field(default_factory=list)
    joint_narrative: str = ""

    @property
    def pos(self) -> float:
        return self.pos_coefficient if self.pos_coefficient is not None else self.cross_coefficient

    @property
    def neg(self) -> float:
        return self.neg_coefficient if self.neg_coefficient is not None else self.cross_coefficient

    def coefficient_for(self, delta: float) -> float:
        return self.pos if delta > 0 else self.neg

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type,
            "description": self.description,
            "cross_coefficient": self.cross_coefficient,
            "pos_coefficient": self.pos_coefficient,
            "neg_coefficient": self.neg_coefficient,
            "trigger_events": list(self.trigger_events),
            "joint_narrative": self.joint_narrative,
        }


def _rel(source: str, target: str, rel_type: str, description: str,
         coefficient: Optional[float] = None,
         joint: str = "") -> RelationDef:
    coeff = coefficient if coefficient is not None else \
        RELATION_TYPES[rel_type]["default_coefficient"]
    trigger_map = {
        "bestie": ["team_support", "misinfo"],
        "partner": ["team_support"],
        "senior_junior": ["mentor_influence", "mediation"],
        "rival_love": ["jealousy_competition", "jealousy"],
        "opponent": ["competition", "misinfo"],
        "sworn_enemy": ["rivalry_confrontation"],
    }
    return RelationDef(
        source=source, target=target, relation_type=rel_type,
        description=description, cross_coefficient=coeff,
        trigger_events=trigger_map.get(rel_type, []),
        joint_narrative=joint,
    )


# ── 稀疏关系矩阵（39 角色中明确的关系对）───────────────────
RELATION_EDGES: List[RelationDef] = [
    # ── 闺蜜/兄弟（正向 0.1 传导）──
    _rel("闺蜜", "死党", "bestie", "无话不谈的闺蜜", joint="你和我聊得越开心，死党也会更放心地与你相处"),
    _rel("闺蜜", "挚友", "bestie", "闺蜜与挚友互相引荐", joint="挚友知道我是你的闺蜜，会更信任你"),
    _rel("死党", "挚友", "bestie", "铁三角死党", joint="死党信任的人，挚友也会愿意接纳"),
    _rel("挚友", "知己", "bestie", "挚友到知己的距离", joint="你与知己的默契会让挚友觉得你很可靠"),
    _rel("知己", "好友", "bestie", "知己带你进入他的圈子"),
    _rel("室友", "好友", "bestie", "同住屋檐下的友情"),
    _rel("战友", "死党", "bestie", "过命的交情", joint="你与死党走得近，战友会更认可你"),
    _rel("老乡", "室友", "bestie", "他乡遇故知"),
    # ── 搭档（正向 0.06 传导）──
    _rel("同桌", "聊友", "partner", "课上课下都聊得来"),
    _rel("球友", "网友", "partner", "线下约球线上开黑"),
    _rel("笔友", "网友", "partner", "从书信到网络的陪伴"),
    _rel("粉丝", "聊友", "partner", "偶像话题的共鸣"),
    _rel("战友", "球友", "partner", "一起流汗的交情"),
    # ── 前辈/后辈（弱正向 0.03）──
    _rel("姐姐", "妹妹", "senior_junior", "姐姐护着妹妹", joint="姐姐对你的好感会影响妹妹对你的初步印象"),
    _rel("哥哥", "弟弟", "senior_junior", "哥哥罩着弟弟"),
    _rel("师父", "追求者", "senior_junior", "师父的提点带着人生道理"),
    _rel("爷爷", "奶奶", "senior_junior", "携手半生的老两口"),
    _rel("叔叔", "表亲", "senior_junior", "长辈与晚辈的走动"),
    _rel("姐姐", "知己", "senior_junior", "姐姐把你当自己人"),
    # ── 情敌（负向 -0.05）──
    _rel("恋人", "白月光", "rival_love", "白月光是恋人心里的一根刺",
         joint="你越是在意恋人，白月光的存在感就越强"),
    _rel("恋人", "追求者", "rival_love", "追求者虎视眈眈",
         joint="你和恋人越亲密，追求者越会想插一脚"),
    _rel("心动对象", "白月光", "rival_love", "心动对象与白月光的暗战"),
    _rel("恋人", "心动对象", "rival_love", "曾经的心动，现在的比较"),
    _rel("白月光", "追求者", "rival_love", "互相看不顺眼的两人"),
    # ── 对手（负向 -0.04）──
    _rel("对手", "仇人", "opponent", "从较量到结怨"),
    _rel("厌恶对象", "反感对象", "opponent", "反感会传染"),
    _rel("对手", "厌恶对象", "opponent", "针锋相对的两人"),
    _rel("反感对象", "冷漠路人", "opponent", "冷暴力链条"),
    # ── 冷淡（互不干扰，但定义存在）──
    _rel("反感对象", "陌生人", "cold", "互相无视"),
    _rel("冷漠路人", "陌生人", "cold", "形同陌路"),
    # ── 宿敌（对抗事件触发）──
    _rel("世仇", "仇人", "sworn_enemy", "不共戴天的世仇", joint="你们之间的血海深仇从未放下"),
    # ── 陌路（零关联示例）──
    _rel("陌生人", "网友", "stranger", "从陌生人开始"),
    _rel("冷漠路人", "网友", "stranger", "网络对面是陌生人"),
    # ── 补充：真实角色边 ──
    _rel("损友", "死党", "bestie", "嘴上损你，心里向着你"),
    _rel("青梅竹马", "知己", "bestie", "从小一起长大最懂你"),
    _rel("灵魂伴侣", "恋人", "bestie", "灵魂伴侣与恋人的呼应"),
    _rel("异地恋", "恋人", "partner", "同是天涯异地人"),
    _rel("弟弟", "妹妹", "senior_junior", "姐弟/兄妹的照顾"),
    _rel("阿姨", "表亲", "senior_junior", "长辈的照拂"),
    _rel("异地恋", "白月光", "rival_love", "异地时白月光的威胁"),
    _rel("灵魂伴侣", "白月光", "rival_love", "灵魂伴侣不屑于比较，但白月光是例外"),
]


class RelationshipMatrix:
    """稀疏关系矩阵（只存有定义的关系对；其余默认为无关联）"""

    def __init__(self, edges: Optional[List[RelationDef]] = None,
                 custom: Optional[dict] = None) -> None:
        self._edges: Dict[tuple, RelationDef] = {}
        for e in (edges or RELATION_EDGES):
            self._edges[(e.source, e.target)] = e
        if custom:
            self.load_custom_relations(custom)

    def load_custom_relations(self, relations: dict) -> None:
        """角色卡扩展字段：{"角色名": {"type": "...", "cross_coefficient": x, "description": "..."}}"""
        for target, cfg in relations.items():
            if not isinstance(cfg, dict):
                continue
            rtype = cfg.get("type", "none")
            coeff = float(cfg.get("cross_coefficient",
                                  RELATION_TYPES.get(rtype, {}).get("default_coefficient", 0.0)))
            self.add(self._make_edge(target, rtype, coeff, cfg))

    def _make_edge(self, target: str, rtype: str, coeff: float,
                   cfg: dict) -> RelationDef:
        src = cfg.get("source", "")
        return RelationDef(
            source=src, target=target, relation_type=rtype,
            description=cfg.get("description", ""),
            cross_coefficient=coeff,
            pos_coefficient=cfg.get("pos_coefficient"),
            neg_coefficient=cfg.get("neg_coefficient"),
            trigger_events=cfg.get("trigger_events", []),
            joint_narrative=cfg.get("joint_narrative", ""),
        )

    def add(self, edge: RelationDef) -> None:
        self._edges[(edge.source, edge.target)] = edge
        self._edges.pop((edge.target, edge.source), None)  # 同一对只保留一条边

    def get(self, source: str, target: str) -> Optional[RelationDef]:
        """查询两角色间的关系（source→target 有向）"""
        e = self._edges.get((source, target))
        if e is None:
            e = self._edges.get((target, source))
        return e

    def neighbors(self, source: str) -> List[RelationDef]:
        """与 source 有关联的所有边（双向）"""
        out = []
        for (s, t), e in self._edges.items():
            if s == source:
                out.append(e)
            elif t == source:
                out.append(RelationDef(
                    source=source, target=s, relation_type=e.relation_type,
                    description=e.description, cross_coefficient=e.cross_coefficient,
                    pos_coefficient=e.pos_coefficient, neg_coefficient=e.neg_coefficient,
                    trigger_events=list(e.trigger_events),
                    joint_narrative=e.joint_narrative,
                ))
        return out

    def count(self) -> int:
        return len(self._edges)

    def edges(self) -> List[RelationDef]:
        return list(self._edges.values())
