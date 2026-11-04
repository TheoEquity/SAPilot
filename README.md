# SAPilot 运维领航员

SAPilot 基于 ApeRAG 二次开发，面向 SAP 知识问答、FAQ 故障处理、ABAP 代码阅读与运维制度检索。项目仓库：[TheoEquity/SAPilot](https://github.com/TheoEquity/SAPilot)。功能目标、当前实现和运行验收分别记录。

## 项目目录

```text
SAPilot/                 项目总目录
├─ AGENTS.md             Agent 工作入口，引用具体规约
├─ README.md             项目入口与导航
├─ app/                  业务代码
├─ maintenance/          Swagger、Langfuse 等维护工具
├─ data/                 业务数据、摄取原文、测试数据集
├─ runtime/              日志、原始报表、截图、缓存和临时文件
└─ docs/                 长期维护的项目资料
   ├─ specs/             正式开发规约、架构和目录约定
   ├─ prompts/           开发建议、需求启动 Prompt 模板
   ├─ design/            产品设计、方案讨论和历史设计
   └─ records/           实施、审查和验证的结论记录
```

`app/` 包含 `aperag/` 后端、`config/` 后台任务配置、`web/` 前端、`tests/`、`scripts/`、`models/` 模型配置，以及 Makefile、Dockerfile、Compose 和依赖清单。Python 包名继续使用 `aperag`。

`data/` 与 `runtime/` 已放入同一个总目录，整体忽略、不提交 Git。前者保存原始材料和可复用题集，后者保存日志、原始评测、私有凭据及历史运行材料。依赖和工具自动管理的 `.venv`、`node_modules`、`.next` 等可留在 `app/` 内，同样不提交。Git、GitHub 和本机 Agent 的隐藏元数据保留工具要求的位置。

开发用建议 Prompt 在 `docs/prompts/`；产品运行时模型 Prompt 属于 `app/` 业务配置。整理过的验证结论在 `docs/records/`，大量原始输出在 `runtime/`。

## 本地访问

| 服务 | 地址 |
| --- | --- |
| SAPilot 前端 | [localhost:3000](http://localhost:3000) |
| API 健康检查 | [localhost:8000/health](http://localhost:8000/health) |
| Swagger UI | [localhost:8000/docs](http://localhost:8000/docs) |
| ReDoc | [localhost:8000/redoc](http://localhost:8000/redoc) |
| Langfuse | [localhost:3300](http://localhost:3300) |

Swagger 是 API 自带界面，入口说明集中在 `maintenance/swagger/`；Langfuse 是独立服务，部署配置在 `maintenance/langfuse/`。

## 启动位置

按[开发环境指南](docs/specs/development-guide.md)准备依赖和本地配置。应用配置为 `app/.env`，模板在 `app/envs/`。应用命令在 `app/` 执行，各服务使用独立终端：

```bash
cd app
make compose-infra
make run-backend
make run-celery
make run-frontend
```

上述 API、Worker、前端是分别启动的常驻进程。业务数据库和对象存储的数据卷不随目录整理删除。

Langfuse 在项目总目录启动：

```powershell
python maintenance/langfuse/setup.py
docker compose --env-file runtime/private/langfuse.env -f maintenance/langfuse/compose.yaml up -d
```

凭据生成器保留已有文件。停止方法及工具说明见[维护入口](maintenance/README.md)。运行日志统一在 `runtime/logs/`；`make clean` 会删除 Docker 数据卷，不用于普通临时文件清理。

## 文档导航

- [项目目标与 SAP 约束](docs/SAPILOT_PROJECT_CONTEXT.md)
- [文档总入口](docs/README.md)
- [目录约定](docs/specs/project-layout.md)、[开发流程](docs/specs/development-workflow.md)
- [当前架构与消息流程](docs/design/zh-CN/current/current-architecture-and-message-flow.md)
- [开发 Prompt 模板](docs/prompts/development-task.md)
- [本轮目录重组与验证](docs/records/project-layout-reorganization-20261102.md)

正式开发要求由 `AGENTS.md` 直接引用具体规约；讨论稿、建议模板和历史结果各自保留状态。

## 本轮验证范围

2026-11-02 已验证新目录下的登录、Bot 页面、实际检索与模型回答、文本上传、Worker 解析及向量/全文索引、搜索、文件下载，以及 Langfuse 接收模型与工具追踪。测试资源单独创建并回收，原有数据库卷和知识库保留。详细检查和限制见本轮验证记录；这不代表完整业务、全部文档质量或生产容量验收。

现有配置未设置自动标题生成的默认模型，标题接口仍可能返回 400；聊天正文可正常完成，本次没有更换模型或扩大为配置修复。

## 来源与许可证

项目继承 [ApeRAG](https://github.com/apecloud/ApeRAG) 的基础能力，许可证见 [LICENSE](LICENSE)。
