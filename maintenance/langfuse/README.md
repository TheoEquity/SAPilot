# 本地 Langfuse

在项目总目录执行：

```powershell
python maintenance/langfuse/setup.py
docker compose --env-file runtime/private/langfuse.env -f maintenance/langfuse/compose.yaml up -d
```

`setup.py` 只在凭据文件不存在时生成配置，不覆盖已有密钥。Compose 项目名固定为 `sapilot-langfuse`，沿用现有本地数据卷；迁移目录时不创建另一套监控数据。

服务入口：[http://localhost:3300](http://localhost:3300)。应用追踪接入配置保留在 `app/.env`，容器内访问宿主的地址见 `app/envs/docker.env.overrides`。

停止服务并保留数据：

```powershell
docker compose --env-file runtime/private/langfuse.env -f maintenance/langfuse/compose.yaml stop
```
