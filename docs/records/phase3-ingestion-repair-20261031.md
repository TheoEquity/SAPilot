# 七份原始材料摄取修复与复验

日期：2026-10-31。目标：接通 PDF 截图与文字分块，补旧 DOC 转换依赖，通过真实 API 重新摄取原始七份材料，并清理无用文件。

**摄取修复及复验已通过；文件清理尚未执行，删除命令被自动审批拦截。** 本记录不代表整套难题问答、Recall 或八成质量目标验收通过。

## 修改

- 新增 `aperag/docparser/pdf_parser.py`，由现有本地 PDF 入口调用。保留原 PDF 文字层，生成 180 DPI 页图，用本地 Tesseract 提取补充文字；页图链接、`asset_id`、页码及 `pdf_source_map` 同时进入预览和分块。OCR 内容标明可能存在误识，原文字层保留。
- 分块时隔离 PDF 页上下文，长页仍按现有大小拆分，各分块保留同一页的图片定位。已有页图不再重复生成或被低分辨率版本覆盖。
- Dockerfile 增加 LibreOffice Writer、CJK 字体、Tesseract 及简体中文语言包。API/worker 使用在既有运行镜像上补齐同组系统依赖的本地镜像 `sapilot-api:ingestion-repair-20261031`；保留原环境、挂载、网络和端口，没有全量重装应用 Python 依赖。
- 修复 DOC 转换时的扩展名前导点、输入存在性及转换输出校验；转换使用独立临时 LibreOffice profile 和超时。旧 DOC 转换后优先复用现有 FAQ 表格解析，保留完整 FAQ 和图片归属。
- 开发环境说明补充必要系统依赖。未修改高层架构、问答路由、默认模型或原来的五份样本集合。

PDF 的原问题是页图虽被生成和存储，却没有进入关联的文字分块；旧 DOC 原问题是 worker 没有 `soffice`，补依赖后还需修正既有转换文件名处理。

## 实际复验

本地生产解析器先处理七份原件，再通过真实上传 API 新建独立验收集合并摄取原始文件；DOC 测试上传的仍是原 `.doc`，没有用本地预转换的 DOCX 代替。

验收集合：`验收-原始七份文档-20261031`，ID `col26291ce6ad899dcc`。集合保留，供后续分层测试使用，未自动挂到现有 Bot。重复格式是本次验收输入，不作为独立事实佐证，也不应在业务检索中重复计分。

| 原件 | 文档状态 | 向量/全文索引 | 实际分块 | 可下载图片资源 |
| --- | --- | --- | --- | --- |
| ABAP代码29.docx | COMPLETE | ACTIVE / ACTIVE | 4 | 0（原件无图片） |
| SAP人财物运维常见问题-Max.pdf | COMPLETE | ACTIVE / ACTIVE | 201 | 83 张页图 |
| SAP人财物运维常见问题-Min.pdf | COMPLETE | ACTIVE / ACTIVE | 52 | 20 张页图 |
| SAP人财物运维常见问题解决-test01.doc | COMPLETE | ACTIVE / ACTIVE | 19 | 39 |
| SAP人财物运维常见问题解决-test02-docx.docx | COMPLETE | ACTIVE / ACTIVE | 19 | 39 |
| SAP开发自测规范_V1.0.docx | COMPLETE | ACTIVE / ACTIVE | 18 | 0（原件无图片） |
| 应用系统性能缓慢问题自检表_v1.xlsx | COMPLETE | ACTIVE / ACTIVE | 4 | 0（主表为文字单元格） |

检查结果：

