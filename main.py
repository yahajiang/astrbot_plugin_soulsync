"""心镜 (SoulMirror) v1.0.0 - 镜像反射对话插件 (AstrBot)

一面有回应的镜子：
- 不给建议、不共情、不分析
- 只把你此刻说出来的话，经过镜面折射后，以更清晰的形式返还给你
- 三层反射算法（复述/归因/追问）
- 五级锐度系统（水面→深渊）
- 六问破冰握手
- 动态修正机制
- 安全红线与防干扰协议
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

from .mirror_core import MirrorCore, ReflectionType, MirrorType
from .sharpness import SharpnessManager, SharpnessLevel
from .icebreaker import IcebreakerManager
from .correction import CorrectionManager, CorrectionType
from .safety import SafetyManager, CrisisLevel
from .anti_interference import AntiInterferenceManager
from .commands import CommandRouter
from .quote import QuoteManager
from .session import UserSession, SessionState
from .conflict_detector import ConflictDetector
from .repeat_detector import RepeatDetector
from .llm_mirror import LLMMirror


class SoulMirror(Star):
    """心镜 (SoulMirror) v1.0.0 - 镜像反射对话插件"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # ── 功能开关 ──
        self.enable_sharpness_auto: bool = config.get("enable_sharpness_auto", True)
        self.enable_repeat_detection: bool = config.get("enable_repeat_detection", True)
        self.enable_conflict_detection: bool = config.get("enable_conflict_detection", True)
        self.enable_quote_storage: bool = config.get("enable_quote_storage", True)
        self.silent_mode: bool = config.get("silent_mode", False)
        self.enable_llm_mirror: bool = config.get("enable_llm_mirror", True)

        # ── 核心引擎初始化 ──
        self.mirror_core = MirrorCore()
        self.sharpness_manager = SharpnessManager(
            auto_mode=self.enable_sharpness_auto
        )
        self.icebreaker_manager = IcebreakerManager()
        self.correction_manager = CorrectionManager()
        self.safety_manager = SafetyManager()
        self.anti_interference = AntiInterferenceManager()
        self.command_router = CommandRouter()
        self.conflict_detector = ConflictDetector()
        self.repeat_detector = RepeatDetector()
        self.llm_mirror = LLMMirror(context=context)

        # ── 数据目录 ──
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path
        self.data_dir = Path(get_astrbot_data_path()) / "plugin_data" / "astrbot_plugin_soulmirror"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # ── 金句管理器（需要数据目录）──
        self.quote_manager = QuoteManager(data_dir=self.data_dir)

        # ── 会话状态缓存 ──
        self.sessions: Dict[str, SessionState] = {}

        # ── 加载用户数据 ──
        self._load_user_data()

        # ── 启动日志 ──
        logger.info(
            f"SoulMirror v1.0.0 已加载 | "
            f"自动调锐={self.enable_sharpness_auto} | "
            f"重复词检测={self.enable_repeat_detection} | "
            f"矛盾检测={self.enable_conflict_detection} | "
            f"金句存储={self.enable_quote_storage} | "
            f"LLM镜像={self.enable_llm_mirror} | "
            f"静默模式={self.silent_mode}"
        )

    async def terminate(self):
        """插件卸载/停用时调用"""
        self._save_all()
        logger.info("SoulMirror v1.0.0 已停止，数据已保存")

    # ═══════════════════════════════════════════════════════════════
    #  命令处理
    # ═══════════════════════════════════════════════════════════════

    @filter.regex(r"^心镜\s*(.*)?$")
    async def handle_mirror_command(self, event: AstrMessageEvent):
        """处理 /心镜 命令"""
        user_id = event.get_sender_id()
        # AstrBot 已在 wake_prefix 阶段剥离 "/"，此处按 "心镜" 处理
        command_text = event.message_str[len("心镜"):].strip()

        # 解析命令
        action, args = self.command_router.parse(command_text)

        if action == "toggle":
            msgs = self._handle_toggle(user_id)
        elif action == "reset":
            msgs = self._handle_reset(user_id)
        elif action == "remember":
            msgs = self._handle_remember(user_id)
        elif action == "forget":
            msgs = self._handle_forget(user_id, args)
        elif action == "status":
            msgs = self._handle_status(user_id)
        elif action == "depth":
            msgs = self._handle_depth(user_id, args)
        elif action == "silent":
            msgs = self._handle_silent(user_id)
        elif action == "export":
            msgs = self._handle_export(user_id)
        elif action == "help":
            msgs = self._handle_help(user_id)
        else:
            msgs = [f"未知命令：{action}。输入 /心镜 帮助 查看所有命令。"]

        for msg in msgs:
            yield event.plain_result(msg)

    def _handle_toggle(self, user_id: str) -> List[str]:
        """切换镜像模式"""
        session = self._get_session(user_id)
        msgs = []

        if session.state == SessionState.MIRROR_MODE:
            # 退出镜像模式
            if not self.silent_mode:
                msgs.append(self._generate_summary(session))
            session.state = SessionState.IDLE
            msgs.append("镜子已收起。")
        else:
            # 进入镜像模式
            session.reset()
            session.state = SessionState.DECLARATION
            session.session_start_time = time.time()
            self.anti_interference.session_start_times[user_id] = session.session_start_time
            msgs.append(self._get_declaration(full=True))

            # 自动展示命令列表
            msgs.append(self.command_router.get_help())

            # 开始破冰
            session.state = SessionState.ICEBREAKER_FIXED
            first_question = self.icebreaker_manager.get_next_question(session)
            if first_question:
                msgs.append(first_question)

        return msgs

    def _handle_reset(self, user_id: str) -> List[str]:
        """重置会话"""
        session = self._get_session(user_id)
        session.reset()
        session.state = SessionState.DECLARATION
        msgs = [self._get_declaration(full=True)]

        # 自动展示命令列表
        msgs.append(self.command_router.get_help())

        # 开始破冰
        session.state = SessionState.ICEBREAKER_FIXED
        first_question = self.icebreaker_manager.get_next_question(session)
        if first_question:
            msgs.append(first_question)

        return msgs

    def _handle_remember(self, user_id: str) -> List[str]:
        """保存当前信息"""
        session = self._get_session(user_id)
        self.quote_manager.save_session(user_id, session)
        return ["已保存。下次进入时，镜子会记得你说过的话。"]

    def _handle_forget(self, user_id: str, args: str) -> List[str]:
        """擦除记忆"""
        if args:
            # 擦除指定条目
            self.quote_manager.remove_quote(user_id, args)
            return [f"已忘记：{args}"]
        else:
            # 全部擦除
            self.quote_manager.clear_all(user_id)
            return ["已清空所有记忆。"]

    def _handle_status(self, user_id: str) -> List[str]:
        """查看状态"""
        session = self._get_session(user_id)
        quotes = self.quote_manager.get_quotes(user_id)
        status = (
            f"称呼：{session.nickname or '未设置'}\n"
            f"当前锐度：{self.sharpness_manager.get_current_level(session).value}\n"
            f"静默模式：{'开启' if self.silent_mode else '关闭'}\n"
            f"金句数量：{len(quotes)}"
        )
        return [status]

    def _handle_depth(self, user_id: str, args: str) -> List[str]:
        """查看或设定锐度"""
        session = self._get_session(user_id)
        if not args:
            level = self.sharpness_manager.get_current_level(session)
            mode = "自动" if self.sharpness_manager.auto_mode else "手动"
            return [f"当前锐度：{level.value}（{mode}）"]
        elif args == "自动":
            self.sharpness_manager.set_auto_mode(True)
            return ["已恢复自动调锐模式。"]
        else:
            try:
                level = SharpnessLevel(int(args))
                self.sharpness_manager.set_manual_level(level)
                return [
                    f"镜面调至锐度{level.value}。反射会更直接，如果觉得太锐，随时可以调回来。"
                ]
            except ValueError:
                return ["锐度范围：1-5 或 自动"]

    def _handle_silent(self, user_id: str) -> List[str]:
        """切换静默模式"""
        self.silent_mode = not self.silent_mode
        self.config["silent_mode"] = self.silent_mode
        status = "开启" if self.silent_mode else "关闭"
        return [f"静默模式已{status}。"]

    def _handle_export(self, user_id: str) -> List[str]:
        """导出本次会话"""
        session = self._get_session(user_id)
        export = self._export_session(session)
        return [export]

    def _handle_help(self, user_id: str) -> List[str]:
        """显示帮助"""
        help_text = (
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
        return [help_text]

    # ═══════════════════════════════════════════════════════════════
    #  LLM 钩子 - 镜像反射处理
    # ═══════════════════════════════════════════════════════════════

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req):
        """LLM请求前的处理：镜像反射

        仅在镜像模式（含破冰阶段）拦截用户消息并反射，
        处理完成后通过 stop_event 阻止 LLM 生成。
        """
        try:
            user_id = event.get_sender_id()
            session = self._get_session(user_id)

            # ── 非镜像/破冰模式，不处理 ──
            if session.state not in (
                SessionState.MIRROR_MODE,
                SessionState.ICEBREAKER_FIXED,
                SessionState.ICEBREAKER_RANDOM,
            ):
                return

            query = (event.message_str or "").strip()
            if not query:
                return

            # ── 安全红线检查 ──
            crisis = self.safety_manager.check_crisis(query)
            if crisis:
                await event.send(event.plain_result(self.safety_manager.get_crisis_response(crisis)))
                session.state = SessionState.IDLE
                event.stop_event()
                return

            # ── 输入过滤（防干扰）──
            filtered_input = self.anti_interference.filter_input(query)
            if filtered_input is None:
                # 检测到注入攻击
                await event.send(event.plain_result("镜子不换角色。你想说什么？"))
                event.stop_event()
                return

            # ── 破冰阶段处理 ──
            if session.state in (SessionState.ICEBREAKER_FIXED, SessionState.ICEBREAKER_RANDOM):
                await self._process_icebreaker(session, filtered_input, event)
                event.stop_event()
                return

            # ── 镜像反射处理 ──
            await self._process_mirror(session, filtered_input, event)
            event.stop_event()
        except Exception as e:
            logger.error(f"SoulMirror on_llm_request 异常: {e}", exc_info=True)

    async def _process_icebreaker(
        self,
        session: UserSession,
        filtered_input: str,
        event: AstrMessageEvent,
    ):
        """破冰阶段处理"""
        response = self.icebreaker_manager.process_response(session, filtered_input)
        await event.send(event.plain_result(response))

        # 更新破冰阶段
        session.icebreaker_stage += 1

        # 检查破冰是否完成
        if self.icebreaker_manager.is_complete(session):
            session.state = SessionState.MIRROR_MODE
            await event.send(event.plain_result(f"{session.nickname}，镜子准备好了。你说，我听。"))
        else:
            # 获取下一个问题
            next_question = self.icebreaker_manager.get_next_question(session)
            if next_question:
                await event.send(event.plain_result(next_question))

    async def _process_mirror(
        self,
        session: UserSession,
        filtered_input: str,
        event: AstrMessageEvent,
    ):
        """镜像反射处理"""
        user_id = event.get_sender_id()
        # ── 修正检测 ──
        correction = self.correction_manager.detect(session, filtered_input)
        if correction:
            if correction.type == CorrectionType.NICKNAME:
                session.nickname = correction.new_value
                await event.send(event.plain_result(f"好，之后叫你 {correction.new_value}。"))
            else:
                annotation = self.correction_manager.get_annotation(session, correction)
                if annotation:
                    session.correction_count += 1
                    session.last_correction_time = time.time()
                    await event.send(event.plain_result(annotation))

        # ── 矛盾检测 ──
        if self.enable_conflict_detection:
            conflict = self.conflict_detector.detect(session, filtered_input)
            if conflict:
                session.conflicts.append(conflict)
                await event.send(event.plain_result(self.conflict_detector.get_conflict_response(conflict)))

        # ── 重复词检测 ──
        if self.enable_repeat_detection:
            repeat = self.repeat_detector.detect(session, filtered_input)
            if repeat:
                session.repeats.append(repeat)
                await event.send(event.plain_result(repeat.response))

        # ── 自动调锐 ──
        if self.enable_sharpness_auto:
            self.sharpness_manager.auto_adjust(session, filtered_input)

        # ── 生成镜像反射 ──
        response = None
        used_llm = False

        # 优先使用 LLM 镜像（如果启用）
        if self.enable_llm_mirror:
            umo = getattr(event, "unified_msg_origin", None) or user_id
            response = await self.llm_mirror.reflect(
                user_input=filtered_input,
                umo=umo,
                conversation_history=session.dialogue_history,
            )
            used_llm = response is not None

        # LLM 不可用或失败时，降级到算法反射
        if response is None:
            sharpness = self.sharpness_manager.get_current_level(session)
            response = self.mirror_core.reflect(
                user_input=filtered_input,
                session=session,
                sharpness=sharpness,
            )

        # ── 输出审查（LLM 回复放宽新词限制，只查角色漂移/格式）──
        if self.anti_interference.check_output(response, filtered_input, strict=not used_llm):
            await event.send(event.plain_result(response))
        else:
            # 输出异常，降级处理
            await event.send(event.plain_result(self.mirror_core.reflect_simple(filtered_input)))

    # ═══════════════════════════════════════════════════════════════
    #  辅助方法
    # ═══════════════════════════════════════════════════════════════

    def _get_session(self, user_id: str) -> UserSession:
        """获取或创建会话"""
        if user_id not in self.sessions:
            self.sessions[user_id] = UserSession(user_id=user_id)
        return self.sessions[user_id]

    def _get_declaration(self, full: bool = True) -> str:
        """获取声明文本"""
        if full:
            return (
                "心镜不是聊天机器人。它不会给你建议，不会安慰你，不会评价你。"
                "它唯一做的事，是把你现在说的话，重新说给你听——用一种让你更清楚自己在说什么的方式。\n\n"
                "每一次对话都是独立的。你上一次说过什么，它不记得。它只知道你正在打的这行字。\n\n"
                "你说的所有内容，只存在于当前对话中。只有你主动说「记住」，信息才会被保存到你的设备上。"
                "不上传，不记录到任何服务器。\n\n"
                "如果你说了很严重的话，镜子会停下来，帮你去找真正能帮你的人。"
                "这不是它的功能缺陷，是它知道自己不擅长什么。\n\n"
                "一切准备好了，我们聊几句。"
            )
        else:
            return (
                "心镜是一面镜子：你说什么，它帮你看清你在说什么。"
                "它不给建议，不评价，不记录你说的话——除非你主动让它记住。"
            )

    def _generate_summary(self, session: SessionState) -> str:
        """生成退出总结"""
        if not session.dialogue_history:
            return "本轮对话到此结束。没有留下什么，镜子只是静静待了一会儿。"

        # Level 2：捕捉对话变化轨迹
        trajectory_summary = self._get_trajectory_summary(session)
        if trajectory_summary:
            return trajectory_summary

        # Level 1：列出频次最高的三个实义词
        word_freq = {}
        for entry in session.dialogue_history:
            words = self.mirror_core.extract_content_words(entry.user_input)
            for word in words:
                word_freq[word] = word_freq.get(word, 0) + 1

        if not word_freq:
            return "本轮对话到此结束。你说了一些话，镜子帮你记着。"

        top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:3]
        words_text = "、".join([f"『{w}』" for w, _ in top_words])

        return f"本轮对话到此结束。你提到了{words_text}。这些是你说的，镜子只是帮你记下来。"

    def _get_trajectory_summary(self, session: SessionState) -> str:
        """获取对话变化轨迹摘要（Level 2）"""
        if len(session.dialogue_history) < 4:
            return ""

        # 检测情绪变化
        early_emotions = []
        late_emotions = []

        for i, entry in enumerate(session.dialogue_history):
            emotion = self.mirror_core._extract_emotion(entry.user_input)
            if emotion:
                if i < len(session.dialogue_history) // 2:
                    early_emotions.append(emotion)
                else:
                    late_emotions.append(emotion)

        if early_emotions and late_emotions:
            early_main = max(set(early_emotions), key=early_emotions.count)
            late_main = max(set(late_emotions), key=late_emotions.count)

            if early_main != late_main:
                return (
                    f"你在前半段一直在说'{early_main}'，"
                    f"从后半段开始说'{late_main}'。"
                    f"从'{early_main}'到'{late_main}'，这中间发生了什么，只有你知道。"
                )

        # 检测用词变化
        first_input = session.dialogue_history[0].user_input
        last_input = session.dialogue_history[-1].user_input

        first_words = set(self.mirror_core.extract_content_words(first_input))
        last_words = set(self.mirror_core.extract_content_words(last_input))

        if first_words and last_words:
            common = first_words & last_words
            if not common and len(first_words) > 0 and len(last_words) > 0:
                return (
                    f"你一开始在说『{'』『'.join(list(first_words)[:2])}』，"
                    f"后来转向了『{'』『'.join(list(last_words)[:2])}』。"
                    f"这个转变，是怎么发生的？"
                )

        return ""

    def _export_session(self, session: SessionState) -> str:
        """导出会话摘要"""
        if not session.dialogue_history:
            return "本次会话没有对话记录。"

        lines = ["=== 心镜会话导出 ===\n"]
        for i, entry in enumerate(session.dialogue_history, 1):
            lines.append(f"[{i}] 你：{entry.user_input}")
            lines.append(f"    镜：{entry.mirror_response}\n")

        return "\n".join(lines)

    def _load_user_data(self):
        """加载用户数据"""
        try:
            data_file = self.data_dir / "user_data.json"
            if data_file.exists():
                data = json.loads(data_file.read_text(encoding="utf-8"))
                for user_id, user_data in data.items():
                    session = self._get_session(user_id)
                    session.load_from_dict(user_data)
                logger.info(f"SoulMirror 已加载 {len(data)} 个用户数据")
        except Exception as e:
            logger.error(f"SoulMirror 加载用户数据失败: {e}")

    def _save_all(self):
        """保存所有用户数据"""
        try:
            data = {}
            for user_id, session in self.sessions.items():
                data[user_id] = session.to_dict()

            data_file = self.data_dir / "user_data.json"
            data_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            logger.info("SoulMirror 用户数据已保存")
        except Exception as e:
            logger.error(f"SoulMirror 保存用户数据失败: {e}")
