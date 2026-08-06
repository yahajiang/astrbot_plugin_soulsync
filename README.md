# 心旅知音 (SoulSync) v2.19 - 融合版情感智能插件（时间感知深化）

> 本插件由 AI 编写，融合 EmotionAI 与 FavourPro 精华，实现「关键词+LLM 双通道情感分析 · 8 维情感 · 好感/亲密度 · 十二阶段演进 · 惩罚奖励 · 长期记忆 · 关系角色 · 纪念日节日 · 时间感知深化（天气×节气×月相→心情映射 · 倒计时六阶段叙事 · 时间跳跃告别/回归） · 数据趋势 · 自画像 · 图片输出 · WebUI 控制台」，v2.17 新增「个性化训练」模块（人格微调 · 知识库 · 语言风格 · 私人记忆），打造真实、渐进、可养成的 AI 情感交互系统。

---

## 📑 目录

- [✨ 功能模块总览](#overview) · [🙏 参考与致谢](#credits) · [📦 安装](#install) · [🎯 命令](#commands) · [🔄 更新流程](#flow) · [🖼️ 情感自画像](#portrait) · [🎂 纪念日与节日](#anniversary) · [⏰ 时间感知](#time) · [🌤️ 时间感知深化](#tpd) · [📈 数据趋势](#trends) · [🎭 关系角色](#roles) · [🖨️ 图片输出](#image) · [🎮 WebUI](#webui) · [🧬 十二阶段](#stages) · [⚖️ 惩罚奖励](#pr) · [🧠 智能更新](#smart) · [📜 记忆系统](#memory) · [🎯 个性化训练](#trainer) · [🌐 关系深度演进](#rde) · [⚙️ 配置说明](#config) · [📂 文件结构](#files) · [📜 版本记录](#changelog)

---

<a id="overview"></a>

## ✨ 功能模块总览（简介）

| 模块 | 简介 |
|------|------|
| 🧠 关键词+LLM 双通道情感分析 | 关键词引擎每轮必做轻量分析，辅助 LLM 按四维决策深度分析，双通道结果按权重融合 |
| 🎭 8 维情感 | 喜悦/悲伤/愤怒/恐惧/惊讶/厌恶/信任/期待，随对话演变，参与复合评分与自画像展示 |
| 💛 好感/亲密度 | 好感 -100~200 驱动全部机制，亲密度按好感派生（`(好感+100)/3`） |
| 📊 十二阶段演进 | 复合评分十二阶段（15~200）带过渡缓冲防抖动，负好感走独立路线 |
| ⚖️ 惩罚奖励 | 行为势头/冷落惩罚（每日结算）/回归奖励/背叛/道歉/里程碑，效果 72h 半衰期衰减 |
| 🧠 长期记忆 | 四层记忆体系：近期对话 → 长期记忆 → 行为档案 → 每日数据快照 |
| 🎭 关系角色 | 39 个内置角色，内容自动判定 / 用户解锁一次性锁定 / 管理员调整三机制并存 |
| 🎂 纪念日节日 | 农历换算 + 认识里程碑 + 生日 + 27+ 传统节日，当天奖励与 LLM 氛围注入 |
| 🌤️ 时间感知深化 | 天气×节气×月相→心情映射 + 倒计时六阶段叙事 + 时间跳跃（告别/回归/被动离开）+ 冷落惩罚冻结 |
| ⏰ 时间感知 | 每次请求注入时间/星期/时段/节假日/农历干支感知信息 |
| 📈 数据趋势 | 每日情感快照，`/趋势` 柱状图 + WebUI 近 7 日趋势条 |
| 🖼️ 情感自画像 | 完整档案：核心数值、阶段角色、8 维情感、行为模式、关系建议 |
| 🖨️ 图片输出 | 信息命令渲染为 Pillow 图片卡片（含趋势图），三级开关，自动降级 |
| 🎮 WebUI 控制台 | 仪表盘 / 自画像 / 125 项配置热更新 / 排行榜 / 管理员工具 |
| 🎭 个性化训练（v2.17） | 人格微调（20 参数隐式训练+稳定化）/ 知识库（6 类知识） / 语言风格（三阶段+快照）/ 私人记忆（4 类型+星标+审计） |
| 🌐 关系深度演进（v2.18） | 十二阶段叙事注入 / 关系危机系统（7 类型 14 事件、概率触发、选择处理、阶段倒退）/ 多角色关系网（跨角色好感传导、5 类社交事件、关系感知注入） |

各模块详细说明见下文对应章节。

---

<a id="credits"></a>

## 🙏 参考与致谢（二次创作声明）

本插件为对以下开源项目的 **参考与二次创作（二创）**，借鉴其核心机制思路并融合扩展：

| 参考插件 | 借鉴内容 | 原项目 |
|----------|---------|--------|
| 🧠 情感智能插件 **EmotionAI-Pro** | 8 维情感模型、好感/亲密度双核、六阶段关系演进、智能更新决策、辅助 LLM 情感分析、惩罚奖励机制 | [asakiyoshi/EmotionAI-Pro](https://github.com/asakiyoshi/EmotionAI-Pro) |
| ⏰ 环境感知增强插件 **LLMPerception** | 时间/节假日/农历/平台环境感知的注入方式 | [miaoxutao123/astrbot_plugin_LLMPerception](https://github.com/miaoxutao123/astrbot_plugin_LLMPerception) |

**声明：** 本项目为二次创作，仅用于学习交流，代码与文案由 AI 辅助编写；项目版权归原作者所有，若原作者有异议请联系删除；使用本项目产生的任何问题与原作者无关。

---

<a id="install"></a>

## 📦 安装

1. 将 `astrbot_plugin_soulsync/` 目录复制到 AstrBot 的 `data/plugins/` 下
2. 重启 AstrBot，或 WebUI 插件管理页点「重载插件」
3. 在插件配置页按需调整参数

纯 Python 实现，无强制依赖：图片输出需 `Pillow`、节假日调休需 `chinese-calendar`、农历精确换算需 `lunarcalendar`，未安装自动降级。

---

<a id="commands"></a>

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
| `/标记重要回忆 <序号>` | 把某条长期记忆标记为重要（⭐ 永不忘却，1=最近） |
| `/忘记这件事 <序号>` | 忘掉某条长期记忆（1=最近） |
| `/月度报告` / `/月报 [上月]` | 查看本月（或上月）关系月报（净好感/情绪主色调/里程碑/考验战绩） |
| `/角色回顾 [天数]` | 以角色第一人称口吻总结最近一段相处（默认 14 天） |
| `/雷达图 [天数]` | 前后两段 N 天关系六维对比（默认 7 天） |
| `/时间回溯` | 回溯关键时刻的时间线叙事（最多 5 条） |
| `/角色列表` | 查看可对话的角色（默认 + 自定义） |
| `/切换角色 <名字\|默认>` | 切换当前对话角色（好感/记忆按角色独立） |
| `/创建角色 <名字> [emoji] [性格]` | 创建并切换到自定义角色 |
| `/删除角色 <名字>` | 删除自建角色（档案保留，回到默认角色） |

**时间感知深化（v2.19）**：

| 命令 | 说明 |
|------|------|
| `/天气` | 查看当前环境感知（天气/季节/节气/月相/心情倾向），支持图片模式 |
| `/倒计时` | 查看即将到来的倒计时事件（类型/距离/得分），支持图片模式 |
| `/跳跃` | 查看时间跳跃状态；`/跳跃 三天后见` 触发跳跃，支持图片模式 |

**个性化训练（v2.17）**：

| 命令 | 说明 |
|------|------|
| `/人格微调` | 查看人格微调面板（训练阶段/稳定度/锁定状态/参数快照） |
| `/人格参数 <参数> <值>` | 直接调整单个人格参数（需先解锁，值域见面板；如 `/人格参数 grudge_coefficient 2.0`） |
| `/人格重置` | 恢复全部人格参数为默认值 |
| `/人格锁定` | 切换人格参数锁定/解锁（锁定后不可修改，恢复默认需先解锁） |
| `/知识库` | 查看知识库（按分类分组展示全部条目） |
| `/知识添加 <分类> <键> <值>` | 添加知识（分类：profile/interests/people/promises/experiences/values；promises 自动联动纪念日） |
| `/知识删除 <ID>` | 删除知识条目（ID 见 `/知识库` 列表） |
| `/风格训练` | 查看语言风格训练状态（阶段/融合度/特征统计/快照列表） |
| `/风格快照 保存 [名称]` | 保存当前风格为快照（如 `/风格快照 保存 我的风格`） |
| `/风格快照 恢复 <名称>` | 恢复历史风格快照 |
| `/风格锁定` | 切换风格锁定/解锁（锁定期停止学习） |
| `/记忆库` | 查看私人记忆库（按类型分组 + 星标标记） |
| `/记忆添加 <类型> <内容>` | 添加记忆（类型：text/image/promise/emotional） |
| `/记忆删除 <ID>` | 删除记忆（ID 见 `/记忆库` 列表） |
| `/记忆星标 <ID>` | 切换记忆星标（⭐ 星标记忆在检索中优先） |
| `/个性化导出` | 导出全部个性化数据为 JSON（persona/knowledge/style/memory） |

> 个性化训练默认关闭：需在配置中开启 `enable_personalization` 后命令才可用（未开启时命令会提示）。

**关系深度演进（v2.18）**：

| 命令 | 说明 |
|------|------|
| `/RDE阶段 [ID]` | 查看 RDE 关系阶段详情（当前阶段/称谓/叙事/危机状态/冷却）；管理员加 ID 查看他人 |
| `/危机记录 [ID]` | 查看关系危机历史（事件/选择/好感变化）与当前冷却；管理员加 ID 查看他人 |
| `/角色关系网 [ID]` | 查看多角色关系网（全部关系定义与跨角色互动统计）；管理员加 ID 查看他人 |

> RDE 系统默认关闭：需在配置中开启 `enable_rde` 后生效（未开启时命令会提示「未启用」）。

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
| `/强制跳跃 <ID> <天数>` | 强制指定用户时间跳跃（冻结冷落惩罚） |
| `/重置跳跃 [ID]` | 重置用户跳跃状态（偏移归零、解冻） |
| `/天气调试` | 查看天气获取调试信息（API/缓存/来源），支持图片模式 |

管理员身份判定：AstrBot 内置管理员 **或** 配置项 `admin_ids` 中的用户 ID。

---

<a id="flow"></a>

## 🔄 更新流程

每条消息进入 `on_llm_request` 钩子，依次执行：

```
① 关键词分析（每轮必做，轻量）→ ② 惩罚奖励分析 → ③ 智能更新决策
→ ④ 辅助 LLM 深度分析（条件触发，超时保护+熔断，失败自动降级）
→ ⑤ 应用变更（好感/亲密度/8维情感/复合评分/阶段）
→ ⑥ 个性化训练（v2.17，仅 enable_personalization 时启用）：
   人格偏移应用（joy/trust 基线）→ 每轮隐式训练（on_each_turn）→ 注入个性化上下文（人格>知识>记忆>风格，总预算 450 token 自动裁剪）
→ ⑦ 注入 LLM（时间感知 + 关系角色人设 + 情感上下文 + 个性化上下文）
```

关键词通道每轮必做；LLM 通道按四维决策触发，结果按 `llm_weight`（0.4）融合；惩罚奖励按 `pr_weight`（0.6）融合。

---

<a id="portrait"></a>

## 🖼️ 情感自画像

`/我的画像` 或 WebUI 点击用户卡片，展示完整自画像：核心数值（好感/亲密度/复合评分）、关系阶段与角色、自定义态度/关系描述、8 维情感、互动统计、行为模式（势头/连续/里程碑）、关系建议。

```
💚 好感 +32.5 ████████░░ · 💜 亲密 45.2 █████░░░ · 🧬 好感期
🎭 喜悦 62 · 悲伤 35 · 愤怒 28 · 恐惧 31 · 惊讶 45 · 厌恶 22 · 信任 71 · 期待 58
🔥 正面势头 ×4 · 🏆 里程碑 2 个 · 💡 关系建议…
```

---

<a id="anniversary"></a>

## 🎂 纪念日与节日系统

内置农历换算（1900-2100）自动识别**认识里程碑**（7/30/50/100/200/365/500/1000/1500/2000/3000 天）、认识周年、生日与 27+ 传统节日；节日当天自动好感/亲密奖励（每日去重）+ LLM 氛围注入；`/纪念日` `/节日列表` 查看倒计时，WebUI 可视化编辑。

---

<a id="time"></a>

## ⏰ 时间感知（仿 LLMPerception 实现）

每次 LLM 请求注入一行感知信息：

```
[发送时间: 2026-09-25 14:30:00 | 周五, 下午 | 法定节假日(中秋节) | 农历丙午年(马年)八月十五 | 特别日子: 中秋]
```

节假日调休（`chinese-calendar` 可选）与农历精确换算（`lunarcalendar` 可选）未装自动降级；`enable_time_perception` / `enable_holiday_perception` / `enable_lunar_perception` 分开关控制，时区 `timezone` 可配。

---

<a id="tpd"></a>

## 🌤️ 时间感知深化（TPD）

v2.19 新增时间感知深化系统，三大子系统协同运行：

### 环境感知（天气 × 节气 × 月相）

- **天气获取**：三级降级（API → 本地节气推算 → 纯时间兜底），60 分钟缓存
- **API 支持**：和风天气（hefeng）、OpenWeather，留空自动使用本地推算（无需 API Key）
- **心情映射**：10 种天气 × 6 档温度 × 4 季节 × 8 月相 → 8 维情感增量，强度可配（默认天气 0.3 / 季节 0.2 / 月相 0.1）
- **注入**：每次对话注入 `[环境] 天气: ☀️晴 · 温度: 24℃（舒适）· 季节: 春 · 节气: 清明 · 月相: 🌒蛾眉月 · 心情倾向: 喜悦↑1.5`

### 倒计时事件（T-7 到 T+7 六阶段叙事）

- **事件源**：认识周年 / 用户生日 / 自定义纪念日 / 节日（含农历）
- **优先级**：`权重 × (1/距离) × 关注度`（权重：里程碑 5 / 生日 4 / 纪念日 2）
- **叙事强度**：远期感知(T-7~T-4, 强度1) → 余韵(T-3~T-1, 强度2) → 当天(T0, 强度5) → 临近(T+1, 强度3) → 预热(T+2~T+3, 强度2) → 远期感知(T+4~T+7, 强度1)
- **防重复**：24 小时去重，每天最多提及 1 次

### 时间跳跃叙事（告别 / 回归 / 被动离开）

- **告别**：用户说"三天后见"→ 角色自然告别，约定期间冷落惩罚冻结
- **回归**：用户返回 → 重逢叙事 + 纪念日迟到庆祝
- **被动离开**：6 小时以上无对话 → 分级反应（轻微/中度/显著/强烈/极端）
- **情感漂移**：约定 +5 期待；长跳（≥14 天）按 forget_speed 自然衰减
- **虚拟时钟**：每用户 offset_days 永久偏移，"今天" = 真实日期 + 偏移

### 命令

| 命令 | 说明 |
|------|------|
| `/天气` | 查看当前环境感知（天气/季节/节气/月相/心情倾向） |
| `/倒计时` | 查看即将到来的倒计时事件 |
| `/跳跃` | 查看跳跃状态；`/跳跃 三天后见` 触发跳跃 |
| `/强制跳跃 <ID> <天数>` | 管理员：强制指定用户跳跃 |
| `/重置跳跃 [ID]` | 管理员：重置跳跃状态 |
| `/天气调试` | 管理员：天气获取调试信息 |

### WebUI

控制台新增「🌤️ 时间感知」面板，三区块：环境感知 / 倒计时事件 / 跳跃历史，含用户选择器。

### 天气 API 配置

```yaml
# 和风天气（推荐，免费额度充足）
tpd_weather_api_provider: hefeng
tpd_weather_api_key: 你的和风天气API Key
tpd_weather_api_city: 北京  # 或 LocationID

# OpenWeather
tpd_weather_api_provider: openweather
tpd_weather_api_key: 你的OpenWeather API Key
tpd_weather_api_city: Beijing

# 本地推算（默认，无需配置）
tpd_weather_api_provider: ""  # 留空即自动使用
```

**申请指南**：
- 和风天气：https://dev.qweather.com → 注册 → 创建应用 → 获取 API Key
- OpenWeather：https://openweathermap.org/api → 注册 → 获取 API Key（免费 1000 次/天）

---

<a id="trends"></a>

## 📈 情感数据趋势

每日好感/亲密度快照落盘（默认保留 30 天自动清理）；`/趋势 [天数]` 纯文本柱状图 + WebUI 近 7 日趋势条。

---

<a id="roles"></a>

## 🎭 关系角色系统

内置 **39 个关系角色**，三种机制并存：

| 机制 | 说明 |
|------|------|
| 🤖 内容自动判定 | 态度/关系文本 + 最近消息关键词匹配角色（长词加权），未命中按画像推荐 |
| 🔓 用户解锁+一次性切换 | 满足条件 `/解锁关系`；`/切换关系` **切换即锁定，不可逆** |
| 🛠️ 管理员调整 | `/设置关系角色 <ID> <角色>` 或 WebUI 强制调整，调整后解除锁定 |

- 解锁需好感、亲密、互动次数同时满足；负好感自动定级（世仇→仇人→对手→厌恶→反感→冷漠）
- 自定义态度/关系（`/设置态度` `/设置关系` AI 生成）合并进当前角色人设，注入 LLM、自画像与状态显示
- WebUI「关系角色」弹窗查看解锁状态、锁定标记并直接设置

---

<a id="image"></a>

## 🖨️ 图片输出

信息命令（`/好感度` `/我的画像` `/好感排行` `/负好感排行` `/纪念日` `/趋势` `/关系阶段` `/关系角色` `/缓存统计` `/查看好感` `/调试记忆`）均可渲染为 Pillow 图片卡片（含双线趋势图）。

- **三级开关**：总开关 `enable_image_output` → 全局（`/全局图片模式`）→ 用户级（`/图片模式`）；自动探测中文字体、emoji 剔除；未装 Pillow 自动降级纯文本；图片保留最近 30 张

---

<a id="webui"></a>

## 🎮 WebUI 控制台

独立控制台页面（AstrBot 插件详情页进入）：概览仪表盘（档案数/平均好感/平均亲密/最高阶段）、用户列表（好感排序）、用户自画像、125 项配置 12 组可视化编辑（保存即热更新）、正/负排行榜 TOP15、管理员工具（设置好感/清空记忆/重置/强制关系角色/添加节日）、系统状态。v2.17 新增「🎯 个性化训练」面板：选择用户后四标签页管理人格（20 参数滑块/下拉实时生效 + 锁定/重置）、知识库（6 分类增删）、语言风格（阶段/融合度/快照保存恢复/锁定）、私人记忆（4 类型增删/星标）。v2.18 新增「🌐 RDE 关系演进」面板：选择用户后四区块展示当前阶段叙事（含称谓/阈值/下一阶段）、危机状态与历史记录、角色关系网（全部关系边与系数）、完整阶段叙事配置列表。v2.19 新增「🌤️ 时间感知」面板：三区块展示环境感知（天气/温度/季节/节气/月相/心情倾向）、倒计时事件（类型/距离/得分）、跳跃历史（偏移/冻结/记录），含用户选择器。

**API：** `/data`(GET 档案) · `/config`(GET 配置+schema / POST 保存) · `/admin`(POST 管理员操作) · `/trainer/data`(GET 个性化数据/用户列表) · `/trainer/config`(POST 个性化配置) · `/trainer/persona`(POST 人格 set/reset/lock/unlock) · `/trainer/knowledge`(POST 知识增删) · `/trainer/memory`(POST 记忆增删/星标) · `/trainer/style`(POST 风格 lock/snapshot/restore) · `/rde/data`(GET RDE 数据/用户列表) · `/tpd/data`(GET TPD 环境/倒计时/跳跃数据)

---

<a id="stages"></a>

## 🧬 关系阶段系统（十二阶段）

复合评分 = 好感 + 情感加成（喜悦/信任/期待均值 ×15，上限 215）；十二阶段阈值 **15/35/55/75/95/115/135/152/168/180/185/200**，每阶段带过渡缓冲（2~8 分）防阶段抖动。

- 负好感路线（好感 < 0 直接以好感值为准）：冷淡(-15) → 反感(-40) → 厌恶(-70) → 敌对(-100)

---

<a id="pr"></a>

## 🎯 惩罚奖励机制

| 机制 | 触发条件 | 效果 |
|------|---------|------|
| 🔥 行为势头 | 连续正面互动 | 每层 +0.24（上限 10 层） |
| ⚡ 行为势头 | 连续负面互动 | 每层 -0.76（上限 10 层） |
| ❄️ 冷落惩罚 | 每日定时结算（启动补结算 + 每日 00:10） | 基础 -1.8 + 0.43/天 × 好感因子（上限 -14） |
| 💫 回归奖励 | 冷落 48h+ 后回归 | +1.5 + 0.24/天（上限 +6.0） |
| 💔 背叛检测 | 背叛/欺骗/骗我… | -7.3（累犯加重，冷却 1h） |
| 🕊️ 道歉恢复 | 对不起/抱歉/我错了… | +1.0（冷却 10min） |
| 🏆 里程碑 | 首次正面 / 50 / 100 / 200 次互动 | +1.0 / +1.5 / +2.6 / +4.2 |

效果带 72h 半衰期自然衰减，按 `pr_weight`（0.6）权重融合。

---

<a id="smart"></a>

## 🧠 智能更新（四维决策）

四维触发，任一满足即调用辅助 LLM 深度分析：**关键词强度**（情绪词累计分 ≥ 阈值）· **时间压力**（距上次分析 ≥ N 秒）· **强制计数器**（对话轮数 ≥ N 兜底）· **LLM 标记**（消息含 `[emotion_update]` 等）。

---

<a id="memory"></a>

## 📜 记忆系统

四层记忆：近期对话（内存 10 轮）→ 长期记忆（落盘 JSON，显著性阈值记入，跨重启保留）→ 行为档案（势头/里程碑/惩罚奖励统计）→ 每日数据快照（自动清理防膨胀）。

---

<a id="trainer"></a>

## 🎯 个性化训练（v2.17）

四大模块，开启 `enable_personalization` 后自动生效（默认关闭）：

| 模块 | 说明 |
|------|------|
| 🎭 人格微调 | 20 参数（情感倾向/行为模式/表达风格/记忆偏好），隐式训练（反馈词触发微调）+ 稳定度防抖（半衰期衰减），锁定后不可改 |
| 📚 知识库 | 6 类知识（基本信息/兴趣偏好/人物关系/私密约定/个人经历/价值观），情景捕捉自动提取 + 手动增删，`promises` 类自动联动纪念日系统 |
| 💬 语言风格 | 三阶段训练（采集→模仿→融合），特征统计（句长/正式度/直白度/混用率/语气词），快照保存/恢复，锁定停止学习 |
| 🧠 私人记忆 | 4 类型（文字/图片/约定/情感）+ 星标 ⭐，按显著性阈值自动提取，检索排序（星标>当日>关键词>重要度>少访问），审计日志 |

**四模块联动**：

- **注入优先级**：人格 > 知识 > 记忆 > 风格；总预算 `personalization_total_token_budget`（默认 450 token），超限按优先级裁剪，人格永不整块丢弃
- **记忆→知识**：importance≥8 的文字/情感记忆自动提取为「个人经历」知识
- **知识→纪念日**：`promises` 类知识新增时自动尝试解析日期写入纪念日系统
- **长期记忆→私人记忆**：v2.16 长期记忆写入高显著性事件（≥8 或 important）自动沉淀为私人记忆
- **人格→检索**：记仇系数加权负向记忆、浪漫权重加权甜蜜记忆、遗忘速度加速衰减
- **人格→情感**：joy/trust 基线每日轮次注入情感引擎（clamp 0-100）
- **辅助 LLM**：`_call_secondary_llm` 注入个性化上下文供深度分析参考

**数据存储**：`data/personalization/{user_id}/`（persona.json / knowledge.json / language_profile.json / private_memory.json / audit.json / snapshots/），每用户独立，JSON 原子写入（.tmp+.bak 防损坏），目录总容量上限 5MB 自动清理。

---

<a id="rde"></a>

## 🌐 关系深度演进（v2.18）

RDE（Relationship Depth Evolution）三大子系统，开启 `enable_rde` 后每轮对话自动生效（默认关闭，关闭时与 v2.17 行为完全一致）：

| 子系统 | 说明 |
|--------|------|
| 📜 十二阶段叙事 | 正向 s1~s12（初识→共生）+ 负向 n1~n4（冷淡→敌对），每阶段独立称谓/口吻/互动倾向/叙事注入文本，称谓随阶段从「你」自然演进到专属爱称 |
| 🌪️ 关系危机 | 7 类型 14 事件（误会/冷落/信任/成长/外部/秘密/嫉妒），概率+阶段/好感/冷落/节日修正因子触发，2~3 个选择分支处理，超时自动解决，仅危机可致阶段倒退，冷却/保护期防抖 |
| 🕸️ 多角色关系网 | 39 角色稀疏关系矩阵，跨角色好感传导（延迟一轮到账，ΔB = ΔA × 系数），5 类社交事件（吃醋/助攻/竞争/调解/误解传播），关系感知注入 LLM |

**每轮流程**（`rde/rde_orchestrator.py` `process_message`）：危机检测（超时自动解决+新触发）→ 跨角色好感传导 → 阶段跃迁叙事 → 三段上下文注入（阶段叙事/危机叙事/关系网感知）。性能实测单轮处理 **<0.01ms**（目标 <30ms）。

**子开关**：`enable_crisis_system`（危机系统）/ `enable_network`（关系网），概率与阈值参数见配置面板「RDE 关系深度演进」分组（`crisis_trigger_probability` 0.02 基础概率 · `crisis_max_probability` 0.10 上限 · `crisis_min_stage` 最低阶段 · `crisis_min_cold_penalties` 冷落门槛 · `crisis_min_rounds_secret` 秘密型轮数 · `crisis_protection_hours` 72h 保护期 · `network_transmission_delay_turns` 传导延迟 · `social_event_cooldown_rounds` 社交事件冷却 · `jealousy_gap_threshold`/`assist_min_fav`/`competition_gap_threshold` 社交事件条件）。

### 十二阶段叙事配置说明

阶段定义在 `rde/narrative/stage_definitions.py`：正向 `STAGE_DEFINITIONS`（12 条）+ 负向 `NEGATIVE_STAGE_DEFINITIONS`（4 条），字段：

| 字段 | 说明 |
|------|------|
| `stage_id` | "s1"~"s12" / "n1"~"n4" |
| `stage_name` / `relationship_state` | 阶段名与关系状态描述 |
| `threshold` | 正向阶段好感阈值（15/35/55/75/95/115/135/152/168/180/185/200） |
| `address_config` | 称谓配置 `{"base": "你"}`，跨阶段演进：你 → 你啊/傻瓜 → 昵称 → 宝贝 → 亲爱的 → 我的宝贝 → 爱人 → 唯一的你 |
| `dialogue_style` / `interaction_features` | LLM 注入的口吻与互动倾向指令 |
| `transition_trigger` | 跃迁叙事（升段/退行文案，见 `rde/narrative/transition_handler.py`） |

负向称谓由 `rde/narrative/address_system.py` 配置（n1「你」→ n2 省略 → n3「那个人」→ n4 不愿提及）。自定义叙事：编辑对应条目后重启插件生效。

### 危机事件自定义指南

事件池在 `rde/crisis/crisis_definitions.py` 的 `CRISIS_EVENTS` 列表（7 类型 × 2 = 14 个内置事件），追加条目即可添加自定义危机：

```python
_crisis("my_crisis", "trust", "你想自定义的事件", "s6", 130.0,
        "叙事文本 {char_name} 对你说……{user_name}，{friend_name} 也在场",
        [Choice("a", "选项A文字", +8.0, 0, emotion_deltas={"joy": 10},
                memory_text="……", response_text="角色回复……"),
         Choice("b", "选项B文字", -15.0, -1, memory_text="……", response_text="……")],
        cooldown_rounds=200, duration_rounds=3,
        extra_conditions={"cold_penalties": 2},      # 可选附加条件
        extra_probability={"special_date": 0.01})     # 可选附加概率
```

| 字段 | 说明 |
|------|------|
| `type` | 七类之一：misunderstanding/cold/trust/growth/external/secret/jealousy |
| `stage_requirement` / `favorability_requirement` | 最低阶段与好感下限 |
| `narrative` | 事件叙事文本，占位符 `{char_name}`/`{user_name}`/`{friend_name}` 注入时替换 |
| `choices` | 2~3 个 `Choice`（`favorability_delta` 好感变化、`stage_delta` 阶段变化 0/±1、`emotion_deltas` 8 维情感、`memory_text` 写入长期记忆、`response_text` 角色回复、`unlocks_stage_context` 解锁叙事） |
| `cooldown_rounds` / `duration_rounds` | 触发冷却轮数 / 持续轮数（期限内未选择自动解决） |
| `auto_resolve` / `auto_resolve_effect` | 超时是否自动解决及效果 |
| `extra_conditions` / `extra_probability` | 附加触发条件（如冷落次数）与附加概率（如节日） |

### 角色关系矩阵配置指南

默认网在 `rde/network/relation_definitions.py`（39 角色稀疏矩阵）。自定义关系写在角色卡 `relations` 字段（数据文件 `data/characters.json`，结构 `{uid: {cid: {relations: {...}}}}`）：

```json
"relations": {
  "小雪": {"type": "bestie", "cross_coefficient": 0.1, "description": "从小一起长大的好友"},
  "阿澈": {"type": "rival_love", "cross_coefficient": -0.05}
}
```

| 字段 | 说明 |
|------|------|
| 键名 | 目标角色名（source 缺省=用户，即「用户 ↔ 角色」边） |
| `type` | 关系类型：bestie 挚友 / partner 恋人 / senior_junior 前辈后辈 / rival_love 情敌 / opponent 对手 / cold 冷漠 / sworn_enemy 死敌 / stranger 陌生人 / none 无关联 |
| `cross_coefficient` | 传导系数（可正可负），该角色好感变化 ΔA 传导到对方 ΔB = ΔA × 系数，延迟 `network_transmission_delay_turns` 轮到账 |
| `description` | 关系描述（感知注入用） |

自定义关系与默认网**叠加**生效；无 `relations` 字段的角色卡自动使用默认网。

---

<a id="config"></a>

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

### 时间感知深化（TPD，v2.19）

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `tpd_enabled` | bool | `false` | TPD 总开关 |
| `tpd_weather_enabled` | bool | `true` | 天气联动开关 |
| `tpd_weather_api_provider` | string | `""` | API 提供商（hefeng/openweather/空=本地推算） |
| `tpd_weather_api_key` | string | `""` | API Key |
| `tpd_weather_api_city` | string | `""` | 查询城市 |
| `tpd_weather_cache_minutes` | int | `60` | 缓存时间（分钟） |
| `tpd_weather_mood_strength` | float | `0.3` | 天气心情影响强度 |
| `tpd_season_mood_strength` | float | `0.2` | 季节心情影响强度 |
| `tpd_moonphase_enabled` | bool | `true` | 月相影响开关 |
| `tpd_moonphase_mood_strength` | float | `0.1` | 月相心情影响强度 |
| `tpd_countdown_enabled` | bool | `true` | 倒计时事件开关 |
| `tpd_countdown_mention_start_days` | int | `7` | 倒计时开始提及天数 |
| `tpd_countdown_mention_freq_days` | int | `1` | 同一事件提及频率（天） |
| `tpd_countdown_max_per_turn` | int | `1` | 每轮最多提及倒计时数 |
| `tpd_countdown_auto_greet` | bool | `true` | T-0 当天自动问候 |
| `tpd_skip_enabled` | bool | `true` | 时间跳跃开关 |
| `tpd_skip_max_days` | int | `365` | 单次最大跳跃天数 |
| `tpd_skip_freeze_penalty` | bool | `true` | 跳跃期间冻结冷落惩罚 |
| `tpd_skip_emotion_drift` | bool | `true` | 跳跃期间情感漂移 |
| `tpd_passive_gap_threshold_hours` | int | `6` | 被动离开检测阈值（小时） |
| `tpd_return_narrative_enabled` | bool | `true` | 回归叙事开关 |

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

### 个性化训练（v2.17）

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_personalization` | bool | `false` | 总开关：启用个性化训练（注入/训练/命令/WebUI 面板全部受此门控） |
| `personalization_total_token_budget` | int | `450` | 个性化上下文总 token 预算，超限按优先级裁剪（人格>知识>记忆>风格） |
| `persona_implicit_training` | bool | `true` | 人格隐式训练（反馈词触发微调） |
| `persona_explicit_panel` | bool | `true` | 人格显式面板（命令/WebUI 手动调整） |
| `persona_stability_enabled` | bool | `true` | 人格稳定度防抖（防短时大幅漂移） |
| `knowledge_enabled` | bool | `true` | 知识库模块开关 |
| `knowledge_auto_capture` | bool | `true` | 知识情景捕捉（对话中自动提取知识） |
| `knowledge_max_tokens_per_turn` | int | `150` | 知识注入每轮 token 上限 |
| `style_training_enabled` | bool | `true` | 语言风格训练开关 |
| `style_collection_turns` | int | `100` | 风格采集期所需对话轮数 |
| `style_adoption_turns` | int | `300` | 风格模仿期所需对话轮数（之后进入融合期） |
| `private_memory_enabled` | bool | `true` | 私人记忆模块开关 |
| `private_memory_proactive_chance` | float | `0.08` | 私人记忆主动回忆触发概率（每轮） |
| `private_memory_token_budget` | int | `120` | 私人记忆注入每轮 token 上限 |

---

<a id="files"></a>

## 📂 文件结构

```
astrbot_plugin_soulsync/
├── metadata.yaml          # 插件元数据
├── _conf_schema.json      # WebUI 配置 Schema（125 项可见）
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
├── trainer/               # 个性化训练模块（v2.17）
│   ├── trainer_orchestrator.py  # 调度器：注入组装 + token 预算裁剪 + 四模块联动门面
│   ├── trainer_storage.py       # 统一存储（JSON 原子写入 + 容量控制）
│   ├── trainer_types.py         # 数据模型（PersonaParams/KnowledgeBase/StyleState/PrivateMemory）
│   ├── _conf_schema.json        # 个性化配置 Schema（14 项）
│   ├── persona/                 # 人格微调（20 参数 + 隐式训练 + 稳定度 + 注入）
│   ├── knowledge/               # 知识库（6 类 + 情景捕捉 + 注入 + 导出）
│   ├── style/                   # 语言风格（三阶段训练 + 快照 + 注入）
│   └── memory/                  # 私人记忆（增删改查 + 检索 + 审计 + 导出）
└── pages/
    └── dashboard/
        └── index.html     # WebUI 控制台（自画像 + 配置 + 排行榜 + 节日/关系角色管理 + 个性化训练面板）
```

---

<a id="changelog"></a>

## 📜 版本更新记录

> 完整版本记录见 [changelog.md](changelog.md)

| 版本 | 摘要 |
|------|------|
| **v2.17**（当前） | 个性化训练模块：人格微调（20 参数隐式训练+稳定化+锁定）、知识库（6 类知识+情景捕捉）、语言风格（三阶段训练+快照）、私人记忆（4 类型+星标+审计）· 四模块联动（token 预算裁剪/记忆↔知识↔纪念日/长期记忆沉淀/人格加权检索/joy·trust 基线注入辅助 LLM）· 15 个新命令 · WebUI 个性化训练面板（4 标签页+5 组 trainer API） |
| **v2.16** | 情感深化 14 功能点：记忆情感锚点/遗忘曲线/记忆编辑 · 复合情绪/情绪传染/阶段风格 · 关系危机事件 · 季节天气/倒计时/月度报告/角色独白/对比雷达图/时间跳跃叙事 · 多角色并行关系（角色卡） |
| **v2.15** | 惩罚机制改为每日更新：冷落惩罚每日定时结算（启动补结算 + 每日 00:10，按自然日缺席递增），对话不再触发冷落 |
| **v2.14** | WebUI 玻璃态整合系列：毛玻璃美化 → 性能优化 → 美化增强 → 管理员工具 → Minimal Modern 滚动条滑块 → 浅色日景玻璃拟态重构 → 合成器级性能优化 |
| **v2.13** | 好感正向增长放缓 50%（`fav_growth_rate` 默认 0.5） |
| **v2.12** | 关系阶段 6 → 12 阶段（复合阈值 15~200） |
| **v2.11** | 惩罚奖励正面数值放缓约 30%（惩罚不变） |
| **v2.10** | 好感上限 100→200；亲密度按好感派生；自定义关系/态度并入关系角色系统；六阶段阈值调高 |
| **v2.9 ~ v1.0** | WebUI 配置热同步 / 关系角色系统 / 数据趋势 / 纪念日节日 / 惩罚奖励机制 / 辅助 LLM 深度分析 / 初版融合（简史见 changelog.md） |
