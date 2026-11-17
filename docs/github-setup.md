# GitHub 仓库创建与上传

建议新建**私有**仓库 `stone-seo-growth`，避免把新项目混入其他业务代码库。

当前会话的 GitHub 连接已验证属于 `slotmagia`，但可用的 GitHub 连接动作**没有创建仓库的功能**，因此不宣称已完成远程推送。

1. 打开 <https://github.com/new>，选择账号 `slotmagia`，Repository name 填 `stone-seo-growth`，Visibility 选 **Private**。
2. 不勾选 Initialize with README、.gitignore 或 license（项目包已包含必要文件）。
3. 解压项目包并在解压目录运行以下命令：

```bash
git init
git branch -M main
git add .
git commit -m "feat: bootstrap evidence-first stone SEO/GEO platform MVP"
git remote add origin https://github.com/slotmagia/stone-seo-growth.git
git push -u origin main
```

或完成空仓库创建后，将仓库 URL 返回给 ChatGPT。连接器具备向**现有**仓库创建文件/分支、创建 commit 的能力，可在该仓库上继续提交。

**不要**上传 `.env`、真实登录信息或数据库副本。GitHub Actions 会执行自动化测试；首次 GitHub Actions 运行结果以仓库实际显示为准。
