# 项目目录重组与验证（2026-11-02）

用户批准将业务代码、维护工具、业务数据、运行产物和长期文档集中到同一个项目总目录，要求重组后启动项目验证，再将结构写入根 README。

## 实际布局

- `app/`：原后端、前端、任务配置、测试、脚本、模型配置、依赖和应用构建/部署文件；包名 `aperag` 不变，原有未提交业务改动保留。
- `maintenance/`：Swagger/ReDoc 入口说明及 Langfuse 配置、凭据生成入口。Swagger 仍由 FastAPI 提供，不另复制后端。
- `data/`：原始资料、派生材料、权重入口和可复用题集。准备图片题集的整组材料保留在 `data/evaluation-sets/`。
- `runtime/`：日志、历史评测、私有配置、历史回放输入、临时工具和移动/恢复依据。原 `.run/` 迁至 `runtime/work/`。
- `docs/specs/`、`docs/prompts/`、`docs/design/`、`docs/records/`：规约、建议模板、设计和结论记录。设计保持语言与 current/planned/historical 等状态分类。

52 个入口移动映射、原文件哈希和移动前未提交补丁保存在被忽略的 `runtime/layout/2026-11-02/`。旧兄弟目录 `SAPilot-data/` 已清空并移除，未建立旧路径别名。原 Langfuse Git 工作树保留，维护配置已在本项目内可用。

## 路径与维护调整

- 同步应用日志、PID、OpenAPI 导出及生成配置的路径，更新 Git hooks 的仓库发现方式；应用镜像构建上下文分别为 `app/` 和 `app/web/`。
- 更新文档链接和当前规约；源文档同步工具支持新的设计目录，保持网站路由。未执行覆盖真实网站文档的批量同步。
- `data/`、`runtime/` 和实际环境文件均忽略，Docker 上下文另排除私有内容及本机依赖。工具管理的 `.venv`、`node_modules`、`.next` 和 pytest 默认缓存允许留在 `app/` 的忽略目录。
- 数据题集清单和准备脚本的当前路径随布局调整；冻结的历史报告、源码和运行脚本保留原始路径语义，追溯使用移动映射，不将历史脚本升级为当前维护入口。
- 链接更新一度误触 34 份外部 Markdown 原件，已从清单锁定提交下载并恢复到原 SHA256；两份误触的历史构建文档也按固定 Git 版本及原哈希恢复。最终原始资料完整性检查通过。

## 实际检查

| 检查 | 结果 |
| --- | --- |
| 移动前源文件清单 | 1,987 条，无缺失；其中 1,890 条字节相同，其余为必要路径、说明及配置更新 |
| 资料与图片 | 355 个来源文件、70 条图片输入逐项 SHA256 一致 |
| Python 契约测试 | 从 `app/` 使用默认 pytest 缓存配置：180 passed，1 条 Starlette 弃用警告 |
| API 导出相关契约 | 另检查 23 项通过，与上述集合有重叠；有既有 pytest 异步配置警告 |
| 前端日志与 Mock | 5 + 2 项通过 |
| TypeScript | `tsc --noEmit --incremental false` 通过 |
| 脚本与 Compose | Bash/Node/Python 语法、应用与 Langfuse 配置、构建上下文和日志挂载检查通过 |
| 文档同步工具 | 在临时测试目录验证 13 个真实源文件、分类、跨语言图片及编码/换行映射；未覆盖真实网站副本 |
| 页面与登录 | 前端 3000 可访问，既有账号真实登录后 Bot 列表及聊天页面正常 |
| 实际问答 | 独立会话执行向量/全文检索，模型返回带证据边界的回答及引用；服务端记录 `chat.message.completed`，持久化回读 200 |
| 摄取与检索 | 独立临时知识库上传文本，Worker 处理为 COMPLETE，VECTOR/FULLTEXT 均 ACTIVE，搜索命中验证标记 |
| 文件与任务 | 下载内容逐字节一致；Celery inspect 返回 pong |
| 维护工具 | API health、Swagger、Langfuse health 均 200；实际聊天在 Langfuse v4 的 events_core 中收到 285 个 SPAN/TOOL/GENERATION 事件 |
| 收尾 | 临时知识库删除后回读 404；临时会话删除后回读 404；旧 API/worker 容器已回收，沿用原数据库及对象存储卷 |

API 与 worker 重新挂载 `app/ -> /app`、`runtime/logs/ -> /logs`，对象存储继续使用原 `sapilot_aperag-shared-data` 卷。前端从新 `app/web/` 启动；Langfuse 沿用 `sapilot-langfuse` 项目名及数据卷。

## 限制与未验项

- 现有默认标题模型未配置，聊天完成后的可选标题接口仍可能返回 400；页面没有错误层。该限制在重组前已存在，本轮未更换模型或扩大为配置修复。
- 历史 Node 回放 harness 有 3 项与旧基线 AST 或 logger 替身相关的失败，不是目录缺失；现行 Python 契约、前端检查和实际业务冒烟结果如上，不能据此声称全部历史回放通过。
- Langfuse v4 events_only 模式的旧 traces 查询接口返回 404，收数以实际 events_core 记录核实，未据旧接口状态推断监控失败。
- 本轮复用既有运行镜像和工具依赖，没有重建全部镜像或重装全部依赖，也没有做完整 SAP 内容质量、压力或生产部署验收。
- 重组验收阶段未提交或推送，既有工作树与未提交内容保留；根 README 在实际流程验证后写入用户批准的目录结构和当前访问入口。后续用户已授权将本轮版本发布到当前分支 `codex/architecture-foundation-20261029`，发布结果以 Git 提交和远端分支核对为准，原有独立 HTML 草稿不纳入该提交。
