# SAPilot 当前知识图谱构建与合并

> 状态：当前说明，依据 2026 年 10 月 29 日源码静态核对整理。未执行图谱任务或验证 SAP 实体、关系与召回效果。

## 构建路径与参数

Collection 启用 `enable_knowledge_graph` 后，图索引路径通过 manager 创建带 Collection workspace 的 LightRAG 实例，执行分块、提取、分组与合并，并在 manager 的 finally 路径释放存储。空文本可按零实体成功返回。

LightRAGConfig 的默认分块是 1200 tokens、重叠 100，LLM 最大异步数为 20，批大小为 32；这些只适用于该子路径，不能用于推定普通 Parser 参数或云机吞吐。manager 默认 `gleaning=0`，代码虽然保留补充提取能力，默认并不保证多轮提取。

依据：[图索引入口](../../../../aperag/index/graph_index.py)、[LightRAG manager](../../../../aperag/graph/lightrag_manager.py)、[提取与合并](../../../../aperag/graph/lightrag/operate.py)。

## 提取、分量与实际并发

`extract_entities` 对 chunk 创建任务，用 `Semaphore(llm_model_max_async)` 限制调用，并处理首个异常。实体与关系解析后，`_find_connected_components` 以无向邻接表做 BFS；`_grouping_process_chunk_results` 按分量筛选节点与两端都属于分量的边。

当前分组合并使用 `Semaphore(1)`。即使创建了多个异步任务，同一实例的分量合并仍受一并发限制；跨文档、跨实例的并发需要另行检查，不能从分量数推导吞吐倍数或 CPU 线性扩展。

依据：[LightRAG 主流程与分组实现](../../../../aperag/graph/lightrag/lightrag.py)、[实体提取实现](../../../../aperag/graph/lightrag/operate.py)。

## 实体、关系与摘要

当前合并主要按精确名称聚合。实体类型参考出现次数，描述、`source_id`、`file_path` 做去重与合并；关系端点排序后聚合，再按当前函数规则合并权重和信息。这不能保证任意语义别名或 SAP 标识自动归一。

描述摘要按片段数量触发，manager 默认阈值为 10；2000 是摘要输出 token 上限参数，不是描述达到 2000 tokens 就触发的阈值，也不保证固定压缩比或信息完全保留。依据：[合并与摘要实现](../../../../aperag/graph/lightrag/operate.py)、[参数构造](../../../../aperag/graph/lightrag_manager.py)。

## 锁与存储边界

实体和关系的锁名称包含 workspace；公共锁管理器默认使用 `threading` 类型。合并主要逐实体、逐边 upsert 图与向量数据，不能视为全批次数据库事务或跨存储原子提交。依据：[锁管理器](../../../../aperag/concurrent_control/manager.py)、[合并实现](../../../../aperag/graph/lightrag/operate.py)。

workspace、锁和版本存在不等于跨 Worker 隔离、故障恢复或权限边界已验收。图存储后端可配置；实体规模阈值、建库耗时、内存及倍数提速不沿用旧稿数值作为当前结论。

旧方法名、旧并行说明和未证实性能数据见[历史差异](../historical/superseded-design-notes.md)；动态批处理、优先级与分量缓存见[未实现规划](../planned/README.md)。

原始材料：[图索引](../pending-review/graph_index_creation.md)、[连通分量优化](../pending-review/connected_components_optimization.md)、[实体提取与合并](../pending-review/lightrag_entity_extraction_and_merging.md)。返回[当前说明目录](README.md)。
