# Swagger 与 ReDoc

启动 `app/` 中的 API 后访问：

- [Swagger UI](http://localhost:8000/docs)
- [ReDoc](http://localhost:8000/redoc)
- [OpenAPI JSON](http://localhost:8000/openapi.json)

接口契约由 `app/aperag/views/` 的 FastAPI 路由和 `app/aperag/schema/` 的 Python 模型生成。Swagger 是 API 自带的维护界面，不需要单独复制一份业务后端。离线导出文件写入 `runtime/work/openapi/`。
