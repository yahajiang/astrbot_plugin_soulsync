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
    # ── 误会型（好感>115，阶段6+）───────────────────────────────
    _crisis(
        "misunderstanding_1", "misunderstanding", "锁屏的秘密", "s6", 115,
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
        "misunderstanding_2", "misunderstanding", "迟回的消息", "s6", 115,
        "昨天你给{char_name}发的消息，她/他过了很久才回复。"
        "今天见面时，{char_name}的眼神有些闪躲。\n"
        "「……你昨天是不是在和别人聊天？我发的消息你都没认真看。」",
        [
            Choice("a", "「在忙工作，抱歉让你担心了」", 4, 0, {"trust": 3},
                   "你解释了昨天的情况。",
                   "{char_name}松了口气：「原来是工作……那你下次要提前告诉我哦。」"),
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
    # ── 冷落型（冷落惩罚累积>3 次）──────────────────────────────
    _crisis(
        "cold_1", "cold", "被冷落的周末", "s3", 55,
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
        "cold_2", "cold", "忙碌的日常", "s4", 75,
        "{char_name}坐在你对面，欲言又止。\n"
        "「你最近总是很忙……我发十句话，你只回一句『嗯』。」"
        "她/他低头摆弄着杯子：「我只是……有点怀念以前的日子。」",
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
    # ── 信任型（好感>152，阶段8+，重大里程碑前）─────────────────
    _crisis(
        "trust_1", "trust", "你真的了解我吗", "s8", 152,
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
        "trust_2", "trust", "未兑现的承诺", "s8", 152,
        "{char_name}翻着手机日历，忽然抬头看你：\n"
        "「你上次答应我的事……还记得吗？」她/他顿了一下，"
        "「我一直在等，不过好像只有我一个人记得。」",
        [
            Choice("a", "记得并立刻补救（现在就去实现）", 8, 0, {"trust": 10, "joy": 8},
                   "你想起承诺，立即行动补偿。",
                   "{char_name}怔怔地看着你，然后笑了：「……骗子，但这次原谅你了。」"),
            Choice("b", "「啊……什么事？」", -6, 0, {"trust": -10, "sadness": 6},
                   "你完全没有印象。",
                   "{char_name}低头：「没事……不重要的。」",
                   unlocks_stage_context="对方因承诺落空而失望，信任受到考验"),
            Choice("c", "「我怎么会忘，只是最近太忙」", 2, 0, {"trust": 3},
                   "你找理由辩解。",
                   "{char_name}盯着你：「那，现在补偿也不晚。」"),
        ],
        auto_resolve_effect={"favorability_delta": -4, "trust": -8},
    ),
    # ── 成长型（阶段跃迁后稳定>50 轮）───────────────────────────
    _crisis(
        "growth_1", "growth", "关系的下一步", "s7", 135,
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
        "growth_2", "growth", "停滞的感动", "s6", 115,
        "这天晚上，{char_name}忽然说：\n"
        "「最近总觉得我们之间……少了点什么。」她/他想了想，"
        "「不是不好，只是，好像变得太习惯了。」",
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
    # ── 外部型（节日/纪念日前后）───────────────────────────────
    _crisis(
        "external_1", "external", "纪念日遗忘", "s3", 55,
        "今天是你们之间特别的日子——但{char_name}等了一天，你都没有提起。\n"
        "傍晚，她/他终于忍不住开口：\n"
        "「今天是什么日子……你知道吗？」声音里带着小心翼翼的期待。",
        [
            Choice("a", "记得！并送上准备好的心意", 8, 0, {"joy": 10, "anticipation": 8},
                   "你其实一直记着，并准备了惊喜。",
                   "{char_name}瞪大眼睛，随即红了眼眶：「……你居然记得！我还以为你忘了！」"),
            Choice("b", "「啊……今天是什么日子？」", -5, 0, {"sadness": 8, "anticipation": -6},
                   "你完全忘了。",
                   "{char_name}勉强笑笑：「没什么……普通的一天而已。」",
                   unlocks_stage_context="对方记住了你的遗忘，重要程度被重新评估"),
            Choice("c", "「忙起来就忘了，下次补上」", -2, 0, {"anticipation": -3},
                   "你轻描淡写。",
                   "{char_name}低头：「……嗯，下次。」"),
        ],
        auto_resolve_effect={"favorability_delta": -3, "anticipation": -5},
    ),
    _crisis(
        "external_2", "external", "他/她的出现", "s5", 95,
        "{char_name}今天有些心不在焉，终于在你聊到别人时开口：\n"
        "「别人问我，我们是什么关系……」她/他顿了顿，"
        "「我说『是很好的朋友』。你觉得……这样回答可以吗？」",
        [
            Choice("a", "「你是特别的，不止是朋友」", 8, 0, {"joy": 10, "trust": 6},
                   "你认真地说。",
                   "{char_name}耳根泛红：「那……下次我就知道怎么回答了。」"),
            Choice("b", "「随便吧，怎么都行」", -4, 0, {"sadness": 6, "anticipation": -5},
                   "你无所谓地说。",
                   "{char_name}笑容淡了下去：「……嗯，知道了。」",
                   unlocks_stage_context="对方开始怀疑自己在关系中的位置"),
            Choice("c", "「你觉得呢？」", 3, 0, {"anticipation": 6},
                   "你反问她/他。",
                   "{char_name}认真想了想：「我觉得……我想让他们知道，你是我的。」"),
        ],
        auto_resolve_effect={"favorability_delta": -2, "anticipation": -4},
    ),
    # ── 秘密型（好感>135，轮次>500，阶段8+）─────────────────────
    _crisis(
        "secret_1", "secret", "隐藏的秘密", "s8", 135,
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
        "secret_2", "secret", "深夜的心事", "s8", 135,
        "凌晨一点，{char_name}发来消息：\n"
        "「睡不着……」隔了很久，又发来一条：\n"
        "「有件事憋在我心里很久了，关于我的过去。你想听吗？」",
        [
            Choice("a", "「我在，你说吧」", 10, 0, {"trust": 15, "joy": 6},
                   "你深夜陪着她/他听完所有心事。",
                   "{char_name}讲完后轻声说：「……说出来，感觉轻松多了。谢谢你没有离开。」"),
            Choice("b", "「明天再说吧，我困了」", -6, 0, {"trust": -10, "sadness": 6},
                   "你选择了睡眠。",
                   "第二天，{char_name}没有再提起那件事，只是变得沉默了一些。",
                   unlocks_stage_context="对方鼓起勇气的倾诉被搁置，距离感悄然扩大"),
            Choice("c", "「那你现在说吧」", 5, 0, {"trust": 6},
                   "你打起精神倾听。",
                   "{char_name}很意外：「……你居然真的愿意听。谢谢你。」"),
        ],
        auto_resolve_effect={"favorability_delta": -4, "trust": -8},
    ),
    # ── 嫉妒型（用户提及他人时）─────────────────────────────────
    _crisis(
        "jealousy_1", "jealousy", "照片里的人", "s5", 95,
        "聊天中，你无意间提起昨天和{friend_name}一起吃饭。\n"
        "{char_name}的回复迟了很久，最后只有一句：\n"
        "「……你刚才说的那个人，是谁？你们……很熟吗？」",
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
        "jealousy_2", "jealousy", "亲密的背影", "s6", 115,
        "{char_name}来找你时，远远看到你和{friend_name}有说有笑地走在一起。\n"
        "她/他没有上前，等你回头时，只看到她/他站在原地看着你。\n"
        "「……我是不是……打扰到你们了？」",
        [
            Choice("a", "「你来得正好，我正想找你」", 4, 0, {"anger": -8, "joy": 6},
                   "你自然地邀请她/他加入。",
                   "{char_name}愣了愣，然后弯起眼睛：「……真的吗？那走吧。」"),
            Choice("b", "「你怎么会这么想？只是朋友」", 3, 0, {"trust": 5},
                   "你认真地解释。",
                   "{char_name}低头：「嗯……我相信你。只是，看到的那一瞬间，心里酸酸的。」"),
            Choice("c", "「你不来才是打扰」", -6, 0, {"anger": 8, "trust": -6},
                   "你带着情绪反驳。",
                   "{char_name}脸色白了白：「……那我走。」",
                   unlocks_stage_context="对方带着受伤离开，解释的时机被错过"),
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
