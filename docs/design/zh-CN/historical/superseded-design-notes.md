# SAPilot 旧设计差异与历史声明

> 状态：历史记录。整理日期：2026 年 10 月 29 日。依据本轮 18 篇原稿的源码核对结果摘录；原文继续保留，不作为现行接口、配置或安全保证。

## 如何使用

本页记录已经不符合当前实现的描述，以及没有验证依据的旧效果声明。同一原稿中仍适用的内容已提炼到[当前说明](../current/README.md)，没有接通的方案进入[未实现规划](../planned/README.md)。完整旧稿和逐项证据仍在[核对原文目录](../pending-review/README.md)，路径保留。

“历史”只表示这些描述不再用于解释当前行为；它不等于相关功能全部废弃，也不把旧方案转成后续必须实施的任务。

## 逐篇历史差异

| 原稿 | 留作历史的内容 | 当前阅读入口 |
| --- | --- | --- |
| [平台架构](../pending-review/architecture.md) | Web SSE 主路径；把 1200/100 泛化为全部分块默认值；固定 MinIO/Neo4j 构成；笼统的摘要 SQL 向量匹配及生产保证 | [平台架构](../current/platform-architecture.md) |
| [认证](../pending-review/authentication.md) | Ant Design/UmiJS、固定旧回调地址和 current_user 示例；固定 bcrypt 及完整 XSS/CSRF、生产 Cookie 安全保证 | [认证与配额](../current/authentication-and-quotas.md) |
| [聊天历史](../pending-review/chat_history_design.md) | 全部 thinking/工具 Part 重放、统一消息写入路径、默认 TTL 或完整恢复的泛化描述 | [历史与 Prompt](../current/chat-history-and-prompts.md) |
| [导出](../pending-review/collection_knowledge_export_design.md) | 原前端直接比较 owner 的入口示例、计数判断描述和“文件必定完整”的验收措辞；七天自动清理另列规划 | [市场与导出](../current/marketplace-and-export.md) |
| [市场](../pending-review/collection_marketplace_design.md) | 必须订阅才可读、所有市场操作需登录；旧 frontend/src/pages 与 Umi 结构；仍将专用文档/图谱页面列为未开发的清单 | [市场与导出](../current/marketplace-and-export.md) |
| [连通分量优化](../pending-review/connected_components_optimization.md) | _process_entity_groups 旧方法名、分量同时合并、CPU 线性扩展；未找到的指定测试文件不能当作覆盖证据 | [知识图谱](../current/knowledge-graph.md) |
| [文档上传](../pending-review/document_upload_design.md) | 30 秒固定调谐、固定 Worker 并发、指数重试、配额 429、重复确认总成功，以及对象存储随数据库统一回滚的保证 | [摄取与索引](../current/document-ingestion-and-indexing.md) |
| [评测](../pending-review/evaluation-design.md) | evaluation_results 旧表、bot_id/judge_llm_model_id 字段、独立 QuestionGenerationTask 示意、旧页面位置；暂停/恢复仍属未来的标记 | [问题集与评测](../current/evaluation.md) |
| [图索引](../pending-review/graph_index_creation.md) | 分量并行与倍数加速、以 2000 tokens 作为摘要触发阈值、固定压缩到 200 tokens、文档 ACTIVE 等混淆 | [知识图谱](../current/knowledge-graph.md) |
| [索引调度](../pending-review/indexing_architecture.md) | 上传请求只操作数据库、全系统无锁、最终必定成功、部分失败必定不影响可搜索等绝对表述 | [摄取与索引](../current/document-ingestion-and-indexing.md) |
| [实体提取与合并](../pending-review/lightrag_entity_extraction_and_merging.md) | 分量并行、全批次或跨存储原子写、统一 1024 维及固定效果；精确名称合并不等于语义别名全部归一 | [知识图谱](../current/knowledge-graph.md) |
| [Prompt 自定义](../pending-review/prompt_customization_design.md) | language 参数与 ZH/EN 旧签名；索引 Prompt 已自动生效的描述；原文“三层”实际含硬编码第四级兜底 | [历史与 Prompt](../current/chat-history-and-prompts.md) |
| [配额](../pending-review/quota-system-design.md) | 资源配额等同请求限流、所有粒度均线程安全、全部管理拒绝必为 403 的概括 | [认证与配额](../current/authentication-and-quotas.md) |
| [检索](../pending-review/search_flow_design.md) | 降级时把所有结果统一按分数排序、全部节点均按 chat_id 过滤、MCP 地址已有环境覆盖、topk 是最终总数保证等示例 | [检索与视觉](../current/search-and-vision.md) |
| [标签授权](../pending-review/tag_based_permission_design.md) | 订阅即访问权限、只增加两表且现有权限逻辑完全不变的前提；整个功能仍是未落地方案，不认定已废弃 | [未实现规划](../planned/README.md) |
| [URL 与文本导入](../pending-review/url_and_text_import_design.md) | 回调内部 web/read HTTP 的示例、documents/id/name 响应、完整入口校验保证，以及将导入整体视为未开始的实施清单 | [摄取与索引](../current/document-ingestion-and-indexing.md) |
| [视觉索引](../pending-review/vision_index_creation.md) | images 新字段、独立 VLM/MULTIMODAL_EMBEDDING API 枚举和模型选择器的原结构；当前改用 doc_parts 与模型能力判断 | [检索与视觉](../current/search-and-vision.md) |
| [Web 搜索](../pending-review/web-search-design.md) | MCP 仍待集成、search_engine/urls 旧契约、统一 zh-CN 默认值、HTTP 选择策略及单靠 JINA_API_KEY 即生效的旧示例 | [检索与视觉](../current/search-and-vision.md) |

原稿中的 `sapilot/` Python 包路径也仅作历史示意，当前包名为 `aperag/`；前端按 `web/` 实际目录定位。完整证据和各条适用范围见原稿篇首核对表。

## 未证实的旧效果声明

原稿中的 100ms、2–3 倍或更高提速、低于 1% 开销、固定内存/时长、10 万或 100 万实体选型边界、无资源泄漏、信息完全保留及生产稳定性等，均没有本轮运行证据。它们保留为原有描述，不作为当前指标，也不自动进入规划验收标准。

源码能确认异步任务、锁、超时或状态机制存在；实际性能、完整隔离、异常恢复与内容质量需要对应环境和样例验证。这些验证边界已保留在相关当前说明中。

返回[历史资料目录](README.md)或[设计资料导航](../README.md)。
