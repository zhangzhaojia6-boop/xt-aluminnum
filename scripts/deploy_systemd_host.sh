#!/usr/bin/env sh
set -eu

# HOST-SYSTEMD ONLY: updates the current ECS host-managed deployment.

DRY_RUN=0
SKIP_PULL=1
REQUIRE_EXTERNAL=0
PARSED_BASE_URL=""

usage() {
  cat <<'EOF'
用法: scripts/deploy_systemd_host.sh [http://host-or-domain] [--pull] [--skip-pull] [--dry-run] [--require-external]

说明:
- 仅用于当前 ECS 宿主机 systemd 形态：nginx + aluminum-bypass.service + 宿主机 PostgreSQL。
- 默认不执行 git pull；加 --pull 时执行 git pull --ff-only origin main。
- --require-external 会在 readyz 通过后继续检查 MES / Workflow / LLM / 钉钉 / 应用连接正式联通。
- --dry-run / --check-only 仅打印计划，不执行备份、迁移、构建或服务重启。
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run|--check-only)
      DRY_RUN=1
      shift
      ;;
    --pull)
      SKIP_PULL=0
      shift
      ;;
    --skip-pull)
      SKIP_PULL=1
      shift
      ;;
    --require-external)
      REQUIRE_EXTERNAL=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    -*)
      echo "不支持的参数: $1" >&2
      usage
      exit 1
      ;;
    *)
      if [ -n "$PARSED_BASE_URL" ]; then
        echo "不支持的参数: $1" >&2
        usage
        exit 1
      fi
      PARSED_BASE_URL="$1"
      shift
      ;;
  esac
done

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
BACKEND_ENV_FILE="$BACKEND_DIR/.env"
SERVICE_NAME="${SERVICE_NAME:-aluminum-bypass}"
NGINX_SERVICE_NAME="${NGINX_SERVICE_NAME:-nginx}"
BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups}"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
BACKUP_FILE="${BACKUP_FILE:-$BACKUP_DIR/systemd-predeploy-$TIMESTAMP.dump}"
BACKEND_BASE_URL="${PARSED_BASE_URL:-${BACKEND_BASE_URL:-http://127.0.0.1:8000}}"
READY_RETRIES="${READY_RETRIES:-24}"
READY_INTERVAL_SECONDS="${READY_INTERVAL_SECONDS:-5}"
ADMIN_LOGIN_PASSWORD="${ADMIN_LOGIN_PASSWORD:-${DEPLOY_ADMIN_LOGIN_PASSWORD:-}}"

cd "$REPO_ROOT"

require_command() {
  command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "未检测到命令: $command_name" >&2
    exit 1
  fi
}

get_env_value() {
  key="$1"
  awk -F= -v key="$key" '
    $1 == key {
      sub(/^[^=]*=[[:space:]]*/, "", $0)
      gsub(/^"|"$/, "", $0)
      gsub(/^'"'"'|'"'"'$/, "", $0)
      print $0
      exit
    }
  ' "$BACKEND_ENV_FILE" | tr -d '\r'
}

require_env_value() {
  key="$1"
  value="$(get_env_value "$key" | tr -d '\r')"
  if [ -z "$value" ]; then
    echo "${key} 未配置，请先检查 $BACKEND_ENV_FILE" >&2
    exit 1
  fi
  if echo "$value" | grep -q "CHANGE_ME"; then
    echo "${key} 仍为占位值，请先替换 $BACKEND_ENV_FILE 中对应值（不允许 CHANGE_ME）" >&2
    exit 1
  fi
}

is_weak_secret_key() {
  value="$1"
  case "$value" in
    ""|\
    "change-this-secret-key-in-production-min-32-chars"|\
    "replace-with-a-strong-secret-key-at-least-32-characters"|\
    "CHANGE_ME_SECRET_KEY_FOR_DEPLOYMENT_ONLY_32CHARS_MIN"|\
    "dev-only-secret-key-change-before-production-2026")
      return 0
      ;;
  esac
  if [ "${#value}" -lt 32 ]; then
    return 0
  fi
  return 1
}

