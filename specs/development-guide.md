---
title: 开发指南
description: SAPilot 开发环境设置和工作流程
---

# 🛠️ 开发指南

本指南重点介绍如何为 SAPilot 设置开发环境和开发工作流程。这是为希望为 SAPilot 做贡献或在本地运行它进行开发的开发人员设计的。

## 本地日志查看与排查

日志字段、打点和脱敏遵循[全栈日志规约](logging-and-diagnostics.md)。浏览器事件在开发者工具的控制台查看，请求状态在网络面板查看；Next.js 服务端日志在运行 Next.js 的终端或容器查看，不能用浏览器控制台代替。

日志配置统一在 `config/logging/`，默认输出到项目旁 `../SAPilot-data/logs/`：`api.log`、`worker.log`、`frontend.log`，每个主文件默认 10 MB，最多保留 3 份备份。设置 `SAPILOT_LOG_DIR` 可覆盖目录；相对路径以项目根为基准。浏览器控制台的诊断导出和页面截图放在 `logs/browser/`，原始验证日志归档放在 `logs/verification/`。浏览器日志不会自动上传，导出时仍须遵循脱敏要求。

API 使用 `config/logging/api.yaml`，worker 复用 Python 的公共配置；本地前端的 `yarn dev` / `yarn start` 通过 `scripts/run-with-logs.mjs` 保存标准输出和错误，同时保留控制台输出。Docker Compose 将 API/worker 的日志目录挂载为 `/logs`；容器内设置 `SAPILOT_LOG_DIR=/logs`。其他启动方式需要使用同一配置与挂载。Docker 自身日志仍可用 `docker logs --since 10m <实际容器名>` 查看，不把本机容器名写死在业务代码里。

前端统一调用 `@/lib/logger`；API 和 worker 使用 Python `logging`，由 `aperag/logging.py` 提供 JSON 格式和上下文。排查时先按 `event`、`document_id` 或 `message_id` 筛选，再看阶段、状态、耗时与异常链中的代码位置。HTTP 响应存在有效追踪时返回 `X-Trace-ID`，前端请求日志复用该值；后台阶段可按同一个文档 ID 关联不同追踪，不要求它们共用一个 trace。

日志基础检查：后端运行 `pytest tests/contract/test_application_logging.py tests/contract/test_stage2_tracing.py`；前端在 `web/` 下运行 `yarn test:logs`。这些检查覆盖日志行为，不代替实际页面操作、模型调用或摄取验收。

排查先确定时间范围和请求/文档/消息标识，再检查页面操作、接口结果、后台阶段与重试，最后关联下节的 Langfuse 追踪。浏览器日志需从用户侧获取或通过受控入口采集；缺少某段日志或追踪时明确标注，不能据此推断该环节成功。私有日志和诊断导出按[目录约定](project-layout.md)保存到项目旁的数据目录，不提交 Git。

## 本地 Langfuse 监控

复用已有的 Langfuse 实例与项目，在本机不提交 Git 的 `.env` 中填写项目 API keys。配置示例见 [`envs/env.monitoring-local.template`](../envs/env.monitoring-local.template)。

- `OTEL_ENABLED=True`、`LANGFUSE_ENABLED=True`：启用应用追踪与 Langfuse 导出。
- `LANGFUSE_BASE_URL`：Langfuse 实例根地址，本机示例为 `http://localhost:3300`。
- `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`：同一 Langfuse 项目的公钥和密钥，保持私有。
- `OPIK_SENTRY_ENABLE=False`：关闭 Opik 的可选 Sentry 错误上报，避免第三方初始化覆盖应用的追踪采样。

应用使用现有 OpenTelemetry SDK，通过 OTLP/HTTP 向 Langfuse 导出；API 与文档 worker 共用接入配置，`OTEL_SERVICE_NAME` 可分别设置。MCP 模型追踪复用应用 Provider，记录用量；对话追踪按会话 ID 关联，文档任务按文档 ID 关联。

本机 Python 进程直接使用上述 localhost 地址。Docker Desktop 下，`envs/docker.env.overrides` 将地址设为 `http://host.docker.internal:3300`；其他部署环境填写容器实际可访问的 Langfuse 地址。容器环境修改后重新创建相应 API / worker 进程。

检查接入时，在 Langfuse 对应项目中确认真实问答和文档任务已产生记录，核对阶段名称、耗时、模型、Token 用量、会话或文档标识和错误状态。具体模型没有价格配置时，费用可能为空，不把空值当作零费用。业务用例是否通过与监控是否收数分别判断。

## 🚀 开发环境设置

按照以下步骤从源代码设置 SAPilot 进行开发：

### 1. 📂 克隆仓库并设置环境

首先，获取源代码并配置环境变量：

