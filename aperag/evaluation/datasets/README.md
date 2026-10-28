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

当前评测入口不会自动据 `acceptance` 判题；本轮制作测试集与验收条件，
不新增模型评委或发布任务完成率。Langfuse 中的参考答案和逐题元数据可供审阅，
不能将“已导入”升级为“已执行”“已审定”或“已通过”。

测试集清单和检查记录保存在 `task-evaluation-v1.manifest.local.json`；
发布后的数据集 ID、地址与回读结果保存在 `task-evaluation-v1.receipt.local.json`。

限制：三个已标注文档相关性的测试库均只有单文档；FAQ 另有未在本轮核对的 PDF
替代来源，因此不为 FAQ 或边界题计算检索 Recall/MRR。本集不构成图片召回、
摄取结构保真、真实版本冲突、多轮、跨用户隔离或生产处置效果的验收。
干扰题 B05 仅在用户消息中构造伪指令，不能代表检索文档注入防护已验证。

下一步由业务人员审定参考答案、适用版本和逐题条件，再使用本集试跑、复核判题，
随后确定验收阈值。正式验收还需要补充独立于开发调优的真实问题和测试资料。
