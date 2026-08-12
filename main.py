"""心镜 · 启明 v3.0 - 图鉴探索插件 (AstrBot)

以图鉴为核心入口的反问镜：
- /心镜 → 图鉴列表
- /心镜 [名称] → 进入图鉴探索
- 对话式追问，捕捉维度信号
- 轮廓卡呈现维度信号 + 类型参考
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

from .session import UserSession, SessionMode
from .safety import SafetyManager
from .postprocessor import process as postprocess
from .prompts import QIMING_GUIDE, QIMING_PROFILE
from .guides import GUIDE_REGISTRY, CATEGORY_ORDER, CATEGORY_ICONS, match_guide, generate_guide_list
from .profile_generator import (
    validate_profile,
    render_profile,
    generate_fallback_profile,
)
from .image_renderer import ImageRenderer

# 加载配置 schema
_CONF_SCHEMA = json.loads(
    (Path(__file__).parent / "_conf_schema.json").read_text(encoding="utf-8")
)


class SoulMirror(Star):
    """心镜 · 启明 v3.0 - 图鉴探索插件"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # ── 配置 ──
        self.guide_max_rounds: int = config.get("guide_max_rounds", 6)
        self.guide_auto_exit: bool = config.get("guide_auto_exit", True)
        self.enable_profile_on_end: bool = config.get("enable_profile_on_end", True)
        self.enable_guide_list: bool = config.get("enable_guide_list", True)
        self.list_max_aliases: int = config.get("list_max_aliases_display", 3)
        self.history_max_rounds: int = config.get("history_max_rounds", 6)
        self.session_timeout_minutes: int = config.get("session_timeout_minutes", 30)
        self.max_output_ratio: float = config.get("max_output_length_ratio", 0)
        self.end_keywords: List[str] = config.get(
            "end_keywords",
            ["结束", "再见", "拜拜", "就到这", "走了", "今天就到这"],
        )
        self.safe_mode: bool = config.get("safe_mode", True)
        self.llm_provider: str = config.get("llm_provider", "")
        self.llm_timeout: int = config.get("llm_timeout", 30)
        self.profile_max_length: int = config.get("profile_max_length", 0)

        # ── 核心引擎 ──
        self.safety_manager = SafetyManager()

        # ── 数据目录 ──
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path
        self.data_dir = Path(get_astrbot_data_path()) / "plugin_data" / "astrbot_plugin_soulsync_mirror"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # ── 图片渲染器 ──
        self.image_renderer = ImageRenderer(data_dir=self.data_dir)

        # ── 会话状态缓存 ──
        self.sessions: Dict[str, UserSession] = {}

        # ── 加载用户数据 ──
        self._load_user_data()

        total = len(GUIDE_REGISTRY)
        logger.info(
            f"SoulMirror v3.0 已加载 | "
            f"图鉴={total} | "
            f"最大轮数={self.guide_max_rounds} | "
            f"超时={self.session_timeout_minutes}分钟"
        )

    async def terminate(self):
        """插件卸载/停用时调用"""
        self._save_all()
        logger.info("SoulMirror v3.0 已停止，数据已保存")

    def _config_schema_for_page(self) -> dict:
        """为 WebUI 提供动态配置 schema（注入 LLM 服务商选项）"""
        schema = json.loads(json.dumps(_CONF_SCHEMA, ensure_ascii=False))
        provider_options = self._provider_options()
        schema["llm_provider"]["options"] = [item["id"] for item in provider_options]
        schema["llm_provider"]["option_labels"] = [item["label"] for item in provider_options]
        return schema

    def _provider_options(self) -> list:
        """获取可用的 LLM 服务商列表"""
        providers = self.context.get_all_providers()
        return [
            {"id": p["id"], "label": f"{p['id']} - {p.get('type', '')} / {p.get('model', '')}"}
            for p in providers
        ]

    # ═══════════════════════════════════════════════════════════════
    #  命令处理
    # ═══════════════════════════════════════════════════════════════

    @filter.regex(r"^心镜\s*(.*)?$")
    async def handle_mirror_command(self, event: AstrMessageEvent):
        """处理 /心镜 命令"""
        user_id = event.get_sender_id()
        command_text = event.message_str[len("心镜"):].strip()

        reply = handle_message(
            command_text=command_text,
            user_id=user_id,
            session_getter=self._get_session,
            enable_guide_list=self.enable_guide_list,
            list_max_aliases=self.list_max_aliases,
            guide_max_rounds=self.guide_max_rounds,
            end_keywords=self.end_keywords,
        )

        for msg in reply:
            # 退出标记：生成轮廓卡
            if msg == "__EXIT__":
                session = self._get_session(user_id)
                if self.enable_profile_on_end and len(session.history) > 0:
                    profile = await self._generate_profile(session)
                    if self.image_renderer.available:
                        img_path = self.image_renderer.render_profile_card(profile)
                        if img_path:
                            yield event.image_result(img_path)
                        else:
                            yield event.plain_result(profile)
                    else:
                        yield event.plain_result(profile)
                session.reset()
                yield event.plain_result("镜子已收起。")
                return

            # 列表命令：尝试渲染为图片
            if command_text == "列表" and self.image_renderer.available:
                img_path = self.image_renderer.render_guide_list(
                    guide_data=GUIDE_REGISTRY,
                    category_order=CATEGORY_ORDER,
                    category_icons=CATEGORY_ICONS,
                    total=len(GUIDE_REGISTRY),
                )
                if img_path:
                    yield event.image_result(img_path)
                    return
            yield event.plain_result(msg)

    # ═══════════════════════════════════════════════════════════════
    #  LLM 钩子 - 图鉴探索
    # ═══════════════════════════════════════════════════════════════

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req):
        """LLM请求前的处理：图鉴反问"""
        try:
            user_id = event.get_sender_id()
            session = self._get_session(user_id)

            # ── 非图鉴模式不处理 ──
            if session.mode != SessionMode.GUIDE:
                return

            query = (event.message_str or "").strip()
            if not query:
                return

            # ── 安全红线检查 ──
            if self.safe_mode:
                crisis = self.safety_manager.check_crisis(query)
                if crisis:
                    await event.send(event.plain_result(self.safety_manager.get_crisis_response(crisis)))
                    session.reset()
                    event.stop_event()
                    return

            # ── 超时检查 ──
            if session.is_timeout(self.session_timeout_minutes * 60):
                await event.send(event.plain_result("镜子已因久未对话收起。有需要随时 /心镜 重新开启。"))
                session.reset()
                event.stop_event()
                return

            # ── 结束检测 ──
            if _is_end_input(query, self.end_keywords):
                await self._handle_end(session, event)
                event.stop_event()
                return

            # ── 轮满检测 ──
            if self.guide_auto_exit and session.guide_round >= self.guide_max_rounds:
                await self._handle_end(session, event)
                event.stop_event()
                return

            # ── 生成反问 ──
            await self._process_qiming(session, query, event)
            event.stop_event()

        except Exception as e:
            logger.error(f"SoulMirror on_llm_request 异常: {e}", exc_info=True)

    async def _process_qiming(
        self,
        session: UserSession,
        user_input: str,
        event: AstrMessageEvent,
    ):
        """图鉴反问处理"""
        umo = getattr(event, "unified_msg_origin", None) or session.user_id

        # 生成反问
        reply = await self._generate_guide_reply(session, user_input, umo)

        # 后处理
        reply = postprocess(
            reply=reply,
            user_input=user_input,
            safety_manager=self.safety_manager,
            max_output_ratio=self.max_output_ratio,
        )

        # 记录对话
        session.add_turn(user_input, reply, max_rounds=self.history_max_rounds)

        # 轮次推进
        session.guide_round += 1

        await event.send(event.plain_result(reply))

    async def _generate_guide_reply(
        self, session: UserSession, user_input: str, umo: str
    ) -> str:
        """图鉴模式反问"""
        guide = GUIDE_REGISTRY.get(session.guide_key)
        if not guide:
            return _fallback_guide_reply(guide or {}, session.guide_round)

        signals_text = session.get_signals_text()
        prompt = QIMING_GUIDE.format(
            guide_name=guide["name"],
            dims="、".join(guide["dims"]),
            current_round=session.guide_round,
            max_rounds=self.guide_max_rounds,
            signals=signals_text,
            user_input=user_input,
        )

        reply = await self._call_llm(prompt, umo)
        if reply:
            return reply

        # 降级：维度轮转追问
        return _fallback_guide_reply(guide, session.guide_round)

    async def _handle_end(self, session: UserSession, event: AstrMessageEvent):
        """处理结束：出轮廓卡"""
        if self.enable_profile_on_end and len(session.history) > 0:
            profile = await self._generate_profile(session)
            if self.image_renderer.available:
                img_path = self.image_renderer.render_profile_card(profile)
                if img_path:
                    await event.send(event.image_result(img_path))
                    session.reset()
                    return
            await event.send(event.plain_result(profile))
        else:
            await event.send(event.plain_result("镜子已收。有需要时，我还在。"))

        session.reset()

    async def _generate_profile(self, session: UserSession) -> str:
        """生成轮廓卡（LLM + 降级）"""
        guide = GUIDE_REGISTRY.get(session.guide_key)
        type_refs = "、".join(guide["type_refs"]) if guide else "待辨认"

        history_text = session.get_full_history_text()
        signals_text = session.get_signals_text()

        prompt = QIMING_PROFILE.format(
            history=history_text,
            signals=signals_text,
            type_refs=type_refs,
        )

        reply = await self._call_llm(prompt, session.user_id)
        if reply:
            validation = validate_profile(reply, max_length=self.profile_max_length)
            if validation["valid"]:
                return render_profile(reply)
            else:
                logger.warning(f"轮廓卡校验失败: {validation['errors']}")
                return render_profile(reply)

        # 降级：模板轮廓卡
        fallback = generate_fallback_profile(
            signals=session.signals,
            history=session.history,
            type_refs=type_refs,
        )
        return render_profile(fallback)

    async def _call_llm(self, prompt: str, umo: str) -> Optional[str]:
        """统一 LLM 调用"""
        if not self.context:
            return None

        try:
            if self.llm_provider:
                provider_id = self.llm_provider
            else:
                provider_id = await self.context.get_current_chat_provider_id(umo=umo)

            if not provider_id:
                logger.warning("LLM: 无法获取 provider ID")
                return None

            resp = await asyncio.wait_for(
                self.context.llm_generate(
                    chat_provider_id=provider_id,
                    prompt=prompt,
                    system_prompt=QIMING_GUIDE,
                ),
                timeout=self.llm_timeout,
            )

            if resp and resp.completion_text:
                return resp.completion_text.strip()
            return None

        except asyncio.TimeoutError:
            logger.warning(f"LLM 超时（{self.llm_timeout}s）")
            return None
        except Exception as e:
            logger.warning(f"LLM 调用失败: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════
    #  辅助方法
    # ═══════════════════════════════════════════════════════════════

    def _get_session(self, user_id: str) -> UserSession:
        """获取或创建会话"""
        if user_id not in self.sessions:
            self.sessions[user_id] = UserSession(user_id=user_id)
        return self.sessions[user_id]

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
                encoding="utf-8",
            )
            logger.info("SoulMirror 用户数据已保存")
        except Exception as e:
            logger.error(f"SoulMirror 保存用户数据失败: {e}")


