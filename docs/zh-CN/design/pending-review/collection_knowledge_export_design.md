# 知识库导出功能设计

> 分类：待核对设计；已补本轮源码核对。核对日期：2026 年 10 月 29 日。
> 状态：异步 ZIP 导出主链有源码；七天自动清理未找到实现，入口条件和并发边界需按当前代码理解。
> 使用边界：下文原稿保留供追溯；先读本次核对，再按源码与运行证据判断。静态存在不等于已验收，本次不构成设计定案或实施批准。见[核对总览](README.md)。

<!-- source-audit:begin -->
## 本次源码核对（2026 年 10 月 29 日）

**结论：** 异步 ZIP 导出主链有源码；七天自动清理未找到实现，入口条件和并发边界需按当前代码理解。

核对范围为本文主要架构、接口、配置、处理流程及完成状态声明；不是逐行示例、全量安全或性能审计。依据为当前工作区源码（含既有未提交改动），详见[基线与状态说明](README.md#核对口径)。本轮未启动服务、调用模型、执行数据库或后台任务。

| 原文范围 / 声明 | 判定 | 当前源码与使用限制 | 源码依据 |
| --- | --- | --- | --- |
| 第 4–6 节：创建、轮询和下载 API | 仍适用（静态） | 三个路由存在，创建返回 202；ExportService 创建任务、提交 Celery、按任务创建者查状态并流式下载。 | [aperag/views/export.py](../../../../aperag/views/export.py)<br />[aperag/service/export_service.py](../../../../aperag/service/export_service.py) |
| 第 3 节：Owner 与并发数量 | 部分适用 | 后端核对 Collection.user，区分不存在与非 Owner；未完成任务计数 >=3 时拒绝新建（429），不是已有数量 >3 才拒绝。并发竞争下上限是否严格成立未运行验证。 | [aperag/service/export_service.py](../../../../aperag/service/export_service.py) |
| 第 4、5 节：打包、manifest 和存储路径 | 仍适用（静态） | 任务按 Collection 对象前缀列举，最多 5 个下载线程，生成 manifest、ZIP 并上传 exports/user-...；完成时设置七天后的 gmt_expires。 | [config/export_tasks.py](../../../../config/export_tasks.py)<br />[aperag/db/models.py](../../../../aperag/db/models.py) |
| 第 5 节：七天定时清理并转 EXPIRED | 规划／未找到对应执行链 | 在 aperag 与 config 的导出实现和 Beat 注册中，仅找到过期时间记录、EXPIRED 枚举及下载分支，未找到导出过期清理任务或调度注册。不能承诺七天自动删除；原文件回退/实际存储需运行核验。 | [config/export_tasks.py](../../../../config/export_tasks.py)<br />[config/celery.py](../../../../config/celery.py)<br />[aperag/service/export_service.py](../../../../aperag/service/export_service.py) |
| 第 7 节：前端组件、轮询和阻止关闭 | 部分适用 | CollectionExport、2 秒轮询、处理中阻止关闭有代码；入口当前按 share 条件渲染，并非原文示例直接比较 collection.user 与 currentUser.id；具体页面权限仍由后端约束。 | [web/src/components/collections/export-dialog.tsx](../../../../web/src/components/collections/export-dialog.tsx)<br />[web/src/app/workspace/collections/[collectionId]/collection-header.tsx](../../../../web/src/app/workspace/collections/[collectionId]/collection-header.tsx) |
| MVP、完整文件和可下载性声明 | 待运行验证 | 文件打包链存在不等于全部下载成功、对象存储权限或大文件行为已验收；本次未创建导出任务、下载 ZIP 或执行清理。 | [config/export_tasks.py](../../../../config/export_tasks.py)<br />[aperag/objectstore/base.py](../../../../aperag/objectstore/base.py) |

以下保留原稿；其中旧的“已实现”“待完成”、接口示例和效果数字，以本节标注的适用范围为准。未单列的示例不代表已逐行验证。

---

## 原文（保留记录）
<!-- source-audit:end -->

**状态**: 已实现（MVP）

---

## 1. 背景与目标

SAPilot 文档处理管线会将用户上传的原始文件（PDF、Word 等）解析为结构化知识内容，并将所有产物存储在对象存储中。这些内容有独立的使用价值：

- 将解析结果迁移到其他 RAG 框架（如 LlamaIndex、Dify）
- 审查文档解析质量，发现截断/格式错误
- 离线分析分块策略效果
- 数据备份与合规存档

本功能在知识库操作菜单中新增「**导出知识库**」按钮，允许知识库 Owner 将对象存储中该知识库目录的全部内容打包为 ZIP 文件下载。

**MVP 范围**：
- ✅ 触发导出（异步后台打包）
- ✅ 实时进度展示（前端轮询）
- ✅ 完成后一键下载 ZIP
- ❌ 后台运行（对话框保持打开直到完成或失败）
- ❌ 导出历史页面

---

## 2. 导出内容

对象存储中每个知识库的目录结构如下：

```
.objects/
└── user-{user_id}/
    └── {collection_id}/           ← 导出此前缀下的全部内容
        ├── {document_id_1}/
        │   ├── original.pdf
        │   ├── converted.pdf
        │   ├── processed_content.md
        │   ├── chunks/
        │   │   ├── chunk_0.json
        │   │   └── chunk_1.json
        │   └── images/
        │       ├── page_0.png
        │       └── page_1.png
        └── {document_id_2}/
            └── ...
```

**导出策略**：对 `user-{user_id}/{collection_id}/` 前缀下的所有对象做全量导出，无任何过滤。

生成的 ZIP 包结构：

```
{collection_title}_export_{YYYY-MM-DD}.zip
├── manifest.json              ← 元数据（id → 标题映射）
├── {document_id_1}/
│   └── ...（与对象存储目录结构一致）
└── {document_id_2}/
    └── ...
```

`manifest.json` 格式：

```json
{
  "schema_version": "1.0",
  "collection": {
    "id": "colff4f33902752abee",
    "title": "医学文献库",
    "exported_at": "2026-03-04T10:00:00Z"
  },
  "documents": [
    { "id": "doc_xyz789", "title": "高血压诊疗指南", "status": "COMPLETE" }
  ]
}
```

> `manifest.json` 仅作信息记录，不影响哪些文件被导出。导出的 ZIP 保存在对象存储的 `exports/user-{user_id}/export_{task_id}.zip`，7 天后由定时任务清理。

---

## 3. 权限

| 角色 | 能否导出 |
|------|---------|
| Collection Owner | ✅ |
| 订阅用户（Marketplace） | ❌ |
| 未登录用户 | ❌ |

- 「导出知识库」按钮**仅对 Owner 渲染**（在 `collection-header.tsx` 中用 `collection.user === currentUser.id` 判断）
- 后端通过查询 `Collection.user == user_id` 做权限校验，非 Owner 返回 `403`

---

## 4. 系统架构

### 整体流程

```
用户点击「导出知识库」
        │
        ▼
前端弹出确认对话框
        │ 点击「开始导出」
        ▼
POST /api/v1/collections/{id}/export
        │
        ├─► 校验 Owner 权限（非 Owner → 403）
        ├─► 检查并发任务数（同一用户 > 3 → 429）
        ├─► 创建 ExportTask（status=PENDING）
        └─► 触发 Celery 任务 export_collection_task.delay(task_id)
        │
        ▼ 202 Accepted: { export_task_id, status: "PENDING" }
        │
前端切换为进度对话框，每 2 秒轮询
GET /api/v1/export-tasks/{task_id}
        │
        ▼ status=COMPLETED
前端显示「下载 ZIP」按钮
        │
        ▼
GET /api/v1/export-tasks/{task_id}/download
（后端从对象存储读取 ZIP，StreamingResponse 流式返回）
```

### Celery Worker 处理流程（`config/export_tasks.py`）

```
1. 更新 ExportTask.status → PROCESSING
2. 列举对象存储 user-{user_id}/{collection_id}/ 下所有对象（list_objects_by_prefix）
3. 创建本地临时目录 /tmp/export_{task_id}/
4. 并发下载所有文件（最多 5 个并发，ThreadPoolExecutor）
   progress = downloaded / total * 85
5. 从数据库查文档列表，生成 manifest.json → /tmp/export_{task_id}/
   progress → 90%
6. 打包 ZIP（ZIP_DEFLATED）→ /tmp/export_{task_id}.zip
   progress → 95%
7. 上传 ZIP 到对象存储 exports/user-{user_id}/export_{task_id}.zip
   progress → 98%
8. 清理本地临时文件
9. 更新 ExportTask：
   status=COMPLETED, progress=100, file_size, gmt_completed, gmt_expires=now()+7d
   （失败时：status=FAILED, error_message=<traceback>）
```

---

## 5. 数据库

### `export_task` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | VARCHAR(24) | PK，格式 `export` + random_id() |
| `user` | VARCHAR(256) | 用户 ID |
| `collection_id` | VARCHAR(24) | 所属知识库 |
| `status` | VARCHAR(32) | 见下表 |
| `progress` | INTEGER | 0–100 |
| `message` | TEXT | 展示给用户的进度文字 |
| `error_message` | TEXT | 失败时的错误详情 |
| `object_store_path` | TEXT | ZIP 在对象存储的路径 |
| `file_size` | BIGINT | ZIP 大小（字节） |
| `gmt_created` | TIMESTAMP | |
| `gmt_updated` | TIMESTAMP | |
| `gmt_completed` | TIMESTAMP | |
| `gmt_expires` | TIMESTAMP | 创建后 7 天 |

### 状态枚举

| 状态 | 说明 | 可下载 |
|------|------|--------|
| `PENDING` | 等待 Worker 处理 | ❌ |
| `PROCESSING` | 正在打包中 | ❌ |
| `COMPLETED` | 打包完成 | ✅ |
| `FAILED` | 打包失败 | ❌ |
| `EXPIRED` | ZIP 已被清理 | ❌ |

```
PENDING → PROCESSING → COMPLETED
                    └→ FAILED
COMPLETED / FAILED → EXPIRED（7 天后定时任务）
```

---

## 6. API

API 定义的源文件：
- Schema：`sapilot/api/components/schemas/export.yaml`
- 路径：`sapilot/api/paths/export.yaml`
- 注册：`sapilot/api/openapi.yaml`

修改 API 后需运行：
```bash
make generate-models          # 重新生成 sapilot/schema/view_models.py
make generate-frontend-sdk    # 重新生成 web/src/api/**
```

### 接口列表

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| `POST` | `/api/v1/collections/{collection_id}/export` | 创建导出任务 | Owner Only |
| `GET` | `/api/v1/export-tasks/{task_id}` | 查询任务状态 | 任务创建者 |
| `GET` | `/api/v1/export-tasks/{task_id}/download` | 下载 ZIP | 任务创建者 |

### POST /collections/{collection_id}/export

**Response 202**
```json
{ "export_task_id": "export6f918baaa28e0180", "status": "PENDING", "progress": 0 }
```

**错误码**

| 场景 | HTTP |
|------|------|
| 非 Owner | 403 |
| 集合不存在 | 404 |
| 并发任务超限（>3） | 429 |

### GET /export-tasks/{task_id}

**处理中**
```json
{ "export_task_id": "...", "status": "PROCESSING", "progress": 58, "message": "Downloading files: 87 / 150" }
```

**完成**
```json
{
  "export_task_id": "...", "status": "COMPLETED", "progress": 100,
  "download_url": "/api/v1/export-tasks/.../download",
  "file_size": 8388608,
  "gmt_expires": "2026-03-11T10:01:30Z"
}
```

### GET /export-tasks/{task_id}/download

流式返回 ZIP 文件，`Content-Disposition: attachment; filename="{title}_export_{date}.zip"`。

---

## 7. 前端

### 入口

`web/src/app/workspace/collections/[collectionId]/collection-header.tsx`

Owner 的操作下拉菜单中：

```
┌──────────────────────┐
│  发布至市场           │
│  导出知识库  ← 新增   │
│  ─────────────────── │
│  删除知识库           │
└──────────────────────┘
```

### 组件：`CollectionExport`

路径：`web/src/components/collections/export-dialog.tsx`

组件内部实现四个状态的对话框状态机：

```
confirm → processing → completed
                   └→ failed → confirm（点击「重试」）
```

- 使用自动生成的 SDK 方法调用接口：
  - `apiClient.defaultApi.createExportTask({ collectionId })`
  - `apiClient.defaultApi.getExportTask({ taskId })`（每 2 秒轮询一次）
- 下载时直接使用 `download_url` 字段（指向 download 接口）
- 进度对话框期间禁止关闭（屏蔽 ESC 和点击外部）

### i18n

翻译键均以 `export_knowledge_base_` 为前缀，定义在：
- `web/src/i18n/en-US/page_collections.json`
- `web/src/i18n/zh-CN/page_collections.json`

---

## 8. 性能与限制

| 限制项 | 值 |
|--------|---|
| 每用户最大并发导出任务数 | 3 |
| Worker 内并发文件下载数 | 5（ThreadPoolExecutor） |
| 导出文件保留时间 | 7 天 |

---

## 9. 相关文件索引

### 新增文件

| 文件 | 说明 |
|------|------|
| `sapilot/api/components/schemas/export.yaml` | API Schema 定义（源文件） |
| `sapilot/api/paths/export.yaml` | API 路径定义（源文件） |
| `sapilot/db/models.py` | 新增 `ExportTask` 模型和 `ExportTaskStatus` 枚举 |
| `sapilot/migration/versions/20260304120000-a1b2c3d4e5f6.py` | 数据库迁移 |
| `sapilot/service/export_service.py` | 导出业务逻辑 |
| `sapilot/views/export.py` | FastAPI 路由（3 个接口） |
| `config/export_tasks.py` | Celery 异步打包任务 |
| `web/src/components/collections/export-dialog.tsx` | 导出对话框组件 |
| `docs/zh-CN/design/pending-review/collection_knowledge_export_design.md` | 本文档 |

### 修改的文件

| 文件 | 修改内容 |
|------|---------|
| `sapilot/objectstore/base.py` | 新增 `list_objects_by_prefix` 抽象方法 |
| `sapilot/objectstore/local.py` | 实现 `list_objects_by_prefix` |
| `sapilot/objectstore/s3.py` | 实现 `list_objects_by_prefix` |
| `sapilot/api/openapi.yaml` | 注册新增的 3 个路径 |
| `sapilot/schema/view_models.py` | 自动生成，含 `ExportTaskResponse` |
| `sapilot/app.py` | 注册 `export_router` |
| `config/celery.py` | 注册 `config.export_tasks` 模块 |
| `web/src/api/**` | 自动生成的前端 SDK |
| `web/src/app/workspace/collections/[collectionId]/collection-header.tsx` | 接入导出按钮 |
| `web/src/i18n/en-US/page_collections.json` | 新增翻译键 |
| `web/src/i18n/zh-CN/page_collections.json` | 新增翻译键 |
