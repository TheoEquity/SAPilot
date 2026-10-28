# ApeRAG 评估系统

一个基于Ragas的RAG系统评估工具，支持对ApeRAG Bot进行全面的性能评测。

## Langfuse 基线评测

当前 Bot 使用 WebSocket 聊天。下方旧版 `run.py` 直接调用的
`/v1/chat/completions` 在当前后端尚未实现；真实 Bot 基线使用新入口
`python -m aperag.evaluation.baseline`，复用原有 Ragas 评分。

从仓库根目录运行（Windows 虚拟环境的 Python 位于 `.venv/Scripts/python`）：

```powershell
python deploy/langfuse/setup.py
docker compose --env-file deploy/langfuse/.env.langfuse -f deploy/langfuse/compose.yaml up -d
python -m venv .venv
.venv/Scripts/python -m pip install -r aperag/evaluation/requirements.txt
```

Langfuse 地址为 <http://localhost:3300>。初始化账号及随机密码保存在
`deploy/langfuse/.env.langfuse`，脚本重复执行不会覆盖密钥。
服务使用独立网络和数据卷，不复用 SAPilot 的 PostgreSQL、Redis 或对象存储。
本配置用于本地评测，没有提供生产高可用或备份方案。

复制 `baseline.example.yaml` 为 `baseline.local.yaml`。在忽略的 `.env.local`
文件中配置 `SAPILOT_SESSION`（当前登录的 session cookie）、`SAPILOT_BOT_ID`、
`EVAL_LLM_BASE_URL`、`EVAL_LLM_API_KEY`、`EVAL_LLM_MODEL`、
`SAPILOT_RUNTIME_REVISION`（实际服务镜像或 commit）和
`SAPILOT_KNOWLEDGE_VERSION`（本次知识库/索引快照标识）。只使用获批模型服务；
不配置评委时不会自动选用公共模型。也可以在配置中使用环境变量提供
`api.username` / `api.password`，由脚本登录获取 cookie。

```powershell
.venv/Scripts/python -m aperag.evaluation.baseline --config aperag/evaluation/baseline.local.yaml --env-file deploy/langfuse/.env.langfuse --env-file aperag/evaluation/.env.local
```

测试集为 JSON 数组，每题具有唯一 `id`、`question`、`answer`、`scenario` 和
`expected_action`（`answer` / `clarify` / `refuse`）。示例见
`datasets/integration-smoke.json`，仅供接入验证。重复问题可以使用不同 ID。
正式测试集需根据原文标注并由业务人员复核。业务资料可放入忽略的
`*.local.json`，无需提交到 Git。

每次运行按文件 SHA-256 建立独立版本的 Langfuse 测试集，记录评分标准版本、
实际服务版本、Bot 配置摘要、知识版本及评委模型。每题使用新会话，保留失败和超时；
明细先写本地，再提交 Langfuse。脚本回读全部用例和评分，超时或缺失会失败，
不会仅凭“上传成功”宣称完成。结果保存在 `aperag/evaluation/reports/`。

评分口径：

- `request_success` 与全量请求失败率独立于回答质量；报错、空回答和超时进入分母。
- `ragas_factual_correctness` 对照参考答案评估事实；评委仍需人工校准。
- `ragas_cited_*` 仅以最终引用文本作上下文，不代表完整模型上下文。无证据、NaN 或
  评委报错显示为不可用并说明原因，不替换为零或跳过整个用例。
- 澄清/拒答用例保留人工复核状态，不自动按错误回答打分。
- 可选 `retrieval_probe` 独立调用知识库检索接口。用例需标注
  `relevant_document_ids`；可逐题指定 `collection_id`。
  `probe_document_recall_at_1/3/5` 和 `probe_document_mrr_at_5` 按文档去重后计算，
  **不是 Agent 实际检索成绩**。最终引用经过筛选，不能反推真实排序。
- 当前不计算总任务通过率或自动设置验收阈值；整体任务通过及严重违规仍需按明确的
  逐题条件复核。本入口也不替代摄取结构、图文关系、权限隔离和多轮专项测试。