# ═══════════════════════════════════════════════════════════════
#  纯函数（可测试）
# ═══════════════════════════════════════════════════════════════

def handle_message(
    command_text: str,
    user_id: str,
    session_getter,
    enable_guide_list: bool = True,
    list_max_aliases: int = 3,
    guide_max_rounds: int = 6,
    end_keywords: Optional[List[str]] = None,
) -> List[str]:
    """主消息处理入口"""
    session = session_getter(user_id)

    # /心镜（空参数）
    if not command_text:
        if session.mode == SessionMode.GUIDE:
            # 探索中退出
            return ["__EXIT__"]
        else:
            # 显示图鉴列表
            return [generate_guide_list(max_aliases=list_max_aliases)]

    # 图鉴探索中：禁止切换图鉴/查看列表，只允许退出
    if session.mode == SessionMode.GUIDE:
        if command_text == "列表":
            return ["正在探索图鉴中，退出后才能查看列表。输入 /心镜 退出。"]
        guide_key = match_guide(command_text)
        if guide_key:
            guide = GUIDE_REGISTRY.get(guide_key)
            name = guide["name"] if guide else command_text
            return [f"正在探索当前图鉴，无法切换。如需切换，请先 /心镜 退出，再进入「{name}」。"]
        return [f"正在探索图鉴中。输入 /心镜 退出，或直接聊天继续探索。"]

    # /心镜 列表
    if command_text == "列表":
        if not enable_guide_list:
            return ["列表功能未启用。"]
        return [generate_guide_list(max_aliases=list_max_aliases)]

    # /心镜 [名称] → 图鉴匹配
    guide_key = match_guide(command_text)
    if guide_key:
        guide = GUIDE_REGISTRY[guide_key]
        session.activate_guide(guide_key)
        declaration = (
            f"已进入【{guide['name']}】图鉴模式。\n"
            f"我会通过聊天帮你探索这个话题，大概需要{guide_max_rounds}轮。\n"
            f"直接说你想说的就好，结束时我会生成一张「轮廓卡」给你参考。\n"
            f"输入 /心镜 随时退出。\n\n"
            f"隐私提示：对话内容仅用于生成轮廓卡，不会分享给第三方。退出后数据仅保留在本地。"
        )
        return [declaration, guide["opening"]]

    return [f"未找到图鉴「{command_text}」。输入 /心镜 列表 查看所有图鉴。"]


def _is_end_input(text: str, end_keywords: List[str]) -> bool:
    """检测用户是否想结束对话"""
    text = text.strip()
    for kw in end_keywords:
        if text == kw or text.startswith(kw):
            return True
    return False


def _fallback_guide_reply(guide: dict, round_num: int) -> str:
    """图鉴模式降级反问（无 LLM 时）"""
    dims = guide.get("dims", [])
    if not dims:
        return "你能再具体说说吗？"

    idx = round_num % len(dims)
    dim = dims[idx]
    dim_name = dim.split("：")[0] if "：" in dim else dim

    templates = [
        f"关于「{dim_name}」，你能举一个具体的例子吗？",
        f"在「{dim_name}」这个方面，你觉得自己的状态是怎样的？",
        f"你刚才说的这些，在「{dim_name}」上有什么体现？",
        f"如果给「{dim_name}」打个分，你会打几分？为什么？",
    ]
    t_idx = round_num % len(templates)
    return templates[t_idx]
