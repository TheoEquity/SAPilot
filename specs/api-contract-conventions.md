# 接口契约维护规约

本文规定接口定义、文档和前端调用的维护方式。公共变更按[开发流程与公共变更边界](development-workflow.md#公共变更与已有授权)处理。

## 维护源与归属

HTTP 接口采用代码优先：FastAPI 路由和 Python 请求、响应模型是维护源，OpenAPI 是自动导出的产物。接口按“HTTP 方法＋路径”标识，架构只说明职责与边界，不复制接口或字段清单。

| 内容 | 维护位置与规则 |
| --- | --- |
| 路由与协议 | `aperag/views/` 对应业务模块；新增接口优先新增独立 Python 文件，修改接口修改对应实现；沿用 FastAPI Router 注册，不另建手工 OpenAPI 接口清单 |
| 请求、响应与共享类型 | `aperag/schema/`；已有模型在 `view_models.py`，新增模型按业务就近组织，公共结构复用，不为迁移批量拆分已有模型 |
| 业务逻辑 | 对应 Service，路由负责协议、身份和调用，不把业务实现写进接口导出工具 |
| 前端生成代码 | `web/src/api/generated/`；由 Orval 生成，手工适配与请求策略放在 `web/src/lib/api/` |
| 聊天事件 | 对照 `aperag/agent/response_types.py`、聊天路由和实际前端消费单独维护，不把 WebSocket 当普通 HTTP 接口生成 |

接口注册进 FastAPI 后参与导出；新业务 Router 需按应用入口注册，未注册的文件不会自动暴露。`aperag/api/` 下原有 YAML 和旧生成工具仅供历史核对，不作为新接口或修改接口的维护入口，也不再由 YAML 生成覆盖 Python 模型。

## 路由与模型要求

- 明确请求体、路径和查询参数、返回模型、状态码、默认值、必填与可空、错误响应及资源权限；描述、字段说明和示例在 Python 路由或模型维护，随代码进入文档。
- 路由使用业务 `tags` 分组；tag 使用字母开头的字母、数字、连字符或下划线。保持 `operation_id` 唯一、稳定；同一路径多个 HTTP 方法分别标识，不因改函数名意外重命名前端调用。
- 返回 `dict`、直接 `Response`、文件或流式结果时，按实际协议声明必要的模型、媒体类型、状态和错误，不能把类型不完整称为文档完整。
- 保留已有字段、nullable、默认值、显式清空、配置保存、鉴权和错误语义；契约整理不自动授权增加业务执行能力。

## 文档与导出

服务默认提供 `/docs`（Swagger UI）、`/redoc` 和 `/openapi.json`。开发者通过页面查阅、调试，工具读取同一份机器可读描述；查看文档不等于运行验收通过。

在已激活项目 Python 环境、后端运行于默认本地端口时，从项目根目录执行：

```bash
python scripts/export_openapi.py
# 其他本地地址
python scripts/export_openapi.py --url http://localhost:8000/openapi.json
# 不启动服务，使用已安装后端依赖导出；不运行应用 lifespan
python scripts/export_openapi.py --app aperag.app:app
# 只导出指定业务分组，可重复 --module
python scripts/export_openapi.py --module bots --module collections
```

默认输出 `.run/openapi/openapi.json`、按 tag 分组的 `.run/openapi/modules/<分组>.json`，以及 `.run/openapi/docs/index.html`、`redoc.html`。各模块带所需的公共定义；全量与模块产物数量不绑定。只选模块时只更新选定模块，不要求生成全量文件。

`--output` 可指定产物目录。导出先检查操作标识和内部引用，输入错误时保留已有文件；产物不写入后端源目录，不通过链接重定向输出。相同输入产生稳定 JSON。浏览导出的文档需经 HTTP 服务提供，页面资源使用 Swagger/ReDoc 默认 CDN，离线环境需另行解决资源供应；后端服务自身的文档入口优先用于本地调试。

## 前端生成与接入

使用 Node.js 22.18 或更高版本安装 `web/` 的锁定依赖后，在 `web/` 执行：

```bash
yarn api:build       # 从运行中的后端导出，再生成前端类型和请求函数
yarn api:export      # 单独导出，可追加 --url 或 --app
yarn api:generate    # 使用已导出的 JSON 生成，无需再次启动服务
```

Orval 配置在 `web/orval.config.ts`，按 tag 分模块，类型另放模型目录；不手改产物。应用客户端针对 `/api/v1/` 路由生成相对请求路径，复用已有浏览器、服务器 Axios 封装的基础地址、鉴权、语言、Cookie、超时和错误处理。其他前缀的兼容 API 不接入这套应用基础地址。

业务调用先核对生成候选与受影响调用方，再采用任务涉及的接口；已有 `web/src/api/` 旧 SDK 调用保持兼容，迁移到生成目录时逐模块验证，不整体覆盖其手工扩展。不得长期在旧 SDK、YAML 和新 Python 模型重复维护同一个新契约。

## 变更与检查

1. 沿页面、请求封装、路由、Service 和数据核对直接相关路径，明确修改范围。
2. 在 Python 路由、请求与响应模型维护契约，导出后核对字段、状态和实际路由覆盖。
3. 运行生成、TypeScript 检查及相关契约测试，核对未编辑字段、默认值、空值、导出和既有扩展。
4. 按任务风险验证实际请求响应和必要保存回读；静态类型与生成成功不能替代运行验收。
5. 文档保持维护规则，实施进展、迁移批次和未验证项放在根目录 `records/`。

## WebSocket 与历史消息

- 分别核对连接地址与鉴权、Bot / 会话身份、问题和附件等请求字段、实际事件及消费方式。
- 对 `start`、`message`、`thinking`、`tool_call_result`、`stop`、`error` 和业务分支事件，按影响核对字段、顺序、追加方式、引用、错误和结束语义，不由一个类型定义推断协议已完整覆盖。
- 请求消息、实时事件与持久化历史格式分别处理；停止按钮、连接断开与后端任务取消的效果需实际验证。
- 保留 Agent 与传统 Flow 的实际协议边界。组件或目录整理不自动构成传输协议、响应包装或业务语义变更。
