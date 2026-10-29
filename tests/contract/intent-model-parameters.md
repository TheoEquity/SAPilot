# 第 2 批：意图分类模型参数修正与验证

记录日期：2026-10-29。代码基线：`1722d2cb2602db9ac958a3857a9c4cb33ab7de44`（第 1 批保存契约）。本批仅修正 Agent 意图分类的 Provider/model 选择和 max_tokens 传递；没有接口/schema 变更，无需重新生成模型或 SDK。

## 改动与依据

[实际分类分支](../../aperag/service/agent_chat_service.py)原来把消息/Bot 的 completion 传给 `_get_agent_session`，该方法据此查询 Provider、用户 Key 和 base_url，并构造 AgentConfig.default_model。随后调用的 `get_llm(intent_model)` 在[会话管理器](../../aperag/agent/agent_session_manager.py)中只返回缓存实例，不据参数切换 Provider。分类 RequestParams 的 maxTokens 另固定为 512，未读取已保存的意图 max_tokens（模型默认值为 1024）。

本批在分类分支复制消息与 completion，仅覆盖 model_service_provider/model，再调用原 `_get_agent_session`；分类 maxTokens 读取 intent_router.llm.max_tokens。原消息/Bot completion 保留供 Skill 执行。规则、强制 Skill、候选过滤、Prompt、temperature 参数、兜底、异常传播和队列 finally 均沿用原逻辑。没有修改会话平台、缓存键、Skill runtime、confidence_threshold、启停、IO、重试或传统 Flow 协议。

## 可复跑的源码方法回归

[回归文件](test_intent_model_parameters.py)使用 pytest、Pydantic 和 Python 标准库。可在仓库根目录执行：

```powershell
python -m pytest tests/contract/test_intent_model_parameters.py -q
```

本轮复用隔离工作区已有的 `.run/contract/venv/Scripts/python.exe`。测试以 AST 编译执行当前文件中的完整方法体，不复制其算法，不通过字符串匹配判定修复：

- 实际 `process_agent_message`、`_get_agent_session`、`try_hard_rules_match`。
- 实际 AgentConfig、ChatSession、get_or_create_session；只替换 ChatSession.initialize，避免初始化 MCP/模型网络。
- 实际 Pydantic 配置模型与实际异常类。为避免导入业务运行栈，方法注解延后求值；数据库、LLM.generate_str、RequestParams、SimpleMemory、历史、队列/流格式化、Skill 执行使用本地替身。

因此测试证明的是源码方法的控制流和送达边界的参数，不证明真实 SDK 已执行、真实 MCP 初始化、Skill 模型调用、HTTP/WS 或数据库持久化。

覆盖：不同 Provider 的查询/Key/base_url/default_model、max_tokens=1/1379/缺省1024、temperature=0/0.17、原消息与 Bot fallback completion 保持、最近四条历史、精确 Prompt、禁用候选、首条规则和强制 Skill 优先级、分类输出修剪与非法/空输出兜底、模型异常、缺 Provider/Key 时不调用模型/Skill及队列关闭。

同 Provider 缓存场景实际执行现有缓存管理与 get_llm：先建立 default_model 为旧回答模型的会话，再执行分类。会话复用且旧 config.default_model 保持；每次分类 generate_str 收到显式 intent model/maxTokens。本批没有把新 AgentConfig 的传入误记为旧缓存已刷新。

## 固定版本 SDK 的静态核对

本轮仅下载 wheel 并读取源码，没有安装或执行这两个 SDK：

```powershell
python -m pip download --no-deps --only-binary=:all: --dest .run/intent-parameters mcp-agent==0.2.6 openai==1.101.0
```

下载文件 SHA256 均与 `uv.lock` 对应 wheel 一致：

| wheel | SHA256 |
| --- | --- |
| mcp_agent-0.2.6-py3-none-any.whl | `184205d9a16535264497568b3ca2a805c8ac8e36144f6ff4264bdb785d71f745` |
| openai-1.101.0-py3-none-any.whl | `6539a446cce154f8d9fb42757acdfd3ed9357ab0d34fcac11096c461da87133b` |

原始 wheel 内部源码位置：

- `mcp_agent/workflows/llm/augmented_llm.py:372–392,418–439`：显式 request_params.model 优先；请求以 exclude_unset=True 的字段覆盖默认参数。
- `mcp_agent/workflows/llm/augmented_llm_openai.py:204,247,262–304`：生成请求使用合并后的 model；普通模型把 maxTokens 映射为 max_tokens，reasoning 分支映射为 max_completion_tokens。
- 同文件 `968–979`：AsyncOpenAI 从会话配置读取 api_key/base_url；`openai/resources/chat/completions/completions.py:2583–2600` 将 model、max_tokens/max_completion_tokens 放入请求体。

这是固定版本的静态参数映射证据，支持同 Provider 缓存下显式 model/token 参数的方案判断；没有验证真实 HTTP 载荷、Provider 接受情况或返回效果。temperature 只核对本地 RequestParams 的保留，未把它升级为真实 Provider 采样参数验收。

## 本轮实际结果与限制

原始输出全部另存于被忽略的 `.run/intent-parameters/`，未覆盖第 1 批 `.run/contract/` 的证据：

| 检查 | 实际结果 |
| --- | --- |
| 修改前初始 16 项回归 | 7 失败、9 通过；直接复现查询 answer-provider、default_model=answer-model、maxTokens=512 |
| 最小修改后初始 16 项回归 | 16 通过 |
| 增补 temperature=0 和 Bot completion fallback 后，与第 1 批联合运行 | 36 通过（本批20 + 第1批16）；2 条既有 pytest asyncio 配置警告，未装 pytest-asyncio |
| 本批测试文件 Ruff | 通过 |
| Git diff whitespace 检查 | 通过 |
| SDK wheel 哈希与静态映射 | 已核对；未执行 SDK/HTTP |

联合运行命令：

```powershell
.run/contract/venv/Scripts/python.exe -m pytest tests/contract/test_intent_model_parameters.py tests/contract/test_bot_config_contract.py -q
ruff check tests/contract/test_intent_model_parameters.py
git diff --check
```

未读取真实凭据、未调用计费模型、未连接或修改现有数据库。未验真实 HTTP/WS、浏览器、MCP、跨 Provider 并发隔离及 SAP 问答效果；本批只改后端分类参数，没有重跑前端构建。

已知既有问题仍保留：同 Provider 缓存不因新配置刷新旧 instruction/Key/base_url/default_model；`MCPAppFactory` 写全局 OPENAI 环境变量；`_get_agent_session` 在缺 Provider/Key 时使用错误签名构造 AgentConfigurationError，当前会抛 TypeError。失败回归只要求在该失败边界停止、未调用模型/Skill并关闭队列，不把 TypeError 作为产品应维持的契约。无系统 Aperag Key 的自动创建分支未覆盖，也没有据此承诺该既有分支正常。

临时资源是本批 wheel、提取源码、静态核对脚本及日志；没有新增服务、进程、端口、依赖安装或数据库资源。交由独立审查者核对实际 diff、上述回归和边界后，再由主 Agent 决定集成。
