# SAPilot 当前说明

9 篇当前说明，包括原有消息流程和从 18 篇核对原稿中提炼的 8 篇专题。更新日期：2026 年 10 月 29 日。常规了解实现时从这里进入；运行效果和生产能力仍按各篇边界判断。

| 要了解的内容 | 当前说明 |
| --- | --- |
| 平台组件、分层与存储配置 | [平台架构](platform-architecture.md) |
| 用户消息、意图分流、Skill 与 Bot 配置 | [架构与消息处理流程](current-architecture-and-message-flow.md) |
| Cookie、API Key、OAuth 与资源配额 | [认证与配额](authentication-and-quotas.md) |
| 文件、URL、文本、暂存确认、解析与异步索引 | [摄取与索引调度](document-ingestion-and-indexing.md) |
| 实体关系提取、分量合并、摘要与锁 | [知识图谱](knowledge-graph.md) |
| 检索 DAG、重排、视觉索引和 Web 搜索 | [检索与视觉索引](search-and-vision.md) |
| 历史存取、回放范围与 Prompt 生效路径 | [聊天历史与 Prompt](chat-history-and-prompts.md) |
| 市场发布、订阅、读取边界与 ZIP 导出 | [知识库市场与导出](marketplace-and-export.md) |
| 问题集、异步评分、暂停与恢复 | [问题集与评测](evaluation.md) |

## 使用边界

准备前后端拆分时，先读[接口、组件与配置字段盘点](../../reference/api-component-config-inventory.md)及[HTTP 调用对应表](../../reference/http-api-component-matrix.md)。该盘点覆盖实施前路由、调用与核心字段差异；后续修正和验证以[实施记录](../../../../records/architecture-implementation-record.md)为准，不能继续把所有差异视为当前未修复。

上述专题根据 2026 年 10 月 29 日逐篇核对结果整理。后续代码实施、审核与验证的变化见[架构整理实施记录](../../../../records/architecture-implementation-record.md)，使用专题时需同时核对该记录和最新源码。工作区含既有未提交改动，不能只用最初 Git HEAD 复现全部内容；各篇保留源码链接和具体限制。

“当前”指有对应实现，不代表已启用、权限审计通过或实际运行验收完成。部署、模型联通、并发、异常恢复和 SAP 内容质量仍需实际证据，不能由目录分类推定。

[历史差异](../historical/superseded-design-notes.md)保留旧结构、旧保证和未证实效果；[未实现规划](../planned/README.md)保留没有接通的方案；[18 篇核对原文](../pending-review/README.md)保留旧正文与 110 条核对记录。规划和讨论稿不作为当前能力说明。

返回[设计资料分类导航](../README.md)。
