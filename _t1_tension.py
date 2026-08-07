# -*- coding: utf-8 -*-
"""T1 张力参数调优：accumulate 2→4 / threshold 85→70 / per_day 10→6"""
import json, io, re

s = json.load(open("_conf_schema.json", encoding="utf-8"))
s["tension_accumulate_rate"]["default"] = 4.0
s["tension_threshold"]["default"] = 70.0
s["tension_release_per_day"]["default"] = 6.0
s["tension_accumulate_rate"]["hint"] = s["tension_accumulate_rate"]["hint"].replace(
    "负面情绪每轮积累速率（越高张力增长越快）", "负面情绪每轮积累速率（默认 4，张力随负面情绪快速积累）")
json.dump(s, open("_conf_schema.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

p = "main.py"
t = io.open(p, encoding="utf-8").read()
reps = [
    ('float(config.get("tension_accumulate_rate", 2.0))', 'float(config.get("tension_accumulate_rate", 4.0))'),
    ('self.config.get("tension_accumulate_rate", 2.0),', 'self.config.get("tension_accumulate_rate", 4.0),'),
    ('self.config.get("tension_threshold", 85.0)', 'self.config.get("tension_threshold", 70.0)'),
    ('self.config.get("tension_release_per_day", 10.0)', 'self.config.get("tension_release_per_day", 6.0)'),
]
miss = 0
for a, b in reps:
    if a in t:
        t = t.replace(a, b)
    else:
        miss += 1
        print("未命中:", a)
io.open(p, "w", encoding="utf-8", newline="").write(t)
print(f"done, 未命中 {miss}/{len(reps)}")
