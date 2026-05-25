# 用户指令记忆

本文件记录了用户的指令、偏好和教导，用于在未来的交互中提供参考。

## 格式

### 用户指令条目
用户指令条目应遵循以下格式：

[用户指令摘要]
- Date: [YYYY-MM-DD]
- Context: [提及的场景或时间]
- Instructions:
  - [用户教导或指示的内容，逐行描述]

### 项目知识条目
Agent 在任务执行过程中发现的条目应遵循以下格式：

[项目知识摘要]
- Date: [YYYY-MM-DD]
- Context: Agent 在执行 [具体任务描述] 时发现
- Category: [代码结构|代码模式|代码生成|构建方法|测试方法|依赖关系|环境配置]
- Instructions:
  - [具体的知识点，逐行描述]

## 去重策略
- 添加新条目前，检查是否存在相似或相同的指令
- 若发现重复，跳过新条目或与已有条目合并
- 合并时，更新上下文或日期信息
- 这有助于避免冗余条目，保持记忆文件整洁

## 条目

[SAPilot 变更验证命令]
- Date: 2026-05-13
- Context: Agent 在执行图片搜索历史与附件展示修复时发现
- Category: 测试方法
- Instructions:
  - 后端单文件语法检查可使用 `.venv/bin/python -m py_compile <files>`。
  - 后端 lint 可使用 `.venv/bin/python -m ruff check <files>`。
  - 图搜相关单测可使用 `.venv/bin/python -m pytest tests/unit_test/test_image_search_refactor.py -q`。
  - 前端格式检查可在 `web` 目录使用 `npx prettier --check <files>`。
  - 前端全量类型检查可在 `web` 目录使用 `yarn tsc --noEmit --pretty false`。

[SAPilot 聊天附件图片预览交互]
- Date: 2026-05-13
- Context: 用户要求聊天中上传的图片附件点击回看时采用平台同类交互
- Instructions:
  - 聊天图片附件应以小图标/附件入口展示，点击后在页面内弹窗回看原图。
  - 图片回看弹窗应支持鼠标滚轮放大缩小。

[SAPilot 钉钉现场问诊助手管理规则]
- Date: 2026-05-13
- Context: 用户规划 1.1 版本钉钉接口配置和专用 Agent 管理方式
- Instructions:
  - 钉钉现场问诊助手只能由 admin 管理员账号创建和配置。
  - 钉钉接口启用并绑定该助手后，该 Agent Bot 应进入删除保护状态。
  - 钉钉问诊通道应尽量采用和 Web Agent 一致的问答策略；不要额外限制 100 字、500 字、3 到 5 步等钉钉专用回答格式。
  - 钉钉通道只做消息接收、即时回复、Markdown 发送和图片上下文适配，普通文本应原样交给 Agent 分流。

[远程仓库同步规则]
- Date: 2026-05-24
- Context: 用户要求后续推送远程仓必须明确要求才可执行
- Instructions:
  - 后续同步远程仓（git push）必须用户明确要求后才可执行
  - 远程仓实际为备份用途，不是日常开发推送目标
  - 本地 git add + commit 可以正常进行

[SAPilot 代码修改授权规则]
- Date: 2026-05-13
- Context: 用户要求先分析 FAQ 故障问答机器人恢复问题
- Instructions:
  - 未经用户明确许可，不要修改代码。
  - 对已经磨合稳定的 FAQ 故障问答和图片检索链路，先按链路分析原因，再等待用户确认是否执行修改。

[SAPilot FAQ 故障问答回答流程]
- Date: 2026-05-13
- Context: 用户要求恢复 FAQ 故障问答机器人的原回答流程和格式，后改为方案B条件化搜索
- Instructions:
  - FAQ 故障问答机器人首轮回答应注明"基于知识库标准答案"。
  - 首轮回答只基于知识库问答内容整理，处理步骤严格按知识库中的步骤列出，避免 LLM 自行扩展。
  - 首轮回答末尾追问"是否需要我从专业角度扩展解答？"。
  - 用户回复确认语后，LLM 结合上一轮 FAQ 标准答案、用户原问题和自身知识自由补充回答，作为顾问参考。
  - 图搜命中后取 faq_title（而非问题描述）作为检索关键词交给 LLM，后续按文本问答流程回答。
  - 方案B：默认自由对话不搜知识库，只有明确触发才注入搜索工具。触发条件：上传图片、明确搜索请求、含SAP业务关键词、扩展确认。
  - 非触发场景用 tool_filter={"aperag": set()} 禁用 MCP 工具，LLM 自由回答。
  - 1.3版本将引入工作流和意图识别替代当前规则触发器。

