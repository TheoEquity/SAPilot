# SAPilot 当前检索与视觉索引

> 状态：当前说明，依据 2026 年 10 月 29 日源码静态核对整理。索引可用性、模型兼容性、隔离效果与召回质量仍待运行验证。

## 检索如何执行

MCP 的 `search_collection` 使用 Bearer API Key 调用 `/api/v1/collections/{collection_id}/searches`。CollectionService 校验知识库访问后，按 SearchRequest 的非空检索配置动态建立 DAG：各召回节点进入 merge，再进入 rerank。非 owner 访问可转市场检查，并以 owner 身份解析检索配置，具体边界见[市场与导出](marketplace-and-export.md)。

FlowEngine 做拓扑排序、依赖分组、异步执行和 Jinja 参数传递。MCP 工具的索引开关默认打开不代表对应知识库已有全部索引；本次哪些节点执行仍由请求及实际配置决定。当前 MCP 的 `API_BASE_URL` 是模块常量 `http://localhost:8000`，没有本轮已确认的环境覆盖读取路径。

依据：[MCP](../../../../aperag/mcp/server.py)、[CollectionService](../../../../aperag/service/collection_service.py)、[FlowEngine](../../../../aperag/flow/engine.py)、[请求模型](../../../../aperag/schema/view_models.py)。

| 召回类型 | 当前主要行为 | 源码 |
| --- | --- | --- |
| vector | 查询 embedding 与向量检索 | [vector_search.py](../../../../aperag/flow/runners/vector_search.py) |
| fulltext | 使用输入关键词或提取关键词，调用全文索引 | [fulltext_search.py](../../../../aperag/flow/runners/fulltext_search.py) |
| graph | 检查图谱开关，LightRAG hybrid 查询上下文 | [graph_search.py](../../../../aperag/flow/runners/graph_search.py) |
| summary | 查询向量存储，仅取 summary 索引类型 | [summary_search.py](../../../../aperag/flow/runners/summary_search.py) |
| vision | 查询向量存储，仅取 vision 索引类型，并对同一图片资产去重 | [vision_search.py](../../../../aperag/flow/runners/vision_search.py) |

merge 当前只支持 union，默认按文本内容去重。rerank 节点始终存在；启用且配置有效时尝试模型服务，未启用、缺配置或异常时走降级：图谱结果优先，其余结果按分数排序。不能把不同召回的分数直接理解为可比的质量指标。

部分召回会扩大候选数，主流程没有一个统一的最终 topk 截断保证。依据：[merge](../../../../aperag/flow/runners/merge.py)、[rerank](../../../../aperag/flow/runners/rerank.py)、[结果组装](../../../../aperag/service/collection_service.py)。

## 会话文件过滤的实际范围

`/api/v1/chats/{chat_id}/search` 复用搜索服务；当前 vector/fulltext 路径接收并传递 `chat_id`。summary、vision、graph runner 所核对的服务签名和查询没有同等传递，因此不能把“所有节点都会按会话过滤”作为当前隔离保证。是否存在实际可达的混入场景需要结合调用配置验证，本文不将静态差异直接升级为已确认的运行问题。

依据为上表各 runner 及[搜索服务](../../../../aperag/service/collection_service.py)。

## 视觉索引的两条建库路径

VisionIndexer 按 `enable_vision` 启用，图片来自 `ParsedDocumentData.doc_parts` 的图片资产。模型沿用 EMBEDDING/COMPLETION API 类型，以能力标记判断可用路径；没有图片或缺少能力时存在跳过分支。

| 路径 | 执行方式 | 索引标记 |
| --- | --- | --- |
| 多模态 embedding | 图片编码为 data URI，直接生成向量 | `multimodal_embedding` |
| 视觉 completion 转文本 | 用视觉模型生成内容描述，再用 embedding 建向量 | `vision_to_text` |

两个条件分支可同时满足，但当前代码不是双路并行保证。文本查图走 vision_search，同一图片同时命中两种向量时优先保留描述向量结果。ImageSearchService 已有图片 embed_query 查图及资产去重；原方案“图片再经 VLM 转文本、双路并行查询”的完整策略未在该服务中接通。

通用搜索将视觉结果合并后交给 rerank，未按原稿的 index_method 为纯视觉结果单独跳过文本重排。独立模型 API 类型、完整双路查询与分区展示等保留在[未实现规划](../planned/README.md)。

依据：[VisionIndexer](../../../../aperag/index/vision_index.py)、[任务数据结构](../../../../aperag/tasks/models.py)、[APIType](../../../../aperag/db/models.py)、[图片查询服务](../../../../aperag/service/image_search_service.py)、[Collection 配置页面](../../../../web/src/app/workspace/collections/collection-form.tsx)。

## Web 搜索与内容读取

`/api/v1/web/search`、`/api/v1/web/read` 及对应 MCP 工具均已存在。SearchService 默认 DuckDuckGo，ReaderService 默认 Trafilatura；HTTP 层会按配置选 Provider，常规搜索依次尝试 Firecrawl、Jina、DuckDuckGo，并支持 LLM.txt 发现。

当前 WebSearchRequest 使用 `query/source/search_llms_txt`，不以旧稿的 `search_engine` 选引擎；WebReadRequest 必填 `url_list`，locale 默认 `en-US`。读取可按 Jina Key 优先使用 Jina，零成功或异常时回退 Trafilatura；部分成功直接返回，不逐条补抓。批量读取由 Provider 使用 Semaphore 与 gather 控制并发。

全部搜索失败时 HTTP 接口可返回手动搜索建议，200 响应或非空 results 不必然代表实际找到网页。外网可达性、反爬、页面完整性、超时与资源释放需实际验证。依据：[Web 路由](../../../../aperag/views/web.py)、[数据模型](../../../../aperag/schema/view_models.py)、[SearchService](../../../../aperag/websearch/search/search_service.py)、[ReaderService](../../../../aperag/websearch/reader/reader_service.py)。

原始材料：[检索流程](../pending-review/search_flow_design.md)、[视觉索引](../pending-review/vision_index_creation.md)、[Web 搜索](../pending-review/web-search-design.md)。返回[当前说明目录](README.md)。
