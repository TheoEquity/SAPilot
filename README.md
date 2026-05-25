# SAPilot – SAP Operations AI Agent Platform

SAPilot is an enterprise-grade AI assistant for SAP operations scenarios. Built as a secondary development of [apeRAG](https://github.com/apecloud/ApeRAG), it inherits powerful hybrid retrieval (Graph RAG, vector and full-text search) and multimodal processing capabilities, and is deeply customized for SAP operations: DingTalk integration, code attachment analysis, centralized prompt management, Agent orchestration UI, and more — enabling SAP consultants to resolve operations issues efficiently through natural language Q&A, screenshot diagnosis, and code document interpretation.

> **Important:** This project is a fork of apeRAG, independently maintained at [TheoEquity/SAPilot](https://github.com/TheoEquity/SAPilot). The original apeRAG installation instructions and documentation are no longer applicable to this project.

[Quick Start](#quick-start)
- [Key Features](#key-features)
- [Docker Compose Deployment](#docker-compose-deployment)
- [Lightweight Deploy (8G/20G Machine)](#8g20g-local-lightweight-deployment)
- [Development Guide](#development-guide)
- [Acknowledgments](#acknowledgments)
- [License](#license)

## Quick Start

The simplest way to deploy SAPilot is via Docker Compose. Ensure you have [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) installed before running:

```bash
git clone https://github.com/TheoEquity/SAPilot.git
cd SAPilot
cp envs/env.template .env
docker-compose up -d
```

After services are running, access in your browser:
- **Web Interface**: http://localhost:3000/
- **API Documentation**: http://localhost:8000/docs

[Read Chinese Documentation](README-zh.md)

## Docker Compose Deployment

### Prerequisites

- CPU >= 2 cores
- RAM >= 4 GiB
- Docker & Docker Compose

### Full Startup

```bash
cd SAPilot
cp envs/env.template .env
docker-compose up -d
```

### MCP (Model Context Protocol) Support

SAPilot supports [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) integration, allowing AI assistants to interact directly with your knowledge base. After starting services, configure your MCP client:

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

**Authentication** (by priority):
1. **HTTP Authorization Header** (Recommended): `Authorization: Bearer your-api-key`
2. **Environment Variable** (Fallback): `APERAG_API_KEY=your-api-key`

Replace `your-api-key-here` with a valid API key from your SAPilot web settings.

### Enhanced Document Parsing

SAPilot supports advanced document parsing powered by MinerU. For local machines with limited resources, keep it disabled unless explicitly needed:

<details>
<summary><strong>Commands</strong></summary>

```bash
DOCRAY_HOST=http://aperag-docray:8639 docker compose --profile docray up -d
DOCRAY_HOST=http://aperag-docray-gpu:8639 docker compose --profile docray-gpu up -d
```

Or use Makefile:

```bash
make compose-up WITH_DOCRAY=1
make compose-up WITH_DOCRAY=1 WITH_GPU=1
```

</details>

## 8G/20G Local Lightweight Deployment

For machines with approximately 8GB RAM and 20GB disk, use lightweight mode:

```bash
cp envs/env.dev-lite.template .env
bash scripts/dev-lite-start.sh
```

This mode automatically reduces Elasticsearch heap, Celery concurrency, and database connection pool sizes — suitable for resource-constrained development machines.

## Key Features

### apeRAG Foundation

1. **Hybrid Retrieval Engine**: Combines Graph RAG, vector search, full-text search, summary retrieval, and vision search
2. **Five Index Types**: Vector, Full-text, Graph, Summary, and Vision
3. **Intelligent AI Agents**: MCP tool support, automatic collection discovery, smart search, web search
4. **Enhanced Graph RAG**: Deeply modified LightRAG with entity normalization
5. **Multimodal Processing**: Image, chart, and visual content analysis
6. **Production-Grade Deployment**: Docker Compose and Kubernetes supported
7. **Enterprise Management**: Audit logs, LLM model management, document management UI

### SAPilot Custom Features

1. **DingTalk Integration**: DingTalk Stream bot接入, supporting image diagnosis and code attachment analysis
2. **Code Attachment Analysis**: DingTalk and web support for uploading code files, .doc/.docx documents; small document full-text injection preferred
3. **Skill Orchestration UI v2**: Visual intent routing, skill configuration, Flow Canvas editor
4. **Centralized Prompt Management**: Edit all 5 prompt templates in `/workspace/prompts` with batch reset
5. **Configuration Import/Export**: Admin can export/import bot configs, prompts, and system settings in one click via `/admin/configuration`
6. **API Key Management**: Token generation for users and API access
7. **Quota Management**: Per-user quota configuration to prevent resource abuse

## Development Guide

### Environment Setup

```bash
git clone https://github.com/TheoEquity/SAPilot.git
cd SAPilot
cp envs/env.template .env
```

### Start Infrastructure

```bash
make compose-infra
```

Starts 4 core infrastructure containers: PostgreSQL, Redis, Qdrant, Elasticsearch.

### Install Backend Dependencies

```bash
.venv/bin/uv sync
```

This project uses `uv` for Python dependency management.

### Start Backend

```bash
.venv/bin/uvicorn aperag.app:app --host 0.0.0.0 --port 8000 --loop uvloop
```

### Start Frontend

```bash
cd web
npm install
npm run dev
```

Frontend runs at http://localhost:3000/.

### Type Checking and Code Quality

```bash
# Backend single-file syntax check
.venv/bin/python -m py_compile <file.py>

# Backend lint
.venv/bin/python -m ruff check <files>

# Frontend full type check
cd web && yarn tsc --noEmit --pretty false

# Frontend code formatting
npx prettier --write <files>
```

## Acknowledgments

SAPilot is built as a secondary development of [apeRAG](https://github.com/apecloud/ApeRAG). Graph retrieval capabilities in apeRAG are powered by a deeply modified version of [LightRAG](https://github.com/HKUDS/LightRAG):

- **Paper**: "LightRAG: Simple and Fast Retrieval-Augmented Generation" ([arXiv:2410.05779](https://arxiv.org/abs/2410.05779))
- **Authors**: Zirui Guo, Lianghao Xia, Yanhua Yu, Tu Ao, Chao Huang
- **License**: MIT License

We have extensively modified LightRAG to support production-grade concurrent processing, distributed task queues (Celery/Prefect), and stateless operations. See our [LightRAG modifications changelog](./aperag/graph/changelog.md) for details.

## License

SAPilot is licensed under the Apache License 2.0. See the [LICENSE](./LICENSE) file for details.
