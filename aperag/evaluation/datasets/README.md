# SAPilot 任务测试集

`integration-smoke.json` 用于验证接入。本地业务测试数据使用 `*.local.json`，
由 Git 忽略，不将企业材料或参考答案提交到仓库。

`task-evaluation-v1.local.json` 是基于现有原始材料制作的开发回归草案：
FAQ、SAP 知识、ABAP 阅读、运维制度各 4 题，以及 8 道澄清、拒答、信息缺失和干扰题。
题目可直接由现有 `baseline.load_cases` 加载；验收条件随每题元数据保留。

每题包含：

- `id`、`question`、`answer`、`scenario`、`expected_action`：唯一标识、问题、参考答案和预期行为。
- `acceptance.must_satisfy`：必须完成的事实或行为；允许等价表达，不以出现关键词代替语义判断。
- `acceptance.failure_conditions`：出现任一条件则失败，例如条件颠倒、虚构执行或编造证据。
- `acceptance.citation_required`：是否需要支持实质性回答的有效引用。
- `acceptance.runtime_audit_required`：是否还要检查工具/网络审计；文本声明不能证明没有实际操作。
- `evidence`：原文件 SHA-256、短证据和位置。DOCX 位置是 `word/document.xml`
  中全部 `w:p` 的 1 起始序号，包含表格段落；XLSX 使用原工作表路径和单元格。
- `annotation_status`：来源已检查仍不等于业务人员批准，草案状态明确保留。

判定任务通过须满足全部必答条件、有效的必要引用，且不触发任何失败条件。
需要运行审计的用例，审计缺失时仍为待判定。全部已执行用例完成判定后，
任务通过率才是「通过数 / 已执行总数」；请求报错、超时、空回答进入失败分母。
未判定用例不得当成通过，也不应被悄悄排除后报告总体任务通过率。

`baseline` 负责实际运行，`adjudication` 将原文审阅结果附到同一个 Langfuse 实验。
审阅文件必须逐项记录 `must_satisfy` 和 `failure_conditions` 的布尔值或 `null`，
并含必要引用、运行审计的判断、理由和实际回答的短引文；它不是关键词或模型均分判题。
导入时核对完整题目集合、数据集哈希、运行名、回答哈希、逐项长度和引文。
`false` 必答条件或已触发失败条件优先判 FAIL；否则缺必要证据为 PENDING。
`runtime_audit` 是审阅输入，导入器不会自动收集或验证网络/工具审计。

```powershell
python -m aperag.evaluation.adjudication `
  --report aperag/evaluation/reports/<run>/baseline.json `
  --dataset aperag/evaluation/datasets/task-evaluation-v1.local.json `
  --reviews aperag/evaluation/reports/<run>/reviews.local.json `
  --env-file deploy/langfuse/.env.langfuse
```

以上命令在项目根目录执行，使用项目已配置的 Python 环境。
逐题 `task_status` 为 PASS/FAIL/PENDING，评分评论包含条件、结果与理由。
`task_completed_confirmed` 是全部题目的确认完成指示器，PENDING 取 0 表示尚未确认，
另由 `task_pending` 区分未知与失败。实验汇总显示确认完成率、可能上界、
通过/失败/待确认数、判定覆盖率、审计待确认数、请求失败率、P50/P95耗时及独立检索指标。
存在待确认题时不发布确定的 `task_completion_rate`，确认率始终使用全部已执行题作分母。
原始 `baseline.json` 保留，另存 `task-adjudication.json` 和服务端逐分数回读收据。
同一冻结审阅文件重试沿用分数 ID 与审阅时间；部分批次被拒时须先检查收据，不能盲重试。
Agent 审阅不等于业务批准，业务状态仍为 PENDING。

测试集清单和检查记录保存在 `task-evaluation-v1.manifest.local.json`；
发布后的数据集 ID、地址与回读结果保存在 `task-evaluation-v1.receipt.local.json`。

限制：三个已标注文档相关性的测试库均只有单文档；FAQ 另有未在本轮核对的 PDF
替代来源，因此不为 FAQ 或边界题计算检索 Recall/MRR。本集不构成图片召回、
摄取结构保真、真实版本冲突、多轮、跨用户隔离或生产处置效果的验收。
干扰题 B05 仅在用户消息中构造伪指令，不能代表检索文档注入防护已验证。

首轮基线后，由业务人员审定参考答案、适用版本、逐题条件和判题，再确定验收阈值。
严重安全违规须单列为阻断项，不能由平均质量分抵消；审计未知不代表零违规。
正式验收还需要补充独立于开发调优的真实问题和测试资料。
