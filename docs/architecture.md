# 技术架构设计 · Architecture v1

## 1. 业务边界与系统职责

业务目标是石材批发、工程和跨境采购的**有效询盘与成交**，而非仅提高文章数量或虚构收录。

当前架构采用 **模块化单体 + 可替换适配器**：一个 FastAPI API，一个关系数据库，一组清晰业务域。首期不使用微服务、外部任务队列和付费 AI 平台，便于离线自测并避免接口授权之前产生外部副作用。

```
运营控制台 / OpenAPI
     |
API Security (X-API-Key; production upgrade to SSO + RBAC)
     |
Catalog ---- Keywords ---- Content ---- Publishing
   |           |            |             |
   +------- evidence -------+         Adapter Port
                                   /  |   |    \
                                CMS  抖音 百度 国际站 ... (待授权)
     |
Analytics + GEO sample evaluation + Audit Events
     |
PostgreSQL (production) / SQLite (local MVP)
```

业务域：

- `catalog`：SKU、规格、加工能力、原始证据与人工核验记录；v0.1.1 加入 CSV 导入（仅未核实事实）、去重及整批校验。
- `keywords`：统一关键词、平台/语言/意图、可解释评分与待办机会。
- `content`：事实快照、内容创建、QA、审核状态转换。
- `publishing`：平台授权、发布协议、幂等任务与状态回执（目前只有交接包）。
- `analytics`：导入可信渠道数据、页面与关键词主题维度效果指标。
- `geo`：人工采样、品牌提及/来源引用/事实准确度评估。
- `site_audit`：人工录入静态页面状态，生成可追溯 SEO 基线（不联网抓取、不推断排名）。
- `governance`（下一期）：规则版本、审批角色、权限、成本预算与运行证据。

### 2. 状态机

```
DRAFT -> VALIDATED -> REVIEW_REQUIRED -> APPROVED -> HANDOFF_READY -> PUBLISHED
  |          |               |              |              |
  +--QA fail-+               +--人工否决(待实现)             +--人工确认外部 URL
```

已实现严格顺序验证，QA 失败停留在 `DRAFT`；下一期需要增加 `REJECTED`、`REVISION_REQUESTED`、`RETRACTED` 及内容多版本回退。

`PUBLISHED` 仅代表操作员记录已在外部渠道发布，不代表系统独立验证 URL，更不代表搜索收录或平台排名。

### 3. 模型与表

| 表 | 关键字段 | 说明 |
|---|---|---|
| `products` | SKU、属性、证据兼容字段 | 产品主档；`verified_fields` 不再是可信状态的唯一来源 |
| `product_fact_revisions` | 字段、事实值、证据来源、复核人、版本、有效期、撤销 | v2 有效事实的唯一来源；旧历史不覆盖 |
| `keywords` | 词、渠道、语言、4项评分、产品 ID | 单渠道机会与归属 |
| `contents` | 关键词 ID、产品 ID、证据快照、审批状态、外部 URL | 内容聚合根 |
| `metrics` | 内容、日期、渠道、来源、曝光、点击、询盘、订单 | 外部指标的已标识导入记录 |
| `geo_observations` | 提问、模型版本、语言、是否提及/引用、审阅准确率 | 不推断全网 AI 搜索表现 |
| `audit_events` | 实体、动作、详情、时间 | 关键操作记录 |
| `site_audit_runs` | 域名、页面数、输入哈希、问题列表与摘要 | 人工静态 SEO 基线（v0.1.1） |

v0.1.2 已加入 Alembic 基线和 ProductFact 迁移；SQLite 本地演示可 `create_all`，PostgreSQL Compose 启动前执行 `alembic upgrade head`。生产上线仍需 PostgreSQL 测试实例的备份/恢复演练。

### 4. 关键数据契约

`ProductFact v2`: `(product_id, field_path, revision, value_snapshot, evidence_reference, evidence_sha256, reviewer, valid_until, action)`；实现追加式事实版本与撤销，`reviewer` 为操作员提供的声明，真实身份绑定/证据附件哈希核验/正式电子签名仍待做。

