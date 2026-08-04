"""心旅知音 (SoulSync) v2.11 - 融合版情感智能插件 (AstrBot)

融合 EmotionAI 与 FavourPro 精华，支持：
- 8 维情感模型 + 好感/亲密度双核
- 六阶段关系演进 + 负好感阶段
- 四维智能更新（关键词+时间+计数+LLM标记）
- 辅助 LLM 情感分析专家（注入关系角色 persona）
- 长期记忆 + 近期对话缓存
- 惩罚奖励机制（行为势头/冷落惩罚/回归奖励/背叛检测/道歉恢复/里程碑）
- 纪念日/节日系统（农历换算 + 认识里程碑 + 节日奖励）
- 情感数据统计（每日快照 + 趋势图表）
- 关系角色系统（39 角色：内容自动判定 + 解锁/一次性切换锁定 + 管理员可调）
- 时间感知（节假日/农历/时段）与指令输出转图片（Pillow，无依赖降级文本）
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api.web import error_response, json_response, request
from astrbot.core.agent.message import TextPart

from .emotion_engine import (
    EmotionEngine, EmotionProfile, STAGES, NEGATIVE_STAGES,
    EMOTION_DIMENSIONS, DIM_LABELS, DIM_ICONS,
    intimacy_from_favorability, FAVORABILITY_MAX,
)
from .smart_updater import SmartUpdater
from .memory_manager import LongTermMemory
from .llm_analyzer import LLMAnalyzer
from .penalty_reward import PenaltyRewardEngine, BehaviorProfile, MILESTONES
from .anniversary import AnniversaryManager, parse_month_day
from .stats_tracker import StatsTracker
from .relationship_roles import (
    RelationshipRoleManager,
    resolve_relationship_key,
    SYSTEM_ROLES_BY_KEY,
)
from .image_renderer import ImageRenderer
from .time_perception import (
    load_calendar_dependencies,
    build_time_info,
    build_holiday_info,
    build_lunar_info,
)


class SoulSyncPro(Star):
    """心旅知音 (SoulSync) v2.11 - 融合版情感智能插件（含惩罚奖励机制、关系角色）"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # ── 功能开关 ──
        self.enable_attitude: bool = config.get("enable_attitude_system", True)
        self.enable_secondary_llm: bool = config.get("enable_secondary_llm", True)
        self.enable_smart_update: bool = config.get("enable_smart_update", True)

        # ── 情感参数 ──
        self.default_favorability: float = config.get("default_favorability", 0.0)
        self.sensitivity: float = config.get("keyword_sensitivity", 1.0)

        # ── 智能更新参数 ──
        self.force_interval: int = config.get("force_update_interval", 5)
        self.keyword_threshold: float = config.get("keyword_update_threshold", 2.0)
        self.time_threshold_sec: float = float(config.get("time_update_threshold_sec", 120))

        # ── LLM 熔断机制 ──
        self._llm_circuit_broken: bool = False
        self._llm_fail_count: int = 0
        self._llm_circuit_threshold: int = 3

        # ── 记忆与存储 ──
        self.significance_threshold: float = config.get("emotional_significance_threshold", 5.0)
        self.max_ltm_events: int = config.get("max_long_term_events", 50)
        self.auto_save_sec: int = config.get("auto_save_interval_sec", 300)

        # ── 隐私与安全 ──
        self.session_based: bool = config.get("session_based", False)
        self.admin_ids: set = self._parse_admin_ids(config.get("admin_ids", ""))

        # ── 惩罚奖励参数（动态读取，支持热更新）──
        self.pr_enable_momentum: bool = config.get("pr_enable_momentum", True)
        self.pr_enable_cold_penalty: bool = config.get("pr_enable_cold_penalty", True)
        self.pr_enable_comeback_reward: bool = config.get("pr_enable_comeback_reward", True)
        self.pr_enable_milestone_reward: bool = config.get("pr_enable_milestone_reward", True)
        self.pr_enable_betrayal_penalty: bool = config.get("pr_enable_betrayal_penalty", True)
        self.pr_enable_apology_recovery: bool = config.get("pr_enable_apology_recovery", True)
        self.pr_cold_threshold_hours: float = config.get("pr_cold_threshold_hours", 24)
        self.pr_comeback_threshold_hours: float = config.get("pr_comeback_threshold_hours", 48)
        self.pr_decay_half_life_hours: float = config.get("pr_decay_half_life_hours", 72)
        self.pr_momentum_reward_per_level: float = config.get("pr_momentum_reward_per_level", 0.24)
        self.pr_momentum_penalty_per_level: float = config.get("pr_momentum_penalty_per_level", -0.8)

        # ── 纪念日/节日参数（动态读取，支持热更新）──
        self.anniv_fav_bonus: float = config.get("anniv_fav_bonus", 2.5)
        self.anniv_int_bonus: float = config.get("anniv_int_bonus", 1.5)
        self.festival_fav_bonus: float = config.get("festival_fav_bonus", 1.8)
        self.festival_int_bonus: float = config.get("festival_int_bonus", 1.0)

        # ── 数据统计参数 ──
        self.stats_history_days: int = config.get("stats_history_days", 30)
        self.trend_default_days: int = config.get("trend_default_days", 14)

        # ── 图片输出参数 ──
        self.image_output_default: bool = config.get("image_output_default", False)

        # ── 引擎初始化 ──
        self.emotion_engine = EmotionEngine(sensitivity=self.sensitivity)
        self.smart_updater = SmartUpdater(
            force_interval=self.force_interval,
            keyword_threshold=self.keyword_threshold,
            time_threshold_sec=self.time_threshold_sec,
            sensitivity=self.sensitivity,
        )
        self.llm_analyzer = LLMAnalyzer()
        self.penalty_reward_engine = PenaltyRewardEngine(
            cold_threshold_hours=self.pr_cold_threshold_hours,
            comeback_threshold_hours=self.pr_comeback_threshold_hours,
            decay_half_life_hours=self.pr_decay_half_life_hours,
            momentum_reward_per_level=self.pr_momentum_reward_per_level,
            momentum_penalty_per_level=self.pr_momentum_penalty_per_level,
            enable_cold_penalty=self.pr_enable_cold_penalty,
            enable_comeback_reward=self.pr_enable_comeback_reward,
            enable_milestone_reward=self.pr_enable_milestone_reward,
            enable_betrayal_penalty=self.pr_enable_betrayal_penalty,
            enable_apology_recovery=self.pr_enable_apology_recovery,
            enable_momentum=self.pr_enable_momentum,
        )

        # ── 数据目录 ──
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path
        self.data_dir = Path(get_astrbot_data_path()) / "plugin_data" / "astrbot_plugin_soulsync"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # ── 存储 ──
        self.profiles: Dict[str, EmotionProfile] = {}
        self.behavior_profiles: Dict[str, BehaviorProfile] = {}
        self.long_memory = LongTermMemory(self.data_dir, max_events_per_user=self.max_ltm_events)
        self.show_status: Dict[str, bool] = {}

        # ── 近期对话缓存（用于辅助 LLM 分析）──
        self.recent_messages: Dict[str, List[str]] = {}

        # ── 新功能管理器 ──
        self.anniversary_manager = AnniversaryManager(self.data_dir)
        self.stats_tracker = StatsTracker(self.data_dir, max_days=self.stats_history_days)
        self.relationship_manager = RelationshipRoleManager(self.data_dir)
        self.image_renderer = ImageRenderer(self.data_dir)
        self.image_mode: Dict[str, bool] = {}

        # ── 时间感知（仿 LLMPerception）──
        load_calendar_dependencies()
        import zoneinfo
        tz_name = self.config.get("timezone", "Asia/Shanghai")
        try:
            self.timezone = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            self.timezone = zoneinfo.ZoneInfo("Asia/Shanghai")
            logger.warning(f"SoulSync 无效时区 '{tz_name}'，使用 Asia/Shanghai")

        # ── 加载数据 ──
        self._load_profiles()
        self._load_behavior_profiles()
        self._load_show_status()
        self._load_image_mode()

        # ── 自动保存任务 ──
        self._save_task = None
        self._start_auto_save()

        # ── 注册 WebUI API ──
        self._setup_webui()

        # ── 启动日志 ──
        logger.info(
            f"SoulSync v2.11 已加载 | "
            f"智能更新={self.enable_smart_update} | "
            f"辅助LLM={self.enable_secondary_llm} | "
            f"态度系统={self.enable_attitude} | "
            f"纪念日={self.config.get('enable_anniversary_system', True)} | "
            f"关系角色={self.config.get('enable_relationship_roles', True)} | "
            f"时间感知={self.config.get('enable_time_perception', True)} | "
            f"节假日感知={self.config.get('enable_holiday_perception', True)} | "
            f"农历感知={self.config.get('enable_lunar_perception', True)} | "
            f"图片输出={'可用' if self.image_renderer.available else '降级文本'} | "
            f"惩罚奖励={self.pr_enable_momentum or self.pr_enable_cold_penalty or self.pr_enable_comeback_reward} | "
            f"已加载 {len(self.profiles)} 个档案"
        )

    # ═══════════════════════════════════════════════════════════════
    #  生命周期
    # ═══════════════════════════════════════════════════════════════
    async def terminate(self):
        """插件卸载/停用时调用"""
        if self._save_task and not self._save_task.done():
            self._save_task.cancel()
        self._save_all()
        logger.info("SoulSync v2.11 已停止，数据已保存")

    # ═══════════════════════════════════════════════════════════════
    #  WebUI
    # ═══════════════════════════════════════════════════════════════
    _PLUGIN_ROUTE = "astrbot_plugin_soulsync"

    def _setup_webui(self):
        """注册 WebUI API 路由"""
        try:
            self.context.register_web_api(
                f"/{self._PLUGIN_ROUTE}/data", self._web_data, ["GET"],
                "SoulSync: 获取档案与行为数据",
            )
            self.context.register_web_api(
                f"/{self._PLUGIN_ROUTE}/config", self._web_config_get, ["GET"],
                "SoulSync: 获取配置",
            )
            self.context.register_web_api(
                f"/{self._PLUGIN_ROUTE}/config", self._web_config_post, ["POST"],
                "SoulSync: 保存配置",
            )
            self.context.register_web_api(
                f"/{self._PLUGIN_ROUTE}/admin", self._web_admin, ["POST"],
                "SoulSync: 管理操作",
            )
            logger.info("SoulSync WebUI 路由注册成功")
        except Exception as e:
            logger.error(f"SoulSync WebUI 路由注册失败: {e}")

    async def _web_data(self):
        """GET - 档案数据"""
        try:
            import datetime as _dt
            today = _dt.date.today()
            profiles = []
            for p in self.profiles.values():
                d = p.to_dict()
                d["stage_label"] = self._get_stage_label(p)
                d["anniversaries"] = self.anniversary_manager.list_user_anniversaries(
                    p.user_id, today
                )
                d["trend"] = self.stats_tracker.to_web(p.user_id, 7)
                d["trend_summary"] = self.stats_tracker.summary(p.user_id, 7)
                d["relationships"] = self.relationship_manager.status(
                    p.user_id, p.favorability, p.intimacy, p.total_interactions
                )
                d["rel_active"] = self.relationship_manager.active_role(p.user_id)
                d["rel_locked"] = self.relationship_manager.is_locked(p.user_id)
                d["rel_pinned"] = self.relationship_manager.pinned_role(p.user_id)
                d["rel_custom"] = self.relationship_manager.custom_info(p.user_id)
                d["memory"] = self.long_memory.get_events(p.user_id, 20)
                profiles.append(d)
            bps = [bp.to_dict() for bp in self.behavior_profiles.values()]
            return json_response({
                "profiles": profiles,
                "behavior_profiles": bps,
                "festivals": self.anniversary_manager.get_festivals(),
                "relationship_roles": self.relationship_manager.status(
                    "", 0.0, 0.0, 0
                ),
            })
        except Exception as e:
            return error_response(str(e))

    async def _web_config_get(self):
        """GET - 配置数据"""
        try:
            cfg = {}
            for k in list(self.config.keys()):
                if not k.startswith("_"):
                    try:
                        cfg[k] = self.config.get(k)
                    except Exception:
                        pass
            schema = {}
            p = Path(__file__).parent / "_conf_schema.json"
            if p.exists():
                schema = json.loads(p.read_text(encoding="utf-8"))
            return json_response({"config": cfg, "schema": schema})
        except Exception as e:
            return error_response(str(e))

    async def _web_config_post(self):
        """POST - 保存配置"""
        try:
            body = await request.json(default={})
            if not isinstance(body, dict):
                return error_response("请求体必须是 JSON 对象")
            raw = body.get("config", body)
            for k, v in raw.items():
                if not k.startswith("_"):
                    try:
                        self.config[k] = v
                    except Exception:
                        pass
            fn = getattr(self.config, "save_config", None)
            if callable(fn):
                fn()
            self._sync_runtime_config()
            return json_response({"ok": True, "message": "配置已保存"})
        except Exception as e:
            return error_response(str(e))

    def _sync_runtime_config(self):
        """将 WebUI 保存的配置同步到运行时缓存属性（支持热更新，无需重载插件）"""
        try:
            # ── 功能开关 ──
            self.enable_attitude = bool(self.config.get("enable_attitude_system", True))
            self.enable_secondary_llm = bool(self.config.get("enable_secondary_llm", True))
            self.enable_smart_update = bool(self.config.get("enable_smart_update", True))

            # ── 情感参数 ──
            self.default_favorability = float(self.config.get("default_favorability", 0.0))
            self.sensitivity = float(self.config.get("keyword_sensitivity", 1.0))
            self.emotion_engine.sensitivity = self.sensitivity

            # ── 智能更新参数 ──
            self.force_interval = int(self.config.get("force_update_interval", 5))
            self.keyword_threshold = float(self.config.get("keyword_update_threshold", 2.0))
            self.time_threshold_sec = float(self.config.get("time_update_threshold_sec", 120))
            self.smart_updater.force_interval = self.force_interval
            self.smart_updater.keyword_threshold = self.keyword_threshold
            self.smart_updater.time_threshold_sec = self.time_threshold_sec
            self.smart_updater.sensitivity = self.sensitivity

            # ── 记忆与存储 ──
            self.significance_threshold = float(self.config.get("emotional_significance_threshold", 5.0))
            self.max_ltm_events = int(self.config.get("max_long_term_events", 50))

            # ── 隐私与安全 ──
            self.session_based = bool(self.config.get("session_based", False))
            self.admin_ids = self._parse_admin_ids(self.config.get("admin_ids", ""))

            # ── 惩罚奖励参数 ──
            self.pr_enable_momentum = bool(self.config.get("pr_enable_momentum", True))
            self.pr_enable_cold_penalty = bool(self.config.get("pr_enable_cold_penalty", True))
            self.pr_enable_comeback_reward = bool(self.config.get("pr_enable_comeback_reward", True))
            self.pr_enable_milestone_reward = bool(self.config.get("pr_enable_milestone_reward", True))
            self.pr_enable_betrayal_penalty = bool(self.config.get("pr_enable_betrayal_penalty", True))
            self.pr_enable_apology_recovery = bool(self.config.get("pr_enable_apology_recovery", True))
            self.pr_cold_threshold_hours = float(self.config.get("pr_cold_threshold_hours", 24))
            self.pr_comeback_threshold_hours = float(self.config.get("pr_comeback_threshold_hours", 48))
            self.pr_decay_half_life_hours = float(self.config.get("pr_decay_half_life_hours", 72))
            self.pr_momentum_reward_per_level = float(self.config.get("pr_momentum_reward_per_level", 0.24))
            self.pr_momentum_penalty_per_level = float(self.config.get("pr_momentum_penalty_per_level", -0.8))
            try:
                self.penalty_reward_engine.update_config(
                    cold_threshold_hours=self.pr_cold_threshold_hours,
                    comeback_threshold_hours=self.pr_comeback_threshold_hours,
                    decay_half_life_hours=self.pr_decay_half_life_hours,
                    momentum_reward_per_level=self.pr_momentum_reward_per_level,
                    momentum_penalty_per_level=self.pr_momentum_penalty_per_level,
                    enable_cold_penalty=self.pr_enable_cold_penalty,
                    enable_comeback_reward=self.pr_enable_comeback_reward,
                    enable_milestone_reward=self.pr_enable_milestone_reward,
                    enable_betrayal_penalty=self.pr_enable_betrayal_penalty,
                    enable_apology_recovery=self.pr_enable_apology_recovery,
                    enable_momentum=self.pr_enable_momentum,
                )
            except Exception:
                pass

            # ── 纪念日/节日参数 ──
            self.anniv_fav_bonus = float(self.config.get("anniv_fav_bonus", 2.5))
            self.anniv_int_bonus = float(self.config.get("anniv_int_bonus", 1.5))
            self.festival_fav_bonus = float(self.config.get("festival_fav_bonus", 1.8))
            self.festival_int_bonus = float(self.config.get("festival_int_bonus", 1.0))

            # ── 数据统计参数 ──
            self.stats_history_days = int(self.config.get("stats_history_days", 30))
            self.trend_default_days = int(self.config.get("trend_default_days", 14))

            # ── 图片输出参数 ──
            self.image_output_default = bool(self.config.get("image_output_default", False))

            # ── 时区 ──
            tz_name = self.config.get("timezone", "Asia/Shanghai")
            try:
                import zoneinfo
                self.timezone = zoneinfo.ZoneInfo(tz_name)
            except Exception:
                pass

            logger.debug("SoulSync 运行时配置已热同步")
        except Exception as e:
            logger.warning(f"SoulSync 配置热同步失败: {e}")

    async def _web_admin(self):
        """POST - 管理操作"""
        try:
            body = await request.json(default={})
            act = body.get("action", "")
            uid = body.get("user_id", "")
            val = body.get("value")
            name = body.get("name", "") or str(body.get("value", "") or "")

            if act in ("unlock_relationship", "switch_relationship") and uid and name:
                # WebUI 为管理员工具：强制解锁/切换并清除用户锁定（手动模式调整）
                key = resolve_relationship_key(str(name))
                if not key:
                    return error_response(f"未知关系角色: {name}")
                ok, msg = self.relationship_manager.admin_switch(uid, key)
                if ok:
                    self._save_all()
                return json_response({"ok": ok, "message": msg})

            if act == "add_festival" and name and val:
                md = parse_month_day(str(val))
                if not md:
                    return error_response("日期格式应为 MM-DD")
                ok, msg = self.anniversary_manager.add_festival(str(name), md[0], md[1])
                if ok:
                    self._save_all()
                return json_response({"ok": ok, "message": msg})

            if act == "remove_festival" and name:
                ok, msg = self.anniversary_manager.remove_festival(str(name))
                if ok:
                    self._save_all()
                return json_response({"ok": ok, "message": msg})

            if not uid:
                return error_response("缺少 user_id")

            if act == "set_favorability" and val is not None:
                val = max(-100, min(FAVORABILITY_MAX, float(val)))
                old, _ = self._set_profile_value(uid, fav=val)
                self._save_all()
                return json_response({"ok": True, "message": f"好感度 {old:+.1f} → {val:+.1f}"})

            elif act == "set_intimacy" and val is not None:
                # 亲密度已改为按好感度百分比派生，不再独立设置
                return json_response({"ok": False, "message": "亲密度按好感度百分比派生（亲密度=(好感+100)/3），请调整好感度"})

            elif act == "reset":
                self.profiles.pop(uid, None)
                self.behavior_profiles.pop(uid, None)
                self.long_memory.clear_user(uid)
                self._save_all()
                return json_response({"ok": True, "message": f"已重置 {uid}"})

            return error_response(f"未知操作: {act}")
        except Exception as e:
            return error_response(str(e))

    # ═══════════════════════════════════════════════════════════════
    #  用户命令
    # ═══════════════════════════════════════════════════════════════

    @filter.command("好感度")
    async def cmd_favorability(self, event: AstrMessageEvent):
        """查看当前情感状态（含惩罚奖励信息）"""
        profile = self._get_or_create_profile(event)
        bp = self._get_or_create_behavior_profile(self._get_user_id(event))
        lines = self._format_profile(profile, event, detail=False, behavior_profile=bp)
        path = self._try_render_image(event, "情感状态", lines)
        if path:
            yield event.image_result(path)
        else:
            yield event.plain_result("\n".join(lines))

    @filter.command("状态显示")
    async def cmd_toggle_status(self, event: AstrMessageEvent):
        """切换是否在对话后显示情感状态"""
        uid = self._get_user_id(event)
        current = self.show_status.get(uid, self.config.get("show_status_default", False))
        self.show_status[uid] = not current
        self._save_show_status()
        state = "开启 ✅" if self.show_status[uid] else "关闭 ❌"
        yield event.plain_result(f"情感状态显示已{state}")

    @filter.command("好感排行")
    async def cmd_leaderboard(self, event: AstrMessageEvent):
        """查看好感度排行榜 TOP n"""
        for res in self._render_leaderboard(event, positive=True):
            yield res

    @filter.command("负好感排行")
    async def cmd_negative_leaderboard(self, event: AstrMessageEvent):
        """查看负好感排行榜 BOTTOM n"""
        for res in self._render_leaderboard(event, positive=False):
            yield res

    def _render_leaderboard(self, event, positive: bool):
        parts = event.message_str.split()
        n = 10
        if len(parts) >= 2:
            try:
                n = int(parts[1])
            except ValueError:
                pass
        n = max(1, min(20, n))
        if positive:
            sorted_profiles = sorted(
                self.profiles.values(), key=lambda p: p.favorability, reverse=True
            )[:n]
            if not sorted_profiles:
                yield event.plain_result("暂无情感数据。")
                return
            title = f"🏆 好感度排行榜 TOP {n}"
            lines = [title, "━" * 24]
        else:
            sorted_profiles = sorted(
                self.profiles.values(), key=lambda p: p.favorability
            )[:n]
            if not sorted_profiles:
                yield event.plain_result("暂无负好感数据。")
                return
            title = f"💀 负好感排行榜 BOTTOM {n}"
            lines = [title, "━" * 24]
        entries = []
        for i, p in enumerate(sorted_profiles, 1):
            stage = self._get_stage_label(p) if positive else self._get_negative_stage_label(p.favorability)
            name = p.user_name or p.user_id
            desc = f"好感 {p.favorability:+.1f} | 亲密 {p.intimacy:.1f} | {stage}" if positive \
                else f"好感 {p.favorability:+.1f} | {stage}"
            if positive:
                medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"{i}."
                lines.append(f"{medal} {name}")
            else:
                lines.append(f"{i}. {name}")
            lines.append(f"   {desc}")
            entries.append((name, desc))
        if self._is_image_mode(event):
            try:
                path = self.image_renderer.render_leaderboard(
                    title, entries,
                    subtitle=f"共 {len(self.profiles)} 位用户",
                    file_name=f"rank_{int(time.time())}.png",
                )
                if path:
                    yield event.image_result(path)
                    return
            except Exception:
                pass
        yield event.plain_result("\n".join(lines))

    @filter.command("关系阶段")
    async def cmd_relationship_stage(self, event: AstrMessageEvent):
        """显示当前阶段、动态权重、过渡状态与进阶建议"""
        profile = self._get_or_create_profile(event)
        bp = self._get_or_create_behavior_profile(self._get_user_id(event))
        if profile.favorability < 0:
            stage_label = self._get_negative_stage_label(profile.favorability)
            yield event.plain_result(
                f"❄️ 当前关系：{stage_label}\n"
                f"好感度：{profile.favorability:+.1f}\n"
                f"💡 建议：改善互动方式，减少负面表达"
            )
            return
        stage = STAGES[max(0, min(profile.stage_index, len(STAGES) - 1))]
        next_stage = STAGES[min(profile.stage_index + 1, len(STAGES) - 1)]
        lines = [
            f"📊 关系阶段详情", f"━" * 24,
            f"当前阶段：{stage.label}",
            f"阶段进度：{profile.stage_progress:.1f}%",
            f"复合评分：{profile.composite_score:.1f}（阶段阈值 {stage.composite_threshold:.0f}）",
            f"亲密度（按好感度派生）：{profile.intimacy:.1f}",
        ]
        if profile.stage_index < len(STAGES) - 1:
            need = next_stage.composite_threshold - profile.composite_score
            lines.append(f"💡 距下一阶段还需：{need:.1f} 分")
        else:
            lines.append("🌸 已达最高阶段！")
        custom = self.relationship_manager.custom_info(profile.user_id)
        if custom["attitude"]:
            lines.append(f"💭 态度：{custom['attitude']}")
        if custom["relationship"]:
            lines.append(f"🤝 关系：{custom['relationship']}")
        # 行为模式信息
        if bp.current_streak_count > 1:
            streak_label = "正面 ✨" if bp.current_streak_type == "positive" else "负面 ⚡"
            lines.append(f"\n🔥 行为势头：{streak_label} ×{bp.current_streak_count}")
        lines.append(f"📈 累计奖励：{bp.total_reward_accumulated:+.1f} | 累计惩罚：{bp.total_penalty_accumulated:+.1f}")
        if bp.betrayal_count > 0:
            lines.append(f"💔 背叛次数：{bp.betrayal_count}")
        if bp.comeback_count > 0:
            lines.append(f"💫 回归次数：{bp.comeback_count}")
        if bp.achieved_milestones:
            lines.append(f"🏆 里程碑：{len(bp.achieved_milestones)} 个")
        path = self._try_render_image(event, "关系阶段详情", lines)
        if path:
            yield event.image_result(path)
        else:
            yield event.plain_result("\n".join(lines))

    @filter.command("缓存统计")
    async def cmd_cache_stats(self, event: AstrMessageEvent):
        """查看插件数据规模"""
        lines = [
            "📦 数据规模", f"━" * 20,
            f"档案数：{len(self.profiles)}",
            f"行为档案数：{len(self.behavior_profiles)}",
            f"长期记忆用户数：{len(self.long_memory._memory)}",
        ]
        path = self._try_render_image(event, "数据规模", lines)
        if path:
            yield event.image_result(path)
        else:
            yield event.plain_result("\n".join(lines))

    # ═══════════════════════════════════════════════════════════════
    #  新功能命令（纪念日/节日、趋势统计、关系角色、图片模式）
    # ═══════════════════════════════════════════════════════════════

    @filter.command("图片模式")
    async def cmd_image_mode(self, event: AstrMessageEvent):
        """切换指令输出是否渲染为图片"""
        if not self.image_renderer.available:
            yield event.plain_result("⚠️ 图片渲染不可用（未安装 Pillow 或缺少中文字体），已保持文本输出。")
            return
        uid = self._get_user_id(event)
        current = self.image_mode.get(uid, self.image_output_default)
        self.image_mode[uid] = not current
        self._save_image_mode()
        state = "开启 ✅（图片输出）" if self.image_mode[uid] else "关闭 ❌（文本输出）"
        yield event.plain_result(f"指令图片输出已{state}")

    @filter.command("全局图片模式")
    async def cmd_global_image_mode(self, event: AstrMessageEvent):
        """管理员：全局开启/关闭图片输出（所有信息命令强制图片）"""
        if not self._is_admin(event):
            yield event.plain_result("⛔ 权限不足，仅管理员可用")
            return
        if not self.image_renderer.available:
            yield event.plain_result("⚠️ 图片渲染不可用（未安装 Pillow 或缺少中文字体）")
            return
        cur = bool(self.config.get("image_output_global", False))
        self.config["image_output_global"] = not cur
        self._save_config()
        state = "开启 ✅（所有信息命令输出图片）" if not cur else "关闭 ❌（按用户设置）"
        yield event.plain_result(f"全局图片模式已{state}")

    @filter.command("纪念日")
    async def cmd_anniversary(self, event: AstrMessageEvent):
        """查看纪念日、节日与倒计时"""
        import datetime as _dt
        today = _dt.date.today()
        uid = self._get_user_id(event)
        if self.config.get("enable_anniversary_system", True):
            self.anniversary_manager.ensure_first_meet(uid)
        lines = ["📅 纪念日与节日", "━" * 22]
        today_events = self.anniversary_manager.get_today_events(uid, today)
        if today_events:
            lines.append("🎉 今天：")
            for evt in today_events:
                lines.append(f"  {evt['description']}")
            lines.append("")
        my = self.anniversary_manager.list_user_anniversaries(uid, today)
        if my:
            lines.append("💝 我的纪念日：")
            for a in my:
                if a["is_today"]:
                    lines.append(f"  {a['name']} · 就是今天 🎉")
                elif a["days_left"] >= 0:
                    lines.append(f"  {a['name']} · {a['month']:02d}-{a['day']:02d} · 还有 {a['days_left']} 天")
                else:
                    lines.append(f"  {a['name']} · {a['month']:02d}-{a['day']:02d}")
            lines.append("")
        else:
            lines.append("💝 我的纪念日：暂无")
            lines.append("  用 /添加纪念日 <名称> <MM-DD> 记录一个吧！")
            lines.append("")
        fest = self.anniversary_manager.list_festivals_with_dates(today)
        up = [f for f in fest if not f["is_today"]][:8]
        td = [f for f in fest if f["is_today"]]
        if td:
            lines.append("🎊 今日节日：")
            for f in td:
                lines.append(f"  {f['name']}")
            lines.append("")
        if up:
            lines.append("🗓️ 近期节日：")
            for f in up[:8]:
                lines.append(f"  {f['name']} · {f['date'][5:]} · {f['days_left']} 天后")
        lines.append("")
        lines.append("💡 /设置生日 <MM-DD> · /添加纪念日 <名称> <MM-DD> · /节日列表")
        path = self._try_render_image(event, "纪念日与节日", lines)
        if path:
            yield event.image_result(path)
        else:
            yield event.plain_result("\n".join(lines))

    @filter.command("添加纪念日")
    async def cmd_add_anniversary(self, event: AstrMessageEvent):
        """添加自定义纪念日。用法：/添加纪念日 <名称> <MM-DD>"""
        if not self.config.get("enable_anniversary_system", True):
            yield event.plain_result("⚠️ 纪念日系统未启用")
            return
        parts = event.message_str.split()
        if len(parts) < 3:
            yield event.plain_result("用法：/添加纪念日 <名称> <MM-DD>，例如：/添加纪念日 恋爱纪念日 05-20")
            return
        md = parse_month_day(parts[-1])
        if not md:
            yield event.plain_result("❌ 日期格式应为 MM-DD（例如 05-20、5月20日）")
            return
        name = " ".join(parts[1:-1])
        uid = self._get_user_id(event)
        self.anniversary_manager.ensure_first_meet(uid)
        ok, msg = self.anniversary_manager.add_anniversary(uid, name, md[0], md[1])
        self._save_all()
        yield event.plain_result(msg)

    @filter.command("删除纪念日")
    async def cmd_remove_anniversary(self, event: AstrMessageEvent):
        """删除自定义纪念日。用法：/删除纪念日 <名称>"""
        parts = event.message_str.split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("用法：/删除纪念日 <名称>")
            return
        uid = self._get_user_id(event)
        ok, msg = self.anniversary_manager.remove_anniversary(uid, parts[1].strip())
        if ok:
            self._save_all()
        yield event.plain_result(msg)

    @filter.command("设置生日")
    async def cmd_set_birthday(self, event: AstrMessageEvent):
        """设置生日。用法：/设置生日 <MM-DD>"""
        parts = event.message_str.split()
        if len(parts) < 2:
            yield event.plain_result("用法：/设置生日 <MM-DD>")
            return
        md = parse_month_day(parts[1])
        if not md:
            yield event.plain_result("❌ 日期格式应为 MM-DD")
            return
        uid = self._get_user_id(event)
        self.anniversary_manager.ensure_first_meet(uid)
        ok, msg = self.anniversary_manager.add_anniversary(uid, "我的生日", md[0], md[1], kind="birthday")
        self._save_all()
        yield event.plain_result(msg)

    @filter.command("节日列表")
    async def cmd_festival_list(self, event: AstrMessageEvent):
        """查看全部节日"""
        import datetime as _dt
        today = _dt.date.today()
        lines = ["🗓️ 节日列表", "━" * 22]
        for f in self.anniversary_manager.get_festivals():
            kind = "农历" if f["lunar"] else "公历"
            lines.append(f"  {f['name']} · {kind} · {f['month']:02d}-{f['day']:02d}")
        lines.append("")
        lines.append("管理员可用 /设置节日 <名称> <MM-DD> 添加")
        path = self._try_render_image(event, "节日列表", lines)
        if path:
            yield event.image_result(path)
        else:
            yield event.plain_result("\n".join(lines))

    @filter.command("设置节日")
    async def cmd_add_festival(self, event: AstrMessageEvent):
        """管理员：添加全球节日。用法：/设置节日 <名称> <MM-DD>"""
        if not self._is_admin(event):
            yield event.plain_result("⛔ 权限不足，仅管理员可用")
            return
        parts = event.message_str.split()
        if len(parts) < 3:
            yield event.plain_result("用法：/设置节日 <名称> <MM-DD>")
            return
        md = parse_month_day(parts[-1])
        if not md:
            yield event.plain_result("❌ 日期格式应为 MM-DD")
            return
        name = " ".join(parts[1:-1])
        ok, msg = self.anniversary_manager.add_festival(name, md[0], md[1])
        if ok:
            self._save_all()
        yield event.plain_result(msg)

    @filter.command("删除节日")
    async def cmd_remove_festival(self, event: AstrMessageEvent):
        """管理员：删除全球节日。用法：/删除节日 <名称>"""
        if not self._is_admin(event):
            yield event.plain_result("⛔ 权限不足，仅管理员可用")
            return
        parts = event.message_str.split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("用法：/删除节日 <名称>")
            return
        ok, msg = self.anniversary_manager.remove_festival(parts[1].strip())
        if ok:
            self._save_all()
        yield event.plain_result(msg)

    @filter.command("趋势")
    async def cmd_trend(self, event: AstrMessageEvent):
        """查看好感度/亲密度趋势。用法：/趋势 [天数]"""
        if not self.config.get("enable_stats_tracking", True):
            yield event.plain_result("⚠️ 数据统计未启用")
            return
        uid = self._get_user_id(event)
        parts = event.message_str.split()
        days = self.trend_default_days
        if len(parts) >= 2:
            try:
                days = max(3, min(60, int(parts[1])))
            except ValueError:
                pass
        entries = self.stats_tracker.trend(uid, days)
        if not entries:
            yield event.plain_result("📊 暂无统计数据。\n用户发送消息后自动记录，每天一条快照。")
            return
        s = self.stats_tracker.summary(uid, days)
        lines = [f"📈 情感趋势（近 {s['days']} 天）", "━" * 24]
        lines.extend(self.stats_tracker.build_text_chart(uid, days))
        lines.append("")
        lines.append(f"当前好感 {s['end_fav']:+.1f}（期间最高 {s['max_fav']:+.1f} / 最低 {s['min_fav']:+.1f}）")
        lines.append(f"期间净变化 {s['delta']:+.1f} · 上升 {s['up_days']} 天 / 下降 {s['down_days']} 天")
        lines.append(f"平均亲密 {s['avg_int']:.1f} · 总互动 {s['total_interactions']} 次")
        path = self._try_render_trend_image(event, uid, days)
        if path:
            yield event.image_result(path)
        else:
            # 趋势图不可用时，图片模式下仍输出卡片（文本图）
            path = self._try_render_image(event, f"情感趋势（近 {s['days']} 天）", lines)
            if path:
                yield event.image_result(path)
            else:
                yield event.plain_result("\n".join(lines))

    @filter.command("关系角色")
    async def cmd_relationship_roles(self, event: AstrMessageEvent):
        """查看关系角色列表与解锁进度。用法：/关系角色 [角色]"""
        uid = self._get_user_id(event)
        profile = self._get_or_create_profile(event)
        parts = event.message_str.split(maxsplit=1)
        if len(parts) >= 2:
            key = resolve_relationship_key(parts[1])
            if not key:
                yield event.plain_result(f"❌ 未知关系角色：{parts[1]}")
                return
            r = SYSTEM_ROLES_BY_KEY.get(key)
            if not r:
                yield event.plain_result(f"❌ 未知关系角色：{parts[1]}")
                return
            st = self.relationship_manager.status(
                uid, profile.favorability, profile.intimacy, profile.total_interactions
            )
            row = next((x for x in st if x["key"] == key), None)
            lines = [
                f"{r['emoji']} 关系角色：{r['name']}",
                f"💬 {r['desc']}",
                "━" * 22,
                r["persona"],
                "━" * 22,
            ]
            if row:
                state = (
                    "✅ 使用中" if row["active"]
                    else "🔓 已解锁" if row["unlocked"]
                    else "🔒 未解锁"
                )
                lines.append(f"状态：{state}")
                if not row["unlocked"] and not row["active"]:
                    need = self.relationship_manager.unmet(
                        r, profile.favorability, profile.intimacy, profile.total_interactions
                    )
                    if need:
                        lines.append(f"解锁条件：{'、'.join(need)}")
            lines.append("")
            lines.append("💡 /解锁关系 <角色> 解锁；/切换关系 <角色> 切换（一次且不可逆）")
            lines.append("💡 管理员：/设置关系角色 <用户ID> <角色> 可强制调整并解除锁定")
            path = self._try_render_image(event, f"{r['name']} · 关系角色", lines)
            if path:
                yield event.image_result(path)
            else:
                yield event.plain_result("\n".join(lines))
            return
        st = self.relationship_manager.status(
            uid, profile.favorability, profile.intimacy, profile.total_interactions
        )
        active = self.relationship_manager.active_role(uid)
        lines = ["🎭 关系角色解锁", "━" * 22]
        if not self.config.get("enable_relationship_roles", True):
            lines.append("⚠️ 关系角色系统未启用")
        if active:
            r = SYSTEM_ROLES_BY_KEY.get(active)
            if r:
                lock_tag = "（🔒 已锁定）" if self.relationship_manager.is_locked(uid) else ""
                lines.append(f"当前关系：{r['emoji']} {r['name']} {lock_tag}")
                lines.append("")
        else:
            lines.append("当前关系：🚶 陌生人（默认）")
            lines.append("")
        lines.append("系统内置角色（解锁仅限以下角色）：")
        lines.append("")
        for row in st:
            mark = (
                "✅" if row["active"]
                else "🔓" if row["unlocked"]
                else "🔒" if not row["can_unlock"]
                else "🔑"
            )
            progress = ""
            if not row["unlocked"] and row["key"] != "stranger":
                need = self.relationship_manager.unmet(
                    SYSTEM_ROLES_BY_KEY[row["key"]],
                    profile.favorability, profile.intimacy, profile.total_interactions,
                )
                if need:
                    progress = "  (" + " ".join(need) + ")"
            lines.append(f"{mark} {row['emoji']} {row['name']}{progress}")
        lines.append("")
        lines.append("💡 /解锁关系 <角色> 解锁；/切换关系 <角色> 切换（一次且不可逆）")
        lines.append("💡 管理员：/设置关系角色 <用户ID> <角色> 可强制调整并解除锁定")
        path = self._try_render_image(event, "关系角色解锁", lines)
        if path:
            yield event.image_result(path)
        else:
            yield event.plain_result("\n".join(lines))

    @filter.command("解锁关系")
    async def cmd_unlock_relationship(self, event: AstrMessageEvent):
        """解锁关系角色（仅限系统内置角色）。用法：/解锁关系 <角色>"""
        if not self.config.get("enable_relationship_roles", True):
            yield event.plain_result("⚠️ 关系角色系统未启用")
            return
        uid = self._get_user_id(event)
        profile = self._get_or_create_profile(event)
        parts = event.message_str.split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("用法：/解锁关系 <角色>\n例如：/解锁关系 恋人、/解锁关系 哥哥、/解锁关系 妹妹")
            return
        key = resolve_relationship_key(parts[1])
        if not key:
            yield event.plain_result(f"❌ 未知关系角色：{parts[1]}")
            return
        ok, msg = self.relationship_manager.unlock(
            uid, key, profile.favorability, profile.intimacy, profile.total_interactions
        )
        if ok:
            self._save_all()
        yield event.plain_result(msg)

    @filter.command("切换关系")
    async def cmd_switch_relationship(self, event: AstrMessageEvent):
        """切换已解锁的关系角色。用法：/切换关系 <角色>"""
        if not self.config.get("enable_relationship_roles", True):
            yield event.plain_result("⚠️ 关系角色系统未启用")
            return
        uid = self._get_user_id(event)
        parts = event.message_str.split(maxsplit=1)
        if len(parts) < 2:
            yield event.plain_result("用法：/切换关系 <角色>")
            return
        key = resolve_relationship_key(parts[1])
        if not key:
            yield event.plain_result(f"❌ 未知关系角色：{parts[1]}")
            return
        ok, msg = self.relationship_manager.switch(uid, key)
        if ok:
            self._save_all()
        yield event.plain_result(msg)

    @filter.command("我的画像")
    async def cmd_my_portrait(self, event: AstrMessageEvent):
        """查看个人情感自画像（完整档案 + 行为模式 + 长期记忆）"""
        uid = self._get_user_id(event)
        profile = self._get_or_create_profile(event)
        bp = self._get_or_create_behavior_profile(uid)
        privacy = self.config.get("global_privacy_level", 1)

        lines = []
        name = profile.user_name or "你"
        lines.append(f"╔═══ {name} 的情感自画像 ═══╗")
        lines.append("")

        # ── 核心数值 ──
        fav = profile.favorability
        fav_icon = "💚" if fav > 40 else "💙" if fav > 0 else "💛" if fav > -20 else "💔"
        fav_bar = self._progress_bar(fav, -100, 200, 16)
        lines.append(f"{fav_icon} 好感度：{fav:+.1f}  {fav_bar}")

        int_bar = self._progress_bar(profile.intimacy, 0, 100, 16)
        lines.append(f"💜 亲密度：{profile.intimacy:.1f}  {int_bar}")

        lines.append(f"📊 复合评分：{profile.composite_score:.1f}")
        lines.append("")

        # ── 关系阶段 ──
        stage = self._get_stage_label(profile)
        lines.append(f"🧬 当前关系：{stage}")
        prog_bar = self._progress_bar(profile.stage_progress, 0, 100, 16)
        lines.append(f"📈 阶段进度：{profile.stage_progress:.1f}%  {prog_bar}")

        if profile.stage_index >= 0 and profile.stage_index < len(STAGES) - 1:
            next_s = STAGES[profile.stage_index + 1]
            need = next_s.composite_threshold - profile.composite_score
            lines.append(f"💡 距下一阶段还需：{need:.1f} 分")
        elif profile.stage_index >= len(STAGES) - 1:
            lines.append("🌸 已达最高阶段！")
        lines.append("")

        # ── 关系角色（锁定 > 管理员固定 > 自动判定/手动激活）──
        if self.config.get("enable_relationship_roles", True):
            locked = self.relationship_manager.is_locked(uid)
            pinned = self.relationship_manager.pinned_role(uid)
            if locked:
                ai = self.relationship_manager.active_info(uid)
                role_key = ai["key"] if ai else None
            elif pinned:
                role_key = pinned
            elif self.config.get("relationship_auto_assign", True):
                content = self.relationship_manager.custom_content(uid)
                role_key = (
                    self.relationship_manager.from_content(content)
                    or self.relationship_manager.recommend(
                        profile.favorability, profile.intimacy, profile.total_interactions
                    )
                )
            else:
                ai = self.relationship_manager.active_info(uid)
                role_key = ai["key"] if ai else None
            if role_key:
                r = SYSTEM_ROLES_BY_KEY.get(role_key)
                if r and r["key"] != "stranger":
                    lock_tag = "（🔒 已锁定）" if locked else ""
                    pin_tag = "（🛠️ 管理员固定）" if (pinned and not locked) else ""
                    lines.append(f"🎭 关系角色：{r['emoji']} {r['name']}{lock_tag}{pin_tag}")
                    if r.get("desc"):
                        lines.append(f"  {r['desc']}")
                    lines.append("")

        # ── 自定义态度/关系描述（合并进关系角色系统）──
        custom = self.relationship_manager.custom_info(profile.user_id)
        if custom["attitude"]:
            lines.append(f"💭 AI 对你的态度：{custom['attitude']}")
        if custom["relationship"]:
            lines.append(f"🤝 你们的关系：{custom['relationship']}")
        if custom["attitude"] or custom["relationship"]:
            lines.append("")

        # ── 8 维情感 ──
        if privacy >= 1:
            lines.append("🎭 情感画像：")
            for dim in EMOTION_DIMENSIONS:
                val = profile.emotions.get(dim, 50)
                bar = self._progress_bar(val, 0, 100, 12)
                icon = DIM_ICONS.get(dim, "•")
                label = DIM_LABELS.get(dim, dim)
                lines.append(f"  {icon} {label}：{val:.0f}  {bar}")
            lines.append("")

        # ── 互动统计 ──
        lines.append(f"💬 互动统计：")
        lines.append(f"  总互动：{profile.total_interactions} 次")
        lines.append(f"  正面互动：{profile.positive_interactions} 次")
        lines.append(f"  负面互动：{profile.negative_interactions} 次")
        lines.append(f"  对话轮数：{profile.conversation_turns} 轮")
        lines.append("")

        # ── 行为模式 ──
        if bp:
            lines.append("🎯 行为模式：")
            if bp.current_streak_count > 1:
                streak_type = "正面 ✨" if bp.current_streak_type == "positive" else "负面 ⚡"
                lines.append(f"  当前势头：{streak_type} ×{bp.current_streak_count}")
            lines.append(f"  最长正面连续：{bp.max_positive_streak} 次")
            lines.append(f"  最长负面连续：{bp.max_negative_streak} 次")
            lines.append(f"  累计获得奖励：{bp.total_reward_accumulated:+.1f}")
            lines.append(f"  累计受到惩罚：{bp.total_penalty_accumulated:+.1f}")
            if bp.betrayal_count > 0:
                lines.append(f"  💔 背叛次数：{bp.betrayal_count}")
            if bp.apology_count > 0:
                lines.append(f"  🕊️ 道歉次数：{bp.apology_count}")
            if bp.comeback_count > 0:
                lines.append(f"  💫 回归次数：{bp.comeback_count}")
            if bp.achieved_milestones:
                milestone_names = {v[0]: v[1] for v in MILESTONES.values()}
                names = [milestone_names.get(m, m) for m in bp.achieved_milestones]
                lines.append(f"  🏆 已达成里程碑：{', '.join(names)}")
            lines.append("")

        # ── 长期记忆 ──
        ltm = self.long_memory.get_summary(profile.user_id)
        if ltm and ltm != "暂无长期记忆。":
            lines.append("📜 情感记忆：")
            lines.append(ltm)
            lines.append("")

        # ── 关系建议（阈值对齐新阶段体系 30/70/115/160/185/200）──
        lines.append("💡 关系建议：")
        if fav < -50:
            lines.append("  你们的关系处于敌对状态，需要真诚的道歉和长时间的修复。")
        elif fav < -20:
            lines.append("  关系有些紧张，试着多表达善意，减少负面言辞。")
        elif fav < 0:
            lines.append("  关系偏冷淡，多一些温暖的互动可以改善。")
        elif fav < 30:
            lines.append("  初识阶段，保持真诚和耐心，关系会慢慢加深。")
        elif fav < 70:
            lines.append("  好感在增长，继续用心互动，信任正在建立。")
        elif fav < 115:
            lines.append("  关系不错！深化期需要更多真诚和陪伴。")
        elif fav < 160:
            lines.append("  关系很亲密了，珍惜这份信任。")
        elif fav < 185:
            lines.append("  已到承诺期，这段感情已非常深厚。")
        elif fav < 200:
            lines.append("  已达共生期前夜，这是最深层的情感连接。🌸")
        else:
            lines.append("  已达最高阶段，这是最深层的情感连接。🌸")

        lines.append("")
        lines.append("╚═════════════════════════╝")

        path = self._try_render_image(event, f"{name} 的情感自画像", lines)
        if path:
            yield event.image_result(path)
        else:
            yield event.plain_result("\n".join(lines))

    # ═══════════════════════════════════════════════════════════════
    #  管理员命令
    # ═══════════════════════════════════════════════════════════════

    @filter.command("设置关系角色")
    async def cmd_set_relationship_role(self, event: AstrMessageEvent):
        """管理员：强制调整指定用户的关系角色（绕过锁定与解锁条件）。用法：/设置关系角色 <ID> <角色>"""
        if not self._is_admin(event):
            yield event.plain_result("⛔ 权限不足，仅管理员可用")
            return
        parts = event.message_str.split(maxsplit=2)
        if len(parts) < 3:
            yield event.plain_result("用法：/设置关系角色 <用户ID> <角色>\n例如：/设置关系角色 123456 恋人、/设置关系角色 123456 陌生人")
            return
        key = resolve_relationship_key(parts[2])
        if not key:
            yield event.plain_result(f"❌ 未知关系角色：{parts[2]}")
            return
        ok, msg = self.relationship_manager.admin_switch(parts[1], key)
        if ok:
            self._save_all()
        yield event.plain_result(msg)

    @filter.command("设置好感")
    async def cmd_set_favorability(self, event: AstrMessageEvent):
        """管理员：设置指定用户好感度。用法：/设置好感 <ID> <值>"""
        if not self._is_admin(event):
            yield event.plain_result("⛔ 权限不足，仅管理员可用")
            return
        parts = event.message_str.split()
        if len(parts) < 3:
            yield event.plain_result("用法：/设置好感 <用户ID> <-100~200的数值>")
            return
        user_id = parts[1]
        try:
            value = float(parts[2])
        except ValueError:
            yield event.plain_result("❌ 值必须是数字")
            return
        old, msg = self._set_profile_value(user_id, fav=max(-100, min(FAVORABILITY_MAX, value)))
        yield event.plain_result(f"✅ 已将 {user_id} 好感度从 {old:+.1f} 设置为 {value:+.1f}")

    @filter.command("设置亲密")
    async def cmd_set_intimacy(self, event: AstrMessageEvent):
        """管理员：设置指定用户亲密度。用法：/设置亲密 <ID> <值>"""
        if not self._is_admin(event):
            yield event.plain_result("⛔ 权限不足，仅管理员可用")
            return
        parts = event.message_str.split()
        if len(parts) < 3:
            yield event.plain_result("用法：/设置亲密 <用户ID> <0~100的数值>")
            return
        user_id = parts[1]
        yield event.plain_result(f"ℹ️ 亲密度已改为按好感度百分比派生（亲密度=(好感+100)/3），请使用 /设置好感 调整")
        return

    def _set_profile_value(self, user_id: str, fav: Optional[float] = None,
                           int_: Optional[float] = None):
        """管理员设值通用入口：好感/亲密 修改后重算亲密度、复合评分与阶段"""
        profile = self._get_or_create_profile_by_id(user_id)
        old = profile.favorability
        if fav is not None:
            profile.favorability = max(-100.0, min(FAVORABILITY_MAX, fav))
        if int_ is not None:
            profile.intimacy = max(0.0, min(100.0, int_))
        # 亲密度按好感度派生（与 emotion_engine 保持一致）
        profile.intimacy = intimacy_from_favorability(profile.favorability)
        profile.composite_score = self.emotion_engine.calc_composite(profile)
        profile.stage_index = self.emotion_engine.evaluate_stage(profile)
        profile.stage_progress = self.emotion_engine.calc_stage_progress(profile)
        self._save_profile(profile)
        return old, ""

    @filter.command("设置态度")
    async def cmd_set_attitude(self, event: AstrMessageEvent):
        """管理员：自定义用户态度描述（合并进关系角色人设）。用法：/设置态度 <ID> <文本>"""
        for res in self._set_user_text(event, "attitude", "态度"):
            yield res

    def _set_user_text(self, event, kind: str, label: str):
        if not self._is_admin(event):
            yield event.plain_result("⛔ 权限不足，仅管理员可用")
            return
        parts = event.message_str.split(maxsplit=2)
        if len(parts) < 3:
            yield event.plain_result(f"用法：/设置{label} <用户ID> <{label}描述文本>")
            return
        user_id, text = parts[1], parts[2]
        ok, msg = self.relationship_manager.set_custom(user_id, kind, text)
        yield event.plain_result(msg)

    @filter.command("设置关系")
    async def cmd_set_relationship(self, event: AstrMessageEvent):
        """管理员：自定义用户关系描述（合并进关系角色人设）。用法：/设置关系 <ID> <文本>"""
        for res in self._set_user_text(event, "relationship", "关系"):
            yield res

    @filter.command("重置好感")
    async def cmd_reset(self, event: AstrMessageEvent):
        """管理员：重置指定用户情感数据。用法：/重置好感 <ID>"""
        if not self._is_admin(event):
            yield event.plain_result("⛔ 权限不足，仅管理员可用")
            return
        parts = event.message_str.split()
        if len(parts) < 2:
            yield event.plain_result("用法：/重置好感 <用户ID>")
            return
        user_id = parts[1]
        self.profiles.pop(user_id, None)
        self.behavior_profiles.pop(user_id, None)
        self.long_memory.clear_user(user_id)
        self._save_all()
        yield event.plain_result(f"✅ 已重置 {user_id} 的所有情感数据（含行为档案）")

    @filter.command("查看好感")
    async def cmd_view_detail(self, event: AstrMessageEvent):
        """管理员：查看完整情感档案。用法：/查看好感 <ID>"""
        if not self._is_admin(event):
            yield event.plain_result("⛔ 权限不足，仅管理员可用")
            return
        parts = event.message_str.split()
        if len(parts) < 2:
            yield event.plain_result("用法：/查看好感 <用户ID>")
            return
        user_id = parts[1]
        profile = self._get_or_create_profile_by_id(user_id)
        bp = self.behavior_profiles.get(user_id)
        lines = self._format_profile(profile, event, detail=True, behavior_profile=bp)
        path = self._try_render_image(event, f"{profile.user_name or user_id} 完整档案", lines)
        if path:
            yield event.image_result(path)
        else:
            yield event.plain_result("\n".join(lines))

    @filter.command("隐私级别")
    async def cmd_privacy_level(self, event: AstrMessageEvent):
        """管理员：设置全局隐私级别。用法：/隐私级别 <0-2>"""
        if not self._is_admin(event):
            yield event.plain_result("⛔ 权限不足，仅管理员可用")
            return
        parts = event.message_str.split()
        if len(parts) < 2:
            yield event.plain_result("用法：/隐私级别 <0|1|2>")
            return
        try:
            level = int(parts[1])
        except ValueError:
            yield event.plain_result("❌ 级别必须是 0、1 或 2")
            return
        level = max(0, min(2, level))
        self.config["global_privacy_level"] = level
        self.config.save_config()
        yield event.plain_result(f"✅ 全局隐私级别已设置为 {level}（0=保密 1=基础 2=详细）")

    @filter.command("重置插件")
    async def cmd_reset_plugin(self, event: AstrMessageEvent):
        """管理员：清空所有情感数据"""
        if not self._is_admin(event):
            yield event.plain_result("⛔ 权限不足，仅管理员可用")
            return
        self.profiles.clear()
        self.behavior_profiles.clear()
        self.long_memory.clear_all()
        self._save_all()
        yield event.plain_result("✅ 所有情感数据已清空（含行为档案）")

    @filter.command("备份数据")
    async def cmd_backup(self, event: AstrMessageEvent):
        """管理员：创建数据快照"""
        if not self._is_admin(event):
            yield event.plain_result("⛔ 权限不足，仅管理员可用")
            return
        import shutil
        backup_dir = self.data_dir / "backups"
        backup_dir.mkdir(exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"backup_{ts}"
        backup_path.mkdir(exist_ok=True)
        profiles_file = self.data_dir / "profiles.json"
        if profiles_file.exists():
            shutil.copy2(profiles_file, backup_path / "profiles.json")
        behavior_file = self.data_dir / "behavior_profiles.json"
        if behavior_file.exists():
            shutil.copy2(behavior_file, backup_path / "behavior_profiles.json")
        ltm_dir = self.data_dir / "long_term_memory"
        if ltm_dir.exists():
            shutil.copytree(ltm_dir, backup_path / "long_term_memory", dirs_exist_ok=True)
        yield event.plain_result(f"✅ 数据已备份到：{backup_path.name}")

    @filter.command("修复互动统计")
    async def cmd_fix_stats(self, event: AstrMessageEvent):
        """管理员：依据好感/亲密度自动修正正负互动次数"""
        if not self._is_admin(event):
            yield event.plain_result("⛔ 权限不足，仅管理员可用")
            return
        fixed = 0
        for uid, profile in self.profiles.items():
            if profile.total_interactions == 0:
                continue
            if profile.favorability > 20:
                expected_pos = max(1, int(profile.total_interactions * 0.7))
                expected_neg = profile.total_interactions - expected_pos
            elif profile.favorability < -20:
                expected_neg = max(1, int(profile.total_interactions * 0.7))
                expected_pos = profile.total_interactions - expected_neg
            else:
                expected_pos = profile.total_interactions // 2
                expected_neg = profile.total_interactions - expected_pos
            if (abs(profile.positive_interactions - expected_pos) > 3 or
                    abs(profile.negative_interactions - expected_neg) > 3):
                profile.positive_interactions = expected_pos
                profile.negative_interactions = expected_neg
                fixed += 1
        self._save_all()
        yield event.plain_result(f"✅ 已修正 {fixed} 个用户的互动统计")

    @filter.command("调试事件")
    async def cmd_debug_event(self, event: AstrMessageEvent):
        """管理员：输出事件结构（排障用）"""
        if not self._is_admin(event):
            yield event.plain_result("⛔ 权限不足，仅管理员可用")
            return
        info = {
            "sender_id": event.get_sender_id(),
            "sender_name": event.get_sender_name(),
            "message_str": event.message_str[:200],
            "unified_msg_origin": event.unified_msg_origin,
            "message_obj_type": str(type(event.message_obj)),
        }
        yield event.plain_result(f"🔧 事件结构：\n{json.dumps(info, ensure_ascii=False, indent=2)}")

    @filter.command("调试记忆")
    async def cmd_debug_memory(self, event: AstrMessageEvent):
        """管理员：查看短期缓存与长期记忆（含行为档案）"""
        if not self._is_admin(event):
            yield event.plain_result("⛔ 权限不足，仅管理员可用")
            return
        uid = self._get_user_id(event)
        ltm_summary = self.long_memory.get_summary(uid)
        recent = self.recent_messages.get(uid, [])
        bp = self.behavior_profiles.get(uid)
        lines = [
            "🧠 记忆调试", f"━" * 20,
            f"近期对话缓存：{len(recent)} 条",
            f"", f"📜 长期记忆：", ltm_summary,
        ]
        if bp:
            lines.append(f"")
            lines.append(f"🎯 行为档案：")
            lines.append(f"  当前势头：{bp.current_streak_type} ×{bp.current_streak_count}")
            lines.append(f"  最长正面连续：{bp.max_positive_streak} | 最长负面连续：{bp.max_negative_streak}")
            lines.append(f"  背叛：{bp.betrayal_count} 次 | 道歉：{bp.apology_count} 次 | 回归：{bp.comeback_count} 次")
            lines.append(f"  累计奖励：{bp.total_reward_accumulated:+.1f} | 累计惩罚：{bp.total_penalty_accumulated:+.1f}")
            lines.append(f"  里程碑：{bp.achieved_milestones or '无'}")
            lines.append(f"  待衰减效果：{len(bp.pending_effects)} 条")
        path = self._try_render_image(event, "记忆调试", lines)
        if path:
            yield event.image_result(path)
        else:
            yield event.plain_result("\n".join(lines))

    # ═══════════════════════════════════════════════════════════════
    #  LLM 请求钩子（注入情感上下文 + 触发更新 + 惩罚奖励）
    # ═══════════════════════════════════════════════════════════════

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req):
        """
        每次 LLM 对话前自动执行：
        1. 记录近期对话
        2. 每轮都做关键词分析 + 微变化（保证基础更新）
        3. 惩罚奖励机制：行为模式分析 + 特殊事件检测
        4. 智能更新决策：判断是否需要调用辅助 LLM 深度分析
        5. 注入情感上下文到 LLM 请求
        """
        try:
            uid = self._get_user_id(event)
            profile = self._get_or_create_profile(event)
            behavior_profile = self._get_or_create_behavior_profile(uid)
            text = event.message_str

            # ── 动态读取配置（支持 WebUI 热更新，无需重载插件）──
            dyn_enable_smart = self.config.get("enable_smart_update", True)
            dyn_enable_llm = self.config.get("enable_secondary_llm", True)
            dyn_enable_ai = self.config.get("enable_ai_text_generation", True)
            dyn_micro_fav = self.config.get("micro_change_favorability", 0.21)
            dyn_micro_int = self.config.get("micro_change_intimacy", 0.07)
            dyn_llm_weight = self.config.get("llm_weight", 0.4)
            dyn_pr_weight = self.config.get("pr_weight", 0.6)

            # ── 更新对话计数 ──
            profile.conversation_turns += 1
            profile.turns_since_update += 1

            # ── 记录近期对话 ──
            if uid not in self.recent_messages:
                self.recent_messages[uid] = []
            self.recent_messages[uid].append(text)
            if len(self.recent_messages[uid]) > 10:
                self.recent_messages[uid] = self.recent_messages[uid][-10:]

            # ── 第一步：关键词分析（每轮必做，轻量）──
            kw_result = self.emotion_engine.analyze_keywords(text)
            fav_delta = kw_result["fav_delta"]
            int_delta = kw_result["int_delta"]
            emotion_deltas = kw_result["emotion_deltas"]

            # ── 无关键词命中时的微变化（模拟自然互动积累）──
            if fav_delta == 0 and int_delta == 0:
                fav_delta = dyn_micro_fav
                int_delta = dyn_micro_int
                emotion_deltas = {"trust": 0.1, "anticipation": 0.1}

            # ── 第一步半：纪念日/节日检查（当天奖励 + 上下文提示）──
            anniv_events = []
            if self.config.get("enable_anniversary_system", True):
                self.anniversary_manager.ensure_first_meet(uid, profile.last_update_ts)
                anniv_bonus_fav, anniv_bonus_int, anniv_events = self._check_anniversary(
                    profile, uid
                )
                fav_delta += anniv_bonus_fav
                int_delta += anniv_bonus_int

            # ── 第二步：惩罚奖励机制分析 ──
            pr_events = []
            dyn_pr_enabled = any([
                self.config.get("pr_enable_momentum", True),
                self.config.get("pr_enable_cold_penalty", True),
                self.config.get("pr_enable_comeback_reward", True),
                self.config.get("pr_enable_betrayal_penalty", True),
                self.config.get("pr_enable_apology_recovery", True),
                self.config.get("pr_enable_milestone_reward", True),
            ])

            if dyn_pr_enabled:
                pr_fav, pr_int, pr_events = self.penalty_reward_engine.analyze_and_apply(
                    bp=behavior_profile,
                    text=text,
                    fav_delta=fav_delta,
                    int_delta=int_delta,
                    current_favorability=profile.favorability,
                    total_interactions=profile.total_interactions,
                )
                # 惩奖结果按权重融合到情感变化中
                fav_delta += pr_fav * dyn_pr_weight
                int_delta += pr_int * dyn_pr_weight

                # 更新累计统计
                if pr_fav > 0:
                    behavior_profile.total_reward_accumulated += pr_fav
                elif pr_fav < 0:
                    behavior_profile.total_penalty_accumulated += abs(pr_fav)

                # 惩罚奖励事件记入长期记忆
                if pr_events:
                    for evt in pr_events:
                        if any(icon in evt for icon in ["💔", "💫", "🏆", "🔥", "⚡"]):
                            self.long_memory.add_event(profile.user_id, {
                                "favorability": round(profile.favorability + fav_delta, 1),
                                "stage": self._get_stage_label(profile),
                                "description": evt,
                                "message": text[:80],
                            })

            # ── 第三步：智能更新决策 → 是否调用辅助 LLM ──
            llm_adjust = None
            should_deep_update = False

            if dyn_enable_smart:
                llm_marker = self.smart_updater.check_llm_marker(text)
                decision = self.smart_updater.evaluate(
                    text=text,
                    turns_since_update=profile.turns_since_update,
                    last_update_ts=profile.last_update_ts,
                    llm_marker_detected=llm_marker,
                )
                should_deep_update = decision.should_update
                if should_deep_update:
                    logger.info(
                        f"SoulSync 智能更新触发 [{uid}]: {decision.reason} "
                        f"(置信度 {decision.confidence:.2f})"
                    )
            else:
                should_deep_update = True

            # ── 第四步：辅助 LLM 深度分析（条件触发）──
            if should_deep_update and dyn_enable_llm and not self._llm_circuit_broken:
                try:
                    llm_result = await self._call_secondary_llm(profile, text, event)
                    if llm_result:
                        llm_fav = llm_result.get("fav_delta", 0)
                        llm_int = llm_result.get("int_delta", 0)
                        kw_w = 1.0 - dyn_llm_weight
                        fav_delta = fav_delta * kw_w + llm_fav * dyn_llm_weight
                        int_delta = int_delta * kw_w + llm_int * dyn_llm_weight

                        llm_emotions = llm_result.get("emotions", {})
                        llm_adjust = {}
                        for dim, val in llm_emotions.items():
                            if dim in EMOTION_DIMENSIONS:
                                llm_adjust[dim] = val * dyn_llm_weight

                        if dyn_enable_ai:
                            attitude = llm_result.get("attitude", "")
                            relationship = llm_result.get("relationship", "")
                            if attitude:
                                self.relationship_manager.set_custom(
                                    profile.user_id, "attitude", attitude
                                )
                            if relationship:
                                self.relationship_manager.set_custom(
                                    profile.user_id, "relationship", relationship
                                )

                        significance = llm_result.get("significance", 0)
                        if significance >= self.significance_threshold:
                            self.long_memory.add_event(profile.user_id, {
                                "favorability": round(profile.favorability, 1),
                                "stage": self._get_stage_label(profile),
                                "description": f"好感{fav_delta:+.1f} 亲密{int_delta:+.1f}",
                                "message": text[:100],
                            })

                        logger.info(
                            f"SoulSync LLM分析完成 [{uid}]: "
                            f"fav_delta={llm_fav:+.1f} int_delta={llm_int:+.1f} "
                            f"significance={significance}"
                        )
                    else:
                        logger.debug(f"SoulSync LLM返回为空 [{uid}]")
                except Exception as e:
                    logger.warning(f"SoulSync 辅助LLM分析异常 [{uid}]: {e}")

            # ── 第五步：应用情感变更 ──
            old_stage = profile.stage_index
            old_fav = profile.favorability

            self.emotion_engine.apply_change(
                profile, fav_delta, int_delta, emotion_deltas, llm_adjust
            )

            if profile.stage_index != old_stage:
                self.long_memory.add_event(profile.user_id, {
                    "favorability": round(profile.favorability, 1),
                    "stage": self._get_stage_label(profile),
                    "description": f"阶段变化：{old_stage} → {profile.stage_index}",
                })
                logger.info(
                    f"SoulSync 阶段变化 [{uid}]: "
                    f"{old_stage} → {profile.stage_index} "
                    f"(好感 {old_fav:+.1f} → {profile.favorability:+.1f})"
                )

            if should_deep_update:
                profile.turns_since_update = 0
                profile.last_update_ts = time.time()

            # ── 数据统计：记录每日快照 ──
            if self.config.get("enable_stats_tracking", True):
                self.stats_tracker.update(
                    uid=profile.user_id,
                    favorability=profile.favorability,
                    intimacy=profile.intimacy,
                    stage_index=profile.stage_index,
                    stage_label=self._get_stage_label(profile),
                    total_interactions=profile.total_interactions,
                    positive=profile.positive_interactions,
                    negative=profile.negative_interactions,
                    conversation_turns=profile.conversation_turns,
                )

            # ── 关系角色：聊天内容自动判定 + 注入角色人设到系统提示词 ──
            if self.config.get("enable_relationship_roles", True):
                content = self.relationship_manager.custom_content(uid)
                content += " " + " ".join(self.recent_messages.get(uid, [])[-4:])
                role = self.relationship_manager.resolve_active(
                    uid,
                    profile.favorability,
                    profile.intimacy,
                    profile.total_interactions,
                    auto_assign=self.config.get("relationship_auto_assign", True),
                    content=content,
                )
                if role:
                    role_key, role_text = role
                    if role_text and "<stage_role>" not in (req.system_prompt or ""):
                        req.system_prompt = (
                            f"{req.system_prompt or ''}\n\n"
                            f"<stage_role>{role_text}</stage_role>"
                        )

            # ── 时间/节假日/农历感知（仿 LLMPerception：prompt 前缀注入）──
            perception = self._build_perception_block(uid, anniv_events)
            if perception and req.prompt:
                req.prompt = f"[{perception}]\n{req.prompt}"

            # ── 注入情感上下文到 LLM ──
            emotion_context = self._build_emotion_context(profile)
            if emotion_context:
                req.extra_user_content_parts.append(TextPart(text=emotion_context))

            # ── 注入惩罚奖励事件提示 ──
            if pr_events:
                pr_hint = self._build_pr_context(pr_events, behavior_profile)
                if pr_hint:
                    req.extra_user_content_parts.append(TextPart(text=pr_hint))

            # ── 状态显示 ──
            if self.show_status.get(uid, self.config.get("show_status_default", False)):
                status_line = self._build_status_line(profile, behavior_profile)
                if status_line:
                    req.extra_user_content_parts.append(TextPart(text=status_line))

            # ── 保存 ──
            self._save_profile(profile)
            self._save_behavior_profile(behavior_profile)

        except Exception as e:
            logger.error(f"SoulSync on_llm_request 异常: {e}", exc_info=True)

    # ═══════════════════════════════════════════════════════════════
    #  核心情感更新逻辑
    # ═══════════════════════════════════════════════════════════════

    async def _call_secondary_llm(
        self, profile: EmotionProfile, text: str, event: AstrMessageEvent
    ) -> Optional[dict]:
        """调用辅助 LLM 进行情感分析（带熔断保护 + provider 降级）"""
        if self._llm_circuit_broken:
            return None

        configured_provider = self.config.get("llm_provider_id", "")
        session_provider = await self.context.get_current_chat_provider_id(
            umo=event.unified_msg_origin
        )

        provider_id = configured_provider or session_provider
        if not provider_id:
            logger.debug("SoulSync 无可用 LLM provider，跳过")
            return None

        recent_count = self.config.get("llm_recent_messages_count", 5)
        memory_summary = self.long_memory.get_summary(profile.user_id)
        recent = self.recent_messages.get(profile.user_id, [])
        recent_text = "\n".join(f"- {m}" for m in recent[-recent_count:]) if recent else "暂无"

        # 角色上下文：让态度/关系描述贴合当前关系角色
        role_context = ""
        if self.config.get("enable_relationship_roles", True):
            content = self.relationship_manager.custom_content(profile.user_id)
            content += " " + " ".join(self.recent_messages.get(profile.user_id, [])[-4:])
            rk = self.relationship_manager.resolve_active(
                profile.user_id, profile.favorability, profile.intimacy,
                profile.total_interactions,
                auto_assign=self.config.get("relationship_auto_assign", True),
                content=content,
            )
            if rk:
                rr = SYSTEM_ROLES_BY_KEY.get(rk[0])
                if rr:
                    role_context = f"{rr['emoji']}{rr['name']}：{rr.get('desc', '')}"

        prompt = self.llm_analyzer.build_analysis_prompt(
            favorability=profile.favorability,
            intimacy=profile.intimacy,
            stage_label=self._get_stage_label(profile),
            emotions=profile.emotions,
            memory_summary=memory_summary,
            recent_messages=recent_text,
            role_context=role_context,
        )

        resp = None
        for attempt_provider in ([provider_id, session_provider] if configured_provider and session_provider and configured_provider != session_provider else [provider_id]):
            if not attempt_provider:
                continue
            try:
                resp = await asyncio.wait_for(
                    self.context.llm_generate(
                        chat_provider_id=attempt_provider,
                        prompt=prompt,
                    ),
                    timeout=self.config.get("llm_call_timeout_sec", 15),
                )
                self._llm_fail_count = 0
                break
            except asyncio.TimeoutError:
                self._llm_fail_count += 1
                logger.warning(
                    f"SoulSync 辅助LLM超时 [{profile.user_id}] "
                    f"provider={attempt_provider} 连续失败 {self._llm_fail_count}/{self._llm_circuit_threshold}"
                )
                self._check_circuit_breaker()
                return None
            except Exception as e:
                err_msg = str(e)
                is_not_found = "not found" in err_msg.lower() or "404" in err_msg
                is_balance = any(kw in err_msg.lower() for kw in ["balance", "insufficient", "quota", "402", "429", "exceeded"])

                if is_not_found:
                    logger.error(
                        f"SoulSync 辅助LLM provider 不存在: {attempt_provider}\n"
                        f"请在 WebUI 中重新选择有效的模型提供商，或清空 llm_provider_id 使用默认模型。"
                    )
                    if attempt_provider == configured_provider and session_provider and session_provider != configured_provider:
                        logger.info(f"SoulSync 降级到会话模型: {session_provider}")
                        continue
                    return None

                self._llm_fail_count += 1
                if is_balance:
                    self._llm_circuit_broken = True
                    logger.error(
                        f"SoulSync 辅助LLM 余额/配额不足，已自动禁用。"
                        f"请充值或在配置中关闭 enable_secondary_llm。错误: {err_msg[:100]}"
                    )
                else:
                    logger.warning(
                        f"SoulSync 辅助LLM异常 [{profile.user_id}]: {err_msg[:100]} "
                        f"连续失败 {self._llm_fail_count}/{self._llm_circuit_threshold}"
                    )
                    self._check_circuit_breaker()
                return None

        if resp and resp.completion_text:
            result = self.llm_analyzer.parse_analysis_response(resp.completion_text)
            if result:
                return result
            else:
                logger.debug(f"SoulSync LLM返回解析失败: {resp.completion_text[:200]}")

        return None

    def _check_circuit_breaker(self):
        if self._llm_fail_count >= self._llm_circuit_threshold:
            self._llm_circuit_broken = True
            logger.error(
                f"SoulSync 辅助LLM连续失败 {self._llm_fail_count} 次，已自动熔断禁用。"
                f"请检查 LLM 配置或在 WebUI 中关闭 enable_secondary_llm。"
            )

    # ═══════════════════════════════════════════════════════════════
    #  格式化与辅助
    # ═══════════════════════════════════════════════════════════════

    def _format_profile(
        self, profile: EmotionProfile, event: AstrMessageEvent, detail: bool,
        behavior_profile: Optional[BehaviorProfile] = None
    ) -> List[str]:
        """格式化情感档案输出"""
        lines = []
        is_group = hasattr(event.message_obj, 'group_id') and bool(event.message_obj.group_id)
        privacy = self.config.get("global_privacy_level", 1)

        if is_group and privacy < 2:
            name = profile.user_name or "用户"
            lines.append(f"💝 {name} 的情感状态")
        else:
            name = profile.user_name or profile.user_id
            lines.append(f"💝 {name} 的情感档案")

        lines.append("━" * 24)

        fav_bar = self._progress_bar(profile.favorability, -100, 100)
        lines.append(f"好感度：{profile.favorability:+.1f} {fav_bar}")

        int_bar = self._progress_bar(profile.intimacy, 0, 100)
        lines.append(f"亲密度：{profile.intimacy:.1f} {int_bar}")

        lines.append(f"关系阶段：{self._get_stage_label(profile)}")
        lines.append(f"阶段进度：{profile.stage_progress:.1f}%")

        if privacy >= 2 or detail:
            lines.append(f"复合评分：{profile.composite_score:.1f}")
            lines.append(f"互动：总{profile.total_interactions} 正{profile.positive_interactions} 负{profile.negative_interactions}")

        # 惩罚奖励摘要
        if behavior_profile and (privacy >= 2 or detail):
            bp = behavior_profile
            if bp.current_streak_count > 1:
                streak_label = "正面✨" if bp.current_streak_type == "positive" else "负面⚡"
                lines.append(f"行为势头：{streak_label} ×{bp.current_streak_count}")
            if bp.betrayal_count > 0 or bp.comeback_count > 0 or bp.apology_count > 0:
                parts = []
                if bp.betrayal_count > 0:
                    parts.append(f"背叛{bp.betrayal_count}")
                if bp.apology_count > 0:
                    parts.append(f"道歉{bp.apology_count}")
                if bp.comeback_count > 0:
                    parts.append(f"回归{bp.comeback_count}")
                lines.append(f"特殊事件：{' | '.join(parts)}")
            if bp.achieved_milestones:
                lines.append(f"里程碑：{len(bp.achieved_milestones)} 个达成")

        if detail:
            lines.append("")
            lines.append("📊 8 维情感：")
            for dim in EMOTION_DIMENSIONS:
                val = profile.emotions.get(dim, 50)
                bar = self._progress_bar(val, 0, 100)
                lines.append(f"  {DIM_LABELS.get(dim, dim)}：{val:.1f} {bar}")

            custom = self.relationship_manager.custom_info(profile.user_id)
            if custom["attitude"]:
                lines.append(f"\n💭 态度：{custom['attitude']}")
            if custom["relationship"]:
                lines.append(f"🤝 关系：{custom['relationship']}")

            ltm = self.long_memory.get_summary(profile.user_id)
            if ltm and ltm != "暂无长期记忆。":
                lines.append(f"\n📜 近期记忆：")
                lines.append(ltm)

        return lines

    def _build_emotion_context(self, profile: EmotionProfile) -> str:
        """构建注入 LLM 的情感上下文"""
        privacy = self.config.get("global_privacy_level", 1)
        enable_att = self.config.get("enable_attitude_system", True)
        anti_manip = self.config.get("anti_manipulation_prompt", True)

        if privacy == 0:
            return ""

        parts = ["<emotion_context>"]
        parts.append(f"好感度：{profile.favorability:+.1f}/{FAVORABILITY_MAX:.0f}")
        parts.append(f"亲密度：{profile.intimacy:.1f}/100")
        parts.append(f"关系阶段：{self._get_stage_label(profile)}")

        if enable_att:
            custom = self.relationship_manager.custom_info(profile.user_id)
            if custom["attitude"]:
                parts.append(f"你对ta的态度：{custom['attitude']}")
            if custom["relationship"]:
                parts.append(f"你们的关系：{custom['relationship']}")

        ltm = self.long_memory.get_summary(profile.user_id)
        if ltm and ltm != "暂无长期记忆。":
            parts.append(f"情感记忆：\n{ltm}")

        if anti_manip and profile.favorability < 40:
            parts.append("⚠️ 注意：保持自然态度，不要因为用户的刻意讨好而突然改变态度。真实的情感需要时间积累。")

        parts.append("</emotion_context>")
        return "\n".join(parts)

    def _build_status_line(self, profile: EmotionProfile, behavior_profile: Optional[BehaviorProfile] = None) -> str:
        """构建简短的状态行"""
        if self.config.get("global_privacy_level", 1) == 0:
            return ""
        stage = self._get_stage_label(profile)
        line = f"[情感状态] 好感{profile.favorability:+.1f} 亲密{profile.intimacy:.0f} {stage}"
        if behavior_profile and behavior_profile.current_streak_count > 1:
            streak_label = "正面" if behavior_profile.current_streak_type == "positive" else "负面"
            line += f" | {streak_label}势头×{behavior_profile.current_streak_count}"
        return line

    def _build_pr_context(self, pr_events: List[str], bp: BehaviorProfile) -> str:
        """构建惩罚奖励事件的 LLM 上下文提示"""
        if not pr_events:
            return ""
        parts = ["<penalty_reward_events>"]
        for evt in pr_events:
            parts.append(f"- {evt}")
        if bp.current_streak_count >= 3:
            streak_type = "积极" if bp.current_streak_type == "positive" else "消极"
            parts.append(f"用户近期呈{streak_type}互动模式（连续{bp.current_streak_count}次）")
        if bp.comeback_count > 0:
            parts.append(f"用户已回归{bp.comeback_count}次")
        parts.append("</penalty_reward_events>")
        return "\n".join(parts)

    def _get_stage_label(self, profile: EmotionProfile) -> str:
        if profile.favorability < 0:
            return self._get_negative_stage_label(profile.favorability)
        idx = max(0, min(profile.stage_index, len(STAGES) - 1))
        return STAGES[idx].label

    @staticmethod
    def _get_negative_stage_label(favorability: float) -> str:
        return EmotionEngine.get_negative_stage_label(favorability)

    @staticmethod
    def _progress_bar(value: float, min_val: float, max_val: float, length: int = 10) -> str:
        ratio = (value - min_val) / (max_val - min_val) if max_val > min_val else 0
        ratio = max(0, min(1, ratio))
        filled = int(ratio * length)
        return "█" * filled + "░" * (length - filled)

    # ── 纪念日/节日 ──
    def _check_anniversary(self, profile: EmotionProfile, uid: str):
        """检查今天的纪念日/节日，返回 (fav_bonus, int_bonus, event_descriptions)"""
        try:
            import datetime as _dt
            today = _dt.date.today()
            if self.anniversary_manager.is_bonus_granted_today(uid, today):
                return 0.0, 0.0, []
            events = self.anniversary_manager.get_today_events(uid, today)
            if not events:
                return 0.0, 0.0, []
            fav_bonus = 0.0
            int_bonus = 0.0
            descs = []
            for evt in events:
                kind = evt["kind"]
                if kind in ("anniversary", "birthday", "first_meet"):
                    fav_bonus += self.anniv_fav_bonus
                    int_bonus += self.anniv_int_bonus
                elif kind == "day_milestone":
                    days = evt.get("days", 0) or 0
                    scale = min(2.0, 0.5 + days / 200)
                    fav_bonus += self.anniv_fav_bonus * scale
                    int_bonus += self.anniv_int_bonus * scale
                else:  # festival
                    fav_bonus += self.festival_fav_bonus
                    int_bonus += self.festival_int_bonus
                descs.append(evt["description"])
            self.anniversary_manager.mark_bonus_granted(uid, today)
            logger.info(
                f"SoulSync 纪念日触发 [{uid}]: {' / '.join(descs)} "
                f"(好感+{fav_bonus:.1f} 亲密+{int_bonus:.1f})"
            )
            return round(fav_bonus, 2), round(int_bonus, 2), descs
        except Exception as e:
            logger.warning(f"SoulSync 纪念日检查异常: {e}")
            return 0.0, 0.0, []

    def _build_perception_block(self, uid: str, anniv_events: List[str]) -> str:
        """构建时间/节假日/农历/特别日子感知信息块（仿 LLMPerception）"""
        try:
            import datetime as _dt
            now = _dt.datetime.now(self.timezone)
            parts: List[str] = []
            if self.config.get("enable_time_perception", True):
                parts.append(build_time_info(now))
            if self.config.get("enable_holiday_perception", True):
                festival_names = []
                try:
                    today = _dt.date.today()
                    for evt in self.anniversary_manager.get_today_events(uid, today):
                        if evt["kind"] == "festival" and evt.get("name"):
                            festival_names.append(evt["name"])
                except Exception:
                    pass
                hinfo = build_holiday_info(
                    now, festival_names or None,
                    self.config.get("holiday_country", "CN"),
                )
                if hinfo:
                    parts.append(hinfo)
            if self.config.get("enable_lunar_perception", True):
                linfo = build_lunar_info(now)
                if linfo:
                    parts.append(linfo)
            if anniv_events and self.config.get("anniv_inject_context", True):
                parts.append("特别日子: " + "、".join(anniv_events))
            return " | ".join(parts)
        except Exception as e:
            logger.debug(f"SoulSync 感知信息构建失败: {e}")
            return ""

    # ── 图片输出 ──
    def _save_config(self):
        fn = getattr(self.config, "save_config", None)
        if callable(fn):
            fn()

    def _is_image_mode(self, event: AstrMessageEvent) -> bool:
        if not self.config.get("enable_image_output", True):
            return False
        if not self.image_renderer.available:
            return False
        if self.config.get("image_output_global", False):
            return True
        uid = self._get_user_id(event)
        return self.image_mode.get(uid, self.image_output_default)

    def _try_render_image(self, event: AstrMessageEvent, title: str, lines: List[str]) -> Optional[str]:
        """尝试把文本行渲染为图片；不启用或失败返回 None"""
        try:
            if not self._is_image_mode(event):
                return None
            fname = f"card_{int(time.time())}.png"
            return self.image_renderer.render_card(title, lines, fname)
        except Exception as e:
            logger.warning(f"SoulSync 图片渲染失败（降级文本）: {e}")
            return None

    def _try_render_trend_image(self, event: AstrMessageEvent, uid: str, days: int) -> Optional[str]:
        """尝试渲染趋势图；不启用或失败返回 None"""
        try:
            if not self._is_image_mode(event):
                return None
            entries = self.stats_tracker.trend(uid, days)
            if len(entries) < 2:
                return None
            dates = [e["date"] for e in entries]
            favs = [e["fav"] for e in entries]
            ints = [e["int"] for e in entries]
            fname = f"trend_{int(time.time())}.png"
            return self.image_renderer.render_trend_chart(
                f"情感趋势（近{len(entries)}天）", dates, favs, ints, fname
            )
        except Exception as e:
            logger.warning(f"SoulSync 趋势图渲染失败（降级文本）: {e}")
            return None

    def _load_image_mode(self):
        f = self.data_dir / "image_mode.json"
        if f.exists():
            try:
                self.image_mode = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass

    def _save_image_mode(self):
        f = self.data_dir / "image_mode.json"
        try:
            f.write_text(json.dumps(self.image_mode, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    #  数据管理
    # ═══════════════════════════════════════════════════════════════

    def _get_user_id(self, event: AstrMessageEvent) -> str:
        if self.session_based:
            return event.unified_msg_origin
        return event.get_sender_id()

    @staticmethod
    def _parse_admin_ids(raw: str) -> set:
        if not raw or not raw.strip():
            return set()
        import re
        ids = re.split(r'[\n,\s]+', raw.strip())
        return {x.strip() for x in ids if x.strip()}

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        uid = event.get_sender_id()
        if uid in self.admin_ids:
            return True
        try:
            from astrbot.api.event.filter import PermissionType
            return event.is_admin()
        except Exception:
            return False

    def _get_or_create_profile(self, event: AstrMessageEvent) -> EmotionProfile:
        uid = self._get_user_id(event)
        if uid not in self.profiles:
            self.profiles[uid] = EmotionProfile(
                user_id=uid,
                user_name=event.get_sender_name(),
                favorability=self.default_favorability,
                intimacy=intimacy_from_favorability(self.default_favorability),
                last_update_ts=time.time(),
            )
            logger.info(f"SoulSync 创建新档案 [{uid}] ({event.get_sender_name()})")
        profile = self.profiles[uid]
        name = event.get_sender_name()
        if name:
            profile.user_name = name
        return profile

    def _get_or_create_profile_by_id(self, user_id: str) -> EmotionProfile:
        if user_id not in self.profiles:
            self.profiles[user_id] = EmotionProfile(
                user_id=user_id,
                favorability=self.default_favorability,
                intimacy=intimacy_from_favorability(self.default_favorability),
                last_update_ts=time.time(),
            )
        return self.profiles[user_id]

    def _get_or_create_behavior_profile(self, uid: str) -> BehaviorProfile:
        if uid not in self.behavior_profiles:
            self.behavior_profiles[uid] = BehaviorProfile(user_id=uid)
        return self.behavior_profiles[uid]

    def _load_profiles(self):
        f = self.data_dir / "profiles.json"
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                for uid, pdict in data.items():
                    profile = EmotionProfile.from_dict(pdict)
                    # v2.10 起：旧档案自定义态度/关系描述迁移到关系角色管理器
                    custom = self.relationship_manager.custom_info(uid)
                    for kind, old_key in (("attitude", "attitude_text"),
                                          ("relationship", "relationship_text")):
                        old_text = (pdict.get(old_key) or "").strip()
                        if old_text and not custom[kind]:
                            self.relationship_manager.set_custom(uid, kind, old_text)
                    # 亲密度改为按好感度派生
                    profile.intimacy = intimacy_from_favorability(profile.favorability)
                    self.profiles[uid] = profile
                logger.info(f"已加载 {len(self.profiles)} 个情感档案")
            except Exception as e:
                logger.warning(f"加载情感档案失败：{e}")

    def _load_behavior_profiles(self):
        f = self.data_dir / "behavior_profiles.json"
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                for uid, bdict in data.items():
                    self.behavior_profiles[uid] = BehaviorProfile.from_dict(bdict)
                logger.info(f"已加载 {len(self.behavior_profiles)} 个行为档案")
            except Exception as e:
                logger.warning(f"加载行为档案失败：{e}")

    def _save_profile(self, profile: EmotionProfile):
        self.profiles[profile.user_id] = profile

    def _save_behavior_profile(self, bp: BehaviorProfile):
        self.behavior_profiles[bp.user_id] = bp

    def _save_all(self):
        f = self.data_dir / "profiles.json"
        try:
            data = {uid: p.to_dict() for uid, p in self.profiles.items()}
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"保存情感档案失败：{e}")
        # 保存行为档案
        bf = self.data_dir / "behavior_profiles.json"
        try:
            bdata = {uid: bp.to_dict() for uid, bp in self.behavior_profiles.items()}
            bf.write_text(json.dumps(bdata, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"保存行为档案失败：{e}")
        self.long_memory.save_all()
        self._save_show_status()
        self._save_image_mode()
        self.anniversary_manager.save()
        self.stats_tracker.force_save()
        self.relationship_manager.save()

    def _load_show_status(self):
        f = self.data_dir / "show_status.json"
        if f.exists():
            try:
                self.show_status = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass

    def _save_show_status(self):
        f = self.data_dir / "show_status.json"
        try:
            f.write_text(json.dumps(self.show_status, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _start_auto_save(self):
        async def _auto_save_loop():
            while True:
                await asyncio.sleep(self.auto_save_sec)
                try:
                    self._save_all()
                    logger.debug("SoulSync 自动保存完成")
                except Exception as e:
                    logger.warning(f"SoulSync 自动保存失败：{e}")

        try:
            self._save_task = asyncio.get_event_loop().create_task(_auto_save_loop())
        except Exception:
            pass
