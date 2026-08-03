"""EmotionAI Pro - 情感数据统计（时间序列追踪）

按天记录每个用户的好感度/亲密度/阶段/互动数据快照，
支持趋势文本图表与概要统计，可搭配图片渲染器输出图表图片。
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional


class StatsTracker:
    """每日情感数据快照追踪器（落盘存储）"""

    def __init__(self, data_dir: Path, max_days: int = 30):
        self.data_dir = Path(data_dir)
        self.max_days = max(7, int(max_days))
        self.history: Dict[str, List[dict]] = {}
        self._dirty: bool = False
        self._load()

    # ── 数据加载/保存 ──
    def _load(self):
        f = self.data_dir / "stats_history.json"
        if f.exists():
            try:
                self.history = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                self.history = {}

    def save(self):
        if not self._dirty:
            return
        f = self.data_dir / "stats_history.json"
        try:
            f.write_text(
                json.dumps(self.history, ensure_ascii=False), encoding="utf-8"
            )
            self._dirty = False
        except Exception:
            pass

    def force_save(self):
        self._dirty = True
        self.save()

    # ── 记录 ──
    def update(self, uid: str, favorability: float, intimacy: float,
               stage_index: int, stage_label: str,
               total_interactions: int, positive: int, negative: int,
               conversation_turns: int):
        """更新今日快照（每天每用户一条）"""
        today = date.today().isoformat()
        entries = self.history.setdefault(uid, [])
        now = date.today()
        # 清理过期数据
        cutoff = now - timedelta(days=self.max_days - 1)
        entries[:] = [
            e for e in entries
            if self._parse_date(e.get("date", "")) is not None
            and self._parse_date(e.get("date", "")) >= cutoff
        ]
        if entries and entries[-1].get("date") == today:
            e = entries[-1]
            e.update({
                "fav": round(favorability, 2),
                "int": round(intimacy, 2),
                "stage": stage_index,
                "stage_label": stage_label,
                "interactions": total_interactions,
                "positive": positive,
                "negative": negative,
                "turns": conversation_turns,
            })
        else:
            entries.append({
                "date": today,
                "fav": round(favorability, 2),
                "int": round(intimacy, 2),
                "stage": stage_index,
                "stage_label": stage_label,
                "interactions": total_interactions,
                "positive": positive,
                "negative": negative,
                "turns": conversation_turns,
            })
            self._dirty = True
            self.save()

    @staticmethod
    def _parse_date(s: str):
        try:
            return date.fromisoformat(s)
        except Exception:
            return None

    # ── 查询 ──
    def trend(self, uid: str, days: Optional[int] = None) -> List[dict]:
        entries = self.history.get(uid, [])
        if days:
            entries = entries[-max(3, int(days)):]
        return list(entries)

    def summary(self, uid: str, days: int = 14) -> dict:
        """概览统计：最高/最低/平均/涨跌天数/净变化"""
        entries = self.trend(uid, days)
        if not entries:
            return {"has_data": False, "days": 0}
        favs = [e["fav"] for e in entries]
        ints = [e["int"] for e in entries]
        deltas = [favs[i] - favs[i - 1] for i in range(1, len(favs))]
        first, last = entries[0], entries[-1]
        return {
            "has_data": True,
            "days": len(entries),
            "first_date": first["date"],
            "last_date": last["date"],
            "start_fav": first["fav"],
            "end_fav": last["fav"],
            "max_fav": max(favs),
            "min_fav": min(favs),
            "avg_fav": round(sum(favs) / len(favs), 2),
            "max_int": max(ints),
            "min_int": min(ints),
            "avg_int": round(sum(ints) / len(ints), 2),
            "delta": round(last["fav"] - first["fav"], 2),
            "up_days": sum(1 for d in deltas if d > 0.01),
            "down_days": sum(1 for d in deltas if d < -0.01),
            "total_interactions": last["interactions"],
        }

    # ── 文本图表 ──
    def build_text_chart(self, uid: str, days: int = 14) -> List[str]:
        """好感度/亲密度趋势文本图表"""
        entries = self.trend(uid, days)
        if not entries:
            return ["暂无统计数据。", "用户发送消息后开始自动记录（每天一条快照）。"]
        lines = []
        w = 20
        for e in entries:
            md = e["date"][5:]  # MM-DD
            fav = e["fav"]
            it = e["int"]
            fav_n = max(0, min(w, int((fav + 100) / 200 * w)))
            int_n = max(0, min(w, int(it / 100 * w)))
            bar = "█" * fav_n + "░" * (w - fav_n)
            i_bar = "█" * int_n + "░" * (w - int_n)
            fav_s = f"{fav:+.1f}"
            lines.append(f"{md} 好感 {fav_s:>7} {bar}")
            lines.append(f"{md} 亲密 {it:>6.1f} {i_bar}")
        return lines

    def to_web(self, uid: str, days: int = 7) -> dict:
        entries = self.trend(uid, days)
        return {
            "dates": [e["date"][5:] for e in entries],
            "fav": [e["fav"] for e in entries],
            "int": [e["int"] for e in entries],
            "stages": [e["stage_label"] for e in entries],
        }
