# 前后端关键流程日志实施与验证

日期：2026-10-31。目标是统一日志入口、先覆盖关键流程，便于定位失败，不增加日志平台、依赖或一套新的关联 ID。

本记录保留首版验证范围；后续实际页面补验、取消日志修正及目录集中配置见[页面与日志目录补验](full-stack-page-logging-20261031.md)。首版三份原始日志已核验 SHA256 后移至 `../SAPilot-data/logs/verification/full-stack-logging/2026-10-31/`，脚本及结构化验证结果仍在原私有 runtime 目录。

## 实施范围

- 前端入口为 [`web/src/lib/logger.ts`](../web/src/lib/logger.ts)：浏览器和 Next.js 共用 `debug/info/warn/error`，输出受控字段，过滤正文、异常消息、完整对象和 URL 查询串；生产默认不打印 debug，输出失败不抛给业务。
- 浏览器和 Next.js 的现有 Axios 客户端共用 [`web/src/lib/api/logging.ts`](../web/src/lib/api/logging.ts)，记录请求结果、耗时、状态码及响应中的已有 trace ID，保留原响应和原异常。取消记 INFO，校验类响应记 WARNING，网络或服务器失败记 ERROR。
- 页面关键事件覆盖知识库文档上传、提交摄取，以及聊天发送、流式开始/结束、取消、协议解析和连接异常。上传完成只表示 uploaded，提交摄取只表示 submitted，不报成后台完成。不逐 Token、渲染或上传进度打印。
- 后端仍用 Python `logging`。[`aperag/logging.py`](../aperag/logging.py) 提供 JSON 格式、上下文及阶段日志；Uvicorn 与 Celery 使用同一格式，worker 主进程和 solo 模式均接入。HTTP 中间件不缓冲请求或流式响应，也不接管 WebSocket。
- 后端关键事件覆盖 HTTP 结果、聊天消息处理、文档解析、Office 转换、PDF 页图提取、分块、索引及文档任务重试/最终失败。保留原业务返回、异常、重试次数和状态更新方式。

有有效 OTel 上下文时自动复用 trace ID，HTTP 响应附带 `X-Trace-ID`；没有时不另生成 ID。摄取跨阶段使用 document ID，聊天使用已有 message ID；WebSocket 的 start/stop `id` 对应消息 ID，前端按 message_id 记录。重试事件仅补 Celery 原生 task ID 和重试次数。文档各阶段可以属于不同 trace，通过 document ID 关联。

## 脱敏与输出边界

后端只输出允许字段；异常链保留类型、文件名、行号及函数，不保留异常消息、源码行、局部变量或完整本机路径。已知转换依赖缺失可以保留依赖分类。

旧日志的任意自由文本、格式参数和 Celery 完整任务结果不原样输出，统一显示为 `application.log`，保留级别、模块、代码位置及允许字段/异常链。本次关键流程已改为明确事件名，其他旧日志尚未逐条迁移，因此历史自由文本的具体描述不能再直接从新输出读取。

浏览器日志仍在开发者工具控制台，Next.js 日志在服务进程，API/worker 日志在各自标准输出。Langfuse 继续承担现有调用链与模型观测；本次没有接入浏览器集中上报或新增存储。查看方法见[开发环境说明](../specs/development-guide.md#本地日志查看与排查)。

## 实际验证

| 检查 | 结果 |
| --- | --- |
| 应用日志、文档追踪和 Langfuse 导出契约测试 | 26 项通过；包含并发上下文隔离、关闭追踪仍产生日志、原异常保持、取消分类、流式响应保持、复用 trace、输出故障不影响业务、重试钩子及敏感字段过滤 |
| Office 转换与 PDF 摄取回归 | 6 项通过 |
| 前端 logger 与 Axios 日志测试 | 4 项通过；覆盖服务器/浏览器标识、生产 debug、实际本地 HTTP 成功/失败、取消及网络异常保持 |
| 原前端 Mock 接口回归 | 2 项通过 |
| TypeScript、涉及前端源文件 ESLint | 通过 |
| 新日志模块及直接涉及的后端文件 Ruff | 通过；两个历史文件的基线问题见下文 |
| Git diff 空白检查 | 通过 |

已在本地真实 API、Celery worker、数据库、对象存储、向量及全文服务上执行：

1. 无效请求返回 400，API 日志状态与响应 trace ID 一致，URL 查询串中的测试标记未进入日志。
2. 小型旧 DOC 完成转换、解析、分块和两类索引；PDF 完成页图/OCR、解析、分块和两类索引。两份状态均为 COMPLETE，向量和全文索引均 ACTIVE；按 document ID 能取得各阶段事件、耗时和 trace。
3. 损坏 PDF 产生解析失败及底层 PdfiumError 异常链，观察到原生任务的 retrying 和最终 failed 事件，最终文档及两类索引均 FAILED。保留原有三次重试策略。
4. 真实 WebSocket 聊天收到 start、流式 message、stop；后端 started/completed 的 message ID 和 trace ID 一致，完成事件包含耗时。本次验证的是流式处理及日志，不是回答准确率验收。
5. 所检查 API/worker 普通日志未包含测试正文、API key 或会话凭据。临时知识库删除返回 200，临时聊天删除返回 204。

原始证据与运行脚本保留在项目旁私有数据目录 `../SAPilot-data/runtime/full-stack-logging/2026-10-31/`，不提交 Git。

## 限制与后续

- 没有进行真实浏览器页面点击验收或生产构建；前端验证范围为日志/请求测试、Mock 回归、类型与 ESLint。真实运行验证覆盖 API、后台摄取和 WebSocket。
- `agent_chat_service.py` 全文件 Ruff 有 4 项、`config/celery_tasks.py` 有 15 项问题；与 Git HEAD 对比，规则与对象一致，包含既有未定义名称及导入问题。本次不扩展修复这些无关问题，不能宣称全仓静态检查通过。
- 没有全仓替换日志或重新验收七份原始材料、检索指标和回答指标。后续功能维护继续按[日志规约](../specs/logging-and-diagnostics.md)补相关事件。当前改动未提交、未推送。
