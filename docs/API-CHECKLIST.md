# 平台 API 授权检查清单（逐渠道填写）

> 一张核验表对应一个渠道+一个授权账号，不要将“开发者平台有接口”理解为“当前账号已获权限”。

| 字段 | 待确认内容 |
|---|---|
| 平台 | 百度 / Google / 抖音 / 国内店铺 / 阿里国际站 / 自有 CMS |
| 账号范围 | 主体、店铺 ID、站点、域名、操作负责人 |
| 授权类型 | OAuth / 服务账号 / API Key（由平台实际要求决定） |
| 能力类别 | 只读数据 / 草稿 / 正式发布 / 删除 / 审核回调 |
| 权限状态 | 未申请 / 审批中 / 已批准 / 已拒绝 / 已过期 |
| 调用配额 | 官方额度、频率、超限处理 |
| 数据口径 | 日期、国家、设备、搜索词、汇总规则及缺失项 |
| 风控合规 | 服务条款、自动化限制、账号操作边界 |
| 回滚能力 | 删除、撤回、修订、人工处理流程 |
| 测试证据 | 沙箱调用响应、API 版本、权限签收记录 |

## 参考官方入口（接入前重新核对最新文档）

- Google Search Console API: <https://developers.google.com/webmaster-tools>
- Google 搜索 SEO 文档: <https://developers.google.com/search/docs>
- 百度搜索资源平台: <https://ziyuan.baidu.com/>
- 抖音开放平台: <https://developer.open-douyin.com/>
- 抖店开放平台: <https://op.jinritemai.com/>
- 阿里国际站开放平台: <https://open.alibaba.com/>

上述链接仅为入口，没有表示任何账号已获授权。以目标 API 的当前官方版本、账号审核结果、平台协议为准。
