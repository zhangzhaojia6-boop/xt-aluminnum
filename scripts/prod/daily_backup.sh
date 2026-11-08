#!/usr/bin/env bash
# 生产每日备份：数据库 + 上传附件。校验通过才落盘，只清理 backups/daily 里超过 14 天的文件。
set -euo pipefail
umask 077

APP_ROOT="${APP_ROOT:-/srv/aluminum-bypass}"
DAILY_DIR="${DAILY_DIR:-$APP_ROOT/backups/daily}"
KEEP_DAYS="${KEEP_DAYS:-14}"
MIN_FREE_MB="${MIN_FREE_MB:-2048}"
ENV_FILE="$APP_ROOT/backend/.env"
STAMP=$(date +%Y%m%d-%H%M%S)

read_env() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2-; }

free_mb=$(df -Pm "$APP_ROOT" | awk 'NR==2 {print $4}')
if [ "$free_mb" -lt "$MIN_FREE_MB" ]; then
  echo "备份中止：剩余空间 ${free_mb}MB，低于 ${MIN_FREE_MB}MB" >&2
  exit 1
fi

mkdir -p "$DAILY_DIR"
db_url=$(read_env DATABASE_URL | sed -E 's#^postgresql\+[a-z0-9]+://#postgresql://#')
upload_dir=$(read_env UPLOAD_DIR)
upload_dir="${upload_dir:-./uploads}"
cd "$APP_ROOT/backend"

db_tmp="$DAILY_DIR/.db-$STAMP.tmp"
files_tmp="$DAILY_DIR/.uploads-$STAMP.tmp"
trap 'rm -f "$db_tmp" "$files_tmp"' EXIT

pg_dump "$db_url" -Fc -f "$db_tmp"
pg_restore -l "$db_tmp" > /dev/null
tar -czf "$files_tmp" -C "$(dirname "$upload_dir")" "$(basename "$upload_dir")"
tar -tzf "$files_tmp" > /dev/null

mv "$db_tmp" "$DAILY_DIR/db-$STAMP.dump"
mv "$files_tmp" "$DAILY_DIR/uploads-$STAMP.tar.gz"
find "$DAILY_DIR" -maxdepth 1 -type f \( -name 'db-*.dump' -o -name 'uploads-*.tar.gz' \) -mtime +"$KEEP_DAYS" -delete

echo "备份完成 db=$(du -h "$DAILY_DIR/db-$STAMP.dump" | cut -f1) uploads=$(du -h "$DAILY_DIR/uploads-$STAMP.tar.gz" | cut -f1) 剩余=${free_mb}MB"
