# 第二阶段：Langfuse 监控与既有用例复跑

日期：2026-10-30。用户已明确统一使用已有 Langfuse，要求先接入、复跑原用例并核对收数，再清理 Jaeger。本轮已按此顺序执行；业务路由和 Prompt 未修改。

## 材料与范围

原“测试用例”的 7 份原件位于项目旁 `../SAPilot-data/sources/internal/`；历史四技能批次实际入库 5 份。本轮继续使用这 5 份：FAQ DOCX、Min.pdf、性能自检表 XLSX、ABAP代码29.docx、SAP开发自测规范 DOCX。文件大小与 SHA256 已和原清单核验，没有为凑数量另选材料。

- 摄取：沿用隔离测试库 `colde5295f20dc4cad1`，对同 5 份原件执行真实重新解析及向量、全文索引更新。
- 问答：沿用原 Bot `bot9172fba8dd6207b4` 和原四个业务知识库，不改变其配置。
- 测试输入：原 `e2e-v2-results.json` 的 5 单轮、`multiturn-fixed-results.json` 的 10 多轮，以及 `retrieval-checks.json` 的 8 个检索检查；未新编问题。
- 多轮前 9 轮共用会话，第 10 轮另起会话；问题、预期 Skill、请求字段和路由/stop 断言沿用原入口。

## 接入与改动

复用本机已有 Langfuse **4.70.1**、项目 **SAPilot Baseline**（项目 ID `sapilot-baseline`）；入口 `http://localhost:3300`。项目 API 鉴权与真实观测回读均通过，没有另建 Langfuse 实例、数据库或项目。

