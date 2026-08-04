# astrbot_plugin_menu_image

自动汇总 Bot **全部已注册指令**，按插件分组生成一张菜单图片的 AstrBot 插件。

## 功能

- 自动读取 AstrBot 所有已注册指令（含子指令与别名），**无需手动维护指令列表**
- 按插件自动分组，指令自带描述注释（取自各插件 handler 的 docstring/desc）
- Pillow 渲染深色卡片风格图片，自动探测中文字体（Windows/Linux/macOS）
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
| command_prefix | string | / | 菜单中指令显示的前缀 |
| font_size | int | 30 | 正文字号（14-60） |
| bg_color / accent_color / text_color / desc_color | string | - | 颜色（十六进制） |

## 安装

将 `astrbot_plugin_menu_image` 文件夹放入 AstrBot 插件目录，安装依赖 `Pillow`（`requirements.txt`），重启 AstrBot。

## 数据目录

`AstrBot/data/plugin_data/astrbot_plugin_menu_image/cache/` 存放生成的菜单图片，按 `cache_max_files` 自动清理。

## 测试

```
python tests/test_menu_image.py
```

不依赖真实 AstrBot 环境（使用桩模块注入），验证指令枚举、分组、去重、过滤、分页与图片渲染。
