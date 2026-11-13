# 前端 HTTP 客户端迁移记录（2026-11-12）

## 决定与改动

用户决定继续使用 OpenAPI，但不保留旧 OpenAPI Generator SDK 的兼容层。FastAPI 路由和 Pydantic 模型仍是接口维护源，导出的 OpenAPI 供 Orval 生成前端类型、请求函数和 Mock。

本次将前端业务 HTTP 调用与类型接到 `app/web/src/api/generated/`，浏览器和服务端继续复用原有 Axios 实例、鉴权与错误处理。补齐被本次调用使用、但先前没有准确声明的后端请求体和响应模型；旧 SDK 的 `apis/`、`models/`、入口文件、合并 YAML、生成器配置与 npm 依赖已移除。历史盘点文档中的旧 SDK 链接固定到迁移前提交，当前维护说明改为生成客户端。

## 已验证

| 检查 | 结果 |
| --- | --- |
| 从当前 FastAPI 应用导出 OpenAPI，移除旧生成器后执行 `yarn api:generate` | 导出 138 个操作、30 个 tag；Orval 生成成功 |
| `yarn tsc --noEmit --pretty false --incremental false` | 通过，0 错误 |
| `yarn next build` | 退出码 0，编译、类型检查和静态页生成完成；预渲染时因无应用后端出现 HTTP 失败日志 |
| 后端契约、生成客户端传输和 Bot 配置回归 | Python 契约 32 项通过；Node 传输 7 次请求断言通过；Bot 保存回调及 16 项 Pydantic 回读回归通过 |
| `yarn test:mock`、`yarn test:logs`、生成类型独立编译 | 分别 2/2、5/5，通过 |
| 含斜杠模型路径 | 前端生成客户端发送 `model%2Fone`；FastAPI HTTP 测试确认 Service 收到 `model/one` |
| 隔离的本地 PostgreSQL 中 Bot 路由与真实 Service | GET→PUT→GET 均为 200；回读确认修改、显式空串和未编辑的 flow、skills、collections。临时测试记录和容器已清理 |
| `git diff --check`；旧 SDK 导入搜索 | 通过；应用源码没有旧 SDK 导入 |
| 旧/新客户端方法与路径静态比对 | 逐项比对 145 个有效调用、96 个不同方法，HTTP 方法和路径 145/145 一致；删除的一处旧注释调用不计入运行调用 |

## 边界与未验证项

真实浏览器交互、完整应用 lifespan、其他业务写入链和生产环境尚未验收。数据库保存回读在隔离的临时 PostgreSQL 中用当前 Bot 路由与 Service 验证；原有本地数据库容器口令与 `app/.env` 不一致，因此未对其写入。Next.js 构建的预渲染 HTTP 失败日志来自缺少运行中的应用后端，构建本身成功。

独立只读复核检查了旧/新调用、生成源码、Axios 封装、Bot 与模型请求体及主要响应模型，未发现剩余的迁移缺陷。其指出的一处英文开发指南旧生成器说明已修正。方法/路径静态比对由主任务再次独立运行，结果相同；它不证明所有请求体或运行分支已联调。任何未覆盖路径仍需在实际业务联调中验证。