离线部署需预先导入固定版本镜像、Python 包和模型资源。Ragas 遥测在此入口关闭；
Langfuse 自部署不代表配置的模型也自动变为离线模型。

## 🚀 快速开始

### 1. 配置评估环境

**复制并编辑配置文件：**

```bash
# 复制示例配置文件
cp aperag/evaluation/config.example.yaml aperag/evaluation/config.yaml
```

**必须修改的配置项：**

1. **API密钥配置** - 设置环境变量或直接在配置文件中修改：
   ```yaml
   api:
     base_url: "http://localhost:8000/api/v1"
     api_token: "${APERAG_API_KEY}"  # 替换为你的 ApeRAG API Key

   llm_for_eval:
     api_key: "${OPENROUTER_API_KEY}"  # 替换为你的 LLM API Key

   embeddings_for_eval:
     api_key: "${SILICONFLOW_API_KEY}"  # 替换为你的 Embedding API Key
   ```

2. **Bot ID配置** - 替换为你创建的Bot ID：
   ```yaml
   evaluations:
     - bot_id: "your-bot-id-here"  # 🔴 必须替换为实际的Bot ID
   ```

3. **样本数量配置** - 根据需要调整测试样本数量：
   ```yaml
   evaluations:
     - max_samples: 10  # 🔴 建议先用小数量测试，如3-10个样本
   ```

### 2. 创建Bot和Collection

⚠️ **重要前置条件：** 运行评估前，你需要先在ApeRAG系统中创建：

1. **创建Collection（知识库）**：
   - 在ApeRAG Web界面中创建Collection
   - 上传相关文档并完成索引

2. **创建Bot**：
   - 基于上述Collection创建Bot
   - 配置Bot的对话参数
   - 记录Bot ID并更新到配置文件中

### 3. 准备评估数据集

确保你的数据集是CSV格式，包含 `question` 和 `answer` 两列：

```csv
question,answer
"什么是检索增强生成？","检索增强生成（RAG）是一种结合信息检索和文本生成的AI技术..."
"如何优化RAG系统性能？","可以通过改进检索策略、优化chunk size、使用更好的embedding模型等方式..."
```

### 4. 运行评估

使用Make命令（推荐）：

```bash
# 运行评估
make evaluate
```

或者直接使用Python命令：

```bash
# 使用默认配置
python -m aperag.evaluation.run

# 指定配置文件
python -m aperag.evaluation.run --config aperag/evaluation/config.yaml
```

## 📊 评估指标说明

系统使用Ragas框架的5个核心指标：

| 指标 | 说明 | 范围 | 依赖 |
|------|------|------|------|
| **Faithfulness** | 答案对检索内容的忠实度 | 0-1 | LLM |
| **Answer Relevancy** | 答案与问题的相关性 | 0-1 | LLM + Embedding |
| **Context Precision** | 检索上下文的精确度 | 0-1 | LLM |
| **Context Recall** | 检索上下文的召回率 | 0-1 | LLM |
| **Answer Correctness** | 答案的整体正确性 | 0-1 | LLM |

## 📁 输出报告

评估完成后会生成多种格式的报告：

```
evaluation/reports/
├── evaluation_summary_YYYYMMDD_HHMMSS.json    # 详细统计数据
├── evaluation_report_YYYYMMDD_HHMMSS.md       # 可读性报告
└── evaluation_report_YYYYMMDD_HHMMSS.csv      # 原始评估数据
```

## ⚙️ 高级配置

### 性能调优

在 `config.yaml` 中调整以下参数：

```yaml
advanced:
  request_timeout: 30    # API超时时间（秒）
  request_delay: 3       # 请求间延迟（秒）
  batch_size: 3          # 批处理大小
  save_intermediate: true # 保存中间结果
```

### 环境变量

设置环境变量以避免在配置文件中硬编码密钥：

```bash
export APERAG_API_KEY="your-aperag-api-key"
export OPENROUTER_API_KEY="your-openrouter-api-key"
export SILICONFLOW_API_KEY="your-siliconflow-api-key"
```
