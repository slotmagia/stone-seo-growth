# P0-02 ProductFact v2：事实证据版本与人工复核

版本：0.1.2，2026-11-18。此版本尚未具备可信电子签名、附件对象存储或复核人身份验证；`reviewer` 和证据引用均为操作员填写的声明，不是系统独立认证结果。

## 1. 核心设计

- `product_fact_revisions` 是按 `(product_id, field_path, revision)` 唯一约束的**追加式**版本历史：复核、重新核验、撤销均新建版本，应用层不编辑旧历史；操作员必须拥有管理 API Key。
- 单字段历史内容：核验时的 `value_snapshot`、来源引用 `evidence_reference`、可选文件 SHA-256、声明的 `reviewer`、`source_kind`、`valid_until`、`created_at`；撤销还记录原因。
- **有效事实**必须同时满足：存在最新版本、action 为 `verified`、尚未过期、产品当前字段值与核验快照相同。撤销永不抹除历史；重新核验产生下一个版本。
- 内容草稿引用 `revision_id` 和来源快照。QA、人工批准、生成发布交接包及确认人工发布时，会检查当前证据版本；发生变化/撤销/过期必须重新生成草稿。
- 旧 `products.evidence` / `products.verified_fields` 仅供兼容；v0.1 无版本记录的旧事实**不会自动被当作新证据使用**。旧产品须重新核验。原有数据不清除。

## 2. API

`/api/v1/*` 均需 `X-API-Key`。例如先创建一条 SKU 后：

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/products/1/facts/verify' \
 -H "X-API-Key: $ADMIN_API_KEY" -H 'Content-Type: application/json' \
 -d '{"field_path":"stone_type","evidence_reference":"supplier-techsheet-2026-page-3","reviewer":"qa-operator-01","evidence_sha256":null,"valid_until":null}'

curl -X GET 'http://127.0.0.1:8000/api/v1/products/1/facts' \
 -H "X-API-Key: $ADMIN_API_KEY"

curl -X POST 'http://127.0.0.1:8000/api/v1/products/1/facts/revoke' \
 -H "X-API-Key: $ADMIN_API_KEY" -H 'Content-Type: application/json' \
 -d '{"field_path":"stone_type","reviewer":"qa-operator-01","reason":"Supplier specification superseded"}'
```

> `evidence_sha256` 是可选文件摘要字段，不代表服务器已收到或校验过源文件；绝对不要在公开 GitHub 仓库或不安全的日志粘贴商业秘密或客户信息。

`POST /products/{id}/verify` 旧接口仍可使用，但历史标记 `source_kind=legacy_api` / `reviewer=legacy_api_unattributed`，**不能将此标签解读为真实人工签名**。建议新系统只用 `/facts/verify`，必须显式输入复核人。

`GET /products/{id}/facts` 返回 `effective_facts` 和最近最多 1000 个历史版本。不能把该有限列表视为完整归档；数据库持久存储所有历史记录。`GET /products` 根据当前版本计算有效字段，避免在旧缓存上展示已过期事实。

## 3. 验收 & 安全边界

- 核验缺失字段、无效 SHA-256、无效到期日直接拒绝，禁止以假证明填充空字段。
- 撤销后旧草稿不允许继续 QA/批准/发布交接。已在外部平台发布的内容**不会被此系统自动撤回**，需人工启动下架纠错流程。
- 仍需要：OAuth/OIDC + RBAC、真实复核人的身份绑定、证据附件对象存储（加密、哈希核验、保留期）、多方复核、防篡改日志及合规审计。
- 不发布到任何外部官网/百度/抖音/电商平台，无真实搜索排名或抓取能力。
