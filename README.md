# 心旅知音 (SoulSync)

> 融合 EmotionAI 与 FavourPro 精华的情感智能插件：关键词+LLM 双通道分析 · 8 维情感 · 好感/亲密度 · 十二阶段 · 惩罚奖励 · 四层记忆 · 关系角色 · 纪念日节日 · 时间感知深化 · 个性化训练 · RDE 关系深度演进 · 图片输出 · WebUI 控制台

---

## 目录

- [功能总览](#overview) · [安装](#install) · [命令](#commands) · [更新流程](#flow) · [核心机制](#core) · [WebUI](#webui) · [配置](#config) · [文件结构](#files) · [版本记录](#changelog) · [致谢](#credits)

---

<a id="overview"></a>

## 功能总览

| 模块 | 说明 |
|------|------|
| 双通道情感分析 | 关键词引擎每轮必做，辅助 LLM 按四维决策深度分析，按权重融合 |
| 8 维情感 + 好感/亲密 | 喜悦/悲伤/愤怒/恐惧/惊讶/厌恶/信任/期待；好感 -100~200，亲密按好感派生 |
| 十二阶段演进 | 复合评分 12 阶段（15~200）带过渡缓冲，负好感走独立路线 |
| 惩罚奖励 | 行为势头/冷落惩罚（每日结算）/回归奖励/背叛/道歉/里程碑，效果 72h 半衰期衰减 |
| 四层记忆 | 近期对话 → 长期记忆（SQLite + 摘要压缩）→ 行为档案 → 每日快照（月度分表） |
| 关系角色 | 39 个内置角色：内容自动判定 / 用户解锁一次性锁定 / 管理员调整 |
| 纪念日节日 | 农历换算 + 认识里程碑 + 生日 + 27+ 传统节日 |
| 时间感知深化（TPD） | 天气×节气×月相→心情映射 + 倒计时六阶段叙事 + 时间跳跃 |
| 图片输出 | Pillow 图片卡片（含趋势图），三级开关，未装自动降级 |
| WebUI 控制台 | 仪表盘 / 自画像 / 141 项配置 · 16 模块组热更新 / 排行榜 / 管理员工具 |
| 个性化训练 | 人格微调（20 参数+护栏）· 知识库（6 类）· 语言风格（三阶段+快照）· 私人记忆（4 类型）；四模块联动，注入优先级 人格>知识>记忆>风格（450 token 预算）；人格护栏：50 轮稳定自动锁定 / 24h 3 次剧变回滚 / 背叛·冷落≥3 天自动解锁 |
| RDE 关系深度演进 | 十二阶段叙事注入（按 `rde_stage_inject_every_n` 轮间隔，跃迁强制）· 关系危机（7 类型 14 事件）· 多角色关系网（39 角色跨角色传导，5 类社交事件） |
| SQLite 分片存储（v3.00） | WAL 模式连接池 · 月度分表 · 排行榜缓存 · `SOULSYNC_DB_FALLBACK=true` 一键回退 JSON |
| 渐进式摘要压缩（v3.00） | 记忆 >20 条自动压缩旧记忆为泛化摘要（权重 0.3）· TF-IDF 关键词提取 · `/心管 压缩` 手动触发 |
| 转生系统（v3.00） | 好感达阈值自动转生（递增式无限轮回）· 每转关键词敏感度 +5%、冷落抗性 +3% |
| v2.20 架构 | 命令路由（10 父命令+`/心管`）· 事件总线 · 人格护栏 · 意图识别 · 前后置钩子 |

---

<a id="install"></a>

## 安装

1. 将 `astrbot_plugin_soulsync/` 复制到 AstrBot `data/plugins/`
2. 重启 AstrBot 或 WebUI 点「重载插件」
3. 配置页按需调整参数

纯 Python 实现，无强制依赖：图片输出需 `Pillow`、节假日调休需 `chinese-calendar`、农历换算需 `lunarcalendar`，未装自动降级。

---

<a id="commands"></a>

## 命令

> 💡 **95% 场景无需输入命令**：查询类自然语言（如"我们之间现在算什么关系？"）由意图识别自动输出卡片并阻断聊天。

### 情感状态

#### `/心声`

| 权限 | 子命令 | 说明 |
|------|--------|------|
| 👤 | `好感` | 核心情感数值（好感/亲密度/阶段/行为势头） |
| 👤 | `阶段` | 当前关系阶段详情 |
| 👤 | `画像` | 个人情感自画像（8 维情感 + 行为模式 + 里程碑） |
| 👤 | `系统` | 插件数据规模（缓存统计） |

#### `/回忆`

| 权限 | 子命令 | 说明 |
|------|--------|------|
| 👤 | `趋势 [天数]` | 最近 N 天（默认 14）情感数据趋势 |
| 👤 | `月报 [上月]` | 关系月报（净好感/情绪主色调/里程碑） |
| 👤 | `报告 [天数]` / `独白` | 角色第一人称口吻回顾（默认 14 天） |
| 👤 | `对比 [天数]` | 前后两段 N 天关系六维雷达对比（默认 7 天） |
| 👤 | `时间线 [ID]` | RDE 阶段时间线叙事（管理员可加 ID 查看他人） |
| 👤 | `危机 [ID]` | RDE 危机历史与冷却（管理员可加 ID 查看他人） |
| 👤 | `关系网 [ID]` | 多角色关系网（管理员可加 ID 查看他人） |

### 纪念日与角色

#### `/纪念`

| 权限 | 子命令 | 说明 |
|------|--------|------|
| 👤 | `查看` | 纪念日列表与倒计时 |
| 👤 | `添加 <MM-DD> <名称>` | 添加自定义纪念日 |
| 👤 | `删除 <名称>` | 删除自定义纪念日 |
| 👤 | `生日 <MM-DD>` | 设置生日 |
| 👤 | `节日` | 全部节日列表与倒计时 |
| 🛡️ | `节日添加` / `节日删除` | **仅管理员**；添加/删除节日 |

#### `/角色`

| 权限 | 子命令 | 说明 |
|------|--------|------|
| 👤 | `列表` / `查看` | 角色列表（默认 + 自定义） |
| 👤 | `创建 <名字> [emoji] [性格]` | 创建并切换到自定义角色 |
| 👤 | `切换 <名字\|默认>` | 切换对话角色（好感/记忆按角色独立） |
| 👤 | `删除 <名字>` | 删除自建角色（档案保留） |
| 👤 | `称谓 [称呼\|无]` | 设置专属称谓 |
| 👤 | `关系 [角色]` | 关系角色列表与解锁进度 |
| 👤 | `解锁 <角色>` | 解锁系统内置关系角色 |
| 👤 | `关系切换 <角色>` | 切换关系角色（**一次即锁定，不可逆**） |

### 个性化训练

> 默认关闭：需开启 `enable_personalization` 后 `/人格 /知识 /风格 /记忆` 才可用。

#### `/人格`

| 权限 | 子命令 | 说明 |
|------|--------|------|
| 👤 | `查看` | 人格面板（20 参数/稳定度/锁定状态），全员只读 |
| 🛡️ | `设置 <参数> <值>` | **仅管理员**；操作后 2h 自动化微调暂停 |
| 🛡️ | `重置` | **仅管理员**；恢复全部默认并解除锁定 |
| 🛡️ | `锁定` | **仅管理员**；锁定/解锁人格参数 |

#### `/知识`

| 权限 | 子命令 | 说明 |
|------|--------|------|
| 👤 | `查看` | 知识库（按分类分组） |
| 👤 | `添加 [分类] <内容>` | 添加知识（profile/interests/people/promises/experiences/values） |
| 👤 | `删除 <ID>` | 删除知识条目 |

#### `/风格`

| 权限 | 子命令 | 说明 |
|------|--------|------|
| 👤 | `状态` | 语言风格训练状态（阶段/融合度/快照列表） |
| 👤 | `保存 [名称]` / `恢复 <名称>` | 风格快照保存/恢复 |
| 👤 | `锁定` | 锁定/解锁风格（锁定期停止学习） |

#### `/记忆`

| 权限 | 子命令 | 说明 |
|------|--------|------|
| 👤 | `查看` | 私人记忆库（按类型分组 + 星标） |
| 👤 | `添加 <类型> <内容>` | 添加记忆（text/image/promise/emotional） |
| 👤 | `删除 <ID>` / `星标 <ID>` | 删除记忆 / 切换星标（⭐ 检索优先） |
| 👤 | `重要 [序号]` / `忘记 [序号]` | 长期记忆标记重要 / 忘掉（1=最近） |

### 环境感知与排行

#### `/天象`

| 权限 | 子命令 | 说明 |
|------|--------|------|
| 👤 | `天气` | 当前环境感知（天气/季节/节气/月相/心情倾向） |
| 👤 | `倒计时` | 即将到来的倒计时事件（类型/距离/得分） |
| 👤 | `跳跃 [N天后见]` | 时间跳跃状态；触发告别→冷落冻结→回归叙事 |
| 👤 | `回溯` | 回溯关键时刻的时间线叙事（最多 5 条） |

#### `/排行`

| 权限 | 子命令 | 说明 |
|------|--------|------|
| 👤 | `好感 [n]` / `负好感 [n]` | TOP n 好感 / BOTTOM n 负好感（默认 10，最多 20） |

### 独立命令

| 权限 | 命令 | 说明 |
|------|------|------|
| 👤 | `/图片模式` | 切换本人指令输出为图片卡片（需 Pillow） |
| 👤 | `/设置` | 切换是否在对话后自动显示情感状态行 |
| 👤 | `/心助` | 命令总览（普通用户自动隐藏管理员命令，管理员全显） |

> `enable_rde` 开启后 `/回忆 时间线/危机/关系网` 才可用；`/心助` 按权限过滤：普通用户不显示节日添加/删除、人格设置/重置/锁定、`/心管`。

### 管理员命令（🛡️ `/心管`，仅管理员）

| 权限 | 命令 | 说明 |
|------|------|------|
| 🛡️ | `/心管 图片模式` | 全局开启/关闭图片输出（所有信息命令强制图片） |
| 🛡️ | `/心管 好感/亲密/态度/关系 <ID> ...` | 强制设置好感、态度、关系描述（关系角色）等 |
| 🛡️ | `/心管 关系角色 <ID> <角色>` | 强制调整关系角色（绕过锁定与解锁条件，解除锁定） |
| 🛡️ | `/心管 重置好感 <ID>` | 重置为默认值并清空长期记忆和行为档案 |
| 🛡️ | `/心管 查看好感 <ID>` | 查看完整档案（含 8 维情感、长期记忆、行为模式） |
| 🛡️ | `/心管 隐私 <0-2>` | 0=完全保密 1=基础 2=详细 |
| 🛡️ | `/心管 重置` / `备份` | 清空所有数据 / 创建快照（含长期记忆和行为档案） |
| 🛡️ | `/心管 修复统计` | 依据好感/亲密度自动修正正负互动次数 |
| 🛡️ | `/心管 强制跳跃 <ID> <天数>` / `重置跳跃 [ID]` | 强制用户时间跳跃（冻结冷落惩罚）/ 重置跳跃状态 |
| 🛡️ | `/心管 天气调试` | 查看天气获取调试信息（API/缓存/来源） |
| 🛡️ | `/心管 导出` | 导出个性化数据为 JSON（persona/knowledge/style/memory） |
| 🛡️ | `/心管 人格锁定` | 锁定/解锁指定用户人格参数 |
| 🛡️ | `/心管 调试事件` / `调试记忆` | 排障：输出事件结构 / 近期对话缓存、长期记忆、行为档案详情 |
| 🛡️ | `/心管 压缩 <ID>` | 手动触发指定用户记忆压缩（v3.00） |

管理员判定：AstrBot 内置管理员 **或** `admin_ids` 配置项。

---

<a id="flow"></a>

## 更新流程

每条消息依次执行：

```
⓪ 前置钩子：意图识别（查询类→出卡片并阻断，不走 LLM）
① 关键词分析（每轮必做）→ ② 惩罚奖励分析 → ③ 智能更新决策
→ ④ 辅助 LLM 深度分析（四维触发，超时保护+熔断，失败降级）
→ ⑤ 应用变更（好感/亲密/8 维情感/复合评分/阶段）
→ ⑥ 个性化训练（仅 enable_personalization）：
   人格偏移 → 每轮隐式训练（人格护栏守护）→ 注入上下文（人格>知识>记忆>风格，450 token 预算）
→ ⑦ 注入 LLM（时间感知 + 角色人设 + 情感上下文 + 个性化上下文）
→ ⑧ 后置钩子：prompt 泄漏清理等
```

关键词通道每轮必做；LLM 通道按 `llm_weight`（0.4）融合；惩罚奖励按 `pr_weight`（0.6）融合。

---

<a id="core"></a>

## 核心机制

### 关系阶段

复合评分 = 好感 + 情感加成（喜悦/信任/期待均值 ×15，上限 215）。阈值 **15/35/55/75/95/115/135/152/168/180/185/200**，过渡缓冲 2~8 分。负好感独立：冷淡(-15) → 反感(-40) → 厌恶(-70) → 敌对(-100)。

### 惩罚奖励

| 机制 | 触发条件 | 效果 |
|------|---------|------|
| 🔥 行为势头 | 连续正/负面互动 | +0.24 / -0.76 每层（上限 10 层） |
| ❄️ 冷落惩罚 | 每日定时结算 | 基础 -1.8 + 0.43/天 × 好感因子（上限 -14） |
| 💫 回归奖励 | 冷落 48h+ 后回归 | +1.5 + 0.24/天（上限 +6.0） |
| 💔 背叛检测 | 背叛/欺骗关键词 | -7.3（累犯加重，冷却 1h） |
| 🕊️ 道歉恢复 | 抱歉/我错了 | +1.0（冷却 10min） |
| 🏆 里程碑 | 50/100/200 次互动 | +1.0 / +1.5 / +2.6 / +4.2 |

效果带 72h 半衰期自然衰减。

### 记忆系统

近期对话（内存 10 轮）→ 长期记忆（落盘 JSON，显著性阈值）→ 行为档案 → 每日快照。

### 智能更新（四维决策）

关键词强度 · 时间压力 · 强制计数器 · LLM 标记，任一满足即触发辅助 LLM。

### 纪念日与节日

内置农历换算（1900-2100），自动识别认识里程碑（7/30/50/100/200/365/500/1000/1500/2000/3000 天）、生日与 27+ 传统节日；节日当天自动奖励 + LLM 氛围注入。

### 情感自画像

`/心声 画像` 展示：核心数值、关系阶段与角色、8 维情感、互动统计、行为模式、关系建议。

### 关系角色系统

内置 **39 个关系角色**，三种机制并存：

| 机制 | 说明 |
|------|------|
| 🤖 内容自动判定 | 态度/关系文本 + 最近消息关键词匹配（长词加权），未命中按画像推荐 |
| 🔓 用户解锁+一次性切换 | 满足条件 `/角色 解锁`；`/角色 关系切换` 切换即锁定 |
| 🛠️ 管理员调整 | `/心管 关系角色` 或 WebUI 强制调整，调整后解除锁定 |

- 解锁需好感、亲密、互动次数同时满足；负好感自动定级（世仇→仇人→对手→厌恶→反感→冷漠）
- 自定义态度/关系合并进当前角色人设，注入 LLM、自画像与状态显示

### 时间感知

每次 LLM 请求注入感知信息（时间/星期/时段/节假日/农历干支）。`enable_time_perception` / `enable_holiday_perception` / `enable_lunar_perception` 分开关。

### 时间感知深化（TPD）

`tpd_enabled` 开启，三大子系统：

- **环境感知**：三级降级天气（API → 本地节气推算 → 纯时间，60 分钟缓存）；天气×温度×季节×月相 → 8 维心情映射
- **倒计时事件**：认识周年/生日/纪念日/节日（含农历），T-7~T+7 六阶段叙事，24h 去重
- **时间跳跃**：`/天象 跳跃 三天后见` 告别 → 冷落惩罚冻结 → 回归重逢叙事；被动离开 6h+ 分级反应

天气 API 配置：`tpd_weather_api_provider`（hefeng / openweather / 留空=本地推算）· `tpd_weather_api_key` · `tpd_weather_api_city`

### 数据趋势

每日快照落盘（默认 30 天自动清理）；`/回忆 趋势` 文本柱状图 + WebUI 趋势条。

### 图片输出

信息命令均可渲染图片卡片。三级开关：总开关 → 全局（`/心管 图片模式`）→ 用户级（`/图片模式`）；自动探测中文字体，未装 Pillow 自动降级。

---

<a id="webui"></a>

## WebUI 控制台

AstrBot 插件详情页进入：仪表盘（档案数/平均好感/平均亲密/最高阶段）· 用户列表 · 自画像 · 141 项配置 · 16 模块组热更新 · 排行榜 · 管理员工具 · 系统状态。

模块面板：**个性化训练**（四标签页）· **RDE 关系演进**（阶段/危机/关系网）· **时间感知**（环境/倒计时/跳跃）。

**API**：`/data` · `/config` · `/admin` · `/trainer/*` · `/rde/data` · `/tpd/data`

---

<a id="config"></a>

## 配置

141 项配置，WebUI 可视化编辑（数值类带滑块），保存即生效，无需重载插件。16 个模块组：

| 分组 | 关键配置 |
|------|---------|
| 功能开关 | `enable_attitude_system` `enable_ai_text_generation` `enable_secondary_llm` `enable_smart_update` `show_status_default` `enable_multi_role` `enable_intent_router` `enable_hooks` `enable_stage_styles` `enable_s12_forced_address` |
| RDE 深度演进 | `enable_rde` `rde_stage_inject_every_n` `enable_crisis_system` `enable_network` `crisis_trigger_probability`(0.02) `crisis_max_probability`(0.10) `crisis_min_stage` `crisis_protection_hours` `network_transmission_delay_turns` |
| 情感参数 | `default_favorability` `keyword_sensitivity` `fav_growth_rate`(0.5) `micro_change_*` `enable_emotion_contagion` `tension_*` `eruption_fav_penalty` |
| 智能更新 | `force_update_interval` `keyword_update_threshold` `time_update_threshold_sec` |
| 辅助 LLM | `llm_provider_id` `llm_weight`(0.4) `llm_call_timeout_sec` `llm_recent_messages_count` |
| 记忆 | `emotional_significance_threshold` `max_long_term_events` `memory_half_life_days` `memory_recall_bonus` |
| 个性化训练 | `enable_personalization` `personalization_static_every_n` `persona_implicit_training` `persona_stability_enabled` `knowledge_enabled` `style_training_enabled` `private_memory_enabled` `personalization_total_token_budget`(450) |
| 隐私 | `global_privacy_level` `session_based` `anti_manipulation_prompt` `admin_ids` |
| 惩罚奖励 | `pr_enable_*`(6 开关) `pr_cold_threshold_hours` `pr_comeback_threshold_hours` `pr_decay_half_life_hours` `pr_weight`(0.6) |
| 纪念日/节日 | `enable_anniversary_system` `anniv_fav_bonus` `festival_fav_bonus` `anniv_inject_context` |
| 时间感知 | `timezone` `enable_time_perception` `enable_holiday_perception` `enable_lunar_perception` `enable_weather_perception` `time_jump_*` |
| TPD 环境 | `tpd_enabled` `tpd_env_inject_every_n` `tpd_weather_*`(provider/key/city/cache/mood_strength) `tpd_season_mood_strength` `tpd_moonphase_*` |
| TPD 倒计时/跳跃 | `tpd_countdown_*` `tpd_skip_*`(上限/冻结/漂移) `tpd_passive_gap_threshold_hours` `tpd_return_narrative_enabled` |
| 数据统计 | `enable_stats_tracking` `stats_history_days` `trend_default_days` |
| 关系角色 | `enable_relationship_roles` `relationship_auto_assign` |
| 图片输出 | `enable_image_output` `image_output_default` `image_output_global` |

---

<a id="files"></a>

## 文件结构

```
astrbot_plugin_soulsync/
├── metadata.yaml / _conf_schema.json / requirements.txt
├── main.py                # 主入口：命令 + LLM 钩子 + 情感引擎 + WebUI + 图片
├── command_router.py      # 10 父命令 + /心管 路由表与帮助
├── event_bus.py           # 事件总线（favor.changed / stage.advanced）
├── intent_router.py       # 意图识别（自然语言静默命令路由）
├── hook_bus.py            # 前后置钩子注册表
├── emotion_engine.py      # 8 维情感 + 好感/亲密度引擎
├── smart_updater.py       # 四维智能更新决策器
├── memory_manager.py      # 长期记忆管理器（JSON 后端，降级模式用）
├── llm_analyzer.py        # 辅助 LLM 情感分析
├── penalty_reward.py      # 惩罚奖励引擎（含冷落冻结）
├── anniversary.py         # 纪念日/节日系统（农历 1900-2100）
├── stats_tracker.py       # 每日快照与趋势统计（JSON 后端，降级模式用）
├── relationship_roles.py  # 关系角色系统（39 角色）
├── relationship_crisis.py # 关系危机事件
├── character_manager.py   # 多角色并行关系
├── time_perception.py     # 时间/节假日/农历感知
├── image_renderer.py      # 图片卡片渲染（Pillow，可选）
├── report.py              # 报告生成（月报/回顾/趋势等）
├── storage/               # v3.00 SQLite 存储引擎
│   ├── pool.py            #   连接池（WAL 模式，单例，10s 超时）
│   ├── schema.py          #   表结构定义（9 主表 + 月度分表）
│   ├── memory_store.py    #   长期记忆（替代 JSON）
│   ├── stats_store.py     #   每日快照（月度分表）
│   └── leaderboard_cache.py # 排行榜缓存
├── compressor/            # v3.00 渐进式摘要压缩
│   ├── keyword_extractor.py   # TF-IDF 关键词提取
│   └── memory_compressor.py   # 记忆压缩器
├── rebirth/               # v3.00 转生系统
│   └── rebirth_engine.py      # 递增式无限轮回
├── db_migration/          # v3.00 数据迁移工具
│   ├── validator.py           # JSON vs SQLite 校验
│   └── migrate_json_to_sqlite.py # 全量迁移脚本
├── trainer/               # 个性化训练：人格 / 知识 / 风格 / 记忆 + 护栏
├── rde/                   # 关系深度演进：narrative / crisis / network
├── tpd/                   # 时间感知深化：天气 / 倒计时 / 跳跃
├── pages/dashboard/       # WebUI 控制台
├── docs/                  # 文档
│   └── UPGRADE_GUIDE.md   #   v3.00 升级指南
└── tests/                 # 测试文件
    ├── stress_test.py     #   2000 轮压力测试
    └── test_migration_roundtrip.py # 迁移回环测试
```

---

<a id="changelog"></a>

## 版本记录

完整记录见 [changelog.md](changelog.md)

| 版本 | 摘要 |
|------|------|
| **v3.00**（当前） | Project Hermes：SQLite 分片存储 · 转生系统 · 记忆压缩 · 降级熔断 · 排行榜缓存 · S12 满分之爱强制称谓修复 |
| **v2.23** | `/心助` 命令总览按权限过滤 · 帮助说明全面扩充 |
| **v2.22** | 帮助图片排版重构 · 张力种子增强 · 关键词上限翻倍 |
| **v2.21** | RDE 叙事频控 · WebUI 16 模块组 141 键全量可视化 · 命令换词 |
| **v2.20** | 轻量化重构：10 父命令 + EventBus + 人格护栏 + 意图识别 + HookBus |
| **v2.19** | 时间感知深化（TPD）：天气/倒计时/时间跳跃 · 74 组测试 |
| **v2.18** | 关系深度演进（RDE）：十二阶段叙事 · 危机系统 · 多角色关系网 |
| **v2.17** | 个性化训练：人格微调 / 知识库 / 语言风格 / 私人记忆 · 四模块联动 |
| **v2.16** | 情感深化：记忆锚点/遗忘曲线 · 复合情绪/情绪传染 · 多角色并行关系 |
| **v2.15** | 冷落惩罚改为每日定时结算 |
| **v2.14** | WebUI 玻璃态整合系列 |
| **v2.13~v2.10** | 好感放缓 50% · 6→12 阶段 · 惩罚奖励放缓 · 好感上限 200 |
| **v2.9~v1.0** | 配置热同步 / 关系角色 / 数据趋势 / 纪念日节日 / 初版融合 |

---

<a id="credits"></a>

## 参考与致谢（二创声明）

本插件为二次创作，借鉴以下开源项目核心机制思路并融合扩展：

| 参考项目 | 借鉴内容 |
|----------|---------|
| [EmotionAI-Pro](https://github.com/asakiyoshi/EmotionAI-Pro) | 8 维情感模型、好感/亲密度双核、阶段演进、智能更新、辅助 LLM、惩罚奖励 |
| [LLMPerception](https://github.com/miaoxutao123/astrbot_plugin_LLMPerception) | 时间/节假日/农历/平台环境感知注入方式 |

代码与文案由 AI 辅助编写；版权归原作者所有，若有异议请联系删除。
