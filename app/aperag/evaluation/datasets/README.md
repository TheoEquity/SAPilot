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
$env:PYTHONPATH = "app"
python -m aperag.evaluation.adjudication `
  --report app/aperag/evaluation/reports/<run>/baseline.json `
  --dataset app/aperag/evaluation/datasets/task-evaluation-v1.local.json `
  --reviews app/aperag/evaluation/reports/<run>/reviews.local.json `
  --env-file runtime/private/langfuse.env
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

## 已知问题：指定资料查询被路由至不含目标文档的库

状态：待修复；本条仅记录诊断，尚未实施修复或完成修复后复测。
记录日期：2026-10-27（America/New_York）。

关联运行：`baseline-20261028T010300480241Z`，
[Langfuse 实验](http://localhost:3300/project/sapilot-baseline/experiments/results?baseline=0ee3f1ba476fd879&pageIndex=0&pageSize=50)。
原始证据为本地 `../reports/baseline-20261028T010300480241Z/baseline.json`、
各题 `case-*.json`、`reviews.local.json` 及当次 `aperag-api` 容器日志。

已验证事实：

- 本轮路由器采用 LLM 分类，候选说明提供业务类别，但没有提供“性能自检表位于哪个库”的资料归属信息。
- 运行日志记录 K01、K02 选择 `sap_faq`，仅注入 FAQ 库；K03、K04 选择 `ops_policy`，仅注入制度库。
  K01、K02、K04 的实际检索请求和最终引用也指向这些库。所需性能自检表位于 SAP 知识库，
  当前 `sap_knowledge` 才绑定该库；选中其他技能后，证据不足的补检仍在原绑定范围内进行。
- 日志中的分类时间（UTC，2026-10-28）分别为 K01 01:09:05、K02 01:08:38、
  K03 01:07:48、K04 01:07:19。诊断时核对的 Bot 配置响应哈希与本轮报告快照哈希一致。
- 目标文档已经入库，四题独立检索探针均找到了目标文档。但探针从题目标签直接取得正确的
  `collection_id`，绕过意图路由；本轮已标注 12 题的文档级 Recall/MRR 为 100%，
  不能据此认定端到端路由或召回正确。
- K03 还发生 `ConnectionClosedError`，不能把该题未完成全部归因于错库。

推断与未知：故障描述可能使分类偏向 FAQ，“自检表/检查项”措辞可能使分类偏向制度。
日志未保留分类模型的选择理由，因此这些措辞是否为实际触发原因尚未证实。
确定的是“所选业务类别与任务所需资料范围不匹配”，而非模型内部分类动机。

后续建议（未实施）：明确“按指定资料提取内容”与“诊断实际故障/查询制度要求”的边界，
向路由候选提供相关资料范围。复测需核对实际 Skill、实际请求的 collection、目标文档引用
及逐题答案，保留正常 FAQ 和制度查询作为边界对照；不能只运行已指定正确库的独立探针。
