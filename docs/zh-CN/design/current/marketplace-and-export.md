# SAPilot 当前知识库市场与导出

> 状态：当前说明，依据 2026 年 10 月 29 日源码静态核对整理。未完成全量权限审计、导出下载或并发验收。

## 发布、订阅与读取

当前存在 CollectionMarketplace 与 UserCollectionSubscription，以及发布、下架、订阅和取消订阅服务。订阅关联市场记录；下架事务会使相关订阅失效。市场列表允许匿名浏览，创建订阅及读取自己的订阅列表要求有效用户。

市场详情、文档与预览等部分读取路由使用 `optional_user`，允许空 user_id。主要访问检查 `_check_marketplace_access` 校验发布状态和 owner，订阅作为可选信息；保留的 `_check_subscription_access` 不是这些读取路径的统一前置条件。

因此，当前“已订阅”不能直接解释成“获得了原本不可读的内容访问权”。标签与批量授权方案若继续推进，需要先明确团队定向访问与公开市场的关系；该方案见[未实现规划](../planned/README.md)。

依据：[模型](../../../../aperag/db/models.py)、[市场服务](../../../../aperag/service/marketplace_service.py)、[市场访问服务](../../../../aperag/service/marketplace_collection_service.py)、[市场路由](../../../../aperag/views/marketplace.py)、[专用读取路由](../../../../aperag/views/marketplace_collections.py)。

## 前端与权限边界

当前前端位于 `web/src/app/marketplace`，采用 Next.js 与现有 UI；专用文档、预览和图谱页面已有实现。隐藏修改控件不能证明所有后端写接口均通过只读审计。匿名、未订阅、已订阅、owner 和下架等组合需要运行验证。

依据：[市场页面](../../../../web/src/app/marketplace/)、[读取服务](../../../../aperag/service/marketplace_collection_service.py)。旧 Ant Design/Umi 路径与“订阅后才可读”的旧假设见[历史差异](../historical/superseded-design-notes.md)。

## 导出的执行链

导出已有创建、查询状态和下载三条路由；创建返回 202，ExportService 检查 Collection owner 后创建任务并交 Celery 执行。查询和下载按任务创建者检查访问。

同一用户未完成导出任务计数达到 3 时，新请求返回 429；这是当前计数判断，不代表并发竞争下已经验证为严格上限。打包任务按 Collection 的对象前缀列举，最多 5 个下载线程，生成 manifest 与 ZIP 后上传对象存储。

依据：[导出路由](../../../../aperag/views/export.py)、[ExportService](../../../../aperag/service/export_service.py)、[导出任务](../../../../config/export_tasks.py)。

任务完成时会写入七天后的 `gmt_expires`。本轮只找到该时间字段、EXPIRED 状态和下载分支，未找到自动清理任务及 Beat 注册链，所以七天自动删除应列为[未实现规划](../planned/README.md)，不能承诺已经生效。

前端导出组件有约两秒轮询和处理中阻止关闭逻辑；入口按 `share` 条件渲染，后端 owner 检查仍是实际约束。完整文件是否都被纳入 ZIP、大文件内存占用、任务失败后的存储状态和下载可用性仍待运行验证。

原始材料：[市场设计](../pending-review/collection_marketplace_design.md)、[导出设计](../pending-review/collection_knowledge_export_design.md)。返回[当前说明目录](README.md)。
