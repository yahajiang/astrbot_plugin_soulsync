"""SoulSync - 父命令路由器（v3.11 指令精简版）

精简后：8 个父命令 + 18 个普通用户子命令 + 8 个管理员子命令。
配置/分析/调试类功能迁移至 WebUI 控制台。

路由表：父命令 → {子命令: 方法名}
- 子命令 "" 表示父命令无子命令时的默认动作
- 返回 None 表示未知子命令（调用方输出该父命令帮助）
"""

from __future__ import annotations

import re

# ─── 迁移提示文案 ────────────────────────────────────────────
MIGRATED_HINT = "⏳ 该功能已迁移至 WebUI 控制台\n请前往：AstrBot → 插件管理 → SoulSync → 控制台 进行操作"

# ─── 8 父命令路由表（精简后）──────────────────────────────────
PARENT_COMMANDS = {
    "心声": {
        "": "cmd_favorability",              # 默认输出状态卡片
        "好感": "cmd_favorability",
        "阶段": "cmd_relationship_stage",
        "画像": "cmd_my_portrait",
    },
    "回忆": {
        "趋势": "cmd_trend",                 # [天数]
        "月报": "cmd_monthly_report",        # [上月]
    },
    "纪念": {
        "": "cmd_anniversary",               # 查看
        "查看": "cmd_anniversary",
        "添加": "cmd_add_anniversary",       # <日期> <名称>
        "删除": "cmd_remove_anniversary",    # <id>
        "生日": "cmd_set_birthday",          # <日期>
        "节日": "cmd_festival_list",
        "节日添加": "cmd_add_festival",      # 管理员 <名称> <日期>
        "节日删除": "cmd_remove_festival",   # 管理员 <名称>
    },
    "角色": {
        "称谓": "cmd_set_preferred_address",  # [称呼|无] 专属称谓
        "关系": "cmd_relationship_roles",    # [角色] 关系角色查看
        "解锁": "cmd_unlock_relationship",   # <角色>
        "关系切换": "cmd_switch_relationship",  # <角色>
    },
    "人格": {
        "": "cmd_persona",                   # 查看面板（只读）
        "查看": "cmd_persona",
    },
    "知识": {
        "": "cmd_knowledge",
        "查看": "cmd_knowledge",
        "添加": "cmd_knowledge_add",         # [分类] <内容>
    },
    "风格": {
        "": "cmd_style",
        "状态": "cmd_style",
        "保存": "cmd_style_snapshot",        # KEEP_SUB：方法内解析 保存/恢复
        "恢复": "cmd_style_snapshot",        # KEEP_SUB
        "锁定": "cmd_style_lock",
    },
    "记忆": {
        "": "cmd_memory",
        "查看": "cmd_memory",
        "添加": "cmd_memory_add",            # <类型> <内容>
        "删除": "cmd_memory_remove",         # <id>
        "星标": "cmd_memory_star",           # <id>
        "重要": "cmd_mark_important",        # [序号]
        "忘记": "cmd_forget",                # [序号]
    },
    "排行": {
        "": "cmd_leaderboard",
        "好感": "cmd_leaderboard",           # [n]
        "负好感": "cmd_negative_leaderboard",  # [n]
    },
}

# ─── 独立命令（零参数即时切换）────────────────────────────────
STANDALONE_COMMANDS = {
    "图片模式": "cmd_image_mode",            # 指令输出图片/文本切换
    "设置": "cmd_toggle_status",             # 状态显示开关
}

# ─── /心管 管理员集中入口（精简后 8 个核心）──────────────────
ADMIN_COMMANDS = {
    "设置": "cmd_admin_set",                # <ID> <字段> <值> 统一入口
    "查看": "cmd_view_detail",              # <ID> 完整档案
    "重置": "cmd_reset",                    # <ID> 清空全部数据
    "跳跃": "cmd_admin_skip",               # <ID> <天数>（0=重置冻结）
    "压缩": "cmd_admin_compress",           # <ID> 手动触发记忆压缩
    "隐私": "cmd_privacy_level",            # <ID> <0-2>
    "备份": "cmd_backup",                   # 全局数据快照
    "调试": "cmd_admin_debug",              # [ID] 综合诊断
}

# 需要保留子命令 token 的方法（方法自身已实现子命令解析）
KEEP_SUB_METHODS = {"cmd_style_snapshot"}

# ─── 帮助文本 ────────────────────────────────────────────────

