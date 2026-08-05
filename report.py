# -*- coding: utf-8 -*-
"""月度关系报告（v2.16 P10）：按月聚合记忆事件，总结双方关系进展与成长"""
import time
from typing import Dict, List, Optional, Tuple

EMOTION_LABELS: Dict[str, str] = {
    "joy": "喜悦", "sadness": "悲伤", "anger": "愤怒", "fear": "担忧",
    "disgust": "抗拒", "surprise": "惊喜", "trust": "信任", "anticipation": "期待",
}

CRISIS_PASS_MARK = "🌱"
CRISIS_FAIL_MARKS = ("💔", "🌫️")


def aggregate_month(events: List[dict], year: int, month: int) -> Optional[dict]:
    """聚合某年某月的记忆事件为月度统计；该月无事件返回 None。
    返回字段：event_count / fav_delta / pos_count / neg_count /
              top_emotions（[(标签, 总分)] 取前2）/ important_names /
              crisis_pass / crisis_fail / samples（最近3条描述）"""
    items = [e for e in events if time.localtime(e.get("ts", 0))[:2] == (year, month)]
    if not items:
        return None
    fav = 0.0
    pos = neg = 0
    for e in items:
        d = float(e.get("fav_delta", 0.0))
        fav += d
        if d > 0:
            pos += 1
        elif d < 0:
            neg += 1
    emo_sum: Dict[str, float] = {}
    for e in items:
        for k, v in (e.get("emotions") or {}).items():
            emo_sum[k] = emo_sum.get(k, 0.0) + float(v)
    top = sorted(emo_sum.items(), key=lambda kv: kv[1], reverse=True)[:2]
    top_emo = [(EMOTION_LABELS.get(k, k), round(v)) for k, v in top]
    imp_names = [e.get("description", "")[:20] for e in items if e.get("important")]
    pass_n = sum(1 for e in items if CRISIS_PASS_MARK in e.get("description", ""))
    fail_n = sum(1 for e in items if any(m in e.get("description", "") for m in CRISIS_FAIL_MARKS))
    samples = [e.get("description", "") for e in items[-3:]]
    return {
        "year": year, "month": month,
        "event_count": len(items),
        "fav_delta": round(fav, 1),
        "pos_count": pos, "neg_count": neg,
        "top_emotions": top_emo,
        "important_names": imp_names,
        "crisis_pass": pass_n, "crisis_fail": fail_n,
        "samples": samples,
    }


def _tone_word(stats: dict) -> str:
    if stats["fav_delta"] > 0:
        return "关系稳步升温"
    if stats["fav_delta"] < 0:
        return "经历了一段起伏"
    return "平稳相处"


def format_report(stats: dict) -> str:
    """将月度统计渲染为可读的关系月报文本"""
    lines = [
        f"📊 {stats['year']}年{stats['month']}月 关系月报",
        f"· {_tone_word(stats)}：本月 {stats['event_count']} 段深刻记忆，"
        f"净好感 {stats['fav_delta']:+.1f}（{stats['pos_count']} 次升温 / {stats['neg_count']} 次降温）",
    ]
    if stats["top_emotions"]:
        emo = "、".join(f"{k}{v}" for k, v in stats["top_emotions"])
        lines.append(f"· 情绪主色调：{emo}")
    if stats["important_names"]:
        stars = "、".join(f"⭐{n}" for n in stats["important_names"])
        lines.append(f"· 难忘时刻：{stars}")
    if stats["crisis_pass"] or stats["crisis_fail"]:
        lines.append(f"· 信任考验：通过 {stats['crisis_pass']} 次，挫折 {stats['crisis_fail']} 次")
    if stats["samples"]:
        lines.append("· 回忆切片：" + "；".join(f"「{s}」" for s in stats["samples"]))
    return "\n".join(lines)


def last_month_label(year: int, month: int) -> Tuple[int, int]:
    """返回上个月的 (年, 月)"""
    if month == 1:
        return year - 1, 12
    return year, month - 1
