# 全量接口运行检查

日期：2026-10-30（America/New_York）。首次检查按运行服务实际导出的 OpenAPI 清单逐项检查，范围为 **138 个 HTTP 操作**，另外验证 WebSocket 的 Agent 与普通 Flow 分支。首次检查未修改业务代码；随后按用户要求修复，结果见下节。未提交或推送。

## 后续修复与定向复验

原 10 个失败 HTTP 操作中，**9 个对应缺陷已修复并实际请求复验；1 个 OpenAI 兼容操作仍未实现，现明确返回 501**。原 6 个受限操作未补齐业务前提，仍保留受限结论。下面原始 138 项矩阵保留首次结果；本次没有重新完整请求其余 122 个操作，不将新旧结果合称为一次新的全量验收。

| 修复对象 | 改动与本次运行证据 |
| --- | --- |
| Flow Bot 创建、更新、读取与删除 | 配置按 JSON alias 保存；读取时兼容旧 `schema_`。创建、修改、列表和回读 200；对本轮 Bot 定向构造历史字段格式后，读取仍为 200、删除 204、再次读取 404 |
| 删除用户 | 使用请求的数据库 session 调用仓储并提交。独立测试用户删除 200、数据库确认不存在、重复删除 404；原管理员自删除仍被 400 拒绝 |
| 审计日志 | 响应类型补齐数据库已有资源枚举。默认列表、invitation 过滤及该记录详情均为 200 |
| 知识库摘要触发 | 服务支持数据库 JSON 配置及 API 的 CollectionConfig。接口 200，数据库摘要记录为 PENDING、version=2；只验证触发与保存，不声称后台最终摘要生成完成 |
| 题集及问题三个写入接口 | QuestionType 转换为底层字符串。显式 USER_DEFINED 创建题集、追加问题和 FACTUAL 更新均为 200，并验证保存回读 |
| 评测问答 | 使用当前用户默认 Agent 的编排及 Prompt。原 ABAP 用例得到真实回答；后台单题评测与 item 均 COMPLETED，回答 1487 字符、judge=5，未返回固定缺编排文本。单题评分不代表总体准确率或 80% 目标达标 |
| OpenAI 兼容占位 | 改为 HTTP 501，运行确认错误消息明确未实现；不能计作正常 completion 通过 |

评测沿用现有 Bot、模型和原用例。评测请求的模型不会覆盖 Skill runtime 原有优先级；本轮默认 Bot 的相关 Skill 已配置为现有 DeepSeek 模型。没有增加 Bot 选择参数或另建问答流程。

普通 Flow WebSocket 补齐缺失 import，并修复无附件消息将 `files=None` 传入历史模型的问题。后续运行可完成 start/references/stop，但一次没有正文；原始模型流核对发现该 Flow 的 1000-token 额度耗尽（finish_reason=length），新请求只有 reasoning delta、没有正文，缓存回放也没有正文。**普通 Flow 的完整回答仍未通过**，未以结束事件冒充业务成功，也未为此改动模型选型、全局缓存或整个模型调用层。下一步若继续维护该旧分支，需要针对输出预算及缓存返回做独立处理。

验证：`python -m pytest tests/contract -q` 实际 **136 passed**；新增回归覆盖真实模型或方法，数据库、模型流与 Redis 等 IO 的替身范围在测试文件注明，另以上表真实请求交叉验证。改动文件 Ruff 通过；Agent 聊天服务原有 4 项 Ruff 问题经 HEAD 对照确认未新增。`git diff --check` 通过。运行服务重新导出仍为 138 个 HTTP 操作，Orval 重新生成成功，生成文件无差异。

本轮临时用户、知识库、Bot、会话、题集和评测已清理；原默认 Bot 保留。对首次检查前已有未提交文件逐一核对哈希，仅本轮授权修改的 `agent_chat_service.py` 发生变化，原监控修改保留。架构、规约和 README 本轮未改。原始请求、回归状态及模型流元数据保存在旁侧数据目录的 `runtime/api-full-verification/2026-10-30/repairs/`。

受限项后续分别处理：标题生成配置后台任务默认模型；两个 MinerU 检查提供有效 token；Rerank 配置可用重排模型凭据；钉钉准备授权的测试渠道和签名回调；图谱 action 准备本轮资源内可操作的合并建议。当前没有替用户新增公共模型凭据、发送钉钉消息或伪造有效建议来消除限制。

## 首次检查结果与判定

