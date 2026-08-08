# -*- coding: utf-8 -*-
"""将手写新菜数据合并进 recipes.json。

用法：python tools/add_recipes.py <新菜文件1> [新菜文件2 ...]

- 新菜文件为 JSON 数组，元素与 recipes.json 同构（含手写详细 steps）
- 按菜名去重（现有库优先，重复跳过）
- 写入前做字段完整性校验，非法条目跳过并打印原因
- 校验通过后写回 recipes.json（indent=1, ensure_ascii=False）
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RECIPES_PATH = BASE_DIR / "recipes.json"

REQUIRED_KEYS = (
    "name", "category", "ingredients", "steps", "tags", "methods",
    "tools", "difficulty", "bv", "spicy", "vegetarian", "mood_hint",
)
ALLOWED_CATEGORIES = {"主食", "汤羹", "粥羹", "素菜", "荤菜", "凉菜", "甜品零食"}
ALLOWED_DIFFICULTY = {"简单", "普通", "困难"}
ALLOWED_MOODS = {"喜悦", "悲伤", "愤怒", "焦虑", "期待"}


def validate(recipe: dict, src_name: str) -> list:
    """返回错误列表；为空表示通过。"""
    errors = []
    name = recipe.get("name")
    for k in REQUIRED_KEYS:
        if k not in recipe:
            errors.append(f"缺字段 {k}")
    if not name or not str(name).strip():
        errors.append("name 为空")
    if recipe.get("category") not in ALLOWED_CATEGORIES:
        errors.append(f"category 非法: {recipe.get('category')!r}")
    if not recipe.get("ingredients"):
        errors.append("ingredients 为空")
    if len(recipe.get("steps", [])) < 3:
        errors.append(f"steps 少于 3 条: {len(recipe.get('steps', []))}")
    if not isinstance(recipe.get("spicy"), bool):
        errors.append("spicy 必须为 bool")
    if not isinstance(recipe.get("vegetarian"), bool):
        errors.append("vegetarian 必须为 bool")
    if recipe.get("difficulty") not in ALLOWED_DIFFICULTY:
        errors.append(f"difficulty 非法: {recipe.get('difficulty')!r}")
    for m in recipe.get("mood_hint", []):
        if m not in ALLOWED_MOODS:
            errors.append(f"mood_hint 非法: {m!r}")
    if errors:
        print(f"[跳过] {src_name} / {name or '?'}: {'; '.join(errors)}")
    return errors


def main():
    if len(sys.argv) < 2:
        print("用法: python tools/add_recipes.py <新菜文件1> [新菜文件2 ...]")
        sys.exit(1)

    existing = json.loads(RECIPES_PATH.read_text(encoding="utf-8"))
    existing_names = {r["name"] for r in existing}
    added, skipped = [], []

    for arg in sys.argv[1:]:
        p = Path(arg)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[错误] {p.name}: {e}")
            continue
        if not isinstance(data, list):
            print(f"[错误] {p.name}: 顶层必须是数组")
            continue
        for r in data:
            name = str(r.get("name") or "").strip()
            if not name or name in existing_names:
                skipped.append(name or p.stem)
                continue
            if not validate(r, p.name):
                added.append(r)
                existing_names.add(name)

    merged = existing + added
    RECIPES_PATH.write_text(
        json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"现有 {len(existing)} 道, 新增 {len(added)} 道, 跳过 {len(skipped)} 道")
    print(f"合并后共 {len(merged)} 道 -> {RECIPES_PATH.name} ({RECIPES_PATH.stat().st_size // 1024} KB)")
    if skipped:
        print("跳过/重复:", skipped[:30])


if __name__ == "__main__":
    main()
