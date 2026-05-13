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
