#!/usr/bin/env sh
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_ROOT"

BACKUP_DIR="${BACKUP_DIR:-backups}"
SERVICE_NAME="${SERVICE_NAME:-db}"
COMPOSE_FILES="${COMPOSE_FILES:-docker-compose.yml}"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
OUTPUT_FILE="${1:-$BACKUP_DIR/postgres-$TIMESTAMP.dump}"
CONTAINER_FILE="/tmp/postgres-backup-$TIMESTAMP.dump"

mkdir -p "$BACKUP_DIR"

set -- $COMPOSE_FILES
COMPOSE_ARGS=""
for file in "$@"; do
  COMPOSE_ARGS="$COMPOSE_ARGS -f $file"
done

docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" sh -lc \
  "pg_dump -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -Fc -f \"$CONTAINER_FILE\""

CONTAINER_ID=$(docker compose $COMPOSE_ARGS ps -q "$SERVICE_NAME")
docker cp "$CONTAINER_ID:$CONTAINER_FILE" "$OUTPUT_FILE"
docker compose $COMPOSE_ARGS exec -T "$SERVICE_NAME" rm -f "$CONTAINER_FILE"

echo "Backup created: $OUTPUT_FILE"
