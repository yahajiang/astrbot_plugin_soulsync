# -*- coding: utf-8 -*-
"""v1.10 数据补全：为 tags <=1 的稀疏菜补做法/场景标签（规则推断，幂等）。

用法：
  python tools/backfill_tags.py            # DRY-RUN 预览统计
  python tools/backfill_tags.py --write    # 写回 recipes.json
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).resolve().parent.parent
RECIPES = BASE / "recipes.json"

# 做法规则：(名称关键词, 标签)；长关键词在前，避免「红烧」被「炒」误判
METHOD_RULES = (
    (("红烧", "酱爆"), "红烧"),
    (("凉拌", "沙拉", "炝"), "凉拌"),
    (("卤",), "卤味"),
    (("泡菜", "酱菜", "腌菜", "腊肉"), "腌菜"),
    (("煲",), "煲汤"),
    (("粉蒸", "清蒸", "蒸"), "蒸菜"),
    (("煨", "炖"), "炖菜"),
    (("天妇罗", "吉列", "炸"), "炸物"),
    (("烧烤", "焗", "烤"), "烧烤"),
    (("锅贴", "烙", "煎"), "煎烙"),
    (("爆炒", "熘", "炒"), "炒菜"),
)

# 名称含这些词不算炸物/煲汤（如炸酱面、煲仔饭、空气炸锅、电饭煲）
METHOD_EXEMPT = {
    "炸物": ("炸酱", "空气炸锅"),
    "煲汤": ("煲仔", "电饭煲", "电饭锅"),
}

# 场景补全：仅稀疏菜
SCENE_RULES = (
    ("下酒", lambda r: r.get("category") == "凉菜"),
    (
        "夜宵",
        lambda r: any(
            k in str(r.get("name", ""))
            for k in ("烧烤", "烤串", "炸串", "麻辣烫", "卤味", "鸭脖", "小龙虾", "螺蛳粉", "关东煮", "炸鸡", "臭豆腐")
        ),
    ),
    (
        "早餐",
        lambda r: r.get("category") in ("主食", "粥羹")
        and any(k in str(r.get("name", "")) for k in ("粥", "馄饨", "包子", "馒头", "煎饼", "油条")),
    ),
    (
        "懒人",
        lambda r: any(
            k in str(r.get("name", ""))
            for k in ("电饭煲", "电饭锅", "微波炉", "空气炸锅", "懒人", "速食", "自热", "焖饭", "快手")
        ),
    ),
)


def method_of(name: str) -> list:
    tags = []
    for kws, tag in METHOD_RULES:
        if not any(k in name for k in kws):
            continue
        exempt = METHOD_EXEMPT.get(tag, ())
        if any(e in name for e in exempt):
            continue
        tags.append(tag)
    return tags


def main():
    dry = "--write" not in sys.argv
    data = json.loads(RECIPES.read_text(encoding="utf-8"))
    changed = 0
    added = 0
    stat = {}
    for r in data:
        if len(r.get("tags", [])) > 1:
            continue
        tags = list(r.get("tags", []))
        new = []
        for t in method_of(str(r.get("name", ""))):
            if t not in tags and t not in new:
                new.append(t)
        for t, cond in SCENE_RULES:
            if cond(r) and t not in tags and t not in new:
                new.append(t)
        if not new:
            continue
        changed += 1
        added += len(new)
        for t in new:
            stat[t] = stat.get(t, 0) + 1
        if not dry:
            r["tags"] = tags + new

    print(f"模式: {'DRY-RUN（仅预览）' if dry else '写回 recipes.json'}")
    print(f"补全菜数: {changed} / 4000，新增标签数: {added}")
    print("新增标签分布:", dict(sorted(stat.items(), key=lambda x: -x[1])))
    sparse_after = sum(1 for r in data if len(r.get("tags", [])) <= 1)
    print(f"补全后稀疏菜(<=1 tag): {sparse_after}")
    if not dry:
        RECIPES.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print("已写回 recipes.json。")


if __name__ == "__main__":
    main()