PARENT_HELP = {
    "心声": "/心声 [好感|阶段|画像] — 核心情感数值、阶段、画像",
    "回忆": "/回忆 [趋势 天数|月报] — 情感趋势与月度报告",
    "纪念": "/纪念 [查看|添加 日期 名称|删除 id|生日 日期|节日|节日添加|节日删除] — 特殊日期管理",
    "角色": "/角色 [称谓 称呼|关系|解锁|关系切换] — 关系角色与专属称谓",
    "人格": "/人格 [查看] — 人格面板（20 参数/稳定度/锁定状态）",
    "知识": "/知识 [查看|添加] — 知识库管理",
    "风格": "/风格 [状态|保存 名称|恢复 名称|锁定] — 语言风格控制",
    "记忆": "/记忆 [查看|添加|删除|星标|重要|忘记] — 私人记忆库",
    "排行": "/排行 [好感 n|负好感 n] — 好感/负好感排行榜",
}

ADMIN_HELP = (
    "🛡️ 心管后台操作（仅管理员）\n"
    "/心管 设置 <ID> <字段> <值> — 统一设置（好感/亲密/态度/关系/角色/图片模式）\n"
    "/心管 查看 <ID> — 完整档案（8 维+记忆+行为）\n"
    "/心管 重置 <ID> — 清空全部数据\n"
    "/心管 跳跃 <ID> <天数> — 时间跳跃（0=重置）\n"
    "/心管 压缩 <ID> — 手动记忆压缩\n"
    "/心管 隐私 <ID> <0-2> — 隐私等级\n"
    "/心管 备份 — 创建全局快照\n"
    "/心管 调试 [ID] — 综合诊断"
)

# ─── 结构化帮助（图片渲染专用）──────────────────────────────────

PARENT_HELP_SECTIONS = [
    ("心声", [
        ("好感", "核心情感数值（好感/亲密度/阶段/行为势头）"),
        ("阶段", "当前关系阶段详情"),
        ("画像", "个人情感自画像（8 维情感+行为模式+里程碑）"),
    ], "/心声 好感"),
    ("回忆", [
        ("趋势 天数", "最近 N 天（默认 14）情感数据趋势"),
        ("月报", "关系月报（净好感/情绪主色调/里程碑）"),
    ], "/回忆 趋势 7"),
    ("纪念", [
        ("添加 日期 名称", "添加自定义纪念日"),
        ("删除 id", "删除自定义纪念日"),
        ("生日 日期", "设置生日"),
        ("节日", "全部节日列表与倒计时"),
        ("节日添加 名称 日期", "添加节日（管理员）"),
        ("节日删除 名称", "删除节日（管理员）"),
    ], "/纪念 添加 12-25 圣诞"),
    ("角色", [
        ("称谓 称呼", "角色叫你的专属称呼"),
        ("关系", "关系角色列表与解锁进度"),
        ("解锁 角色", "解锁系统内置关系角色"),
        ("关系切换 角色", "切换关系角色（一次即锁定，不可逆）"),
    ], "/角色 称谓 宝贝"),
    ("人格", [
        ("查看", "人格面板（20 参数/稳定度/锁定状态），全员只读"),
    ], "/人格 查看"),
    ("知识", [
        ("查看", "知识库全部条目（按分类分组）"),
        ("添加 内容", "添加知识（profile/interests/people/promises/experiences/values）"),
    ], "/知识 添加 我喜欢喝奶茶"),
    ("风格", [
        ("状态", "语言风格训练状态（阶段/融合度/快照列表）"),
        ("保存 名称", "保存风格快照"),
        ("恢复 名称", "恢复风格快照"),
        ("锁定", "锁定/解锁风格（锁定期停止学习）"),
    ], "/风格 保存 温柔"),
    ("记忆", [
        ("添加 内容", "添加记忆（text/image/promise/emotional）"),
        ("删除 id", "删除记忆"),
        ("星标 id", "切换星标（⭐ 检索优先）"),
        ("重要", "长期记忆标记重要（1=最近）"),
        ("忘记", "长期记忆忘记（1=最近）"),
    ], "/记忆 添加 我喜欢下雨天"),
    ("排行", [
        ("好感 n", "TOP n 好感排行榜（默认 10，最多 20）"),
        ("负好感 n", "BOTTOM n 负好感排行榜（默认 10，最多 20）"),
    ], "/排行 好感 5"),
]

HELP_GUIDE = "想不起来命令？直接说你想做的事，例如「我们什么关系？」"

