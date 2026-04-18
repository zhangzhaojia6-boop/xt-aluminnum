#!/usr/bin/env sh
set -eu

if [ "${1:-}" = "" ]; then
  echo "Usage: scripts/restore_db.sh <backup-file> [target-database]" >&2
  exit 1
fi

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_ROOT"

BACKUP_FILE="$1"
TARGET_DATABASE="${2:-aluminum_bypass_restore_check}"
SERVICE_NAME="${SERVICE_NAME:-db}"
COMPOSE_FILES="${COMPOSE_FILES:-docker-compose.yml}"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
CONTAINER_FILE="/tmp/postgres-restore-$TIMESTAMP.dump"

case "$TARGET_DATABASE" in
  *[!A-Za-z0-9_]*)
    echo "Target database name can only contain letters, digits, and underscores." >&2
    exit 1
    ;;
esac

set -- $COMPOSE_FILES
COMPOSE_ARGS=""
for file in "$@"; do
  COMPOSE_ARGS="$COMPOSE_ARGS -f $file"
done

CONTAINER_ID=$(docker compose $COMPOSE_ARGS ps -q "$SERVICE_NAME")
docker cp "$BACKUP_FILE" "$CONTAINER_ID:$CONTAINER_FILE"

POSTGRES_USER=$(docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" printenv POSTGRES_USER | tr -d '\r')

docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" \
  psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $TARGET_DATABASE WITH (FORCE);"
docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" \
  psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $TARGET_DATABASE;"
docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" \
  pg_restore -U "$POSTGRES_USER" -d "$TARGET_DATABASE" --no-owner --no-privileges "$CONTAINER_FILE"
docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" \
  psql -U "$POSTGRES_USER" -d "$TARGET_DATABASE" -t -A -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';"
docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" rm -f "$CONTAINER_FILE"

echo "Restore completed into database: $TARGET_DATABASE"
