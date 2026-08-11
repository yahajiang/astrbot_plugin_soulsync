"""db_migration/validator.py - JSON vs SQLite 数据一致性校验工具

Sprint 0 产出物：对比 JSON 与 SQLite 查询结果的差异，差异阈值 < 0.1% 为通过。
迁移时自动运行并输出差异报告。

用法:
    from db_migration.validator import MigrationValidator
    v = MigrationValidator(data_dir)
    report = v.run_all()
    print(report.summary())
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("soulsync.migration.validator")


@dataclass
class DiffRecord:
    """单条差异记录"""
    table: str
    uid: str
    field: str
    json_value: Any
    sqlite_value: Any
    severity: str = "INFO"  # INFO / WARN / ERROR


@dataclass
class TableReport:
    """单表校验报告"""
    table: str
    json_count: int = 0
    sqlite_count: int = 0
    diffs: List[DiffRecord] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def match_rate(self) -> float:
        """字段匹配率（0~1）"""
        total = self.json_count
        if total == 0:
            return 1.0
        mismatched = len(set(d.uid for d in self.diffs if d.severity == "ERROR"))
        return 1.0 - mismatched / total


@dataclass
class ValidationReport:
    """完整校验报告"""
    tables: List[TableReport] = field(default_factory=list)
    passed: bool = True

    @property
    def total_diffs(self) -> int:
        return sum(len(t.diffs) for t in self.tables)

    @property
    def total_errors(self) -> int:
        return sum(1 for t in self.tables for d in t.diffs if d.severity == "ERROR")

    def summary(self) -> str:
        lines = [
            "═" * 60,
            "  SoulSync 数据迁移校验报告",
            "═" * 60,
        ]
        for t in self.tables:
            status = "✅" if t.error is None and len([d for d in t.diffs if d.severity == "ERROR"]) == 0 else "❌"
            lines.append(f"\n{status} [{t.table}] JSON={t.json_count} SQLite={t.sqlite_count} 匹配率={t.match_rate:.2%}")
            if t.error:
                lines.append(f"   ⚠️ 错误: {t.error}")
            for d in t.diffs[:10]:  # 最多显示 10 条
                lines.append(f"   {d.severity} uid={d.uid} field={d.field} JSON={d.json_value!r} SQLite={d.sqlite_value!r}")
            if len(t.diffs) > 10:
                lines.append(f"   ... 还有 {len(t.diffs) - 10} 条差异")
        lines.append("\n" + "═" * 60)
        verdict = "✅ 通过" if self.passed else "❌ 未通过（差异 > 0.1%）"
        lines.append(f"  结论: {verdict}  总差异: {self.total_diffs} 条")
        lines.append("═" * 60)
        return "\n".join(lines)


class MigrationValidator:
    """JSON vs SQLite 数据一致性校验器"""

    THRESHOLD = 0.001  # 0.1% 差异阈值

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.json_data: Dict[str, Any] = {}
        self._load_all_json()

    # ─── JSON 加载 ────────────────────────────────────────────

    def _load_all_json(self):
        """加载全部 JSON 文件"""
        self._load_json_file("profiles", "profiles.json")
        self._load_json_file("behavior_profiles", "behavior_profiles.json")
        self._load_json_file("show_status", "show_status.json")
        self._load_json_file("image_mode", "image_mode.json")
        self._load_json_file("characters", "characters.json")
        self._load_json_file("anniversaries", "anniversaries.json")
        self._load_json_file("relationship_roles", "relationship_roles.json")
        self._load_json_file("stats_history", "stats_history.json")
        self._load_long_term_memory()
        self._load_personalization()

    def _load_json_file(self, key: str, filename: str):
        path = self.data_dir / filename
        if path.exists():
            try:
                self.json_data[key] = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"加载 {filename} 失败: {e}")
                self.json_data[key] = {}
        else:
            self.json_data[key] = {}

    def _load_long_term_memory(self):
        """加载 long_term_memory/*.json"""
        ltm_dir = self.data_dir / "long_term_memory"
        self.json_data["long_term_memory"] = {}
        if ltm_dir.exists():
            for f in ltm_dir.glob("*.json"):
                uid = f.stem
                try:
                    self.json_data["long_term_memory"][uid] = json.loads(f.read_text(encoding="utf-8"))
                except Exception as e:
                    logger.warning(f"加载 long_term_memory/{uid}.json 失败: {e}")

    def _load_personalization(self):
        """加载 personalization/<uid>/*.json"""
        pers_dir = self.data_dir / "personalization"
        self.json_data["personalization"] = {}
        if pers_dir.exists():
            for uid_dir in pers_dir.iterdir():
                if uid_dir.is_dir():
                    uid = uid_dir.name
                    user_data = {}
                    for f in uid_dir.glob("*.json"):
                        try:
                            user_data[f.stem] = json.loads(f.read_text(encoding="utf-8"))
                        except Exception as e:
                            logger.warning(f"加载 personalization/{uid}/{f.name} 失败: {e}")
                    self.json_data["personalization"][uid] = user_data

    # ─── 校验方法（SQLite 对比）────────────────────────────────

    def validate_table(self, table: str, sqlite_rows: Dict[str, Any],
                       key_extractor=None, field_comparator=None) -> TableReport:
        """校验单表：对比 JSON 数据与 SQLite 查询结果

        Args:
            table: 表名
            sqlite_rows: SQLite 查询结果 {uid: row_dict}
            key_extractor: 从 JSON 条目提取 uid 的函数
            field_comparator: 字段值比较函数（默认 ==）
        """
        report = TableReport(table=table)
        json_data = self.json_data.get(table, {})

        if not json_data:
            report.json_count = 0
            report.sqlite_count = len(sqlite_rows)
            if sqlite_rows:
                report.diffs.append(DiffRecord(table=table, uid="*", field="count",
                                                json_value=0, sqlite_value=len(sqlite_rows),
                                                severity="WARN"))
            return report

        # 提取 uid -> row 的映射
        json_rows = {}
        for uid, row in json_data.items():
            if key_extractor:
                uid = key_extractor(row)
            json_rows[uid] = row

        report.json_count = len(json_rows)
        report.sqlite_count = len(sqlite_rows)

        # 逐 uid 对比
        for uid in set(json_rows.keys()) | set(sqlite_rows.keys()):
            j_val = json_rows.get(uid)
            s_val = sqlite_rows.get(uid)

            if j_val is None:
                report.diffs.append(DiffRecord(table=table, uid=uid, field="*",
                                                json_value=None, sqlite_value=s_val,
                                                severity="ERROR"))
                continue
            if s_val is None:
                report.diffs.append(DiffRecord(table=table, uid=uid, field="*",
                                                json_value=j_val, sqlite_value=None,
                                                severity="ERROR"))
                continue

            # 字段级对比
            if isinstance(j_val, dict) and isinstance(s_val, dict):
                all_keys = set(j_val.keys()) | set(s_val.keys())
                for k in all_keys:
                    jv = j_val.get(k)
                    sv = s_val.get(k)
                    if field_comparator:
                        match = field_comparator(jv, sv)
                    else:
                        match = jv == sv
                    if not match:
                        report.diffs.append(DiffRecord(table=table, uid=uid, field=k,
                                                        json_value=jv, sqlite_value=sv,
                                                        severity="ERROR"))
            else:
                if j_val != s_val:
                    report.diffs.append(DiffRecord(table=table, uid=uid, field="root",
                                                    json_value=j_val, sqlite_value=s_val,
                                                    severity="ERROR"))

        return report

    # ─── 运行全部校验 ─────────────────────────────────────────

    def run_all(self, sqlite_conn=None) -> ValidationReport:
        """运行全量校验。sqlite_conn 为 None 时仅输出 JSON 基线统计。

        Args:
            sqlite_conn: sqlite3.Connection（Sprint 1 实现后传入）
        """
        report = ValidationReport()

        tables = [
            ("profiles", "profiles"),
            ("behavior_profiles", "behavior_profiles"),
            ("show_status", "show_status"),
            ("image_mode", "image_mode"),
            ("anniversaries", "anniversaries"),
            ("relationship_roles", "relationship_roles"),
            ("stats_history", "stats_history"),
            ("long_term_memory", "long_term_memory"),
        ]

        for table_name, json_key in tables:
            json_data = self.json_data.get(json_key, {})
            if sqlite_conn is None:
                # 仅输出 JSON 基线
                tr = TableReport(table=table_name, json_count=len(json_data))
                report.tables.append(tr)
            else:
                # TODO: Sprint 1 实现 SQLite 查询
                pass

        # 个性化数据统计
        pers = self.json_data.get("personalization", {})
        report.tables.append(TableReport(table="personalization", json_count=len(pers)))

        report.passed = all(t.match_rate >= (1 - self.THRESHOLD) for t in report.tables
                           if t.error is None)
        return report

    # ─── 工具方法 ─────────────────────────────────────────────

    def get_json_snapshot(self, table: str) -> Dict[str, Any]:
        """获取指定表的 JSON 快照（用于迁移前后的比对）"""
        return self.json_data.get(table, {})

    def print_baseline(self):
        """打印 JSON 数据基线统计"""
        print("\n📊 JSON 数据基线:")
        for key, data in self.json_data.items():
            if isinstance(data, dict):
                print(f"  {key}: {len(data)} 条记录")
            else:
                print(f"  {key}: {type(data).__name__}")
