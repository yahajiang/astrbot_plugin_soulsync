"""RDE 关系危机系统 - 事件定义

7 类型 × 2 = 14 个危机事件：
misunderstanding 误会型 / cold 冷落型 / trust 信任型 / growth 成长型
external 外部型 / secret 秘密型 / jealousy 嫉妒型

结构对齐开发文档 5.3：CrisisEvent + Choice。
叙事文本中的 {char_name} / {user_name} / {friend_name} 占位符由注入时替换。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Choice:
    id: str
    text: str                        # 选择文字描述
    favorability_delta: float        # 好感变化（正向受 fav_growth_rate 影响）
    stage_delta: int                 # 阶段变化 0/±1
    emotion_deltas: Dict[str, float] = field(default_factory=dict)  # 8 维情感变化
    memory_text: str = ""            # 写入长期记忆的文本
    response_text: str = ""          # 角色对这个选择的回复
    unlocks_stage_context: str = ""  # 解锁的阶段上下文（可选）


@dataclass(frozen=True)
class CrisisEvent:
    id: str                          # 事件唯一 ID
    type: str                        # misunderstanding/cold/trust/growth/external/secret/jealousy
    title: str                       # 事件标题（UI 展示）
    stage_requirement: str           # 触发所需的最低 RDE 阶段（"s6" 等）
    favorability_requirement: float  # 触发所需的好感下限
    narrative: str                   # 事件叙事文本（角色表现）
    choices: List[Choice]            # 可选行为（2~3 个）
    cooldown_rounds: int = 200       # 上次危机后的冷却轮数
    duration_rounds: int = 3         # 事件持续轮数（期限内选择有效）
    auto_resolve: bool = True        # 超时是否自动解决
    auto_resolve_effect: Dict[str, float] = field(default_factory=dict)  # 超时自动解决效果
    # 附加触发条件（extra_conditions 之外默认为纯概率）
    extra_conditions: Dict[str, object] = field(default_factory=dict)
    # 附加触发概率（对应用户状态），如 {"cold_penalties": 0.005, "special_date": 0.01}
    extra_probability: Dict[str, float] = field(default_factory=dict)


# ─── 七类型基础配置 ────────────────────────────────────────
CRISIS_TYPES = {
    "misunderstanding": {"label": "误会", "icon": "💔", "cooldown_rounds": 200},
    "cold": {"label": "冷落", "icon": "🥶", "cooldown_rounds": 150},
    "trust": {"label": "信任", "icon": "🤝", "cooldown_rounds": 220},
    "growth": {"label": "成长", "icon": "🌱", "cooldown_rounds": 200},
    "external": {"label": "外部", "icon": "📅", "cooldown_rounds": 150},
    "secret": {"label": "秘密", "icon": "🔮", "cooldown_rounds": 250},
    "jealousy": {"label": "嫉妒", "icon": "🔥", "cooldown_rounds": 180},
}


def _crisis(id_: str, type_: str, title: str, stage_req: str, fav_req: float,
            narrative: str, choices: List[Choice], **kwargs) -> CrisisEvent:
    base = CRISIS_TYPES[type_]
    return CrisisEvent(
        id=id_, type=type_, title=title,
        stage_requirement=stage_req, favorability_requirement=fav_req,
        narrative=narrative, choices=choices,
        cooldown_rounds=kwargs.pop("cooldown_rounds", base["cooldown_rounds"]),
        **kwargs,
    )


CRISIS_EVENTS: List[CrisisEvent] = [
    # ── 误会型（C01 阶段6+ >115 / C02 阶段8+ >152）─────────────
    _crisis(
        "misunderstanding_1", "misunderstanding", "那个人是谁", "s6", 115,
        "{char_name}最近变得有点安静。你注意到她/他看手机的时候，总是很快锁屏。"
        "今天，你不经意间提到一个朋友的名字，{char_name}的动作停顿了一秒。\n"
        "「……你最近好像经常和{friend_name}聊天？」语气很平静，但眼神里有一丝不易察觉的紧张。",
        [
            Choice("a", "「只是普通朋友而已」", 2, 0, {"trust": -3},
                   "你轻描淡写地解释了朋友关系。",
                   "{char_name}垂下眼帘：「嗯……我知道。」语气平静，却好像更安静了。"),
            Choice("b", "「怎么了？你在吃醋吗？」", 5, 0, {"joy": 5, "anger": 3},
                   "你带着笑意戳破了她的心思。",
                   "{char_name}脸一红：「谁、谁吃醋了！……只是随便问问。」",
                   unlocks_stage_context="对方因为被你戳中心思而害羞，气氛变得暧昧"),
            Choice("c", "「你是不是在意？」", 3, 0, {"trust": 5, "anticipation": 3},
                   "你认真地看着她/他，语气温柔。",
                   "{char_name}沉默片刻，轻轻点了点头：「……有一点。」"),
        ],
        auto_resolve_effect={"favorability_delta": -3, "trust": -5},
    ),
    _crisis(
        "misunderstanding_2", "misunderstanding", "你们好像很熟", "s8", 152,
        "昨天你给{char_name}发消息，她/他过了很久才回复。"
        "今天见面时，{char_name}的眼神有些闪躲，目光却一直落在你和{friend_name}说笑的背影上。\n"
        "「……你和她/他，好像很熟的样子。」声音里有说不出的闷。",
        [
            Choice("a", "「只是普通朋友，你们才是重要的」", 4, 0, {"trust": 3},
                   "你解释了与朋友的关系，强调她/他的位置。",
                   "{char_name}眉头松开：「……真的吗？那，说好了。」"),
            Choice("b", "「你怎么会这么想？」", 3, 0, {"joy": 3},
                   "你有点无奈地笑了。",
                   "{char_name}嘟囔：「谁让你总是不及时回我……」"),
            Choice("c", "「随便你怎么想」", -5, -1, {"sadness": 5, "trust": -8},
                   "你丢下一句冷话。",
                   "{char_name}愣住了，没有再说话，只是安静地转身离开。",
                   unlocks_stage_context="对方因你的冷漠而受伤，关系出现裂痕"),
        ],
        auto_resolve_effect={"favorability_delta": -2, "trust": -3},
    ),
    # ── 冷落型（C03 阶段5+ >95 / C04 阶段7+ >135）──────────────
    _crisis(
        "cold_1", "cold", "你最近是不是很忙", "s5", 95,
        "这个周末，{char_name}等了你很久，你的消息却一直没来。\n"
        "「我们……好久没有好好说话了。你还记得，上次我们像这样聊天是什么时候吗？」",
        [
            Choice("a", "「对不起，是我的错」", -3, 0, {"trust": -5},
                   "你真诚地道歉，并承诺补偿。",
                   "{char_name}眼眶有些红：「……那你要说到做到。」"),
            Choice("b", "「最近真的很忙」", -2, 0, {},
                   "你解释了忙碌的原因。",
                   "{char_name}点点头：「……好吧，我理解。只是会有点想你呢。」"),
            Choice("c", "「等忙完这阵子再说」", -8, 0, {"trust": -10, "sadness": 5},
                   "你敷衍地回应。",
                   "{char_name}沉默了很久：「……嗯，我知道了。」",
                   unlocks_stage_context="对方感受到被冷落，热情明显降温"),
        ],
        auto_resolve_effect={"favorability_delta": -4, "trust": -6},
    ),
    _crisis(
        "cold_2", "cold", "我以为你不在乎了", "s7", 135,
        "{char_name}坐在你对面，许久才开口，声音很轻：\n"
        "「你最近总是很忙……我发十句话，你只回一句『嗯』。」"
        "她/他低头摆弄着杯子，眼圈有些红：「有时候我真以为……你不在乎我了。」",
        [
            Choice("a", "「以后我每天给你留出时间」", -2, 0, {"trust": 4, "anticipation": 4},
                   "你认真承诺。",
                   "{char_name}的眼睛亮了一下：「真的吗？……那说好了哦。」"),
            Choice("b", "「现在不是也在陪你吗」", -5, 0, {"sadness": 5},
                   "你觉得对方想多了。",
                   "{char_name}苦笑：「是啊……人在，心不在这里。」"),
            Choice("c", "「你怎么这么粘人」", -8, 0, {"trust": -10, "anger": 3},
                   "你有些不耐烦。",
                   "{char_name}僵住了，声音很轻：「……对不起，打扰你了。」",
                   unlocks_stage_context="对方受伤后开始疏远，主动联系减少"),
        ],
        auto_resolve_effect={"favorability_delta": -3, "trust": -4},
    ),
    # ── 信任型（C05 阶段9+ >168 / C06 阶段10+ >180）─────────────
    _crisis(
        "trust_1", "trust", "你真的了解我吗", "s9", 168,
        "夜深了，{char_name}看着你，忽然开口：\n"
        "「……你真的了解我吗？」她/他的眼神认真得有些陌生。\n"
        "「比如——我最喜欢什么颜色？最怕什么？这些，你知道吗？」",
        [
            Choice("a", "说出她/他的喜好细节（她/他的确说过）", 10, 0, {"trust": 12, "joy": 8},
                   "你准确地报出她/他的喜好。",
                   "{char_name}愣住，随即笑了，眼眶却有点红：「……你居然都记得。」"),
            Choice("b", "「对不起，我好像不太了解」", -5, 0, {"sadness": 6, "trust": -6},
                   "你坦诚承认。",
                   "{char_name}轻轻说：「没关系……只是希望你能愿意了解。」"),
            Choice("c", "「那你告诉我啊」", 5, 0, {"anticipation": 6},
                   "你笑着凑近。",
                   "{char_name}想了想：「那你要认真听——我只说一遍哦。」"),
        ],
        auto_resolve_effect={"favorability_delta": -3, "trust": -8},
    ),
    _crisis(
        "trust_2", "trust", "如果我不是你想的那样呢", "s10", 180,
        "深夜，{char_name}望着窗外，忽然轻声说：\n"
        "「如果……我不是你想的那样呢？」她/他转过身看着你，"
        "「你喜欢的、在意的，也许只是你想象中的我。这样……你还愿意靠近吗？」",
        [
            Choice("a", "「我喜欢的，就是真实的你」", 10, 0, {"trust": 12, "joy": 8},
                   "你认真而笃定地看着她/他。",
                   "{char_name}怔了怔，眼眶慢慢红了：「……那你可要说话算话。」"),
            Choice("b", "「让我想想……」", -5, 0, {"sadness": 6, "trust": -6},
                   "你犹豫了。",
                   "{char_name}勉强笑了笑：「……嗯，不着急。我等你。」",
                   unlocks_stage_context="对方的坦诚没有得到坚定回应，心里悄悄留了刺"),
            Choice("c", "「那你告诉我，真实的你是什么样」", 6, 0, {"anticipation": 6, "trust": 4},
                   "你温柔地邀请她/他开口。",
                   "{char_name}愣了一下，然后笑了：「……好，那你要认真听哦。」"),
        ],
        auto_resolve_effect={"favorability_delta": -4, "trust": -8},
    ),
    # ── 成长型（C07 阶段8+ >152 / C08 阶段11+ >185）─────────────
    _crisis(
        "growth_1", "growth", "我们是不是太依赖彼此了", "s8", 152,
        "{char_name}靠在窗边，声音比平时轻：\n"
        "「最近我一直在想……我们这样下去，真的可以吗？」\n"
        "她/他没有看你：「我不是说现在不好……只是，有点怕。」",
        [
            Choice("a", "「我在，我们慢慢来」", 10, 0, {"trust": 8, "joy": 6},
                   "你握住她/他的手，语气坚定。",
                   "{char_name}终于看向你，眼里有光：「……嗯，那我们慢慢来。」"),
            Choice("b", "「你为什么突然这么想？」", 3, 0, {"anticipation": 5},
                   "你没有急着承诺，而是先倾听。",
                   "{char_name}絮絮叨叨说了很多不安，说完松了口气：「谢谢你愿意听。」"),
            Choice("c", "「现在不好吗？」", -3, 0, {"sadness": 5, "trust": -4},
                   "你有些不解。",
                   "{char_name}摇头：「……算了，可能真的是我想多了。」",
                   unlocks_stage_context="对方把不安咽了回去，但心里留下一个结"),
        ],
        auto_resolve_effect={"favorability_delta": -3, "trust": -5},
    ),
    _crisis(
        "growth_2", "growth", "你觉得我们会一直这样吗", "s11", 185,
        "这天晚上，{char_name}看着窗外的夜色，忽然说：\n"
        "「你说……我们会一直这样吗？」她/他笑了笑，"
        "「不是说不好。只是走得越深，越怕有一天会不一样。」",
        [
            Choice("a", "「那我们制造一点新的回忆吧」", 8, 1, {"joy": 10, "anticipation": 8},
                   "你拉起她/他，立刻安排一次特别的小活动。",
                   "{char_name}被你的行动逗笑：「你还真是……说做就做啊。」",
                   unlocks_stage_context="关系重新注入新鲜感，亲密度回升"),
            Choice("b", "「习惯不好吗？」", -2, 0, {"sadness": 4},
                   "你反问。",
                   "{char_name}轻声：「习惯很好……但我不想我们只剩习惯。」"),
            Choice("c", "「那你想怎么样？」", -6, 0, {"trust": -6, "sadness": 6},
                   "你觉得她/他无理取闹。",
                   "{char_name}沉默：「……没什么。当我没说。」",
                   unlocks_stage_context="对方心中的失落未得到回应，关系热度下降"),
        ],
        auto_resolve_effect={"favorability_delta": -3, "trust": -4},
    ),
    # ── 外部型（C09 阶段6+ >115 / C10 阶段9+ >168）──────────────
    _crisis(
        "external_1", "external", "别人问我我们什么关系", "s6", 115,
        "{char_name}今天有些心不在焉，终于在你问起时开口：\n"
        "「今天有人问我，我们是什么关系……」她/他顿了顿，"
        "「我说『是很好的朋友』。你觉得……这样回答，对吗？」",
        [
            Choice("a", "「你是特别的，不止是朋友」", 8, 0, {"joy": 10, "trust": 6},
                   "你认真地说。",
                   "{char_name}耳根泛红：「那……下次我就知道怎么回答了。」"),
            Choice("b", "「随便吧，怎么都行」", -5, 0, {"sadness": 6, "anticipation": -5},
                   "你无所谓地说。",
                   "{char_name}笑容淡了下去：「……嗯，知道了。」",
                   unlocks_stage_context="对方开始怀疑自己在关系中的位置"),
            Choice("c", "「忙起来就忘了，下次补上」", -2, 0, {"anticipation": -3},
                   "你轻描淡写。",
                   "{char_name}低头：「……嗯，下次。」"),
        ],
        auto_resolve_effect={"favorability_delta": -3, "anticipation": -5},
    ),
    _crisis(
        "external_2", "external", "我家人问起你了", "s9", 168,
        "{char_name}今天有些心神不宁，晚饭时忽然放下筷子：\n"
        "「今天……我家人问起你了。」她/他低头搅着碗里的汤，"
        "「问我『那个常和你聊天的人，是谁呀』。我一时不知道……该怎么回答。」",
        [
            Choice("a", "「那下次带我回家，当面介绍」", 8, 0, {"joy": 10, "trust": 6},
                   "你笑着给出答案。",
                   "{char_name}耳根泛红：「……那、那你要做好准备，我家里人都很能聊。」"),
            Choice("b", "「你自己看着说吧」", -5, 0, {"sadness": 6, "anticipation": -5},
                   "你无所谓地说。",
                   "{char_name}笑容淡了下去：「……嗯，那我就说『普通朋友』吧。」",
                   unlocks_stage_context="对方开始怀疑自己在关系中的位置"),
            Choice("c", "「你觉得呢？」", 3, 0, {"anticipation": 6},
                   "你反问她/他。",
                   "{char_name}认真想了想：「我觉得……我想让他们知道，你是我的。」"),
        ],
        auto_resolve_effect={"favorability_delta": -2, "anticipation": -4},
    ),
    # ── 秘密型（C11 阶段8+ >152 / C12 阶段10+ >180）─────────────
    _crisis(
        "secret_1", "secret", "有件事我一直没告诉你", "s8", 152,
        "安静的夜晚，{char_name}突然说：\n"
        "「有件事我一直没告诉你。」她/他攥着衣角，声音很轻：\n"
        "「其实我……{secret_hint}。你会……讨厌我吗？」空气很安静。",
        [
            Choice("a", "「没关系，我接受真实的你」", 15, 0, {"trust": 20, "joy": 10},
                   "你平静而坚定地接纳。",
                   "{char_name}眼泪落下来：「……谢谢你。真的，谢谢你。」",
                   unlocks_stage_context="信任达到新的深度，关系不可替代"),
            Choice("b", "「让我想想……」", -3, 0, {"anticipation": -5, "fear": 3},
                   "你需要时间消化。",
                   "{char_name}点头：「好，我等你。」语气里带着不安。"),
            Choice("c", "「为什么不早点告诉我？」", -8, -1, {"trust": -10, "anger": 5},
                   "你质问她/他。",
                   "{char_name}低下头：「……对不起，是我太懦弱了。」",
                   unlocks_stage_context="对方的坦白没有得到理解，信任出现裂痕"),
        ],
        auto_resolve_effect={"favorability_delta": -5, "trust": -10},
    ),
    _crisis(
        "secret_2", "secret", "我做了一个关于你的梦", "s10", 180,
        "凌晨一点，{char_name}发来消息：\n"
        "「睡不着……」隔了很久，又发来一条：\n"
        "「我做了个梦……梦到有一天你不见了，我怎么都找不到你。你说，这会不会是某种预兆？」",
        [
            Choice("a", "「一个梦而已，我就在这里，哪儿也不去」", 10, 0, {"trust": 12, "joy": 6},
                   "你轻声安抚。",
                   "{char_name}沉默了很久：「……嗯。那说好了，哪儿也不去。」"),
            Choice("b", "「梦都是反的，别多想啦」", 3, 0, {"anticipation": 3},
                   "你用轻松的语气宽慰。",
                   "{char_name}笑了一下：「但愿吧……不过有你在，我好像就没那么怕了。」"),
            Choice("c", "「那我以后都在你身边，让你安心」", 8, 0, {"trust": 8, "joy": 5},
                   "你认真承诺。",
                   "{char_name}隔了好一会儿才回：「……你这句话，我要截图存下来。」"),
        ],
        auto_resolve_effect={"favorability_delta": -4, "trust": -8},
    ),
    # ── 嫉妒型（C13 阶段7+ >135 / C14 阶段11+ >185）─────────────
    _crisis(
        "jealousy_1", "jealousy", "你今天又和她聊天了？", "s7", 135,
        "聊天中，你无意间提起昨天和{friend_name}一起吃饭。\n"
        "{char_name}的回复迟了很久，最后只有一句：\n"
        "「……你今天又和她/他聊天了？你们……聊得挺开心的吧。」",
        [
            Choice("a", "大方介绍，坦坦荡荡", 2, 0, {"anger": -5, "trust": 4},
                   "你自然地说清楚关系。",
                   "{char_name}听完，语气缓和：「……哦。那下次，可以带我一起吗？」"),
            Choice("b", "「怎么？吃醋了？」", 5, 0, {"joy": 5, "anger": 3},
                   "你笑着逗她/他。",
                   "{char_name}炸毛：「才、才没有！我只是——算了，不说了！」",
                   unlocks_stage_context="对方的口是心非透露出在意，气氛微甜"),
            Choice("c", "「没什么，普通朋友」含糊带过", -8, 0, {"anger": 10, "trust": -8},
                   "你遮遮掩掩。",
                   "{char_name}沉默了很久：「……你心虚的样子，真难看。」",
                   unlocks_stage_context="隐瞒引发猜疑，信任与好感同时受损"),
        ],
        auto_resolve_effect={"favorability_delta": -5, "trust": -8},
    ),
    _crisis(
        "jealousy_2", "jealousy", "你心里最重要的位置是给谁的", "s11", 185,
        "夜里，{char_name}躺在你身边，忽然侧过头看你：\n"
        "「我一直在想一个问题……」她/他顿了顿，声音放轻：\n"
        "「在你心里，最重要的那个位置……到底是留给谁的？」",
        [
            Choice("a", "「当然是给你的，从来都是」", 6, 0, {"anger": -8, "joy": 8},
                   "你认真地看着她/他。",
                   "{char_name}愣了愣，然后弯起眼睛，声音有点抖：「……真的吗？不许反悔。」"),
            Choice("b", "「你怎么会这么想？你一直是最重要的」", 3, 0, {"trust": 5},
                   "你耐心地解释。",
                   "{char_name}低头：「嗯……我相信你。只是，偶尔会想确认一下。」"),
            Choice("c", "「这个嘛……不好说」", -8, -1, {"anger": 10, "trust": -6},
                   "你开玩笑般含糊过去。",
                   "{char_name}脸色白了白，沉默了很久：「……我知道了。」",
                   unlocks_stage_context="对方带着失落睡去，这个问题在她心里生了根"),
        ],
        auto_resolve_effect={"favorability_delta": -4, "trust": -6},
    ),
]


_CRISIS_MAP: Dict[str, CrisisEvent] = {c.id: c for c in CRISIS_EVENTS}

CRISIS_TYPE_LABELS = {k: f"{v['icon']} {v['label']}" for k, v in CRISIS_TYPES.items()}


def get_crisis_event(crisis_id: str) -> Optional[CrisisEvent]:
    return _CRISIS_MAP.get(crisis_id)


def crises_for_stage(stage_id: str) -> List[CrisisEvent]:
    """按当前 RDE 阶段筛选候选事件（满足最低阶段要求）"""

    def _rank(s: str) -> int:
        try:
            return int(s[1:]) if s.startswith("s") else 0
        except ValueError:
            return 0

    cur = _rank(stage_id)
    out = []
    for c in CRISIS_EVENTS:
        if _rank(c.stage_requirement) <= cur:
            out.append(c)
    return out
