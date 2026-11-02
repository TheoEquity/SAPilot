# Bot / 编排配置保存契约回归

本目录对应架构推进计划第 1 批。测试执行实际表单保存回调、实际 Zod 校验、PUT 请求构造和当前 Pydantic 模型序列化；React hooks、展示组件、HTTP 传输和数据库持久化使用本地替身。它不证明浏览器、真实 BotService/数据库或模型执行链通过。

## 本批变更与保留规则

- `bot.yaml` 补齐后端已有的欢迎字段、默认/保护标记和编排引用；`orchestration.yaml` 以原 Python 字段、必填性、nullable 和默认值为基线。
- Bot 设置保留未编辑的 agent.collections 与 completion 高级参数；意图保存保留 llm.top_p/timeout_ms；Skill 两种保存保留 category、runtime 高级参数和工具高级绑定。显式删除工具/集合或清空文本仍提交空值，不恢复已删除项。
- 画布构造保存对象时带回 viewport 与 edge.type。现有边 ID 规范化仍沿用原逻辑。
- 普通 Skill 保存的校验、兜底冲突保护和去重，以及快捷保存绕过这些处理的既有差异分别测试，未统一两者语义。SkillList 仅在已有 intent_router 的分支收窄 fallback 类型，不改变有效配置的删除逻辑。
- 编排业务类型引用生成 SDK；画布类型仅收窄为其既有的 x/y 坐标与已规范化数组形状，后端仍接受原来的 numeric position 字典；edge.type 的 null 在 UI 边界转为 undefined，与后端 exclude_none 语义一致。
- 未实现 confidence_threshold 比较、启停执行、工具必用/重试/超时策略等规划。字段保存不等于策略执行。

## 执行回归

在仓库根目录、已安装前端依赖且 Python 有 pytest、pydantic、email-validator、PyYAML 的环境执行：

```powershell
python -m pytest tests/contract/test_bot_config_contract.py -q
node tests/contract/bot_config_callbacks.cjs
node web/node_modules/typescript/bin/tsc --strict --noEmit --skipLibCheck --moduleResolution bundler --module esnext --target es2017 tests/contract/generated-types.ts
node web/node_modules/typescript/bin/tsc --project web/tsconfig.json --noEmit --incremental false
```

Node harness 将捕获请求写到 stdout，不连接后端或模型服务。Python 测试对四条路径的载荷执行 `BotUpdate.model_validate` → `config.model_dump_json(exclude_none=True)` → `BotConfig.model_validate_json` → 再次打开编辑与保存。另覆盖显式空数组/空串、缺省与显式 null、默认值、请求失败、快捷保存失败提示及其他 Skill/候选/兜底的保持。

## 隔离生成

本批实际使用 datamodel-code-generator 0.30.0、Pydantic 2.11.7、Redocly 1.34.14、OpenAPI Generator 7.12.0；输出均在被忽略的 `.run/contract/`。生成前创建该目录与专用工具环境，避免调用会清理 `web/src/api` 的 `api:build`。以下命令在仓库根目录执行：

```powershell
node -e "const fs=require('node:fs');const {bundle,createConfig,stringifyYaml}=require('./web/node_modules/@redocly/openapi-core');(async()=>{const r=await bundle({ref:'aperag/api/openapi.yaml',config:await createConfig({})});if(r.problems.some(p=>p.severity==='error'))throw Error('bundle failed');fs.writeFileSync('.run/contract/openapi.merged.yaml',stringifyYaml(r.bundle.parsed));})().catch(e=>{console.error(e);process.exitCode=1});"
.run/contract/venv/Scripts/datamodel-codegen.exe --input .run/contract/openapi.merged.yaml --input-file-type openapi --output .run/contract/view_models.py --output-model-type pydantic_v2.BaseModel --target-python-version 3.11 --use-standard-collections --use-schema-description --enum-field-as-literal all --encoding utf-8 --strict-nullable
java -jar .run/contract/openapi-generator-cli-7.12.0.jar generate -g typescript-axios -i .run/contract/openapi.merged.yaml -o .run/contract/sdk --api-package apis --model-package models --skip-validate-spec --additional-properties enumPropertyNaming=original,supportsES6=true,withInterfaces=true,prependFormOrBodyParameters=false,withoutPrefixEnums=false,withSeparateModelsAndApi=true,useSingleRequestParameter=true
```

`--strict-nullable` 保持 IntentRouterLLM 的非空默认字段；SkillRuntime 原本允许 null 的字段在 YAML 中逐项保留 null 联合，不被该选项收窄。根定义为 OpenAPI 3.1，本批用原生 null 联合替代生成器在 3.1 模式忽略的旧 nullable 关键字；Candidate.examples 用 anyOf 表达数组/null，以兼容这两个固定版本生成器，后端原有接受语义不变。`--encoding utf-8` 避免 Windows 默认 GBK 解码失败，两项也同步到 Makefile。

仅采用 Bot/Agent/编排相关的 20 个 Python 类和 20 个 TS model 文件；TS model 去除生成器的行尾空白和额外尾空行，index 只追加本批导出。Python 生成器把 default_factory=list 输出为列表默认值，Pydantic 每实例复制；回归确认实例之间不共享列表，空值/缺省业务值保持。

未全量覆盖生成输出。2026-10-29 对比发现另有 22 个既有 Python 类差异（聊天、Collection、检索、模型配置等）且全量生成缺少手工 MCPToolInfo；TS 另有 chat-message、chat、model-file、settings 和总 index 差异。这些范围外输出均未采用；全项目生成契约尚未对齐。固定版本 TS 生成器还会报告既有 failResponse 引用解析异常，但完成生成并返回 exit 0；本批相关模型的实际产物另做一致性和编译检查，生成 exit 0 不代表全量定义无误。

## 本地验证记录（2026-10-29）

实际命令、生成比较及原始输出保存在本轮隔离工作区 `.run/contract/`。16 项回归测试通过（隔离环境未装 pytest-asyncio，pytest 对两个现有 asyncio 配置项有警告）；生成 TS nullable 静态契约编译通过。相关 ESLint 无错误，29 条警告与修改前一致。全量 tsc 在变更前后均有 search-test.tsx 的 6 个 `number | undefined` 错误，本批未修改该页面。真实 HTTP/数据库持久化、浏览器交互和问答执行未验收。
