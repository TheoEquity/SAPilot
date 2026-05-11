# SAPilot DingTalk Integration

SAPilot 钉钉机器人用于客户现场 SAP 顾问通过钉钉发送问题、日志和报错截图，并由 SAPilot Agent 结合企业知识库与大模型返回排查建议。

## Scope

- 支持钉钉单聊文本问答。
- 支持钉钉群聊通过 `@SAPilot` 触发问答。
- 支持接收图片类消息，下载钉钉临时文件并用知识库 `VISION` 索引做相似报错截图检索。
- 支持在知识库信息不足时检索 SAP Community 官方社区公开内容。
- 使用 SAPilot Agent 的默认知识库、模型和 Prompt 配置。
- 会话来源保存为 `dingtalk`，便于后续审计和渠道区分。

## Configuration

在后端 `.env` 中配置：

```bash
# Enable DingTalk integration
DINGTALK_ENABLED=True

# DingTalk outgoing robot signing secret
DINGTALK_WEBHOOK_SECRET=your-dingtalk-signing-secret

# Optional. DingTalk group robot webhook for sending messages back to the group.
DINGTALK_OUTGOING_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=your-token

# Optional. Signing secret for the outgoing group robot webhook.
DINGTALK_OUTGOING_WEBHOOK_SECRET=your-dingtalk-outgoing-signing-secret

# SAPilot user id that owns the Agent bot
DINGTALK_BOT_USER_ID=your-sapilot-user-id

# Optional. If empty, SAPilot uses the user's default Agent bot.
DINGTALK_BOT_ID=botxxxxxxxxxxxxxxxx

# Use sync to return callback response directly, or webhook to send answer through group robot webhook.
DINGTALK_RESPONSE_MODE=sync

# Optional. Stream mode credentials from DingTalk application basic information.
DINGTALK_STREAM_CLIENT_ID=your-client-id
DINGTALK_STREAM_CLIENT_SECRET=your-client-secret
DINGTALK_STREAM_TOPIC=/v1.0/im/bot/messages/get

# Optional. Used to download DingTalk image messages. Defaults to Stream credentials when empty.
DINGTALK_APP_KEY=your-client-id
DINGTALK_APP_SECRET=your-client-secret

# Enable image-to-image search against SAPilot VISION indexes.
DINGTALK_IMAGE_SEARCH_ENABLED=True
DINGTALK_IMAGE_SEARCH_TOPK=5
DINGTALK_IMAGE_SEARCH_SIMILARITY=0.2

# Allow the Agent to use web_search with source=community.sap.com for SAP Community answers.
DINGTALK_SAP_COMMUNITY_SEARCH_ENABLED=True
```

## Callback URL

钉钉机器人回调地址：

```text
https://your-sapilot-api.example.com/api/v1/dingtalk/bot/callback
```

本地开发预览环境可使用后端预览域名：

```text
https://8000-xxxx.monkeycode-ai.online/api/v1/dingtalk/bot/callback
```

## Behavior

1. 钉钉把消息事件推送到 SAPilot。
2. SAPilot 校验钉钉签名。
3. SAPilot 解析文本、图片地址或媒体标识。
4. 当消息包含图片时，SAPilot 使用钉钉 `downloadCode` 获取临时下载链接，下载原图并转为 data URI。
5. SAPilot 使用绑定 Agent 的默认知识库做 `VISION` 相似图检索，召回历史报错图及其关联说明。
6. SAPilot 查找配置的 Agent Bot，或使用该用户默认 Agent。
7. SAPilot 调用 Agent 问答流程。
8. SAPilot 返回钉钉 Markdown 消息。

当 `DINGTALK_RESPONSE_MODE=webhook` 时，SAPilot 会通过 `DINGTALK_OUTGOING_WEBHOOK_URL` 把答案主动发送到钉钉群。

## Stream Mode

如果钉钉 HTTP 模式发布校验失败，建议切换到 Stream 模式。Stream 模式由 SAPilot 主动连接钉钉开放平台，不需要公网回调地址。

启动 Stream 监听进程：

```bash
# Start DingTalk Stream bot listener
uv run python scripts/dingtalk_stream_bot.py
```

机器人回调 Topic 固定为：

```text
/v1.0/im/bot/messages/get
```

## Recommended Agent Prompt

钉钉绑定的 Agent 建议使用“SAP 现场问诊助手”定位：

```text
你是 SAPilot 现场问诊助手，面向在客户现场处理 SAP 运维、开发和接口问题的顾问。你需要优先结合企业知识库回答问题。用户可能通过钉钉发送简短问题、日志片段或报错截图。回答应聚焦 SAP 相关问题，给出问题判断、可能原因、处理建议和需要补充的信息。对于生产高风险操作，提醒用户走审批或人工确认。
```

## Screenshot Search

截图检索依赖知识库已启用 `VISION` 索引，并且集合使用支持图文同空间的多模态 embedding 模型，例如 `multimodal-embedding-v1`。

处理流程：

1. 钉钉图片消息提供 `downloadCode` 或临时图片 URL。
2. SAPilot 下载原图并生成图片 embedding。
3. SAPilot 只检索知识库中的 `VISION` 向量。
4. 命中结果按相似度排序并去重。
5. Agent 根据命中图片、关联说明、用户问题生成现场排查建议。

## SAP Community Search

SAP Community 搜索通过已有 `web_search` MCP 工具完成，Agent 会优先使用：

```text
source=community.sap.com
```

必要时再使用：

```text
source=help.sap.com
```

该能力只读取公开搜索结果与公开页面内容，并在回答中保留来源链接。

## Current Limitations

- 复杂问题可能接近钉钉 Stream 处理超时，建议使用 `DINGTALK_RESPONSE_MODE=webhook` 先发送即时反馈。
- 图片检索依赖知识库中已有相似报错图，冷启动阶段命中率取决于历史案例质量。
- SAP Community 搜索依赖公开搜索结果与页面可读性，页面读取失败时会降级使用搜索摘要。