is_weak_admin_password() {
  value="$1"
  case "$value" in
    ""|\
    "Admin@123456"|\
    "CHANGE_ME_ADMIN_PASSWORD_FOR_DEPLOYMENT"|\
    "DevAdmin#ChangeMe2026")
      return 0
      ;;
  esac
  if [ "${#value}" -lt 12 ]; then
    return 0
  fi
  return 1
}

normalize_pg_dump_url() {
  value="$1"
  case "$value" in
    postgresql+*://*)
      driverless="${value#postgresql+}"
      printf 'postgresql://%s\n' "${driverless#*://}"
      ;;
    postgres+*://*)
      driverless="${value#postgres+}"
      printf 'postgres://%s\n' "${driverless#*://}"
      ;;
    *)
      printf '%s\n' "$value"
      ;;
  esac
}

if [ ! -d "$BACKEND_DIR" ]; then
  echo "未检测到后端目录: $BACKEND_DIR" >&2
  exit 1
fi

if [ ! -d "$FRONTEND_DIR" ]; then
  echo "未检测到前端目录: $FRONTEND_DIR" >&2
  exit 1
fi

if [ ! -f "$BACKEND_ENV_FILE" ]; then
  echo "未检测到后端生产配置: $BACKEND_ENV_FILE" >&2
  exit 1
fi

if [ "$DRY_RUN" -eq 0 ]; then
  require_command pg_dump
  require_command pg_restore
  require_command curl
  require_command systemctl
  require_command npm
  if [ "$SKIP_PULL" -eq 0 ]; then
    require_command git
  fi
fi

SQLALCHEMY_DB_URL="${DATABASE_URL:-$(get_env_value DATABASE_URL)}"
if [ -z "$SQLALCHEMY_DB_URL" ]; then
  echo "DATABASE_URL 未配置，请检查 $BACKEND_ENV_FILE" >&2
  exit 1
fi
DB_URL="$(normalize_pg_dump_url "$SQLALCHEMY_DB_URL")"

APP_ENV_VALUE="$(get_env_value APP_ENV | tr -d '\r')"
if [ "$APP_ENV_VALUE" != "production" ]; then
  echo "部署 systemd host 前必须设置 APP_ENV=production" >&2
  exit 1
fi

require_env_value SECRET_KEY
require_env_value INIT_ADMIN_PASSWORD

SECRET_KEY_VALUE="$(get_env_value SECRET_KEY | tr -d '\r')"
if is_weak_secret_key "$SECRET_KEY_VALUE"; then
  echo "SECRET_KEY 过弱：长度必须 >= 32，且不能使用默认/示例值。请先更新 $BACKEND_ENV_FILE 后再部署。" >&2
  exit 1
fi

