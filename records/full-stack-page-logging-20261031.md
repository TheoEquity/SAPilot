# 页面操作与日志目录补验

日期：2026-10-31。按用户要求，在 `http://localhost:3000` 做一次上传和一次包含取消的聊天验证；发现取消误报后仅复验该步骤。

## 实际页面结果

- 浏览器通过既有本机账号登录，创建隔离测试知识库，使用真实文件选择器上传一个 PDF，点击 Add Documents 提交摄取；最终页面 Vector、Fulltext 均显示 Active。浏览器上传事件与 worker 的解析、页图、分块、两类索引事件使用同一 document ID；HTTP 结果与浏览器 trace ID 对应。
- 在新建聊天中通过输入框发送，观察流式开始，再点击停止按钮。页面恢复可发送状态，前端记录 submitted、started、cancelled；started 中的 message ID 与后端处理记录一致。
- 首次取消暴露：后端将 WebSocketDisconnect 记成失败并尝试向关闭的连接发送错误，随后又产生 RuntimeError。已在消息边界按 INFO/cancelled 处理断开，消费者原样上抛断开、外层正常结束；避免向关闭连接再发送错误，不写完成历史。新增回归测试先复现失败，修改后通过。
- 复验消息前后端 ID 一致，后端最终为 INFO/cancelled，未出现该消息的 failed 事件。取消停止页面接收；当前不会主动撤销已发出的外部模型调用，后端在后续写流检测到断开时结束，本次后端记录耗时约 36.8 秒。这不代表外部模型立即停止计算。
- 本次按用户要求控制页面测试数量，没有另开大量异常或回答质量用例。

测试对象：知识库 `col4737e148e19a7976`、文档 `docbf776ba42b4dfee7`、聊天 `chat60da360359193194`。截图、浏览器导出及核对结果保存在 `../SAPilot-data/logs/browser/2026-10-31/`，测试业务数据在取证后清理。

## 目录与配置

- 配置统一在 [`config/logging/`](../config/logging/)：`settings.json` 管目录、10 MB 单文件上限和 3 份备份；API 配置从旧启动脚本目录移至 `api.yaml`，搬迁时核验原始 SHA256，随后补文件输出并更新启动与说明引用。
- 默认输出为项目旁 `../SAPilot-data/logs/`；`SAPILOT_LOG_DIR` 可覆盖，相对路径以项目根为准。API 与 worker 原生 logging 增加安全轮转文件 handler，同时保留控制台；当前两容器已挂载该宿主目录。
- 本地前端通过 [`scripts/run-with-logs.mjs`](../scripts/run-with-logs.mjs) 保存 stdout/stderr 到 `frontend.log`；开发和启动入口引用该脚本。日志输出故障保留控制台与业务进程，保持子命令退出状态。浏览器 logger 改为单行 JSON，便于控制台导出和字段核对。
- `api.log`、`worker.log`、`frontend.log` 已实际落在统一目录。浏览器仍在控制台记录，按需导出到 `logs/browser/`，没有新建浏览器上报接口。首版三份诊断日志移至 `logs/verification/`，哈希清单一起保存，原导出脚本已改为新目的地；其他历史任务资料未批量改写。
- Docker Compose 为 API/worker 增加共享日志挂载；本机正在使用的两个测试容器保持原镜像、凭据、数据库和业务挂载，仅增加日志目录及更新 API 配置路径。旧容器配置快照保留在私有 runtime 目录。生产前端镜像仍使用其原有容器日志出口，本次没有验收生产镜像或构建流程。

## 验证与范围

- 后端日志、取消及文档追踪检查：26 项通过，包含新增目录覆盖、轮转保留上限与 WebSocketDisconnect 回归。
- 前端日志及输出脚本：5 项通过；TypeScript、前端 logger ESLint、后端公共日志模块 Ruff、Node 启动脚本语法检查通过。
- `docker compose config --quiet` 通过；API、worker、前端当前文件与浏览器证据已核对，测试正文和已知凭据未出现在普通服务日志中。
- 两个既有后端大文件的其他 Ruff 基线问题沿用[首版记录](full-stack-logging-20261031.md)，未扩展修复。没有声称全仓检查、生产构建、召回或回答准确率验收通过。未提交、未推送。
