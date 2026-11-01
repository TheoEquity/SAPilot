# 接口生成与 Mock 开发接入

目标：保留后端 Python 接口定义作为维护源，使前端能先使用同一契约的 Mock 数据开发，再切换真实后端。未提交或推送。

## 实现

- `web/orval.config.ts`：同一次生成按业务输出请求函数、类型、MSW 处理器和 Faker 数据工厂。对 Orval 8.45 生成的空 Faker 文件，生成后自动排除其无效索引引用；不手改生成产物。
- `web/src/mocks/handlers.ts`：复用生成处理器与类型，提供 Bot 列表及增查改删的内存状态、空列表和 500 错误场景，以及页面所需的用户、模型和空知识库数据。
- `web/src/mocks/server.ts`：将同一组 MSW 处理器用于本地 HTTP 服务。浏览器经已有 Next.js 代理，服务端通过已有 API 客户端访问它，避免浏览器与服务端内存各自保存造成新增后回读不一致。未匹配的请求返回 501，不转发真实后端；WebSocket 不模拟。
- `web/scripts/dev-mock.ts`：启动本地 Mock 与 Next.js，只对 Next 子进程设置 API 地址；不覆盖 `.env`，不改页面和请求客户端。退出时关闭服务，内存数据重置；生产环境拒绝该启动入口。
- `aperag/views/auth.py`：为现有 `/user` 声明实际已返回的 `view_models.User`，使工具生成真实响应结构。未改变鉴权规则。此文件此前的用户删除修复保留。
- `specs/api-contract-conventions.md`：补充 Mock、生成、前后端并行开发及真实联调的规范。高层架构、README 本次未改。

开发依赖固定为 MSW 2.14.6、Faker 10.6.0、tsx 4.23.15；MSW 3 的类型与当前 Orval 产物不兼容，因此未采用。Node 最低版本与既有接口规约统一为 22.18。锁文件与 HEAD 对照，没有改变既有 selector 的依赖版本；保留原有 registry URL，安装时仅临时指定官方源，未改全局包源。

## 使用

在 `web/` 执行：

```bash
yarn api:build                 # 后端接口更新后：导出，再生成客户端和基础 Mock
yarn dev:mock                  # 使用现有生成产物启动，真实后端可以不运行
yarn dev:mock --scenario empty # Bot 初始列表为空
yarn dev:mock --scenario error # Bot 列表及创建返回 500
yarn test:mock                 # 本地 HTTP 服务与生成客户端回归
```

可给开发启动命令追加 `--port 3100`。停止 Mock 后使用正常启动方式，例如 `yarn next dev --turbopack`，恢复真实环境。业务测试场景保留，随需求补充，不维护第二套接口字段定义。

## 实际验证

- 在项目隔离 Python 工具环境下，`yarn api:build` 完整链路通过：导出 138 个 HTTP 操作，Orval 生成客户端与 Mock 成功；全项目 `tsc --noEmit --pretty false --incremental false` 通过。
- `yarn test:mock`：2 个集成测试通过，检查真实生成客户端经 HTTP 的增查改删、模拟浏览器代理写入后的服务端回读、404/保护删除、实例隔离，以及空列表、500 场景。
- 关联 Python 契约回归 18 项通过；认证接口 Ruff、相关 TypeScript 文件 ESLint、格式及差异空白检查通过。
- Yarn 安装完整性及实际依赖树检查均通过。
- 本机默认 Anaconda 的 Pydantic/typing_extensions 存在导入冲突；使用项目隔离工具环境的 Python 执行生成链路，不修改全局 Python。接口规约原有的“激活项目 Python 环境”要求仍适用；直接使用已有产物的 Mock 启动不依赖 Python。
- 浏览器实际打开 Bot 列表、填写新增表单、选择 Mock 模型、保存并进入详情编辑页；返回列表、完整刷新后，新 Bot 仍然存在。
- 停止 Mock，正常启动 Next.js 后，代理的匿名 `/user` 请求恢复 401，浏览器恢复真实登录页；真实后端的 Bot 列表没有新增 Mock 数据。真实 `/user` 的已登录请求为 200，文档响应引用 User。
- 本次测试启动的 Mock 和 Next.js 服务已停止。

原始测试材料、安装日志、依赖版本对照、真实模式检查及页面截图放在旁侧 `../SAPilot-data/runtime/mock-development/2026-10-30/`，未放入源码仓库。

## 验证边界

Bot 的上述场景有状态；其他模块的自动生成数据只用于结构样例，未宣称全部业务流程可离线使用。缺少响应模型的接口仍需在 Python 源头补充声明，不能由 Mock 猜出完整字段。本次未模拟模型回答、文件摄取、WebSocket，也未做生产构建或全项目浏览器验收。空态和失败场景已在 HTTP 测试验证，浏览器本轮验证的是正常新增与刷新回读。
