# 接口代码优先与前端生成实施记录

日期：2026 年 10 月 30 日。

## 目标与范围

用户确认采用 FastAPI/Pydantic 维护接口、Swagger/ReDoc 提供文档、Orval 生成前端调用的方向。本轮接通全量 HTTP 导出与应用客户端生成，并以 Bot 列表读取、删除验证浏览器和服务器接入；其余页面按模块迁移，不整体覆盖旧 SDK，不修改业务 Service、数据结构或聊天协议。

维护规则见 [接口契约规约](../specs/api-contract-conventions.md)，由根 `AGENTS.md` 直接引用。README 不承载开发规则。

## 改动与依据

- `aperag/schema/view_models.py` 保留全部模型定义，仅将生成标记改为 Python 维护归属；取消 Makefile 中反向生成 Python 模型的入口。
- `scripts/export_openapi.py` 从运行服务的 `/openapi.json` 或导入的 `aperag.app:app` 导出完整 JSON、按 tag 的模块 JSON，以及 Swagger/ReDoc HTML。检查操作标识、内部引用和输出路径；输入错误不改写已有产物。
- FastAPI 默认的 `/docs`、`/redoc`、`/openapi.json` 沿用同一套路由和模型。原 YAML、旧 SDK 和旧构建器保留用于兼容、核对，退出默认维护链路。
- `web/orval.config.ts` 使用固定 Orval 8.45.0，按 tag 分模块，输出到 `web/src/api/generated/`。生成针对 `/api/v1/` 的应用客户端，去除一次路径前缀以复用现有 Axios 基础地址；文档保留完整路径。
- 浏览器和服务器请求封装增加 `bots` 客户端，保留原有 Axios、Cookie、语言、超时、错误处理和旧客户端。Bot 列表页面改用新读取调用，列表删除改用新删除调用；列表类型使用新模型，不复制或断言旧模型。
- Bot 路由补稳定操作标识和摘要，删除接口文档标为实际返回的 204。钉钉既有 GET/HEAD 回调拆成同一函数的两个路由装饰器，消除导出时重复操作标识；处理函数不变。
- `web/package.json` 默认入口改为 `api:export`、`api:generate`、组合 `api:build`；原 `api:bundle` 转为导出别名。Makefile 增加 `export-openapi`，停止安装不再用于默认链路的全局生成器。
- AGENTS、接口规约、相关引用和开发环境命令同步。Node.js 开发要求为 22.18 或更高版本；生产运行镜像未因生成工具调整。

## 实际验证

| 检查 | 结果与边界 |
| --- | --- |
| 真实应用离线导出 | 在既有后端依赖镜像中只读挂载最新工作区、关闭网络导入应用，导出 138 个 HTTP 操作、31 个 tag 分组；未启动应用 lifespan |
| 真实应用文档 HTTP | 使用真实应用的 TestClient，请求 `/docs`、`/redoc`、`/openapi.json` 均为 200；核对 Bot 操作标识和删除 204；未验证浏览器 CDN 资源加载或业务请求 |
| 默认生成入口 | `yarn api:build` 成功；用临时本地 HTTP 文件服务承载真实应用导出的 JSON，验证 HTTP 读取到前端生成的链路；临时服务已关闭，没有启动完整业务服务 |
| 生成范围与稳定性 | `/api/v1/` 覆盖 136 个操作，生成 461 份 TypeScript 文件；重复生成逐文件哈希一致 |
| 请求接入 | 真实生成代码与 Axios 经本地网络适配器测试，覆盖地址前缀、浏览器 5 秒和服务器 15 秒超时、Cookie、语言、错误提示及高级字段、false/null 保留；网络和 Next 上下文为测试替身 |
| 契约回归 | 代码优先 8 项、既有 Bot/意图契约及旧构建器回归，共 75 项通过；保留一个第三方 TestClient 弃用警告 |
| 静态检查 | 全项目 `tsc --noEmit --incremental false`、相关 ESLint、Python Ruff 与格式检查、JS 语法检查、Git 差异空白检查通过 |
| 锁定安装 | 固定依赖的离线 frozen-lockfile 安装通过，跳过第三方安装脚本；使用经过完整性校验的临时归档镜像与隔离缓存，临时 `.yarnrc` 已删除；原有 1713 个锁选择器的内容和版本保持不变，Axios 沿用 1.16.1、Zod 沿用 4.4.3 |
| 原有改动保护 | 对照本轮开始时哈希，范围外 1414 份原有文件未变；未更新 Git index、提交、推送或部署 |

安装初期遇到不完整缓存与归档校验失败，未跳过完整性验证或修改原有依赖版本；改用逐包校验的任务内镜像和隔离缓存完成安装。检查摘要和短期原始日志位于被忽略的 `.run/openapi-tools/`。

## 保留边界与下一步

未进行真实数据库鉴权、Bot 业务端到端、浏览器页面交互、完整 Next 生产构建或部署验收。源码中宽泛的 dict、直接 Response 和流式响应仍需随相关模块补足具体契约；生成成功不表示全部接口描述已经完整。

其他页面仍使用旧 SDK，聊天 WebSocket 和非 `/api/v1/` 兼容前缀未切换到应用客户端。后续由处理对应业务需求的主 Agent 按模块维护 Python 契约、重新生成、迁移调用并完成对应验证，不重复手工维护 YAML，也不将本轮局部试点表述为全量迁移完成。
