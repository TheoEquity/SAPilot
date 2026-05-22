# 本地轻量部署说明

这份说明适合完全不懂开发的业务同事。

目标效果：
- 启动 4 个基础设施容器：PostgreSQL、Redis、Qdrant、Elasticsearch
- 启动后端服务
- 启动 Celery 后台任务服务
- 启动前端页面
- 支持后端自动重载和前端热更新

## 你需要准备的内容

请先在电脑里安装下面 4 个软件：

1. Docker Desktop
2. Git
3. Python 3.11 或更高版本
4. Node.js 20 或更高版本

安装完成后，重启一次电脑。

## 第一次启动

在项目根目录打开终端，复制执行下面这条命令：

```bash
bash scripts/dev-lite-start.sh
```

第一次启动会自动完成这些动作：
- 创建低资源 `.env` 配置
- 启动 4 个 Docker 容器
- 安装 Python 运行依赖
- 安装前端依赖
- 初始化数据库
- 启动前后端和 Celery

第一次启动时间通常会比较长，因为需要下载镜像和安装依赖。

## 启动成功后怎么打开系统

浏览器访问：

```text
前端页面：http://localhost:3000
后端接口：http://localhost:8000
接口文档：http://localhost:8000/docs
```

## 查看当前状态

```bash
bash scripts/dev-lite-status.sh
```

这个命令会显示：
- 前端是否在运行
- 后端是否在运行
- Celery 是否在运行
- 4 个 Docker 容器是否正常

## 停止系统

```bash
bash scripts/dev-lite-stop.sh
```

这个命令会停止：
- 前端
- 后端
- Celery
- 4 个基础设施容器

## 常见问题

### 1. 提示缺少 `docker` 或 `docker-compose`

请先安装 Docker Desktop，然后重新打开终端。

### 2. 提示缺少 `yarn`

请先安装 Node.js 20+。安装完成后重新打开终端再执行脚本。

### 3. 页面打不开

先执行：

```bash
bash scripts/dev-lite-status.sh
```

如果状态异常，再查看日志目录：

```text
.run/logs/backend.log
.run/logs/celery.log
.run/logs/frontend.log
```

### 4. 电脑内存紧张

当前脚本已经是低资源模式：
- Elasticsearch 堆内存 512m
- Celery 并发 4
- 数据库连接池 4/4
- 默认不安装 NVIDIA、CUDA、MinerU、Neo4j 相关依赖

这套配置适合 8GB 内存、20GB 磁盘的本地机器。
