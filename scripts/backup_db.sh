#!/usr/bin/env sh
set -eu

DRY_RUN=0

BACKUP_OUTPUT_FILE=""

for arg in "$@"; do
  case "$arg" in
    --dry-run|--check-only)
      DRY_RUN=1
      ;;
    --help|-h)
      echo "用法: $0 [backup-file] [--dry-run]"
      exit 0
      ;;
    -*)
      echo "不支持的参数: $arg" >&2
      echo "用法: $0 [backup-file] [--dry-run]" >&2
      exit 1
      ;;
    *)
      if [ -n "$BACKUP_OUTPUT_FILE" ]; then
        echo "不支持的参数: $arg" >&2
        echo "用法: $0 [backup-file] [--dry-run]" >&2
        exit 1
      fi
      BACKUP_OUTPUT_FILE="$arg"
      ;;
  esac
done

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_ROOT"

BACKUP_DIR="${BACKUP_DIR:-backups}"
SERVICE_NAME="${SERVICE_NAME:-db}"
COMPOSE_FILES="${COMPOSE_FILES:-docker-compose.yml docker-compose.prod.yml}"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
OUTPUT_FILE="${BACKUP_OUTPUT_FILE:-$BACKUP_DIR/postgres-$TIMESTAMP.dump}"
OUTPUT_DIR="$(dirname "$OUTPUT_FILE")"
CONTAINER_FILE="/tmp/postgres-backup-$TIMESTAMP.dump"
COMPOSE_ARGS=""
CONTAINER_ID=""

for compose_file in $COMPOSE_FILES; do
  if [ ! -f "$compose_file" ]; then
    echo "未检测到 ${compose_file}，请在项目根目录执行备份脚本并确保 compose 文件存在。" >&2
    exit 1
  fi
done

if [ ! -f ".env" ]; then
  echo "未检测到 .env，请先在项目根目录准备 .env 后再执行备份脚本。" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "未检测到 docker 命令，请先安装 Docker 后再执行备份脚本。" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose 不可用，请先安装并启用 Docker Compose Plugin（docker compose）后再执行备份脚本。" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon 未启动，请先启动 Docker 服务后再执行备份脚本。" >&2
  exit 1
fi

set -- $COMPOSE_FILES
for file in "$@"; do
  COMPOSE_ARGS="$COMPOSE_ARGS -f $file"
done

cleanup_backup_tmp() {
  if [ -n "${CONTAINER_ID:-}" ]; then
    docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" rm -f "$CONTAINER_FILE" >/dev/null 2>&1 || true
  fi
  if [ -f "$OUTPUT_FILE" ] && [ ! -s "$OUTPUT_FILE" ]; then
    rm -f "$OUTPUT_FILE" >/dev/null 2>&1 || true
  fi
}
trap cleanup_backup_tmp EXIT

if [ "$DRY_RUN" -eq 1 ]; then
  echo "DRY RUN：仅做备份前置预检，不执行数据库导出与拉取。"
  echo "将执行:"
  echo " - 预检输出路径: $OUTPUT_FILE"
  echo " - 检查 compose 文件可用性"
  echo " - 检查 .env 与 docker/compose/docker daemon"
  echo " - 检查数据库服务运行中"
  echo " - 仅输出将执行导出: docker compose ... exec pg_dump"
  echo " - 仅输出将执行格式校验和落盘验证"
  exit 0
fi

if ! mkdir -p "$OUTPUT_DIR"; then
  echo "无法创建备份目录: $OUTPUT_DIR" >&2
  echo "请检查路径权限后重试。" >&2
  exit 1
fi

CONTAINER_ID=$(docker compose $COMPOSE_ARGS ps -q "$SERVICE_NAME")
if [ -z "$CONTAINER_ID" ]; then
  echo "数据库服务未运行: $SERVICE_NAME" >&2
  echo "请先执行 ./scripts/deploy_trial.sh 再重试备份。" >&2
  exit 1
fi

docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" sh -lc \
  "pg_dump -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -Fc -f \"$CONTAINER_FILE\""

if ! docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" sh -lc "pg_restore -l \"$CONTAINER_FILE\" >/dev/null 2>&1"; then
  echo "备份格式校验失败，无法读取新生成的备份文件。" >&2
  echo "请检查数据库状态后重试备份。" >&2
  exit 1
fi

docker cp "$CONTAINER_ID:$CONTAINER_FILE" "$OUTPUT_FILE"

if [ ! -s "$OUTPUT_FILE" ]; then
  echo "备份文件为空或写入失败: $OUTPUT_FILE" >&2
  echo "请检查数据库状态与磁盘空间后重试。" >&2
  exit 1
fi

echo "Backup created: $OUTPUT_FILE"
