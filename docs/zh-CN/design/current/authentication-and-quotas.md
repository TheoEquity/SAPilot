# SAPilot 当前认证与资源配额

> 状态：当前说明，依据 2026 年 10 月 29 日源码静态核对整理。实际登录联通、权限覆盖与并发计数仍待运行验证。

## 身份如何进入业务接口

认证基于 FastAPI-Users。当前登录校验密码后签发 JWT，并写入 `session` HttpOnly Cookie；有效期为 `86400` 秒，SameSite 为 `lax`。`optional_user` 先尝试 Cookie，再尝试 Bearer API Key；`required_user` 在没有有效用户时拒绝访问。

源码中的 CookieTransport 为 `secure=False`，自定义登录的 set_cookie 也未指定 secure。密码校验走 `password_helper.verify_and_update`，此处不能把具体哈希算法、安全强度或生产 Cookie 配置写成已保证行为。依据：[认证实现](../../../../aperag/views/auth.py)。

Google 和 GitHub OAuth 路由按配置条件启用；后端使用 `oauth_redirect_url` 加 `/google` 或 `/github`，默认根地址为 `http://localhost:3000/auth/callback`。前端承接路径是 `auth/callback/[provider]`。实际 Provider 控制台配置及 TLS 代理须按部署验证。依据：[应用配置](../../../../aperag/config.py)、[OAuth 回调页面](../../../../web/src/app/auth/callback/[provider]/page.tsx)。

User、OAuthAccount、ApiKey 及 ADMIN/RW/RO 角色模型存在；首次用户管理员和邀请注册也有对应分支。角色枚举不能证明所有 CRUD 路由都已按 RO/RW 完成授权。市场读取另有边界，见[市场与导出](marketplace-and-export.md)。

## 资源配额与默认值

`UserQuota` 按用户和资源类型记录 `quota_limit`、`current_usage`。系统默认值可由 `config.system_default_quotas` 覆盖；配置缺失时的代码兜底如下，实际用户限额需读取数据库。

| 配额键 | 默认兜底 | 检查对象 |
| --- | --- | --- |
| `max_collection_count` | 10 | 用户的知识库数量 |
| `max_document_count` | 1000 | 用户的文档总数 |
| `max_document_count_per_collection` | 100 | 单知识库文档数量 |
| `max_bot_count` | 5 | 非系统默认 Bot 数量 |

注册后初始化用户配额；系统默认 Bot 创建时跳过配额检查。依据：[QuotaService](../../../../aperag/service/quota_service.py)、[注册与初始化](../../../../aperag/views/auth.py)、[数据模型](../../../../aperag/db/models.py)。

创建 Collection、Bot 和上传文档的路径调用配额服务，删除路径释放对应配额。消费与释放对已有用户配额行使用 `SELECT FOR UPDATE`，并可复用业务事务的 session。单库上限另做计数检查，不能由这些锁推定所有入口、粒度和并发条件都没有竞态。对象存储与数据库也不因此成为一个原子事务。

依据：[CollectionService](../../../../aperag/service/collection_service.py)、[BotService](../../../../aperag/service/bot_service.py)、[DocumentService](../../../../aperag/service/document_service.py)。

## 配置入口与错误边界

以下业务接口均位于 `/api/v1` 下：

| 入口 | 当前行为 |
| --- | --- |
| `GET /quotas` | 默认读取自己；查他人或搜索用户要求 ADMIN |
| `PUT /quotas/{user_id}` | 管理员更新用户上限 |
| `POST /quotas/{user_id}/recalculate` | 管理员重算使用量 |
| `GET/PUT /system/default-quotas` | 管理员读取或修改系统默认值 |

前端入口分布在[个人配额页](../../../../web/src/app/workspace/quotas/page.tsx)、[用户配额操作](../../../../web/src/app/admin/users/user-quota-action.tsx)与[系统配额配置](../../../../web/src/app/admin/configuration/quota-settings.tsx)。

资源数量配额不是 HTTP 请求速率限制。对应 `QuotaExceededException` 映射为 403；但当前重算路由的权限异常会进入通用异常包装，静态看可转为 500，因此不能统一承诺所有管理拒绝都返回 403。依据：[配额路由](../../../../aperag/views/quota.py)、[异常定义](../../../../aperag/exceptions.py)。

配额历史、策略自动调整和告警等尚属[未实现规划](../planned/README.md)。真实配额、失败回滚后的计数、并发创建与重算一致性仍需运行核对。

原始材料：[认证](../pending-review/authentication.md)、[配额](../pending-review/quota-system-design.md)。返回[当前说明目录](README.md)。
