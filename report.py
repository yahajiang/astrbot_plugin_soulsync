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


def _stats_of(items: List[dict]) -> Optional[dict]:
    """由过滤后的事件列表生成统计（列表为空返回 None）"""
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
        "event_count": len(items),
        "fav_delta": round(fav, 1),
        "pos_count": pos, "neg_count": neg,
        "top_emotions": top_emo,
        "important_names": imp_names,
        "crisis_pass": pass_n, "crisis_fail": fail_n,
        "samples": samples,
    }


def aggregate_window(events: List[dict], start_ts: float, end_ts: float) -> Optional[dict]:
    """聚合时间窗口 [start_ts, end_ts) 内的记忆事件（P11 角色视角回顾的数据基础）"""
    items = [e for e in events if start_ts <= float(e.get("ts", 0)) < end_ts]
    return _stats_of(items)


def aggregate_month(events: List[dict], year: int, month: int) -> Optional[dict]:
    """聚合某年某月的记忆事件为月度统计；该月无事件返回 None。
    返回字段：event_count / fav_delta / pos_count / neg_count /
              top_emotions（[(标签, 总分)] 取前2）/ important_names /
              crisis_pass / crisis_fail / samples（最近3条描述）"""
    from datetime import datetime
    if month == 12:
        start = datetime(year, 12, 1)
        end = datetime(year + 1, 1, 1)
    else:
        start = datetime(year, month, 1)
        end = datetime(year, month + 1, 1)
    stats = aggregate_window(events, start.timestamp(), end.timestamp())
    if stats is None:
        return None
    stats["year"] = year
    stats["month"] = month
    return stats


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


def _tone_narrative(stats: dict) -> str:
    """角色视角的基调叙述（按净好感变化）"""
    fav = stats["fav_delta"]
    if fav > 2:
        return "这段时间，我们之间像是被阳光晒得暖洋洋的，每一段回忆都闪着光"
    if fav > 0:
        return "这段时间，我们一起留下的回忆大多是甜美的，心里满满当当的"
    if fav < -2:
        return "这段时间，我们确实走过了几道坎，我心里有过失落和不安"
    if fav < 0:
        return "这段时间有些小波折，但每一次我都舍不得放开你的手"
    return "这段时间，日子平平淡淡，但能这样陪着你，我就觉得很安心"


# ══════════ P12 对比雷达图：关系六维评分 ══════════
DIMENSIONS = ["甜蜜", "心动", "信任", "安稳", "浓度", "羁绊"]

# 各维度由情绪均值映射的权重（"安稳"为负向情绪反转）
_DIM_W = [
    ({"joy": 0.6, "trust": 0.4}, 0),        # 甜蜜
    ({"anticipation": 0.6, "surprise": 0.4}, 0),  # 心动
    ({"trust": 1.0}, 0),                    # 信任
    ({"sadness": -0.5, "anger": -0.5}, 100),  # 安稳 = 100 - 负面
    (None, 0),                              # 浓度：全部情绪均值
]


def dimension_scores(events: List[dict], start_ts: float, end_ts: float) -> Optional[dict]:
    """按时间窗口聚合关系六维评分（0~100）。无事件返回 None。
    甜蜜/心动/信任/安稳 由情绪均值映射，浓度=情绪活跃度均值，羁绊=min(100, 事件数*20)"""
    items = [e for e in events if start_ts <= float(e.get("ts", 0)) < end_ts]
    if not items:
        return None
    emo_means: Dict[str, float] = {}
    emo_count = 0
    for e in items:
        em = e.get("emotions") or {}
        if em:
            emo_count += 1
            for k, v in em.items():
                emo_means[k] = emo_means.get(k, 0.0) + float(v)
    for k in list(emo_means):
        emo_means[k] /= emo_count or 1
    scores = []
    for weights, base in _DIM_W:
        if weights is None:
            mean = sum(emo_means.values()) / 8.0 if emo_means else 0.0
        else:
            mean = sum(v * emo_means.get(k, 0.0) for k, v in weights.items())
        scores.append(round(max(0.0, min(100.0, base + mean))))
    scores.append(min(100, len(items) * 20))  # 羁绊
    return dict(zip(DIMENSIONS, scores))


