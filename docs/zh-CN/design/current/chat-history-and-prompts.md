# SAPilot 当前聊天历史与 Prompt 配置

> 状态：当前说明，依据 2026 年 10 月 29 日源码静态核对整理。当前消息主流程见[架构与消息处理流程](current-architecture-and-message-flow.md)。

## 历史数据如何读取

`GET /api/v1/bots/{bot_id}/chats/{chat_id}` 先查询当前用户和 Bot 下的会话，再由 `query_chat_messages` 读取历史并组装返回数据。会话元数据和反馈存于 PostgreSQL，历史正文使用 RedisChatMessageHistory。

Redis List 键前缀为 `message_store:`，写入使用 LPUSH，读取 LRANGE 后逆序；反馈按 AI 消息 ID 组装。当前历史响应只保留 `message`、`references`、`faq_choice`，不能承诺实时出现过的 thinking 或工具事件会在重新打开后全部重放。

依据：[ChatService](../../../../aperag/service/chat_service.py)、[历史工具](../../../../aperag/utils/history.py)、[消息格式](../../../../aperag/chat/history/message.py)、[AgentHistoryManager](../../../../aperag/agent/agent_history_manager.py)。

## 保存、TTL 与恢复边界

Agent 通过 AgentHistoryManager 保存回合，传统 Flow 有自己的执行与写入路径，不能用一种格式概括全部消息协议。RedisChatMessageHistory 的 ttl 默认 None，仅在指定 TTL 时设置 expire；当前 AgentHistoryManager 入口没有指定 TTL。

Redis 是否持久化、备份及重启后能否恢复取决于部署。Skill 缓冲还有实例内状态，重连后的恢复需要运行验证。`query_chat_messages` 异常时返回空数组，因此空历史也可能表示读取失败。依据：[历史工具](../../../../aperag/utils/history.py)、[Agent 历史保存](../../../../aperag/agent/agent_history_manager.py)、[Agent 服务](../../../../aperag/service/agent_chat_service.py)。

## Prompt 存储与生效路径

`prompt_template` 保存用户与系统默认配置；Bot 可在 `config.agent` 中设置专属 system/query 模板。Agent 两类解析均按以下顺序取首个有效配置：

1. Bot 专属模板。
2. 用户默认模板。
3. 系统默认模板。
4. 代码硬编码兜底。

AgentChatService 与钉钉服务已有对应调用。WebSocket 入口在进入消息循环前解析模板，不能据此认定已连接会话会在每条消息前重新读取所有变更。Skill 的提示词组合仍按[消息处理说明](current-architecture-and-message-flow.md)理解。

依据：[PromptTemplateService](../../../../aperag/service/prompt_template_service.py)、[AgentChatService](../../../../aperag/service/agent_chat_service.py)、[钉钉服务](../../../../aperag/service/dingtalk_bot_service.py)。

索引侧存在 `index_prompts` 字段和 `resolve_index_prompt` 方法，但所核对的 graph/summary/vision 索引主路径没有调用该方法，summary/vision 仍用内置 prompt。因此“配置已保存”不能等同“索引 Prompt 已生效”；接入任务单列在[未实现规划](../planned/README.md)。

依据：[配置模型](../../../../aperag/schema/view_models.py)、[解析器](../../../../aperag/service/prompt_template_service.py)、[graph](../../../../aperag/index/graph_index.py)、[summary](../../../../aperag/index/summary_index.py)、[vision](../../../../aperag/index/vision_index.py)。

## 用户配置入口

`/workspace/prompts` 已有配置页面。`/api/v1/prompts` 下提供 user 的读取、批量更新、删除、reset，system 的读取，以及 preview、validate 工具。当前表无 language 列，解析方法也无旧稿的 language 参数；预览和语法校验不等于所有运行变量都已正确绑定。

依据：[页面](../../../../web/src/app/workspace/prompts/prompt-settings.tsx)、[路由](../../../../aperag/views/prompts.py)、[模型](../../../../aperag/db/models.py)。各级覆盖、错误模板、空值回退和聊天恢复尚需运行测试。

原始材料：[聊天历史](../pending-review/chat_history_design.md)、[Prompt 设计](../pending-review/prompt_customization_design.md)。返回[当前说明目录](README.md)。