[SAPilot 钉钉 Stream 图片接收规则]
- Date: 2026-05-14
- Context: Agent 在验证钉钉 Stream 模式图片接收链路时发现
- Category: 代码模式
- Instructions:
  - Stream 模式接收图片时，优先使用 `ChatbotMessage.get_image_list()` 获取原始 `downloadCode`。
  - 避免用 SDK 的 `extract_image_from_incoming_message()` 作为接收判断，因为该 helper 会立即下载并重新上传图片，容易把“收到图片凭证”和“下载图片失败”混在一起。
  - 钉钉端发图能命中图搜时，说明第一步“Agent 能收到钉钉图片凭证并进入图搜链路”已打通。

[SAPilot 知识库存在性问题规则]
- Date: 2026-05-14
- Context: 用户指出询问“知识库里是否有某资料”时，LLM 应依据本地知识库回答
- Instructions:
  - 用户提到“知识库”“库里”“本地知识库”“是否收录”“有没有相关文档/资料”等存在性问题时，必须触发本地知识库搜索。
  - 回答知识库是否存在某资料时，应基于本地知识库检索结果，不使用 LLM 自身知识推断。
  - 用户特意指明“外部知识库”“官方知识库”“SAP官方”“你的知识库”等非本地知识库语义时，不触发本地知识库搜索，交由 LLM 自由回答；单独出现 SAP 字样不能作为排除条件。
  - SAP、ABAP、报错、流程等业务词不能自动触发本地知识库搜索；顾问需要查库时应明确说“从知识库查/查知识库”。

---

## 项目基本信息

### 项目概况
- **项目名称**: SAPilot
- **项目定位**: SAP 运维场景智能助手，面向企业知识库与运维经验
- **基础平台**: 基于 aperag（ApeCloud RAG 平台）二次开发
- **GitHub**: https://github.com/TheoEquity/SAPilot
- **主分支**: main / master
- **开发分支**: feat/orchestration-ui-v2（能力编排 UI v2）

### 项目结构
```
/workspace/
├── aperag/              # 后端 (Python/FastAPI)
│   ├── db/              # 数据库模型和 ORM 操作
│   ├── index/           # 索引引擎 (Vector/Fulltext/Graph/Summary/Vision)
│   ├── llm/             # LLM 服务封装 (Completion/Embed/Rerank)
│   ├── service/         # 业务逻辑层
│   ├── tasks/           # Celery 异步任务
│   ├── views/           # FastAPI 路由
│   ├── graph/           # 知识图谱 (LightRAG)
│   ├── docparser/       # 文档解析
│   └── vectorstore/     # 向量存储连接器
├── web/                 # 前端 (Next.js)
│   ├── src/app/         # App Router 页面
│   ├── src/components/  # 共享组件
│   ├── src/lib/         # 工具库和 API 客户端
│   └── src/i18n/        # 国际化 (zh-CN, en-US)
├── deploy/              # 部署脚本和配置
├── tests/               # 测试代码
├── docs/                # 项目文档
└── .monkeycode/         # AI Agent 记忆和配置
```

### 技术栈
- **后端**: Python 3.11 + FastAPI + Celery + SQLAlchemy
- **前端**: Next.js + React + TypeScript + TailwindCSS + next-intl
- **异步任务**: Celery (线程池模式)
- **LLM 框架**: LiteLLM（统一多提供商接口）

---

## 基础设施配置

