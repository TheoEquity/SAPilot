# SAPilot 接口、前端组件与配置字段盘点

> 状态：2026 年 10 月 29 日当前工作区的源码静态盘点。描述对应关系、确认的差异和验证边界；不修改业务代码、接口定义或生成产物，不代表运行验收或修复完成。

后续状态：本页保留实施前的盘点基线，不能将下列差异一概视为当前仍未修复。按批代码变更、独立审核与实际验证见[架构整理实施记录](../../../records/architecture-implementation-record.md)。

## 1 范围与结论

当前前后端已有 OpenAPI、生成 SDK、业务表单和后端模型，但定义、页面能编辑的字段、保存的配置与执行时读取的参数并未完全对齐。Bot、意图与 Skill 编辑共用 Bot 更新接口；聊天使用 WebSocket，另有直接 fetch 和资源 URL。架构拆分应保留这些实际关系，不能按页面名称假定独立接口。

| 盘点内容 | 本轮结果 |
| --- | --- |
| 主 OpenAPI 与生成 SDK | 各 127 个 HTTP 操作，方法/路径相对应；不代表载荷一致 |
| 后端静态挂载 | 137 个 HTTP 操作及 1 个 WebSocket，包含健康检查、独立 /v1 与 dev 测试接口；条件启用不等于实际启用 |
| 定义与实现的路径对应 | 126 个主定义操作找到实现，另 1 个为明确的 Doc Only 占位；HTTP 并集 138 行 |
| 前端 SDK 源码调用 | TypeScript AST 找到 147 个调用点，涉及 97 个 SDK 方法；30 个未发现前端直接调用，不能直接判为无用 |
| 组件与配置深查 | Bot、意图、Skill、画布、聊天、附件、Collection、检索、模型与 Prompt；其他 HTTP 操作列在附表作调用定位 |

完整路由、定义、后端函数、签名、SDK 方法与调用文件见[HTTP 接口对应表](http-api-component-matrix.md)。OAuth 工厂生成的子路由、FastAPI 自动文档和 MCP 协议内部工具不计入静态 HTTP 数；本轮也没有逐字段审计所有响应、分页、错误码或全部权限规则。

基线是本次当前工作区，包含既有未提交改动。证据以本页源码链接和附表为准；没有读取运行数据库、真实密钥或发起网络请求，也没有执行代码生成。未知项需要实际配置、请求与响应或隔离生成比较才能确认。

## 2 共同调用与保存方式

浏览器 `apiClient` 的 baseURL 为 `NEXT_PUBLIC_BASE_PATH + /api/v1`，默认超时 5 秒；服务器 `getServerApi` 使用 `API_SERVER_ENDPOINT + API_SERVER_BASE_PATH`，默认 15 秒，并传递 Cookie/Lang。部分业务调用另行覆盖超时，不能据默认值推定所有操作的截止时间。

BotConfigProvider 持有服务器配置快照。意图与 Skill 编辑器生成下一份 orchestration，交 `updateBotOrchestration` 调 `botsBotIdPut`；后端解析 BotUpdate 后以 `model_dump_json(exclude_none=True)` 序列化，并直接替换 `Bot.config`。这是一份配置快照的更新，不是仅修改某个 Skill 字段的 PATCH。

保存后前端调用 loadBot/刷新重新读取；运行中的 WebSocket 在连接建立后加载 Bot 配置与 Prompt，不能由保存响应推定旧连接已即时切换。多页面同时保存的合并行为尚未运行验证。

依据：[浏览器客户端][client]、[服务器客户端][server]、[配置 Provider][bot-provider]、[编排更新器][updater]、[Bot 路由][bot-view]、[BotService][bot-service]、[Agent 主路径][agent]。

## 3 页面、业务组件与接口对应

本表 HTTP 路径省略 `/api/v1`；基础 Button/Input 等不单独绑定业务接口。下列组件负责组合、编辑或调用，不据文件中存在调用就认定页面已运行可达。

