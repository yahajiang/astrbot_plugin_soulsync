# -*- coding: utf-8 -*-
"""合并分片步骤文件：tools/part_XX_steps.json -> recipes.json

用法：python tools/merge_steps.py [输出路径]
每个分片文件必须包含完整菜谱对象（与 part_XX.json 同构），steps 字段已填充。
"""

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent


def main(out_path: Path):
    recipes = []
    total_steps = 0
    for p in sorted(TOOLS.glob("part_*_steps.json")):
        chunk = json.loads(p.read_text(encoding="utf-8"))
        for r in chunk:
            assert isinstance(r.get("steps"), list) and r["steps"], (
                f"{p.name} 中「{r.get('name')}」缺少步骤"
            )
            total_steps += len(r["steps"])
        recipes.extend(chunk)
        print(f"{p.name}: {len(chunk)} 道")
    out_path.write_text(
        json.dumps(recipes, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"合并完成: {len(recipes)} 道, 步骤总数 {total_steps} -> {out_path}")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else TOOLS.parent / "recipes.json"
    main(out)
