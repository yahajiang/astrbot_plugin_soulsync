# 心旅知音 (SoulSync) - 融合版情感智能插件

> 融合 EmotionAI 与 FavourPro 精华的情感智能插件：关键词+LLM 双通道情感分析 · 8 维情感 · 好感/亲密度 · 十二阶段演进 · 惩罚奖励 · 四层记忆 · 关系角色 · 纪念日节日 · 时间感知深化 · 个性化训练（人格/知识/风格/记忆）· RDE 关系深度演进 · 图片输出 · WebUI 控制台配置板块 16 模块组 141 项全量可视化。

---

## 📑 目录

- [功能模块总览](#overview) · [安装](#install) · [命令](#commands) · [更新流程](#flow) · [核心机制](#core) · [个性化训练](#trainer) · [RDE 关系深度演进](#rde) · [WebUI](#webui) · [配置说明](#config) · [文件结构](#files) · [版本记录](#changelog) · [参考与致谢](#credits)

---

<a id="overview"></a>

## ✨ 功能模块总览

| 模块 | 简介 |
|------|------|
| 🧠 双通道情感分析 | 关键词引擎每轮必做轻量分析，辅助 LLM 按四维决策深度分析，双通道按权重融合 |
| 🎭 8 维情感 + 好感/亲密 | 喜悦/悲伤/愤怒/恐惧/惊讶/厌恶/信任/期待；好感 -100~200 驱动全部机制，亲密按好感派生 |
| 📊 十二阶段演进 | 复合评分十二阶段（15~200）带过渡缓冲防抖动，负好感走独立路线 |
| ⚖️ 惩罚奖励 | 行为势头/冷落惩罚（每日结算）/回归奖励/背叛/道歉/里程碑，效果 72h 半衰期衰减 |
| 🧠 四层记忆 | 近期对话 → 长期记忆 → 行为档案 → 每日数据快照 |
| 🎭 关系角色 | 39 个内置角色：内容自动判定 / 用户解锁一次性锁定 / 管理员调整 |
| 🎂 纪念日节日 | 农历换算 + 认识里程碑 + 生日 + 27+ 传统节日，当天奖励与氛围注入 |
| ⏰ 时间感知深化（TPD） | 天气×节气×月相→心情映射 + 倒计时六阶段叙事 + 时间跳跃（告别/回归/被动离开） |
| 🖼️ 图片输出 | 信息命令渲染 Pillow 图片卡片（含趋势图），三级开关，未装自动降级 |
| 🎮 WebUI 控制台 | 仪表盘 / 自画像 / 141 项配置 · 16 模块组热更新 / 排行榜 / 管理员工具 / 各模块面板 |
| 🎯 个性化训练 | 人格微调（20 参数+护栏）/ 知识库（6 类）/ 语言风格（三阶段+快照）/ 私人记忆（4 类型） |
| 🌐 RDE 关系深度演进 | 十二阶段叙事注入 / 关系危机系统（7 类型 14 事件）/ 多角色关系网 |
| 🔌 v2.20 轻量化重构 | 命令路由（10 父命令+`/admin`）· 事件总线 EventBus · 人格护栏（自动锁定/回滚/极端解锁）· 意图识别静默命令 · 前后置钩子 HookBus |

---

<a id="install"></a>

## 📦 安装

1. 将 `astrbot_plugin_soulsync/` 目录复制到 AstrBot 的 `data/plugins/` 下
2. 重启 AstrBot，或 WebUI 插件管理页点「重载插件」
3. 在插件配置页按需调整参数

纯 Python 实现，无强制依赖：图片输出需 `Pillow`、节假日调休需 `chinese-calendar`、农历精确换算需 `lunarcalendar`，未安装自动降级。

---

<a id="commands"></a>

## 🎯 命令（v2.20 父命令体系）

> 💡 **95% 场景无需输入命令**：查询类自然语言（如"我们之间现在算什么关系？""你还记得我们第一次见面吗"）由意图识别自动输出卡片并阻断聊天，无需输入 `/心助`。

### 用户命令（👤 = 全体用户 / 🛡️ = 仅管理员）

| 权限 | 父命令 | 子命令 | 说明 |
|------|------|------|------|
| 👤 | `/心声` | `好感` | 核心情感数值（好感/亲密度/阶段/行为势头） |
| 👤 | | `阶段` | 当前关系阶段详情 |
| 👤 | | `画像` | 个人情感自画像（8 维情感 + 行为模式 + 里程碑） |
| 👤 | | `系统` | 插件数据规模（缓存统计） |
| 👤 | `/回忆` | `趋势 [天数]` | 最近 N 天（默认 14）情感数据趋势 |
| 👤 | | `月报 [上月]` | 关系月报（净好感/情绪主色调/里程碑） |
| 👤 | | `报告 [天数]` / `独白` | 角色第一人称口吻回顾（默认 14 天） |
| 👤 | | `对比 [天数]` | 前后两段 N 天关系六维雷达对比（默认 7 天） |
| 👤 | | `时间线 [ID]` | RDE 阶段时间线叙事（管理员可加 ID 查看他人） |
| 👤 | | `危机 [ID]` | RDE 危机历史与冷却（管理员可加 ID 查看他人） |
| 👤 | | `关系网 [ID]` | 多角色关系网（管理员可加 ID 查看他人） |
| 👤 | `/纪念` | `查看` | 纪念日列表与倒计时 |
| 👤 | | `添加 <MM-DD> <名称>` | 添加自定义纪念日 |
| 👤 | | `删除 <名称>` | 删除自定义纪念日 |
| 👤 | | `生日 <MM-DD>` | 设置生日 |
| 👤 | | `节日` | 全部节日列表与倒计时 |
| 🛡️ | | `节日添加/节日删除` | **仅管理员**；添加/删除节日 |
| 👤 | `/角色` | `列表` / `查看` | 角色列表（默认 + 自定义） |
| 👤 | | `创建 <名字> [emoji] [性格]` | 创建并切换到自定义角色 |
| 👤 | | `切换 <名字\|默认>` | 切换对话角色（好感/记忆按角色独立） |
| 👤 | | `删除 <名字>` | 删除自建角色（档案保留） |
| 👤 | | `关系 [角色]` | 关系角色列表与解锁进度 |
| 👤 | | `解锁 <角色>` | 解锁系统内置关系角色 |
| 👤 | | `关系切换 <角色>` | 切换关系角色（**一次即锁定，不可逆**） |
| 👤 | `/人格` | `查看` | 人格面板（20 参数/稳定度/锁定状态），全员只读 |
| 🛡️ | | `设置 <参数> <值>` | **仅管理员**；操作后 2h 自动化微调暂停 |
| 🛡️ | | `重置` | **仅管理员**；恢复全部默认并解除锁定 |
| 🛡️ | | `锁定` | **仅管理员**；锁定/解锁人格参数 |
| 👤 | `/知识` | `查看` | 知识库（按分类分组） |
| 👤 | | `添加 [分类] <内容>` | 添加知识（profile/interests/people/promises/experiences/values） |
| 👤 | | `删除 <ID>` | 删除知识条目 |
| 👤 | `/风格` | `状态` | 语言风格训练状态（阶段/融合度/快照列表） |
| 👤 | | `保存 [名称]` / `恢复 <名称>` | 风格快照保存/恢复 |
| 👤 | | `锁定` | 锁定/解锁风格（锁定期停止学习） |
| 👤 | `/记忆` | `查看` | 私人记忆库（按类型分组 + 星标） |
| 👤 | | `添加 <类型> <内容>` | 添加记忆（text/image/promise/emotional） |
| 👤 | | `删除 <ID>` / `星标 <ID>` | 删除记忆 / 切换星标（⭐ 检索优先） |
| 👤 | | `重要 <序号>` / `忘记 <序号>` | 长期记忆标记重要 / 忘掉（1=最近） |
| 👤 | `/天象` | `天气` | 当前环境感知（天气/季节/节气/月相/心情倾向） |
| 👤 | | `倒计时` | 即将到来的倒计时事件（类型/距离/得分） |
| 👤 | | `跳跃` | 时间跳跃状态；`/天象 跳跃 三天后见` 触发跳跃 |
| 👤 | | `回溯` | 回溯关键时刻的时间线叙事（最多 5 条） |
| 👤 | `/排行` | `好感 [n]` / `负好感 [n]` | TOP n 好感 / BOTTOM n 负好感排行榜（默认 10，最多 20） |
| 👤 | `/图片模式` | — | 切换本人指令输出为图片卡片（需 Pillow） |
| 👤 | `/设置` | — | 切换是否在对话后自动显示情感状态行 |
| 👤 | `/心助` | — | 命令总览 |

> 个性化训练默认关闭：需开启 `enable_personalization` 后 `/人格 /知识 /风格 /记忆` 才可用。RDE 相关子命令需开启 `enable_rde`。

### 管理员命令（🛡️ `/心管` 集中入口，仅管理员）

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

管理员身份判定：AstrBot 内置管理员 **或** 配置项 `admin_ids` 中的用户 ID。`/人格 设置 /重置 /锁定` 亦仅管理员可用。

---

<a id="flow"></a>

## 🔄 更新流程

每条消息进入 `on_llm_request` 钩子，依次执行：

```
⓪ 前置钩子（v2.20）：意图识别静默命令（查询类消息直接出卡片并阻断，不走 LLM）
① 关键词分析（每轮必做，轻量）→ ② 惩罚奖励分析 → ③ 智能更新决策
→ ④ 辅助 LLM 深度分析（条件触发，超时保护+熔断，失败自动降级）
→ ⑤ 应用变更（好感/亲密度/8维情感/复合评分/阶段）
→ ⑥ 个性化训练（仅 enable_personalization 时启用）：
   人格偏移应用（joy/trust 基线）→ 每轮隐式训练（on_each_turn，人格护栏守护）→ 注入个性化上下文（人格>知识>记忆>风格，总预算 450 token 自动裁剪）
→ ⑦ 注入 LLM（时间感知 + 关系角色人设 + 情感上下文 + 个性化上下文）
→ ⑧ 后置钩子（v2.20）：prompt 泄漏清理等回复修饰
```

关键词通道每轮必做；LLM 通道按四维决策触发，结果按 `llm_weight`（0.4）融合；惩罚奖励按 `pr_weight`（0.6）融合。

---

<a id="core"></a>

## 🧬 核心机制

### 关系阶段（十二阶段）

复合评分 = 好感 + 情感加成（喜悦/信任/期待均值 ×15，上限 215）；十二阶段阈值 **15/35/55/75/95/115/135/152/168/180/185/200**，每阶段带过渡缓冲（2~8 分）防阶段抖动。负好感独立路线：冷淡(-15) → 反感(-40) → 厌恶(-70) → 敌对(-100)。

### 惩罚奖励

| 机制 | 触发条件 | 效果 |
|------|---------|------|
| 🔥/⚡ 行为势头 | 连续正/负面互动 | 每层 +0.24 / -0.76（上限 10 层） |
| ❄️ 冷落惩罚 | 每日定时结算（启动补结算 + 每日 00:10） | 基础 -1.8 + 0.43/天 × 好感因子（上限 -14） |
| 💫 回归奖励 | 冷落 48h+ 后回归 | +1.5 + 0.24/天（上限 +6.0） |
| 💔 背叛检测 | 背叛/欺骗/骗我… | -7.3（累犯加重，冷却 1h） |
| 🕊️ 道歉恢复 | 对不起/抱歉/我错了… | +1.0（冷却 10min） |
| 🏆 里程碑 | 首次正面 / 50 / 100 / 200 次互动 | +1.0 / +1.5 / +2.6 / +4.2 |

效果带 72h 半衰期自然衰减，按 `pr_weight`（0.6）权重融合。

### 记忆系统（四层）

近期对话（内存 10 轮）→ 长期记忆（落盘 JSON，显著性阈值记入，跨重启保留）→ 行为档案（势头/里程碑/惩罚奖励统计）→ 每日数据快照（自动清理防膨胀）。

### 智能更新（四维决策）

**关键词强度**（情绪词累计分 ≥ 阈值）· **时间压力**（距上次分析 ≥ N 秒）· **强制计数器**（对话轮数 ≥ N 兜底）· **LLM 标记**（消息含 `[emotion_update]` 等），任一满足即调用辅助 LLM 深度分析。

### 纪念日与节日

内置农历换算（1900-2100）自动识别**认识里程碑**（7/30/50/100/200/365/500/1000/1500/2000/3000 天）、认识周年、生日与 27+ 传统节日；节日当天自动好感/亲密奖励（每日去重）+ LLM 氛围注入；`/纪念` 查看倒计时，WebUI 可视化编辑。

### 情感自画像

`/心声 画像` 或 WebUI 点击用户卡片，展示完整自画像：核心数值（好感/亲密度/复合评分）、关系阶段与角色、自定义态度/关系描述、8 维情感、互动统计、行为模式（势头/连续/里程碑）、关系建议。

### 关系角色系统

内置 **39 个关系角色**，三种机制并存：

| 机制 | 说明 |
|------|------|
| 🤖 内容自动判定 | 态度/关系文本 + 最近消息关键词匹配角色（长词加权），未命中按画像推荐 |
| 🔓 用户解锁+一次性切换 | 满足条件 `/角色 解锁`；`/角色 关系切换` **切换即锁定，不可逆** |
| 🛠️ 管理员调整 | `/心管 关系角色 <ID> <角色>` 或 WebUI 强制调整，调整后解除锁定 |

- 解锁需好感、亲密、互动次数同时满足；负好感自动定级（世仇→仇人→对手→厌恶→反感→冷漠）
- 自定义态度/关系（`/心管 态度/关系`）合并进当前角色人设，注入 LLM、自画像与状态显示

### 时间感知（仿 LLMPerception）

每次 LLM 请求注入一行感知信息（时间/星期/时段/节假日/农历干支）。节假日调休（`chinese-calendar` 可选）与农历精确换算（`lunarcalendar` 可选）未装自动降级；`enable_time_perception` / `enable_holiday_perception` / `enable_lunar_perception` 分开关控制，时区 `timezone` 可配。

### 时间感知深化（TPD，v2.19）

三大子系统，`tpd_enabled` 开启：

- **环境感知**：三级降级天气获取（API → 本地节气推算 → 纯时间兜底，60 分钟缓存）；和风/OpenWeather 可选，留空自动本地推算；10 天气 × 6 温度 × 4 季节 × 8 月相 → 8 维心情映射
- **倒计时事件**：认识周年/生日/纪念日/节日（含农历），T-7~T+7 六阶段叙事（当天 T0 强度最高），24h 去重每天最多提及 1 次
- **时间跳跃**：`/天象 跳跃 三天后见` 告别 → 约定期间冷落惩罚冻结 → 回归重逢叙事 + 迟到庆祝；被动离开 6h+ 分级反应；每用户虚拟时钟（offset_days 永久偏移）

天气 API 配置：

```yaml
tpd_weather_api_provider: hefeng        # hefeng / openweather / 留空=本地推算
tpd_weather_api_key: 你的API Key
tpd_weather_api_city: 北京
```

申请：和风天气 https://dev.qweather.com · OpenWeather https://openweathermap.org/api

### 数据趋势

每日好感/亲密度快照落盘（默认保留 30 天自动清理）；`/回忆 趋势 [天数]` 文本柱状图 + WebUI 近 7 日趋势条。

### 图片输出

信息命令（`/心声` `/回忆 趋势` `/排行` `/纪念` `/角色 关系` 等）均可渲染 Pillow 图片卡片（含双线趋势图）。三级开关：总开关 `enable_image_output` → 全局（`/心管 图片模式`）→ 用户级（`/图片模式`）；自动探测中文字体、emoji 剔除；未装 Pillow 自动降级纯文本；图片保留最近 30 张。

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

**四模块联动**：注入优先级 人格 > 知识 > 记忆 > 风格（总预算 450 token，超限按优先级裁剪，人格永不整块丢弃）；记忆→知识（importance≥8 自动沉淀）；知识→纪念日（promises 解析日期）；人格→检索（记仇/浪漫/遗忘参数加权）；人格→情感（joy/trust 基线注入）；辅助 LLM 参考个性化上下文。

**v2.20 人格护栏（PersonaGuard）**：连续 50 轮无显著波动且稳定度 ≥70% → 自动锁定（防噪声干扰）；24h 内 ≥3 次剧变 → 回滚至最近稳定快照；背叛/连续冷落 ≥3 天 → 自动解锁（允许角色重新适应）；`/人格 设置` 后管理员 2h 临时锁定，期间自动化微调暂停。

**数据存储**：`data/personalization/{user_id}/`（persona.json / knowledge.json / language_profile.json / private_memory.json / audit.json / snapshots/），每用户独立，JSON 原子写入（.tmp+.bak 防损坏），目录总容量上限 5MB 自动清理。

---

<a id="rde"></a>

## 🌐 关系深度演进（RDE，v2.18）

开启 `enable_rde` 后每轮对话自动生效（默认关闭，关闭时行为与 v2.17 完全一致）：

| 子系统 | 说明 |
|--------|------|
| 📜 十二阶段叙事 | 正向 s1~s12（初识→共生）+ 负向 n1~n4（冷淡→敌对），每阶段独立称谓/口吻/互动倾向/叙事注入，称谓随阶段从「你」演进到专属爱称 |
| 🌪️ 关系危机 | 7 类型 14 事件（误会/冷落/信任/成长/外部/秘密/嫉妒），概率+阶段/好感/冷落/节日修正因子触发，2~3 个选择分支处理，超时自动解决，仅危机可致阶段倒退，冷却/保护期防抖 |
| 🕸️ 多角色关系网 | 39 角色稀疏关系矩阵，跨角色好感传导（延迟一轮到账，ΔB = ΔA × 系数），5 类社交事件（吃醋/助攻/竞争/调解/误解传播），关系感知注入 LLM |

**每轮流程**（`rde/rde_orchestrator.py`）：危机检测（超时自动解决+新触发）→ 跨角色好感传导 → 阶段跃迁叙事 → 三段上下文注入。性能实测单轮 **<0.01ms**。

**v2.21 叙事频控**：阶段叙事（含称谓/禁忌等行为指导）由每轮注入改为按 `rde_stage_inject_every_n`（默认 3 轮）间隔注入，阶段跃迁轮强制注入；阶段跃迁时强制重新注入静态层（人设/知识）；危机叙事与关系感知不受间隔限制。

**子开关**：`enable_crisis_system`（危机系统）/ `enable_network`（关系网）。阶段定义见 `rde/narrative/stage_definitions.py`（`STAGE_DEFINITIONS` + `NEGATIVE_STAGE_DEFINITIONS`）；危机事件池见 `rde/crisis/crisis_definitions.py` 的 `CRISIS_EVENTS`（追加条目即可自定义）；默认关系网见 `rde/network/relation_definitions.py`，自定义关系写在角色卡 `relations` 字段（`type`：bestie/partner/senior_junior/rival_love/opponent/cold/sworn_enemy/stranger；`cross_coefficient` 传导系数；`description` 感知描述），与默认网叠加生效。

---

<a id="webui"></a>

## 🎮 WebUI 控制台

AstrBot 插件详情页进入：概览仪表盘（档案数/平均好感/平均亲密/最高阶段）、用户列表（好感排序）、用户自画像、141 项配置 · 16 个模块组分组可视化编辑（保存即热更新）、正/负排行榜 TOP15、管理员工具、系统状态。

各模块面板：**🎯 个性化训练**（四标签页：人格 20 参数实时生效/锁定/重置 · 知识库 · 语言风格 · 私人记忆）· **🌐 RDE 关系演进**（当前阶段叙事/危机状态与历史/角色关系网/阶段配置）· **🌤️ 时间感知**（环境感知/倒计时/跳跃历史）。

**API：** `/data` · `/config`(GET/POST) · `/admin` · `/trainer/data` `/trainer/config` `/trainer/persona` `/trainer/knowledge` `/trainer/memory` `/trainer/style` · `/rde/data` · `/tpd/data`

---

<a id="config"></a>

## ⚙️ 配置说明

全部 141 项配置均在 WebUI 插件管理页可视化编辑（数值类带滑块），保存后**无需重载插件，下次对话自动生效**。16 个模块组：

| 分组 | 关键配置 |
|------|---------|
| ⚡ 功能开关 | `enable_attitude_system` `enable_ai_text_generation` `enable_secondary_llm` `enable_smart_update` `show_status_default` `enable_multi_role` `enable_intent_router` `enable_hooks` `enable_stage_styles` `enable_s12_forced_address` |
| 🌐 RDE 深度演进 | `enable_rde` `rde_stage_inject_every_n`（3）`enable_crisis_system` `enable_network` `crisis_trigger_probability`（0.02）`crisis_max_probability`（0.10）`crisis_min_stage` `crisis_min_cold_penalties` `crisis_min_rounds_secret` `crisis_protection_hours` `network_transmission_delay_turns` `social_event_cooldown_rounds` `jealousy_gap_threshold` `assist_min_fav` `competition_gap_threshold` |
| 💝 情感参数 | `default_favorability` `keyword_sensitivity` `fav_growth_rate`（0.5 放缓）`micro_change_favorability` `micro_change_intimacy` `enable_emotion_contagion` `tension_*`（张力积累/释放/阈值）`eruption_fav_penalty` |
| 🧠 智能更新 | `force_update_interval` `keyword_update_threshold` `time_update_threshold_sec` |
| 🤖 辅助 LLM | `llm_provider_id` `llm_weight`（0.4）`llm_call_timeout_sec` `llm_recent_messages_count` |
| 💾 记忆 | `emotional_significance_threshold` `max_long_term_events` `auto_save_interval_sec` `enable_memory_recall` `memory_half_life_days` `memory_recall_bonus` |
| 🧬 个性化训练 | `enable_personalization` `personalization_static_every_n` `persona_implicit_training` `persona_explicit_panel` `persona_stability_enabled` `knowledge_enabled` `style_training_enabled` `private_memory_enabled` `personalization_total_token_budget`（450）等 |
| 🔒 隐私 | `global_privacy_level` `session_based` `anti_manipulation_prompt` `admin_ids` |
| 🎯 惩罚奖励 | `pr_enable_*`（6 开关）`pr_cold_threshold_hours` `pr_comeback_threshold_hours` `pr_decay_half_life_hours` `pr_momentum_reward_per_level` `pr_weight`（0.6）`crisis_*`（事件开关/阈值/概率/冷却/奖励惩罚） |
| 📅 纪念日/节日 | `enable_anniversary_system` `anniv_fav_bonus` `anniv_int_bonus` `festival_fav_bonus` `festival_int_bonus` `anniv_inject_context` `enable_countdown_events` `report_*`（月报/角色报告） |
| ⏰ 时间感知 | `timezone` `enable_time_perception` `enable_holiday_perception` `enable_lunar_perception` `enable_weather_perception` `holiday_country` `time_jump_*` |
| 🌦️ TPD 环境深化 | `tpd_enabled` `tpd_env_inject_every_n` `tpd_weather_*`（provider/key/city/cache/mood_strength）`tpd_season_mood_strength` `tpd_moonphase_*` `tpd_aqi_enabled` |
| ⏳ TPD 倒计时/跳跃 | `tpd_countdown_*`（开关/提及窗口/频率/去重/自动问候）`tpd_skip_*`（跳跃上限/冻结惩罚/情感漂移）`tpd_passive_gap_threshold_hours` `tpd_return_narrative_enabled` |
| 📈 数据统计 | `enable_stats_tracking` `stats_history_days` `trend_default_days` |
| 🎭 关系角色 | `enable_relationship_roles` `relationship_auto_assign` |
| 🖼️ 图片输出 | `enable_image_output` `image_output_default` `image_output_global` |

---

<a id="files"></a>

## 📂 文件结构

```
astrbot_plugin_soulsync/
├── metadata.yaml / _conf_schema.json / requirements.txt / README.md
├── main.py                # 主入口：命令 + LLM 钩子 + 情感引擎 + WebUI + 图片输出
├── command_router.py      # v2.20 命令路由：10 父命令 + /心管 映射表与帮助
├── event_bus.py           # v2.20 事件总线（favor.changed / stage.advanced 等）
├── intent_router.py       # v2.20 意图识别（自然语言静默命令路由）
├── hook_bus.py            # v2.20 前后置钩子注册表
├── emotion_engine.py      # 8 维情感 + 好感/亲密度引擎（十二阶段）
├── smart_updater.py       # 四维智能更新决策器
├── memory_manager.py      # 长期记忆管理器（落盘 JSON）
├── llm_analyzer.py        # 辅助 LLM 情感分析（注入关系角色上下文）
├── penalty_reward.py      # 惩罚奖励引擎（含冷落冻结）
├── anniversary.py         # 纪念日/节日系统（农历换算 1900-2100）
├── stats_tracker.py       # 每日情感快照与趋势统计
├── relationship_roles.py  # 关系角色系统（39 角色）
├── relationship_crisis.py # 关系危机事件
├── character_manager.py   # 多角色并行关系（角色卡）
├── time_perception.py     # 时间/节假日/农历感知
├── image_renderer.py      # 图片卡片/趋势图渲染（Pillow，可选）
├── report.py              # 报告生成（月报/回顾/趋势等）
├── trainer/               # 个性化训练（v2.17）
│   ├── trainer_orchestrator.py  # 调度器：注入组装 + token 裁剪 + 四模块联动
│   ├── trainer_storage.py / trainer_types.py
│   ├── persona/           # 人格微调（含 persona_guard.py 护栏）
│   ├── knowledge/  style/  memory/   # 知识库 / 语言风格 / 私人记忆
├── rde/                   # 关系深度演进（v2.18）：narrative/ crisis/ network/
├── tpd/                   # 时间感知深化（v2.19）：天气/倒计时/跳跃/环境注入
├── pages/dashboard/       # WebUI 控制台
└── tests/                 # 26 个测试文件全量断言回归
```

---

<a id="changelog"></a>

## 📜 版本更新记录

> 完整版本记录见 [changelog.md](changelog.md)

| 版本 | 摘要 |
|------|------|
| **v2.21**（当前） | RDE 阶段叙事频控注入（间隔 3 轮/跃迁强制，危机感知不受限）· 阶段跃迁静态层重注 · WebUI 配置板块 16 模块组 141 键全量可视化（.cs 玻璃卡片化）· schema `_section_rde` 分组 · 插件名称定为「心旅知音 (SoulSync) - 融合版情感智能插件」 |
| **v2.20** | 轻量化重构：70 命令收敛为 10 父命令+`/admin` · 事件总线 EventBus 解耦 · 人格护栏（50 轮稳定自动锁定/24h 3 次剧变回滚/背叛·冷落72h+自动解锁/管理员 2h 临时锁定）· 意图识别静默命令 · 前后置钩子机制 |
| **v2.19** | 时间感知深化（TPD）：三级降级天气+8维心情映射 · 倒计时六阶段叙事 · 时间跳跃（告别/回归/被动离开）· 冷落惩罚冻结 · 22 项配置 · WebUI 时间感知面板 · 74 组测试 |
| **v2.18** | 关系深度演进（RDE）：十二阶段叙事 · 关系危机系统（7 类型 14 事件）· 多角色关系网 · WebUI RDE 面板 |
| **v2.17** | 个性化训练模块：人格微调（20 参数）/ 知识库 / 语言风格 / 私人记忆 · 四模块联动 · WebUI 个性化面板 |
| **v2.16** | 情感深化：记忆锚点/遗忘曲线 · 复合情绪/情绪传染 · 阶段风格 · 危机事件 · 月度报告/角色独白/雷达图 · 多角色并行关系 |
| **v2.15** | 惩罚机制改为每日更新：冷落惩罚每日定时结算（启动补结算 + 每日 00:10） |
| **v2.14** | WebUI 玻璃态整合系列（美化/性能/管理员工具/滚动条滑块） |
| **v2.13 ~ v2.10** | 好感正向增长放缓 50% · 阶段 6→12 · 惩罚奖励放缓约 30% · 好感上限 100→200（详情见 changelog.md） |
| **v2.9 ~ v1.0** | 配置热同步 / 关系角色 / 数据趋势 / 纪念日节日 / 惩罚奖励 / 辅助 LLM / 初版融合 |

---

<a id="credits"></a>

## 🙏 参考与致谢（二次创作声明）

本插件为对以下开源项目的 **参考与二次创作（二创）**，借鉴其核心机制思路并融合扩展：

| 参考插件 | 借鉴内容 | 原项目 |
|----------|---------|--------|
| 🧠 情感智能插件 **EmotionAI-Pro** | 8 维情感模型、好感/亲密度双核、关系阶段演进、智能更新决策、辅助 LLM 情感分析、惩罚奖励机制 | [asakiyoshi/EmotionAI-Pro](https://github.com/asakiyoshi/EmotionAI-Pro) |
| ⏰ 环境感知增强插件 **LLMPerception** | 时间/节假日/农历/平台环境感知的注入方式 | [miaoxutao123/astrbot_plugin_LLMPerception](https://github.com/miaoxutao123/astrbot_plugin_LLMPerception) |

**声明：** 本项目为二次创作，仅用于学习交流，代码与文案由 AI 辅助编写；项目版权归原作者所有，若原作者有异议请联系删除；使用本项目产生的任何问题与原作者无关。
