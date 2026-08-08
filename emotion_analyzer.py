# -*- coding: utf-8 -*-
"""本地中文情绪分析器：对 SoulSync 的回复文本进行情感极性判断。

纯规则 + 词典驱动，无外部依赖。输出 5 类情绪之一：
喜悦 / 悲伤 / 愤怒 / 焦虑 / 期待（另有中性回退）。
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# 情绪词典：每个情绪对应一组触发词。词条按强度分两级（强/弱）。
# 强词权重 2，弱词权重 1；句子长度归一化后取最高分情绪。
EMOTION_LEXICON: Dict[str, Dict[str, List[str]]] = {
    "喜悦": {
        "strong": [
            "开心", "高兴", "快乐", "幸福", "太棒了", "太好了", "哈哈", "哈哈哈",
            "笑死", "好耶", "哇塞", "爱死", "喜欢", "超喜欢", "好喜欢", "嘿嘿",
            "美滋滋", "爽", "舒服", "惊喜", "激动", "雀跃", "欣喜", "愉悦",
            "高兴坏了", "笑得合不拢嘴", "喜滋滋", "乐开花", "心花怒放", "偷着乐",
        ],
        "weak": [
            "不错", "还行", "挺好", "赞", "棒", "加油", "好棒", "开心点",
            "笑", "好玩", "有趣", "可爱", "治愈", "温暖", "感动", "期待已久",
            "满足", "满意", "有希望", "充满希望", "元气满满",
        ],
    },
    "悲伤": {
        "strong": [
            "难过", "伤心", "难过死了", "好难过", "想哭", "哭了", "哭", "呜呜",
            "崩溃", "心碎", "绝望", "好想哭", "泪目", "眼眶红了", "鼻子一酸",
            "低落", "沮丧", "消沉", "忧郁", "闷闷不乐", "郁郁寡欢", "悲",
            "痛", "伤透了", "孤", "孤独", "寂寞", "emo", "EMO",
        ],
        "weak": [
            "失落", "遗憾", "叹息", "叹气", "唉", "累", "好累", "疲惫", "无精打采",
            "没意思", "无聊", "空虚", "茫然", "失意", "委屈", "受伤", "不舍",
            "想念", "想家", "遗憾", "可惜", "心累",
        ],
    },
    "愤怒": {
        "strong": [
            "气死", "气疯", "炸了", "火大", "忍不了", "不能忍", "可恶", "混蛋",
            "垃圾", "傻逼", "神经病", "滚", "闭嘴", "烦死", "烦透了", "恶心",
            "讨厌", "恨", "愤怒", "怒火", "暴怒", "抓狂", "毛了", "无语了",
            "凭什么", "岂有此理", "气不打一处来", "恼火", "气炸", "怒",
        ],
        "weak": [
            "生气", "不满", "不爽", "烦躁", "烦", "窝火", "郁闷", "赌气",
            "别扭", "委屈", "怄气", "气鼓鼓", "不开心", "闹心", "糟心", "头疼",
            "郁闷死了",
        ],
    },
    "焦虑": {
        "strong": [
            "焦虑", "紧张", "害怕", "恐惧", "担心", "担忧", "不安", "心慌",
            "睡不着", "失眠", "噩梦", "压力大", "压力山大", "喘不过气", "窒息",
            "恐慌", "惊恐", "崩溃边缘", "心神不宁", "提心吊胆", "坐立不安",
        ],
        "weak": [
            "愁", "发愁", "烦心事", "心事", "压力", "忙", "好忙", "加班",
            "考试", "deadline", "截止", "赶", "来不及", "来不及了", "怎么办",
            "犹豫", "纠结", "不确定", "迷茫", "忐忑", "没底", "慌",
        ],
    },
    "期待": {
        "strong": [
            "期待", "盼望", "渴望", "迫不及待", "等不及", "好想", "想快点",
            "梦想", "憧憬", "幻想", "希望", "盼望已久", "盼星星盼月亮",
        ],
        "weak": [
            "计划", "打算", "准备", "想试试", "想学", "憧憬", "好奇",
            "充满期待", "值得期待", "新开始", "重新开始", "改变", "未来",
            "约好", "说好", "安排", "规划",
        ],
    },
}

# 中性回退
NEUTRAL = "平静"

# 否定词：出现在触发词前 2 字内时翻转权重（"不难过" → 不判悲伤）
NEGATORS = ("不", "没", "别", "莫", "无", "未", "不是", "没有", "别不")


class EmotionResult:
    __slots__ = ("emotion", "confidence", "scores", "matched")

    def __init__(self, emotion: str, confidence: float, scores: Dict[str, float], matched: List[str]):
        self.emotion = emotion
        self.confidence = confidence
        self.scores = scores
        self.matched = matched

    def __repr__(self):
        return f"EmotionResult({self.emotion}, conf={self.confidence:.2f})"


def analyze(text: str) -> EmotionResult:
    """分析文本情绪，返回 EmotionResult。

    规则：
    1. 对每类情绪，扫描词典词，命中强词 +2 分、弱词 +1 分；
       触发词前 2 字内存在否定词时扣 1 分（抵消）。
    2. 总分除以 (log2(len+1)+1) 归一化，抑制长文本累计优势。
    3. 取最高分情绪；最高分 <= 0 或并列分差 < 0.15 时判为平静。
    confidence = 最高分 / 总分和（无分时为 0）。
    """
    text = text or ""
    scores: Dict[str, float] = {}
    matched: List[str] = []
    for emotion, levels in EMOTION_LEXICON.items():
        total = 0.0
        for weight, words in ((2.0, levels["strong"]), (1.0, levels["weak"])):
            for word in words:
                idx = text.find(word)
                if idx < 0:
                    continue
                negated = False
                start = max(0, idx - 2)
                before = text[start:idx]
                for n in NEGATORS:
                    if n in before:
                        negated = True
                        break
                total += -1.0 if negated else weight
                matched.append(word)
        scores[emotion] = total

    # 仅弱词命中（如单个"不错"）不足以判为情绪，需要至少一个强词或两个弱词
    for k in list(scores):
        if scores[k] < 2.0:
            scores[k] = 0.0

    norm = max(1.0, len(text) ** 0.5)
    normalized = {k: v / norm for k, v in scores.items()}
    best = max(normalized, key=normalized.get)
    second = sorted(normalized.values(), reverse=True)[1] if len(normalized) > 1 else 0.0

    if normalized[best] <= 0 or abs(normalized[best] - second) < 0.15:
        return EmotionResult(NEUTRAL, 0.0, normalized, matched)

    total_score = sum(normalized.values())
    confidence = normalized[best] / total_score if total_score > 0 else 0.0
    return EmotionResult(best, min(confidence, 1.0), normalized, matched)


def is_positive(emotion: str) -> bool:
    return emotion in ("喜悦", "期待")


def is_negative(emotion: str) -> bool:
    return emotion in ("悲伤", "愤怒", "焦虑")