HELP_TIPS = [
    "参数用空格分隔，如：/纪念 添加 12-25 圣诞",
    "子命令留空即默认视图，如直接输入 /心声",
    "更多功能请前往 WebUI 控制台操作",
]

STANDALONE_HELP = [
    ("/图片模式", "切换本人指令输出为图片卡片（需 Pillow）"),
    ("/设置", "对话后自动显示情感状态行开关"),
    ("/心管", "管理员后台：设置、查看、重置、跳跃等"),
]

# ─── 管理员专属子命令（普通用户总览隐藏）──────────────────────
ADMIN_ONLY_SUBS = {
    "纪念": ("节日添加", "节日删除"),
}
ADMIN_STANDALONE = ("/心管",)


# ═══════════════════════════════════════════════════════════════
#  内部工具
# ═══════════════════════════════════════════════════════════════

def _filter_sections(sections, include_admin: bool) -> list:
    if include_admin:
        return sections
    out = []
    for sec in sections:
        name, cmds, example = sec
        hidden = ADMIN_ONLY_SUBS.get(name)
        keep = [(c, d) for c, d in cmds
                if not hidden or not any(c.startswith(h) for h in hidden)]
        out.append((name, keep, example))
    return out


# ═══════════════════════════════════════════════════════════════
#  公开 API
# ═══════════════════════════════════════════════════════════════

def resolve_parent(parent: str, sub: str) -> str | None:
    """解析父命令+子命令 → 方法名；未知返回 None"""
    table = PARENT_COMMANDS.get(parent)
    if not table:
        return None
    return table.get(sub)


def resolve_admin(sub: str) -> str | None:
    """解析 /心管 子命令 → 方法名"""
    return ADMIN_COMMANDS.get(sub)


def normalize_args(text: str, keep_sub: bool = False) -> list[str]:
    """把 '/父命令 子命令 参数...' 归一化为 '命令 参数...'（剥离子命令 token）"""
    parts = text.split()
    if len(parts) >= 2 and not keep_sub:
        return [parts[0]] + parts[2:]
    return parts


def keep_sub(method_name: str) -> bool:
    return method_name in KEEP_SUB_METHODS


def migrated_hint() -> str:
    """返回迁移提示文案"""
    return MIGRATED_HINT


def parent_help(parent: str) -> str:
    return PARENT_HELP.get(parent, f"/{parent} — 未知父命令")


def admin_help() -> str:
    return ADMIN_HELP


def parent_help_sections(include_admin: bool = True) -> list:
    """结构化帮助：[(父命令, [(子命令+参数, 说明), ...], 示例)]，供图片渲染器排版"""
    return [tuple(sec) for sec in _filter_sections(PARENT_HELP_SECTIONS, include_admin)]


def standalone_help(include_admin: bool = True) -> list:
    """独立命令：[(命令, 说明), ...]；include_admin=False 时隐藏 /心管"""
    if include_admin:
        return list(STANDALONE_HELP)
    return [item for item in STANDALONE_HELP if item[0] not in ADMIN_STANDALONE]


def help_guide() -> str:
    """顶部引导语（图片渲染专用）"""
    return HELP_GUIDE


def help_tips() -> list:
    """底部提示列表（图片渲染专用）"""
    return list(HELP_TIPS)


def _visible_parent_line(parent: str, include_admin: bool) -> str:
    line = PARENT_HELP[parent]
    hidden = ADMIN_ONLY_SUBS.get(parent)
    if include_admin or not hidden:
        return line
    m = re.match(r"^(.*\[)([^\]]*)(\].*)$", line)
    if not m:
        return line
    toks = [t.strip() for t in m.group(2).split("|")]
    keep = [t for t in toks if not any(t.startswith(h) for h in hidden)]
    return m.group(1) + "|".join(keep) + m.group(3)


def all_parent_help(include_admin: bool = True) -> str:
    lines = ["🎛️ SoulSync 命令总览", "━" * 24]
    for parent in ("心声", "回忆", "纪念", "角色", "人格", "知识",
                   "风格", "记忆", "排行"):
        lines.append(_visible_parent_line(parent, include_admin))
    lines.append("")
    lines.append("/图片模式 — 指令输出图片/文本切换（零参数）")
    lines.append("/设置 — 状态显示开关（零参数）")
    if include_admin:
        lines.append("/心管 ... — 管理员后台操作")
    lines.append("")
    lines.append("💡 95% 场景无需输入命令：查询意图会自动识别（如\"我们什么关系？\"）")
    lines.append("📡 更多功能请前往 WebUI 控制台")
    return "\n".join(lines)
