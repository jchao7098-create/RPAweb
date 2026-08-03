# 业务数据统一入 RPA 主库

自 2026-07-27 起，生产环境中的以下数据统一存入 RPA 主 MySQL 数据库：

- RPA 需求、项目和项目日志；
- Skill 与 Python 插件资产；
- 学习角色、角色变更记录、周名单、学习周报、正式提交和退回记录。

代码仍为资产与学习模型保留 `assets` bind key，但生产配置将该 bind 指向与
RPA 项目相同的数据库。测试环境可以继续覆盖为临时 SQLite。

## 项目状态规则

RPA、Skill 和 Python 插件共用四种生命周期状态：

- `在编`
- `使用`
- `大修`
- `停用`

自动模式下，`0%–99%` 对应 `在编`，`100%` 对应 `使用`；管理员也可以
手动指定四种状态。Skill/Python 的审核状态仍独立保存为待审核、已通过或已拒绝。

## 数据迁移与核验

旧 `backend/var/assets.db` 保留为迁移源和离线备份，应用运行时不再读取它。
迁移脚本默认只预览，增加 `--apply` 后执行：

```powershell
python scripts/migrate_assets_to_main_mysql.py
python scripts/migrate_assets_to_main_mysql.py --apply
```

项目状态同步脚本同样默认只预览；执行前会在 `backend/var/backups` 自动保存
项目 ID、原状态和进度快照：

```powershell
python scripts/sync_project_statuses.py
python scripts/sync_project_statuses.py --apply
```

两个脚本均可重复执行；已存在的资产/学习主键不会被重复插入。
