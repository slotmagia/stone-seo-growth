# P0 第一批增量交付 — 可复现验收

**交付性质**：离线、本地、由操作员输入数据。项目与真实网站、Search Console、百度/抖音/国际站均未连接；不要将报告当作真实抓取、索引或排名结果。

## P0 工作项状态

| 项 | 当前状态 | 本次交付 / 剩余缺口 |
| --- | --- | --- |
| P0-01 资产清查 | 待业务输入 | 需要真实域名、CMS 版本、已授权账号、站点语言、sitemap；不在代码库提交凭据 |
| P0-02 Product Fact v2 | 部分 | 新导入 SKU 默认未核验、源 CSV SHA256 汇总审计；字段复核人、附件存储、失效时间与字段版本待做 |
| P0-03 CSV 导入 | **离线 MVP 完成** | UTF-8 BOM、字段校验、大小/条数限制、SKU 去重、dry-run、整批原子导入、审计和错误行报告；Excel 尚未支持 |
| P0-04 技术 SEO 基线 | **静态快照 MVP 完成** | 自备页面元数据 JSON → 问题列表、严重程度、历史记录；未连接在线爬虫、真实 robots.txt/sitemap 或索引状态 |
| P0-05 安全基线 | 部分 | 原有 API Key 保护、测试、审计；生产 SSO/RBAC、速率限制/备份/密钥轮换待做 |
| P0-06 迁移体系 | 待开发 | 当前数据库 `create_all`；新表 `site_audit_runs` 会在本地自动建立。生产迁移必须使用 Alembic 并实测回滚 |

## 1. 产品 CSV 规范

端点：`POST /api/v1/products/import-csv?dry_run=true|false`

- 原始 `text/csv` 请求体，UTF-8 或 UTF-8 BOM，不使用 multipart。
- 必需列 `sku,title_zh,stone_type`，可选 `title_en` 和 `property.<key>`（扁平小写字母、数字、下划线）。示例在 `examples/demo_products.csv`。
- `property.<key>` 值为一般文本，或 JSON 数组/对象字符串；数组/对象需要合法 JSON 且必须按 CSV 规则转义引号。
- SKU 去除首尾空格、转大写；文件内与库内 SKU 均不区分大小写检查重复。
- 大小上限 1 MiB、数据行最多 1000 行、列最多 24 列。其他字段与错误编码必须经过校验。
- 全文件无错才导入；任意错误 **整个文件不写库**。`dry_run=true` 只预检，不写入数据和审计事件。
- 导入后产品 `evidence={}`、`verified_fields=[]`，仍需单独人工核实。文件摘要（SHA-256）保存在导入审计事件中，但当前不存储原 CSV 文件，也不形成单字段证据附件。

本地预检和导入（需配置并导出管理密钥）：

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/products/import-csv?dry_run=true" \
  -H "X-API-Key: $ADMIN_API_KEY" -H "Content-Type: text/csv" \
  --data-binary @examples/demo_products.csv

curl -sS -X POST "http://127.0.0.1:8000/api/v1/products/import-csv" \
  -H "X-API-Key: $ADMIN_API_KEY" -H "Content-Type: text/csv" \
  --data-binary @examples/demo_products.csv
```

返回结果含 `rows_received`、`valid_rows`、`would_import`、`imported`、`errors`、`sha256`。失败导入返回 422 和行号/错误编码；并发 SKU 冲突返回 409 且回滚。

## 2. SEO 基线（静态快照）

端点：`POST /api/v1/sites/audits`，`GET /api/v1/sites/audits`，`GET /api/v1/sites/audits/{id}`。

提交 JSON（见 `examples/demo_site_snapshot.json`），至少有一个页面、最多 200 个页面，声明 `site_url`；各页面提供 `url`、`http_status`、`title`、`meta_description`、`canonical`、`h1_count`、`noindex`、`in_sitemap`。页面必须属于目标站点域，不能重复；允许子域名。不访问任何传入 URL。

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/sites/audits" \
  -H "X-API-Key: $ADMIN_API_KEY" -H "Content-Type: application/json" \
  --data-binary @examples/demo_site_snapshot.json
```

当前规则：HTTP 错误、缺失标题、重复标题、meta description、H1 数量、noindex、sitemap 成员资格、canonical 与 URL 差异。标题 70 / 描述 160 字符均为**编辑建议阈值而非搜索引擎官方要求**。没有提供的 robots / sitemap / canonical 字段按「未知」列入信息项，不伪造缺陷。问题与 SHA-256 及汇总存储在 `site_audit_runs`，由 `audit_events` 记录操作。

**明确限制**：站点快照中的 HTTP 状态、robots、sitemap 均是输入声明；当前版本不会联网抓取，也不验证网站所有权、Search Console 数据或排名表现。

## 3. 本地验收

```bash
python -m pytest -q
python -m compileall -q app
```

验收覆盖：成功预检/入库、BOM、属性 JSON、重复 SKU、错误行与全量回滚、超过大小/列数的拒绝、鉴权、站点分析和结果持久化、跨域/重复 URL 拒绝、未知状态不误判。

## 4. 下一批任务 / 发布阻断项

1. 收集真实站点域名、CMS、源数据样本（脱敏）、多语言站结构与账号权限，不向公共 GitHub 提交商业秘密。
2. 引入产品级字段证据 `ProductFact` 版本表（来源、采集时间、复核人、有效期、附件哈希、撤销），为审批提供可验证来源。
3. 新增 SQLite→PostgreSQL Alembic 初始迁移/升级/回滚测试，禁止直接在生产使用 `create_all`。
4. 在线技术 SEO 只读采集器：域名 allowlist、robots 遵从、SSRF/内网地址阻断、限流、超时、采集快照；必须额外授权并在隔离环境测试。
5. 上线前补齐 SSO/RBAC、API Key 轮换、审计保留与备份恢复演练；多租户隔离尚未实现。
