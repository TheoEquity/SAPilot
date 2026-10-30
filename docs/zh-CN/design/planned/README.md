# SAPilot 未实现规划

> 状态：从已核对原稿中提取的未实现方案或未闭合的集成。整理日期：2026 年 10 月 29 日。仅整理文档，未排期、未实施；列入本页不表示用户已批准开发。

## 范围与使用

下列事项在本轮核对的模型、迁移、路由、服务或主调用路径中没有完整实现，或只有字段/方法占位。每项保留来源和当前已有基础，实施范围仍需按用户后续指令确定。源码判断范围见[逐篇核对记录](../pending-review/README.md)。

已存在但没有运行验收的功能继续写在[当前说明](../current/README.md)的边界中；旧接口、示例和未证实效果见[历史差异](../historical/superseded-design-notes.md)。本页不把缺少运行证据自动解释为没有实现。

## P1 标签分组与批量授权

原稿提出 tag、tag_relation 两表、用户与知识库分组、标签 CRUD、批量创建/撤销订阅，以及缓存失效和审计。当前模型、迁移、业务服务、路由和前端未找到对应完整功能；已有市场发布和订阅基础设施。

**实施前提待重新确认**：当前市场读取不强制订阅，部分路由允许匿名；因此批量创建订阅不能直接达成团队定向授权。应先确认公开市场、订阅与团队访问控制的关系，再决定复用范围。原稿两表 SQL 和“不改现有权限逻辑”的假设均未定案。

来源：[标签方案](../pending-review/tag_based_permission_design.md)。当前基础：[市场说明](../current/marketplace-and-export.md)、[访问检查实现](../../../../aperag/service/marketplace_collection_service.py)。

## P2 索引 Prompt 接入

已有 `index_prompts` 配置和 `resolve_index_prompt`，但本轮全项目 Python 调用检索及 graph/summary/vision 主路径未发现解析器调用；summary/vision 仍内置 prompt。

待接通的方案是 Collection、用户、系统和硬编码配置在索引执行时的选择与模板变量绑定。具体传递方式、哪些索引支持自定义及旧配置兼容应在实施时确定，不能根据页面能保存就认定已生效。

来源：[Prompt 原稿](../pending-review/prompt_customization_design.md)。现状：[Prompt 当前说明](../current/chat-history-and-prompts.md)、[解析器](../../../../aperag/service/prompt_template_service.py)。

## P3 导出过期清理

已有导出任务、ZIP、`gmt_expires`、EXPIRED 枚举和下载分支。原方案的七天自动清理、对象删除与状态迁移没有找到对应任务和调度链。

待落地范围为过期扫描、删除结果与数据库状态的协调及失败后处理；七天时间记录本身不证明清理已执行。

来源：[导出原稿](../pending-review/collection_knowledge_export_design.md)。现状：[导出说明](../current/marketplace-and-export.md)、[导出任务](../../../../config/export_tasks.py)、[Beat](../../../../config/celery.py)。

## P4 视觉查询与展示扩展

已有多模态 embedding、视觉描述转文本两种建库路径，文本查图、图片向量查图和去重。原稿的图片经 VLM 转文本后与直接图片向量双路并行查询、纯视觉结果独立重排策略和分区展示，在本轮核对路径内没有形成完整实现。

这些仍是原方案备选，是否继续保留需要结合实际模型和页面需求确认。原稿独立 API 枚举、images 字段等结构已被当前能力判断和 doc_parts 结构替代，留在历史记录，不列为必须补做的改造。

来源：[视觉原稿](../pending-review/vision_index_creation.md)。现状：[检索与视觉说明](../current/search-and-vision.md)、[VisionIndexer](../../../../aperag/index/vision_index.py)、[图片搜索服务](../../../../aperag/service/image_search_service.py)。

## P5 图谱分量调度扩展

已有 BFS 分量识别与分组过滤，单实例分组合并当前受 `Semaphore(1)` 限制。原稿的动态批处理、优先级和分量缓存，在所核对的分量主路径中未发现对应实现。

实际并行合并如要推进，也需要明确数据一致性和公共锁的约束；旧稿的倍数提升不能作为实现完成后的预定效果。是否推进这些优化尚未确定。

来源：[连通分量原稿](../pending-review/connected_components_optimization.md)。现状：[图谱说明](../current/knowledge-graph.md)、[分组实现](../../../../aperag/graph/lightrag/lightrag.py)。

## P6 配额增强

已有管理员手工调整、消费/释放、默认值和用量重算。原稿的配额历史、按策略自动调整、临时/按时间配额、告警、缓存和外部配额提供商等，在所核对的配额模型、服务和路由中未形成完整机制。

这些是可选增强，不能把手工改上限记为策略自动调整，也不能把资源数量限制当作请求限流已实现。

来源：[配额原稿](../pending-review/quota-system-design.md)。现状：[认证与配额说明](../current/authentication-and-quotas.md)、[QuotaService](../../../../aperag/service/quota_service.py)。

## P7 Web 缓存与指标采集

Provider、HTTP/MCP、超时参数与批量并发控制已有代码；原稿的完整缓存机制及专门指标采集，在所核对的 websearch 服务内未找到对应完整实现。是否建设、缓存什么和采用哪些指标仍待实际需求确定。

来源：[Web 搜索原稿](../pending-review/web-search-design.md)。现状：[Web 搜索说明](../current/search-and-vision.md)、[websearch 实现](../../../../aperag/websearch/)。

## P8 导入来源元数据与后续扩展

URL 和文本导入主链已经存在。原示例的 `source_url/source_type` 元数据写入没有在 fetch_url_documents 的上传调用中接入；响应携带 URL 不等于数据库已保存来源字段。

原稿还保留“根据文字搜索网络后导入”的扩展空间，但明确不在原期范围；此项只保留为备选，不能自动列为当前待交付需求。

来源：[URL 与文本导入原稿](../pending-review/url_and_text_import_design.md)。现状：[摄取说明](../current/document-ingestion-and-indexing.md)、[DocumentService](../../../../aperag/service/document_service.py)。

## P9 Prefect 调度后端占位

现行索引任务使用 Celery；PrefectTaskScheduler 的方法仍抛出 `NotImplementedError`。它是第二调度后端的占位，不是可用部署选项，也不代表当前必须另建调度后端。

来源：[索引架构原稿](../pending-review/indexing_architecture.md)。现状：[索引说明](../current/document-ingestion-and-indexing.md)、[调度器](../../../../aperag/tasks/scheduler.py)。

返回[设计资料导航](../README.md)。本轮架构与开发规约讨论仍单独保留在[讨论稿](../discussions/README.md)，其原有决定、建议与作废状态不变。