- 7 份原件的 SHA-256 与原始清单一致，没有改写原件。
- **181 个图片资源**下载均返回 200、内容非空，并能由对应分块的图片链接或元数据定位。PDF 的原嵌入截图由完整页图承载，不把 103 张页图说成 103 个原始独立截图。
- FAQ DOCX 的 **39 个媒体字节哈希**与原件全部匹配；19 个 FAQ 的 **41 次图片引用**顺序及表格归属一致。
- DOC/DOCX 的 **19 张 FAQ 表、106 个非空表内段落**分别在对应 FAQ 分块中按原顺序保留；原难题引用的 DOC 正文亦保留。
- 现有题集的 **232 条文字引文记录**在新预览中均能匹配：FAQ 33、Max 40、ABAP/规范 159（含重复引用）。没有将 OCR 识别文字冒充原件逐字引文。
- XLSX 的 **19 条业务行、57 个业务数据单元格**均保留。原表标题/表头另有 4 个非空单元格，不混入 57 的业务数据口径。
- 4 条真实检索请求均为 200；预算相关结果携带 `page_41.png` 的图片定位，包含截图识别出的补充内容。仅证明检索路径及图文定位可用，不作为 Recall/MRR 或难题回答通过率。
- 53 项相关测试通过，包含新回归及原有分块/Markdown 测试；Ruff 与本次差异空白检查通过。修复前的回归明确复现转换格式错误、缺文件仍启动转换、成功无产物未报错，以及缺少 PDF 图文解析路径。

实际 worker 中确认 `LibreOffice 25.2.3.2`、Tesseract 的 `chi_sim` 和 `eng` 语言数据可用。Docker 起初有旧 socket 启动错误，用户恢复引擎后才进行上述真实 API 验收；没有将此前本地解析结果当作完整应用验收。

## 证据位置

私有目录：项目旁 `../SAPilot-data/evaluations/phase3-ingestion-repair/2026-10-31/`。

| 文件 | 内容 |
| --- | --- |
| `api-ingestion-results.json` | 七份文档、索引、图片下载与分块关联的实际结果 |
| `<document-id>-preview.json` | 新摄取预览、文字及元数据 |
| `content-verification.json` | 原文引文、表格顺序、单元格、图片哈希及 FAQ 归属比对 |
| `post-repair-search-checks.json` | 4 条检索路径抽查原始结果 |
| `local-parser-results.json`、`local-*/` | 本地真实解析结果及派生文件，不代替 API 层验证 |
| `worker-run.log` | 实际 worker 任务结果 |
| `cleanup-manifest.json`、`cleanup.ps1` | 未执行的清理清单及默认预览脚本 |

容器原配置及本地镜像构建材料留在 `../SAPilot-data/runtime/phase3-ingestion-repair/2026-10-31/`，含私有配置，不提交 Git。

## 清理状态

已核对并准备清理，但**删除未执行**：

- 178 个重复的本地 PNG/媒体验证文件，合计 40,058,111 字节。原件、真实集合资源以及 3 张代表性页图保留。
- 本轮临时 WSL Python 环境 `.run/ingestion-tools-wsl/`，预检约 309,576,268 字节。
- 两份创建容器时生成的临时 `.env` 文件；原私有配置快照保留，供必要回退使用。

自动审批拒绝了执行上述删除的命令，仅返回 `blocked by policy`，没有更具体原因。未改用其他删除工具绕过。用户如需手工完成，可在项目根目录用 PowerShell 运行：

```powershell
# 默认仅检查和预览
& ../SAPilot-data/evaluations/phase3-ingestion-repair/2026-10-31/cleanup.ps1 -ProjectRoot (Get-Location).Path

# 按清单执行：先校验文件哈希和目标目录，保留原件、题集及验收证据
& ../SAPilot-data/evaluations/phase3-ingestion-repair/2026-10-31/cleanup.ps1 -ProjectRoot (Get-Location).Path -Execute
```

## 限制与下一步

此次验证证明解析、文字/表格保留、图片保存与定位、向量及全文索引链路正常。**OCR 不等于逐字准确**：本地 Max 第 42 页抽查中，小字段“预算类别”和数值 `9C` 未被准确识别，完整原页图仍保留并可下载。小字、按钮、金额与日期应核对原图，不能拿 OCR 补全不确定事实。PDF 目前是页级关联，没有宣称自动完成每个截图到某一 FAQ 的精确语义归属。

既有 FAQ 表外标题与 XLSX 隐藏表/`NaN` 展示未在本次范围内调整。整套 26 题答案评测、跨页检索完整性和响应指标仍在下一阶段分别验证；后续无需再把旧 DOC 转换失败或 PDF 无关联页图当成当前缺口。
