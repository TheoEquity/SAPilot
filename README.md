# SAPilot – Ops Agent Platform Built on apeRAG
APilot 是一个基于强大apeRAG基础的企业级AI代理平台。继承了apeRAG强大的混合检索（图谱RAG、向量和全文搜索）和多模态处理能力，SAPilot通过为SAP操作设计的专用AI代理扩展这些功能。它通过灵活的框架使SAP顾问能够快速构建、部署和定制复杂的AI应用程序，从而为复杂的 enterprise 场景实现深度二次开发。

 [快速开始](#快速开始)
- [主要特点](#主要特点)
- [Kubernetes 部署（推荐用于生产环境）(#kubernetes-deployment-recommended-for-production)
- [开发](./docs/en-US/development-guide.md)
- [构建Docker镜像](./docs/en-US/build-docker-image.md)
- [致谢](#致谢)
- [许可证](#许可证)




>
> - CPU >= 2 核
> - 内存 >= 4 GiB
> - Docker & Docker Compose

启动SAPilot的最简单方法是通过Docker Compose。在运行以下命令之前，请确保[Docker](https://docs.docker.com/get-docker/)和[Docker Compose](https://docs.docker.com/compose/install/)已安装在您的机器上：

```bash
git clone https://github.com/TheoEquity/WCF.git
cd SAPiolt
cp envs/env.template .env
docker-compose up -d --pull always
```

After running, you can access SAPilot in your browser at:
- **Web Interface**: http://localhost:3000/web/
- **API Documentation**: http://localhost:8000/docs

#### MCP (Model Context Protocol) Support

SApilot supports [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) integration, allowing AI assistants to interact with your knowledge base directly. After starting the services, configure your MCP client with:

```json
{
  "mcpServers": {
    "aperag-mcp": {
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

**Important**: Use your deployed API origin if not local (e.g. `https://your-host/mcp/`). Replace `your-api-key-here` with a valid API key from your ApeRAG settings.

The MCP server provides:
- **Collection browsing：列出和探索您的知识集合
- **混合搜索**：使用向量、全文和图方法进行搜索
- **智能查询**：用自然语言对您的文档进行提问

#### 增强的文档解析

For enhanced document parsing capabilities, ApeRAG supports an **advanced document parsing service** powered by MinerU, which provides superior parsing for complex documents, tables, and formulas. 

<details>
<summary><strong>Enhanced Document Parsing Commands</strong></summary>

```bash
# Enable advanced document parsing service
DOCRAY_HOST=http://aperag-docray:8639 docker compose --profile docray up -d

# Enable advanced parsing with GPU acceleration 
DOCRAY_HOST=http://aperag-docray-gpu:8639 docker compose --profile docray-gpu up -d
```

Or use the Makefile shortcuts (requires [GNU Make](https://www.gnu.org/software/make/)):
```bash
# Enable advanced document parsing service
make compose-up WITH_DOCRAY=1

# Enable advanced parsing with GPU acceleration (recommended)
make compose-up WITH_DOCRAY=1 WITH_GPU=1
```

</details>

#### Development & Contributing

For developers interested in source code development, advanced configurations, or contributing to ApeRAG, please refer to our [Development Guide](./docs/en-US/development-guide.md) for detailed setup instructions.

## Key Features

**1. Advanced Index Types**:
Five comprehensive index types for optimal retrieval: **Vector**, **Full-text**, **Graph**, **Summary**, and **Vision** - providing multi-dimensional document understanding and search capabilities.

**2. Intelligent AI Agents**:
Built-in AI agents with MCP (Model Context Protocol) tool support that can automatically identify relevant collections, search content intelligently, and provide web search capabilities for comprehensive question answering.

**3. 带实体规范化的增强图RAG**:
深度修改的LightRAG实现，具有先进的实体规范（实体合并），以获得更清洁的知识图谱和更好的关系理解。

**4. 多模式处理与视觉支持**:
完成多模态文档处理，包括对图像、图表和视觉内容分析的传统文本处理能力。

**5. 混合检索引擎**:
复杂的检索系统结合了图RAG、向量搜索、全文搜索、基于摘要的检索和基于视觉的搜索，以实现全面的文档理解。

**6. MinerU Integration**:
Advanced document parsing service powered by MinerU technology, providing superior parsing for complex documents, tables, formulas, and scientific content with optional GPU acceleration.

**7. Production-Grade Deployment**:
Full Kubernetes support with Helm charts and KubeBlocks integration for simplified deployment of production-grade databases (PostgreSQL, Redis, Qdrant, Elasticsearch, Neo4j).

**8. Enterprise Management**:
Built-in audit logging, LLM model management, graph visualization, comprehensive document management interface, and agent workflow management.

**9. MCP Integration**:
Full support for Model Context Protocol (MCP), enabling seamless integration with AI assistants and tools for direct knowledge base access and intelligent querying.

**10. Developer Friendly**:
FastAPI backend, React frontend, async task processing with Celery, extensive testing, comprehensive development guides, and agent development framework for easy contribution and customization.

## Kubernetes Deployment (Recommended for Production)

> **Enterprise-grade deployment with high availability and scalability**

Deploy ApeRAG to Kubernetes using our provided Helm chart. This approach offers high availability, scalability, and production-grade management capabilities.

### Prerequisites

*   [Kubernetes cluster](https://kubernetes.io/docs/setup/) (v1.20+)
*   [`kubectl`](https://kubernetes.io/docs/tasks/tools/) configured and connected to your cluster
*   [Helm v3+](https://helm.sh/docs/intro/install/) installed

### Clone the Repository

First, clone the ApeRAG repository to get the deployment files:

```bash
git clone https://github.com/apecloud/ApeRAG.git
cd ApeRAG
```

### Step 1: Deploy Database Services

ApeRAG requires PostgreSQL, Redis, Qdrant, and Elasticsearch. You have two options:

**Option A: Use existing databases** - If you already have these databases running in your cluster, edit `deploy/aperag/values.yaml` to configure your database connection details, then skip to Step 2.

**Option B: Deploy databases with KubeBlocks** - Use our automated database deployment (database connections are pre-configured):

```bash
# Navigate to database deployment scripts
cd deploy/databases/

# (Optional) Review configuration - defaults work for most cases
# edit 00-config.sh

# Install KubeBlocks and deploy databases
bash ./01-prepare.sh          # Installs KubeBlocks
bash ./02-install-database.sh # Deploys PostgreSQL, Redis, Qdrant, Elasticsearch

# Monitor database deployment
kubectl get pods -n default

# Return to project root for Step 2
cd ../../
```

Wait for all database pods to be in `Running` status before proceeding.

### Step 2: Deploy ApeRAG Application

```bash
# If you deployed databases with KubeBlocks in Step 1, database connections are pre-configured
# If you're using existing databases, edit deploy/aperag/values.yaml with your connection details

# Deploy ApeRAG
helm install aperag ./deploy/aperag --namespace default --create-namespace

# Monitor ApeRAG deployment
kubectl get pods -n default -l app.kubernetes.io/instance=aperag
```

### Configuration Options

**Resource Requirements**: By default, includes [`doc-ray`](https://github.com/apecloud/doc-ray) service (requires 4+ CPU cores, 8GB+ RAM). To disable: set `docray.enabled: false` in `values.yaml`.

**Advanced Settings**: Review `values.yaml` for additional configuration options including images, resources, and Ingress settings.

### Access Your Deployment

Once deployed, access ApeRAG using port forwarding:

```bash
# Forward ports for quick access
kubectl port-forward svc/aperag-frontend 3000:3000 -n default
kubectl port-forward svc/aperag-api 8000:8000 -n default

# Access in browser
# Web Interface: http://localhost:3000
# API Documentation: http://localhost:8000/docs
```

For production environments, configure Ingress in `values.yaml` for external access.

### Troubleshooting

**Database Issues**: See `deploy/databases/README.md` for KubeBlocks management, credentials, and uninstall procedures.

**Pod Status**: Check pod logs for any deployment issues:
```bash
kubectl logs -f deployment/aperag-api -n default
kubectl logs -f deployment/aperag-frontend -n default
```

## Acknowledgments

ApeRAG integrates and builds upon several excellent open-source projects:

### LightRAG
The graph-based knowledge retrieval capabilities in ApeRAG are powered by a deeply modified version of [LightRAG](https://github.com/HKUDS/LightRAG):
- **Paper**: "LightRAG: Simple and Fast Retrieval-Augmented Generation" ([arXiv:2410.05779](https://arxiv.org/abs/2410.05779))
- **Authors**: Zirui Guo, Lianghao Xia, Yanhua Yu, Tu Ao, Chao Huang
- **License**: MIT License

We have extensively modified LightRAG to support production-grade concurrent processing, distributed task queues (Celery/Prefect), and stateless operations. See our [LightRAG modifications changelog](./aperag/graph/changelog.md) for details.

## Community

* [Discord](https://discord.gg/FsKpXukFuB)
* [Feishu](docs%2Fen-US%2Fimages%2Ffeishu-qr-code.png)

<img src="docs/en-US/images/feishu-qr-code.png" alt="Feishu" width="150"/>

## Star History

![star-history-2025922.png](docs%2Fen-US%2Fimages%2Fstar-history-2025922.png)

## License

ApeRAG is licensed under the Apache License 2.0. See the [LICENSE](./LICENSE) file for details.
