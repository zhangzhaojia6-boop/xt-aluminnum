#!/usr/bin/env sh
set -eu

DRY_RUN=0
BACKUP_FILE=""
TARGET_DATABASE=""

for arg in "$@"; do
  case "$arg" in
    --dry-run|--check-only)
      DRY_RUN=1
      ;;
    --help|-h)
      echo "用法: $0 <backup-file> [target-database] [--dry-run]"
      exit 0
      ;;
    -*)
      echo "不支持的参数: $arg" >&2
      echo "用法: $0 <backup-file> [target-database] [--dry-run]" >&2
      exit 1
      ;;
    *)
      if [ -z "$BACKUP_FILE" ]; then
        BACKUP_FILE="$arg"
      elif [ -z "$TARGET_DATABASE" ]; then
        TARGET_DATABASE="$arg"
      else
        echo "不支持的参数: $arg" >&2
        echo "用法: $0 <backup-file> [target-database] [--dry-run]" >&2
        exit 1
      fi
      ;;
  esac
done

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: scripts/restore_db.sh <backup-file> [target-database]" >&2
  exit 1
fi

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_ROOT"

TARGET_DATABASE="${TARGET_DATABASE:-aluminum_bypass_restore_check}"
SERVICE_NAME="${SERVICE_NAME:-db}"
COMPOSE_FILES="${COMPOSE_FILES:-docker-compose.yml docker-compose.prod.yml}"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
CONTAINER_FILE="/tmp/postgres-restore-$TIMESTAMP.dump"
COMPOSE_ARGS=""
CONTAINER_ID=""

for compose_file in $COMPOSE_FILES; do
  if [ ! -f "$compose_file" ]; then
    echo "未检测到 ${compose_file}，请在项目根目录执行恢复脚本并确保 compose 文件存在。" >&2
    exit 1
  fi
done

if [ ! -f ".env" ]; then
  echo "未检测到 .env，请先在项目根目录准备 .env 后再执行恢复脚本。" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "未检测到 docker 命令，请先安装 Docker 后再执行恢复脚本。" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose 不可用，请先安装并启用 Docker Compose Plugin（docker compose）后再执行恢复脚本。" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon 未启动，请先启动 Docker 服务后再执行恢复脚本。" >&2
  exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo "备份文件不存在: $BACKUP_FILE" >&2
  echo "请先执行 ./scripts/backup_db.sh 生成备份，或检查传入路径。" >&2
  exit 1
fi

if [ ! -s "$BACKUP_FILE" ]; then
  echo "备份文件为空: $BACKUP_FILE" >&2
  echo "请重新执行 ./scripts/backup_db.sh 生成有效备份后再恢复。" >&2
  exit 1
fi

case "$TARGET_DATABASE" in
  *[!A-Za-z0-9_]*)
    echo "Target database name can only contain letters, digits, and underscores." >&2
    exit 1
    ;;
esac

set -- $COMPOSE_FILES
for file in "$@"; do
  COMPOSE_ARGS="$COMPOSE_ARGS -f $file"
done

cleanup_restore_tmp() {
  if [ -n "${CONTAINER_ID:-}" ]; then
    docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" rm -f "$CONTAINER_FILE" >/dev/null 2>&1 || true
  fi
}
trap cleanup_restore_tmp EXIT

CONTAINER_ID=$(docker compose $COMPOSE_ARGS ps -q "$SERVICE_NAME")
if [ -z "$CONTAINER_ID" ]; then
  echo "数据库服务未运行: $SERVICE_NAME" >&2
  echo "请先执行 ./scripts/deploy_trial.sh，再进行恢复校验。" >&2
  exit 1
fi

POSTGRES_DB=$(docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" printenv POSTGRES_DB | tr -d '\r')
if [ -n "$POSTGRES_DB" ] && [ "$TARGET_DATABASE" = "$POSTGRES_DB" ]; then
  echo "恢复目标库不能与生产库同名: $TARGET_DATABASE" >&2
  echo "请使用独立的恢复校验库名（例如 aluminum_bypass_restore_check）。" >&2
  exit 1
fi

case "$TARGET_DATABASE" in
  postgres | template0 | template1)
    echo "恢复目标库不能使用系统保留库名: $TARGET_DATABASE" >&2
    echo "请使用独立的恢复校验库名（例如 aluminum_bypass_restore_check）。" >&2
    exit 1
    ;;
esac

if [ "$DRY_RUN" -eq 1 ]; then
  echo "DRY RUN：仅做恢复前置预检，不执行数据库恢复。"
  echo "将执行:"
  echo " - 检查备份文件: $BACKUP_FILE"
  echo " - 检查 compose 文件可用性"
  echo " - 检查 .env 与 docker/compose/docker daemon"
  echo " - 检查数据库服务运行中"
  echo " - 检查目标库合法性: $TARGET_DATABASE"
  echo " - 预检恢复命令: docker compose ... psql/pg_restore"
  exit 0
fi

docker cp "$BACKUP_FILE" "$CONTAINER_ID:$CONTAINER_FILE"

POSTGRES_USER=$(docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" printenv POSTGRES_USER | tr -d '\r')

if ! docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" sh -lc "pg_restore -l \"$CONTAINER_FILE\" >/dev/null 2>&1"; then
  echo "备份文件格式校验失败，无法读取: $BACKUP_FILE" >&2
  echo "请重新执行 ./scripts/backup_db.sh 生成新备份后再恢复。" >&2
  exit 1
fi

docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" \
  psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $TARGET_DATABASE WITH (FORCE);"
docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" \
  psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $TARGET_DATABASE;"
docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" \
  pg_restore -U "$POSTGRES_USER" -d "$TARGET_DATABASE" --no-owner --no-privileges "$CONTAINER_FILE"
docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" \
  psql -U "$POSTGRES_USER" -d "$TARGET_DATABASE" -t -A -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';"

echo "Restore completed into database: $TARGET_DATABASE"