`KeywordOpportunity`: `(phrase, platform, locale, intent, product_ref, score_breakdown, source, measured_at)`；目前 MVP 存来源文字和评分，下一期补原始指标与可靠性权重。

`ContentDraft`: `(keyword_id, product_id, channel, locale, text, fact_snapshot, state, version)`；事实在生成时拷贝，后续变更必须重新 QA。

`PublicationIntent`: `(content_id, content_version, destination, idempotency_key, reviewer)`；未来适配器需回传 `(status, external_id, url, error_code)`，禁止按请求已发出就标记成功。

### 5. Agent Runtime（目标架构，**尚未执行**）

建议第二阶段采用 LangGraph：

```
Start -> KeywordClassifier -> PagePlanner -> EvidenceRetriever
                 |                  |
                 +------ No opportunity -> Halt
                                    |
                               DraftGenerator
                                    |
                               DeterministicQA
                           bad facts |       | pass
                           Reject ---+       v
                                HumanApproval (interrupt)
                                          |
                              AuthorizedPublisher or ManualHandoff
                                          |
                                     MetricsFeedback
```

工程要求：

1. `State` 使用 Pydantic 定义，不允许 Agent 自由写数据库。通过受控工具调用应用服务。
2. 调用大模型前仅注入已核实的 `ProductFact`，携带每条事实的 `evidence_ref`。
3. 生成输出为结构化 JSON，草稿必须经过确定性 QA 和人工审批。
4. 关键节点有重试预算、幂等键、checkpoint、中断/恢复和成本上限。
5. `Publisher` 默认关闭，具备明确授权、可回滚机制及最小工具权限后才可启用。
6. Agent 的评分是业务优先级建议，不被解释为排名承诺。
7. 全流程保存 `input_hash/model/prompt_version/tools/outputs/errors/approval`，供质量回归测试。

不推荐先引入多个自由聊天 Agent。只在业务决策有明显收益的节点使用模型，数据同步、状态转换、权限检查都采用确定性代码。

### 6. 平台连接器矩阵

| 渠道 | MVP | 首个可验证交付 | 权限/限制 |
|---|---|---|---|
| 官网 CMS | 人工交接包 | WordPress/Headless CMS 授权发布 | 需要真实 CMS、API 凭据、回滚接口 |
| 百度搜索 | 分发状态占位 | Webmaster/Sitemap、获准的链接提交与收录指标 | 接口授权、配额；提交≠收录 |
| Google | 分发状态占位 | GSC Search Analytics、Sitemap 和技术审计 | GSC OAuth/服务账号权限；Indexing API 不适用于普通商品页 |
| 抖音 | 人工交接包 | 脚本+素材+获准发布/数据接口 | 内容发布权限、账号授权、速率限制 |
| 国内店铺 | 人工交接包 | 商品映射+商品/订单授权接口 | 店铺和应用的 API 权限 |
| 阿里国际站 | 人工交接包 | 国际站商品字段/属性映射及获准接口 | ICBU 对应开发者资格与授权 |
| GEO | 手动采样 | 合规样本评测及可见性趋势 | 采样不能代替平台排名或搜索引擎官方数据 |

### 7. 页面与 SEO 结构（目标）

```
/products/{material}/{sku}
/applications/{application}
/projects/{real-case-id}
/guide/{topic}
/en/products/{material}/{sku}
/en/applications/{application}
```

目标包括稳定 canonical、语言互指 hreflang、动态 sitemap、schema.org 类型合规、图片 alt、移动端体验、重复页面识别、站内链接和 404 审计。实际 URL 结构需根据现有官网确认，不直接重建老站或破坏原有流量。

### 8. 横切关注点

- 安全：接口限权、密钥托管、SSO、RBAC、数据脱敏、PII 生命周期管理。
- 可靠性：任务去重、超时、指数重试、死信队列、失败人工接管。
- 性能：站点爬取速率与 robots 限制、缓存、分页及批量 IO。
- 成本：每个任务记录 API 调用、token、计算资源和有效询盘成本。
- 可观测性：OpenTelemetry + 指标/日志/追踪；指标必须标明采集来源。
- 治理：模块注册表、领域公共接口、架构约束测试，防止 AI 迭代形成平铺代码。
