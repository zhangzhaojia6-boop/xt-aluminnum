#!/usr/bin/env bash
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$BACKEND_DIR/.." && pwd)"
DB_DIR="$REPO_DIR/.tmp/e2e"
DB_PATH="$DB_DIR/e2e.sqlite3"

mkdir -p "$DB_DIR"
rm -f "$DB_PATH"

export APP_ENV=e2e
export DATABASE_URL="sqlite:///$DB_PATH"
export SECRET_KEY="${SECRET_KEY:-e2e-secret-key-change-before-production-2026}"
export INIT_ADMIN_USERNAME="${PLAYWRIGHT_USERNAME:-${INIT_ADMIN_USERNAME:-admin}}"
export INIT_ADMIN_PASSWORD="${PLAYWRIGHT_PASSWORD:-${INIT_ADMIN_PASSWORD:-E2eAdmin#2026}}"
export INIT_ADMIN_NAME="${INIT_ADMIN_NAME:-E2E Admin}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:4173,http://127.0.0.1:4173}"
export PRODUCTION_CORS_ORIGINS="$CORS_ORIGINS"
export MES_ADAPTER="${MES_ADAPTER:-null}"
export DINGTALK_ENABLED=false
export WORKFLOW_ENABLED=false
export LLM_ENABLED=false

cd "$BACKEND_DIR"
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