```bash
git clone https://github.com/apecloud/SAPilot.git
cd SAPilot
cp envs/env.template .env
```

如果需要，编辑 `.env` 文件以配置您的 AI 服务设置。默认设置适用于下一步启动的本地数据库服务。

8GB 内存、20GB 磁盘的本机开发建议直接使用精简模板：

```bash
cp envs/env.dev-lite.template .env
```

这个模板会降低连接池、并发和配额相关默认值，同时保持 4 个基础设施容器开发模式。
其中 Elasticsearch 默认堆内存为 `512m`，更适合 8GB 本机开发。
其中 Celery worker 默认并发为 `4`，可以进一步降低后台任务的内存占用。
数据库连接池默认也已压到 `4/4`，适合轻量本地开发。

如果使用者是业务同事，可以直接参考一键说明：`docs/zh-CN/deployment/local-lite-business-guide.md`

### 2. 📋 系统前提条件

在开始之前，请确保您的系统具备：

*   **Node.js**：前端接口生成工具需要 22.18 或更高版本，本地开发可使用 Node.js 24。[下载 Node.js](https://nodejs.org/)
*   **Docker & Docker Compose**：本地运行数据库服务所需。[下载 Docker](https://docs.docker.com/get-docker/)

文档 worker 需要 LibreOffice Writer（`soffice`）转换旧 `.doc`，以及 Tesseract 和 `chi_sim`、`eng` 语言数据提取 PDF 截图文字；中文文档转换还需要 CJK 字体。PDF 本地解析保留原文字层，并将页图和 OCR 补充文字关联到同一页，不需要新增外部模型服务；OCR 结果仍需核对原图。项目 Docker 镜像已声明这些系统依赖，修改镜像后需重建并重新创建 worker。直接运行 Python worker 时，应在所在系统安装相同工具，并确认 `soffice`、`tesseract` 可通过 PATH 找到。

**注意**：需要 Python 3.11，但将在下一步中通过 `uv` 自动管理。

### 3. 🗄️ 启动数据库服务

使用 Docker Compose 启动必要的数据库服务：

```bash
# 启动 4 个核心基础设施容器：PostgreSQL、Redis、Qdrant、Elasticsearch
make compose-infra
```

这会在后台启动 4 个开发基础设施容器。默认开发模式不启动 Neo4j、DocRay、GPU/CUDA 相关服务，适合 8GB 内存、20GB 磁盘的本地机器。您的 `.env` 文件中的默认连接设置已预配置为与这些服务一起工作。

<details>
<summary><strong>高级数据库选项</strong></summary>

```bash
# 使用 Neo4j 进行图存储
make compose-infra WITH_NEO4J=1

# 添加高级文档解析服务（DocRay / MinerU）
make compose-infra WITH_DOCRAY=1

# 组合多个选项
make compose-infra WITH_NEO4J=1 WITH_DOCRAY=1

# GPU 加速文档解析（需要 NVIDIA CUDA 和约 6GB VRAM）
make compose-infra WITH_DOCRAY=1 WITH_GPU=1
```

**注意**：DocRay 为复杂的 PDF、表格和公式提供增强的文档解析。CPU 模式需要 4+ 核心和 8GB+ RAM。资源受限机器建议保持默认 4 容器模式。

</details>

### 4. ⚙️ 设置开发环境

创建 Python 虚拟环境并设置开发工具：

```bash
make dev
```

此命令将：
*   如果尚未可用，则安装 `uv`
*   创建 Python 3.11 虚拟环境（位于 `.venv/` 中）
*   前端接口生成工具随 `web/` 中的锁定依赖安装，不另装全局 OpenAPI 生成器
*   为代码质量安装 pre-commit hooks
*   安装 addlicense 工具进行许可证管理

**激活虚拟环境：**
```bash
source .venv/bin/activate
```

当您在终端提示符中看到 `(.venv)` 时，您就知道它是活动的。

### 5. 📦 安装依赖项

安装所有后端和前端依赖项：

```bash
make install
```

此命令将：
*   将 `pyproject.toml` 中的所有 Python 后端依赖项安装到虚拟环境中
*   使用 `yarn` 安装前端 Node.js 依赖项

### 6. 🔄 应用数据库迁移

设置数据库架构：

```bash
make migrate
```

### 7. ▶️ 启动开发服务

现在您可以启动开发服务。为每个服务打开单独的终端窗口/选项卡：

**终端 1 - 后端 API 服务器：**
```bash
make run-backend
```
这将在 `http://localhost:8000` 启动 FastAPI 开发服务器，代码更改时自动重新加载。

**终端 2 - Celery Worker：**
```bash
make run-celery
```
这将启动 Celery worker 以处理异步后台任务。

**终端 3 - 前端（可选）：**
```bash
make run-frontend
```
这将在 `http://localhost:3000` 启动前端开发服务器，支持热重载。

推荐开发启动顺序：

```bash
make compose-infra
make run-backend
make run-frontend
```

这个组合会保留数据库容器化，同时让后端和前端直接基于源码热启动。

### 8. 🌐 访问 SAPilot

服务运行后，您可以访问：
*   **前端 UI**：http://localhost:3000 (如果已启动)
*   **后端 API**：http://localhost:8000
*   **API 文档**：http://localhost:8000/docs

### 9. ⏹️ 停止服务

要停止开发环境：

**停止数据库服务：**
```bash
# 停止数据库服务（保留数据）
make compose-down

# 停止服务并移除所有数据卷
make compose-down REMOVE_VOLUMES=1
```

**停止开发服务：**
- 后端 API 服务器：在运行 `make run-backend` 的终端中按 `Ctrl+C`
- Celery Worker：在运行 `make run-celery` 的终端中按 `Ctrl+C`
- 前端服务器：在运行 `make run-frontend` 的终端中按 `Ctrl+C`

**数据管理：**
- `make compose-down` - 停止服务但保留所有数据（PostgreSQL、Redis、Qdrant 等）
- `make compose-down REMOVE_VOLUMES=1` - 停止服务并**⚠️ 永久删除所有数据**
- 即使已经运行过 `make compose-down`，您也可以运行 `make compose-down REMOVE_VOLUMES=1`

**验证数据移除：**
```bash
# 检查卷是否仍然存在
docker volume ls | grep sapilot

# REMOVE_VOLUMES=1 后应该不返回结果
```

现在您已经从源代码本地运行 SAPilot，准备好进行开发！🎉

## ❓ 常见开发任务

### Q: 🔧 如何添加或修改 REST API 端点？

**完整工作流程：**
1. 按[接口契约规约](api-contract-conventions.md)，在 `aperag/views/` 与 `aperag/schema/` 对应模块维护路由、请求模型、响应模型、状态和说明；不再手改接口 YAML。
2. 实现对应 Service，启动本地后端；通过 `/docs` 或 `/redoc` 查阅接口。
3. 在已激活项目 Python 环境、安装前端依赖后，从 `web/` 执行 `yarn api:build`，自动导出接口描述并由 Orval 生成前端类型和请求函数。
4. 已有导出文件时可运行 `yarn api:generate`。需离线导出时在项目根目录运行 `python scripts/export_openapi.py --app aperag.app:app`，只导入应用而不执行 lifespan。
5. 新产物位于 `web/src/api/generated/`，通过现有 Axios 封装接入；旧 SDK 的业务调用按模块迁移，核对已有扩展，不整体覆盖。
6. 检查相关契约、TypeScript 类型及实际请求响应；生成成功与业务运行验收分别说明。

### Q: 🗃️ 如何修改数据库模型/架构？

**数据库迁移工作流程：**
1. 编辑 `sapilot/db/models.py` 中的 SQLModel 类
2. 生成迁移文件：
   ```bash
   make makemigration  # 在 migration/versions/ 中创建新迁移
   ```
3. 将迁移应用到数据库：
   ```bash
   make migrate  # 更新数据库架构
   ```
4. 更新相关代码（`sapilot/db/repositories/` 中的仓库，`sapilot/service/` 中的服务）
5. 验证更改：
   ```bash
   make test  # ✅ 确保一切正常工作
   ```

### Q: ⚡ 如何添加具有后台处理的新功能？

**功能实现工作流程：**
1. 实现功能组件：
   - 后端逻辑：`sapilot/[module]/`
   - 异步任务：`sapilot/tasks/`
   - 数据库模型：`sapilot/db/models.py`
2. 更新 API 并生成代码：
   ```bash
   make makemigration      # 生成迁移文件
   make migrate           # 应用数据库更改
   make export-openapi    # 从运行中的后端导出接口描述
   make generate-frontend-sdk  # 更新 TypeScript 客户端
   ```
3. 质量保证：
   ```bash
   make format && make lint && make test
   ```

### Q: 🧪 如何运行单元测试和 e2e 测试？

**单元测试（快速，无外部依赖）：**
```bash
# 运行所有单元测试
make unit-test

# 运行特定测试文件
uv run pytest tests/unit_test/test_model_service.py -v

# 运行特定测试类或函数
uv run pytest tests/unit_test/test_model_service.py::TestModelService::test_get_models -v

# 运行带覆盖率的测试
uv run pytest tests/unit_test/ --cov=sapilot --cov-report=html
```

**E2E 测试（需要运行服务）：**
```bash
# 设置：首先启动所需服务
make compose-infra      # 🗄️ 启动数据库
make run-backend       # 🚀 启动 API 服务器（单独终端）

# 运行所有 e2e 测试
make e2e-test

# 运行特定 e2e 测试模块
uv run pytest tests/e2e_test/test_chat/ -v
uv run pytest tests/e2e_test/graphstorage/ -v

# 运行带详细输出且不捕获的测试
uv run pytest tests/e2e_test/test_specific.py -v -s

# 性能基准测试（带计时）
make e2e-performance-test
```

**完整测试套件：**
```bash
# 运行所有内容（单元 + e2e）
make test

# 使用不同配置进行测试
make compose-infra WITH_NEO4J=1  # 使用 Neo4j 而不是 PostgreSQL 进行测试
make test
```

### Q: 🐛 如何调试失败的测试？

**调试工作流程：**
1. 单独运行失败的测试：
   ```bash
   # 带完整输出的单个测试
   uv run pytest tests/unit_test/test_failing.py::test_specific_function -v -s
   
   # 在第一次失败时停止
   uv run pytest tests/unit_test/ -x --tb=short
   ```
2. 对于 e2e 测试失败，确保服务正在运行：
   ```bash
   make compose-infra       # 数据库服务
   make run-backend         # API 服务器
   make run-celery         # 后台 workers（如果测试异步任务）
   ```
3. 使用调试工具：
   ```bash
   # 使用 pdb 调试器运行
   uv run pytest tests/unit_test/test_failing.py --pdb
   
   # 在测试期间捕获日志
   uv run pytest tests/e2e_test/test_failing.py --log-cli-level=DEBUG
   ```
4. 修复并重新测试：
   ```bash
   make format              # 自动修复样式问题
   make lint               # 检查剩余问题
   uv run pytest tests/path/to/fixed_test.py -v  # 验证修复
   ```

### Q: 📊 如何运行 RAG 评估和分析？

**评估工作流程：**
```bash
# 确保环境准备就绪
make compose-infra WITH_NEO4J=1  # 使用 Neo4j 获得更好的图性能
make run-backend
make run-celery

# 运行全面的 RAG 评估
make evaluate               # 📊 运行 sapilot.evaluation.run 模块

# 📈 检查 tests/report/ 中的评估报告
```

### Q: 📦 如何安全地更新依赖项？

**Python 依赖项：**
1. 编辑 `pyproject.toml`（添加/更新包）
2. 更新虚拟环境：
   ```bash
   make install            # 使用 uv 同步所有组和额外内容
   make test              # 验证兼容性
   ```

**前端依赖项：**
1. 编辑 `frontend/package.json`
2. 更新并测试：
   ```bash
   cd frontend && yarn install
   make run-frontend      # 测试前端编译
   make generate-frontend-sdk  # 确保 API 客户端仍然工作
   ```

### Q: 🚀 如何准备代码进行生产部署？

**部署前检查清单：**
1. 代码质量验证：
   ```bash
   make format            # 自动修复所有样式问题
   make lint             # 验证无样式违规
   make static-check     # MyPy 类型检查
   ```
2. 全面测试：
   ```bash
   make test             # 所有单元 + e2e 测试
   make e2e-performance-test  # 性能基准测试
   ```
3. API 一致性：
   ```bash
   make export-openapi          # 从 Python 路由和模型导出接口描述
   make generate-frontend-sdk   # 更新前端客户端
   ```
4. 数据库迁移：
   ```bash
   make makemigration    # 生成任何待处理的迁移
   ```
5. 全栈集成测试：
   ```bash
   make compose-up WITH_NEO4J=1 WITH_DOCRAY=1  # 类似生产的设置
   # 在 http://localhost:3000/web/ 手动测试
   make compose-down
   ```

### Q: 🔄 如何完全重置我的开发环境？

**核选项重置（销毁所有数据）：**
```bash
make compose-down REMOVE_VOLUMES=1  # ⚠️ 停止服务 + 删除所有数据
make clean                         # 🧹 清理临时文件

# 重新开始
make compose-infra                 # 🗄️ 新的数据库
make migrate                      # 🔄 应用所有迁移
make run-backend                  # 🚀 启动 API 服务器
make run-celery                   # ⚡ 启动后台 workers
```

**软重置（保留数据）：**
```bash
make compose-down                 # ⏹️ 停止服务，保留数据
make compose-infra               # 🗄️ 重启数据库
make migrate                    # 🔄 应用任何新迁移
```

**仅重置 Python 环境：**
```bash
rm -rf .venv/                   # 🗑️ 移除虚拟环境
make dev                       # ⚙️ 重新创建所有内容
source .venv/bin/activate      # ✅ 重新激活
``` 
