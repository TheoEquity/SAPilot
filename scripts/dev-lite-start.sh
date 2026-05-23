#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$RUN_DIR/logs"

mkdir -p "$RUN_DIR" "$LOG_DIR"

check_command() {
  local command_name="$1"
  local hint="$2"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf '%s\n' "缺少命令: $command_name"
    printf '%s\n' "$hint"
    exit 1
  fi
}

start_process() {
  local name="$1"
  local workdir="$2"
  local command_text="$3"
  local pid_file="$RUN_DIR/$name.pid"
  local log_file="$LOG_DIR/$name.log"

  if [ -f "$pid_file" ]; then
    local existing_pid
    existing_pid="$(cat "$pid_file")"
    if kill -0 "$existing_pid" >/dev/null 2>&1; then
      printf '%s\n' "$name 已在运行，PID=$existing_pid"
      return
    fi
  fi

  nohup bash -lc "cd \"$workdir\" && $command_text" >"$log_file" 2>&1 &
  local new_pid=$!
  printf '%s' "$new_pid" > "$pid_file"
  printf '%s\n' "$name 已启动，PID=$new_pid，日志: $log_file"
}

printf '%s\n' "准备启动 SAPilot 低资源开发环境"

REGISTRY_VALUE="${REGISTRY:-apecloud-registry.cn-zhangjiakou.cr.aliyuncs.com}"

check_command docker "请先安装 Docker Desktop，并确认 docker 命令可用。"
# Check for docker compose v2 (preferred) or docker-compose v1
if ! docker compose version >/dev/null 2>&1; then
  if ! command -v docker-compose >/dev/null 2>&1; then
    printf '%s\n' "缺少 Docker Compose: 请先安装 Docker Compose v2 或 v1。"
    exit 1
  fi
fi
check_command bash "请先安装 bash。"
check_command git "请先安装 git。"
check_command yarn "请先安装 Node.js 20+ 和 yarn。"

if ! command -v uv >/dev/null 2>&1; then
  check_command pip "请先安装 Python 3.11+ 和 pip，用于安装 uv。"
  pip install uv
fi

cd "$ROOT_DIR"

if [ ! -f "$ROOT_DIR/.env" ]; then
  cp "$ROOT_DIR/envs/env.dev-lite.template" "$ROOT_DIR/.env"
  printf '%s\n' "已创建 .env，使用低资源模板。"
fi

printf '%s\n' "启动 4 个基础设施容器..."
REGISTRY="$REGISTRY_VALUE" make compose-infra

printf '%s\n' "准备 Python 开发环境..."
make venv

printf '%s\n' "安装 Python 依赖..."
uv sync

printf '%s\n' "安装前端依赖..."
cd "$ROOT_DIR/web"
yarn install
cd "$ROOT_DIR"

printf '%s\n' "执行数据库迁移..."
.venv/bin/python -m alembic -c aperag/alembic.ini upgrade head

printf '%s\n' "启动后端、Celery 和前端热重载服务..."
start_process "backend" "$ROOT_DIR" "source .venv/bin/activate && make run-backend"
start_process "celery" "$ROOT_DIR" "source .venv/bin/activate && make run-celery"
start_process "frontend" "$ROOT_DIR/web" "yarn dev"

printf '%s\n' ""
printf '%s\n' "启动完成。"
printf '%s\n' "前端地址: http://localhost:3000"
printf '%s\n' "后端地址: http://localhost:8000"
printf '%s\n' "API 文档: http://localhost:8000/docs"
printf '%s\n' "查看状态: bash scripts/dev-lite-status.sh"
printf '%s\n' "停止服务: bash scripts/dev-lite-stop.sh"