| 结果 | HTTP 操作数 | 含义 |
| --- | ---: | --- |
| PASS | 122 | 本轮合法请求及对应响应、保存回读或状态转换检查通过 |
| FAIL | 10 | 存在真实合法场景失败；同一接口另一个场景通过不覆盖失败，含 1 个明确未实现的接口 |
| BLOCKED | 6 | 已发请求，但缺少凭据、配置或业务数据前提，未声称正常业务路径通过 |
| 未请求 | 0 | 138 个操作均有本轮实际请求记录 |

403 权限保护、缺参数的 422、无资源的 404 不计作业务 PASS；HTTP 200 若只是固定错误文本也判为未通过。另测的 Agent WebSocket 正常，普通 Flow WebSocket 失败。这是接口级运行检查，不等同全部参数组合、权限边界、负载或答案质量验收。

共保存 **469 条请求/事件验证记录**：root 122 条、Bot/聊天 282 条、评测 65 条；部分轮询另有状态证据，以上不是所有网络包的数量。测试请求使用本轮独立资源与既有模型，知识文件和问答复用原材料、原用例；网页读取与 URL 导入另以已在来源清单中的公开 SAP Help URL 验证相应接口。

## 未通过的接口与原因

| 操作 | 本轮实际问题 | 定位依据 |
| --- | --- | --- |
| `POST /api/v1/bots` | 合法 Flow 配置创建返回 400，但事务已创建 Bot，并可能影响后续列表响应 | [Bot Service](../aperag/service/bot_service.py)序列化未使用 schema alias，保存了 `schema_`，响应解析需要 `schema` |
| `DELETE /api/v1/bots/{bot_id}` | 删除上述 Bot 返回 400，但事务实际已删除 | 同一 Service 在删除提交后仍解析错误配置构建响应；普通 Agent Bot 删除已通过 |
| `DELETE /api/v1/users/{user_id}` | 管理员删除本轮测试用户返回 500 | [认证路由](../aperag/views/auth.py)传入 `session, target`；[用户仓储](../aperag/db/repositories/user.py)的实例方法接收 `user` |
| `GET /api/v1/audit-logs` | 默认查询遇到 invitation 审计记录返回 400；按 collection 过滤可成功 | [审计路由](../aperag/views/audit.py)返回模型的 resource_type 枚举不含 invitation，实际审计记录可以生成该类型 |
| `POST /api/v1/collections/{collection_id}/summary/generate` | 合法知识库请求返回 400，提示解析配置时拿到 CollectionConfig 而非 JSON | [摘要服务](../aperag/service/collection_summary_service.py)按数据库对象处理路由传入的视图模型 |
| `POST /api/v1/question-sets` | 显式传入合法 USER_DEFINED 类型返回 500 | [题集服务](../aperag/service/question_set_service.py)将 QuestionType RootModel 直接写入 SQL Enum；实际日志为 expected str, got QuestionType |
| `POST /api/v1/question-sets/{qs_id}/questions` | 显式传入合法 USER_DEFINED 类型返回 500 | 同上；省略类型可完成相应 CRUD，但不覆盖显式类型失败 |
| `PUT /api/v1/question-sets/{qs_id}/questions/{q_id}` | 显式传入合法 FACTUAL 类型返回 500 | 同上；省略类型的更新和保存回读通过 |
| `POST /api/v1/evaluations/chat_with_agent` | 返回 200，但回答是固定的“缺少 Bot 编排配置”文本 | [Agent 聊天服务](../aperag/service/agent_chat_service.py)的评测调用没有将 bot_config 传入执行流程 |
| `POST /v1/chat/completions` | 返回错误对象，不能产生真实 completion | [兼容路由](../aperag/views/openai.py)明确仍为未实现占位 |

额外 WebSocket 问题：普通 Flow 分支发送消息后返回 `name 'uuid' is not defined`，见[聊天服务](../aperag/service/chat_service.py)。Agent 分支真实问答、附件关联及历史持久化通过。

## 有前提限制的 6 个接口

- 聊天标题生成：现有用户没有可用的后台任务默认模型，返回 400；未为了标题测试修改原模型凭据或选型。
- 两个 MinerU token 检查接口：没有有效配置 token，分别核对到缺 token 的拒绝路径，未完成真实凭据校验。
- Rerank：现有重排模型没有配置可用凭据，实际请求验证到配置拒绝路径。
- 钉钉 POST callback：空请求连通，缺少带签名的真实外部回调及对应配置，未发送任何钉钉消息。GET/HEAD 探活通过。
- 图谱合并建议 action：本轮实际生成的建议集合为空，没有可操作 suggestion_id；无效 ID 的拒绝不能作为正常 action 通过。图谱读取、导出、生成建议及对真实节点直接合并已通过。

