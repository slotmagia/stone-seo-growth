# P0-06 版本化数据库迁移 · Alembic

适用 v0.1.2；实际生产上线前须在隔离 PostgreSQL 演练备份恢复。自动化测试当前只覆盖 SQLite，**不代表已经在真实 PostgreSQL 服务器验证**。

## 迁移策略

- `0001_baseline`：采用现有 v0.1 SQLAlchemy 表，原有的产品、内容和指标数据不会被删除，缺表才创建。若旧表结构自行修改或发生漂移，需另行检查和制定迁移补丁；它不会擅自更改旧字段。**基线降级故意拒绝删除业务数据**。
- `0002_product_facts`：增加 `product_fact_revisions` 表、唯一约束和检索索引。仅在这张表没有任何记录时允许降级到 `0001_baseline`；有证据历史时拒绝破坏性回滚。
- 旧 `verified_fields` 等原始值仍保留以便审计，但不会自动视为有效 v2 事实；必须逐条复核来源后重新核验。
- Docker Compose 使用 `alembic upgrade head` 成功后才启动 FastAPI 服务；SQLite 本地开发默认可 `create_all`，它不替代迁移验收。可设置 `MVP_SQLITE_AUTO_CREATE=0` 禁止此行为。

## 开发验收

```bash
pip install -e '.[dev]'
# 新建一个独立 SQLite 测试文件
DATABASE_URL=sqlite:///./data/migration-check.db alembic upgrade head
DATABASE_URL=sqlite:///./data/migration-check.db alembic current
# 警告：仅当没有任何 ProductFact 历史时才执行以下降级
DATABASE_URL=sqlite:///./data/migration-check.db alembic downgrade 0001_baseline
DATABASE_URL=sqlite:///./data/migration-check.db alembic upgrade head
python -m pytest -q
```

## 升级前、升级中和回滚流程（运维需人工执行）

1. 停止写入，核对代码版本、数据库版本和所有第三方自动发布功能关闭。
2. 完成**数据库一致性备份**（PostgreSQL 使用 `pg_dump` 或物理备份），在独立实例执行真实恢复演练，保存备份文件校验摘要并妥善加密。
3. 核查旧表 `products`、`contents`、`metrics` 的行数与唯一索引，留存前后验证脚本记录。
4. 在测试恢复实例运行 `alembic upgrade head`；核对 Alembic 版本、既有数据保留及接口回归测试。然后才在批准的目标环境升级。
5. 若程序升级后需回滚，先让新写入停止。`0002` 有数据时不要尝试破坏性 `downgrade`；将旧程序与兼容数据库重新部署，或从**升级前验证可用的完整备份**恢复。执行恢复前确认新增数据的处理策略。
6. 所有操作和审批须留存时间戳、版本号、执行人；不要在 GitHub 或日志发布机密和真实客户记录。

此版本不提供复杂的跨版本双写/回填策略、生产自动回滚、在线 DDL 零停机担保或多节点迁移锁。生产需经额外工程验收。
