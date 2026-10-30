# GitHub Actions 历史工作流归档

归档日期：2026 年 10 月 29 日。用户决定：当前全部暂停 CI/CD，保留原文以便以后按需恢复。本目录不是当前生效的 CI/CD 配置。

13 个 YAML 文件从 `.github/workflows/` 原样移入本目录，逐文件移动前后的 SHA256 一致。当前分支的原工作流目录已无 YAML。GitHub 远端已核对全部停用：11 项为 `disabled_manually`，2 项定时任务原本为 `disabled_inactivity`，没有重新启用它们。

远端默认分支仍可能保留旧文件；仓库级停用使这些定义当前不再触发。既有失败记录和运行日志没有删除，历史红灯不表示归档后又执行了检查。停用前已查询，没有正在排队或运行的工作流。

## 文件清单

| 文件 | 原用途 |
| --- | --- |
| [auto-approve.yml](auto-approve.yml) | PR 评论指令自动批准 |
| [cherry-pick.yml](cherry-pick.yml) | PR 评论指令自动回补提交 |
| [cicd-push.yml](cicd-push.yml) | Push 检查及上游镜像、Helm 检查 |
| [cicd-pull-request.yml](cicd-pull-request.yml) | Review 后的检查与 E2E 编排 |
| [e2e-aperag.yml](e2e-aperag.yml) | 镜像构建及 AWS EKS 测试环境编排 |
| [e2e-aperag-test.yml](e2e-aperag-test.yml) | EKS 部署及端到端测试 |
| [issues-tagstale.yml](issues-tagstale.yml) | 定时标记不活跃 Issue、PR |
| [pull-request-check.yml](pull-request-check.yml) | 分支名、PR 标题与 Issue 关联检查 |
| [pull-request-label-size.yaml](pull-request-label-size.yaml) | PR 大小标签 |
| [pull-request-stats.yml](pull-request-stats.yml) | 定时 PR 统计 |
| [release-chart.yml](release-chart.yml) | 上游 Helm Chart 发布与通知 |
| [release-create.yml](release-create.yml) | Tag 触发上游 Release 创建 |
| [release-image.yml](release-image.yml) | 上游镜像发布、通知及测试触发 |

原路径、Git 内容对象、移动时 SHA256、GitHub workflow ID 和停用前状态见 [manifest.json](manifest.json)。`sha256AtMove` 用于核对本次原样移动；不同平台检出时可能转换换行，跨平台内容追溯使用 `gitBlobOid`。

## 恢复边界

以后需要 CI/CD 时，先重新确定要执行的检查或发布目标，再选择性恢复：

1. 将选定文件复制回仓库根目录的 `.github/workflows/`，一起恢复其调用的本地工作流依赖。
2. 核对、修正旧权限、任务依赖、密钥引用和上游仓库目标，再提交并推送到准备使用的分支。
3. GitHub 识别文件后，手动启用对应 workflow；文件恢复本身不代表已启用。ID 保存在清单中，可使用 `gh workflow enable <ID> --repo TheoEquity/SAPilot`。

原文保留了已知旧错误：镜像复用工作流的 OIDC 权限不匹配、PR 汇总依赖不存在的 `make-test`；还包含 ApeCloud 镜像/通知/仓库目标和 AWS EKS 配置。归档不表示这些文件已修复、适用或可以直接恢复运行。

测试源码、构建命令与 `.github/utils/` 保留，之后可以独立复用。当前仍需在本地完成与变更相称的验证；本次暂停不表示代码通过了远端 CI，也没有建立替代的自动发布流程。

返回[历史资料](../README.md)或[文档入口](../../README.md)。
