# SAPilot 文档入口

本页仅提供资料说明与导航，不承载开发规则或必读流程；实际开发要求由根 [AGENTS.md](../AGENTS.md) 直接引用具体规范。

项目仓库保存代码、可共享文档和配置模板。本机语料、评测原始结果、账号及模型权重放在仓库旁的 `../SAPilot-data/`，不随 Git 提交。

设计资料按当前说明、未实现规划、历史记录、核对原文、测试手册、待办及讨论稿分类，入口见[设计资料分类导航](zh-CN/design/README.md)。本轮已从 18 篇核对原稿提炼当前内容，旧正文保留；目录不代表运行验收或实施批准。

## 从哪里开始

| 要了解的内容 | 入口 | 状态与用途 |
| --- | --- | --- |
| 项目目标、SAP 规则和验收原则 | [项目背景](SAPILOT_PROJECT_CONTEXT.md) | 产品目标与约束；不代表全部已实现 |
| 工程文档概览 | [开发文档说明](zh-CN/development/README.md) | 介绍根目录 `specs/` 中的架构、规约和开发环境资料；具体文件由 `AGENTS.md` 直接引用 |
| 当前组件、消息处理与配置 | [当前架构与消息处理流程](zh-CN/design/current/current-architecture-and-message-flow.md) | 源码基线、意图路由、模型调用、Skill 执行及配置入口；静态核对，运行配置与效果待验证 |
| 文件放置、资料路径与提交规则 | [项目目录约定](../specs/project-layout.md) | 本次整理后的目录及维护规则 |
| 当前平台分层与存储 | [当前平台架构](zh-CN/design/current/platform-architecture.md) | 依据源码提炼当前组件与边界；专题入口见当前说明目录 |
| 接口、组件与配置的实际对应 | [契约盘点](zh-CN/reference/api-component-config-inventory.md)、[HTTP 调用表](zh-CN/reference/http-api-component-matrix.md) | 实施前静态基线与核心字段差异；后续修正见实施记录，运行验收仍待验证 |
| 开发过程与历史验证 | [架构整理实施记录](../records/architecture-implementation-record.md) | 过程材料独立放在根目录 `records/`，记录特定批次的审核、集成与验证，和架构、规约分开 |
| CI/CD 当前状态与历史定义 | [工作流归档](archive/github-actions-20261029/README.md) | 用户决定暂时全部停用；13 个旧定义原样归档，远端对应项已停用，日常验证仍在本地进行 |
| 本地开发启动 | [轻量开发部署](zh-CN/deployment/local-lite-business-guide.md) | 本地开发与热重载操作，不等同于团队云部署说明 |
| 开发与构建 | [开发指南](../specs/development-guide.md)、[镜像构建](zh-CN/deployment/build-docker-image.md) | 既有操作说明，执行前核对环境 |

## 设计资料分类

| 分类 | 入口 | 使用边界 |
| --- | --- | --- |
| 当前说明 | [当前说明](zh-CN/design/current/README.md) | 9 篇：原有消息流程与 8 篇从核对结果提炼的专题；实际配置、端到端行为和效果仍待验证。 |
| 未实现规划 | [未实现规划](zh-CN/design/planned/README.md) | 9 组未接通或可选方案，列明当前基础及未定前提；未自动获批实施。 |
| 历史记录 | [历史记录](zh-CN/design/historical/README.md) | 本轮 18 篇历史差异与旧 Agent 方案；过时描述和未证实效果不作为当前依据。 |
| 核对原文 | [旧原文与整理去向](zh-CN/design/pending-review/README.md) | 18 篇旧正文及 110 条核对记录保留，提供当前说明和规划的逐篇映射。 |
| 测试手册 | [测试手册](zh-CN/design/test-guides/README.md) | 1 篇，保留操作示例；本次未执行测试，示例需先核对。 |
| 待办 | [待办](zh-CN/design/todos/README.md) | 1 篇，旧集成任务，部分方法已存在；完成状态待逐项复核。 |

## 讨论稿

讨论稿与正式设计、技术说明分开存放，统一位于 [design/discussions/](zh-CN/design/discussions/README.md)。其中适用的架构与维护内容已提炼为独立专题，由根 `AGENTS.md` 直接引用；[开发文档说明](zh-CN/development/README.md)仅介绍这些专题。以下保留讨论来源、备选与未采用内容。

