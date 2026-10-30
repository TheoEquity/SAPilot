# SAPilot 当前文档摄取与索引调度

> 状态：当前说明，依据 2026 年 10 月 29 日源码静态核对整理。格式保真、索引质量和故障恢复尚未完成运行验收。

## 从文件到索引

常用两阶段路径在 `/api/v1` 下：

1. `POST /collections/{id}/documents/upload` 保存文件和元数据，文档进入 `UPLOADED` 暂存状态。
2. `POST /collections/{id}/documents/confirm` 校验用户、知识库和暂存状态，转为 `PENDING` 并创建索引记录，触发调谐。
3. 调谐器认领索引操作，Celery 解析文档，再按配置建立各类索引并回报结果。旧的直接创建文档路径仍存在。

依据：[路由](../../../../aperag/views/collections.py)、[DocumentService](../../../../aperag/service/document_service.py)、[文档任务](../../../../aperag/tasks/document.py)。

上传依名称部分唯一索引和 `ON CONFLICT` 处理同名文件，再比较内容哈希；历史记录没有 `content_hash` 时会跳过比较。重复确认非 `UPLOADED` 文档会记入失败结果，不能承诺重复请求总是成功。

默认单文件大小限制为 100MiB，数量配置为 1000；用户总量与单库配额另行检查。文档数量配额超限对应 403。上传在数据库事务回调内写对象存储，数据库回滚不能证明对象写入也已撤回。依据：[配置](../../../../aperag/config.py)、[文档服务](../../../../aperag/service/document_service.py)、[模型约束](../../../../aperag/db/models.py)。

## URL 与粘贴文本

URL 导入已经存在：`POST /collections/{id}/documents/fetch-url` 进入 `fetch_url_documents`，直接调用 ReaderService 获取内容，封装 Markdown 虚拟文件后复用上传。响应为 `results` 数组，条目使用 `document_id`、`filename` 等字段；成功项仍需确认后才进入索引。

服务限制最多 10 个 URL。当前请求类型为 `list[AnyUrl]`，此模型没有完整声明“至少一个且仅 HTTP/HTTPS”的校验；Reader 还有自身 URL 校验。配置了 Jina Key 时先尝试 Jina，零成功结果时回退 Trafilatura；异常则返回整体失败，部分成功不会逐条补抓。当前上传调用没有写入原方案的 `source_url/source_type` 元数据。

文本导入由前端把粘贴内容封装为 `.txt` File，调用现有上传接口。依据：[URL 导入服务](../../../../aperag/service/document_service.py)、[请求响应模型](../../../../aperag/schema/view_models.py)、[URL 前端](../../../../web/src/app/workspace/collections/[collectionId]/documents/upload/import/url-import.tsx)、[文本前端](../../../../web/src/app/workspace/collections/[collectionId]/documents/upload/import/text-import.tsx)。来源元数据和其他扩展见[未实现规划](../planned/README.md)。

## 解析与分块

DocParser 包含 FAQTable、Image、Audio、MarkItDown，以及按配置使用的 DocRay/MinerU；按接受类型选择解析路径，不能由文件扩展名统一承诺某个服务必然处理。FAQ 条目有不再拆分的专门路径。解析还可产生图片资产和 PDF 页面图。

普通解析的默认分块配置是 `400/20`；图谱 LightRAG 子路径另有 `1200/100`。PDF、Word、表格、公式、图片及其关系是否保真，须使用实际样例验收。依据：[DocParser](../../../../aperag/docparser/doc_parser.py)、[FAQ Parser](../../../../aperag/docparser/faq_table_parser.py)、[解析任务实现](../../../../aperag/index/document_parser.py)、[配置](../../../../aperag/config.py)。

## 状态、版本与失败恢复边界

DocumentIndexManager 更新期望版本，reconciler 根据索引状态和版本差选择操作，用条件 UPDATE 认领；成功回调验证状态和 `target_version` 后推进 `observed_version`。解析后的多索引任务通过 group/chord 编排。索引成功状态是 `ACTIVE`，文档聚合成功状态是 `COMPLETE`；任一索引为 `FAILED` 时，文档整体状态会返回 `FAILED`。

当前可用调度实现是 Celery。PrefectTaskScheduler 方法抛出 `NotImplementedError`，属于占位。核心索引任务配置最多重试 3 次、固定 60 秒间隔；不同编排任务应按自身装饰器判断，不统一概括为指数重试。

Beat 的索引调谐周期为 3600 秒，同时业务服务会即时 `delay` 触发。周期任务并不承诺固定完成延迟或最终必定成功。调谐的条件认领与版本校验也不代表图谱和其他外部存储没有锁、已经实现跨进程原子写入。

依据：[索引管理器](../../../../aperag/index/manager.py)、[调谐器](../../../../aperag/tasks/reconciler.py)、[调度器](../../../../aperag/tasks/scheduler.py)、[任务配置](../../../../config/celery_tasks.py)、[Beat](../../../../config/celery.py)、[状态模型](../../../../aperag/db/models.py)。

任务重复、乱序、Worker 中断、存储失败和部分索引失败后还能否召回，都需要结合具体检索路径做运行验证。图谱机制见[知识图谱](knowledge-graph.md)，视觉路径见[检索与视觉索引](search-and-vision.md)。

原始材料：[上传](../pending-review/document_upload_design.md)、[索引架构](../pending-review/indexing_architecture.md)、[URL 与文本导入](../pending-review/url_and_text_import_design.md)。返回[当前说明目录](README.md)。
