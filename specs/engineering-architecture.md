# 工程架构概述

本文说明主要技术选型、高层模块职责、分层依赖、代码归属与关键边界。接口定义和具体开发要求分别由接口规约及开发规约维护。

## 技术栈与用途

项目基于 ApeRAG 二次开发，沿用其知识库、摄取、检索与 Agent 基础，围绕 SAP 业务场景组织功能。

| 层面 | 主要技术 | 用途 |
| --- | --- | --- |
| 前端 | TypeScript、React、Next.js | 页面、路由与业务交互 |
| UI | Tailwind CSS、shadcn/ui、Radix UI | 样式、基础组件与交互组件 |
| 后端 API | Python、FastAPI、Pydantic、Uvicorn | 请求接入、数据校验与 API 服务运行；流式对话使用 WebSocket |
| 接口契约与前端调用 | FastAPI / Pydantic、OpenAPI、Orval、Axios | 从 Python 路由与模型导出接口文档，按业务模块生成前端类型和调用代码 |
| 接口 Mock 与开发测试 | MSW、Faker | 基于同一接口契约生成模拟处理器与测试数据，用于前后端并行开发和回归测试 |
| Agent 与工具 | mcp-agent、MCP / FastMCP、项目 Skill 与 Flow 模块 | 问答任务编排、工具调用和执行能力复用 |
| 模型接入 | 模型 API、OpenAI 兼容 SDK、LiteLLM | 按调用路径接入生成与 Embedding 服务，具体提供商和模型由配置管理 |
| 文档摄取 | MarkItDown、项目 FAQ 表格解析器、Celery | 解析文档、提取内容与资源，在后台组织分块和索引任务 |
| 任务与临时状态 | Celery、Redis | 后台任务分发、任务协调、缓存及会话相关临时状态 |
| 业务数据 | PostgreSQL、SQLAlchemy、Alembic | 保存业务数据，管理数据库访问与结构迁移 |
| 检索 | Qdrant、Elasticsearch | 分别承载向量检索与全文检索，供混合检索流程使用 |
| 图谱检索扩展 | LightRAG | 按需组织知识图谱索引与图谱检索 |
| 文件与资源 | 本地对象存储、S3 兼容对象存储 | 保存原件、解析产物及图片等资源，存储后端由环境配置选择 |
| 观测 | 前端项目 logger（基于原生 console）、Python logging、Langfuse、OpenTelemetry | 前后端及后台任务各自通过统一工具记录业务事件与异常；OpenTelemetry 关联调用链，Langfuse 承担模型与调用链观测 |
| 开发与部署 | uv、Yarn、Docker / Docker Compose | 依赖管理、本地开发与服务部署组织 |

具体版本由依赖清单与锁文件维护；服务地址、凭据和部署参数由环境配置管理。普通新增或修改接口继续按接口规约处理；技术选型、模块职责或依赖边界变化时，再更新本总纲。

## 模块与职责

| 部分 | 高层职责与主要归属 |
| --- | --- |
| 前端 | 页面与业务交互，区分路由、业务模块和通用组件；主要位于 `web/` |
| 后端接入与业务协调 | 接收请求、组织业务操作与资源访问，隔离渠道和业务职责；主要位于 `aperag/views/`、`aperag/service/` |
| Agent 与执行能力 | 路由和执行问答任务，复用模型、检索及工具；沿用 `aperag/agent/`、`aperag/flow/` 等现有模块 |
| 后台摄取 | 组织文档解析、索引和状态更新，与在线问答分开；沿用文档服务、任务与索引模块 |
| 数据与基础能力 | 提供数据访问、存储及外部能力适配，由业务和执行模块按职责调用 |

## 依赖与边界

- 页面组合业务实现，业务实现复用通用组件；基础组件不反向依赖业务。
- 接入层处理协议，业务层协调流程，专门模块提供执行与存储能力；具体分层不要求额外增加转发层。
- 在线问答与耗时文档摄取分别组织；Web 与钉钉复用业务操作，保留渠道差异。
- Agent Skill 与传统 Flow 保留各自执行语义；代码组织规则不等于立即拆分或统一存量实现。
- 浏览器、前端服务端、API 和后台任务分别记录自身事件，通过请求、业务对象和追踪标识关联；日志与追踪复用公共能力，业务模块补充必要上下文。

## 细节归属

文件放置、组件状态及检查方式见[前端开发规约](frontend-architecture-and-conventions.md)；Service、任务与会话等维护方式见[后端开发规约](backend-architecture-and-conventions.md)。数据结构和迁移见[数据库规约](database-design-conventions.md)，变更协作见[开发流程](development-workflow.md)。

HTTP 接口细节由 FastAPI 路由和 Python 模型维护，OpenAPI 文档及前端调用由工具生成；维护规则见[接口契约规约](api-contract-conventions.md)。接口数量随业务演进，不在架构文档中固定，也不另抄接口或字段清单。

日志字段、关键阶段、脱敏和排查要求见[全栈日志与问题排查规约](logging-and-diagnostics.md)，不在架构总纲维护具体事件或接口打点清单。