INIT_ADMIN_PASSWORD_VALUE="$(get_env_value INIT_ADMIN_PASSWORD | tr -d '\r')"
if is_weak_admin_password "$INIT_ADMIN_PASSWORD_VALUE"; then
  echo "INIT_ADMIN_PASSWORD 过弱：长度必须 >= 12，且不能使用默认/示例值。请先更新 $BACKEND_ENV_FILE 后再部署。" >&2
  exit 1
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo "HOST-SYSTEMD ONLY 检查模式"
  echo "REPO_ROOT=$REPO_ROOT"
  echo "BACKEND_DIR=$BACKEND_DIR"
  echo "FRONTEND_DIR=$FRONTEND_DIR"
  echo "BACKEND_ENV_FILE=$BACKEND_ENV_FILE"
  echo "SERVICE_NAME=$SERVICE_NAME"
  echo "NGINX_SERVICE_NAME=$NGINX_SERVICE_NAME"
  echo "BACKUP_FILE=$BACKUP_FILE"
  echo "BACKEND_BASE_URL=$BACKEND_BASE_URL"
  echo "READY_RETRIES=$READY_RETRIES"
  echo "READY_INTERVAL_SECONDS=$READY_INTERVAL_SECONDS"
  echo "REQUIRE_EXTERNAL=$REQUIRE_EXTERNAL"
  echo "执行计划:"
  echo " - 可选同步: git pull --ff-only origin main"
  echo " - 备份数据库并用 pg_restore -l 校验"
  echo " - 安装后端依赖，执行 Alembic 和基础数据初始化"
  if [ -n "$ADMIN_LOGIN_PASSWORD" ]; then
    echo " - 管理员登录密码: 通过 create_admin.py --reset-password 单独重置（不输出密码）"
  else
    echo " - 管理员账号: 保持已有密码，仅确保账号权限契约"
  fi
  echo " - 构建前端"
  echo " - 重启 systemd 服务并检查 /readyz hard_gate_passed=true"
  if [ "$REQUIRE_EXTERNAL" -eq 1 ]; then
    echo " - 检查正式外部联通: MES / Workflow / LLM / 钉钉 / 应用连接"
  fi
  exit 0
fi

if [ "$SKIP_PULL" -eq 0 ]; then
  git pull --ff-only origin main
else
  echo "跳过 git pull（如需同步远端，请加 --pull）"
fi

mkdir -p "$BACKUP_DIR"
pg_dump "$DB_URL" -Fc -f "$BACKUP_FILE"
pg_restore -l "$BACKUP_FILE" >/dev/null

cd "$BACKEND_DIR"
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/python scripts/init_master_data.py
.venv/bin/python scripts/init_real_master_data.py
if [ -n "$ADMIN_LOGIN_PASSWORD" ]; then
  .venv/bin/python scripts/create_admin.py --password "$ADMIN_LOGIN_PASSWORD" --reset-password
else
  .venv/bin/python scripts/create_admin.py
fi

cd "$FRONTEND_DIR"
npm ci --include=dev
npm rebuild
VITE_API_BASE_URL="${VITE_API_BASE_URL:-/api/v1}" npm run build

systemctl restart "$SERVICE_NAME"
systemctl is-active --quiet "$SERVICE_NAME"
systemctl is-active --quiet "$NGINX_SERVICE_NAME"

ATTEMPT=1
READY_PAYLOAD=""
while :; do
  READY_RESPONSE="$(curl -sS --max-time 10 -w '\n%{http_code}' "$BACKEND_BASE_URL/readyz" 2>/dev/null || true)"
  READY_STATUS="$(printf '%s\n' "$READY_RESPONSE" | tail -n 1)"
  READY_PAYLOAD="$(printf '%s\n' "$READY_RESPONSE" | sed '$d')"

  if [ "$READY_STATUS" = "200" ] &&
    printf '%s\n' "$READY_PAYLOAD" | grep -Eq '"hard_gate_passed"[[:space:]]*:[[:space:]]*true'; then
    break
  fi

  if [ "$ATTEMPT" -ge "$READY_RETRIES" ]; then
    echo "readyz 未通过：在 ${READY_RETRIES} 次重试后仍未返回 HTTP 200 且 hard_gate_passed=true" >&2
    echo "$READY_PAYLOAD" >&2
    exit 1
  fi

  echo "等待服务就绪（第 ${ATTEMPT}/${READY_RETRIES} 次未通过，${READY_INTERVAL_SECONDS}s 后重试）..." >&2
  ATTEMPT=$((ATTEMPT + 1))
  sleep "$READY_INTERVAL_SECONDS"
done

if [ "$REQUIRE_EXTERNAL" -eq 1 ]; then
  cd "$BACKEND_DIR"
  .venv/bin/python scripts/check_statistics_module_ready.py --json
fi

echo "systemd host deployment updated: $BACKEND_BASE_URL"
