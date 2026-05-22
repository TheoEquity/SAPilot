#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"

stop_process() {
  local name="$1"
  local pid_file="$RUN_DIR/$name.pid"

  if [ ! -f "$pid_file" ]; then
    printf '%s\n' "$name: 未启动"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid"
    printf '%s\n' "$name: 已停止，PID=$pid"
  else
    printf '%s\n' "$name: 进程已退出，PID=$pid"
  fi
}

printf '%s\n' "停止应用进程..."
stop_process frontend
stop_process celery
stop_process backend

printf '%s\n' ""
printf '%s\n' "停止 4 个基础设施容器..."
if command -v docker-compose >/dev/null 2>&1; then
  cd "$ROOT_DIR"
  docker-compose -f docker-compose.yml stop postgres redis qdrant es
else
  printf '%s\n' "当前环境缺少 docker-compose，请手动停止 Docker 容器。"
fi
