"""storage/schema.py - SQLite 表结构定义与自动建表

Sprint 1 S1-02 产出物。
月度分表自动创建（daily_snapshot_YYYYMM）及 user_profile 主表。

用法:
    from storage.schema import init_schema
    init_schema(conn)  # 建表（幂等）
"""

from __future__ import annotations

import sqlite3
from datetime import date

# ─── 主表 DDL ────────────────────────────────────────────────

_USER_PROFILE_DDL = """
CREATE TABLE IF NOT EXISTS user_profile (
    user_id         TEXT PRIMARY KEY,
    favorability    REAL DEFAULT 0,
    intimacy        REAL DEFAULT 0,
    stage_index     INTEGER DEFAULT 0,
    stage_label     TEXT DEFAULT '',
    attitude_text   TEXT DEFAULT '',
    relationship_text TEXT DEFAULT '',
    total_interactions INTEGER DEFAULT 0,
    positive_interactions INTEGER DEFAULT 0,
    negative_interactions INTEGER DEFAULT 0,
    conversation_turns INTEGER DEFAULT 0,
    first_interaction_ts REAL DEFAULT 0,
    last_interaction_ts  REAL DEFAULT 0,
    created_at      REAL DEFAULT 0,
    updated_at      REAL DEFAULT 0
);
"""

_BEHAVIOR_PROFILE_DDL = """
CREATE TABLE IF NOT EXISTS behavior_profile (
    user_id             TEXT PRIMARY KEY,
    current_streak_type TEXT DEFAULT '',
    current_streak_count INTEGER DEFAULT 0,
    total_reward_accumulated REAL DEFAULT 0,
    total_penalty_accumulated REAL DEFAULT 0,
    betrayal_count      INTEGER DEFAULT 0,
    apology_count       INTEGER DEFAULT 0,
    comeback_count      INTEGER DEFAULT 0,
    last_interaction_ts REAL DEFAULT 0,
    last_betrayal_ts    REAL DEFAULT 0,
    last_apology_ts     REAL DEFAULT 0,
    last_comeback_ts    REAL DEFAULT 0,
    last_active_date    TEXT DEFAULT '',
    cold_days           INTEGER DEFAULT 0,
    penalty_last_date   TEXT DEFAULT '',
    penalty_frozen_until REAL DEFAULT 0,
    achieved_milestones TEXT DEFAULT '[]',
    crisis_active       INTEGER DEFAULT 0,
    crisis_type         TEXT DEFAULT '',
    crisis_started_ts   REAL DEFAULT 0,
    crisis_last_event_ts REAL DEFAULT 0,
    crisis_resolved_count INTEGER DEFAULT 0,
    crisis_cooldown_until REAL DEFAULT 0,
    crisis_protection_until REAL DEFAULT 0,
    pending_effects     TEXT DEFAULT '[]',
    countdown_last_date TEXT DEFAULT '',
    monthly_report_last TEXT DEFAULT '',
    role_report_last_ts REAL DEFAULT 0,
    time_jump_last_ts   REAL DEFAULT 0,
    rde_stage_ctx_last_round INTEGER DEFAULT 0,
    extra_json          TEXT DEFAULT '{}',
    created_at          REAL DEFAULT 0,
    updated_at          REAL DEFAULT 0
);
"""

_SHOW_STATUS_DDL = """
CREATE TABLE IF NOT EXISTS show_status (
    user_id TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 0
);
"""

_IMAGE_MODE_DDL = """
CREATE TABLE IF NOT EXISTS image_mode (
    user_id TEXT PRIMARY KEY,
    enabled INTEGER DEFAULT 0
);
"""

_LONG_TERM_MEMORY_DDL = """
CREATE TABLE IF NOT EXISTS long_term_memory (
    user_id     TEXT NOT NULL,
    ts          REAL NOT NULL,
    description TEXT DEFAULT '',
    message     TEXT DEFAULT '',
    emotions    TEXT DEFAULT '{}',
    favorability REAL DEFAULT 0,
    fav_delta   REAL DEFAULT 0,
    stage       TEXT DEFAULT '',
    vividness   REAL DEFAULT 100,
    last_recalled_ts REAL DEFAULT 0,
    important   INTEGER DEFAULT 0,
    compressed  INTEGER DEFAULT 0,
    created_at  REAL DEFAULT 0,
    PRIMARY KEY (user_id, ts)
);
"""

_ANNIVERSARY_DDL = """
CREATE TABLE IF NOT EXISTS anniversaries (
    user_id     TEXT NOT NULL,
    anniv_id    TEXT NOT NULL,
    name        TEXT DEFAULT '',
    date_str    TEXT DEFAULT '',
    anniv_type  TEXT DEFAULT '',
    created_at  REAL DEFAULT 0,
    PRIMARY KEY (user_id, anniv_id)
);
"""

