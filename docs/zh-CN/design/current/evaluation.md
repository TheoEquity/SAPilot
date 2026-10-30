# SAPilot 当前问题集与自动化评测

> 状态：当前说明，依据 2026 年 10 月 29 日源码静态核对整理。存在评测流程不代表当前题集、评分模型或 SAP 问答效果已经通过验收。

## 问题集准备

QuestionSetService 提供问题集与问题的管理，并可从 Collection 文档生成问题和标准答案。生成在服务方法中准备文档内容、按上下文预算裁剪并调用 LLM；不能按旧架构图认定存在独立的 QuestionGenerationTask。

前端已有 Collection 下的问题集列表、编辑及生成入口，生成结果可进入问题编辑流程。实际页面与组件位于 Next.js 的 `workspace/collections/[collectionId]` 下，不使用原稿路线作为文件定位依据。

依据：[QuestionSetService](../../../../aperag/service/question_set_service.py)、[评测路由](../../../../aperag/views/evaluation.py)、[问题集页面](../../../../web/src/app/workspace/collections/[collectionId]/questions/)。

## 配置与存储

| 内容 | 当前模型 |
| --- | --- |
| 问题集与问题 | `question_sets`、`questions` |
| 评测任务 | `evaluations`，存 Collection、Question Set、`agent_llm_config`、`judge_llm_config` 等 |
| 逐题结果 | `evaluation_items`，含状态、问题与标准答案快照、回答及详情、分数与理由 |

当前任务配置使用模型配置 JSON，而不是旧稿的 `bot_id`、`judge_llm_model_id`；结果表也不是原设计的 `evaluation_results`。依据：[数据库模型](../../../../aperag/db/models.py)、[评测 schema](../../../../aperag/api/components/schemas/evaluation.yaml)。旧 SQL 仅在[历史记录](../historical/superseded-design-notes.md)中保留为追溯材料。

## 任务执行与评分

1. EvaluationService 校验配置并创建任务，尝试触发协调任务。
2. EvaluationExecutor 负责初始化、批次调度和逐项处理，Celery 执行对应任务；Beat 另以 300 秒周期协调评测。
3. Worker 经内部 `/api/v1/evaluations/chat_with_agent` HTTP 接口调用 Agent 处理问题。
4. judge LLM 根据回答与标准答案输出 `score`、`reasoning`，代码要求五分制；异常与失败分支含零分处理。
5. 最终处理汇总条目状态与平均分。

依据：[EvaluationService 与 Executor](../../../../aperag/service/evaluation_service.py)、[Agent 内部路由](../../../../aperag/views/evaluation.py)、[Celery 任务](../../../../config/celery_tasks.py)、[Beat](../../../../config/celery.py)。

## 暂停、恢复与结果界面

`/evaluations/{eval_id}/pause` 与 `/resume` 已有路由及服务方法；恢复会重新触发协调。暂停时已在途任务的处理和恢复一致性尚待运行验证，不能再把这两个接口整体列为未开发。

前端已有评测创建、列表、详情结果和重试等组件。依据：[评测路由](../../../../aperag/views/evaluation.py)、[评测服务](../../../../aperag/service/evaluation_service.py)、[评测页面](../../../../web/src/app/workspace/collections/[collectionId]/evaluations/)。

当前仍需验证题集代表性、模型可达、自动评分稳定性、暂停/恢复与失败重试一致性。历史评测原始结果留在项目旁的数据目录，不能替代当前版本的验收，目录见[项目目录约定](../../reference/project-layout.md)。

原始材料：[评测设计及核对记录](../pending-review/evaluation-design.md)。返回[当前说明目录](README.md)。
