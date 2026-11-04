# 项目目录约定

本文件规定 SAPilot 的文件归属、数据边界和提交规则。项目总目录同时是 Git 仓库根；`origin` 指向 `TheoEquity/SAPilot`。目录结构和运行验收分别判断，实际验证见 `docs/records/`。

## 目录职责

```text
SAPilot/
├─ AGENTS.md             Agent 工作入口，直接引用具体规约
├─ README.md             项目入口与导航
├─ app/                  业务代码、测试、依赖及应用构建配置
├─ maintenance/          Swagger 入口、Langfuse 部署及维护工具
├─ data/                 原始语料、摄取材料、测试题集及本地权重
├─ runtime/              日志、原始评测、凭据、临时工具与运行产物
└─ docs/
   ├─ specs/             工程架构、正式规约与开发环境说明
   ├─ prompts/           手动取用的开发需求启动模板
   ├─ design/            按语言区分的当前设计、讨论、规划和历史资料
   └─ records/           实施、审查和验证的结论记录
```

- `app/aperag/` 保留既有 Python 包名；`app/config/` 为后台任务和日志配置；`app/web/` 为前端；`app/models/` 是模型配置清单，不是权重。
- `app/scripts/`、`app/tests/`、`app/envs/`、`app/deploy/` 分别维护应用脚本、测试、环境模板及应用部署材料；Makefile、Dockerfile、Compose 和依赖清单在 `app/`。应用命令从 `app/` 执行。
- Swagger 由业务 API 提供；`maintenance/swagger/` 集中维护入口说明，不复制另一套 API。Langfuse 配置在 `maintenance/langfuse/`。
- 既有 `docs/zh-CN/`、`docs/en-US/` 中的部署、集成、开发导航和参考资料保留分类。设计正文集中在 `docs/design/zh-CN/` 与 `docs/design/en-US/`，历史归档在 `docs/archive/`。
- Git、GitHub 和本机 Agent 元数据保留工具要求的根目录位置，不把它们视为业务模块。

## 数据与运行产物

- `data/sources/internal/` 保存七份内部测试原件，`data/sources/external/` 保存外部参考资料、支持图片、许可证和来源清单。来源优先级只适用于同一事项且适用范围一致的材料，不能由目录分组推断运行时已应用策略。
- `data/derived/`、`data/weights/` 为派生材料和权重入口，目录存在不代表已生成或安装。`data/evaluation-sets/` 保存可复用题集、评分规则、输入图片及准备依据。
- `runtime/logs/` 保存 API、worker、前端日志、浏览器诊断和原始验证日志；`runtime/evaluations/` 保存历史回答、评分输出和批次运行记录。
- `runtime/private/` 保存账号、私有环境配置及诊断会话；`runtime/config-snapshots/` 保存配置恢复材料；`runtime/history/` 保存历史调查与回放材料；`runtime/reorganization/` 与 `runtime/layout/` 保存迁移映射、哈希和恢复依据。
- `runtime/work/` 为短期工具、API 导出及 PID 等工作文件；`runtime/cache/` 为可配置的检查缓存。`.venv`、`node_modules`、`.next`、pytest 等依赖或缓存可留在 `app/` 中由原工具管理，必须忽略，不作为共享源码提交。
- 旧报告和冻结源码可能保留当时路径；不要把它们当当前可执行配置。跨布局追溯使用 `runtime/layout/` 中的移动映射，不复制原始资料或建立隐式旧路径别名。

## 文档与临时材料

正式规约在 `docs/specs/`，由根 `AGENTS.md` 直接引用。README 只提供说明和导航，不承载开发要求。开发建议和 Prompt 模板不自动成为强制规约，产品运行时的模型 Prompt 属于 `app/` 业务配置。

`docs/design/zh-CN/` 保留 `current/`、`planned/`、`discussions/`、`historical/`、`pending-review/`、`test-guides/` 和 `todos/` 的状态区别；计划和讨论不自动获批，静态源码说明不替代运行验收。

一次性调查优先在内存中执行；确需落盘时放在忽略的临时目录，结束后核对引用再回收。临时清理脚本只在验证成功后回收自身，失败时保留排查依据。题集、评分规则、正式回归和必要结果不自动删除；可复用脚本和测试分别维护在 `app/scripts/`、`app/tests/`。不为每轮清理新增常驻工具或多套报告。

## 移动与提交

1. 保留原有未提交内容、分支与工作树；移动前核对路径边界，移动后核验文件哈希并更新当前引用。不要将用户未跟踪文件直接视为垃圾。
2. 代码、共享规约和脱敏模板提交 Git；`data/`、`runtime/`、实际 `.env`、原始材料、模型权重、账号、密钥及原始评测不提交。Git 与 Docker 忽略规则都要覆盖私有内容，应用构建上下文使用 `app/`。
3. 数据库和对象存储的 Docker 数据卷与目录整理分开管理；调整挂载时保持卷和项目名，不因重组删除数据卷。
4. 提交前按明确路径检查暂存差异；目录移动、运行验证、本地提交和推送是不同状态，不能相互推断。
