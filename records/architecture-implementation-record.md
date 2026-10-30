# SAPilot 架构整理实施记录

更新日期：2026 年 10 月 29 日。用户要求的五批本地架构整理已逐批实施、由另一个独立强子代理审核并集成本地 main。本文区分源码改动、检查通过与完整业务验收；当时未推送，后续分支发布与清理进展见末节，未部署。

## 分批状态

| 批次 | 状态 | 本地候选与审核 |
| --- | --- | --- |
| 1 Bot / 编排保存契约 | 已实施、独立审核通过、已集成本地 main | `1722d2cb2602db9ac958a3857a9c4cb33ab7de44`；无阻断的 Critical/Important 问题 |
| 2 意图模型参数 | 已实施、独立审核通过、已集成本地 main | `7b534cbbaa1bdea63dfb7525cfa65b6e837832ac`；无新增 Critical/Important/Minor 问题 |
| 3 前端 Skill 试点 | 已实施、独立审核通过、已集成本地 main | `d40a75c8015c72aed27ee1697ce76b3ec2036209`；未发现回归，独立快照生产构建通过，浏览器仍待验 |
| 4 后端意图路由试点 | 已实施、独立审核通过、已集成本地 main | `0b86183eb023ee0094e0f370905cd5e73b4a2bff`；无 Critical/Important/Minor 问题 |
| 5 聊天与附件整理 | 已实施、独立审核通过、已集成本地 main | `70eacec14da26842e0017995ebb4b5a8cb272fd0`；无 Critical/Important/Minor 问题，真实生产构建通过 |

推进范围见[计划讨论稿](architecture-implementation-plan-draft.md)。本记录描述实施事实；计划、实现完成、独立审核通过、集成、运行验收分别记录。

## 第 1 批结果

补齐 Bot/编排已有字段的源 YAML，实际隔离生成并采用相关的 20 个 Python 类和 20 份 TypeScript 模型。旧手写编排业务类型改为引用生成类型；画布仍保留必要的 UI 类型收窄。

Bot 设置、意图和 Skill 普通/快捷保存保留未编辑的已有高级字段；画布保存保留 viewport 与 edge.type。普通保存与快捷保存原有校验、兜底保护和去重差异没有被统一。未增加阈值、启停、IO 或工具策略的执行能力。

独立审核重新 bundle、在独立目录重新生成，并核对采用产物、原 Python 字段注解、必填性及业务默认值。16 项实际保存回调/真实 Zod/Pydantic 序列化回归通过；生成类型编译通过。相关 ESLint 无新增错误或警告。

隔离候选的全量 tsc 与基线同为 search-test.tsx 的 6 个既有错误；快进整合回原工作区、保留该页面既有修改后，协调者重跑 `node web/node_modules/typescript/bin/tsc --noEmit --incremental false -p web/tsconfig.json`，退出码为 0。已用哈希检查本批范围外既有文件保持不变。

上述 16 项测试使用 hooks、HTTP 传输与数据库持久化替身，验证局部开发契约；随后补充的真实 HTTP/数据库结果见下节。浏览器生命周期与画布交互、模型调用和 SAP 效果尚未验收。Bot 欢迎词/Prompt 的空串仍有既有默认回填行为，不能概括为所有空值都会原样保留。

全量生成仍会影响范围外类型并遗漏现有手工扩展，因此本批没有全量覆盖产物。已采用范围、生成命令、工具版本和局限见[契约测试说明](../tests/contract/README.md)。`strict-nullable` 是全局生成选项，后续生成仍须比较范围外差异，不能由本批通过推定整个生成链已对齐。

## 第 2 批结果

意图分类创建独立的消息与 completion 副本，使用配置的意图 provider/model 查询 Provider、Key、base_url 并构造分类会话；每次请求的 maxTokens 使用 intent_router.llm.max_tokens，替换原固定 512。Skill 继续收到原合并消息，规则、指定 Skill、候选、Prompt、兜底与队列收尾保持。本批没有 schema 改动，无需重新生成。

