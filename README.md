# Stone Growth OS — 石材行业 SEO / GEO 智能增长平台

> **v0.1.0 · 可运行的离线/本地 MVP，不是生产级全渠道运营系统。**
>
> 对应需求：石材批发、加工、工程、线上零售及外贸的关键词发现、证据型内容、发布审批、搜索表现与询盘增长闭环。

## 已实现范围

| 能力 | 状态 | 说明 |
|---|---|---|
| 产品/规格知识库 | ✅ MVP | 产品 SKU、属性、核验字段、证据引用 |
| 关键词机会 | ✅ MVP | 中文/英文关键词、搜索渠道、意图与可解释评分 |
| 内容生成 | ✅ MVP | **离线模板引擎**：只包含已经核验的事实，尚未接入 LLM |
| AI Agent / LangGraph | 📋 设计阶段 | 在 `docs/architecture.md` 中定义接口及下一期实现路径 |
| QA 和审批状态机 | ✅ MVP | 未核验事实阻止审批、所有关键操作产生审计日志 |
| 发布适配层 | 🟡 骨架 | 接口契约、能力矩阵、人工发布交接；**没有实际第三方发布** |
| 站点技术 SEO | 🟡 基础 | 本地内容 SEO 检查；爬虫审计、站点提交尚未接入 |
| 数据分析 | ✅ MVP | 授权数据的人工导入、按产品内容归集的汇总看板 |
| GEO | 🟡 基础 | 手动记录 AI 搜索采样结果、提及率与引用率；无实时平台查询 |
| 电商/百度/Google/抖音/国际站 API | 📋 待授权 | 需要账号授权、接口审批、平台配额与契约测试 |
| 多渠道自动发布、真实搜索排名 | ❌ 未实现 | 不能声称已实现或保证排名 |

## 本地运行（无需外部账号）

要求 Python 3.11+。

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
cp .env.example .env
# 将 .env 中的 ADMIN_API_KEY 改成随机长密钥
export ADMIN_API_KEY='请改成你自己生成的长随机密钥'
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- 控制台：<http://127.0.0.1:8000/>
- OpenAPI 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/health>
- 默认数据库：`./data/seo_growth.db`（本地 SQLite）

**注意**：代码不自动加载 `.env`，命令行运行时需显式导出环境变量（或通过进程管理器导入）。Docker Compose 会读取 `.env`。

## Docker Compose（PostgreSQL）

```bash
cp .env.example .env
# .env 中填写安全的 ADMIN_API_KEY 和 POSTGRES_PASSWORD
# 设置 DATABASE_URL 为 postgres 的值不必手写，compose 会注入
# 注意：两者都不能留空或使用示例值
# docker compose up --build -d
```

在 `.env` 追加：`POSTGRES_PASSWORD=<随机数据库密码>`。Compose 只在 `127.0.0.1:8000` 监听；远程访问必须经 HTTPS 反向代理与身份认证。此配置仅用于功能试运行。生产需要 Alembic 数据库迁移、备份、角色隔离、SSO、审计保留策略、安全扫描和运行监控。

## 业务操作演示

1. 打开控制台，填写 `ADMIN_API_KEY`。
2. 创建产品 SKU 与属性（新建事实默认**未核实**）。
3. 点击「核实字段与来源」，为每一条真实材料属性提供来源引用，例如产品说明书、检测报告或人工签字复核记录。
4. 创建关键词，评分范围 0–100；例如 `granite paving slabs supplier`，渠道 `google`、语言 `en-US`。
5. 生成草稿。只有**草稿生成前已经核实**的字段会出现在正文中；后续核验不会自动修改旧草稿。
6. `QA → 提交审核 → 人工批准 → 生成发布交接包`。
7. 使用有权限的账号完成**人工发布**后，才能通过网址及平台凭据标记已发布（仅记录操作员确认，未独立校验 URL）。
8. 使用 `POST /api/v1/metrics` 导入实际表现，在控制台查看汇总；GEO 观察可从 Swagger API 导入。

## API 示例

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/v1/dashboard \
  -H "X-API-Key: $ADMIN_API_KEY"
```

所有 `/api/v1/**` 端点均需要密钥，且不内置账号/密钥，未配置返回 503。`GET /` 和 `/health` 为公开页面。

## 测试

```bash
python -m pytest -q
python -m compileall -q app
```

## 结构

```text
app/
  main.py                    # REST API & local dashboard
  database.py, models.py     # persistence
  schemas.py, security.py    # validation and auth
  domains/
    catalog/                 # real product facts + evidence
    keywords/                # scoring and research
    content/                 # evidence-based drafting + QA
    publishing/              # manual handoff and platform registry
    analytics/               # metrics aggregation
  integrations/ports.py      # platform adapter contract
  web/index.html             # zero-build operator UI

docs/
  architecture.md            # domain architecture & integrations
  implementation-plan.md     # 90-day delivery plan and P0/P1/P2 backlog
  operations-and-security.md # security, rollback, failure handling
  requirements.md            # product acceptance criteria & KPI
  github-setup.md            # create private repo and push instructions
```

## 原则

- **事实优先**：产品参数、产地、价格、库存、认证、工程案例不能由 LLM 虚构。
- **官方授权**：仅使用经授权的平台接口；不自动模拟登录、绕过验证码或批量操作账号。
- **人为控制**：高影响的发布、商品声明和风险内容需要人工审批。
- **明确状态**：草稿、审核、发布交接、人工确认、搜索收录、排名及成交彼此独立。
- **可追溯**：保存数据来源、内容版本、审计事件和数据采集方式。
- **不承诺排名**：技术 SEO 和 GEO 提高可发现性，但不保证搜索引擎排名或 AI 引用。

许可证：待仓库所有者明确选择；目前未附带开源许可证，默认保留所有权利。
