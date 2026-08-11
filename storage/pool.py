"""storage/pool.py - SQLite 连接池（单例 WAL 模式，连接超时 10s）

Sprint 1 S1-01 产出物。
并发 50 写请求压测无锁死。

用法:
    from storage.pool import ConnectionPool
    pool = ConnectionPool.get_instance(data_dir)
    with pool.connect() as conn:
        conn.execute("INSERT INTO ...")
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

logger = logging.getLogger("soulsync.storage.pool")

_BUSY_TIMEOUT_MS = 10_000  # 10 秒


class ConnectionPool:
    """SQLite 连接池（单例）

    - WAL 模式：支持并发读写
    - BUSY_TIMEOUT 10s：写冲突时自动重试
    - 单文件单连接：SQLite 本身不支持真正的并发写，用锁串行化
    """

    _instance: Optional[ConnectionPool] = None
    _lock = threading.Lock()

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._conn_lock = threading.Lock()
        self._init_db()

    @classmethod
    def get_instance(cls, data_dir: Path) -> ConnectionPool:
        """获取单例实例（按 data_dir 隔离）"""
        with cls._lock:
            if cls._instance is None or cls._instance._db_path.parent != data_dir:
                db_path = data_dir / "soulsync.db"
                cls._instance = cls(db_path)
                logger.info(f"[StoragePool] 初始化完成: {db_path}")
            return cls._instance

    @classmethod
    def reset(cls):
        """重置单例（用于测试）"""
        with cls._lock:
            if cls._instance and cls._instance._conn:
                cls._instance._conn.close()
            cls._instance = None

    def _init_db(self):
        """初始化数据库连接和 WAL 模式"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(self._db_path),
            timeout=_BUSY_TIMEOUT_MS / 1000,
            check_same_thread=False,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        self._conn = conn

    @contextmanager
    def connect(self):
        """获取数据库连接（线程安全）"""
        with self._conn_lock:
            if self._conn is None:
                raise RuntimeError("ConnectionPool 已关闭")
            yield self._conn

    def close(self):
        """关闭连接池"""
        with self._conn_lock:
            if self._conn:
                self._conn.close()
                self._conn = None