默认模型设置接口已验证标签写入及底层模型回读，并恢复原标签；因用户没有该公共供应商的有效凭据，有效默认模型查询仍可能为空，不据此宣称标题或重排依赖已可用。

## 评测后台及环境

初次评测后台无法连接 API：worker 未配置 `APERAG_API_BASE_URL`，容器内默认 `http://localhost:8000` 指向 worker 自身。本轮只修正专属测试 worker 的运行环境为 `http://sapilot-stage2-api:8000` 并重新创建 worker，没有改业务代码或其他部署。

窄重试后，评测及唯一 item 实际达到 COMPLETED，但得到的 rag_answer 仍是缺少编排的错误文本，judge 给出 1。因此 **状态完成和评分数字均不能替代问答正确性验收**，`chat_with_agent` 仍判 FAIL。

## 资源、配置与证据

所有写入与删除以独立前缀和明确资源 ID 限定。临时知识库、文档、Bot、会话、题集和评测完成回收；测试用户删除接口失败后，只对该明确测试账号及其自动生成、禁止 HTTP 删除的默认 Bot 做定向数据清理，未把该清理当作接口通过。审计、已完成导出任务及软删除历史按系统规则保留。

全局 Settings 原始行、默认配额、原 Prompt 和公共模型标签已核对恢复；原文件下载、对象读取及共享对象读取的 SHA256 与原 ABAP 文档相同。原有未提交文件的哈希保持不变。

原始结果在项目旁 `../SAPilot-data/runtime/api-full-verification/2026-10-30/`，不提交 Git：

- `coverage.json`、`coverage.csv`：逐操作结果及证据来源；下面的清单由同一结果生成。
- `root-*`、`bots-*`、`eval-*`：请求、响应、场景断言、资源清单与后台日志；认证材料保持私有，日志不输出认证头。
- `fixture-corrections.json`：测试脚本返回字段断言等纠正依据，避免将脚本误判当成业务缺陷。
- `preservation-checks.json`、`global-settings-restored.json`、`model-tag-restoration.json`、`native-cleanup.json`：原状态恢复和定向清理证据。

下一步按上述失败接口修复并复跑对应场景；本轮没有通过放宽校验、修改原题或改业务代码来使结果变绿。

## 138 个 HTTP 操作清单