### 数据库 (PostgreSQL)
| 配置项 | 值 |
|--------|-----|
| Host | 127.0.0.1 |
| Port | 5432 |
| Database | postgres |
| User | postgres |
| Password | postgres |
| 连接池大小 | 20 |
| 最大溢出 | 40 |
| 超时 | 60s |
| 回收周期 | 3600s |

### Redis
| 配置项 | 值 |
|--------|-----|
| Host | 127.0.0.1 |
| Port | 6379 |
| User | default |
| Password | password |
| DB 0 | Celery Broker / Result Backend |
| DB 1 | Memory Backend |

### Elasticsearch (全文搜索)
| 配置项 | 值 |
|--------|-----|
| Host | 127.0.0.1 |
| Port | 9200 |
| Protocol | http |
| Timeout | 30s |
| Max Retries | 3 |

### Qdrant (向量数据库)
| 配置项 | 值 |
|--------|-----|
| URL | http://localhost |
| Port | 6333 |
| Distance | Cosine |
| 向量集合 | 每 Collection 独立，命名规则由 `generate_vector_db_collection_name` 生成 |

### 对象存储
- **类型**: 本地存储 (local)
- **根目录**: `/workspace/.objects/`
- **结构**: `.objects/user-{userId}/col{collectionId}/doc{documentId}/`

### Celery Worker
| 配置项 | 值 |
|--------|-----|
| 启动命令 | `celery -A config.celery worker -B -l INFO` |
| 线程池并发数 | **8** |
| Broker | redis://default:password@127.0.0.1:6379/0 |
| Beat Scheduler | django_celery_beat.schedulers:DatabaseScheduler |

---

## 核心配置参数

### 分块配置
- Chunk Size: 400
- Chunk Overlap: 20

### 限额配置
| 资源 | 上限 |
|------|------|
| Bot (Agent) | 10 |
| Collection (知识库) | 50 |
| Document (文档) | 1000 |
| 单个文档大小 | 100MB |
| Conversation (对话) | 100 |

### 默认模型配置
- 配置文件: `/workspace/model_configs.json`
- Embedding 批处理: 最大 10 chunks/batch

---

## 主要服务端口 (参考)

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端 (Next.js) | 3000 | 开发服务器 |
| 后端 (FastAPI) | 8000 (默认) | API 服务 |
| PostgreSQL | 5432 | 关系数据库 |
| Redis | 6379 | 缓存/消息队列 |
| Elasticsearch | 9200 | 全文检索 |
| Qdrant | 6333 | 向量检索 |

---

## 重要表结构 (PostgreSQL)

| 表名 | 说明 |
|------|------|
| `user` | 用户信息 |
| `bot` | Agent Bot 配置 |
| `collection` | 知识库 |
| `document` | 文档 (软删除: gmt_deleted) |
| `document_index` | 文档索引状态 (VECTOR/FULLTEXT/GRAPH/SUMMARY/VISION) |
| `chat` | 会话 |
| `message` | 聊天消息 |
| `collection_summary` | 知识库摘要 |
| `evaluation` | 评估任务 |
| `audit_log` | 审计日志 |
| `quota` | 用户配额 |
| `prompt_template` | 提示词模板 |

---

## 文档索引生命周期

文档上传后的索引流程：
1. **PARSE**: 解析文档内容 (docparser)
2. **VECTOR**: 文档分块并向量化存储到 Qdrant
3. **FULLTEXT**: 全文索引存储到 Elasticsearch
4. **GRAPH**: 知识图谱构建 (LightRAG)
5. **SUMMARY**: 文档摘要生成 (LLM Map-Reduce)
6. **VISION**: 图片/图表索引

索引状态流转: `PENDING → CREATING → ACTIVE` (或 `FAILED`)
文档状态: `PENDING → RUNNING → COMPLETE` (或 `FAILED`)

## 用户行为指令

### Git 推送规则
- Date: 2026-05-23
- Context: 用户在开发过程中明确指示
- Instructions:
  - 所有代码改动只在本地 `git commit`，**不要自动 `git push`**。
  - 需要推送到远程仓库时，等用户明确指令后再执行。
  - 远程仓库作为备份用途，防止本地机器故障或开发问题。
