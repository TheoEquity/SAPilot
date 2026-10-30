# SAPilot 设计讨论稿

本目录只存放讨论记录。常规实现与文档读取不以讨论稿为真源；用户明确要求基于某稿实施时，在指定范围内作为需求输入，当前指令和已确认决定优先。未确认建议不自动成为决定，讨论状态不代表实现或验证完成。

当前说明、未实现规划、历史记录、旧原文与核对记录、测试手册和待办见[上级设计分类导航](../README.md)，完整导航见[文档入口](../../../README.md)。本目录继续只记录讨论。

| 讨论稿 | 当前状态 |
| --- | --- |
| [架构整理推进计划](architecture-implementation-plan-draft.md) | 原建议保留；用户已授权逐批实施并独立审核，当前状态见[实施记录](../../development/architecture-implementation-record.md) |
| [轻量需求开发流程](lightweight-development-workflow-draft.md) | 简化 PRD，明确需求、影响范围和验收，按需并行并验证整合结果；供后续明确引用时采用，流程效果待实际需求验证 |
| [云服务器与模型 API 部署](cloud-api-deployment-draft.md) | 云部署方向、4核16GB 与生成模型选型已确认；其余建议、预算与容量仍按稿内状态处理，尚未部署 |
| [前端架构](frontend-architecture-draft.md) | 保留现有 UI，暂不引入网上组件；Skill 编辑器试点已实施，其余建议未自动生效 |
| [前端开发规约](frontend-coding-conventions-draft.md) | 组件复用、样式与公共修改审批等细则待定案 |
| [后端架构](backend-architecture-draft.md) | 意图路由试点已实施并独立审核，其他职责拆分仍为建议 |
| [后端开发规约](backend-coding-conventions-draft.md) | 公共复用、修改审批与层次职责等细则待定案 |
| [数据库表与字段设计规约](database-schema-conventions-draft.md) | 设计、审批与迁移要求为建议，未修改或核对实际数据库 |
| [接口契约与前后端对接梳理](api-contract-and-integration-draft.md) | 已完成[静态盘点](../../reference/api-component-config-inventory.md)及 Bot/编排局部修正和真实保存回读；全量接口与业务运行未全部验收，见实施记录 |
| [离线部署 已作废](offline-deployment-draft.md) | 保留历史讨论，不能作为当前部署或实现要求 |

本次目录整理不改变各讨论稿的决定、建议、未知项或作废状态。
