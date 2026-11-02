# SAPilot 旧原文与核对记录

18 篇均已在 2026 年 10 月 29 日逐篇对照相关源码，补充 **110 条主要声明的核对记录**。每篇开头有适用范围、差异、未落地部分及源码链接；原文保留供追溯。

适用内容已提炼到[当前说明](../current/README.md)，过时描述归入[历史差异](../historical/superseded-design-notes.md)，未接通内容进入[未实现规划](../planned/README.md)。本目录继续保留 18 篇旧正文与篇首核对表，路径不变；各篇原先的分类和状态文字也保留为当时记录。

常规了解实现时从当前说明进入；这里用于追溯原始上下文和核对依据。下表给出每篇的整理去向，历史差异另按全部 18 篇逐一列明。

## 整理去向

| 核对原文 | 当前说明 | 未实现规划 |
| --- | --- | --- |
| [平台架构](architecture.md) | [平台架构](../current/platform-architecture.md) | — |
| [认证](authentication.md) | [认证与配额](../current/authentication-and-quotas.md) | — |
| [聊天历史](chat_history_design.md) | [历史与 Prompt](../current/chat-history-and-prompts.md) | — |
| [导出](collection_knowledge_export_design.md) | [市场与导出](../current/marketplace-and-export.md) | [P3 过期清理](../planned/README.md#p3-导出过期清理) |
| [市场](collection_marketplace_design.md) | [市场与导出](../current/marketplace-and-export.md) | — |
| [连通分量](connected_components_optimization.md) | [知识图谱](../current/knowledge-graph.md) | [P5 分量调度](../planned/README.md#p5-图谱分量调度扩展) |
| [上传](document_upload_design.md) | [摄取与索引](../current/document-ingestion-and-indexing.md) | — |
| [评测](evaluation-design.md) | [问题集与评测](../current/evaluation.md) | — |
| [图索引](graph_index_creation.md) | [知识图谱](../current/knowledge-graph.md) | — |
| [索引架构](indexing_architecture.md) | [摄取与索引](../current/document-ingestion-and-indexing.md) | [P9 Prefect 占位](../planned/README.md#p9-prefect-调度后端占位) |
| [实体提取与合并](lightrag_entity_extraction_and_merging.md) | [知识图谱](../current/knowledge-graph.md) | — |
| [Prompt](prompt_customization_design.md) | [历史与 Prompt](../current/chat-history-and-prompts.md) | [P2 索引 Prompt](../planned/README.md#p2-索引-prompt-接入) |
| [配额](quota-system-design.md) | [认证与配额](../current/authentication-and-quotas.md) | [P6 配额增强](../planned/README.md#p6-配额增强) |
| [检索](search_flow_design.md) | [检索与视觉](../current/search-and-vision.md) | — |
| [标签授权](tag_based_permission_design.md) | 已有基础见[市场说明](../current/marketplace-and-export.md)；标签主体未实现 | [P1 标签与授权](../planned/README.md#p1-标签分组与批量授权) |
| [URL 与文本导入](url_and_text_import_design.md) | [摄取与索引](../current/document-ingestion-and-indexing.md) | [P8 导入扩展](../planned/README.md#p8-导入来源元数据与后续扩展) |
| [视觉索引](vision_index_creation.md) | [检索与视觉](../current/search-and-vision.md) | [P4 查询与展示](../planned/README.md#p4-视觉查询与展示扩展) |
| [Web 搜索](web-search-design.md) | [检索与视觉](../current/search-and-vision.md) | [P7 缓存与指标](../planned/README.md#p7-web-缓存与指标采集) |

## 核对口径

- **基线**：核对当日的当前工作区，Git HEAD 为 `2eba14caffb9166089cf5d0a2022b853ef20a46f`；包含既有未提交改动，仅检出该提交不足以复现全部证据。后续源码变化时需重核受影响条目。
- **范围**：逐篇检查主要架构、接口、数据模型、配置、处理流程与完成状态声明；不是对每行伪代码、SQL、安装命令、全部权限边界或性能数字的完整审计。
- **仍适用（静态）**：在当前相关主路径找到对应实现；不代表实际启用、配置正确、运行通过或效果达标。
- **过时 / 部分适用**：当前路径、字段、默认值、前提或执行策略与原文有差异；以表内列明的范围和源码为准，不应整段照搬。
- **仅规划 / 未闭合**：在明确列出的模型、迁移、路由、服务或调用路径内未发现对应完整实现，或仅有字段/方法而没有主流程调用；不等于已获批准，也不等于已正式作废。
- **待验证**：实际环境、数据库状态、外部 Provider、权限效果、并发、故障恢复、内容质量、成本及性能需要运行证据。本轮未启动服务、调用模型、操作数据库或执行后台任务。

本轮只整理文档，未修改业务代码。原稿中的“已实现”“待完成”和性能数字均保留为历史声明，适用性以篇首核对记录为准；未单列的示例不能视为已经逐行验证。

## 逐篇结果

| 文档 | 综合判定 | 主要结论 |
| --- | --- | --- |
| [平台总体架构](architecture.md) | 主体适用，局部过时 | 总体分层仍适用；传输、存储和分块参数需按当前路径修正，性能与生产就绪声明未验证。 |
| [认证系统](authentication.md) | 主体适用，局部过时 | Cookie/JWT、API Key 与条件 OAuth 仍有实现；前端栈、回调地址和安全保证文字需修正。 |
| [聊天历史数据流程](chat_history_design.md) | 主体适用，回放范围需收窄 | 历史读取和混合存储仍适用；历史响应会过滤事件，TTL、写入与会话恢复不能按旧文档泛化。 |
| [知识库导出](collection_knowledge_export_design.md) | 主链存在，自动清理仅规划 | 异步 ZIP 导出主链有源码；七天自动清理未找到实现，入口条件和并发边界需按当前代码理解。 |
| [知识库分享与市场](collection_marketplace_design.md) | 主体存在，授权前提过时 | 市场、发布、订阅与专用页面有实现；“必须订阅才能读取”及旧前端实现方案已不适用。 |
| [图谱连通分量优化](connected_components_optimization.md) | 算法存在，并行与性能声明不适用 | BFS 与按分量过滤仍存在；分量合并当前被限为1并发，旧方法名、测试与性能声明需降级。 |
| [文档上传与摄取](document_upload_design.md) | 主体适用，默认值及保证需修正 | 上传、确认、去重与异步索引主链仍适用；调度周期、重试、错误码及跨存储事务保证需修正。 |
| [自动化评测](evaluation-design.md) | 核心与暂停/恢复已有源码，旧设计有差异 | 评测核心流程已有实现，暂停/恢复也已有接口；原稿数据库字段、任务名和页面设计需以当前代码为准，评分效果未验证。 |
| [图索引构建](graph_index_creation.md) | 主体适用，并行与摘要说明过时 | 图谱提取、分组、合并与 workspace 链路仍适用；分组并行和摘要触发说明有实质差异，性能数据未证实。 |
| [索引调度架构](indexing_architecture.md) | 主体适用，锁与可靠性声明需限定 | 状态与版本驱动、Celery 工作流仍适用；“只写数据库”“移除所有锁”和部分失败可检索等表述需限定。 |
| [实体提取与合并](lightrag_entity_extraction_and_merging.md) | 主体适用，并行与原子性声明需限定 | 提取、精确名称聚合、片段阈值摘要及细粒度锁仍有实现；并行分量、批量原子写与示例参数需限定。 |
| [Prompt 自定义设计](prompt_customization_design.md) | Agent 已接入，索引集成仍待落地 | Prompt 表、管理 API 和 Agent 优先级已有实现；索引 Prompt 解析器尚未接入所核对的索引主路径，语言参数与旧包路径已变化。 |
| [配额系统](quota-system-design.md) | 主体适用，限流及一致性保证需收窄 | 配额表、管理 API 和资源消费/释放已有实现；不能把资源数量限制等同请求限流，原子性和错误响应的概括需收窄。 |
| [检索流程](search_flow_design.md) | 主体适用，重排与过滤说明过时 | MCP→REST→动态检索 DAG 主体仍适用；重排降级、会话过滤和配置地址存在重要差异，不能按示例推定所有分支行为。 |
| [标签与批量授权方案](tag_based_permission_design.md) | 主体仅规划，权限前提已变化 | 主体仍是未落地的标签与批量授权方案；订阅即权限的设计前提与当前市场读取主路径不符，实施前需重新确认需求。 |
| [URL 与文本导入方案](url_and_text_import_design.md) | 主链已有源码，旧契约示例过时 | URL 和文本导入及暂存确认已有前后端实现；内部 HTTP 调用、响应结构、来源元数据和校验描述与当前代码不同。 |
| [视觉索引方案](vision_index_creation.md) | 双路径已有源码，部分结构与扩展仍为方案 | 视觉索引两条建库路径及检索已有实现；模型 API 分类、数据结构和重排设计与原稿不同，扩展计划不能当成交付状态。 |
| [Web 搜索与内容读取](web-search-design.md) | 能力已有源码，旧契约与待集成声明过时 | Provider、HTTP 与 MCP 能力已有实现；旧请求模型和待集成声明已过时，当前搜索优先级增加 Firecrawl，生产可靠性没有本轮证据。 |

## 优先注意的差异

- **市场与标签授权**：当前市场读取主路径不强制订阅，部分读取接口允许匿名；标签方案不能以“创建订阅”推定团队定向授权已经成立。
- **图谱并发**：连通分量算法存在，但分组合并当前受 `Semaphore(1)` 限制；旧稿中的分量并行和倍数提升没有当前证据。
- **Prompt 配置**：Agent 路径调用优先级解析器；索引解析器虽存在，所核对的 graph/summary/vision 主路径未接入。
- **导出过期**：代码写入七天后的过期时间，但本轮未找到自动清理任务和调度链。
- **评测及导入**：评测、暂停/恢复、URL 与文本导入已有对应源码，不能再按旧实施清单整体视为未开发。
- **聊天与检索**：当前 Web 聊天主路径是 WebSocket；检索降级重排会优先图谱结果，且不能按原稿认定所有检索节点均按 `chat_id` 过滤。

以上摘要的具体证据与限制见对应篇首核对表。当前用户消息流程另见[当前架构与消息处理流程](../current/current-architecture-and-message-flow.md)。

返回[设计资料分类导航](../README.md)。
