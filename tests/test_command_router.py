"""SoulSync v2.20 - P2 父命令路由器测试

覆盖：10 父命令子命令解析、/admin 子命令解析、参数归一化、帮助文本。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from astrbot_plugin_soulsync.command_router import (
    ADMIN_COMMANDS,
    PARENT_COMMANDS,
    STANDALONE_COMMANDS,
    admin_help,
    all_parent_help,
    keep_sub,
    normalize_args,
    parent_help,
    resolve_admin,
    resolve_parent,
)


def test_ten_parent_commands():
    assert set(PARENT_COMMANDS.keys()) == {
        "状态", "回顾", "纪念", "角色", "人格", "知识",
        "风格", "记忆", "环境", "排行",
    }


def test_status_subcommands():
    assert resolve_parent("状态", "") == "cmd_favorability"
    assert resolve_parent("状态", "好感") == "cmd_favorability"
    assert resolve_parent("状态", "阶段") == "cmd_relationship_stage"
    assert resolve_parent("状态", "画像") == "cmd_my_portrait"
    assert resolve_parent("状态", "系统") == "cmd_cache_stats"


def test_review_subcommands():
    assert resolve_parent("回顾", "趋势") == "cmd_trend"
    assert resolve_parent("回顾", "月报") == "cmd_monthly_report"
    assert resolve_parent("回顾", "对比") == "cmd_radar"
    assert resolve_parent("回顾", "时间线") == "cmd_rde_stage"
    assert resolve_parent("回顾", "危机") == "cmd_rde_crisis_log"
    assert resolve_parent("回顾", "关系网") == "cmd_rde_network"


def test_memory_subcommands():
    assert resolve_parent("记忆", "星标") == "cmd_memory_star"
    assert resolve_parent("记忆", "重要") == "cmd_mark_important"
    assert resolve_parent("记忆", "忘记") == "cmd_forget"


def test_role_subcommands():
    assert resolve_parent("角色", "称谓") == "cmd_set_preferred_address"
    assert resolve_parent("角色", "列表") == "cmd_character_list"
    assert resolve_parent("角色", "创建") == "cmd_character_create"


def test_environment_subcommands():
    assert resolve_parent("环境", "天气") == "cmd_tpd_weather"
    assert resolve_parent("环境", "跳跃") == "cmd_tpd_skip"
    assert resolve_parent("环境", "回溯") == "cmd_time_jump"


def test_unknown_subcommand_returns_none():
    assert resolve_parent("状态", "不存在的子命令") is None
    assert resolve_parent("不存在", "x") is None
    assert resolve_admin("不存在的子命令") is None


def test_admin_subcommands():
    assert resolve_admin("重置") == "cmd_reset_plugin"
    assert resolve_admin("备份") == "cmd_backup"
    assert resolve_admin("强制跳跃") == "cmd_tpd_force_skip"
    assert resolve_admin("导出") == "cmd_personalization_export"


def test_normalize_args_strips_subcommand():
    parts = normalize_args("/排行 好感 10")
    assert parts == ["/排行", "10"]
    parts = normalize_args("/纪念 添加 2026-08-08 认识纪念日")
    assert parts == ["/纪念", "2026-08-08", "认识纪念日"]
    parts = normalize_args("/状态 好感")
    assert parts == ["/状态"]


def test_normalize_args_no_subcommand():
    assert normalize_args("/图片模式") == ["/图片模式"]
    assert normalize_args("") == []


def test_keep_sub_methods():
    assert keep_sub("cmd_style_snapshot")
    assert not keep_sub("cmd_trend")


def test_help_texts_contain_parents():
    help_text = all_parent_help()
    for parent in ("状态", "回顾", "纪念", "角色", "人格", "知识",
                   "风格", "记忆", "环境", "排行"):
        assert parent in help_text
    assert "admin" in admin_help()


def test_no_legacy_command_names_in_tables():
    """10 父命令子命令中不允许残留复合旧命令名（如 '好感度'、'人格微调'）。

    /admin 与单义词子命令（天气/倒计时/跳跃等）是方案明确的迁移形态，不受限。
    """
    legacy = {"好感度", "关系阶段", "人格微调", "知识添加", "我的画像",
              "添加纪念日", "月度报告", "角色回顾", "时间回溯", "天气调试",
              "设置好感", "设置生日", "记忆添加", "风格训练"}
    for sub in PARENT_COMMANDS:
        assert sub not in legacy, f"旧命令名残留: {sub}"


def test_style_keep_sub_mapping():
    assert resolve_parent("风格", "保存") == "cmd_style_snapshot"
    assert resolve_parent("风格", "恢复") == "cmd_style_snapshot"


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS: {fn.__name__}")
            ok += 1
        except Exception:
            print(f"FAIL: {fn.__name__}")
            traceback.print_exc()
    print(f"全部 {ok}/{len(fns)} 通过")
