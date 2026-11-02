# 第4批：意图路由模块提取

记录日期：2026-10-29。固定基线：`d40a75c8015c72aed27ee1697ce76b3ec2036209`。本批是行为保持的后端试点，不修改接口、配置或模型执行语义。

## 改动与边界

- 新增 [intent_router.py](../../aperag/agent/intent_router.py)：`route_intent` 按原顺序处理强制 Skill、首条命中规则、模型分类和非法输出兜底；`try_hard_rules_match` 从服务迁入本模块。
- [Agent 服务](../../aperag/service/agent_chat_service.py)保留接入和编排，以绑定的 `_get_agent_session` 回调提供原会话获取能力。原内联路由和旧规则方法删除，未保留第二套实现。全仓源码调用搜索未发现旧规则方法的其他业务调用。
- 服务仍先合并/校验 completion，发送 start、读取历史并创建 memory，再处理 FAQ 结束旁路，然后校验 orchestration/router/必填字段。强制 Skill 仍不能跳过这些校验。最近四条历史的选择、Skill 上下文切换、`_execute_skill` 调用与队列 finally 留在原位置。
- 第2批 provider/model 消息复制与 max_tokens 修正保留；temperature、启用候选、完整 Prompt、历史转 OpenAI 格式、分类调用次数及异常传播沿用基线。未新增强制/规则目标的候选校验。
- 未拆 Skill 执行器、FAQ、MCP、缓存、凭据、历史、数据库、渠道或传统 Flow；未补 confidence_threshold、启停、IO、重试。未清理该服务其他遗留死代码。

## 源码一致性核对

本地 `.run/intent-router/compare-source.py` 从固定基线 `git show` 读取实际源码，与当前 AST 比较，结果见 `.run/intent-router/source-comparison.txt`：

1. 规则函数 AST 相同，仅移除原 staticmethod 装饰器。
2. 路由语句 AST 在 `merged_agent_message` 改为参数名 `agent_message`、原 self 方法调用改为模块函数/回调，以及删除未使用的局部 `import re as _re` 后相同；新增返回选中 ID。比较包含精确 Prompt 字符串、候选过滤和 RequestParams 全部表达式。
3. 服务原消息合并、校验、FAQ、历史切片、上下文切换、Skill 调用、未触及的死代码和 finally AST 相同；其他服务方法 AST 相同。
4. 原8个测试函数（参数化后20项）、测试辅助函数和 History AST 相同，未删除或放宽断言。仅扩展 fixture 装载真实模块与 FAQ 方法。

## 可复跑验证

在交付工作树根目录执行：

```powershell
.run/contract/venv/Scripts/python.exe -m pytest tests/contract/test_intent_model_parameters.py tests/contract/test_bot_config_contract.py -q
ruff check aperag/agent/intent_router.py tests/contract/test_intent_model_parameters.py
ruff check aperag/service/agent_chat_service.py --output-format json
git diff --check
```

本批输出存放在被忽略的 `.run/intent-router/`，不覆盖之前批次输出：

| 检查 | 实际结果 |
| --- | --- |
| 提取前原36项联合基线 | 36通过，2条既有pytest配置警告 |
| 提取前新增16项边界与原意图20项 | 36通过，2条相同警告 |
| 提取后联合回归 | 52通过（意图原20+新增16+保存16），2条相同警告 |
| 新模块和测试Ruff | 通过 |
| 服务Ruff前后对比 | 5→4条既有诊断；随迁移移除了未使用局部re的F401，无新增code/message诊断 |
| AST源码及原测试比较 | 通过上述4组核对 |
| Git差异空白检查 | 通过 |

新增16项覆盖：关键词大小写和中文标准化、正则命中、禁用/非法正则/未知类型/空值规则跳过及首条优先、未命中规则只分类一次、Skill切换与同Skill缓冲保留、6种配置缺失先于强制路由、FAQ结束绕过路由配置、空白Prompt的原默认文案及精确权威候选后缀。FAQ新增测试的初始文案预期曾与源码不符，对照原方法修正测试预期后才形成提取前通过基线；产品文案未修改。

## 替身、限制与资源

测试执行真实服务方法、新模块函数、AgentConfig、ChatSession/get_or_create_session、实际Pydantic模型和异常类。因本地缺完整运行栈，使用AST装载定义并延后注解求值；RequestParams、SimpleMemory、数据库与LLM传输、历史、流格式化、队列、Skill执行及会话初始化使用本地替身。新路由算法没有替换为mock。

因此结果证明的是这些真实源码定义的控制流、路由选择及送达替身的参数，不证明实际SDK、HTTP/WS聊天、模型返回效果、真实Skill/MCP执行、跨Provider并发隔离或SAP效果。第2批固定wheel的静态映射证据仍见 [参数验证记录](intent-model-parameters.md)，本批没有重新执行SDK或真实请求。独立Docker保存验证不属于本批路由执行验收。

已知原同Provider缓存行为、全局环境写入、缺Provider/Key时异常构造签名问题保持原样，不由本批测试升级为产品保证。测试中模型异常和缺Provider/Key仍停止于原失败边界，未执行Skill且关闭队列。

本批复用 `.run/contract/venv`，未安装依赖，未读取真实凭据，未调用计费模型，未操作Docker或现有数据库，未创建服务、监听端口或后台进程。新增资源只有本批源码、测试、记录以及 `.run/intent-router/` 本地脚本/日志。提交后交主Agent安排独立审核；提交不表示已经集成或通过强审核。
