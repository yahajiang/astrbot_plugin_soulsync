"""EmotionAI Pro - 长期记忆管理器（落盘存储重要情感事件）"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List


class LongTermMemory:
    """
    长期记忆：落盘存储重要情感事件。
    每个用户维护一个事件队列，跨重启保留。
    """

    def __init__(self, data_dir: Path, max_events_per_user: int = 50):
        self.data_dir = data_dir / "long_term_memory"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_events = max_events_per_user
        self._memory: Dict[str, List[dict]] = {}
        self._load_all()

    def add_event(self, user_id: str, event: dict):
        """添加一条重要情感事件"""
        if user_id not in self._memory:
            self._memory[user_id] = []

        event["ts"] = time.time()
        self._memory[user_id].append(event)

        # 超过上限则淘汰最旧的
        if len(self._memory[user_id]) > self.max_events:
            self._memory[user_id] = self._memory[user_id][-self.max_events:]

        self._save_user(user_id)

    def get_events(self, user_id: str, limit: int = 10) -> List[dict]:
        """获取最近 N 条事件"""
        events = self._memory.get(user_id, [])
        return events[-limit:]

    def get_summary(self, user_id: str) -> str:
        """生成用户情感记忆摘要（供 LLM 参考）"""
        events = self.get_events(user_id, 5)
        if not events:
            return "暂无长期记忆。"

        lines = []
        for e in events:
            ts_str = time.strftime("%m-%d %H:%M", time.localtime(e.get("ts", 0)))
            fav = e.get("favorability", "?")
            stage = e.get("stage", "")
            desc = e.get("description", "")
            lines.append(f"[{ts_str}] 好感={fav} {stage} | {desc}")
        return "\n".join(lines)

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
