# 用户指令记忆

本文件记录了用户的指令、偏好和教导，用于在未来的交互中提供参考。

## 格式

### 用户指令条目
用户指令条目应遵循以下格式：

[用户指令摘要]
- Date: [YYYY-MM-DD]
- Context: [提及的场景或时间]
- Instructions:
  - [用户教导或指示的内容，逐行描述]

### 项目知识条目
Agent 在任务执行过程中发现的条目应遵循以下格式：

[项目知识摘要]
- Date: [YYYY-MM-DD]
- Context: Agent 在执行 [具体任务描述] 时发现
- Category: [代码结构|代码模式|代码生成|构建方法|测试方法|依赖关系|环境配置]
- Instructions:
  - [具体的知识点，逐行描述]

## 去重策略
- 添加新条目前，检查是否存在相似或相同的指令
- 若发现重复，跳过新条目或与已有条目合并
- 合并时，更新上下文或日期信息
- 这有助于避免冗余条目，保持记忆文件整洁

## 条目

[SAPilot 变更验证命令]
- Date: 2026-05-13
- Context: Agent 在执行图片搜索历史与附件展示修复时发现
- Category: 测试方法
- Instructions:
  - 后端单文件语法检查可使用 `.venv/bin/python -m py_compile <files>`。
  - 后端 lint 可使用 `.venv/bin/python -m ruff check <files>`。
  - 图搜相关单测可使用 `.venv/bin/python -m pytest tests/unit_test/test_image_search_refactor.py -q`。
  - 前端格式检查可在 `web` 目录使用 `npx prettier --check <files>`。
  - 前端全量类型检查可在 `web` 目录使用 `yarn tsc --noEmit --pretty false`。

[SAPilot 聊天附件图片预览交互]
- Date: 2026-05-13
- Context: 用户要求聊天中上传的图片附件点击回看时采用平台同类交互
- Instructions:
  - 聊天图片附件应以小图标/附件入口展示，点击后在页面内弹窗回看原图。
  - 图片回看弹窗应支持鼠标滚轮放大缩小。

[SAPilot 钉钉现场问诊助手管理规则]
- Date: 2026-05-13
- Context: 用户规划 1.1 版本钉钉接口配置和专用 Agent 管理方式
- Instructions:
  - 钉钉现场问诊助手只能由 admin 管理员账号创建和配置。
  - 钉钉接口启用并绑定该助手后，该 Agent Bot 应进入删除保护状态。

[SAPilot 代码修改授权规则]
- Date: 2026-05-13
- Context: 用户要求先分析 FAQ 故障问答机器人恢复问题
- Instructions:
  - 未经用户明确许可，不要修改代码。
  - 对已经磨合稳定的 FAQ 故障问答和图片检索链路，先按链路分析原因，再等待用户确认是否执行修改。

[SAPilot FAQ 故障问答回答流程]
- Date: 2026-05-13
- Context: 用户要求恢复 FAQ 故障问答机器人的原回答流程和格式，后改为方案B条件化搜索
- Instructions:
  - FAQ 故障问答机器人首轮回答应注明"基于知识库标准答案"。
  - 首轮回答只基于知识库问答内容整理，处理步骤严格按知识库中的步骤列出，避免 LLM 自行扩展。
  - 首轮回答末尾追问"是否需要我从专业角度扩展解答？"。
  - 用户回复确认语后，LLM 结合上一轮 FAQ 标准答案、用户原问题和自身知识自由补充回答，作为顾问参考。
  - 图搜命中后取 faq_title（而非问题描述）作为检索关键词交给 LLM，后续按文本问答流程回答。
  - 方案B：默认自由对话不搜知识库，只有明确触发才注入搜索工具。触发条件：上传图片、明确搜索请求、含SAP业务关键词、扩展确认。
  - 非触发场景用 tool_filter={"aperag": set()} 禁用 MCP 工具，LLM 自由回答。
  - 1.3版本将引入工作流和意图识别替代当前规则触发器。

[SAPilot 钉钉 Stream 图片接收规则]
- Date: 2026-05-14
- Context: Agent 在验证钉钉 Stream 模式图片接收链路时发现
- Category: 代码模式
- Instructions:
  - Stream 模式接收图片时，优先使用 `ChatbotMessage.get_image_list()` 获取原始 `downloadCode`。
  - 避免用 SDK 的 `extract_image_from_incoming_message()` 作为接收判断，因为该 helper 会立即下载并重新上传图片，容易把“收到图片凭证”和“下载图片失败”混在一起。
  - 钉钉端发图能命中图搜时，说明第一步“Agent 能收到钉钉图片凭证并进入图搜链路”已打通。