- [OpenTelemetry 初始化](../aperag/trace/telemetry.py)：使用现有 OTLP/HTTP exporter，项目 keys 通过 Basic Auth 鉴权，并发送 Langfuse v4 ingestion header。
- [观测映射](../aperag/trace/langfuse.py)：传播会话与用户标识，标记工具观测，将模型选择和字符串转换包装步骤保持为普通 span，避免重复计为模型生成。
- [Agent 会话](../aperag/agent/agent_session_manager.py)复用应用 Provider，启用 MCP 的详细追踪标志，让 SDK 记录模型 Token 用量；没有创建第二个 Provider 或重复 exporter。[消息入口](../aperag/service/agent_chat_service.py)设置会话标识。
- [文档追踪](../aperag/trace/document.py)保留解析、索引创建/更新/删除的标识、耗时和状态；业务返回失败和抛异常均标为错误，新增文档 span 不携带正文、异常文本或堆栈。
- [配置示例](../envs/env.monitoring-local.template)、通用环境模板、Docker overrides 和本机私有 `.env` 已统一 Langfuse。说明见[开发指南](../specs/development-guide.md#本地-langfuse-监控)。

`OPIK_SENTRY_ENABLE=False` 保持在启动环境中：已从安装源码与真实进程核实，Opik 的可选 Sentry 错误上报会接管追踪采样，导致业务完成却不导出 span。此处通过环境配置处理。

实际生成模型仍为已有测试配置 `deepseek-flash`，Embedding 为 `text-embedding-v4`（1024 维）；未变更产品后续模型选型。Langfuse 中该模型没有价格配置，费用为空，不作为零费用报告。

## 实际验证结果

以下为启用详细用量、完成观测映射和 flush 修复后，清理 Jaeger **之前**的完整复跑；监控结果由 Langfuse v2 Observations API 实际回读，保留了有截止时间的查询窗口。

| 检查 | 结果 | 结论范围 |
| --- | --- | --- |
| 同 5 份原件重新解析与索引 | 5/5 COMPLETE；向量、全文各 5 个 ACTIVE | 真实后台任务，未扩展语料 |
| 文档观测 | 5 个成功 parse、10 个成功 index.update | 标识、耗时及状态均可读取 |
| 异常观测 | 不存在文档的 parse 为 ERROR，原异常为 DocumentNotFoundException | 无写入的直接调用探针，不代表真实文件失败或 Celery 重试验收 |
| 原 5 单轮 | 路由及 stop 断言 5/5 | 均有引用，未自动验收所有答案事实 |
| 原 10 多轮 | 路由及 stop 断言 7/10 | 第二步、第三步解释及制度追问误路由到 basic_qa；无协议 error |
| 原 8 检索检查 | Hit@1=5/8，Hit@3=8/8，Hit@5=8/8，MRR=0.8125 | 必要词和来源 ID 检查；Markdown 转义按等价文本匹配，不等同完整证据集合 Recall |
| 对话观测 | 15 条消息根观测、30 个模型生成观测 | 全部生成记录有模型、Token 用量及会话标识，并关联到对应消息 trace |
| 工具与检索 | 128 个工具观测、32 个检索 HTTP 请求观测 | 工具观测含嵌套执行层，不能把 128 当作独立实际搜索次数；32 包括问答检索和 8 条独立检查 |
| 用量 | 上述 30 个生成观测合计 193,514 Tokens | 有界测试窗口的实际回读，非成本、容量或速度验收 |
| 自动检查 | 17 passed；追踪模块及新增测试 Ruff 检查通过 | 真实 SDK/OTLP 传输配合本地 collector 替身，另有真实 Langfuse 集成证据 |

同套多轮输入在此前运行出现过 7/10 和 8/10；没有将一次八成升级为稳定达标。已核实意图路由装载历史后仍以 `use_history=False` 请求模型，运行容器的 MCP 适配器仅在该标志为真时发送历史。这能解释追问上下文不足；未取得各次路由模型原始文本，不宣称唯一原因。本轮没有修复这项业务问题。

## Jaeger 清理及清理后验证

在上述监控回读检查全部通过后：

- 删除 `aperag-jaeger` 容器及 `jaegertracing/all-in-one:1.60` 镜像。
- 删除 Compose 服务/profile、Makefile 启动和停止选项、Jaeger exporter、Settings 字段及环境变量。
- 从依赖清单与锁文件移除 3 个 Jaeger exporter 包及其独占的 thrift 依赖；其他库版本保持不变。锁文件同步项目已有版本元数据，`uv lock --check --offline` 通过。
- 删除过时的 Jaeger 操作指南，同步当前组件说明中的部署描述。高层架构已采用 Langfuse，本轮未重写其他架构内容。
- `web/yarn.lock` 中仍有 Redocly → OpenTelemetry SDK 带入的 `propagator-jaeger` 传递协议库；未修改这一前端依赖链。它不是 Jaeger 服务或应用的 Jaeger exporter。

清理后重新创建本轮 API 和 worker，仅连接原应用 Docker 网络，通过已验证的 Docker Desktop host gateway 访问 Langfuse；不再依赖额外的 Langfuse 容器网络连接。

清理后再次执行原 5 单轮：**5/5**；从 Langfuse 回读 **5 条消息、10 个带模型/Token/会话的生成观测**。另对原 ABAP 文档重新解析及索引，状态 COMPLETE、两个索引 ACTIVE；回读到 **1 个成功 parse、2 个成功 index.update**。另一个不存在文档的探针正确记录 ERROR，provider flush 返回 True。没有 Jaeger 容器时上述链路继续收数，Compose 配置校验通过。

本次复用已有业务镜像并挂载最新源码，没有重建完整业务镜像；旧镜像缓存没有批量清理。前一轮 Jaeger 记录和原始证据保存在私有运行资料中，作为历史，不作为当前启动说明。

## 证据、复跑与边界

以下路径以项目旁 `../SAPilot-data/` 为基准；凭据、正文、日志与原始评测不提交 Git：

- `runtime/phase2-monitoring/2026-10-30/langfuse/verified-single/`、`verified-multiturn/`：最终完整原用例、逐帧结果及输入来源哈希。
- 同目录 `verified-observations.json`、`verify-observations.py`：有界窗口的 Langfuse 回读检查、观测 ID、trace ID、状态与指标；不保存模型正文。
- 同目录 `retrieval-rerun.json`：原 8 个检索检查及结果。
- 同目录 `post-cleanup-single/`、`post-cleanup-proof.json`：Jaeger 清理后的原单轮及监控回读证据。
- 同目录 `runtime.env` 与认证文件：本机私有配置，不输出密钥。

原问答复跑入口保持为：

```powershell
& ../SAPilot-data/evaluations/four-business-skills/rerun-existing-tests.ps1 -Suite single
& ../SAPilot-data/evaluations/four-business-skills/rerun-existing-tests.ps1 -Suite multiturn
```

文档任务目前按文档 ID 关联，尚未实现 API 到 Celery 的父子 trace 传播、队列等待及回调耗时；本轮只验证 solo worker、并发 1。原件非空 Markdown、分块和图片链接曾做回读，但未逐图人工验收。质量、速度、并发、百份资料及图文关系不因监控收数而自动达标。

本轮未提交或推送，既有无关未提交改动保留。

## 阶段结项确认

2026-10-31，用户确认第二阶段基础目标结项，进入第三步样本与复杂题集制作。追问路由问题保留为后续待修项，暂不修复，也不作为进入第三步的前置条件。结项不改变本记录的原始测试结果、观测边界与质量未达标结论；整体阶段状态统一记录在[开发计划](development-roadmap.md)。
