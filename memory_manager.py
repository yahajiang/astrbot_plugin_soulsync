"""SoulSync - 长期记忆管理器（落盘存储重要情感事件）"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from emotion_engine import DIM_ICONS, DIM_LABELS


def emotion_anchor(emotions: Optional[dict], top_n: int = 2) -> str:
    """从 8 维情感快照提取情感锚点文本（取最高 top_n 维），如 😊喜悦62 · 🤗信任71"""
    if not emotions:
        return ""
    dims = sorted(
        ((v, d) for d, v in emotions.items() if isinstance(v, (int, float))),
        reverse=True,
    )
    parts = [
        f"{DIM_ICONS.get(d, '•')}{DIM_LABELS.get(d, d)}{v:.0f}"
        for v, d in dims[:top_n]
    ]
    return " · ".join(parts)


class LongTermMemory:
    """
    长期记忆：落盘存储重要情感事件。
    每个用户维护一个事件队列，跨重启保留。
    """

    def __init__(self, data_dir: Path, max_events_per_user: int = 50, half_life_days: float = 30.0):
        self.data_dir = data_dir / "long_term_memory"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_events = max_events_per_user
        # 遗忘曲线半衰期（天）：记忆清晰度减半所需天数
        self.half_life_days = max(1.0, float(half_life_days))
        self._memory: Dict[str, List[dict]] = {}
        self._load_all()

    def set_half_life(self, days: float):
        self.half_life_days = max(1.0, float(days))

    def add_event(self, user_id: str, event: dict):
        """添加一条重要情感事件"""
        if user_id not in self._memory:
            self._memory[user_id] = []

        event["ts"] = time.time()
        event.setdefault("vividness", 100)          # 清晰度基准 0~100
        event.setdefault("last_recalled_ts", 0)     # 最近一次被唤醒时间
        event.setdefault("important", False)        # 重要记忆（永不遗忘）
        self._memory[user_id].append(event)

        # 超过上限则淘汰最旧的
        if len(self._memory[user_id]) > self.max_events:
            self._memory[user_id] = self._memory[user_id][-self.max_events:]

        self._save_user(user_id)

    @staticmethod
    def vividness_of(event: dict, half_life_days: float = 30.0, now: float = 0.0) -> int:
        """遗忘曲线：按指数衰减计算事件当前清晰度（0~100）。
        重要记忆恒为 100（永不遗忘）；其余 base × 0.5^(天数/半衰期)，回忆唤醒后从唤醒时刻重新衰减。"""
        if event.get("important"):
            return 100
        now = now or time.time()
        base = float(event.get("vividness", 100))
        anchor = event.get("last_recalled_ts") or event.get("ts") or now
        days = max(0.0, (now - anchor) / 86400.0)
        return max(5, min(100, round(base * 0.5 ** (days / max(1.0, half_life_days)))))

    @staticmethod
    def _vividness_tone(event: dict) -> str:
        """按情感快照判定模糊记忆的色调（温暖/苦涩/难忘/久远）"""
        em = event.get("emotions") or {}
        if em.get("joy", 0) >= 60 or em.get("trust", 0) >= 60:
            return "温暖的"
        if em.get("sadness", 0) >= 55 or em.get("anger", 0) >= 55 or em.get("disgust", 0) >= 55:
            return "苦涩的"
        if em.get("surprise", 0) >= 55 or em.get("anticipation", 0) >= 55:
            return "难忘的"
        return "久远的"

    @staticmethod
    def _format_event(event: dict, vividness: int) -> str:
        """按清晰度格式化事件行：清晰完整输出，模糊输出占位描述"""
        ts_str = time.strftime("%m-%d %H:%M", time.localtime(event.get("ts", 0)))
        fav = event.get("favorability", "?")
        stage = event.get("stage", "")
        if vividness >= 60:
            return f"[{ts_str}] 好感={fav} {stage} | {event.get('description', '')}"
        tone = LongTermMemory._vividness_tone(event)
        return f"[{ts_str}] 好感={fav} {stage} | 模糊的回忆（{tone}一段记忆 · 清晰度{vividness}%）"

    def get_events(self, user_id: str, limit: int = 10) -> List[dict]:
        """获取最近 N 条事件"""
        events = self._memory.get(user_id, [])
        return events[-limit:]

    def get_summary(self, user_id: str) -> str:
        """生成用户情感记忆摘要（供 LLM 参考）；久远记忆自动模糊化"""
        events = self.get_events(user_id, 5)
        if not events:
            return "暂无长期记忆。"

        lines = []
        for e in events:
            v = self.vividness_of(e, self.half_life_days)
            lines.append(self._format_event(e, v))
        return "\n".join(lines)

    def get_faded_events(self, user_id: str, limit: int = 3, max_vividness: int = 80) -> List[dict]:
        """获取最模糊（清晰度低于阈值、按模糊度升序）的事件，供记忆唤醒（重要记忆不参与）"""
        events = [e for e in self._memory.get(user_id, [])
                  if not e.get("important")
                  and self.vividness_of(e, self.half_life_days) < max_vividness]
        events.sort(key=lambda e: self.vividness_of(e, self.half_life_days))
        return events[:limit]

    def recall(self, user_id: str, ts: float) -> Optional[dict]:
        """唤醒一段记忆：清晰度重置为 100，从当前时刻重新衰减。
        返回被唤醒的事件（无则 None）"""
        for e in self._memory.get(user_id, []):
            if e.get("ts") == ts:
                e["last_recalled_ts"] = time.time()
                e["vividness"] = 100
                self._save_user(user_id)
                return e
        return None

    def mark_important(self, user_id: str, ts: float) -> Optional[dict]:
        """标记重要记忆：永不忘却（清晰度恒 100，不参与遗忘/唤醒）。
        返回被标记的事件（无则 None）"""
        for e in self._memory.get(user_id, []):
            if e.get("ts") == ts:
                e["important"] = True
                e["vividness"] = 100
                self._save_user(user_id)
                return e
        return None

    def forget(self, user_id: str, ts: float) -> bool:
        """忘掉一段记忆：从长期记忆中删除。返回是否删除成功"""
        events = self._memory.get(user_id, [])
        for i, e in enumerate(events):
            if e.get("ts") == ts:
                del events[i]
                self._save_user(user_id)
                return True
        return False

    def get_timeline(self, user_id: str, limit: int = 15) -> List[dict]:
        """获取带情感锚点的记忆时间线（供自画像展示）"""
        events = self.get_events(user_id, limit)
        out = []
        for e in events:
            anchor = emotion_anchor(e.get("emotions"))
            out.append({
                "ts": e.get("ts", 0),
                "ts_str": time.strftime("%m-%d %H:%M", time.localtime(e.get("ts", 0))),
                "favorability": e.get("favorability"),
                "stage": e.get("stage", ""),
                "fav_delta": e.get("fav_delta"),
                "anchor": anchor,
                "vividness": self.vividness_of(e, self.half_life_days),
                "important": bool(e.get("important")),
                "description": e.get("description", ""),
                "message": e.get("message", ""),
            })
        return out

    def get_key_memories(self, user_id: str, limit: int = 5) -> List[dict]:
        """获取关键时刻（重要/大幅变化/考验/里程碑），按重要度排序（P13 时间跳跃叙事）"""
        events = self._memory.get(user_id, [])
        keys = []
        for e in events:
            fav = abs(float(e.get("fav_delta", 0.0)))
            desc = e.get("description", "")
            score = 0
            if e.get("important"):
                score += 1000
            if fav >= 2:
                score += int(fav * 50)
            if any(m in desc for m in ("🌱", "💔", "🌫️")):
                score += 300
            if "🎉" in desc:
                score += 200
            if score > 0:
                keys.append((score, e))
        keys.sort(key=lambda x: (-x[0], -float(x[1].get("ts", 0))))
        return [e for _, e in keys][:limit]

    def clear_user(self, user_id: str):
        self._memory.pop(user_id, None)
        f = self.data_dir / f"{user_id}.json"
        if f.exists():
            f.unlink()

    def clear_all(self):
        self._memory.clear()
        for f in self.data_dir.glob("*.json"):
            f.unlink()

    def _load_all(self):
        for f in self.data_dir.glob("*.json"):
            uid = f.stem
            try:
                self._memory[uid] = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                self._memory[uid] = []

    def _save_user(self, user_id: str):
        f = self.data_dir / f"{user_id}.json"
        try:
            f.write_text(json.dumps(self._memory[user_id], ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def save_all(self):
        for uid in self._memory:
            self._save_user(uid)