独立审核执行本批 20 项及前批 16 项，共 36 项通过；将当前测试用于基线服务源码时得到 11 失败、9 通过，复现旧 provider/default_model/token 错配。锁定 SDK wheel 的哈希与实际源码参数映射已独立核对，但未执行真实 SDK/HTTP。详细范围与可复跑方式见[意图参数验证说明](../tests/contract/intent-model-parameters.md)。

实际源码方法测试替换了外部 DB、LLM/MCP 初始化等边界。同 provider 的既有会话不会刷新旧 instruction/Key/base_url；全局环境写入、缺 Provider/Key 的异常构造问题仍属已知范围外限制，不应把本批通过概括为模型联通、全部错误处理或并发隔离已验收。

## 第 3 批结果

Skill 编辑器同目录拆为配置构造、编辑 Hook、表单分区与薄页面四个模块。没有引入外部组件、状态库或新 API；普通与快捷保存仍保留原有校验、兜底冲突、去重和反馈差异。重复配置构造收敛到同一 helper，未保留第二份旧实现。

独立审核核对 25 条初始化语句的运行时 AST、7 个表单 JSX 块以及原有 34 条断言均保持，新增 18 条断言；6 份提交载荷除 `updated_at` 外前后一致。独立联合回归 36 项通过。集成回原工作区后，协调者再次运行全量 TypeScript 检查，退出码 0。

平台隔离工作区直接执行 Next 生产构建失败：目录扫描 `EPERM` 后出现 Flight 插件错误；原编辑器回放构建日志相同。协调者随后在仓库外的数据目录复制原工作区 610 个已跟踪前端文件（包含保留的既有页面修正），只读复用依赖，直接执行 `node node_modules/next/dist/bin/next build`，完整编译、类型检查、页面生成和追踪退出码为 0，没有跳过检查或修改构建配置。快照哈希与日志保存在 `../SAPilot-data/runtime/architecture-execution-20261029/frontend-build/`。模拟 hooks 不证明真实浏览器生命周期或主题显示；这些运行检查仍待补。

## 第 4 批结果

新增 [intent_router.py](../aperag/agent/intent_router.py)，迁入强制 Skill、首条规则、模型分类与非法输出兜底，删除服务旧内联实现和旧规则方法；AgentChatService 通过绑定的原会话获取方法单次委派。校验、FAQ 旁路、最近四条历史、上下文缓冲、Skill 执行与队列 finally 留在服务，未继续拆分其他职责。

独立审核对固定源码导出重新比较 AST，确认完整算法、精确 Prompt、候选过滤、Provider/model/maxTokens、消息复制、服务其他语句和原测试断言保持。16 项新增边界在提取前后都通过；合并原回归共 52 项独立复跑通过。新模块与测试 Ruff 通过，服务原有 lint 诊断 5→4，无新增；没有 schema 变化，无需重新生成。

审核员另用自有无网络容器真实导入新模块与 Agent 服务，确认绑定新函数，使用 mcp-agent 0.2.6 与 Pydantic 2.11.7，退出码 0；该容器已自动删除。未执行真实模型、HTTP/WS 聊天、Skill/MCP、并发或 SAP 效果。完整边界见[本批验证说明](../tests/contract/intent-router-extraction.md)。

## 第 5 批结果

聊天连接、消息状态、发送/FAQ/反馈/取消和滚动迁入 `use-chat-messages.ts`；附件选择、上传、预览、删除和粘贴迁入 `use-chat-attachments.ts`，原组件保留 UI 与输入发送职责。原 `Attachment` 导出继续兼容。FileUpload 回调保持每次 render 的新身份，以保持其 store 依赖行为；发送回调显式加入从 Hook 返回的原生稳定 setter 依赖，避免新增 lint 警告。

