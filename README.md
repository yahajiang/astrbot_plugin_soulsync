# 心旅小馆（SoulSync Bistro）

🍽️ 一个 AstrBot 插件：根据 SoulSync 检测到的聊天情绪，推荐合适的菜谱。

情绪 → 美食映射：

| 情绪 | 主题 | 示例方向 |
|------|------|----------|
| 😊 喜悦 | 庆祝餐 | 硬菜、烤焗、虾、牛排 |
| 😢 悲伤 | 治愈甜品 | 甜品、粥、汤、软糯 |
| 😠 愤怒 | 释放辣味 | 川菜、香辣、下饭 |
| 😟 焦虑 | 安神清淡 | 清淡、蒸、粥、汤 |
| 🤩 期待 | 创意尝鲜 | 日式、意式、法式、异国 |

## 功能

- **自动情绪感知**：通过 `on_llm_response` 钩子截取 SoulSync 的 LLM 回复，本地词典分析情绪（喜悦/悲伤/愤怒/焦虑/期待/平静），缓存快照 30 分钟（可配置）
- **933 道本地菜谱**：合并云游君 cook 与 HowToCook 数据，全部含详细步骤（平均 6 步/道），运行时零网络
- **情绪特调**：每道菜带 mood_hint 标注，随机推荐保证至少混入一道当前情绪适配菜

## 指令

| 指令 | 说明 |
|------|------|
| `/吃点啥 [分类]` | 根据最近情绪推荐一道菜（分类可选：素菜/荤菜/主食/汤/甜品/凉菜） |
| `/菜谱搜索 关键词` | 搜索菜谱库，与当前情绪契合的标注 ❤️此刻适配 |
| `/怎么做 菜名` | 查看详细做法步骤（含食材、视频参考） |
| `/随机推荐 [数量]` | 随机推荐 N 道，至少一道情绪特调 |
| `/心馆 状态` | 查看当前情绪快照与推荐摘要 |

## 配置

| 配置项 | 默认 | 说明 |
|--------|------|------|
| enable_mood_link | true | 情绪联动开关 |
| mood_ttl_minutes | 30 | 情绪快照有效期（1-1440） |
| max_search_results | 8 | 搜索结果条数上限（1-20） |

情绪 → 菜谱映射可在 `mood_mapping.json` 中自定义（关键词/标签/回复语）。

## 数据与许可

- 菜谱数据来源：[YunYouJun/cook](https://github.com/YunYouJun/cook)（MIT，`app/data/recipe.csv`，含视频 BV 号）与 [DingJunyao/HowToCook_json](https://github.com/DingJunyao/HowToCook_json)（CC BY-NC-SA 4.0，火候/时间/用量详解）
- 合并去重后共 933 道，每道含：名称、分类、食材、步骤、标签、难度、工具、辣度、是否素菜、情绪提示

## 开发

```bash
# 回归测试（不依赖 AstrBot，仅需 Python 3.8+）
python -m pytest tests -v
```

`tools/` 内含数据构建脚本：`build_recipes.py`（CSV→JSON）、`merge_steps.py`（子代理步骤合并）、`merge_howtocook.py`（HowToCook 合并）、`validate.py`（数据校验）。
