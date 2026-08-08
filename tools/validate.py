# -*- coding: utf-8 -*-
"""校验 recipes.json 完整性"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

data = json.loads(Path("recipes.json").read_text(encoding="utf-8"))
empty = [r["name"] for r in data if not r.get("steps")]
short = [r["name"] for r in data if len(r.get("steps", [])) < 4]
no_ing = [r["name"] for r in data if not r.get("ingredients")]
print(f"总菜数: {len(data)}")
print(f"无步骤: {len(empty)}", empty[:10])
print(f"步骤<4条: {len(short)}", short[:10])
print(f"无食材: {len(no_ing)}", no_ing[:10])
cats = {}
for r in data:
    cats[r["category"]] = cats.get(r["category"], 0) + 1
print(f"分类: {cats}")
veg = sum(1 for r in data if r["vegetarian"])
spicy = sum(1 for r in data if r["spicy"])
print(f"素菜: {veg}, 辛辣: {spicy}")
# 抽查新增菜
for name in ("上汤娃娃菜", "乡村啤酒鸭", "麻婆豆腐"):
    r = next((x for x in data if x["name"] == name), None)
    if r:
        print(f"=== {name} [{r['category']}] 步骤{len(r['steps'])}条")
        print("  食材:", r["ingredients"][:4])
        print("  首步:", r["steps"][0][:80])