同一真实 TS harness 执行固定基线与拆分后代码，6 组场景及 1 组 AST 对照通过；原有 52 项 Python 回归通过。独立审核员在另一个源码导出目录重新执行两组检查，分别 7/7、52/52 通过，相关 ESLint 0 错误、1 条既有未用状态函数警告。为匹配原 ESLint 配置，独立 lint 使用导出源码和原虚拟 filePath；只适配依赖解析与配置定位，没有改规则或业务源码。此前环境适配失败日志和最终通过结果分开保留。

该历史对照工具依赖 Git 中的固定基线提交和已安装依赖，不是脱离源码历史的浏览器测试。协调者导出固定候选的 4 个前端文件到此前数据目录构建快照，4 个文件仅归一化 CRLF/LF 后与固定 Git blob 相同，其他 608 个文件原始哈希保持；完整 Next build 退出码为 0。审核员读取了这些构建与源码记录，没有再次独立构建。纯提交隔离区仍有原 search-test 六项错误，不因原工作区带既有修正的构建通过而升级为纯提交全量检查已通过。

保留的既有边界：error 片段不会自动结束 loading；取消只是断开再重连；history 仅初始化状态；附件状态检查没有挂接轮询，非图片上传后可停在 uploaded 并阻挡发送；预览 URL 的已有生命周期问题、失败请求与迟到响应行为没有扩修。状态检查函数在 harness 中手动执行，不表示线上已启用轮询。详情见[本批验证说明](../tests/contract/chat-attachments-extraction.md)。

## Docker 保存回读补验

用户开启 Docker 后，另一个验证子代理在独立 internal 网络、独立 PostgreSQL 中使用真实 Bot FastAPI 路由、APIKey 鉴权、BotService、Pydantic、ORM 和 Uvicorn TCP HTTP，未发布主机端口、未操作现有数据库或加载真实 `.env`。后端固定 `7b534cb`，并实际核对第 3 批没有改变该后端链路。

一份完整合成配置与第 3 批独立源快照捕获的 6 种原始前端提交对象，分别执行 POST→GET→PUT→GET，再直接从 PostgreSQL 读取 config 比对已接受字段；共 28 次成功业务请求，未鉴权请求实际返回 401。Bot、意图、Skill 普通/快捷保存及两种显式清空均通过；第二个 Skill、已有高级字段、意图与 Skill 画布 viewport/edge.type 保留。两个清空载荷的 tools/collections 空数组及 description/prompt 空串实际落库。

证据保存在仓库外 `../SAPilot-data/runtime/architecture-execution-20261029/docker-contract/`，含固定源码、输入、原始请求响应、脚本、镜像 ID、SQLAlchemy 独立读取配置和资源回收结果。协调者检查了脚本、结果及当前 Docker 资源查询，确认本轮自建容器与网络剩余均为 0。

本次使用最小真实 ORM 建表，未验迁移；顶层旧 flow 的节点和边为空，意图/Skill 画布的节点和边非空。前端载荷由实际源码测试捕获，未通过浏览器操作产生；未启动完整应用生命周期、MCP、worker 或模型调用，不代表完整业务端到端验收通过。

## 集成总验

本地 main 为 `70eacec14da26842e0017995ebb4b5a8cb272fd0`。协调者在原工作区保留既有改动后，重新执行 52 项 Python 回归、7 项 Node 对照及全量 `tsc --noEmit --incremental false`，均退出 0；固定候选的完整 Next 生产构建也退出 0。原工作区的既有 search-test/package/lock 修正没有并入本轮候选提交，纯提交隔离区仍有前述 6 项既有类型错误。检查通过不代替真实浏览器、WebSocket/模型聊天、并发或 SAP 效果验收。

五批集成完成时，代码已按五个本地提交集成，文档更新当时保留在原工作区待提交，没有把旧工作一并打包提交。后续用户已授权发布分支，范围见末节。旧原文保留；实施前盘点作为基线，当前说明与目录增加了最新模块和实施状态入口。

最终与实施前 1,284 个已有文件哈希对照，本轮代码与文档范围外无新增修改或删除；本轮文档的本地链接无失效，五批提交的差异空白检查退出 0。协调时曾临时加入 Git common exclude 的两条规则已移除，原共享忽略文件未为此新增规则。

