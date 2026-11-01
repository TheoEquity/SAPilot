# 项目目录约定

更新日期：2026 年 10 月 29 日。本文件约定 SAPilot 的本地文件放置和 Git 提交边界。目录整理不代表运行部署、摄取或容量验收已经完成。

## 1 主项目与工作树

主项目目录名称为 `SAPilot/`，对应仓库为 [TheoEquity/SAPilot](https://github.com/TheoEquity/SAPilot)。主目录位置在本次整理中保持不变。

Git 工作树是同一仓库的分支工作区。以 `git worktree list` 查询实际位置，不把它们当成多份独立项目；保留现有工作树，只有核对分支提交、未提交内容和关联任务后才能收尾。目录干净不能证明分支已合入或任务已完成。

## 2 仓库结构

```text
SAPilot/
├─ aperag/              后端源码，保留既有 Python 包名
├─ web/                 前端源码
├─ config/              应用与 Celery 任务配置
├─ models/              模型配置清单与生成脚本，不放权重
├─ scripts/             启动、开发、构建及维护脚本
├─ deploy/              部署模板
├─ envs/                可共享的环境模板
├─ tests/               自动化测试及必要的脱敏小样本
├─ specs/               架构概述、开发规约与开发环境说明
├─ records/             分批计划、实施、审核与验证过程记录
├─ docs/
│  ├─ README.md         文档导航
│  ├─ SAPILOT_PROJECT_CONTEXT.md
│  ├─ zh-CN/            按设计、部署、开发、集成和参考分类
│  ├─ en-US/            保留既有英文文档
│  └─ archive/          历史记录
├─ AGENTS.md            仓库入口与维护约束
├─ README.md            英文项目入口
└─ README-zh.md         中文项目入口
```

`docker-compose.yml`、`Dockerfile`、`Makefile` 和依赖锁文件继续留在原位置；本次不改应用包名或重构配置系统。`deploy/` 中的模板存在，不表示对应服务已部署。

设计资料在 [`docs/zh-CN/design/`](../docs/zh-CN/design/README.md) 下分类存放：`current/` 为依据源码整理的当前说明，`planned/` 为未实现或未闭合的规划，`historical/` 为过时设计与历史记录，`test-guides/` 为测试手册，`todos/` 为旧待办；讨论稿继续单独放在 [`discussions/`](../docs/zh-CN/design/discussions/README.md)。原 `pending-review/` 保留 18 篇旧正文及逐篇核对记录，沿用路径供追溯，常规阅读改从当前说明进入。根目录仅保留分类导航和目录元数据。分类不将原文声明升级为已定案或已实现，当前说明保留静态核对与运行验证的区别；规划未自动获批，历史归属不等于全部内容作废。旧原文保留。

`specs/` 存放工程架构概述、开发规约、目录约定和开发环境说明，由根 `AGENTS.md` 直接引用。分批计划、实施、审核、集成、补验和清理等过程记录单独放在根目录 `records/`，不放在 `docs/` 或 `specs/` 下。

## 3 本地资料目录

本地资料统一放在主项目旁的 `../SAPilot-data/`。以下路径以这个数据目录为基准，不依赖具体盘符：

这里的相对路径以主项目为基准，不以任意工作树为基准。其他工作树需要这些资料时，显式使用主项目旁的共享数据目录，不另建一套原件副本。

```text
SAPilot-data/
├─ README.md
├─ sources/
│  ├─ source-groups.json
│  ├─ internal/          七份内部知识测试语料与来源清单
│  └─ external/          已下载的外部文档、图片与来源清单
├─ derived/             后续解析、图片、分块等派生产物
├─ logs/                服务日志、浏览器诊断导出及原始验证日志归档
├─ evaluations/
│  ├─ document-inspection/
│  ├─ four-business-skills/
│  └─ intent-route-fix/
├─ weights/             后续准备的本地模型权重
└─ runtime/
   ├─ config-snapshots/ 历史配置快照
   ├─ private/          本机账号等私有记录
   └─ reorganization/   本次整理的校验、映射与回退材料
```

`derived/` 和 `weights/` 是归位入口；目录存在不表示已经生成解析产物或安装模型。数据库持久卷、正在使用的 `.env` 及对象存储不在本轮搬迁范围，运行配置保持原状。空的 `resources/` 保留原状。

现有轻量开发脚本仍会在仓库内生成被忽略的 `.run/`，保存 PID 和日志。本次将已有历史产物外移，不改启动脚本；新生成的短期运行文件仍是本地文件，不提交 Git。

`.codex/personal-development-workflow.json` 是本机工作流适配，含本机仓库位置，原样保留并忽略。共享的项目规则写入 `AGENTS.md`，不把本机路径或 SQLite 工作流状态提交到仓库。

## 4 资料分组与路径口径

- `sources/internal/`：最初七份测试文件的内部知识语料副本。文件已与原件逐字节校验；“内部测试资料”不等于生产审批通过。
- `sources/external/`：已下载的 169 份外部文档或原文章节，以及支持图片、许可证和来源清单。下载和文件校验不等于摄取或检索验收通过。
- `sources/source-groups.json` 的组路径以 `SAPilot-data/` 为基准；各组 `sources.json` 中的 `file` 以所在组目录为基准。
- 同一事项且适用范围一致时，内部资料优先，外部资料补充；保留版本、来源和必要冲突说明。目录和清单中的分组尚未自动应用到运行检索系统。

七份原始测试文件另保存在 `runtime/reorganization/2026-10-28/original-test-files/` 作为迁移回退材料。有效语料统一使用 `sources/internal/`，不要将备份再次摄取成独立知识。

历史评测和运行快照保持原文，可能仍记录旧路径、旧服务端点和当时的系统状态；它们不是当前可执行配置或本次离线验收结果。旧文件到新位置的逐文件映射及哈希保存在本地 `runtime/reorganization/2026-10-28/moves.json`。

## 5 本次归位关系

下表左列是整理前的仓库相对路径；右列明确标出仓库内路径或数据目录相对路径。

| 原位置 | 当前归属 |
| --- | --- |
| `downloads/sap-official/` | 数据目录 `sources/external/` |
| `downloads/enterprise-internal/` | 数据目录 `sources/internal/` |
| `downloads/source-groups.json` | 数据目录 `sources/source-groups.json` |
| `测试用例/` | 数据目录中的迁移原件备份；有效语料见 `sources/internal/` |
| `.run/document-inspection/` | 数据目录 `evaluations/document-inspection/` |
| `.run/four-business-skills/` | 数据目录 `evaluations/four-business-skills/` |
| `.run/intent-route-fix/` | 数据目录 `evaluations/intent-route-fix/` |
| `.run/` 根目录配置快照 | 数据目录 `runtime/config-snapshots/` |
| `.run/` 本机账号记录 | 数据目录 `runtime/private/` |
| `MEMORY0522` | 仓库 `docs/archive/MEMORY0522.md` |
| `docs/SAPILOT_ARCHITECTURE_DRAFT.md` | 仓库 `docs/zh-CN/design/discussions/offline-deployment-draft.md` |
| `docs/dingtalk-integration.md` | 仓库 `docs/zh-CN/integration/dingtalk.md` |

## 6 Git 提交规则

1. 本地仓库中的目录就是后续提交到 GitHub 的结构，不另维护一套“上传专用”目录。
2. 代码、文档、配置模板和脱敏小样本按所属目录提交。企业原件、完整知识语料、私有清单、模型权重、账号、密钥、日志和原始评测结果不提交。
3. `.env` 保持本地；共享配置放在 `envs/` 模板中。`models/` 继续提交配置清单，不能为了存权重而删除或忽略整个目录。
4. 提交时按本次变更的明确路径选择文件，先查看 `git status --short` 和暂存差异，避免把既有未提交改动顺带纳入。
5. 移动文档时同步修改导航和相对链接；搬本地资料时先核验哈希和清单，再处理旧副本，保留回退依据。
6. 整理文件、创建本地提交和推送远端是不同状态，交付时分别说明；本次整理不自动提交或推送。

## 7 整理验收

- 原有源码、服务配置、环境配置和分支提交保持不变；用户既有改动得到保留。
- 移动文件与整理前哈希一致；仅来源路径元数据按新目录更新，并保留旧清单备份。
- 内部七份文件与原件一致，外部清单中的文件均可找到并通过哈希校验。
- 新增或修改文档的本地链接有效，无需访问本机私有目录才能阅读 GitHub 上的仓库文档。
- Git 与 Docker 忽略规则覆盖本机私有内容；不以忽略规则代替提交前的逐项检查。
- 应用代码和运行配置未改时不宣称重新验证了完整部署；运行、摄取质量和容量测试仍按各自验收口径执行。
