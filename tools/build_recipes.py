# -*- coding: utf-8 -*-
"""一次性数据构建脚本：从 YunYouJun/cook 的 recipe.csv 生成插件内置 recipes.json。

用法：python tools/build_recipes.py <recipe.csv 路径> <输出 json 路径>

生成字段：name / category / ingredients / steps / tags / methods / tools /
         difficulty / bv / spicy / mood_hint
其中 steps 为按做法（methods）模板 + 食材注入自动生成，保证每道菜都有步骤。
"""

import csv
import json
import sys
from collections import OrderedDict
from pathlib import Path

MEAT_KEYWORDS = (
    "肉", "鸡", "牛", "猪", "虾", "鱼", "蛋", "腊肠", "午餐肉",
    "骨", "香肠", "火腿", "培根", "肉沫", "肉末",
)

SPICY_KEYWORDS = ("辣", "麻", "花椒", "麻辣", "香辣", "辣椒")

SWEET_KEYWORDS = ("甜", "蛋糕", "布丁", "蛋挞", "甜品", "糖", "蜜汁", "拔丝", "奶黄")

STAPLE_KEYWORDS = ("饭", "面", "粥", "粉", "馒头", "饼", "包子", "饺子", "面包", "吐司", "米")

SOUP_KEYWORDS = ("汤", "羹", "粥")

STEP_TEMPLATES = {
    "炒": [
        "热锅凉油，油温升高后下入{main}大火翻炒。",
        "炒至食材断生后，加入{rest}继续翻炒均匀。",
        "调入适量盐、生抽，大火炒匀即可出锅。",
    ],
    "煎": [
        "平底锅少油烧热，放入{main}小火慢煎。",
        "一面煎至金黄后翻面，两面煎熟。",
        "出锅前按口味撒盐或淋酱汁调味。",
    ],
    "蒸": [
        "锅中加水烧开，将{main}摆盘上锅。",
        "大火蒸至熟透（筷子能轻松插入为准）。",
        "出锅后淋上料汁或撒葱花即可。",
    ],
    "煮": [
        "锅中加水烧开，下入{main}。",
        "大火煮开后转中小火，煮至食材熟软。",
        "按口味加盐调味，关火盛出。",
    ],
    "烤": [
        "将{main}处理好，用腌料腌制入味。",
        "烤盘铺锡纸摆入食材，烤箱预热。",
        "放入烤箱烘烤至表面金黄、熟透。",
        "出炉后稍晾，撒香料或蘸料食用。",
    ],
    "烘": [
        "将{main}处理摆入烤盘或模具。",
        "烤箱预热后放入，烘烤至表面金黄。",
        "出炉脱模，稍凉后食用。",
    ],
    "炸": [
        "锅中倒油烧至六七成热（筷子插入冒密集气泡）。",
        "下入{main}，中小火炸至表面金黄。",
        "捞出控油，可升高油温复炸一次更酥脆。",
    ],
    "炖": [
        "食材处理干净，冷水下锅焯水去腥。",
        "放入锅中加足量水，大火烧开。",
        "转小火慢炖至食材软烂入味。",
        "最后加盐调味，撒葱花出锅。",
    ],
    "烧": [
        "锅中热油，下入{main}煸炒至微微上色。",
        "加入调味料和适量水，没过食材。",
        "小火焖烧至汤汁收浓、完全入味。",
    ],
    "焖": [
        "锅内放少许油，下入{main}翻炒片刻。",
        "加入调料与适量水，盖上锅盖焖煮。",
        "焖至食材熟透、汤汁浓稠即可。",
    ],
    "煲": [
        "将{main}放入砂锅/煲中，加水没过食材。",
        "大火烧开后转小火慢煲。",
        "煲至食材酥软，调味后连锅上桌。",
    ],
    "拌": [
        "将{main}焯水或煮熟，捞出过凉沥干。",
        "放入碗中，加入蒜末、生抽、香醋等调料。",
        "充分拌匀，静置片刻入味即可。",
    ],
    "凉拌": [
        "将{main}焯水或煮熟，捞出过凉沥干。",
        "加入盐、生抽、香醋、辣椒油等调料。",
        "拌匀腌制片刻，爽口开胃。",
    ],
    "卤": [
        "锅中加水，放入八角、桂皮、香叶等卤料烧开。",
        "下入{main}，大火煮开后转小火卤制。",
        "关火后浸泡入味，捞出切片食用。",
    ],
    "腌": [
        "将{main}洗净切好，加盐拌匀腌出水分。",
        "加入调料充分拌匀，装入密封容器。",
        "腌制入味后即可食用，冷藏风味更佳。",
    ],
    "焗": [
        "将{main}处理好铺入烤盘。",
        "表面铺上芝士或浇上料汁。",
        "烤箱预热后焗至表面金黄微焦。",
    ],
    "微波加热": [
        "将{main}装入微波炉专用容器，必要时加盖留孔。",
        "放入微波炉高火加热数分钟。",
        "取出翻动，视情况再加热至熟透。",
    ],
    "灼": [
        "锅中水烧开，下入{main}。",
        "烫至断生立即捞出，保持鲜嫩。",
        "搭配姜葱豉油等蘸料食用。",
    ],
    "烙": [
        "将面团/食材处理成饼坯。",
        "平底锅小火加热，放入饼坯烙制。",
        "一面烙至微焦后翻面，两面金黄即可。",
    ],
    "油泼": [
        "面条/食材煮熟捞入碗中，码上蒜末、葱花与调料。",
        "烧一勺热油，趁热泼在调料上激出香味。",
        "拌匀即可食用。",
    ],
    "泡菜": [
        "食材洗净切块，加盐腌制杀水。",
        "拌入辣椒粉等调料，装入干净容器。",
        "密封冷藏发酵数日即可食用。",
    ],
    "盖浇": [
        "将主料烧制成熟，汤汁浓稠。",
        "连汁浇在米饭或面上。",
        "拌匀即可食用。",
    ],
    "煲仔": [
        "将{main}处理好放入砂煲。",
        "加水小火慢煲至熟透。",
        "调味后直接上桌。",
    ],
}

