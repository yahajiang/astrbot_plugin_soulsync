"""SoulSync - 父命令路由器（v2.20 命令极简化）

将 70 个扁平命令收敛为 10 个父命令 + 子命令 + /心管 集中管理。
纯逻辑模块，不依赖 AstrBot，可独立单测。

路由表：父命令 → {子命令: 方法名}
- 子命令 "" 表示父命令无子命令时的默认动作
- 返回 None 表示未知子命令（调用方输出该父命令帮助）
"""

from __future__ import annotations

# ─── 10 父命令路由表 ───────────────────────────────────────────
PARENT_COMMANDS = {
    "心声": {
        "": "cmd_favorability",              # 默认输出状态卡片
        "好感": "cmd_favorability",
        "阶段": "cmd_relationship_stage",
        "画像": "cmd_my_portrait",
        "系统": "cmd_cache_stats",
    },
    "回忆": {
        "趋势": "cmd_trend",                 # [天数]
        "月报": "cmd_monthly_report",        # [上月]
        "报告": "cmd_role_report",           # [天数] 角色回顾
        "独白": "cmd_role_report",           # 角色独白（角色回顾报告）
        "对比": "cmd_radar",                 # [天数]
        "时间线": "cmd_rde_stage",           # [ID]
        "危机": "cmd_rde_crisis_log",        # [ID]
        "关系网": "cmd_rde_network",         # [ID]
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
        "": "cmd_character_list",            # 列表
        "列表": "cmd_character_list",
        "创建": "cmd_character_create",      # <名字> [emoji] [描述]
        "切换": "cmd_character_switch",      # <名字>
        "删除": "cmd_character_remove",      # <名字>
        "查看": "cmd_character_list",
        "称谓": "cmd_set_preferred_address",  # [称呼|无] 专属称谓
        "关系": "cmd_relationship_roles",    # [角色] 关系角色查看
        "解锁": "cmd_unlock_relationship",   # <角色>
        "关系切换": "cmd_switch_relationship",  # <角色>
    },
    "人格": {
        "": "cmd_persona",                   # 查看面板（只读）
        "查看": "cmd_persona",
        "设置": "cmd_persona_params",        # 仅管理员 <参数> <值>
        "重置": "cmd_persona_reset",         # 仅管理员
        "锁定": "cmd_persona_lock",          # 仅管理员
    },
    "知识": {
        "": "cmd_knowledge",
        "查看": "cmd_knowledge",
        "添加": "cmd_knowledge_add",         # [分类] <内容>
        "删除": "cmd_knowledge_remove",      # <id>
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
    "天象": {
        "": "cmd_tpd_weather",               # 默认环境感知
        "天气": "cmd_tpd_weather",
        "倒计时": "cmd_tpd_countdown",
        "跳跃": "cmd_tpd_skip",              # [N天后见]
        "回溯": "cmd_time_jump",             # 时间线叙事
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

# ─── /心管 管理员集中入口 ─────────────────────────────────────
ADMIN_COMMANDS = {
    "图片模式": "cmd_global_image_mode",
    "好感": "cmd_set_favorability",          # <用户ID> <值>
    "亲密": "cmd_set_intimacy",              # <用户ID> <值>
    "态度": "cmd_set_attitude",              # <用户ID> <文本>
    "关系": "cmd_set_relationship",          # <用户ID> <关系>
    "关系角色": "cmd_set_relationship_role",  # <用户ID> <角色>
    "重置好感": "cmd_reset",                 # <用户ID>
    "查看好感": "cmd_view_detail",           # <用户ID>
    "隐私": "cmd_privacy_level",             # <0-2>
    "重置": "cmd_reset_plugin",
    "备份": "cmd_backup",
    "修复统计": "cmd_fix_stats",
    "强制跳跃": "cmd_tpd_force_skip",        # <用户ID> <天数>
    "重置跳跃": "cmd_tpd_reset_skip",        # [用户ID]
    "天气调试": "cmd_tpd_weather_debug",
    "导出": "cmd_personalization_export",
    "人格锁定": "cmd_persona_lock",
    "调试事件": "cmd_debug_event",
    "调试记忆": "cmd_debug_memory",
}

# 需要保留子命令 token 的方法（方法自身已实现子命令解析）
KEEP_SUB_METHODS = {"cmd_style_snapshot"}

PARENT_HELP = {
    "心声": "/心声 [好感|阶段|画像|系统] — 核心情感数值、阶段、画像",
    "回忆": "/回忆 [趋势 天数|月报|报告|独白|对比|时间线|危机|关系网] — 文本版分析报告",
    "纪念": "/纪念 [查看|添加 日期 名称|删除 id|生日 日期|节日|节日添加|节日删除] — 特殊日期管理",
    "角色": "/角色 [列表|创建|切换|删除|查看|称谓 称呼|关系|解锁|关系切换] — 多角色管理（称谓=角色叫你的专属称呼）",
    "人格": "/人格 [查看|设置 参数 值|重置|锁定] — 查看全员只读，设置/重置/锁定仅管理员",
    "知识": "/知识 [查看|添加|删除] — 知识库管理",
    "风格": "/风格 [状态|保存 名称|恢复 名称|锁定] — 语言风格控制",
    "记忆": "/记忆 [查看|添加|删除|星标|重要|忘记] — 私人记忆库",
    "天象": "/天象 [天气|倒计时|跳跃|回溯] — 环境感知查询",
    "排行": "/排行 [好感 n|负好感 n] — 好感/负好感排行榜",
}

ADMIN_HELP = "/心管 [图片模式|好感|亲密|态度|关系|关系角色|重置好感|查看好感|隐私|重置|备份|修复统计|强制跳跃|重置跳跃|天气调试|导出|人格锁定|调试事件|调试记忆] — 全部后台操作"


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
    """把 '/父命令 子命令 参数...' 归一化为 '命令 参数...'（剥离子命令 token）。

    旧命令方法统一从 parts[1] 起取参数；父命令形态下 parts[1] 是子命令名，
    归一化后 parts[1] 即为第一个真实参数，旧方法逻辑无需改动。
    keep_sub=True 时保留子命令（用于方法自身已实现子命令解析的场景）。
    """
    parts = text.split()
    if len(parts) >= 2 and not keep_sub:
        return [parts[0]] + parts[2:]
    return parts


def keep_sub(method_name: str) -> bool:
    return method_name in KEEP_SUB_METHODS


def parent_help(parent: str) -> str:
    return PARENT_HELP.get(parent, f"/{parent} — 未知父命令")


def admin_help() -> str:
    return ADMIN_HELP


def all_parent_help() -> str:
    lines = ["🎛️ SoulSync 命令总览", "━" * 24]
    for parent in ("心声", "回忆", "纪念", "角色", "人格", "知识",
                   "风格", "记忆", "天象", "排行"):
        lines.append(PARENT_HELP[parent])
    lines.append("")
    lines.append("/图片模式 — 指令输出图片/文本切换（零参数）")
    lines.append("/设置 — 状态显示开关（零参数）")
    lines.append("/心管 ... — 管理员后台操作")
    lines.append("")
    lines.append("💡 95% 场景无需输入命令：查询意图会自动识别（如\"我们什么关系？\"）")
    return "\n".join(lines)
