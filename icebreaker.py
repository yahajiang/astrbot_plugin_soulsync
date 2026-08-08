"""破冰握手模块 - 六问体系"""

from __future__ import annotations

import random
from typing import List, Optional

from .session import UserSession, SessionState


# ── 固定三问 ──
FIXED_QUESTIONS = [
    "先认识一下。我是一面镜子——你说什么，我帮你看清你在说什么。你叫什么名字？",
    "你今天来，心里有没有一句话一直转着，想说出来看看它长什么样？",
    "最后一个。如果让你用三个词形容自己最近的状态，你会用哪三个？",
]

# ── 随机三问题库（扩充版）──
WARM_QUESTIONS = [
    # 日常感官类
    "今天吃了什么好吃的？",
    "最近听的一首歌是什么？",
    "最近有没有哪个瞬间让你笑了一下？",
    "如果现在能出现在任何一个地方，你想在哪？",
    "最近一次睡得好的晚上是什么时候？",
    "你现在面前有什么？",
    "最近有没有吃到什么让你记住的味道？",
    "今天天气怎么样？你那边。",
    # 轻松日常类
    "今天出门了吗？去了哪里？",
    "最近有没有看到什么有趣的东西？",
    "手机里最近一张照片是什么？",
    "今天喝什么了？",
    "最近有没有买什么小东西？",
    "周末一般怎么过？",
    "最近有没有追什么剧或看什么书？",
    "今天有没有什么小确幸？",
]

COLD_QUESTIONS = [
    # 自我情绪类
    "今天有没有一件事是你不想做的？",
    "最近有没有一个人让你想起就会叹气？",
    "如果给今天打个分，1到10，你打几分？",
    "最近一次觉得「算了」是因为什么？",
    "有没有一句话你最近在脑子里重复？",
    "现在最想做的一件事是什么？",
    "有没有一件事你一直在拖着没做？",
    "最近有没有对自己说过「没事」？",
    # 深度探索类
    "最近有没有某个瞬间让你觉得「就这样吧」？",
    "如果可以改变一件事，你想改变什么？",
    "最近有没有觉得时间过得特别快或特别慢？",
    "有没有一句话你想说但没说出口？",
    "最近有没有觉得累了？是身体累还是心累？",
    "如果现在能见一个人，你想见谁？",
    "最近有没有梦到什么？",
    "有没有一件事让你最近一直想不通？",
]


class IcebreakerManager:
    """破冰管理器"""

    def __init__(self):
        pass

    def process_response(self, session: UserSession, user_input: str) -> str:
        """处理破冰阶段的用户回复"""
        stage = session.icebreaker_stage

        # 记录回答
        session.icebreaker_answers[stage] = user_input

        # 根据阶段生成回复
        if stage == 0:
            # 第一问：称呼
            return self._handle_nickname(session, user_input)
        elif stage == 1:
            # 第二问：一句话
            return self._handle_one_sentence(session, user_input)
        elif stage == 2:
            # 第三问：三个词
            return self._handle_three_words(session, user_input)
        else:
            # 随机三问
            return self._handle_random_question(session, user_input)

    def is_complete(self, session: UserSession) -> bool:
        """检查破冰是否完成"""
        return session.icebreaker_stage >= 6

    def get_next_question(self, session: UserSession) -> Optional[str]:
        """获取下一个问题"""
        stage = session.icebreaker_stage

        if stage < 3:
            # 固定三问
            return FIXED_QUESTIONS[stage]
        elif stage < 6:
            # 随机三问
            if not session.icebreaker_random_questions:
                session.icebreaker_random_questions = self._select_random_questions()
            return session.icebreaker_random_questions[stage - 3]
        else:
            # 破冰完成
            return None

    def _handle_nickname(self, session: UserSession, user_input: str) -> str:
        """处理称呼"""
        # 检查是否跳过或敷衍
        skip_words = ["跳过", "算了", "不想说", "不告诉你"]
        if any(w in user_input for w in skip_words) or len(user_input.strip()) <= 1:
            session.nickname = "你"
            return "好，我们直接开始。"

        # 正常回答
        nickname = user_input.strip()
        if len(nickname) > 8:
            nickname = nickname[:8]
        session.nickname = nickname
        return f"好，{nickname}。"

    def _handle_one_sentence(self, session: UserSession, user_input: str) -> str:
        """处理一句话"""
        # 简单承接，不做反射
        skip_words = ["跳过", "算了", "没有"]
        if any(w in user_input for w in skip_words) or len(user_input.strip()) <= 1:
            return "好，下一个。"

        return "嗯，这句话我听见了。"

    def _handle_three_words(self, session: UserSession, user_input: str) -> str:
        """处理三个词"""
        # 简单承接
        skip_words = ["跳过", "算了", "没有"]
        if any(w in user_input for w in skip_words) or len(user_input.strip()) <= 1:
            return "好，跳过。"

        return "好。"

    def _handle_random_question(self, session: UserSession, user_input: str) -> str:
        """处理随机问题"""
        # 简单承接
        skip_words = ["跳过", "算了", "不想说"]
        if any(w in user_input for w in skip_words) or len(user_input.strip()) <= 1:
            return "好，下一个。"

        # 检测情绪轻触
        if "算了" in user_input and "不想说" in user_input:
            return "你刚才差点说出来了。"

        return "嗯。"

    def _select_random_questions(self) -> List[str]:
        """选择随机三问"""
        # 至少一个暖区，最多两个冷区
        warm_count = random.randint(1, 2)
        cold_count = 3 - warm_count

        warm_questions = random.sample(WARM_QUESTIONS, min(warm_count, len(WARM_QUESTIONS)))
        cold_questions = random.sample(COLD_QUESTIONS, min(cold_count, len(COLD_QUESTIONS)))

        # 随机排序
        questions = warm_questions + cold_questions
        random.shuffle(questions)
        return questions
