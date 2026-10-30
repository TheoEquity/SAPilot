# SAPilot v1.2.0 – SAP 运维场景智能助手

[文档入口](docs/README.md) · [目录与提交规则](specs/project-layout.md)

SAPilot 是一个面向 SAP 运维场景的企业级 AI 智能助手。基于 [apeRAG](https://github.com/apecloud/ApeRAG) 二次开发，继承了其强大的混合检索（图谱 RAG、向量和全文搜索）和多模态处理能力，并针对 SAP 运维场景进行了深度定制：钉钉集成、代码附件分析、提示词集中管理、Agent 编排 UI 等特色能力，使 SAP 顾问能够通过自然语言问答、截图问诊、代码文档解读等方式高效解决运维问题。

> **重要说明：** 本项目为 apeRAG 的二次开发版本，已独立维护于 [TheoEquity/SAPilot](https://github.com/TheoEquity/SAPilot) 仓库。原版 apeRAG 的安装说明和文档不再适用于本项目。

## 项目资料地图

这份地图供项目负责人查阅资料、回顾项目组织方式，可以在阶段性整理时不定期更新。日常新增或修改接口、字段、页面，不需要同步修改 README；README 不参与开发流程或验收。实际开发约定由 [AGENTS.md](AGENTS.md) 直接引用具体规约。

| 想了解什么 | 放在哪里 | 内容与用途 |
| --- | --- | --- |
| 产品目标与 SAP 业务背景 | [项目背景](docs/SAPILOT_PROJECT_CONTEXT.md) | 说明项目要解决什么问题、业务范围和验收方向 |
| 高层架构 | [工程架构概述](specs/engineering-architecture.md) | 说明模块分别做什么、职责边界和依赖关系，不维护接口或字段清单 |
| 开发规约 | [specs/](specs/) | 开发流程、前端、后端、数据库及接口维护约定，与架构概述分别存放 |
| 开发环境与目录说明 | [开发环境说明](specs/development-guide.md)、[项目目录约定](specs/project-layout.md) | 查本地环境、运行方式及各类文件的归属 |
| 具体实现与处理链路 | [当前实现说明](docs/zh-CN/design/current/) | 解释消息处理、摄取、检索和存储等实现，供深入查阅 |
| 讨论稿与备选方案 | [discussions/](docs/zh-CN/design/discussions/) | 保留思路、理由和备选方案，讨论内容不自动成为开发决定 |
| 项目大步骤 | [开发路线记录](records/development-roadmap.md) | 回顾整体推进步骤、阶段关注点和待明确事项 |
| 实施、审核与验证记录 | [records/](records/) | 查某一轮改了什么、验证了什么、还剩什么；过程材料与架构、规约分开 |
| 部署、集成与其他资料 | [文档目录](docs/README.md) | 汇集部署说明、钉钉与 MCP 集成、测试手册及参考资料 |
| 旧资料与历史讨论 | [归档](docs/archive/)、[历史设计](docs/zh-CN/design/historical/)、[保留原稿](docs/zh-CN/design/pending-review/) | 供回顾背景和追溯旧方案，不代表当前实现或开发要求 |
| 代码与自动化测试 | [aperag/](aperag/)、[web/](web/)、[tests/](tests/) | 分别是后端、前端和测试代码 |
| 启动脚本与配置模板 | [scripts/](scripts/)、[config/](config/)、[envs/](envs/)、[deploy/](deploy/) | 脚本、应用配置和环境、部署模板 |
| 接口维护与生成位置 | [接口规约](specs/api-contract-conventions.md) | Python 路由与模型位于 `aperag/views/`、`aperag/schema/`；前端生成代码位于 `web/src/api/generated/`，导出文档位于本地 `.run/openapi/` |
| 私有资料与临时产物 | 项目旁的 `../SAPilot-data/`；项目内的 `.run/` | 前者保存私有语料、原始评测和模型权重，后者保存临时运行与生成产物；均不随仓库提交。`models/` 保存配置目录，不是模型权重 |

[快速开始](#快速开始)
- [核心特性](#核心特性)
- [Docker Compose 部署](#docker-compose-部署)
- [轻量部署（8G/20G 本地机器）](#8g20g-本地轻量部署)
- [开发指南](#开发指南)
- [致谢](#致谢)
- [许可证](#许可证)

## 快速开始

部署 SAPilot 最简单的方式是通过 Docker Compose。运行以下命令前，请确保已安装 [Docker](https://docs.docker.com/get-docker/) 和 [Docker Compose](https://docs.docker.com/compose/install/)：

```bash
git clone https://github.com/TheoEquity/SAPilot.git
cd SAPilot
cp envs/env.template .env
docker-compose up -d
```

运行后在浏览器访问：
- **Web 界面**: http://localhost:3000/
- **API 文档**: http://localhost:8000/docs

## Docker Compose 部署

### 前提条件

- CPU >= 2 核
- 内存 >= 4 GiB
- Docker & Docker Compose

### 完整启动

```bash
cd SAPilot
cp envs/env.template .env
docker-compose up -d
```

### MCP（模型上下文协议）支持

SAPilot 支持 [MCP（模型上下文协议）](https://modelcontextprotocol.io/) 集成，允许 AI 助手直接与知识库交互。启动服务后，使用以下配置 MCP 客户端：

```json
{
  "mcpServers": {
    "sapilot-mcp": {
      "url": "http://localhost:8000/mcp/",
      "headers": {
        "Authorization": "Bearer your-api-key-here"
      }
    }
  }
}
```

**认证方式**（按优先级）：
1. **HTTP Authorization 头**（推荐）：`Authorization: Bearer your-api-key`
2. **环境变量**（备用）：`APERAG_API_KEY=your-api-key`

将 `your-api-key-here` 替换为 SAPilot Web 设置中的有效 API 密钥。

### 增强文档解析

SAPilot 支持 MinerU 提供的高级文档解析服务。低资源本地机器建议保持关闭，仅在需要高级解析且资源充足时启用：

<details>
<summary><strong>启用高级文档解析命令</strong></summary>

```bash
DOCRAY_HOST=http://aperag-docray:8639 docker compose --profile docray up -d
DOCRAY_HOST=http://aperag-docray-gpu:8639 docker compose --profile docray-gpu up -d
```

或使用 Makefile：

```bash
make compose-up WITH_DOCRAY=1
make compose-up WITH_DOCRAY=1 WITH_GPU=1
```

</details>

## 8G/20G 本地轻量部署

对于 8GB 内存、20GB 磁盘的本地机器，建议使用轻量模式：

```bash
cp envs/env.dev-lite.template .env
bash scripts/dev-lite-start.sh
```

此模式自动降低 Elasticsearch 堆内存、Celery 并发和数据库连接池大小，适合资源受限的开发机器。

## 核心特性

### apeRAG 基础能力

1. **混合检索引擎**：结合图 RAG、向量搜索、全文搜索、摘要检索和视觉搜索
2. **五种索引类型**：向量、全文、图谱、摘要、视觉
3. **智能 AI 代理**：支持 MCP 工具，自动识别集合、智能搜索、网络搜索
4. **增强的图 RAG**：深度修改的 LightRAG，支持实体规范化
5. **多模态处理**：支持图像、图表和视觉内容分析
6. **生产级部署**：支持 Docker Compose 和 Kubernetes
7. **企业管理**：审计日志、LLM 模型管理、文档管理界面

### SAPilot 二开特性

1. **钉钉集成**：钉钉 Stream 机器人接入，支持图片问诊和代码附件分析
2. **代码附件分析**：钉钉和 Web 端支持上传代码文件、.doc/.docx 文档，小文件全文注入优先
3. **Skill 编排 UI v2**：可视化意图路由、Skill 配置、Flow Canvas 编辑器
4. **提示词集中管理**：在 `/workspace/prompts` 统一编辑 5 种提示词模板并支持全部重置
5. **配置导入导出**：管理员可在 `/admin/configuration` 一键导出/导入 Bot 配置、提示词和系统设置
6. **API Key 管理**：支持为用户和 API 生成令牌
7. **配额管理**：按用户配置调用配额，防止资源滥用

## 开发指南

### 环境准备

```bash
git clone https://github.com/TheoEquity/SAPilot.git
cd SAPilot
cp envs/env.template .env
```

### 启动基础设施

```bash
make compose-infra
```

启动 PostgreSQL、Redis、Qdrant、Elasticsearch 四个核心基础设施容器。

### 安装后端依赖

```bash
.venv/bin/uv sync
```

本项目使用 `uv` 管理 Python 依赖，会自动创建虚拟环境并安装依赖。

### 启动后端

```bash
.venv/bin/uvicorn aperag.app:app --host 0.0.0.0 --port 8000 --loop uvloop
```

### 启动前端

```bash
cd web
npm install
npm run dev
```

前端运行在 http://localhost:3000/。

### 类型检查和代码规范

```bash
# 后端单文件语法检查
.venv/bin/python -m py_compile <file.py>

# 后端 lint
.venv/bin/python -m ruff check <files>

# 前端全量类型检查
cd web && yarn tsc --noEmit --pretty false

# 前端代码格式化
npx prettier --write <files>
```

## 致谢

SAPilot 基于 [apeRAG](https://github.com/apecloud/ApeRAG) 进行二次开发。apeRAG 的图检索能力基于深度修改的 [LightRAG](https://github.com/HKUDS/LightRAG)：

- **论文**: "LightRAG: Simple and Fast Retrieval-Augmented Generation" ([arXiv:2410.05779](https://arxiv.org/abs/2410.05779))
- **作者**: Zirui Guo, Lianghao Xia, Yanhua Yu, Tu Ao, Chao Huang
- **许可证**: MIT License

我们在 LightRAG 基础上进行了广泛修改，以支持生产级并发处理、分布式任务队列（Celery/Prefect）和无状态操作。详情参见 [LightRAG 修改更新日志](./aperag/graph/lightrag/CHANGELOG-zh.md)。

## 许可证

SAPilot 采用 Apache License 2.0 许可。详情请参见 [LICENSE](./LICENSE) 文件。
