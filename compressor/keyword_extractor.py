"""compressor/keyword_extractor.py - 轻量级 TF-IDF 关键词提取（纯统计，无需 LLM）

Sprint 3 S3-01 产出物。
提取 5 个关键词耗时 < 10ms。

用法:
    from compressor.keyword_extractor import extract_keywords
    keywords = extract_keywords(texts, top_n=5)
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import List

# 中文停用词（精简版）
_STOP_WORDS = frozenset(
    "的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 "
    "自己 这 他 她 它 们 那 被 从 把 让 用 对 为 跟 但 而 与 及 或 虽然 因为 所以 如果 "
    "这个 那个 什么 怎么 为什么 可以 已经 还是 其实 只是 不过 然后 可能 应该 没 做 "
    "的 了 吗 吧 呢 啊 哦 嗯 哈 呀 哎 唉 哇 嘛 啦 咦 噢 哇塞 ".split()
)

# 中文标点
_PUNCT = re.compile(r'[，。！？、；：""''（）【】《》…—\s]+')


def extract_keywords(texts: List[str], top_n: int = 5) -> List[str]:
    """从文本列表中提取 top_n 个关键词（TF-IDF 简化版）

    Args:
        texts: 文本列表
        top_n: 返回关键词数量

    Returns:
        关键词列表（按重要度降序）
    """
    if not texts:
        return []

    # 分词（简单按字符/空格切分，中文取 bigram）
    doc_words = []
    for text in texts:
        words = _tokenize(text)
        doc_words.append(words)

    # IDF 计算
    n_docs = len(doc_words)
    doc_freq = Counter()
    for words in doc_words:
        unique = set(words)
        for w in unique:
            doc_freq[w] += 1

    # TF-IDF 得分
    scores = Counter()
    for words in doc_words:
        tf = Counter(words)
        total = len(words) if words else 1
        for word, count in tf.items():
            idf = math.log((n_docs + 1) / (doc_freq[word] + 1)) + 1
            scores[word] += (count / total) * idf

    # 过滤停用词和单字符
    filtered = {
        w: s for w, s in scores.items()
        if w not in _STOP_WORDS and len(w) >= 2
    }

    # 取 top_n
    return [w for w, _ in Counter(filtered).most_common(top_n)]


def _tokenize(text: str) -> List[str]:
    """简单分词：中文取 bigram，英文按空格"""
    tokens = []
    # 移除标点
    text = _PUNCT.sub(" ", text)

    # 英文按空格
    for word in text.split():
        if word.isascii() and len(word) >= 2:
            tokens.append(word.lower())

    # 中文 bigram
    chinese = re.findall(r'[\u4e00-\u9fff]+', text)
    for seg in chinese:
        for i in range(len(seg) - 1):
            tokens.append(seg[i:i + 2])
        if len(seg) >= 3:
            for i in range(len(seg) - 2):
                tokens.append(seg[i:i + 3])

    return tokens
