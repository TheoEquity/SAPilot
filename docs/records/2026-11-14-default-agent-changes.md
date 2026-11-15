# Default Agent 改动记录

运行环境为本机 `localhost:3000`。沿用现有 Default Agent `bot9172fba8dd6207b4`。

| 改动 | 位置 | 核验结果 |
| --- | --- | --- |
| 每轮答复显示实际 Skill | `app/aperag/service/agent_chat_websocket.py` 保存本轮 Skill，`app/aperag/chat/history/message.py` 和 `app/aperag/schema/view_models.py` 将它返回给聊天页面。 | Edge 验证代码解读和修改建议各自显示正确，刷新后仍能看到。旧答复若无 Skill 记录，标签留空。 |
| 修复截图判断模板 | `app/aperag/service/prompt_template_service.py` 根据附件计算图片标记。迁移 `app/aperag/migration/versions/20261114163000-50eeb342a7c9.py` 修复系统记录 `pt_sys_agent_query` 中的旧截图判断块。 | 本地数据库已执行 `50eeb342a7c9`。核对用户模板和 Bot 配置无变化。Edge 及模型调用记录确认纯文本无图片提示，图片请求有提示。 |
| 业务 Skill 集中配置在 Default Agent | `app/aperag/service/sap_bot_configuration.py` 和 `app/scripts/configure_sap_business_bots.py` 配置 FAQ、规范、技术咨询、事务码、三个代码 Skill 和问候路由。混合入口的代码附件由 `app/aperag/service/chat_document_service.py` 处理，图片观察由 `app/aperag/service/visual_context_service.py` 接入账号已有视觉模型。 | Edge 验证问候、粘贴和上传 Java、SU53 正查、权限管理倒查、FAQ 复问免检索。截图加问题描述可定位帐号锁定 FAQ，单独上传同一裁剪小图未确认条目。 |
| FAQ 扩展按确认时的联网开关 | `app/web/src/components/chat/chat-messages.tsx`、`chat-input.tsx` 和 `use-chat-messages.ts` 共用开关状态。 `app/aperag/service/agent_chat_service.py` 和 `faq_choice_service.py` 以扩展请求的开关为准。Default Agent 的 FAQ 扩展配置启用了 `search_sap_help` 和 `web_read`。 | Edge 与后台调用记录确认 FAQ 首轮只查内部库，打开联网后确认扩展会查 SAP Help，确认前关闭则无外部调用。技术咨询首轮实测读取 SAP Help 并返回出处。规范、T-code、代码和问候没有外部调用。71 项相关回归通过。 |
| 修复配置保存与工具边界 | Skill 编辑器保留未填写的运行参数并保存业务分类；FAQ 扩展不进入普通路由候选或兜底；未分类 Skill 只暴露显式绑定的工具。聊天输入在请求前检查 ABAP、Java 源文件的 48 KiB 上限。 | 相关 Python 回归 80 项、前端配置测试 3 项及类型检查通过；Edge 在 `localhost:3000` 确认超限文件没有发起上传请求，小文件可上传。 |

本机配置保存在数据库。其他 Bot 配置已核对，本次没有新增测试 Bot。其他环境仍需单独执行迁移并导入 Default Agent 配置；Git 分支合并不等于数据库配置已同步。文档去重、更新和删除清理仍待单独处理。
