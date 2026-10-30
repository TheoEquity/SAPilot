# SAPilot 文档入口

项目仓库保存代码、可共享文档和配置模板。本机语料、评测原始结果、账号及模型权重放在仓库旁的 `../SAPilot-data/`，不随 Git 提交。

设计资料按当前说明、未实现规划、历史记录、核对原文、测试手册、待办及讨论稿分类，入口见[设计资料分类导航](zh-CN/design/README.md)。本轮已从 18 篇核对原稿提炼当前内容，旧正文保留；目录不代表运行验收或实施批准。

## 从哪里开始

| 要了解的内容 | 入口 | 状态与用途 |
| --- | --- | --- |
| 项目目标、SAP 规则和验收原则 | [项目背景](SAPILOT_PROJECT_CONTEXT.md) | 产品目标与约束；不代表全部已实现 |
| 当前组件、消息处理与配置 | [当前架构与消息处理流程](zh-CN/design/current/current-architecture-and-message-flow.md) | 源码基线、意图路由、模型调用、Skill 执行及配置入口；静态核对，运行配置与效果待验证 |
| 文件放置、资料路径与提交规则 | [项目目录约定](zh-CN/reference/project-layout.md) | 本次整理后的目录及维护规则 |
| 当前平台分层与存储 | [当前平台架构](zh-CN/design/current/platform-architecture.md) | 依据源码提炼当前组件与边界；专题入口见当前说明目录 |
| 接口、组件与配置的实际对应 | [契约盘点](zh-CN/reference/api-component-config-inventory.md)、[HTTP 调用表](zh-CN/reference/http-api-component-matrix.md) | 实施前静态基线与核心字段差异；后续修正见实施记录，运行验收仍待验证 |
| 架构整理的实际实施与审核 | [实施记录](zh-CN/development/architecture-implementation-record.md) | 按批记录候选提交、独立审核、集成与验证；与原静态盘点区分 |
| 本地开发启动 | [轻量开发部署](zh-CN/deployment/local-lite-business-guide.md) | 本地开发与热重载操作，不等同于团队云部署说明 |
| 开发与构建 | [开发指南](zh-CN/development/development-guide.md)、[镜像构建](zh-CN/deployment/build-docker-image.md) | 既有操作说明，执行前核对环境 |

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

讨论稿与正式设计、技术说明分开存放，统一位于 [design/discussions/](zh-CN/design/discussions/README.md)。以下仅为讨论记录，状态与使用边界见各稿。

| 讨论内容 | 入口 | 状态与用途 |
| --- | --- | --- |
| 轻量需求开发与验收流程 | [轻量需求开发流程讨论稿](zh-CN/design/discussions/lightweight-development-workflow-draft.md) | 简化 PRD，澄清需求、检查影响、明确验收后开发；供后续明确引用时采用，流程效果待验证 |
| 架构整理实施顺序 | [架构整理推进计划](zh-CN/design/discussions/architecture-implementation-plan-draft.md) | 原推进建议保留；用户后续已授权逐批实施，当前代码、审核与验证见[实施记录](zh-CN/development/architecture-implementation-record.md) |
| 当前团队云部署与费用选型 | [云服务器与模型 API 部署讨论稿](zh-CN/design/discussions/cloud-api-deployment-draft.md) | 用户已确认本轮采用云部署，4核16GB、千问 3.8 Flash API；云机价格与完整预算待核实，尚未部署或压测 |
| 已作废的离线部署讨论 | [离线架构讨论稿 已作废](zh-CN/design/discussions/offline-deployment-draft.md) | 仅保留历史讨论，不作为当前部署要求或实现依据 |
| 前端分层与业务编辑器整理 | [前端架构讨论稿](zh-CN/design/discussions/frontend-architecture-draft.md) | 保留现有 UI，暂不引入网上组件；Skill 编辑器试点已实施，其他建议不自动升级为已实现 |
| 前端编码与公共组件变更边界 | [前端开发规约讨论稿](zh-CN/design/discussions/frontend-coding-conventions-draft.md) | 讨论组件复用、样式、状态与接口约定及修改前审批；尚未作为完整强制规约生效 |
| 后端分层与 Agent 职责整理 | [后端架构讨论稿](zh-CN/design/discussions/backend-architecture-draft.md) | 意图路由试点已实施并独立审核；其他 Agent 职责拆分仍按原建议边界处理 |
| 后端编码与公共能力变更边界 | [后端开发规约讨论稿](zh-CN/design/discussions/backend-coding-conventions-draft.md) | 讨论公共复用、修改前审批、路由与 Service 等职责及验证要求；尚未作为完整强制规约生效 |
| 数据库表与字段设计边界 | [数据库设计规约讨论稿](zh-CN/design/discussions/database-schema-conventions-draft.md) | 讨论字段语义、约束与索引、结构变更审批及迁移验证；尚未定案，未修改或验证实际数据库 |
| 接口契约与前后端对接盘点 | [接口契约与对接梳理讨论稿](zh-CN/design/discussions/api-contract-and-integration-draft.md) | 静态盘点及 Bot/编排局部契约修正、真实保存回读已完成；全量载荷与完整业务验收仍未完成，分别见契约盘点与实施记录 |

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

## 状态和维护规则

- **当前实现**必须有对应源码或运行证据；目标、讨论稿和历史记录不能替代实现事实。
- 总体架构定案后收敛到一个正式入口，专题文档只解释对应部分，不再另建重复的总架构。
- 当前说明已按 18 篇主要声明的源码核对结果整理；历史差异、未实现规划与旧原文分开阅读。未完成全量实现审计或运行验收，文档描述不能单独作为已交付依据。
- 保留现有 `zh-CN/`、`en-US/` 结构；先按内容核对，再合并或归档，不批量删除语言版本。
- 本地数据路径使用目录约定中的相对路径。仓库文档不链接内部原件或私有运行记录，避免 GitHub 上出现不可访问的本机链接。
- 历史评测结果保留在本地数据目录；只有经过检查、脱敏且可共享的样例或结果摘要才进入仓库。