_RELATIONSHIP_ROLE_DDL = """
CREATE TABLE IF NOT EXISTS relationship_role (
    user_id         TEXT PRIMARY KEY,
    role_id         TEXT DEFAULT '',
    role_name       TEXT DEFAULT '',
    unlocked        INTEGER DEFAULT 0,
    switched        INTEGER DEFAULT 0,
    custom_attitude TEXT DEFAULT '',
    custom_relationship TEXT DEFAULT '',
    extra_json      TEXT DEFAULT '{}',
    updated_at      REAL DEFAULT 0
);
"""

_CHARACTER_DDL = """
CREATE TABLE IF NOT EXISTS characters (
    user_id     TEXT NOT NULL,
    char_id     TEXT NOT NULL,
    name        TEXT DEFAULT '',
    emoji       TEXT DEFAULT '',
    personality TEXT DEFAULT '',
    is_active   INTEGER DEFAULT 0,
    extra_json  TEXT DEFAULT '{}',
    created_at  REAL DEFAULT 0,
    PRIMARY KEY (user_id, char_id)
);
"""

_LEADERBOARD_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS leaderboard_cache (
    rank_type   TEXT NOT NULL,   -- 'favorability' | 'negative_favorability'
    rank        INTEGER NOT NULL,
    user_id     TEXT NOT NULL,
    user_name   TEXT DEFAULT '',
    favorability REAL DEFAULT 0,
    intimacy    REAL DEFAULT 0,
    stage_label TEXT DEFAULT '',
    updated_at  REAL DEFAULT 0,
    PRIMARY KEY (rank_type, rank)
);
"""

_SYSTEM_STATS_DDL = """
CREATE TABLE IF NOT EXISTS system_stats (
    stat_key    TEXT PRIMARY KEY,
    stat_value  TEXT DEFAULT '',
    updated_at  REAL DEFAULT 0
);
"""

# ─── 月度快照表（动态创建）────────────────────────────────────

_SNAPSHOT_TABLE_TEMPLATE = """
CREATE TABLE IF NOT EXISTS {table_name} (
    user_id         TEXT NOT NULL,
    date            TEXT NOT NULL,
    fav             REAL DEFAULT 0,
    int             REAL DEFAULT 0,
    stage           INTEGER DEFAULT 0,
    stage_label     TEXT DEFAULT '',
    interactions    INTEGER DEFAULT 0,
    positive        INTEGER DEFAULT 0,
    negative        INTEGER DEFAULT 0,
    turns           INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, date)
);
"""

# ─── 索引 ────────────────────────────────────────────────────

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_ltm_user ON long_term_memory(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_ltm_ts ON long_term_memory(ts);",
    "CREATE INDEX IF NOT EXISTS idx_ltm_vivid ON long_term_memory(user_id, vividness);",
    "CREATE INDEX IF NOT EXISTS idx_snapshot_user ON daily_snapshot(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_snapshot_date ON daily_snapshot(date);",
    "CREATE INDEX IF NOT EXISTS idx_anniv_user ON anniversaries(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_char_user ON characters(user_id);",
]


def init_schema(conn: sqlite3.Connection):
    """初始化全部表结构（幂等，重复调用安全）"""
    for ddl in [
        _USER_PROFILE_DDL,
        _BEHAVIOR_PROFILE_DDL,
        _SHOW_STATUS_DDL,
        _IMAGE_MODE_DDL,
        _LONG_TERM_MEMORY_DDL,
        _ANNIVERSARY_DDL,
        _RELATIONSHIP_ROLE_DDL,
        _CHARACTER_DDL,
        _LEADERBOARD_CACHE_DDL,
        _SYSTEM_STATS_DDL,
    ]:
        conn.execute(ddl)

    # 默认月度快照表
    today = date.today()
    ensure_snapshot_table(conn, today.year, today.month)

    for idx in _INDEXES:
        try:
            conn.execute(idx)
        except Exception:
            pass  # 部分索引可能因表不存在而失败，忽略

    conn.commit()


def ensure_snapshot_table(conn: sqlite3.Connection, year: int, month: int):
    """确保指定月份的快照表存在"""
    table_name = f"daily_snapshot_{year:04d}{month:02d}"
    conn.execute(_SNAPSHOT_TABLE_TEMPLATE.format(table_name=table_name))
    conn.commit()
    return table_name


def get_snapshot_table(year: int, month: int) -> str:
    """获取月份快照表名"""
    return f"daily_snapshot_{year:04d}{month:02d}"


# ─── 查询所有快照表 ──────────────────────────────────────────

def list_snapshot_tables(conn: sqlite3.Connection) -> list[str]:
    """列出所有已存在的快照表"""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'daily_snapshot_%'"
    )
    return [row["name"] for row in cursor.fetchall()]
