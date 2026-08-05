# 心旅知音 (SoulSync) v2.15 - 融合版情感智能插件（自用）

> 本插件由 AI 编写，参考融合 EmotionAI 与 FavourPro 精华，实现「关键词+LLM 双通道情感分析 · 8 维情感 · 好感/亲密度 · 十二阶段演进 · 惩罚奖励 · 长期记忆 · 关系角色 · 纪念日节日 · 时间感知 · 数据趋势 · 情感自画像 · 图片输出 · WebUI 控制台」，打造真实、渐进、可养成的 AI 情感交互系统。

---

## 🙏 参考与致谢（二次创作声明）

本插件为对以下开源项目的 **参考与二次创作（二创）**，借鉴其核心机制思路并融合扩展：

| 参考插件 | 借鉴内容 | 原项目 |
|----------|---------|--------|
| 🧠 情感智能插件 **EmotionAI-Pro** | 8 维情感模型、好感/亲密度双核、六阶段关系演进、智能更新决策、辅助 LLM 情感分析、惩罚奖励机制 | [asakiyoshi/EmotionAI-Pro](https://github.com/asakiyoshi/EmotionAI-Pro) |
| ⏰ 环境感知增强插件 **LLMPerception** | 时间/节假日/农历/平台环境感知的注入方式 | [miaoxutao123/astrbot_plugin_LLMPerception](https://github.com/miaoxutao123/astrbot_plugin_LLMPerception) |

**声明：** 本项目为二次创作，仅用于学习交流，代码与文案由 AI 辅助编写；项目版权归原作者所有，若原作者有异议请联系删除；使用本项目产生的任何问题与原作者无关。

---

## 📦 安装

1. 将 `astrbot_plugin_soulsync/` 目录复制到 AstrBot 的 `data/plugins/` 下
2. 重启 AstrBot，或在 WebUI 插件管理页面点击「重载插件」
3. 在 WebUI 插件配置页面按需调整参数

纯 Python 实现，无强制依赖（图片输出需 `Pillow`，节假日调休判断需 `chinese-calendar`、农历精确换算需 `lunarcalendar`，均未安装时自动降级）。

---

## 🎯 命令

### 用户命令

| 命令 | 说明 |
|------|------|
| `/好感度` | 查看当前情感状态（好感度、亲密度、阶段进度条、行为势头） |
| `/状态显示` | 切换是否在每次对话后自动显示情感状态行 |
| `/好感排行 [n]` | 查看 TOP n 好感度排行榜（默认 10，最多 20） |
| `/负好感排行 [n]` | 查看 BOTTOM n 负好感排行榜 |
| `/关系阶段` | 显示当前阶段、复合评分、行为势头、惩罚奖励统计 |
| `/缓存统计` | 查看插件数据规模（档案/行为档案/长期记忆用户数） |
| `/图片模式` | 切换本人指令输出为图片卡片（需已安装 Pillow） |
| `/纪念日` | 查看我的纪念日列表与倒计时 |
| `/添加纪念日 <名称> <月日> [类型]` | 添加自定义纪念日（类型可选 birthday/anniversary） |
| `/删除纪念日 <名称>` | 删除自定义纪念日 |
| `/设置生日 <月日>` | 设置生日（格式：MM-DD 或 M月D日） |
| `/节日列表` | 查看全部节日列表与倒计时 |
| `/趋势 [天数]` | 查看最近 N 天（默认 14）情感数据趋势 |
| `/关系角色 [角色]` | 查看关系角色列表与解锁进度，或单个角色详情 |
| `/解锁关系 <角色>` | 解锁系统内置关系角色（满足条件时；重复解锁=切换但不锁定） |
| `/切换关系 <角色>` | 切换已解锁关系角色（**一次即锁定，不可逆**） |
| `/我的画像` | 查看个人情感自画像（完整档案 + 8 维情感 + 行为模式 + 里程碑 + 关系建议） |

### 管理员命令

| 命令 | 说明 |
|------|------|
| `/全局图片模式` | 全局开启/关闭图片输出（所有信息命令强制图片） |
| `/设置关系角色 <ID> <角色>` | 强制调整关系角色（绕过锁定与解锁条件，解除锁定） |
| `/设置好感 <ID> <值>` | 设置好感度（-100 ~ 200，亲密度随之派生） |
| `/设置亲密 <ID> <值>` | 亲密度已按好感度派生，此命令提示改用设置好感 |
| `/设置态度 <ID> <文本>` | 自定义态度描述（合并进当前关系角色人设生效） |
| `/设置关系 <ID> <文本>` | 自定义关系描述（合并进当前关系角色人设生效） |
| `/重置好感 <ID>` | 重置为默认值并清空长期记忆和行为档案 |
| `/查看好感 <ID>` | 查看完整档案（含 8 维情感、长期记忆、行为模式） |
| `/隐私级别 <0-2>` | 0=完全保密 1=基础 2=详细 |
| `/重置插件` | 清空所有数据（含行为档案） |
| `/备份数据` | 创建快照（含长期记忆和行为档案） |
| `/修复互动统计` | 依据好感/亲密度自动修正正负互动次数 |
| `/调试事件` / `/调试记忆` | 输出事件结构 / 近期对话缓存、长期记忆、行为档案详情（排障） |
| `/设置节日 <名称> <月日>` | 添加自定义节日（农历节日按阴历计算） |
| `/删除节日 <名称>` | 删除自定义节日 |

管理员身份判定：AstrBot 内置管理员 **或** 配置项 `admin_ids` 中的用户 ID。

---

## ✨ 功能模块总览

所有配置均可在 AstrBot WebUI 插件管理页面可视化编辑（数值类带滑块），保存后**无需重载插件，下次对话自动生效**。

### 功能开关

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_attitude_system` | bool | `true` | 启用态度关系系统 |
| `enable_ai_text_generation` | bool | `true` | AI 自动生成态度/关系描述 |
| `enable_secondary_llm` | bool | `true` | 启用辅助 LLM 深度情感分析 |
| `enable_smart_update` | bool | `true` | 四维智能更新 |
| `show_status_default` | bool | `false` | 默认显示情感状态行 |

### 情感参数

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `default_favorability` | float | `0.0` | 初始好感度（-100~200） |
| `keyword_sensitivity` | float | `1.0` | 关键词敏感度倍率 |
| `fav_growth_rate` | float | `0.5` | 好感正向增长速率（v2.13 放缓 50%，负向惩罚不受影响） |
| `micro_change_favorability` | float | `0.21` | 无关键词时每轮好感微变化 |
| `micro_change_intimacy` | float | `0.07` | 无关键词时每轮亲密微变化（亲密度已改为按好感度派生，此值保留兼容） |

### 智能更新参数

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `force_update_interval` | int | `5` | 每隔多少轮强制触发辅助 LLM |
| `keyword_update_threshold` | float | `2.0` | 关键词累计分数触发阈值 |
| `time_update_threshold_sec` | int | `120` | 时间触发阈值（秒） |

### 辅助 LLM 参数

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `llm_provider_id` | string | `""` | 情感分析模型（留空=当前会话模型） |
| `llm_weight` | float | `0.4` | LLM 分析融合权重（0~1） |
| `llm_call_timeout_sec` | int | `15` | LLM 调用超时（秒） |
| `llm_recent_messages_count` | int | `5` | 传入 LLM 的近期消息数 |
| `attitude_max_length` | int | `25` | 态度描述最大字数 |
| `relationship_max_length` | int | `25` | 关系描述最大字数 |

### 记忆与存储

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `emotional_significance_threshold` | float | `5.0` | 长期记忆记入阈值 |
| `max_long_term_events` | int | `50` | 每用户长期记忆事件上限 |
| `auto_save_interval_sec` | int | `300` | 自动保存间隔（秒） |

### 隐私与安全

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `global_privacy_level` | int | `1` | 0=保密 1=基础 2=详细 |
| `session_based` | bool | `false` | 按会话隔离情感 |
| `anti_manipulation_prompt` | bool | `true` | 抵御操纵提示 |
| `admin_ids` | text | `""` | 额外管理员 ID |

### 惩罚奖励参数

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `pr_enable_momentum` | bool | `true` | 启用行为势头 |
| `pr_enable_cold_penalty` | bool | `true` | 启用冷落惩罚 |
| `pr_enable_comeback_reward` | bool | `true` | 启用回归奖励 |
| `pr_enable_milestone_reward` | bool | `true` | 启用里程碑奖励 |
| `pr_enable_betrayal_penalty` | bool | `true` | 启用背叛检测惩罚 |
| `pr_enable_apology_recovery` | bool | `true` | 启用道歉恢复 |
| `pr_cold_threshold_hours` | float | `24` | 冷落判定阈值（小时） |
| `pr_comeback_threshold_hours` | float | `48` | 回归奖励阈值（小时） |
| `pr_decay_half_life_hours` | float | `72` | 惩罚奖励半衰期（小时） |
| `pr_momentum_reward_per_level` | float | `0.24` | 每层正面势头奖励（v2.11 放缓） |
| `pr_momentum_penalty_per_level` | float | `-0.76` | 每层负面势头惩罚 |
| `pr_weight` | float | `0.6` | 惩罚奖励融合权重（0~1） |

### 纪念日与节日

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_anniversary_system` | bool | `true` | 启用纪念日/节日系统 |
| `anniv_fav_bonus` | float | `2.5` | 纪念日好感奖励 |
| `anniv_int_bonus` | float | `1.5` | 纪念日亲密奖励 |
| `festival_fav_bonus` | float | `1.8` | 节日好感奖励 |
| `festival_int_bonus` | float | `1.0` | 节日亲密奖励 |
| `anniv_inject_context` | bool | `true` | 纪念日/节日当天注入 LLM 氛围上下文 |

### 时间感知

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `timezone` | string | `Asia/Shanghai` | 时间感知时区 |
| `enable_time_perception` | bool | `true` | 注入发送时间/星期/时段 |
| `enable_holiday_perception` | bool | `true` | 节假日感知（chinese-calendar 可选） |
| `enable_lunar_perception` | bool | `true` | 农历感知（lunarcalendar 可选） |
| `holiday_country` | string | `CN` | 节假日国家/地区代码 |

### 数据统计

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_stats_tracking` | bool | `true` | 启用每日情感快照统计 |
| `stats_history_days` | int | `30` | 统计历史保留天数 |
| `trend_default_days` | int | `14` | /趋势 默认天数 |

### 关系角色与图片输出

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_relationship_roles` | bool | `true` | 启用关系角色系统（AI 扮演当前关系角色） |
| `relationship_auto_assign` | bool | `true` | 聊天内容自动判定 + 画像自动推荐关系角色 |
| `enable_image_output` | bool | `true` | 启用图片输出（未装 Pillow 自动降级） |
| `image_output_default` | bool | `false` | 新用户默认是否开启图片模式 |
| `image_output_global` | bool | `false` | 全局图片输出（所有信息命令强制图片） |

---

## ⚙️ 配置说明

所有配置均可在 AstrBot WebUI 插件管理页面可视化编辑（数值类带滑块），保存后**无需重载插件，下次对话自动生效**。

### 功能开关

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_attitude_system` | bool | `true` | 启用态度关系系统 |
| `enable_ai_text_generation` | bool | `true` | AI 自动生成态度/关系描述 |
| `enable_secondary_llm` | bool | `true` | 启用辅助 LLM 深度情感分析 |
| `enable_smart_update` | bool | `true` | 四维智能更新 |
| `show_status_default` | bool | `false` | 默认显示情感状态行 |

### 情感参数

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `default_favorability` | float | `0.0` | 初始好感度（-100~200） |
| `keyword_sensitivity` | float | `1.0` | 关键词敏感度倍率 |
| `fav_growth_rate` | float | `0.5` | 好感正向增长速率（v2.13 放缓 50%，负向惩罚不受影响） |
| `micro_change_favorability` | float | `0.21` | 无关键词时每轮好感微变化 |
| `micro_change_intimacy` | float | `0.07` | 无关键词时每轮亲密微变化（亲密度已改为按好感度派生，此值保留兼容） |

### 智能更新参数

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `force_update_interval` | int | `5` | 每隔多少轮强制触发辅助 LLM |
| `keyword_update_threshold` | float | `2.0` | 关键词累计分数触发阈值 |
| `time_update_threshold_sec` | int | `120` | 时间触发阈值（秒） |

### 辅助 LLM 参数

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `llm_provider_id` | string | `""` | 情感分析模型（留空=当前会话模型） |
| `llm_weight` | float | `0.4` | LLM 分析融合权重（0~1） |
| `llm_call_timeout_sec` | int | `15` | LLM 调用超时（秒） |
| `llm_recent_messages_count` | int | `5` | 传入 LLM 的近期消息数 |
| `attitude_max_length` | int | `25` | 态度描述最大字数 |
| `relationship_max_length` | int | `25` | 关系描述最大字数 |

### 记忆与存储

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `emotional_significance_threshold` | float | `5.0` | 长期记忆记入阈值 |
| `max_long_term_events` | int | `50` | 每用户长期记忆事件上限 |
| `auto_save_interval_sec` | int | `300` | 自动保存间隔（秒） |

### 隐私与安全

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `global_privacy_level` | int | `1` | 0=保密 1=基础 2=详细 |
| `session_based` | bool | `false` | 按会话隔离情感 |
| `anti_manipulation_prompt` | bool | `true` | 抵御操纵提示 |
| `admin_ids` | text | `""` | 额外管理员 ID |

### 惩罚奖励参数

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `pr_enable_momentum` | bool | `true` | 启用行为势头 |
| `pr_enable_cold_penalty` | bool | `true` | 启用冷落惩罚 |
| `pr_enable_comeback_reward` | bool | `true` | 启用回归奖励 |
| `pr_enable_milestone_reward` | bool | `true` | 启用里程碑奖励 |
| `pr_enable_betrayal_penalty` | bool | `true` | 启用背叛检测惩罚 |
| `pr_enable_apology_recovery` | bool | `true` | 启用道歉恢复 |
| `pr_cold_threshold_hours` | float | `24` | 冷落判定阈值（小时） |
| `pr_comeback_threshold_hours` | float | `48` | 回归奖励阈值（小时） |
| `pr_decay_half_life_hours` | float | `72` | 惩罚奖励半衰期（小时） |
| `pr_momentum_reward_per_level` | float | `0.24` | 每层正面势头奖励（v2.11 放缓） |
| `pr_momentum_penalty_per_level` | float | `-0.76` | 每层负面势头惩罚 |
| `pr_weight` | float | `0.6` | 惩罚奖励融合权重（0~1） |

### 纪念日与节日

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_anniversary_system` | bool | `true` | 启用纪念日/节日系统 |
| `anniv_fav_bonus` | float | `2.5` | 纪念日好感奖励 |
| `anniv_int_bonus` | float | `1.5` | 纪念日亲密奖励 |
| `festival_fav_bonus` | float | `1.8` | 节日好感奖励 |
| `festival_int_bonus` | float | `1.0` | 节日亲密奖励 |
| `anniv_inject_context` | bool | `true` | 纪念日/节日当天注入 LLM 氛围上下文 |

### 时间感知

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `timezone` | string | `Asia/Shanghai` | 时间感知时区 |
| `enable_time_perception` | bool | `true` | 注入发送时间/星期/时段 |
| `enable_holiday_perception` | bool | `true` | 节假日感知（chinese-calendar 可选） |
| `enable_lunar_perception` | bool | `true` | 农历感知（lunarcalendar 可选） |
| `holiday_country` | string | `CN` | 节假日国家/地区代码 |

### 数据统计

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_stats_tracking` | bool | `true` | 启用每日情感快照统计 |
| `stats_history_days` | int | `30` | 统计历史保留天数 |
| `trend_default_days` | int | `14` | /趋势 默认天数 |

### 关系角色与图片输出

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_relationship_roles` | bool | `true` | 启用关系角色系统（AI 扮演当前关系角色） |
| `relationship_auto_assign` | bool | `true` | 聊天内容自动判定 + 画像自动推荐关系角色 |
| `enable_image_output` | bool | `true` | 启用图片输出（未装 Pillow 自动降级） |
| `image_output_default` | bool | `false` | 新用户默认是否开启图片模式 |
| `image_output_global` | bool | `false` | 全局图片输出（所有信息命令强制图片） |

---

## 📂 文件结构

```
astrbot_plugin_soulsync/
├── metadata.yaml          # 插件元数据
├── _conf_schema.json      # WebUI 配置 Schema（57 项可见）
├── requirements.txt       # 依赖声明（Pillow 可选）
├── README.md              # 本文档
├── __init__.py
├── main.py                # 主入口：命令 + LLM 钩子 + 惩罚奖励 + WebUI + 自画像 + 图片输出
├── emotion_engine.py      # 8 维情感 + 好感/亲密度引擎（十二阶段，含情感标签单一来源）
├── smart_updater.py       # 四维智能更新决策器
├── memory_manager.py      # 长期记忆管理器（落盘 JSON）
├── llm_analyzer.py        # 辅助 LLM 情感分析（注入关系角色上下文）
├── penalty_reward.py      # 惩罚奖励引擎（复用关键词词表）
├── anniversary.py         # 纪念日/节日系统（农历换算 1900-2100）
├── stats_tracker.py       # 每日情感快照与趋势统计
├── relationship_roles.py  # 关系角色系统（39 角色 + 内容判定 + 锁定 + 管理员调整）
├── time_perception.py     # 时间/节假日/农历感知（仿 LLMPerception）
├── image_renderer.py      # 图片卡片/趋势图渲染（Pillow，可选）
└── pages/
    └── dashboard/
        └── index.html     # WebUI 控制台（自画像 + 配置 + 排行榜 + 节日/关系角色管理）
```

---

## 📜 版本更新记录

### v2.15（当前版本）
- **惩罚机制改为每日更新**：冷落惩罚不再由对话触发结算（原为下次对话时一次性补刀），改为**每日定时结算**（插件启动时立即补结算一次 + 每日 00:10）：
  - 按自然日缺席判定：昨天（含今天）互动过则不罚；缺席一天结算一天，连续冷落天数递增惩罚（数值不变：基础 -1.8 + 0.43/天，× 好感因子，上限 -14）
  - 每日结算独立入账：好感 clamp(-100~200)、累计惩罚统计、长期记忆记录（❄️ 每日冷落结算）、全量保存
  - `penalty_last_date` 防同日重复结算（重启不重复罚）；旧档案无互动日期不追溯，从结算之日起计
  - 回归奖励（隔 48h+ 回归）+1.5~6 仍对话触发，与每日惩罚互补；行为势头/背叛/道歉/里程碑保持对话触发不变
- **新增字段**：行为档案 `last_active_date` / `cold_days` / `penalty_last_date`（旧档案自动兼容）

### v2.14（WebUI 玻璃态整合系列）
- **毛玻璃玻璃态美化**：卡片/弹窗/统计卡 `backdrop-filter` 高斯模糊 + 半透明渐变背景；页面背景渐变色 + 双模糊光斑装饰；弹窗弹入/淡出动画（transform+opacity，GPU 合成）；hover 微上浮/侧滑、进度条 cubic-bezier 过渡、滚动条美化；`prefers-reduced-motion` 降级 + `@supports` 兼容非 WebKit 环境（低端设备自动回退不透明背景）
- **性能优化（观感不变）**：背景光斑由实时高斯模糊改为预模糊 `radial-gradient`（纯静态绘制，滚动零开销）；弹窗遮罩/玻璃 `backdrop-filter` 仅在弹窗开启时生效；弹窗动画加 `will-change:transform,opacity`；修复关闭动画被 `visibility` 立即打断的瞬隐问题（先 0.22s 淡出再隐藏）
- **美化增强**：玻璃模糊/饱和度升级（18/12px、180%/170%）+ 卡片/统计卡顶部 1px 白色高光线 + 弹窗标题栏内渐变层次；新增紫/绿光斑（多背景渐变，零 DOM）+ 38s/46s 漂移呼吸动画；统计卡错峰入场 + 卡片延迟渐入、图标 hover 弹跳旋转（仅 transform/opacity，GPU 合成）；圆角体系升级（18/16/14/20px）+ 卡片标题渐变文字（@supports 保护）
- **管理员工具增强**：弹窗顶部用户选择器（档案下拉，自动填充 ID + 预览当前好感/亲密/阶段）；移除废弃"设置亲密度"板块 → "快捷调整"（+50/+10/+5/-5/-10/-50，基于当前值钳制 -100~200）；新增"清空长期记忆"（后端 `clear_memory` action，仅清记忆保留档案）；重置增加 confirm 二次确认
- **Minimal Modern 滚动条滑块**：全站滚动容器（页面 + 弹窗内容区）4px 超细全圆角滑块，中性灰三档透明度（静止 0.4/悬停 0.7/拖动 1.0），悬停 200ms 扩至 8px + 微阴影，滚动/悬停 150ms 淡入、停止 1s 淡出，rAF 位置同步，拖拽跟随原生滚动；原生滚动条隐藏（WebKit/`scrollbar-width:none`），触屏（`pointer:coarse`）自动隐藏，`prefers-reduced-motion` 降级
- **浅色日景玻璃拟态全量重构**：统一 Token 体系（文字/深香槟金/玻璃透明度/方向性阴影/spring 缓动，全站 15 处动效统一 500ms `cubic-bezier(.16,1,.3,1)`）；真实玻璃光学（卡片/统计卡/弹窗 blur 40-60px + `saturate(180%)` + 方向性阴影含 inset 顶白高光/底暗缘 + 卡片顶部受光渐变）；深香槟金 `#A67C2F` 唯一强调色（浅色背景 WCAG AA，主按钮/分区标题/滚动条拖拽态）；移除紫粉渐变（光斑改蓝灰+香槟金克制光源、渐变文字删除）；背景 2.5% SVG feTurbulence 噪点；移除全部 bounce 弹跳缓动（hover lift/active scale(.97)/弹窗 spring 弹入）；滚动条滑块金色适配；降级保留
- **合成器级性能优化**：滚动滑块改为 CSS scroll-driven animation（`animation-timeline:scroll()`，合成线程直接跟随，滚动每帧零 JS，内容变化仅低频更新 `--mm-y`，不支持自动回退 rAF）；移除按钮层 backdrop-filter（白 65% 底浅色背景 blur 不可见，常驻重采样层仅剩卡片/统计卡玻璃核心 + 弹窗/遮罩惰性模糊 + transform-only 光斑漂移）
- **修复**：滚动滑块不同步（滑块滞后、跳动）；弹窗关闭动画瞬隐

### v2.13
- **好感正向增长放缓 50%**：新增配置 `fav_growth_rate`（默认 0.5，可调 0.1~1.0），好感正向增量（关键词、微变化、惩罚奖励正向部分）统一减半；负向惩罚不变，阶段阈值/12 阶段体系不变；WebUI 热更新即时生效
- 更新流程图中"好感 +0.21"微变化同步标注放缓生效

### v2.12
- **关系阶段 6 → 12 阶段**（0~200 复合评分更细腻）：新增「🍀 熟悉期」「💬 交心期」「🧡 心动期」「💜 默契期」「💖 依恋期」「💞 缠绵期」，新阈值 15/35/55/75/95/115/135/152/168/180/185/200；承诺期(185)/共生期(200)不变；旧档案 stage_index 加载时自动重算，无需迁移
- 关系建议文案与 WebUI 自画像建议同步对齐十二阶段；WebUI 进度条/阶段列表/最高阶段判定同步更新

### v2.11
- **惩罚奖励增长数值放缓**（只调整正面奖励，惩罚不变，保持负面威慑）：
  - 行为势头正面奖励 0.34 → 0.24/层（约 -30%，10 连击累计约 9.2 → 6.5）
  - 回归奖励 2.1/0.34/8.5 → 1.5/0.24/6.0（基础、每日加成与上限同步下调约 30%）
  - 里程碑奖励 1.4/2.1/3.6/5.8 → 1.0/1.5/2.6/4.2
  - 道歉恢复 1.4 → 1.0
  - 冷落惩罚、负面势头、背叛惩罚维持原值；`pr_momentum_reward_per_level` 默认值同步 0.24

### v2.10
- **好感度上限 100 → 200**：正向上限调高至 200（负向下限保持 -100），`/设置好感`、WebUI、进度条、趋势图 Y 轴（-100~200）、LLM 分析提示词（/200）全部同步
- **亲密度按好感度百分比派生**：`亲密度 = (好感 + 100) / 3`，-100~200 好感映射 0~100 亲密度；不再独立累积（int_delta 仅用于记忆/日志展示）；`/设置亲密` 与 WebUI 设置亲密度改为提示语
- **用户自定义关系/态度合并进关系角色系统**：`/设置关系`、`/设置态度`、AI 自动生成的态度/关系描述统一存入关系角色管理器（每用户），随当前关系角色人设合并生效（`<stage_role>` 注入、自画像、状态显示、LLM 上下文、内容自动判定均统一读取）；旧档案 attitude_text/relationship_text 首次加载自动迁移
- **情感画像计算系统优化**：复合评分 = 好感 + 情感加成（喜悦/信任/期待均值 ×15，上限 215）；负好感仍以好感值为准
- **阶段成长数值调高**：六阶段复合阈值 15/32/50/68/82/95 → 30/70/115/160/185/200（加大间距，成长更慢更耐玩）；移除失效的好感/亲密权重与亲密度增益；移除 `default_intimacy` 配置项

### v2.9 - v1.0 简史

| 版本 | 摘要 |
|------|------|
| v2.9 | WebUI 配置热同步（`_sync_runtime_config` + 惩罚奖励引擎 `update_config`）；WebUI 自画像全面优化（真实长期记忆、行为档案完整字段、关系角色解锁状态、趋势摘要、今日特别日子、原始数据折叠查看） |
| v2.8 | 全局图片模式；关系角色管理员固定（pin）与 WebUI 双向实时同步；图片渲染优化（圆角卡片/渐变背景/进度条彩色/排行榜前三色条/趋势面积填充）；排行榜 async_generator 等 Bug 修复 |
| v2.7 | 冗余清理与重构（删死代码、重复合并单一来源：关键词表/标签/命令公共函数）；负好感分段共享防阈值漂移；persona 精简单句、负角色去除软弱化描写 |
| v2.6 | 关系角色内容自动判定（长词加权）；`/切换关系` 一次性锁定 + 管理员 `admin_switch`；角色池 29 → 39；辅助 LLM 注入角色 persona 上下文 |
| v2.5 | WebUI 控制台重构（仪表盘/自画像/排行榜/12 组配置编辑/管理员工具）；图片输出；时间感知（节假日调休 + 农历干支，可选依赖自动降级） |
| v2.4 | 关系角色系统初版（19 角色、解锁条件、画像推荐、`/解锁关系` `/切换关系` `/关系角色`） |
| v2.3 | 数据趋势：每日情感快照、`/趋势` 文本图表 + WebUI 近 7 日趋势条、自动清理过期数据 |
| v2.2 | 纪念日/节日系统：农历换算（1900-2100）、认识里程碑、生日、20+ 传统节日，当天自动奖励 + LLM 氛围注入 |
| v2.1 | 惩罚奖励机制（行为势头/冷落/回归/背叛/道歉/里程碑）；负好感支持（负阶段标签与专属权重） |
| v2.0 | 辅助 LLM 深度分析（四维智能更新决策、超时保护与熔断）；长期记忆落盘（按显著性阈值记入） |
| v1.0 | 初版融合版：8 维情感模型 + 好感/亲密度双核、六阶段关系演进、过渡保护、关键词微变化、态度/关系描述生成、情感自画像 |
