# 维护工具

业务服务和镜像构建文件在 `../app/`；这里保存维护工具的入口与部署配置。

- [Swagger / ReDoc](swagger/README.md)：由运行中的 FastAPI 提供，浏览器访问 [Swagger](http://localhost:8000/docs) 或 [ReDoc](http://localhost:8000/redoc)。
- [Langfuse](langfuse/README.md)：独立的追踪与模型调用观测服务，默认 [localhost:3300](http://localhost:3300)。

私有配置在 `../runtime/private/`，运行日志在 `../runtime/logs/`；不复制业务数据或原始模型输出到这里。