GENERIC_STEPS = [
    "将食材洗净，按需切块、切丝或切片备用。",
    "起锅热油，下入主料翻炒出香。",
    "加入其余食材与调味料，烹饪至熟透。",
    "收汁出锅，装盘即可享用。",
]

MOOD_HINT_RULES = [
    ("喜悦", ("烤", "焗", "海鲜", "仪式"), ("烤", "焗", "虾", "牛排", "硬菜")),
    ("悲伤", ("甜", "软糯"), ("甜", "蛋糕", "布丁", "蛋挞", "奶", "蜜汁")),
    ("愤怒", ("辣", "刺激"), ("辣", "麻", "麻辣", "香辣")),
    ("焦虑", ("清淡", "安神"), ("清淡", "粥", "汤", "蒸", "小米")),
    ("期待", ("创意", "异国"), ("日式", "意式", "法式", "西班牙", "泰式", "韩式", "大阪")),
]


def _split_stuff(stuff: str):
    parts = []
    for ch in ("、", "，", ",", "，"):
        stuff = stuff.replace(ch, "、")
    for p in stuff.split("、"):
        p = p.strip()
        if p:
            parts.append(p)
    return parts


def _is_vegetarian(ingredients):
    return not any(kw in "".join(ingredients) for kw in MEAT_KEYWORDS)


def _is_spicy(name, tags, ingredients):
    text = name + "".join(tags) + "".join(ingredients)
    return any(kw in text for kw in SPICY_KEYWORDS)


def _category(name, tags, ingredients, methods):
    text = name + "".join(tags)
    if any(kw in text for kw in ("粥", "羹")):
        return "粥羹"
    if "汤" in text:
        return "汤羹"
    if any(kw in text for kw in ("凉菜", "凉拌", "拌")):
        return "凉菜"
    if any(kw in text for kw in STAPLE_KEYWORDS) or "饭" in text or "面" in text:
        return "主食"
    if any(kw in text for kw in ("蛋糕", "布丁", "蛋挞", "甜", "零食")):
        return "甜品零食"
    if _is_vegetarian(ingredients):
        return "素菜"
    return "荤菜"


def _mood_hint(name, tags, ingredients, methods):
    text = name + "".join(tags) + "".join(methods) + "".join(ingredients)
    hints = []
    for label, _, kws in MOOD_HINT_RULES:
        if any(kw in text for kw in kws):
            hints.append(label)
    return hints


def _build_steps(name, ingredients, methods):
    main = ingredients[0] if ingredients else name
    rest = "、".join(ingredients[1:3]) if len(ingredients) > 1 else main
    steps = ["将食材洗净，主料 {main} 按需切块、切丝或切片备用。".format(main=main)]
    if not methods:
        return steps + GENERIC_STEPS[1:]
    for m in methods:
        tmpl = STEP_TEMPLATES.get(m)
        if tmpl:
            steps.extend(s.format(main=main, rest=rest) for s in tmpl)
    if len(steps) < 3:
        steps.extend(GENERIC_STEPS[1:])
    # 收尾统一
    if steps and not steps[-1].endswith("。\n"):
        pass
    return steps


def build(csv_path: Path, out_path: Path, with_steps: bool = False):
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    recipes = []
    seen = set()
    for r in rows:
        name = (r.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        ingredients = _split_stuff(r.get("stuff") or "")
        tags = [t.strip() for t in (r.get("tags") or "").split("、") if t.strip()]
        methods = [m.strip() for m in (r.get("methods") or "").replace("/", "、").split("、") if m.strip()]
        tools = [t.strip() for t in (r.get("tools") or "").replace("/", "、").split("、") if t.strip()]
        bv = (r.get("bv") or "").strip()
        recipe = OrderedDict([
            ("name", name),
            ("category", _category(name, tags, ingredients, methods)),
            ("ingredients", ingredients),
            ("steps", _build_steps(name, ingredients, methods) if with_steps else []),
            ("tags", tags),
            ("methods", methods),
            ("tools", tools),
            ("difficulty", (r.get("difficulty") or "").strip() or "普通"),
            ("bv", bv),
            ("spicy", _is_spicy(name, tags, ingredients)),
            ("vegetarian", _is_vegetarian(ingredients)),
            ("mood_hint", _mood_hint(name, tags, ingredients, methods)),
        ])
        recipes.append(recipe)

    out_path.write_text(
        json.dumps(recipes, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"共写入 {len(recipes)} 道菜谱 -> {out_path} ({out_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        print("用法: python tools/build_recipes.py <recipe.csv> <recipes.json> [--with-steps]")
        sys.exit(1)
    build(
        Path(sys.argv[1]),
        Path(sys.argv[2]),
        with_steps=len(sys.argv) == 4 and sys.argv[3] == "--with-steps",
    )