最终运行日志、固定源码快照、前后观察、独立审核及哈希清单位于仓库外 `../SAPilot-data/runtime/architecture-execution-20261029/`。其中 `implementation-evidence/` 保留五批 341 个证据文件约 2.3 MB，收集时排除了临时 venv、jar、wheel 和缓存，不把工具包当成需提交的交付物。

## 资源与回收（集成完成时的记录）

- 本轮只使用一个平台管理的隔离工作区；原工作区和其他既有工作树保留。已调用平台归档接口，附件状态确认为 `archived_worktree`，但随后磁盘目录及 Git 工作树登记仍存在，包含共用临时 venv、jar、缓存和依赖联接；尚不能认定物理回收完成。平台入口 `%USERPROFILE%/.codex/worktrees/` 是指向实际工作树目录的已有联接；归档状态与物理回收不同步的原因未知，未据此删除或改动其他工作树。
- 第 1 批审核员的独立复跑目录 `%TEMP%/sapilot-review-1722d2c-6f03d` 尚未删除。审核员已限定并校验清理目标，但自动审批拒绝递归删除，仅返回 `blocked by policy`，没有细分理由；未换壳或换工具绕过，后续由用户处理。
- 第 4 批审核员的数据目录 `../SAPilot-data/runtime/architecture-execution-20261029/reviews/step4/snapshot/web/node_modules` 联接尚未删除。删除命令也被自动审批以 `blocked by policy` 拒绝，未重试或绕过；该联接指向既有依赖，不是新安装的依赖副本。
- 协调者的 `../SAPilot-data/runtime/architecture-execution-20261029/frontend-build/web/node_modules` 联接和 `.next` 构建缓存也尚未删除。已限定到本轮构建快照并验证目标的清理命令被自动审批以 `blocked by policy` 拒绝，整个命令未执行，未重试或绕过。构建源码、日志与哈希作为复核证据保留。
- Docker 补验与导入探测的自建容器、网络已回收，最终查询没有本轮资源；未动其他现有容器、卷、数据库或服务。第 5 批独立审核没有新建联接或运行服务。
- 最终实际资源查询见数据目录 `final-resource-audit.json`：三次自动审批拒绝涉及的目录/联接/缓存仍在，平台已标记归档的工作树实体也仍在。代码交付与这些未完成的清理分开记录；受阻删除和平台归档不同步后续由用户或平台维护者处理，不把归档请求视为实体已删除。
- 没有把临时 venv、生成 jar、完整临时输出或原始日志提交到仓库，没有调用真实计费模型。

## 分支快照与后续清理

用户随后要求新建分支并推送当前版本；已创建 `codex/architecture-foundation-20261029`，以五批集成提交 `70eacec` 为基线。本次分支快照纳入对应文档分类、入口、工作规则、本地资料排除规则，以及此前实际构建使用的 `color` 依赖与锁文件、search-test 六处可选数字回退修正，使这些前端验收上下文进入版本。其他部署脚本、Compose、前端 Dockerfile 和本地换行配置不在这次新增提交范围。

本文随分支快照提交，记录的是发布前已知事实；推送是否成功以实际 Git 推送结果及远端分支 SHA 核对为准，不在提交前预记为已推送。原先纯五批提交隔离区的六项类型错误仍是历史验证事实，不代表补入已有修正后的分支状态。

用户手动执行清理脚本后，协调者实际复核：28 个未跟踪参考文件已有备份且哈希一致；审核临时目录、两处数据目录依赖联接和构建缓存已删除；原项目依赖保留；旧工作树已不在 Git 登记中，但上次确认为空的实体目录仍在，未认定该目录已删除。此前系统拒绝删除的记录保留作过程追溯，不再作为当前全部未清理状态。源码与验证证据继续保留在数据目录。

返回[文档入口](../docs/README.md)或[当前说明](../docs/zh-CN/design/current/README.md)。
