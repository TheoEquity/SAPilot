# SAPilot 当前平台架构

> 状态：当前说明，依据 2026 年 10 月 29 日源码静态核对整理。描述已存在的实现及其边界，不代表运行验收或生产容量结论。

## 组件与职责

Web 使用 Next.js App Router、React 和现有 shadcn/Radix 组件。FastAPI 提供 `/api/v1` 业务接口，并挂载 `/mcp` 与 OpenAI 兼容 `/v1` 接口。具体用户消息、意图路由、Skill 和模型配置见[当前架构与消息处理流程](current-architecture-and-message-flow.md)，这里说明公共平台部分。

| 层次 | 当前职责 | 源码入口 |
| --- | --- | --- |
| Web | 页面、业务配置、文件上传与聊天展示 | [web/src/app](../../../../web/src/app/)、[聊天组件](../../../../web/src/components/chat/chat-messages.tsx) |
| API | 请求校验、身份依赖和服务调用 | [app.py](../../../../aperag/app.py)、[views](../../../../aperag/views/) |
| Service | Collection、文档、聊天、市场、配额等业务协调 | [service](../../../../aperag/service/) |
| Flow | 按依赖执行节点，用于传统聊天与动态检索 | [engine.py](../../../../aperag/flow/engine.py) |
| 索引与任务 | 记录期望状态，调谐并调度解析及索引任务 | [索引管理器](../../../../aperag/index/manager.py)、[reconciler.py](../../../../aperag/tasks/reconciler.py)、[Celery 配置](../../../../config/celery.py) |

## 主要处理链路

文档从上传暂存、确认进入索引任务；检索请求按参数组合多个召回节点，经合并与重排返回结果。各索引依 Collection 配置启用，不保证每份文档都建立全部索引。详见[摄取与索引](document-ingestion-and-indexing.md)、[检索与视觉索引](search-and-vision.md)。

当前 Web 聊天连接 `/bots/{bot_id}/chats/{chat_id}/connect` WebSocket。ChatService 按 Bot 类型选择传统 Flow 或 Agent 处理路径；其他流式 HTTP 接口的存在不能替代这条 Web 主路径说明。依据：[聊天路由](../../../../aperag/views/chat.py)、[ChatService](../../../../aperag/service/chat_service.py)。

## 存储与配置边界

| 数据 | 当前实现方式 | 使用边界 |
| --- | --- | --- |
| 业务元数据 | PostgreSQL 模型及 Repository | 表定义存在不表示当前数据库已完成迁移 |
| 历史消息正文 | Redis List，反馈等业务记录另存 PostgreSQL | 持久化、备份和重启恢复取决于部署 |
| 原文件与解析资产 | 对象存储适配，默认 `local`，支持 S3 | Docker 环境覆盖为 `/shared/objects`；MinIO 不是统一强制默认 |
| 向量与摘要/视觉召回 | 配置的向量后端，按索引类型过滤 | 摘要并非固定使用 SQL 向量匹配 |
| 全文召回 | 全文索引及其后端配置 | 可用性依赖实际索引和服务 |
| 图谱 | LightRAG 与配置的图、KV、向量存储 | 环境模板使用 PostgreSQL 图存储实现，也保留其他后端选择 |

依据：[业务模型](../../../../aperag/db/models.py)、[应用配置](../../../../aperag/config.py)、[Docker 环境覆盖](../../../../envs/docker.env.overrides)、[环境模板](../../../../envs/env.template)、[摘要检索](../../../../aperag/flow/runners/summary_search.py)。

普通解析配置默认分块为 `400/20`，LightRAG 子路径默认 `1200/100`；二者服务不同路径，实际仍受配置影响。LightRAG 按 Collection 设置 workspace，但命名隔离的存在不等于权限、并发和跨存储一致性已经验证。

开发、调试与常规验证继续在本地。团队云部署的已确认方向和未定事项见[云部署讨论稿](../discussions/cloud-api-deployment-draft.md)；云机规格与模型选型不构成当前容量验收结论。

## 状态与追溯

本文不保留旧稿中的固定时延、倍数提速、实体规模选型阈值或“生产就绪”保证；这些旧声明见[历史差异记录](../historical/superseded-design-notes.md)。未接通的能力见[未实现规划](../planned/README.md)。

原始材料：[平台架构原稿及核对记录](../pending-review/architecture.md)。返回[当前说明目录](README.md)。
