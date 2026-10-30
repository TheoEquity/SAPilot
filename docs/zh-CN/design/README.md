# SAPilot 设计资料分类导航

更新日期：2026 年 10 月 29 日。已按 18 篇旧稿的源码核对结果，把适用内容提炼为 8 篇当前专题，过时内容归入历史差异，未实现内容分列为规划。18 篇旧正文和 110 条核对记录保留原路径，9 份讨论稿继续独立存放；分批整理计划与实施记录位于根目录 `records/`。

讨论稿中的适用工程内容已提炼为独立规范，由根 [AGENTS.md](../../../AGENTS.md) 直接引用。[开发文档说明](../development/README.md)仅提供专题概览，本页仅介绍设计资料的分类与来源。

| 分类 | 入口 | 当前数量与用途 |
| --- | --- | --- |
| 当前说明 | [current/](current/README.md) | 9 篇：原有消息流程与 8 篇当前专题；有源码依据，保留配置和运行验证边界。 |
| 未实现规划 | [planned/](planned/README.md) | 9 组未接通或可选方案，注明已有基础和未定前提；不代表已排期或获批实施。 |
| 历史记录 | [historical/](historical/README.md) | 旧 Agent 方案与本轮逐篇历史差异；不作为当前契约或性能保证。 |
| 旧原文与核对记录 | [pending-review/](pending-review/README.md) | 保留 18 篇旧稿及 110 条主要声明的核对记录，提供逐篇整理去向；路径沿用供追溯。 |
| 测试手册 | [test-guides/](test-guides/README.md) | 1 篇，保留操作示例；本次未执行测试，示例需先核对。 |
| 待办 | [todos/](todos/README.md) | 1 篇，旧集成任务，部分方法已存在；完成状态待逐项复核。 |
| 讨论稿 | [discussions/](discussions/README.md) | 9 份方案与规约讨论，含已作废离线稿；分批整理计划单独放在根目录 `records/` |

## 优先阅读

- 工程专题概览：见[开发文档说明](../development/README.md)；实际开发规则由根 `AGENTS.md` 直接引用具体规范。
- 了解当前实现：从[当前说明目录](current/README.md)进入；平台公共部分见[平台架构](current/platform-architecture.md)，用户提问与配置见[消息处理流程](current/current-architecture-and-message-flow.md)。
- 准备前后端拆分：读[接口、组件与配置字段盘点](../reference/api-component-config-inventory.md)及[HTTP 调用对应表](../reference/http-api-component-matrix.md)，先核对保存与执行的实际关系；后续修正与审核见[实施记录](../../../records/architecture-implementation-record.md)。
- 查看推进依据：见[架构整理推进计划讨论稿](../../../records/architecture-implementation-plan-draft.md)；用户已授权逐批实施，当前完成、审核与待验状态以[实施记录](../../../records/architecture-implementation-record.md)为准。
- 查未实现部分：读[规划](planned/README.md)，区分主链未接通、占位和可选增强；实施仍以用户明确范围为准。
- 查旧接口、旧保证和变更原因：读[历史差异](historical/superseded-design-notes.md)，需要原始上下文时进入[18 篇核对原文](pending-review/README.md)。
- 查操作示例和旧任务清单：分别进入[测试手册](test-guides/README.md)和[待办](todos/README.md)，其中原有完成标记仍须核验。
- 查本轮架构、接口和规约讨论：进入[讨论稿](discussions/README.md)，按已确认事项、建议及未知项的原有区分阅读。

## 状态与维护

目录表示用途和证据状态，不表示全部已定案或已验收。当前说明只提炼有实现依据的内容，并保留限制；历史记录保留旧描述，规划保留未接通方案。原稿仍混有多种状态，其已实现、工期和 TODO 声明仅作原记录。

此前文档整理阶段未修改业务代码、运行配置或调度脚本；后续代码实施另记于实施记录，旧正文仍保留。18 篇的主要声明做过源码静态核对，但不等于逐行示例、全量权限或端到端验收；其他类别旧稿也没有因分类整理自动获得验证。

资料分类反映用途与证据状态，移动文件本身不代表验收。新增资料的放置、引用和验证要求由根 `AGENTS.md` 及具体规范承载，本页不另设开发要求。

项目规则见 [AGENTS.md](../../../AGENTS.md)，产品与验收目标见[项目背景](../../SAPILOT_PROJECT_CONTEXT.md)，项目级导航见[文档入口](../../README.md)。
