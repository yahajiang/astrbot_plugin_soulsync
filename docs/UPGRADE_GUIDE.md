# SoulSync v3.0 升级指南

> 从 JSON 存储迁移到 SQLite 分片集群 + 转生系统

## 破坏性变更

| 变更 | 影响 | 回退方案 |
|------|------|---------|
| 存储后端 JSON → SQLite | 数据格式完全变更 | `SOULSYNC_DB_FALLBACK=true` 回退 JSON |
| 新增 `soulsync.db` 文件 | 数据目录新增文件 | 删除 db 文件即可 |
| 新增转生系统 | 好感 200 不再封顶 | 配置 `rebirth_enabled=false` 关闭 |
| 新增记忆压缩 | 旧记忆可能被压缩 | 压缩前自动备份 |

## 升级步骤（30 分钟内完成）

### 1. 备份当前数据

```bash
cd <AstrBot 数据目录>/plugin_data/astrbot_plugin_soulsync
tar czf ../soulsync_backup_$(date +%Y%m%d).tar.gz .
```

### 2. 停止 AstrBot

```bash
# 方式一：WebUI 停止
# 方式二：命令行
systemctl stop astrbot  # 或 kill <pid>
```

### 3. 替换插件文件

```bash
# 备份旧插件
mv data/plugins/astrbot_plugin_soulsync data/plugins/astrbot_plugin_soulsync_old

# 复制新版本
cp -r astrbot_plugin_soulsync data/plugins/
```

### 4. 执行数据迁移

```bash
cd data/plugins/astrbot_plugin_soulsync
python -m db_migration.migrate_json_to_sqlite <数据目录>
```

预期输出：
```
📊 迁移报告:
  总行数: XXXX
  耗时: X.XXs
  user_profile: XX 行
  behavior_profile: XX 行
  long_term_memory: XX 行
  stats_history: XX 行
```

### 5. 校验数据一致性

```python
from db_migration.validator import MigrationValidator
from pathlib import Path

v = MigrationValidator(Path("<数据目录>"))
report = v.run_all()
print(report.summary())
# 确认所有表匹配率 >= 99.9%
```

### 6. 启动 AstrBot

```bash
systemctl start astrbot  # 或重新运行
```

### 7. 监控日志（24 小时）

```bash
# 检查无 DatabaseError 或 Timeout
tail -f astrbot.log | grep -i "error\|timeout"
```

## 回退方案

遇到致命 bug 时执行：

```bash
# 1. 停止 AstrBot
systemctl stop astrbot

# 2. 设置降级开关
export SOULSYNC_DB_FALLBACK=true

# 3. 恢复数据目录
cd <AstrBot 数据目录>/plugin_data/astrbot_plugin_soulsync
tar xzf ../soulsync_backup_YYYYMMDD.tar.gz

# 4. 重启 AstrBot
systemctl start astrbot
```

系统将在 2 分钟内完全回退至旧 JSON 模式，用户无感知。

## 新功能配置

### 转生系统

```yaml
# 默认开启，如需关闭：
rebirth_enabled: false
```

转生触发条件：好感 >= 200 + 当前转生数 × 50

### 记忆压缩

```yaml
# 默认开启，如需调整阈值：
memory_compress_threshold: 20  # 超过此条数触发压缩
memory_compress_batch: 10      # 每次压缩的旧记忆条数
```

### 排行榜缓存

自动启用，无需配置。缓存每 3 秒刷新一次。

## 常见问题

**Q: 迁移后数据丢失？**
A: 检查迁移报告的 `errors` 字段，重新运行迁移脚本（幂等操作）。

**Q: 转生后好感显示异常？**
A: 确认 `rebirth_engine.py` 已正确集成到 `emotion_engine.py`。

**Q: 记忆压缩误删重要记忆？**
A: `important=True` 的记忆不会被压缩，可在 WebUI 查看压缩状态。
