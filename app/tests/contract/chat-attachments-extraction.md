# 第5批：聊天与附件模块提取

记录日期：2026-10-29。固定基线：`0b86183eb023ee0094e0f370905cd5e73b4a2bff`。本批仅按既有行为拆分 Web 聊天组件，不改公共 API、生成类型、后端、钉钉、传统 Flow 或共享 UI。

## 改动与保留行为

- [use-chat-messages.ts](../../web/src/components/chat/use-chat-messages.ts)承接原组件的连接、消息/加载状态、发送、FAQ、反馈、取消和滚动 effects；[ChatMessages](../../web/src/components/chat/chat-messages.tsx)保留原 JSX 与展示判断。原内联实现迁出，没有第二套业务实现。
- [use-chat-attachments.ts](../../web/src/components/chat/use-chat-attachments.ts)承接附件 state/refs、选择、拒绝、重复校验、上传、状态函数、删除与粘贴；[ChatInput](../../web/src/components/chat/chat-input.tsx)保留输入、发送载荷和原 JSX，`Attachment` 类型继续由原入口导出。FileUpload 原内联回调移为 Hook 回调，仅增加 File[] 参数注解；保持每次 render 的新函数身份，因为现有 FileUpload 的 store useMemo 依赖此回调。
- `handleSendMessage` 依赖数组显式补上 Hook 返回的原生稳定 `setAttachments`，避免拆分后新增 lint 警告；发送函数体不变。其他现有回调/effect 依赖保持。仅移除搬迁后无用的命名导入和原未用 useInterval 导入。
- 保留消息 mutation/clone、part_id 累加和顺序；stop 仍添加 references 与 stop 片段；error 不自动结束 loading；malformed JSON 仍抛错。取消仍仅 disconnect → connect → setLoading(false)，不代表后端任务取消。history 仅作为初始 state，prop 改变不自动回放替换。
- 未挂接的 `checkAttachmentStatus` 原样迁移，仍没有调用或轮询。非图片上传后可停在 uploaded 并阻挡发送；没有补状态轮询或吞异常。图片上传成功仍立即 success，粘贴与上传各生成一次 URL；删除仅撤销当前 URL，发送清空仍不撤销 URL。既有生命周期资源问题仅记录，没有扩修。
- 单附件限制、重复判断、失败上传不自动重试、移除后迟到上传响应忽略、附件未完成阻挡、发送前清空输入/选择/附件、同步提交抛错仍保留已清空状态，均沿用基线。传统 Flow 的 query 与 data/message 差异未处理。

## 验证

在交付工作树根目录运行：

```powershell
node --test tests/contract/chat_attachments_callbacks.cjs
.run/contract/venv/Scripts/python.exe -m pytest tests/contract/test_bot_config_contract.py tests/contract/test_intent_model_parameters.py -q
node web/node_modules/typescript/bin/tsc --project web/tsconfig.json --noEmit --incremental false
git diff --check
```

在 `web/` 下运行相关 ESLint，使用 `--no-ignore` 避免工作树所在的隐藏父目录导致文件被忽略：

```powershell
node node_modules/eslint/bin/eslint.js --no-ignore src/components/chat/chat-input.tsx src/components/chat/chat-messages.tsx src/components/chat/use-chat-attachments.ts src/components/chat/use-chat-messages.ts
```

[Node harness](chat_attachments_callbacks.cjs)通过 git show 读取固定基线与当前真实 TS/TSX，并由现有 TypeScript 转译器执行相同场景。只在组件/Hook 外层 return 前注入本地变量捕获，不替换业务回调算法。原始基线源码、两边观察和命令输出存于被忽略的 `.run/chat-attachments/`。

7项通过：1组 AST 对照与6组前后行为差分。AST 比较消息完整 setup 与 JSX、附件完整 state/ref/上传/effect setup、原有回调及依赖、原 FileUpload 回调体；输入 JSX 仅规范化回调引用，忽略 JSDoc 与 CRLF/LF 差异。发送函数只允许上述稳定 setter 依赖适配。行为涵盖消息流/多个 turn/引用/工具、异常 JSON/error、发送/FAQ/反馈失败与非200、readyState/取消顺序、附件选择/重复/单文件、图片粘贴/预览/撤销、上传/状态、发送阻挡/清空及请求失败/迟到响应。

既有52项通过（保存16+意图36），保留2条既有 pytest 配置警告。全量 tsc 前后均 exit 2，仅同一 search-test.tsx 的6个 `number | undefined` 错误；两份完整输出相同，本批未改该文件。相关 ESLint 0错误；基线2条未使用警告（useInterval、checkAttachmentStatus），提取后仅剩保留的 checkAttachmentStatus 1条警告。构建由主Agent在已准备的本地 D盘快照最终执行，本记录不宣称构建通过。

## 限制、资源与交接

React hooks/JSX、时间/File/URL/clipboard、WebSocket、HTTP、toast、滚动和展示组件使用本地替身；state/ref支持重渲染，effects按依赖显式刷新，但不模拟真实React调度、StrictMode或浏览器生命周期。状态检查函数由harness手动调用仅验证保留的函数体，不能推断线上已轮询。结果不证明真实浏览器、WS鉴权/重连恢复、后端取消、数据库历史持久化或SAP问答效果。

复用现有前端只读依赖junction及 `.run/contract/venv`，未安装依赖、未改锁文件、未调用真实模型/后端或操作数据库、服务、其他工作树。新增本地资源仅 `.run/chat-attachments/` 日志/基线，未启动后台进程。本批提交后交主Agent安排独立强审核与最终真实构建；提交不表示已审核或已集成。