| 讨论内容 | 入口 | 状态与用途 |
| --- | --- | --- |
| 轻量需求开发与验收流程 | [轻量需求开发流程讨论稿](zh-CN/design/discussions/lightweight-development-workflow-draft.md) | 原讨论保留，常规工作按[正式开发流程](../specs/development-workflow.md)；流程效果仍需实际任务验证 |
| 架构整理实施顺序 | [架构整理推进计划](../records/architecture-implementation-plan-draft.md) | 原推进建议保留；用户后续已授权逐批实施，当前代码、审核与验证见[实施记录](../records/architecture-implementation-record.md) |
| 当前团队云部署与费用选型 | [云服务器与模型 API 部署讨论稿](zh-CN/design/discussions/cloud-api-deployment-draft.md) | 用户已确认本轮采用云部署，4核16GB、千问 3.8 Flash API；云机价格与完整预算待核实，尚未部署或压测 |
| 已作废的离线部署讨论 | [离线架构讨论稿 已作废](zh-CN/design/discussions/offline-deployment-draft.md) | 仅保留历史讨论，不作为当前部署要求或实现依据 |
| 前端分层与业务编辑器整理 | [前端架构讨论稿](zh-CN/design/discussions/frontend-architecture-draft.md) | 已提炼为[正式前端规则](../specs/frontend-architecture-and-conventions.md)，未实施拆分和迁移建议继续保留 |
| 前端编码与公共组件变更边界 | [前端开发规约讨论稿](zh-CN/design/discussions/frontend-coding-conventions-draft.md) | 组件、样式与状态规则已提炼到正式前端规则，统一授权边界见正式开发流程 |
| 后端分层与 Agent 职责整理 | [后端架构讨论稿](zh-CN/design/discussions/backend-architecture-draft.md) | 已提炼为[正式后端规则](../specs/backend-architecture-and-conventions.md)，其余拆分仍按后续任务确定 |
| 后端编码与公共能力变更边界 | [后端开发规约讨论稿](zh-CN/design/discussions/backend-coding-conventions-draft.md) | 维护边界已提炼到正式后端规则，公共变更口径统一维护在正式开发流程 |
| 数据库表与字段设计边界 | [数据库设计规约讨论稿](zh-CN/design/discussions/database-schema-conventions-draft.md) | 已提炼为[正式数据库规约](../specs/database-design-conventions.md)，不构成实际模型或数据库变更授权 |
| 接口契约与前后端对接盘点 | [接口契约与对接梳理讨论稿](zh-CN/design/discussions/api-contract-and-integration-draft.md) | 已提炼为[正式接口规约](../specs/api-contract-conventions.md)，全量契约与完整业务运行仍按证据验收 |

## 专题入口

| 专题 | 文档 |
| --- | --- |
| 摄取与索引 | [文档摄取与索引调度](zh-CN/design/current/document-ingestion-and-indexing.md)、[知识图谱](zh-CN/design/current/knowledge-graph.md) |
| 检索与 Agent | [检索与视觉索引](zh-CN/design/current/search-and-vision.md)、[消息处理](zh-CN/design/current/current-architecture-and-message-flow.md)、[历史与 Prompt](zh-CN/design/current/chat-history-and-prompts.md) |
| 身份与资源管理 | [认证与配额](zh-CN/design/current/authentication-and-quotas.md)、[市场与导出](zh-CN/design/current/marketplace-and-export.md) |
| 评测 | [当前问题集与评测](zh-CN/design/current/evaluation.md)；摄取、检索和回答的验收原则见[项目背景](SAPILOT_PROJECT_CONTEXT.md)，云部署容量仍待压测 |
| 集成 | [钉钉](zh-CN/integration/dingtalk.md)、[MCP](zh-CN/integration/mcp-api.md)、[Dify](zh-CN/integration/dify.md) |
| 模型与调试 | [Ollama 配置](zh-CN/reference/how-to-configure-ollama.md)、[调试说明](zh-CN/reference/HOW-TO-DEBUG.md) |
| 历史资料 | [归档说明](archive/README.md) |

## 资料状态说明

- 当前说明依据源码整理，目标、讨论稿和历史记录分别保留各自状态；文档分类不代表运行验收。
- 架构概述与工程规约分别承载高层组织和维护要求，根 `AGENTS.md` 直接引用它们；README 仅解释资料内容与关系。
- 当前说明覆盖 18 篇主要声明的源码核对结果，完整实现审计与运行验收仍有未覆盖项。
- 文档保留 `zh-CN/`、`en-US/` 结构，历史材料位于归档目录。
- 本地语料和历史评测位于仓库旁的数据目录，共享资料与本地资料的范围详见项目目录约定。
