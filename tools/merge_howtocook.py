# -*- coding: utf-8 -*-
"""将 HowToCook_json（程序员做饭指南）菜谱合并进插件 recipes.json。

用法：python tools/merge_howtocook.py <howtocook目录> [recipes.json]

- 源数据字段：name/category/difficulty/ingredients[{ingredient_name,quantity,unit,is_optional}]/steps[{content,tips}]/tips
- 转换后与 recipes.json 同构，按菜名去重（保留现有库优先）
- difficulty 映射：easy→简单, medium→普通, hard→困难
"""

import json
import sys
from collections import OrderedDict
from pathlib import Path

MEAT_KEYWORDS = (
    "肉", "鸡", "牛", "猪", "虾", "鱼", "蛋", "腊肠", "午餐肉",
    "骨", "香肠", "火腿", "培根", "鸭",
)

SPICY_KEYWORDS = ("辣", "麻", "花椒", "麻辣", "香辣", "辣椒")

DIFF_MAP = {"easy": "简单", "medium": "普通", "hard": "困难"}


def _ingredient_str(ing) -> str:
    name = (ing.get("ingredient_name") or "").strip()
    qty = ing.get("quantity")
    unit = (ing.get("unit") or "").strip()
    if not name:
        return ""
    if qty is not None and str(qty) != "":
        return f"{name} {qty}{unit}".strip()
    return name


def _is_spicy(text: str) -> bool:
    return any(kw in text for kw in SPICY_KEYWORDS)


def _is_vegetarian(category: str, ingredients: str) -> bool:
    if category == "素菜":
        return True
    return not any(kw in ingredients for kw in MEAT_KEYWORDS)


def convert(src_dir: Path, out_path: Path, existing_path: Path):
    existing = json.loads(existing_path.read_text(encoding="utf-8"))
    existing_names = {r["name"] for r in existing}
    added, skipped = [], []

    for f in sorted(src_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"跳过 {f.name}: {e}")
            continue
        name = (data.get("name") or "").strip()
        if not name or name in existing_names:
            skipped.append(name or f.stem)
            continue

        ingredients = [_ingredient_str(i) for i in data.get("ingredients", [])]
        ingredients = [i for i in ingredients if i]
        steps = []
        for s in data.get("steps", []) or []:
            content = (s.get("content") or "").strip()
            if not content:
                continue
            tip = (s.get("tips") or "").strip()
            if tip:
                content = f"{content}（{tip}）"
            steps.append(content)
        if not steps and data.get("tips"):
            steps = [t.strip() for t in data["tips"] if t.strip()]

        all_text = name + "".join(ingredients)
        category = (data.get("category") or "家常菜").strip()
        if category not in ("素菜", "荤菜"):
            category = "素菜" if _is_vegetarian(category, all_text) else "荤菜"
        difficulty = DIFF_MAP.get((data.get("difficulty") or "").lower(), "普通")

        recipe = OrderedDict([
            ("name", name),
            ("category", category),
            ("ingredients", ingredients),
            ("steps", steps),
            ("tags", []),
            ("methods", []),
            ("tools", []),
            ("difficulty", difficulty),
            ("bv", ""),
            ("spicy", _is_spicy(all_text)),
            ("vegetarian", category == "素菜"),
            ("mood_hint", []),
        ])
        added.append(recipe)
        existing_names.add(name)

    merged = existing + added
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"现有 {len(existing)} 道, 新增 {len(added)} 道, 跳过重复 {len(skipped)} 道")
    print(f"合并后共 {len(merged)} 道 -> {out_path} ({out_path.stat().st_size // 1024} KB)")
    if skipped:
        print("重复样例:", skipped[:20])


if __name__ == "__main__":
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("recipes.json")
    convert(src, out, out)
