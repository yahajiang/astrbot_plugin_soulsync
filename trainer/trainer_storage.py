"""SoulSync - 统一存储管理器"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, Optional


class TrainerStorage:
    """统一存储管理器：管理 personalization/{user_id}/ 目录的 JSON 读写"""

    VERSION = 1

    def __init__(self, base_dir: Path, max_total_mb: float = 5.0):
        self.base_dir = Path(base_dir) / "personalization"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.max_total_bytes = int(max_total_mb * 1024 * 1024)
        self._locks: Dict[str, threading.Lock] = {}

    # ── 路径 ──
    def _user_dir(self, user_id: str) -> Path:
        d = self.base_dir / user_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _path(self, user_id: str, filename: str) -> Path:
        return self._user_dir(user_id) / filename

    # ── 读写 ──
    def load(self, user_id: str, filename: str, default: Any = None) -> Any:
        p = self._path(user_id, filename)
        if not p.exists():
            return default
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return default

    def save(self, user_id: str, filename: str, data: Any) -> bool:
        lock = self._locks.setdefault(f"{user_id}/{filename}", threading.Lock())
        with lock:
            p = self._path(user_id, filename)
            bak = p.with_suffix(".bak")
            try:
                if p.exists():
                    shutil.copy2(p, bak)
                tmp = p.with_suffix(".tmp")
                tmp.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                tmp.replace(p)
                self._enforce_capacity()
                return True
            except Exception:
                if bak.exists():
                    shutil.copy2(bak, p)
                return False

    # ── 容量控制 ──
    def _enforce_capacity(self):
        total = sum(f.stat().st_size for f in self.base_dir.rglob("*") if f.is_file())
        if total <= self.max_total_bytes:
            return
        files = sorted(self.base_dir.rglob("*.bak"), key=lambda p: p.stat().st_mtime)
        for f in files:
            if total <= self.max_total_bytes:
                break
            try:
                sz = f.stat().st_size
                f.unlink()
                total -= sz
            except Exception:
                pass

    # ── 版本检查 ──
    def ensure_version(self, user_id: str, filename: str):
        data = self.load(user_id, filename)
        if isinstance(data, dict) and data.get("_version") == self.VERSION:
            return data
        if data is not None:
            data = {"_version": self.VERSION, "data": data}
        else:
            data = {"_version": self.VERSION, "data": {}}
        self.save(user_id, filename, data)
        return data

    # ── 删除 ──
    def clear_user(self, user_id: str):
        d = self._user_dir(user_id)
        if d.exists():
            shutil.rmtree(d)

    # ── 统计 ──
    def total_size(self) -> int:
        return sum(f.stat().st_size for f in self.base_dir.rglob("*") if f.is_file())

    def user_exists(self, user_id: str) -> bool:
        return self._user_dir(user_id).exists()