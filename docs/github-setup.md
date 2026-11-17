# GitHub 仓库与开发流程

## 当前远程状态（2026-11-18）

- 仓库：<https://github.com/slotmagia/stone-seo-growth>
- 默认分支：`main`
- 已初始化源代码：39 个项目文件，包含 FastAPI MVP、文档、测试与 GitHub Actions CI 配置
- **仓库当前是 Public**：请勿在仓库中提交真实客户信息、产品保密资料、API 密钥、`.env` 或数据库备份。需要存放企业敏感资料时，请由管理员先调整仓库可见性及协作权限

## 获取代码

```bash
git clone https://github.com/slotmagia/stone-seo-growth.git
cd stone-seo-growth
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m pytest -q
```

完整启动与本地管理密钥配置详见 [README](../README.md)。

## 后续变更规范

1. 从 `main` 创建 feature 分支；保持 Catalog/Keywords/Content/Publishing/Analytics 领域边界。
2. 本地运行测试，CI 结果以 GitHub Actions 实际运行记录为准。
3. 提交 Pull Request，重点检查产品证据、权限、数据来源、平台接口合法性与副作用。
4. 不允许在未完成 CMS 授权、幂等、回滚和审计之前开启真实自动发布。

历史包中的 `publish-to-github.sh` / `publish-to-github.ps1` 仅适合**完全空白的远程仓库**，此仓库已初始化，不应再次执行这两个脚本。