| 页面 / 组件 | 调用接口或协议 | 后端与数据 | 源码入口 |
| --- | --- | --- | --- |
| Bot 设置、创建表单 | GET/POST /bots；GET/PUT /bots/{id}；POST /available_models | BotService；BotCreate/Update/config，默认 Bot 切换还会更新另一 Bot | [BotForm][bot-form]、[创建表单](../../../web/src/app/workspace/bots/new/bot-create-form.tsx)、[Bot 路由][bot-view] |
| IntentRouterEditor | GET /llm_configuration；经更新器 PUT /bots/{id} | 页面筛选 api=intent；保存 orchestration.intent_router | [意图编辑器][intent]、[更新器][updater] |
| SkillEditor | GET /collections；POST /available_models；GET /mcp_tools；经更新器 PUT /bots/{id} | Skill 与候选/兜底联动保存，不存在本轮已发现的独立 Skill CRUD 接口 | [Skill 编辑器][skill]、[工具列表](../../../aperag/views/main.py#L221) |
| FlowCanvasEditor / JSON 编辑 | onChange 更新父草稿，Skill 的 onQuickSave 还调用父组件保存逻辑 | 两个编辑器均 import flow-canvas-editor.tsx；V2 文件存在不代表被这两页使用。画布仍经 PUT Bot 保存 | [当前画布][canvas]、[Skill 父组件][skill]、[意图父组件][intent]、[JSON 编辑](../../../web/src/app/workspace/bots/[botId]/flow-json-editor.tsx) |
| BotProvider、聊天页面 | 会话列表/创建/修改/删除、历史 GET、标题 POST | ChatService；Chat/ChatDetails/history | [BotProvider](../../../web/src/components/providers/bot-provider.tsx)、[聊天页面](../../../web/src/app/workspace/bots/[botId]/chats/[chatId]/page.tsx)、[Chat 路由][chat-view] |
| ChatMessages / MessagePartsAi | WebSocket /bots/{id}/chats/{id}/connect；POST 消息反馈 | AgentMessage、实时事件、references 与 Skill 标签 | [消息组件][messages]、[AI 展示][ai-parts]、[事件类型][events] |
| ChatInput | POST /chats/{id}/documents；GET /chats/{id}/documents/{id} | 上传附件及轮询；发送文件 id/name/previewUrl | [输入组件][input]、[附件路由](../../../aperag/views/chat_documents.py) |
| CollectionForm | POST /available_models；POST /collections；PUT /collections/{id} | CollectionCreate/Update/config | [知识库表单][collection-form]、[Collection 路由][collection-view] |
| DocumentUpload | upload、staged、confirm | 文件暂存 UPLOADED，再确认入索引 | [上传组件](../../../web/src/app/workspace/collections/[collectionId]/documents/upload/document-upload.tsx)、[文档服务][document-service] |
| UrlImport / TextImport | POST documents/fetch-url 或 documents/upload | URL 返回 results；文本包装 File；两者复用确认 | [URL 导入](../../../web/src/app/workspace/collections/[collectionId]/documents/upload/import/url-import.tsx)、[文本导入](../../../web/src/app/workspace/collections/[collectionId]/documents/upload/import/text-import.tsx) |
| SearchTest | POST /collections/{id}/searches | SearchRequest 的多路召回配置，经动态 Flow 合并与重排 | [搜索组件](../../../web/src/app/workspace/collections/[collectionId]/search/search-test.tsx)、[CollectionService][collection-service] |
| ProviderActions / 模型配置 | /llm_configuration、/llm_providers、/available_models 及模型相关操作 | Provider、模型 api/tags、Key 和默认模型；具体逐项见附表 | [供应商操作](../../../web/src/app/workspace/providers/provider-actions.tsx)、[默认模型](../../../web/src/app/workspace/providers/models-default-configuration.tsx)、[LLM 路由](../../../aperag/views/llm.py) |
| PromptSettings / PromptCard | GET/PUT /prompts/user；DELETE 单项；POST reset | PromptTemplateService 保存默认模板；Agent 和索引接入程度不同 | [Prompt 页面组件][prompt-ui]、[Prompt 路由](../../../aperag/views/prompts.py) |
| 问题生成与评测页面 | question-sets 与 evaluations 操作 | QuestionSetService / EvaluationService；模型配置和逐题结果 | [问题生成](../../../web/src/app/workspace/collections/[collectionId]/questions/[questionSetId]/question-generate.tsx)、[评测创建](../../../web/src/app/workspace/collections/[collectionId]/evaluations/evaluation-create.tsx)、[路由](../../../aperag/views/evaluation.py) |
| BackupSettings | fetchWithAuth 调 backup/export、import/settings、import/prompts 和 Bot 创建/更新 | 备份由内联 Pydantic payload 处理；Bot 导入复用普通 Bot 接口 | [备份组件][backup-ui]、[备份路由](../../../aperag/views/backup.py) |

市场、图谱管理、导出、配额、审计、用户、设置等其余接口的直接调用组件均已纳入[附表](http-api-component-matrix.md)；这些模块的每个字段尚未做与编排相同深度的执行核对。

## 4 配置字段定义覆盖

| 配置 / 消息族 | OpenAPI 与前端类型 | 后端模型与现状 |
| --- | --- | --- |
| Bot.config.agent / flow | bot.yaml 和生成 BotConfig 有定义；agent 内 YAML 缺少当前 welcome_title/subtitle | Python Agent、BotConfig 及设置页有对应内容 |
| Bot.config.orchestration | bot.yaml 与生成 BotConfig 缺失；页面通过 BotConfigWithOrchestration 补充类型 | Python 有 IntentRouterConfig、SkillConfig、ReactFlowSchema 等 |
| Bot 默认/保护标记 | YAML 未列 is_default/is_protected；现有 SDK Bot 有两个标记，Create/Update 只含 is_default | Python Bot/Create/Update 均有两标记，不能直接用当前 YAML 覆盖生成 |
| AgentMessage | YAML/生成类型无 force_skill_id、action | Python 模型有，主路径会保留和使用；FAQ 前端使用 action |
| ChatMessage | YAML 无 faq_choice 枚举、options、skill_id；现有 SDK 有这些扩展 | Python ChatMessage 有 faq_choice/options，但无 skill_id；实时 BaseAgentResponse 有 skill_id |
| CollectionConfig | YAML、生成类型与 Python 已含索引开关、模型、index_prompts、knowledge_graph_config | 通用 CollectionForm 只编辑其中子集，字段存在不等于可编辑或执行已接入 |

依据：[Bot YAML][bot-yaml]、[Agent YAML][agent-yaml]、[Chat YAML][chat-yaml]、[Collection YAML][collection-yaml]、[后端模型][models]、[SDK BotConfig][sdk-bot-config]、[SDK Bot](../../../web/src/api/models/bot.ts)、[SDK BotCreate](../../../web/src/api/models/bot-create.ts)、[SDK BotUpdate](../../../web/src/api/models/bot-update.ts)、[SDK AgentMessage](../../../web/src/api/models/agent-message.ts)、[SDK ChatMessage](../../../web/src/api/models/chat-message.ts)、[编排自定义类型][types]。

## 5 Bot 与意图字段如何保存和执行

以下 `intent.*` 指 `config.orchestration.intent_router.*`。保存统一经 PUT Bot，后端解析为当前 Python 模型后替换 config；本表把“有字段/可保存”与“执行会读取”分列。

| 字段 | 编辑与保存 | 执行、展示或限制 | 依据 |
| --- | --- | --- | --- |
| title / description / is_default | BotForm 提交；默认切换可先清旧默认 | BotService 更新；切换不是单一多 Bot 事务的已验证保证 | [表单][bot-form]、[服务][bot-service] |
| agent.completion.{model,model_service_provider,custom_llm_provider} | BotForm 模型选择保存三字段 | AgentMessage 模型缺失时回退 Bot completion；Skill runtime 可再覆盖 provider/model | [表单][bot-form]、[执行][agent] |
| agent.system_prompt_template / query_prompt_template | BotForm 保存 | Bot → 用户 → 系统 → 硬编码解析，WebSocket 连接前准备 | [表单][bot-form]、[PromptService][prompt-service]、[Agent][agent] |
| agent.welcome_title / welcome_subtitle | BotForm 保存，YAML 还未同步 | 属于展示配置，不应当作模型指令；具体展示分支按页面核对 | [表单][bot-form]、[模型][models] |
| agent.collections | Python/YAML 支持；当前 BotForm 的提交 agent 对象没有带此字段 | BotService 校验该层资源；消息默认集合会先参与合并，再考虑 Skill 集合 | [表单][bot-form]、[服务][bot-service]、[执行][agent] |
| intent.id / name / description / meta | 编辑或生成；meta.updated_at 写入 | 定位与展示元数据，没有把这些项当成路由条件 | [意图编辑][intent]、[执行][agent] |
| intent.enabled | 有开关并保存 | 本轮所核对 process_agent_message 未用它作为路由启停条件 | [意图编辑][intent]、[执行][agent] |
| intent.mode | llm 或 rules+llm | rules+llm 先匹配规则，未命中再分类；显式指定 Skill 可绕过分类，但仍先经过配置完整性检查 | [意图编辑][intent]、[执行][agent] |
| intent.llm.provider / model | 页面筛 api=intent 并保存；后端要求两者存在 | 分类参数使用 model；session 的 provider/Key/base_url 来自合并后的 Agent completion，没有以 intent provider 重新构造；模型跨供应商是否可用待运行验证 | [意图编辑][intent]、[_get_agent_session / 分类][agent]、[会话管理][session] |
| intent.llm.temperature | 前端默认/编辑，Python 默认 0 | 分类 RequestParams 使用它，模型是否采纳待运行验证 | [意图编辑][intent]、[执行][agent] |
| intent.llm.max_tokens | 页面保存，Python 默认 1024 | 分类当前写死 maxTokens=512，没有传入该值 | [意图编辑][intent]、[模型][models]、[执行][agent] |
| intent.llm.top_p / timeout_ms | 类型和 Python 有；当前意图保存构造 llm 未带回 | 本轮分类参数未读取；已有值经此表单保存的保留情况需回读验证 | [类型][types]、[意图保存][intent]、[执行][agent] |
| intent.prompt_template | 页面保存且运行检查非空 | 替换 query/skills，再追加权威候选列表和精确 skill_id 输出规则 | [编辑][intent]、[执行][agent] |
| intent.confidence_threshold | 页面可编辑，Python 默认 0.6 | 当前只校验输出是否精确属于启用候选，不做置信度打分或阈值比较 | [编辑][intent]、[执行][agent] |
| intent.candidate_skills[].{skill_id,label,description,enabled} | 由 Skill 列表、画布与已有候选组合保存 | 分类描述与合法 ID 集合使用启用候选；并不等于所有执行入口统一验证 Skill.enabled | [编辑][intent]、[Skill 保存][skill]、[执行][agent] |
| candidate_skills[].examples | 画布 examples_text 与已有样例合并保存 | 当前分类构造的 skills_desc 只用 id/label/description，未展开 examples | [编辑][intent]、[执行][agent] |
| intent.fallback_skill_id | 编辑器和 Skill 的 is_fallback 联动保存 | 分类输出不合法时回退；引用的 Skill 是否存在还影响后续执行 | [意图][intent]、[Skill][skill]、[执行][agent] |
| intent.rules[].{rule_type,value,target_skill_id,enabled} | 页面保存规则 | try_hard_rules_match 处理启用规则的 keyword/regex；未命中进入模型分类 | [意图][intent]、[执行][agent] |
| intent.flow.{nodes,edges,viewport,version} | 画布/JSON 编辑并保存，节点样例参与候选构造 | 当前路由不按这张画布逐节点执行；不能与 Skill.flow 共用同一执行契约 | [意图][intent]、[执行][agent] |

后端 `validate_collections` 的保存校验仅针对 agent.collections；本轮该保存路径未见同等的完整 Skill 引用、规则目标、兜底和画布跨字段校验。执行阶段还有按用户查询资源的检查，不能据保存可通过就认定所有资源或连线有效。来源：[BotService][bot-service]、[Agent 执行][agent]。

## 6 Skill 与画布字段如何执行

以下路径均位于 `config.orchestration.skills[]`，通过同一个 Bot 更新保存。SkillEditor 同时更新 candidate_skills、fallback_skill_id 等关联配置；不能将保存操作按一个独立 Skill 资源来理解。

| 字段 | 编辑与保存 | 当前执行关系 | 依据 |
| --- | --- | --- | --- |
| id / name / description / meta | 表单保存，按 id 去重，meta 更新时间 | _execute_skill 以 id 查找，找不到返回提示；名称等不是另一套路由引擎 | [编辑][skill]、[执行][agent] |
| enabled / type / category | enabled/type 可编辑；当前 nextSkill 未带 category | _execute_skill 查找时没有统一按 enabled 过滤，也未按 type 切四套执行器；category 未见执行消费 | [编辑][skill]、[模型][models]、[执行][agent] |
| runtime.provider / model | 表单保存 | 覆盖合并后消息的 provider/model，查询对应 Provider 与 Key | [编辑][skill]、[执行][agent] |
| runtime.temperature / max_tokens | 表单保存，Python 默认 0.7/2048 | 传入 AgentConfig 与 RequestParams；没有可用 runtime/max_tokens 时函数另有 8192 兜底 | [模型][models]、[执行][agent] |
| runtime.top_p / timeout_ms | 类型和 Python 有；nextSkill.runtime 未带回 | 当前动作 RequestParams 未传这两项；回读保留和实际生效需分别验证 | [编辑][skill]、[执行][agent] |
| prompts.skill_prompt | 表单保存 | 追加到解析后的基础 system prompt，节点 prompt 另行组合 | [编辑][skill]、[执行][agent] |
| collections[].id | 表单选择集合，保存 ID 列表 | 合并后消息集合仍为空时才注入 Skill 集合；此前消息或 Bot 默认集合已可能占先 | [编辑][skill]、[执行][agent] |
| tools[].{tool_id,enabled} | 表单 Zod 只接收这两项 | 启用工具与动作节点 data.tools 取并集；附件还可加入 search_chat_files；空集合时传 tool_filter=None，不能按 UI 推定严格“禁止所有工具” | [编辑][skill]、[执行][agent] |
| tools[].{required,timeout_ms,retry_count} | 自定义/Python 类型有，当前表单工具 schema 和保存不带这些项 | 本轮 Skill 绑定执行路径未按这些配置实行必用、超时和重试策略 | [类型][types]、[编辑][skill]、[执行][agent] |
| io.input_schema / output_schema | 保存已有 io，没有时写空对象 | 动作输出由引用构造；本轮未见按这两个 schema 做通用输入/输出校验 | [编辑][skill]、[执行][agent] |
| flow.nodes[].{id,type} / edges.{source,target} | 当前画布与 JSON 编辑保存；Skill 的画布快捷保存也重建 Skill 配置 | 按起点和连线遍历，识别 action/condition/startEnd；有 50 步与重复节点保护 | [画布][canvas]、[父保存][skill]、[执行][agent] |
| node.data.prompt / label / tools | 动作节点编辑；data 为 Record/dict，非严格节点联合类型 | prompt 进入当前节点上下文；tools 与 Skill 工具并集；label 参与起点识别/显示 | [画布][canvas]、[执行][agent] |
| condition.data.{source_node_id,field,operator,expected_value} | 条件面板编辑，data 以通用对象保存 | 对前序节点 outputs 做存在/相等/不等比较，选择 yes/no sourceHandle；无匹配边时有第一条边回退 | [画布][canvas]、[条件执行][agent] |
| positions / viewport / version | 画布布局与格式信息；当前 buildSchema 重建结构时未写 viewport | 执行使用节点与边；不按坐标推导顺序。布局往返保存须另验 | [画布][canvas]、[类型][types]、[执行][agent] |

上述“未带回”是保存对象构造与 schema 的静态差异。Python 可能补默认值，不能统一说所有字段都会原样保留或全部被清空；需用含高级字段的配置执行保存—读取—再次执行的对照验证。

## 7 Collection、检索、模型与 Prompt 字段

| 字段 / 请求 | 页面与保存接口 | 当前消费关系与限制 | 依据 |
| --- | --- | --- | --- |
| Collection title/description/type | CollectionForm → POST/PUT Collection | 后端存元数据；通用表单 type 固定 document | [表单][collection-form]、[服务][collection-service] |
| config.source 与外部来源参数 | API 模型有 local/FTP/S3/邮箱等相关字段；通用表单只选 system 并提交表单子集 | 不能把模型所有来源字段视为已有 UI；不同来源逐字段消费不在本轮深查内 | [表单][collection-form]、[模型][models] |
| enable_vector/fulltext/knowledge_graph/summary/vision | CollectionForm 保存；vector/fulltext 当前 UI 禁用切换 | 索引任务按配置启用，搜索请求再决定启用哪些路；API 字段可用范围大于当前 UI 控件 | [表单][collection-form]、[索引管理](../../../aperag/index/manager.py) |
| embedding/completion.{model,model_service_provider,custom_llm_provider} | available_models 返回选项，CollectionForm 提交 | 对应 embedding 与生成服务；UI 开 vision 要求 completion，索引源码还允许多模态 embedding 的图片路径 | [表单][collection-form]、[VisionIndexer](../../../aperag/index/vision_index.py) |
| language / knowledge_graph_config.entity_types | schema 有；通用表单编辑 language，未发现 entity_types 编辑项 | 图谱 manager 读取实体类型；language 与模型最终语言效果不能只由字段存在认定 | [表单][collection-form]、[图谱配置](../../../aperag/graph/lightrag_manager.py) |
| index_prompts.graph/summary/vision | schema 支持，通用 CollectionForm 未编辑/提交该项 | resolve_index_prompt 只有定义，所核对索引主路径没有调用；保存与执行未闭合 | [模型][models]、[PromptService][prompt-service]、[索引目录](../../../aperag/index/) |
| SearchRequest.query 与各路 topk/similarity/keywords、rerank/save_to_history | SearchTest → POST /collections/{id}/searches | 非空召回配置建 DAG，merge→rerank；降级图谱优先，无统一最终 topk 保证 | [搜索 UI](../../../web/src/app/workspace/collections/[collectionId]/search/search-test.tsx)、[服务][collection-service] |
| Provider 模型 api/tags | Provider/模型页面调用 LLM 接口 | 意图编辑筛 api=intent；Skill 模型按 enable_for_agent 标签筛选；前端候选和执行选模型逻辑需分别核对 | [意图][intent]、[Skill][skill]、[Provider 操作](../../../web/src/app/workspace/providers/[providerName]/models/model-actions.tsx) |
| Prompt 默认 agent_system/agent_query | PromptCard → PUT /prompts/user，删除/reset 同族接口 | Agent 解析已接入；Bot 专属模板优先，连接时读取 | [页面][prompt-ui]、[服务][prompt-service]、[执行][agent] |
| Prompt 默认 index_graph/index_summary/index_vision | 同一 PromptCard 可保存 | 保存 API 已有；索引执行未接入解析器，不能提示为已改变实际索引模型指令 | [页面][prompt-ui]、[服务][prompt-service]、[索引](../../../aperag/index/) |

CollectionService 将提交的 CollectionConfig 经 dumpCollectionConfig 序列化，Repository 直接替换 instance.config；未在该路径发现与旧配置的逐字段合并。因此通用表单未带回的高级配置不能视为必然保留，最终默认回填与丢值需保存回读验证。依据：[序列化](../../../aperag/schema/utils.py)、[更新方法][collection-service]、[Repository](../../../aperag/db/repositories/collection.py)。ModelSpec、IntentRouterLLMConfig、SkillRuntimeConfig 的字段命名不同，`timeout` 与 `timeout_ms` 等不能在转换时直接当作同一字段复制。

## 8 聊天请求、实时事件与历史的对接

### 发送到 WebSocket 的请求

下面逐字段表针对 Agent 路径。ChatService 对 knowledge/common 的传统 Flow 路径从 `data` 或 `message` 取文本，而当前 ChatInput 发送 `query`；两者存在静态字段差异，不能把 Agent 请求模型直接当成所有 Bot 的共同协议。相关 Bot 是否仍在使用及实际交互需运行核对。依据：[ChatService](../../../aperag/service/chat_service.py)、[ChatInput][input]。

| 字段 | 当前前端来源 | 后端消费 |
| --- | --- | --- |
| query | ChatInput 文本；FAQ 动作使用选项文案 | AgentMessage 必填；运行还检查空问题等条件 |
| collections | 选择的 Collection 对象数组，FAQ 动作空数组 | 必填列表；为空可回退 Bot 默认集合，再考虑 Skill 集合 |
| completion | 普通 ChatInput 当前发送 null | 后端回退 Bot agent.completion，仍要求完整可用模型 |
| web_search_enabled / language | 开关与当前 locale | 合并保留；工具可用还取决于 Skill 与节点绑定，不能只由开关保证 |
| files | 成功附件的 id/name/previewUrl | 后端还查询关联附件并构造有效文件上下文；客户端列表不是唯一依据 |
| action | MessagePartsAi → ChatMessages 发送 faq_expand/faq_end | 后端按动作处理 FAQ 分支；YAML/SDK AgentMessage 未同步 |
| force_skill_id | Python 支持；普通 ChatInputSubmitParams 没有此字段 | 主路径优先指定 Skill，但前面仍检查意图配置完整；不能当成无需配置的旁路 |

依据：[输入][input]、[消息发送][messages]、[FAQ 展示][ai-parts]、[AgentMessage 模型][models]、[Agent 主流程][agent]。

### 实时事件与前端消费

| 事件 | 当前处理与边界 |
| --- | --- |
| start | setLoading(true)，按消息 id 分组 |
| message | data 字符串追加到消息内容 |
| thinking / tool_call_result | 按 part_id 合并或追加；显示由消息 Part 组件决定；后端事件类型还含 tool_name/result 等 |
| stop | setLoading(false)，将 data 引用数组转换为 references Part，并携带 skill_id；实时 stop.data 不是 SDK ChatMessage.data 声明的字符串 |
| error | 作为事件进入消息分组；当前 onMessage 只在 stop 分支关闭 loading，没有独立 error 状态收尾契约 |
| faq_choice | 前端渲染 options 并回发结构化 action；没有包含在后端 AgentResponse Union 与旧 YAML 的完整类型中 |

后端实时事件有 BaseAgentResponse/专用类型，前端先强制视为 ChatMessage 再做转换；历史经 query_chat_messages 过滤和组装后返回。三者不应合为一种无差别 payload：实时消息可以带 skill_id 与数组 data，Python 历史 ChatMessage 没有 skill_id，重新打开能否保留显示需运行验证。

取消按钮当前通过 disconnect 后 connect 重建连接并复位本地 loading，没有发送专门的取消命令或等待服务端确认；这不证明服务端模型任务已经停止。连接鉴权使用 Cookie，实际 Bot/Chat 用户范围与代理行为仍需按后端和部署验证。

依据：[前端事件处理][messages]、[AI Part][ai-parts]、[实时事件类型][events]、[格式化器](../../../aperag/agent/stream_formatters.py)、[聊天路由][chat-view]、[历史工具](../../../aperag/utils/history.py)。

## 9 SDK 以外的请求与主定义缺项

| 入口 | 定义与调用现状 | 使用边界 |
| --- | --- | --- |
| GET /mcp_tools | SkillEditor 直接 fetch，主 OpenAPI/SDK 无；后端 main.py 有 required_user | 该 URL 没有拼 NEXT_PUBLIC_BASE_PATH；有配置前缀的部署需验证 |
| POST /backup/export、/backup/import/settings、/backup/import/prompts | BackupSettings 的 fetchWithAuth 包装；主定义/SDK 无 | 方法由包装调用者传入；不能只看包装层 fetch 默认认定 GET；导出/导入权限由 get_current_admin 检查 |
| POST/PUT /bots | 备份导入额外直接调用，普通页面用 SDK | 同一路径有两种调用方式，不能只迁 SDK 调用点 |
| GET /auth/{provider}/authorize 与 callback | AppProvider 与回调页 fetch；后端按 OAuth 配置条件挂载工厂子路由 | 不纳入本轮字面装饰器数；请求 URL 和条件挂载存在不等于 OAuth 已联通 |
| 文档 object 与 previewUrl | Markdown、PDF 展示和 MessagePartsUser 直接读资源 URL | URL/下载链也属于对接范围，不全经过 SDK；具体权限与路径编码需运行测试 |
| POST /chats/{chat_id}/search | 后端有；主定义/SDK 无，MCP 使用 | 没有前端 SDK 调用不等于功能闲置 |
| DELETE /collections/{id}/documents；POST /collections/test-mineru-token；钉钉 callback | 后端字面路由有，主定义无 | 调用与是否需并入主定义应按用途决定；本轮只记录 |
| /health、/v1/chat/completions、dev 的 /test/register_admin | 后端有，主 OpenAPI 不覆盖 | 健康、独立兼容协议、仅开发条件分别标记，不统一当作业务定义遗漏 |
| POST /agent/message | 主定义和 SDK 都有，明示 Doc Only；无对应已挂载 HTTP 实现 | 只供消息模型说明，不能拿它替代 WebSocket 测试 |

依据：[main.py](../../../aperag/views/main.py)、[备份 UI][backup-ui]、[备份路由](../../../aperag/views/backup.py)、[应用挂载](../../../aperag/app.py)、[OAuth 鉴权](../../../aperag/views/auth.py)、[MCP](../../../aperag/mcp/server.py)、[资源渲染](../../../web/src/components/markdown.tsx)、[用户附件展示](../../../web/src/components/chat/message-parts-user.tsx)。逐项方法、路径和调用点见[附表](http-api-component-matrix.md)。

## 10 差异汇总与后续边界

| 编号 | 已确认的静态差异 | 对架构整理的影响 |
| --- | --- | --- |
| D01 | orchestration 未完整进入 OpenAPI/生成 BotConfig | 先明确配置源定义与扩展类型关系，再考虑生成或抽模块 |
| D02 | Bot 默认/保护标记、欢迎字段的 YAML、SDK、Python 覆盖不同 | 不能以某一份生成类型代表全部配置 |
| D03 | AgentMessage 的 force_skill_id/action 与 ChatMessage 扩展不一致 | HTTP 请求模型、WS 请求、实时事件和历史类型需分别维护 |
| D04 | OpenAPI CookieAuth 名称 sessionid，实际认证 Cookie 为 session | 鉴权描述与实现有差异；不能据定义推断当前 Cookie 使用正确 |
| D05 | 工具与备份等主链有后端/前端调用但无主定义 | 组件迁移应同时覆盖直接 fetch 和包装器 |
| D06 | 意图 provider 未用于重建 session，max_tokens 未传入，阈值未比较 | 页面配置值与实际模型参数需单独确认，不能在纯拆分中偷偷补语义 |
| D07 | 部分启停、类型、IO、工具高级策略只有存储/定义 | 不把“已保存”写成“已执行”；是否实现由后续范围决定 |
| D08 | Bot config 整份替换，编辑器重建若干嵌套对象 | 先明确快照、合并与字段保留边界；并发与往返保存待验 |
| D09 | 索引 Prompt 可保存、执行解析器未接通 | 页面与生成字段存在不能代替调用链核对 |
| D10 | WS stop/error/取消/历史有不同格式和收尾行为 | 单独记录协议，不能把接口 SDK 统一当聊天协议 |
| D11 | 当前 ChatInput 发 query，传统 Flow 收 data/message | Agent 与传统 Bot 分开验证，不能在拆分时默认为统一请求 |

D01–D03 等会影响生成文件覆盖；本轮未运行 `api:build`、datamodel-codegen 或修改定义。前端生成脚本会清理 src/api，后端目标是 view_models.py；如后续授权对齐，应先在隔离输出中生成并比较，尤其核对已有扩展字段。

本轮交付的是盘点事实，未批准或实施上述修正。运行配置、真实 HTTP/WS 请求响应、表单保存回读、跨 Provider 模型调用和用户隔离仍待验证；字段级深查未覆盖所有管理与集成模块。后续可据本表选定具体契约修正范围，再进入前后端模块拆分。

生成流程依据：[Makefile](../../../Makefile)、[package.json](../../../web/package.json)、[生成器配置](../../../web/openapitools.json)。返回[当前说明](../design/current/README.md)或[文档入口](../../README.md)。

[client]: ../../../web/src/lib/api/client.ts
[server]: ../../../web/src/lib/api/server.ts
[bot-provider]: ../../../web/src/components/providers/bot-config-provider.tsx
[updater]: ../../../web/src/app/workspace/bots/[botId]/bot-config-updater.ts
[bot-view]: ../../../aperag/views/bot.py
[bot-service]: ../../../aperag/service/bot_service.py
[bot-form]: ../../../web/src/app/workspace/bots/[botId]/bot-form.tsx
[intent]: ../../../web/src/app/workspace/bots/[botId]/intent-router/intent-router-editor.tsx
[skill]: ../../../web/src/app/workspace/bots/[botId]/skills/skill-editor.tsx
[types]: ../../../web/src/app/workspace/bots/[botId]/orchestration-types.ts
[canvas]: ../../../web/src/app/workspace/bots/[botId]/flow-canvas-editor.tsx
[agent]: ../../../aperag/service/agent_chat_service.py
[session]: ../../../aperag/agent/agent_session_manager.py
[chat-view]: ../../../aperag/views/chat.py
[messages]: ../../../web/src/components/chat/chat-messages.tsx
[input]: ../../../web/src/components/chat/chat-input.tsx
[ai-parts]: ../../../web/src/components/chat/message-parts-ai.tsx
[events]: ../../../aperag/agent/response_types.py
[models]: ../../../aperag/schema/view_models.py
[bot-yaml]: ../../../aperag/api/components/schemas/bot.yaml
[agent-yaml]: ../../../aperag/api/components/schemas/agent.yaml
[chat-yaml]: ../../../aperag/api/components/schemas/chat.yaml
[collection-yaml]: ../../../aperag/api/components/schemas/collection.yaml
[sdk-bot-config]: ../../../web/src/api/models/bot-config.ts
[collection-form]: ../../../web/src/app/workspace/collections/collection-form.tsx
[collection-view]: ../../../aperag/views/collections.py
[collection-service]: ../../../aperag/service/collection_service.py
[document-service]: ../../../aperag/service/document_service.py
[prompt-ui]: ../../../web/src/app/workspace/prompts/prompt-settings.tsx
[prompt-service]: ../../../aperag/service/prompt_template_service.py
[backup-ui]: ../../../web/src/app/admin/configuration/backup-settings.tsx