| 方法与路径 | 结果 | 实际返回码 |
| --- | --- | --- |
| `DELETE /api/v1/apikeys/{apikey_id}` | PASS | 200 |
| `DELETE /api/v1/bots/{bot_id}` | FAIL | 204, 400, 403 |
| `DELETE /api/v1/bots/{bot_id}/chats/{chat_id}` | PASS | 204 |
| `DELETE /api/v1/collections/{collection_id}` | PASS | 200 |
| `DELETE /api/v1/collections/{collection_id}/documents` | PASS | 200 |
| `DELETE /api/v1/collections/{collection_id}/documents/{document_id}` | PASS | 200 |
| `DELETE /api/v1/collections/{collection_id}/searches/{search_id}` | PASS | 200 |
| `DELETE /api/v1/collections/{collection_id}/sharing` | PASS | 204 |
| `DELETE /api/v1/evaluations/{eval_id}` | PASS | 204 |
| `DELETE /api/v1/llm_providers/{provider_name}` | PASS | 200 |
| `DELETE /api/v1/llm_providers/{provider_name}/models/{api}/{model}` | PASS | 200 |
| `DELETE /api/v1/marketplace/collections/{collection_id}/subscribe` | PASS | 200 |
| `DELETE /api/v1/prompts/user/{prompt_type}` | PASS | 200 |
| `DELETE /api/v1/question-sets/{qs_id}` | PASS | 204 |
| `DELETE /api/v1/question-sets/{qs_id}/questions/{q_id}` | PASS | 204 |
| `DELETE /api/v1/users/{user_id}` | FAIL | 500 |
| `GET /api/v1/apikeys` | PASS | 200 |
| `GET /api/v1/audit-logs` | FAIL | 200, 400 |
| `GET /api/v1/audit-logs/{audit_id}` | PASS | 200 |
| `GET /api/v1/bots` | PASS | 200 |
| `GET /api/v1/bots/{bot_id}` | PASS | 200 |
| `GET /api/v1/bots/{bot_id}/chats` | PASS | 200 |
| `GET /api/v1/bots/{bot_id}/chats/{chat_id}` | PASS | 200 |
| `GET /api/v1/bots/{bot_id}/flow` | PASS | 200 |
| `GET /api/v1/chats/{chat_id}/documents/{document_id}` | PASS | 200 |
| `GET /api/v1/collections` | PASS | 200 |
| `GET /api/v1/collections/{collection_id}` | PASS | 200 |
| `GET /api/v1/collections/{collection_id}/documents` | PASS | 200 |
| `GET /api/v1/collections/{collection_id}/documents/staged` | PASS | 200 |
| `GET /api/v1/collections/{collection_id}/documents/{document_id}` | PASS | 200 |
| `GET /api/v1/collections/{collection_id}/documents/{document_id}/download` | PASS | 200 |
| `GET /api/v1/collections/{collection_id}/documents/{document_id}/object` | PASS | 200 |
| `GET /api/v1/collections/{collection_id}/documents/{document_id}/preview` | PASS | 200 |
| `GET /api/v1/collections/{collection_id}/graphs` | PASS | 200 |
| `GET /api/v1/collections/{collection_id}/graphs/export/kg-eval` | PASS | 200 |
| `GET /api/v1/collections/{collection_id}/graphs/labels` | PASS | 200 |
| `GET /api/v1/collections/{collection_id}/searches` | PASS | 200 |
| `GET /api/v1/collections/{collection_id}/sharing` | PASS | 200 |
| `GET /api/v1/config` | PASS | 200 |
| `GET /api/v1/default_models` | PASS | 200 |
| `GET /api/v1/dingtalk/bot/callback` | PASS | 200 |
| `GET /api/v1/evaluations` | PASS | 200 |
| `GET /api/v1/evaluations/{eval_id}` | PASS | 200 |
| `GET /api/v1/export-tasks/{task_id}` | PASS | 200 |
| `GET /api/v1/export-tasks/{task_id}/download` | PASS | 200 |
| `GET /api/v1/invitations` | PASS | 200 |
| `GET /api/v1/llm_configuration` | PASS | 200 |
| `GET /api/v1/llm_provider_models` | PASS | 200 |
| `GET /api/v1/llm_providers/{provider_name}` | PASS | 200 |
| `GET /api/v1/llm_providers/{provider_name}/models` | PASS | 200 |
| `GET /api/v1/marketplace/collections` | PASS | 200 |
| `GET /api/v1/marketplace/collections/subscriptions` | PASS | 200 |
| `GET /api/v1/marketplace/collections/{collection_id}` | PASS | 200 |
| `GET /api/v1/marketplace/collections/{collection_id}/documents` | PASS | 200 |
| `GET /api/v1/marketplace/collections/{collection_id}/documents/{document_id}/object` | PASS | 200 |
| `GET /api/v1/marketplace/collections/{collection_id}/documents/{document_id}/preview` | PASS | 200 |
| `GET /api/v1/marketplace/collections/{collection_id}/graph` | PASS | 200 |
| `GET /api/v1/mcp_tools` | PASS | 200 |
| `GET /api/v1/prompts/system` | PASS | 200 |
| `GET /api/v1/prompts/user` | PASS | 200 |
| `GET /api/v1/question-sets` | PASS | 200 |
| `GET /api/v1/question-sets/{qs_id}` | PASS | 200 |
| `GET /api/v1/quotas` | PASS | 200 |
| `GET /api/v1/settings` | PASS | 200 |
| `GET /api/v1/system/default-quotas` | PASS | 200 |
| `GET /api/v1/user` | PASS | 200 |
| `GET /api/v1/users` | PASS | 200 |
| `GET /health` | PASS | 200 |
| `HEAD /api/v1/dingtalk/bot/callback` | PASS | 200 |
| `POST /api/v1/apikeys` | PASS | 200 |
| `POST /api/v1/available_models` | PASS | 200 |
| `POST /api/v1/backup/export` | PASS | 200, 403 |
| `POST /api/v1/backup/import/prompts` | PASS | 200, 403 |
| `POST /api/v1/backup/import/settings` | PASS | 200, 403 |
| `POST /api/v1/bots` | FAIL | 200, 400 |
| `POST /api/v1/bots/{bot_id}/chats` | PASS | 200 |
| `POST /api/v1/bots/{bot_id}/chats/{chat_id}/messages/{message_id}` | PASS | 200 |
| `POST /api/v1/bots/{bot_id}/chats/{chat_id}/title` | BLOCKED | 400 |
| `POST /api/v1/bots/{bot_id}/flow/debug` | PASS | 200 |
| `POST /api/v1/change-password` | PASS | 200 |
| `POST /api/v1/chats/{chat_id}/documents` | PASS | 200 |
| `POST /api/v1/chats/{chat_id}/search` | PASS | 200 |
| `POST /api/v1/collections` | PASS | 200 |
| `POST /api/v1/collections/test-mineru-token` | BLOCKED | 400 |
| `POST /api/v1/collections/{collection_id}/documents` | PASS | 200 |
| `POST /api/v1/collections/{collection_id}/documents/confirm` | PASS | 200 |
| `POST /api/v1/collections/{collection_id}/documents/fetch-url` | PASS | 200 |
| `POST /api/v1/collections/{collection_id}/documents/upload` | PASS | 200 |
| `POST /api/v1/collections/{collection_id}/documents/{document_id}/rebuild_indexes` | PASS | 200 |
| `POST /api/v1/collections/{collection_id}/export` | PASS | 202 |
| `POST /api/v1/collections/{collection_id}/graphs/merge-suggestions` | PASS | 200 |
| `POST /api/v1/collections/{collection_id}/graphs/merge-suggestions/{suggestion_id}/action` | BLOCKED | 400 |
| `POST /api/v1/collections/{collection_id}/graphs/nodes/merge` | PASS | 200 |
| `POST /api/v1/collections/{collection_id}/rebuild_failed_indexes` | PASS | 200 |
| `POST /api/v1/collections/{collection_id}/searches` | PASS | 200 |
| `POST /api/v1/collections/{collection_id}/sharing` | PASS | 204 |
| `POST /api/v1/collections/{collection_id}/summary/generate` | FAIL | 400 |
| `POST /api/v1/dingtalk/bot/callback` | BLOCKED | 200 |
| `POST /api/v1/embeddings` | PASS | 200 |
| `POST /api/v1/evaluations` | PASS | 200 |
| `POST /api/v1/evaluations/chat_with_agent` | FAIL | 200 |
| `POST /api/v1/evaluations/{eval_id}/pause` | PASS | 200 |
| `POST /api/v1/evaluations/{eval_id}/resume` | PASS | 200 |
| `POST /api/v1/evaluations/{eval_id}/retry` | PASS | 200 |
| `POST /api/v1/invite` | PASS | 200 |
| `POST /api/v1/llm_providers` | PASS | 200 |
| `POST /api/v1/llm_providers/{provider_name}/models` | PASS | 200 |
| `POST /api/v1/llm_providers/{provider_name}/publish` | PASS | 200 |
| `POST /api/v1/login` | PASS | 200 |
| `POST /api/v1/logout` | PASS | 200 |
| `POST /api/v1/marketplace/collections/{collection_id}/subscribe` | PASS | 200 |
| `POST /api/v1/prompts/preview` | PASS | 200 |
| `POST /api/v1/prompts/user/reset` | PASS | 200 |
| `POST /api/v1/prompts/validate` | PASS | 200 |
| `POST /api/v1/question-sets` | FAIL | 500 |
| `POST /api/v1/question-sets/generate` | PASS | 200 |
| `POST /api/v1/question-sets/{qs_id}/questions` | FAIL | 500 |
| `POST /api/v1/quotas/{user_id}/recalculate` | PASS | 200 |
| `POST /api/v1/register` | PASS | 200 |
| `POST /api/v1/rerank` | BLOCKED | 400 |
| `POST /api/v1/settings/test_mineru_token` | BLOCKED | 404 |
| `POST /api/v1/web/read` | PASS | 200 |
| `POST /api/v1/web/search` | PASS | 200 |
| `POST /v1/chat/completions` | FAIL | 200 |
| `PUT /api/v1/apikeys/{apikey_id}` | PASS | 200 |
| `PUT /api/v1/bots/{bot_id}` | PASS | 200 |
| `PUT /api/v1/bots/{bot_id}/chats/{chat_id}` | PASS | 200 |
| `PUT /api/v1/bots/{bot_id}/flow` | PASS | 200 |
| `PUT /api/v1/collections/{collection_id}` | PASS | 200 |
| `PUT /api/v1/default_models` | PASS | 200 |
| `PUT /api/v1/llm_providers/{provider_name}` | PASS | 200 |
| `PUT /api/v1/llm_providers/{provider_name}/models/{api}/{model}` | PASS | 200 |
| `PUT /api/v1/prompts/user` | PASS | 200 |
| `PUT /api/v1/question-sets/{qs_id}` | PASS | 200 |
| `PUT /api/v1/question-sets/{qs_id}/questions/{q_id}` | FAIL | 500 |
| `PUT /api/v1/quotas/{user_id}` | PASS | 200 |
| `PUT /api/v1/settings` | PASS | 204, 403 |
| `PUT /api/v1/system/default-quotas` | PASS | 200 |
