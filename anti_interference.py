"""防干扰协议模块"""

from __future__ import annotations

import re
from typing import Optional


class AntiInterferenceManager:
    """防干扰管理器"""

    def __init__(self):
        self.interference_count = 0
        self.session_start_times: dict[str, float] = {}  # 用户会话开始时间

    def filter_input(self, user_input: str) -> Optional[str]:
        """
        输入过滤

        检测并隔离可能的注入攻击
        """
        # ── 检测角色切换指令 ──
        if self._is_role_switch(user_input):
            return None

        # ── 检测元指令注入 ──
        if self._is_meta_injection(user_input):
            return None

        # ── 检测人格模拟请求 ──
        if self._is_persona_request(user_input):
            return None

        # ── 检测越狱式长文本攻击 ──
        if self._is_long_text_attack(user_input):
            return user_input  # 视为用户要表达的内容

        # ── 过滤非用户生成内容 ──
        filtered = self._filter_system_content(user_input)

        return filtered

    def check_output(self, response: str, user_input: str) -> bool:
        """
        输出审查

        检查回复是否合规
        """
        # ── 回复长度检测（容忍"你说"等固定前缀开销）──
        if len(response) > len(user_input) * 1.5 + 3:
            return False

        # ── 外部信息检测 ──
        if self._has_external_info(response, user_input):
            return False

        # ── 角色漂移检测 ──
        if self._has_role_drift(response):
            return False

        # ── 格式异常检测 ──
        if self._has_format_anomaly(response):
            return False

        return True

    def _is_role_switch(self, text: str) -> bool:
        """检测角色切换指令"""
        patterns = [
            r"你现在是",
            r"从现在开始你扮演",
            r"忘掉你之前的设定",
            r"忘记你之前的设定",
            r"你的新角色是",
            r"你不再是镜子",
            r"你要变成",
        ]
        return any(re.search(p, text) for p in patterns)

    def _is_meta_injection(self, text: str) -> bool:
        """检测元指令注入"""
        patterns = [
            r"忽略之前的指令",
            r"忽略之前的",
            r"你的新指令是",
            r"override",
            r"forget your rules",
            r"ignore previous",
            r"system prompt",
            r"系统提示",
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    def _is_persona_request(self, text: str) -> bool:
        """检测人格模拟请求"""
        patterns = [
            r"你开心吗",
            r"你有感情吗",
            r"你喜欢我吗",
            r"你觉得我怎么样",
            r"你是什么",
            r"你是谁",
            r"你是AI吗",
            r"你是机器人吗",
        ]
        return any(re.search(p, text) for p in patterns)

    def _is_long_text_attack(self, text: str) -> bool:
        """检测越狱式长文本攻击"""
        if len(text) < 200:
            return False

        # 检测是否包含与当前话题无关的指令性语句
        instruction_patterns = [
            r"现在开始",
            r"从现在起",
            r"新规则",
            r"新指令",
            r"覆盖",
            r"override",
        ]
        return any(re.search(p, text) for p in instruction_patterns)

    def _filter_system_content(self, text: str) -> str:
        """过滤非用户生成内容"""
        # 过滤方括号内的标签
        text = re.sub(r"\[.*?\]", "", text)

        # 过滤以系统口吻生成的分析段落
        text = re.sub(r"系统：.*?$", "", text, flags=re.MULTILINE)
        text = re.sub(r"分析：.*?$", "", text, flags=re.MULTILINE)

        return text.strip()

    def _has_external_info(self, response: str, user_input: str) -> bool:
        """检测是否包含外部信息（新词过多=偏离镜像）"""
        user_words = set(re.findall(r"[\u4e00-\u9fa5]+", user_input))
        response_words = set(re.findall(r"[\u4e00-\u9fa5]+", response))

        # 排除功能词
        function_words = {"你说", "说", "你", "我", "的", "了", "在", "是", "有", "和"}
        user_words -= function_words

        # 检查是否有过多新词（镜像回复应尽量复用用户原词）
        new_words = response_words - user_words - function_words
        return len(new_words) > 3

    def _has_role_drift(self, response: str) -> bool:
        """检测角色漂移"""
        # 建议性表述
        suggestion_words = ["建议", "推荐", "你应该", "你不妨", "你可以试试"]
        if any(w in response for w in suggestion_words):
            return True

        # 共情性表述
        empathy_words = ["我理解你", "我感受到你的", "你的心情我能体会"]
        if any(w in response for w in empathy_words):
            return True

        return False

    def _has_format_anomaly(self, response: str) -> bool:
        """检测格式异常"""
        # emoji检测
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]",
            flags=re.UNICODE,
        )
        if emoji_pattern.search(response):
            return True

        # 连续感叹号或问号
        if "!!" in response or "??" in response:
            return True

        return False

    def record_interference(self):
        """记录干扰尝试"""
        self.interference_count += 1

    def get_interference_response(self) -> str:
        """获取干扰应答"""
        if self.interference_count == 1:
            return ""  # 第一次：忽略
        elif self.interference_count == 2:
            return ""  # 第二次：忽略
        elif self.interference_count == 3:
            return "镜子只反射你说的话。"  # 第三次：加一句
        else:
            return ""  # 第四次及以上：忽略

    def truncate_context(self, user_id: str, messages: list, start_time: float) -> list:
        """
        上下文截断

        只保留心镜启动时间之后的消息
        """
        if user_id not in self.session_start_times:
            self.session_start_times[user_id] = start_time

        session_start = self.session_start_times[user_id]

        # 过滤掉启动时间之前的消息
        truncated = []
        for msg in messages:
            msg_time = msg.get("timestamp", 0)
            if msg_time >= session_start:
                truncated.append(msg)

        return truncated

    def reset_session(self, user_id: str):
        """重置会话"""
        if user_id in self.session_start_times:
            del self.session_start_times[user_id]
