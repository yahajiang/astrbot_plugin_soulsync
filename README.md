# 心旅知音 · 注入防护盾 (astrbot_plugin_soulsync_shield)

心旅知音（SoulSync）衍伸系列插件：防止提示注入（Prompt Injection）与恶意调教，保护 AI 人格设定不被污染。

## 功能

- **Persona 加固**：每次 LLM 请求在 system prompt 末尾注入防注入保护段（`<InjectionGuard>` 标记去重），锁定人格、禁止泄露内部指令。
- **输入检测**：内置中英文硬关键词库 + 启发式正则（动作+敏感词句式、伪 system/INST 标签、DAN 模式、人设劫持家族——"扮演+现实""从现在开始+扮演""否认模型身份""输出无害论""免遵守条款""服从主人命令""条件回答脚本"等）+ 混淆解码（base64、分隔符拆分如 `i-g-n-o-r-e`）。
- **上下文扫描**：同时扫描上下文中的用户历史消息（防记忆/历史投毒，对 SoulSync 等注入长期记忆的插件尤为重要），按当前模式剥离或删除，最多扫描最近 100 条（可配置）。
- **关系角色豁免**：与 SoulSync 内置 39 个关系角色联动——纯身份指派表达（"现在你是我的女朋友/恋人/妹妹"等）放行，保障合法关系推进；混入"忽略/泄露/服从/混淆"等攻击标记的仍拦截；可追加豁免词（如"主人"）。
- **三级处置**：
  - `block`（默认）：拦截提示注入，LLM 完全不执行原指令。
  - `sanitize`：剥离恶意片段，保留正常内容；全部剥离则降级为拦截。
  - `warn`：放行仅记录日志，用于观察误报。
- **拦截提示开关**：开启（默认）时拦截后由模型转告拦截提示语；关闭时模型仅以当前人格自然、简短地拒绝用户（"不能这样做"），静默拦截只记日志。
- **管理员通知**：可选在每次拦截（当前消息拦截、上下文投毒移除）时向管理员**私发**通知，含时间、用户、命中规则与拦截内容片段；接收人可单独配置，通知中内容预览长度可限制（默认 120 字符）。
- **白名单豁免**：管理员与指定用户的消息不检测。
- **统计与日志**：今日拦截/剥离/告警计数 + 最近命中记录，持久化到 AstrBot 数据目录（条数上限默认 500，可配置）。

## 管理指令（管理员）

```
/injguard help                    # 帮助
/injguard stats                   # 今日统计与最近命中
/injguard mode block|sanitize|warn # 切换处置模式（持久化）
/injguard whitelist add|del <用户ID> # 增删白名单
/injguard whitelist list           # 查看白名单
```

## 配置项

| 配置 | 说明 | 默认 |
|---|---|---|
| enabled | 插件总开关 | true |
| mode | 处置模式 block/sanitize/warn | block |
| guard_persona | 注入人格加固段 | true |
| custom_guard_text | 自定义加固段（留空用默认） | "" |
| block_reply | 拦截提示语 | 见 schema |
| send_block_reply | 发送拦截提示（关闭后模型自然拒绝） | true |
| notify_admin | 拦截时私发通知管理员 | false |
| notify_admin_ids | 通知的管理员 ID（留空用 admin_ids） | [] |
| notify_preview_len | 通知内容预览长度上限（50-500） | 120 |
| extra_keywords | 追加检测关键词 | [] |
| enable_heuristics | 启发式检测（正则/混淆） | true |
| exempt_admins | 管理员豁免 | true |
| exempt_users | 白名单用户 | [] |
| admin_ids | 额外管理员 ID | [] |
| log_max_entries | 日志条数上限（1-5000） | 500 |
| scan_contexts | 扫描上下文历史消息（防记忆投毒） | true |
| context_scan_max_entries | 上下文扫描条数上限（1-500） | 100 |
| soulsync_role_exempt | 豁免 SoulSync 内置关系角色表达 | true |
| role_vocab | 额外豁免的关系角色词（如"主人"） | [] |

## 设计说明

- 纯标准库实现，无新增依赖。
- 检测器只收录"正常聊天几乎不会出现"的高危短语，降低误杀；误报时请切换 `warn` 模式观察，或把误判词加入白名单语境（更推荐调整 `extra_keywords` 之外，直接在 issue 反馈内置库）。
- 拦截发生在 `on_llm_request` 钩子，替换请求文本而非仅拦截事件，因此对所有模型供应商生效。

## 部署

将 `astrbot_plugin_soulsync_shield` 目录放入 AstrBot `plugins` 目录，重启或热载入即可。若此前使用旧名 `astrbot_plugin_inj_guard`，统计文件会自动迁移。

## 许可证

MIT
