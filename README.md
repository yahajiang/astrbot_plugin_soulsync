# astrbot_plugin_soulsync_menu

自动汇总 Bot **全部已注册指令**，按插件分组生成一张菜单图片的 AstrBot 插件。

## 功能

- 自动读取 AstrBot 所有已注册指令（含子指令与别名），**无需手动维护指令列表**
- 只展示**已启用插件**的指令（在 WebUI 停用的插件不会出现在菜单中）
- **权限分类**：普通用户只能看到非管理员指令；管理员可看到全部指令，管理员指令带 `[管理员]` 标记
- 按插件自动分组，指令自带描述注释（取自各插件 handler 的 docstring/desc）
- Pillow 渲染暗色卡片风格图片，自动探测中文字体（Windows/Linux/macOS）
- v3 排版：标题圆点装饰、渐变分隔线、分组竖条、指令圆点、别名 `↳` 引导、页码圆点指示器
- **毛玻璃卡片**：卡片区域显示高斯模糊后的背景（磨砂质感 + 轻微提亮），可通过 `frost_glass` 关闭
- **性能优化**：指令收集缓存 60s 强制刷新兜底 + 同页结果 30s 复用；**状态指纹实时失效**——WebUI 启停/新增插件、注册新指令后，下次 `/menu` 立即生效，无需等待缓存过期；图片缓存文件超过 30s 自动清理
- 指令过多时自动分页：`/menu [页码]`
- Pillow 未安装时自动降级为纯文本输出

## 使用

| 指令 | 说明 |
|------|------|
| `/menu` | 查看菜单图片（第 1 页） |
| `/菜单` | 同上（中文触发词） |
| `/menu 2` | 查看第 2 页 |

## 配置（WebUI -> 插件 -> 菜单图片 -> 配置）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| show_builtin | bool | true | 是否显示 AstrBot 内置指令（/help、/reset、/sid 等） |
| hide_self | bool | true | 不在菜单中显示本插件自身的 /menu 指令 |
| exclude_plugins | list | [] | 排除的插件（填插件目录名或显示名） |
| max_commands_per_page | int | 40 | 每页指令数上限（1-200），超出自动分页 |
| max_desc_length | int | 60 | 指令描述最大长度（0-200） |
| cache_max_files | int | 20 | 图片缓存文件数上限（1-100），超出自动清理 |
| menu_title / menu_subtitle / menu_footer | string | - | 标题/副标题/页脚文字 |
| custom_font_path | string | (空) | 中文渲染为方框时，填写字体文件完整路径（如 `C:/Windows/Fonts/msyh.ttc` 或 Linux 下 Noto Sans CJK 路径） |
| command_prefix | string | / | 菜单中指令显示的前缀 |
| font_size | int | 30 | 正文字号（14-60） |
| bg_color / accent_color / text_color / desc_color | string | - | 颜色（十六进制） |
| frost_glass | bool | true | 毛玻璃卡片：卡片区域显示高斯模糊背景并轻微提亮，关闭后为纯色半透明卡片 |

## 安装

将 `astrbot_plugin_soulsync_menu` 文件夹放入 AstrBot 插件目录，安装依赖 `Pillow`（`requirements.txt`），重启 AstrBot。

## 数据目录

`AstrBot/data/plugin_data/astrbot_plugin_soulsync_menu/cache/` 存放生成的菜单图片，按 `cache_max_files` 自动清理。

## 版本历史

- **v1.4.0**：实时更新——状态指纹实时失效（插件启停/新指令注册立即反映到菜单，无需等缓存过期）；图片缓存按 30s 清理、指令收集 60s 强制刷新兜底
- **v1.3.1**：毛玻璃卡片（frost_glass，默认开）：卡片区域贴入高斯模糊背景 + 轻微提亮，可配置关闭
- **v1.3.0**：v3 排版美化（标题圆点/渐变分隔线、分组竖条、指令圆点、页码圆点指示器）；性能优化（换行二分查找、字体缓存、光晕小图层渲染、PNG 压缩级别调优、指令收集 60s 缓存、同页结果 30s 复用）
- **v1.2.0**：v2 排版（垂直渐变背景、装饰光晕、分组卡片化、指令/别名分行、管理员 badge 样式）
- **v1.1.0**：基础版本（自动枚举指令、分组、分页、文本降级）

## 常见问题

### 中文全部显示为方框？

说明系统里没有可用的中文字体（常见于 Linux/Docker 部署，或字体文件损坏）。解决方法二选一：

1. 安装中文字体，例如 Debian/Ubuntu：`apt install fonts-noto-cjk`，然后重启 AstrBot；
2. 在插件配置中设置 `custom_font_path`，填写一个中文字体文件的完整路径。

插件启动日志会打印实际选用的字体（`字体=...`），可据此判断是否生效。

## 测试

```
python tests/test_menu_image.py
```

不依赖真实 AstrBot 环境（使用桩模块注入），验证指令枚举、分组、去重、过滤、分页与图片渲染。
