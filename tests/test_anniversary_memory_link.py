# v2.21 纪念日记忆联动：知识库生日/约定日期提取（脏数据容错）
# 运行: python tests/test_anniversary_memory_link.py
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent.parent))

from astrbot_plugin_soulsync.anniversary import extract_kb_dates

PASS = 0

def ok(name):
    global PASS
    PASS += 1
    print(f"PASS: {name}")

# ── 1. 生日提取（多种格式）────────────────────────────────
b, d = extract_kb_dates(["生日 6月1日 出生的", "别的内容 9-15 见"], ["8.8 一起吃饭"])
assert b == (6, 1, "生日 6月1日 出生的"), b
assert (8, 8, "8.8 一起吃饭") in d
ok("生日多格式提取（6月1日 / 9-15 / 8.8）")

# ── 2. 非法日期跳过（2月30日 / v2.6.1 误匹配）──────────────
b, d = extract_kb_dates(["生日 2月30日 出生", "生日 v2.6.1 上线"], ["12月40日 见面", "用 3.0 版本", "5月5日 去爬山"])
assert b is None, f"非法生日应跳过: {b}"
assert all(x[0] <= 12 and x[1] <= 31 for x in d)
assert (5, 5, "5月5日 去爬山") in d, d
assert not any(x[0] == 2 and x[1] == 6 for x in d), "v2.6.1 不应匹配为日期"
ok("非法日期/版本号误匹配跳过，合法条目保留")

# ── 3. 无知识内容返回空 ───────────────────────────────────
b, d = extract_kb_dates([], [])
assert b is None and d == []
b, d = extract_kb_dates(["毫无日期", "生日还没过"], ["没有时间约定"])
assert b is None and d == []
ok("空库/无日期返回空")

# ── 4. 13月/00日 等极端值跳过 ─────────────────────────────
b, d = extract_kb_dates(["生日 13月1日"], ["0月1日 见面"])
assert b is None and d == []
ok("13月/0月 极端值跳过")

# ── 5. 文本截断 24/28 字 ─────────────────────────────────
long_t = "约定" + "很长" * 50
b, d = extract_kb_dates([], [f"7.7 {long_t}"])
assert len(d[0][2]) <= 28, len(d[0][2])
ok("长文本截断")

print(f"=== 纪念日记忆联动 {PASS} 组全部通过 ===")
