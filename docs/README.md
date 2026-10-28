# SAPilot 文档入口

项目仓库保存代码、可共享文档和配置模板。本机语料、评测原始结果、账号及模型权重放在仓库旁的 `../SAPilot-data/`，不随 Git 提交。

## 从哪里开始

| 要了解的内容 | 入口 | 状态与用途 |
| --- | --- | --- |
| 项目目标、SAP 规则和验收原则 | [项目背景](SAPILOT_PROJECT_CONTEXT.md) | 产品目标与约束；不代表全部已实现 |
| 文件放置、资料路径与提交规则 | [项目目录约定](zh-CN/reference/project-layout.md) | 本次整理后的目录及维护规则 |
| 最终离线部署与容量设计 | [离线架构讨论稿](zh-CN/design/offline-deployment-draft.md) | 8GB 显存、50 名使用者、高峰 20 问；方案尚未部署或压测 |
| 既有平台总体设计 | [系统架构说明](zh-CN/design/architecture.md) | 通用能力说明；需结合源码与运行结果核对 |
| 本地开发启动 | [轻量开发部署](zh-CN/deployment/local-lite-business-guide.md) | 包含联网准备和热重载；不能直接作为最终离线交付说明 |
| 开发与构建 | [开发指南](zh-CN/development/development-guide.md)、[镜像构建](zh-CN/deployment/build-docker-image.md) | 既有操作说明，执行前核对环境 |

## 专题入口

| 专题 | 文档 |
| --- | --- |
| 摄取与索引 | [文档上传](zh-CN/design/document_upload_design.md)、[索引架构](zh-CN/design/indexing_architecture.md)、[视觉索引](zh-CN/design/vision_index_creation.md) |
| 检索与 Agent | [搜索流程](zh-CN/design/search_flow_design.md)、[Agent 后端](zh-CN/design/agent-backend.md)、[提示词](zh-CN/design/prompt_customization_design.md) |
| 评测 | [评测功能设计](zh-CN/design/evaluation-design.md)；摄取验收及容量测试口径见离线架构讨论稿 |
| 集成 | [钉钉](zh-CN/integration/dingtalk.md)、[MCP](zh-CN/integration/mcp-api.md)、[Dify](zh-CN/integration/dify.md) |
| 模型与调试 | [Ollama 配置](zh-CN/reference/how-to-configure-ollama.md)、[调试说明](zh-CN/reference/HOW-TO-DEBUG.md) |
| 历史资料 | [归档说明](archive/README.md) |

## 状态和维护规则

- **当前实现**必须有对应源码或运行证据；目标、讨论稿和历史记录不能替代实现事实。
- 总体架构定案后收敛到一个正式入口，专题文档只解释对应部分，不再另建重复的总架构。
- 专题设计未统一完成实现审计；文档中的功能描述不能单独作为已交付依据。
- 保留现有 `zh-CN/`、`en-US/` 结构；先按内容核对，再合并或归档，不批量删除语言版本。
- 本地数据路径使用目录约定中的相对路径。仓库文档不链接内部原件或私有运行记录，避免 GitHub 上出现不可访问的本机链接。
- 历史评测结果保留在本地数据目录；只有经过检查、脱敏且可共享的样例或结果摘要才进入仓库。
