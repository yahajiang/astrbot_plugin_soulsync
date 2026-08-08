"""命令路由模块"""

from __future__ import annotations

from typing import Tuple


class CommandRouter:
    """命令路由器"""

    def __init__(self):
        self.commands = {
            "": "toggle",
            "退出": "toggle",
            "重置": "reset",
            "记住": "remember",
            "忘记": "forget",
            "状态": "status",
            "深度": "depth",
            "静默": "silent",
            "导出": "export",
            "帮助": "help",
        }

    def parse(self, command_text: str) -> Tuple[str, str]:
        """
        解析命令

        返回 (action, args)
        """
        command_text = command_text.strip()

        if not command_text:
            return "toggle", ""

        # 按空格分割
        parts = command_text.split(maxsplit=1)
        action = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        # 查找命令
        for keyword, cmd in self.commands.items():
            if action == keyword:
                return cmd, args

        # 未找到，返回原始输入
        return action, args

    def get_help(self) -> str:
        """获取帮助文本"""
        return (
            "你可以随时使用这些命令——\n"
            "/心镜 随时进入或退出\n"
            "/心镜 深度 调整反射的锐度\n"
            "/心镜 静默 开关不打扰模式\n"
            "/心镜 记住 让镜子记住你\n"
            "/心镜 忘记 让镜子忘记\n"
            "/心镜 状态 查看镜子记住了什么\n"
            "/心镜 导出 导出本轮对话\n"
            "/心镜 重置 重新开始\n"
            "不记得的时候打 /心镜 帮助"
        )
