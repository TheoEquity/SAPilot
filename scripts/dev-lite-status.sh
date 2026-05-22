#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"

show_process() {
  local name="$1"
  local pid_file="$RUN_DIR/$name.pid"

  if [ ! -f "$pid_file" ]; then
    printf '%s\n' "$name: 未启动"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" >/dev/null 2>&1; then
    printf '%s\n' "$name: 运行中，PID=$pid"
  else
    printf '%s\n' "$name: PID 文件存在，进程已退出"
  fi
}

printf '%s\n' "应用进程状态"
show_process backend
show_process celery
show_process frontend

printf '%s\n' ""
printf '%s\n' "Docker 容器状态"
if command -v docker-compose >/dev/null 2>&1; then
  cd "$ROOT_DIR"
  docker-compose -f docker-compose.yml ps postgres redis qdrant es || true
else
  printf '%s\n' "当前环境缺少 docker-compose，无法展示容器状态。"
fi
