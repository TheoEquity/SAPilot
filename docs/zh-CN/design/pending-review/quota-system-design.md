# SAPilot 配额系统设计文档

> 分类：待核对设计；已补本轮源码核对。核对日期：2026 年 10 月 29 日。
> 状态：配额表、管理 API 和资源消费/释放已有实现；不能把资源数量限制等同请求限流，原子性和错误响应的概括需收窄。
> 使用边界：下文原稿保留供追溯；先读本次核对，再按源码与运行证据判断。静态存在不等于已验收，本次不构成设计定案或实施批准。见[核对总览](README.md)。

<!-- source-audit:begin -->
## 本次源码核对（2026 年 10 月 29 日）

**结论：** 配额表、管理 API 和资源消费/释放已有实现；不能把资源数量限制等同请求限流，原子性和错误响应的概括需收窄。

核对范围为本文主要架构、接口、配置、处理流程及完成状态声明；不是逐行示例、全量安全或性能审计。依据为当前工作区源码（含既有未提交改动），详见[基线与状态说明](README.md#核对口径)。本轮未启动服务、调用模型、执行数据库或后台任务。

| 原文范围 / 声明 | 判定 | 当前源码与使用限制 | 源码依据 |
| --- | --- | --- | --- |
| 四类配额、默认值与初始化 | 仍适用（静态） | UserQuota 存储 limit/usage；默认兜底为 Collection 10、文档总数 1000、每库文档 100、Bot 5，可由 config 中 system_default_quotas 覆盖；注册后初始化配额，默认 Bot 创建跳过配额检查。实际用户限额需读数据库确认。 | [aperag/db/models.py](../../../../aperag/db/models.py)<br />[aperag/service/quota_service.py](../../../../aperag/service/quota_service.py)<br />[aperag/views/auth.py](../../../../aperag/views/auth.py) |
| 消费、释放与事务 | 仍适用但有边界 | check_and_consume_quota / release_quota 对已有配额行使用 SELECT FOR UPDATE，可复用调用方 session；Collection、Bot 和文档路径有调用。每库文档上限另行计数检查，不能由用户配额行锁推定所有入口和所有粒度均无竞态；本轮未做并发测试。 | [aperag/service/quota_service.py](../../../../aperag/service/quota_service.py)<br />[aperag/service/collection_service.py](../../../../aperag/service/collection_service.py)<br />[aperag/service/bot_service.py](../../../../aperag/service/bot_service.py)<br />[aperag/service/document_service.py](../../../../aperag/service/document_service.py) |
| 管理 API、管理员边界与页面 | 仍适用（静态） | /quotas、自身读取、管理员查他人/更新/重算、/system/default-quotas 及管理前端存在，路由依赖 required_user 并检查 ADMIN。实际配额前端已拆在个人、用户管理及系统配置页面。 | [aperag/views/quota.py](../../../../aperag/views/quota.py)<br />[web/src/app/workspace/quotas/page.tsx](../../../../web/src/app/workspace/quotas/page.tsx)<br />[web/src/app/admin/users/user-quota-action.tsx](../../../../web/src/app/admin/users/user-quota-action.tsx)<br />[web/src/app/admin/configuration/quota-settings.tsx](../../../../web/src/app/admin/configuration/quota-settings.tsx) |
| 安全、错误格式与所有操作线程安全声明 | 部分过时 / 需收窄 | 资源数量配额不等于按时间窗口限制 HTTP 请求速率。QuotaExceededException 对这些资源映射 403；但重算路由将权限检查放在通用 except 内，静态看该拒绝会被包装为 500，不能承诺所有管理拒绝均返回文中的 403；未修改代码。 | [aperag/views/quota.py](../../../../aperag/views/quota.py)<br />[aperag/exceptions.py](../../../../aperag/exceptions.py)<br />[aperag/service/quota_service.py](../../../../aperag/service/quota_service.py) |
| 配额历史、动态调整、告警、缓存等增强 | 规划 | 原文明确列于未来增强；本轮核对的配额 Service、模型及路由未见这些完整机制，不能升级为已交付。管理员手工修改上限已存在，不等于按策略自动动态调整。 | [aperag/service/quota_service.py](../../../../aperag/service/quota_service.py)<br />[aperag/db/models.py](../../../../aperag/db/models.py) |
| 并发一致性、计数修复与环境默认值 | 待运行验证 | 未操作实际数据库或触发重算；删除、重复上传、失败回滚等场景的最终计数一致性和当前用户限额仍待验证。 | [aperag/service/quota_service.py](../../../../aperag/service/quota_service.py)<br />[aperag/service/document_service.py](../../../../aperag/service/document_service.py) |

以下保留原稿；其中旧的“已实现”“待完成”、接口示例和效果数字，以本节标注的适用范围为准。未单列的示例不代表已逐行验证。

---

## 原文（保留记录）
<!-- source-audit:end -->

## 目录
- [概述](#概述)
- [架构设计](#架构设计)
- [数据模型](#数据模型)
- [API 设计](#api-设计)
- [服务层](#服务层)
- [前端实现](#前端实现)
- [安全与授权](#安全与授权)
- [错误处理](#错误处理)
- [使用模式](#使用模式)
- [未来增强](#未来增强)

## 概述

SAPilot 配额系统是一个全面的资源管理解决方案，旨在控制和监控平台上的用户资源消耗。它提供对各种资源类型（包括文档集合、文档和机器人）的细粒度控制，确保公平使用并防止系统滥用。

### 核心特性

- **多资源配额管理**：支持不同配额类型（文档集合、文档、机器人）
- **实时使用量跟踪**：自动跟踪当前资源使用情况
- **系统默认配置**：为新用户提供集中式默认配额设置
- **管理控制**：仅限管理员的配额管理和用户搜索功能
- **原子操作**：线程安全的配额消费和释放操作
- **灵活的 API 设计**：支持单个和批量操作的 RESTful API

### 支持的配额类型

1. **max_collection_count**：用户可以创建的最大文档集合数量
2. **max_document_count**：所有文档集合中文档的总最大数量
3. **max_document_count_per_collection**：单个文档集合中的最大文档数量
4. **max_bot_count**：用户可以创建的最大机器人数量（不包括系统默认机器人）

## 架构设计

配额系统采用分层架构模式：

```
┌─────────────────────────────────────────────────────────────┐
│                    前端层                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   用户配额      │  │   管理面板      │  │   系统配置   │ │
│  │     视图        │  │     视图        │  │     视图     │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                      API 层                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   配额 API      │  │   管理 API      │  │   系统 API   │ │
│  │  (quotas.yaml)  │  │                 │  │              │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                    服务层                                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              QuotaService                               │ │
│  │  • get_user_quotas()                                   │ │
│  │  • check_and_consume_quota()                           │ │
│  │  • release_quota()                                     │ │
│  │  • recalculate_user_usage()                            │ │
│  │  • update_user_quota()                                 │ │
│  │  • get/update_system_default_quotas()                  │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                   数据层                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   UserQuota     │  │   ConfigModel   │  │   相关表     │ │
│  │     表          │  │     表          │  │              │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 数据模型

### UserQuota 表

存储用户配额信息的核心表：

```sql
CREATE TABLE user_quota (
    user VARCHAR(256) NOT NULL,           -- 用户标识符
    key VARCHAR(256) NOT NULL,            -- 配额类型键
    quota_limit INTEGER NOT NULL DEFAULT 0, -- 最大允许使用量
    current_usage INTEGER NOT NULL DEFAULT 0, -- 当前使用量
    gmt_created TIMESTAMP WITH TIME ZONE NOT NULL,
    gmt_updated TIMESTAMP WITH TIME ZONE NOT NULL,
    gmt_deleted TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (user, key)
);
```

**关键字段：**
- `user`：用户标识符（用户表的外键）
- `key`：配额类型（如 'max_collection_count'、'max_document_count'）
- `quota_limit`：此配额类型的最大允许使用量
- `current_usage`：当前使用量的实时跟踪
- 复合主键确保每个用户每种配额类型只有一条记录

### ConfigModel 表

存储系统级配置，包括默认配额：

```sql
CREATE TABLE config (
    key VARCHAR(256) PRIMARY KEY,         -- 配置键
    value TEXT NOT NULL,                  -- JSON 配置值
    gmt_created TIMESTAMP WITH TIME ZONE NOT NULL,
    gmt_updated TIMESTAMP WITH TIME ZONE NOT NULL,
    gmt_deleted TIMESTAMP WITH TIME ZONE
);
```

**系统默认配额配置：**
```json
{
  "max_collection_count": 10,
  "max_document_count": 1000,
  "max_document_count_per_collection": 100,
  "max_bot_count": 5
}
```

### 相关表

配额系统与多个其他表集成以进行使用量计算：

- **Collection**：用于计算用户文档集合数量（status != 'DELETED'）
- **Document**：用于计算跨文档集合的文档数量
- **Bot**：用于计算用户机器人数量（不包括系统默认机器人）

## API 设计

### RESTful 端点

#### 1. 获取用户配额
```http
GET /quotas?user_id={user_id}&search={search_term}
```

**功能：**
- 当前用户配额（无参数）
- 仅限管理员按 ID、用户名或邮箱搜索用户
- 支持多个搜索结果

**响应类型：**
- `UserQuotaInfo`：单个用户配额信息
- `UserQuotaList`：多个用户（搜索结果）

#### 2. 更新用户配额
```http
PUT /quotas/{user_id}
```

**功能：**
- 仅限管理员操作
- 支持单个和批量配额更新
- 原子事务处理

**请求体：**
```json
{
  "max_collection_count": 20,
  "max_document_count": 2000,
  "max_bot_count": 10
}
```

#### 3. 重新计算使用量
```http
POST /quotas/{user_id}/recalculate
```

**功能：**
- 仅限管理员操作
- 从数据库重新计算实际使用量
- 原子更新 current_usage 字段

#### 4. 系统默认配额
```http
GET /system/default-quotas
PUT /system/default-quotas
```

**功能：**
- 仅限管理员操作
- 集中式默认配额管理
- 应用于新用户初始化

### OpenAPI 规范

API 遵循 OpenAPI 3.0 规范，包含：
- 全面的模式定义
- 详细的错误响应映射
- 参数验证规则
- 安全要求（仅限管理员操作）

## 服务层

### QuotaService 类

`QuotaService` 类提供配额管理的核心业务逻辑：

#### 关键方法

**1. 配额消费（线程安全）**
```python
async def check_and_consume_quota(
    self, 
    user_id: str, 
    quota_type: str, 
    amount: int = 1, 
    session=None
) -> None:
    """
    使用 SELECT FOR UPDATE 原子地检查和消费配额
    如果配额将被超出则抛出 QuotaExceededException
    """
```

**2. 配额释放**
```python
async def release_quota(
    self, 
    user_id: str, 
    quota_type: str, 
    amount: int = 1, 
    session=None
) -> None:
    """
    释放配额（减少使用量）并保证事务安全
    """
```

**3. 使用量重新计算**
```python
async def recalculate_user_usage(self, user_id: str) -> Dict[str, int]:
    """
    从相关表重新计算实际使用量：
    - 文档集合：COUNT(*) WHERE user=? AND status!='DELETED'
    - 文档：通过与文档集合的 JOIN 进行 COUNT(*)
    - 机器人：COUNT(*) WHERE user=? AND title!='Default Agent Bot'
    """
```

**4. 用户初始化**
```python
async def initialize_user_quotas(self, user_id: str) -> None:
    """
    从系统配置为新用户初始化默认配额
    """
```

#### 事务管理

- **数据库操作**：所有配额操作都使用异步数据库事务
- **原子更新**：SELECT FOR UPDATE 防止竞态条件
- **会话处理**：支持独立和嵌套事务

## 前端实现

### React 组件架构

前端配额管理实现为一个全面的 React 组件，具有：

#### 关键功能

**1. 多标签界面（仅限管理员）**
- 用户配额管理
- 系统默认配置

**2. 用户搜索与选择**
- 按用户名、邮箱或用户 ID 实时搜索
- 多结果处理与选择界面
- 清除搜索功能

**3. 内联表格编辑**
- 配额限制的编辑模式切换
- 实时验证
- 批量保存操作
- 取消/恢复功能

**4. 进度可视化**
- 使用率进度条
- 颜色编码状态（正常/警告/危险）
- 百分比计算

**5. 管理操作**
- 配额重新计算
- 系统默认配额管理
- 用户特定配额更新

#### 组件结构

```typescript
interface QuotaInfo {
  quota_type: string;
  quota_limit: number;
  current_usage: number;
  remaining: number;
}

interface UserQuotaInfo {
  user_id: string;
  username: string;
  email?: string;
  role: string;
  quotas: QuotaInfo[];
}
```

#### 状态管理

- **本地状态**：UI 交互的组件级状态
- **API 集成**：带有加载状态的直接 API 调用
- **错误处理**：带有国际化的用户友好错误消息

## 安全与授权

### 基于角色的访问控制

**普通用户：**
- 仅查看自己的配额
- 只读访问
- 无管理功能

**管理员用户：**
- 完整的配额管理功能
- 用户搜索和选择
- 系统配置访问权限
- 配额重新计算权限

### API 安全

- **身份验证**：所有配额端点都需要身份验证
- **授权**：管理操作的管理员角色验证
- **输入验证**：全面的参数验证
- **速率限制**：通过配额系统本身隐式实现

## 错误处理

### 异常层次结构

```python
class QuotaExceededException(BusinessException):
    """
    当配额消费将超出限制时抛出
    映射到适当的 HTTP 状态码：
    - 文档集合配额：403 Forbidden
    - 文档配额：403 Forbidden  
    - 机器人配额：403 Forbidden
    """
```

### 错误响应格式

```json
{
  "error_code": "COLLECTION_QUOTA_EXCEEDED",
  "code": 1103,
  "message": "已达到max_collection_count的配额限制。当前使用量: 10/10",
  "details": {
    "quota_type": "max_collection_count",
    "quota_limit": 10,
    "current_usage": 10,
    "quota_exceeded": true
  }
}
```

### 前端错误处理

- **国际化消息**：多语言错误显示
- **用户友好反馈**：清晰的操作指导
- **优雅降级**：回退 UI 状态

## 使用模式

### 资源创建流程

```python
# 示例：创建新的文档集合
async def create_collection(user_id: str, collection_data: dict):
    async with database_transaction() as session:
        # 1. 原子地检查和消费配额
        await quota_service.check_and_consume_quota(
            user_id, 
            'max_collection_count', 
            session=session
        )
        
        # 2. 创建资源
        collection = Collection(**collection_data)
        session.add(collection)
        
        # 3. 提交事务（配额和资源一起）
        await session.commit()
```

### 资源删除流程

```python
# 示例：删除文档集合
async def delete_collection(user_id: str, collection_id: str):
    async with database_transaction() as session:
        # 1. 标记资源为已删除
        collection.status = 'DELETED'
        collection.gmt_deleted = utc_now()
        
        # 2. 释放配额
        await quota_service.release_quota(
            user_id, 
            'max_collection_count', 
            session=session
        )
        
        # 3. 提交事务
        await session.commit()
```

### 管理操作

```python
# 示例：批量配额更新
await quota_service.update_user_quota(
    user_id="user123",
    quota_updates={
        "max_collection_count": 20,
        "max_document_count": 2000,
        "max_bot_count": 10
    }
)
```

## 未来增强

### 计划功能

1. **配额历史跟踪**
   - 历史配额变更
   - 使用分析
   - 趋势分析

2. **动态配额调整**
   - 基于使用量的自动调整
   - 临时配额增加
   - 基于时间的配额

3. **高级监控**
   - 实时配额警报
   - 使用预测
   - 容量规划

4. **集成增强**
   - 外部配额提供商
   - 多租户支持
   - API 速率限制集成

### 技术改进

1. **性能优化**
   - 配额缓存策略
   - 批量操作
   - 数据库索引改进

2. **可扩展性**
   - 分布式配额管理
   - 微服务架构
   - 事件驱动更新

3. **可观测性**
   - 详细指标收集
   - 配额操作跟踪
   - 性能监控

---

*本文档提供了 SAPilot 配额系统设计和实现的全面概述。有关具体实现细节，请参考相应模块中的源代码。*