def compare_windows(events: List[dict], mid_ts: float, span_sec: float) -> Optional[dict]:
    """前后两个时间段的关系维度对比：前段 [mid-span, mid)，后段 [mid, mid+span)。
    返回 {labels, before, after, before_avg, after_avg}；两段都无事件返回 None"""
    before = dimension_scores(events, mid_ts - span_sec, mid_ts)
    after = dimension_scores(events, mid_ts, mid_ts + span_sec)
    if before is None and after is None:
        return None
    zero = dict(zip(DIMENSIONS, [0] * len(DIMENSIONS)))
    before = before or zero
    after = after or zero
    return {
        "labels": DIMENSIONS,
        "before": [before[d] for d in DIMENSIONS],
        "after": [after[d] for d in DIMENSIONS],
        "before_avg": round(sum(before.values()) / len(before), 1),
        "after_avg": round(sum(after.values()) / len(after), 1),
    }


def compare_recent(events: List[dict], now: float, span_days: int = 7) -> Optional[dict]:
    """以 now 为界，对比最近 span_days 天与再往前 span_days 天"""
    span = max(1, span_days) * 86400.0
    return compare_windows(events, now - span, span)


def format_compare(comp: dict, span_days: int = 7) -> str:
    """文本版对比摘要：上升/下降的维度 + 总体走向"""
    up = [(l, a - b) for l, b, a in zip(comp["labels"], comp["before"], comp["after"])
          if a > b]
    down = [(l, b - a) for l, b, a in zip(comp["labels"], comp["before"], comp["after"])
            if b > a]
    up.sort(key=lambda x: -x[1])
    down.sort(key=lambda x: -x[1])
    lines = [f"🕸️ 关系雷达对比 · 前{span_days}天 vs 后{span_days}天"]
    if up:
        lines.append("📈 升温：" + "、".join(f"{l}+{d}" for l, d in up[:3]))
    if down:
        lines.append("📉 降温：" + "、".join(f"{l}-{d}" for l, d in down[:3]))
    if not up and not down:
        lines.append("各方面保持稳定，波澜不惊")
    trend = "整体在变好" if comp["after_avg"] > comp["before_avg"] else (
        "整体有些回落" if comp["after_avg"] < comp["before_avg"] else "整体持平")
    lines.append(f"综合评分 {comp['before_avg']} → {comp['after_avg']}，{trend}。")
    return "\n".join(lines)


def format_role_report(stats: dict, days: int = 14) -> str:
    """以角色第一人称口吻渲染这段时间的情感历程（P11 角色视角报告）"""
    lines = [
        f"📖 角色独白 · 最近{days}天",
        f"{_tone_narrative(stats)}。我们之间一共留下了 {stats['event_count']} 个值得记住的瞬间，"
        f"我们的距离，{('近了' if stats['fav_delta'] >= 0 else '起了些波澜')}（好感 {stats['fav_delta']:+.1f}）。",
    ]
    if stats["top_emotions"]:
        emo = "、".join(f"{k}" for k, _ in stats["top_emotions"])
        lines.append(f"说起那时候的心情，大多是{emo}。")
    if stats["important_names"]:
        lines.append(f"最难忘的，是「{'」「'.join(n for n in stats['important_names'])}」。")
    if stats["crisis_pass"] or stats["crisis_fail"]:
        lines.append(
            f"有{stats['crisis_pass'] + stats['crisis_fail']}次考验摆在我们面前："
            f"{('我撑过来了' + str(stats['crisis_pass']) + '次') if stats['crisis_pass'] else ''}"
            f"{('，也有' + str(stats['crisis_fail']) + '次让我夜里辗转反侧') if stats['crisis_fail'] else ''}。"
        )
    if stats["samples"]:
        lines.append("我现在还记得：" + "；".join(f"「{s}」" for s in stats["samples"]))
    lines.append("这些，都是我心底珍藏的、关于你的记忆。")
    return "\n".join(lines)
