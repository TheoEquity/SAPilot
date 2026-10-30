# SAPilot 设计讨论稿

本目录保存讨论记录，包括原始理由、备选、未采用建议和当时的状态；讨论记录不代表当前实现或运行验收。本页仅作内容说明与导航，相关工作规则见根 [AGENTS.md](../../../../AGENTS.md)。

用户随后要求将适用的架构与维护内容整理为独立 Markdown。具体规范现由根 `AGENTS.md` 直接引用，[开发文档说明](../../development/README.md)仅提供概览；原稿继续保留讨论背景和历史状态，文档正式化不代表未实施拆分或生产操作已经获准。

当前说明、未实现规划、历史记录、旧原文与核对记录、测试手册和待办见[上级设计分类导航](../README.md)，完整导航见[文档入口](../../../README.md)。本目录继续只记录讨论。

| 讨论稿 | 当前状态 |
| --- | --- |
| [架构整理推进计划](../../../../records/architecture-implementation-plan-draft.md) | 原建议保留；用户已授权逐批实施并独立审核，当前状态见[实施记录](../../../../records/architecture-implementation-record.md) |
| [轻量需求开发流程](lightweight-development-workflow-draft.md) | 已提炼为[正式开发流程](../../../../specs/development-workflow.md)，原稿保留，流程效果仍需实际需求验证 |
| [云服务器与模型 API 部署](cloud-api-deployment-draft.md) | 云部署方向、4核16GB 与生成模型选型已确认；其余建议、预算与容量仍按稿内状态处理，尚未部署 |
| [前端架构](frontend-architecture-draft.md) | 文件归属及维护边界已提炼到[正式前端规则](../../../../specs/frontend-architecture-and-conventions.md)，其余迁移建议保留 |
| [前端开发规约](frontend-coding-conventions-draft.md) | 组件、样式、状态与验证要求已提炼到正式前端规则，公共变更统一引用正式开发流程 |
| [后端架构](backend-architecture-draft.md) | 已提炼到[正式后端规则](../../../../specs/backend-architecture-and-conventions.md)，进一步拆分仍按后续任务确定 |
| [后端开发规约](backend-coding-conventions-draft.md) | 分层与复用已提炼到正式后端规则，公共变更统一维护在正式开发流程 |
| [数据库表与字段设计规约](database-schema-conventions-draft.md) | 已提炼为[正式数据库规约](../../../../specs/database-design-conventions.md)，不构成模型或实际数据库变更授权 |
| [接口契约与前后端对接梳理](api-contract-and-integration-draft.md) | 已提炼为[正式接口规约](../../../../specs/api-contract-conventions.md)，全量契约和业务运行仍按证据验收 |
| [离线部署 已作废](offline-deployment-draft.md) | 保留历史讨论，不能作为当前部署或实现要求 |

各稿的未采用建议、未知项及已作废离线方案仍保留原状态；正式规则仅覆盖已提炼的工程维护内容。
