# -*- coding: utf-8 -*-
"""多角色并行关系管理（v2.16 P14）：同一用户可与多位 AI 角色并行发展关系。
角色状态按 key = uid(::cid) 隔离；用户的时间线（纪念日/统计/关系角色）按 raw uid 共享。
cid 为空字符串表示「默认角色」，与旧版本数据完全兼容。"""
import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_CID = ""


class CharacterManager:
    """角色分配器：维护每个用户当前激活的角色（default 为空 cid），
    以及用户自建角色（name/emoji/persona/system）"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._active: Dict[str, str] = {}            # uid -> cid（空=默认角色）
        self._custom: Dict[str, Dict[str, dict]] = {}  # uid -> {cid: {name, emoji, persona, system, created_ts}}
        self._load()

    # ── 持久化 ──
    def _load(self):
        f = self.data_dir / "characters.json"
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                self._active = data.get("active", {})
                self._custom = data.get("custom", {})
            except Exception:
                pass

    def save(self):
        try:
            (self.data_dir / "characters.json").write_text(
                json.dumps({"active": self._active, "custom": self._custom},
                           ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ── 激活角色 ──
    def active_cid(self, uid: str) -> str:
        return self._active.get(uid, DEFAULT_CID)

    def set_active(self, uid: str, cid: str) -> str:
        self._active[uid] = cid
        self.save()
        return cid

    def state_key(self, uid: str, enabled: bool = True) -> str:
        """档案状态键：启用多角色且当前非默认 → uid::cid，否则原样 uid"""
        cid = self.active_cid(uid) if enabled else DEFAULT_CID
        return f"{uid}::{cid}" if cid else uid

    def role_info(self, uid: str) -> dict:
        """当前激活角色的展示信息（默认角色返回占位）"""
        cid = self.active_cid(uid)
        if not cid:
            return {"cid": DEFAULT_CID, "name": "默认", "emoji": "💠",
                    "persona": "", "system": ""}
        info = self._custom.get(uid, {}).get(cid)
        return info or {"cid": cid, "name": cid, "emoji": "🎭",
                        "persona": "", "system": ""}

    # ── 自定义角色 ──
    def create(self, uid: str, name: str, emoji: str = "🎭",
               persona: str = "", system: str = "",
               relations: Optional[dict] = None) -> Tuple[str, str]:
        """创建自定义角色，返回 (cid, 提示文本)

        relations: 角色卡关系网定义（RDE 多角色关系网扩展字段）
        {"角色名": {"type": "...", "cross_coefficient": 0.1, "description": "..."}}
        """
        name = (name or "").strip()[:20]
        if not name:
            return "", "❌ 角色名不能为空"
        bucket = self._custom.setdefault(uid, {})
        if any(v.get("name") == name for v in bucket.values()):
            return "", f"❌ 角色「{name}」已存在"
        cid = uuid.uuid4().hex[:8]
        bucket[cid] = {
            "name": name, "emoji": (emoji or "🎭").strip()[:4] or "🎭",
            "persona": (persona or "").strip()[:200],
            "system": (system or "").strip()[:400],
            "relations": relations if isinstance(relations, dict) else {},
            "created_ts": time.time(),
        }
        self.set_active(uid, cid)
        return cid, f"✅ 已创建角色「{emoji or '🎭'} {name}」并切换过去"

    def get_relations(self, uid: str, cid: Optional[str] = None) -> dict:
        """读取角色卡关系网定义（无则空 dict）"""
        cid = cid if cid is not None else self.active_cid(uid)
        info = self._custom.get(uid, {}).get(cid) or {}
        rel = info.get("relations")
        return rel if isinstance(rel, dict) else {}

    def remove(self, uid: str, cid: str) -> Tuple[bool, str]:
        bucket = self._custom.get(uid, {})
        if cid not in bucket:
            return False, "❌ 未找到该角色"
        del bucket[cid]
        if self._active.get(uid) == cid:
            self._active[uid] = DEFAULT_CID
        self.save()
        return True, "🗑️ 已删除角色并回到默认角色"

    def list_for(self, uid: str) -> List[dict]:
        """用户可见角色列表：默认角色排最前，后接自建角色"""
        rows = [{"cid": DEFAULT_CID, "name": "默认", "emoji": "💠",
                 "active": self.active_cid(uid) == DEFAULT_CID}]
        for cid, v in self._custom.get(uid, {}).items():
            rows.append({
                "cid": cid, "name": v.get("name", cid),
                "emoji": v.get("emoji", "🎭"),
                "active": self.active_cid(uid) == cid,
            })
        return rows

    def find_cid(self, uid: str, text: str) -> Optional[str]:
        """按名称（或 cid 前 8 位）查找角色 cid；"默认" 返回默认角色"""
        text = (text or "").strip()
        if text in ("默认", "默认角色", "default"):
            return DEFAULT_CID
        for cid, v in self._custom.get(uid, {}).items():
            if v.get("name") == text or cid == text:
                return cid
        return None
