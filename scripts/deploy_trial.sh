#!/usr/bin/env sh
set -eu

DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --dry-run|--check-only)
      DRY_RUN=1
      ;;
    *)
      echo "不支持的参数: $arg" >&2
      echo "用法: $0 [--dry-run]" >&2
      exit 1
      ;;
  esac
done

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_ROOT"

for compose_file in docker-compose.yml docker-compose.prod.yml; do
  if [ ! -f "$compose_file" ]; then
    echo "未检测到 ${compose_file}，请在项目根目录执行部署脚本并确保 compose 文件存在。" >&2
    exit 1
  fi
done

if ! command -v docker >/dev/null 2>&1; then
  echo "未检测到 docker 命令，请先安装 Docker 后再执行部署脚本。" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose 不可用，请先安装并启用 Docker Compose Plugin（docker compose）。" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon 未启动，请先启动 Docker 服务后再执行部署脚本。" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "未检测到 curl 命令。请先安装 curl（健康检查脚本依赖）后再执行部署脚本。" >&2
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "未检测到 .env。请先运行：python scripts/generate_env.py --app-env production --domain <your-domain>" >&2
  echo "如仅本地快速试跑，也可先复制 .env.example 为 .env 并按需修改。" >&2
  exit 1
fi

if [ ! -s "ssl/cert.pem" ]; then
  echo "未检测到 SSL 证书：ssl/cert.pem（文件不存在或为空）。请先将证书放到项目根目录 ssl/cert.pem 后再部署。" >&2
  exit 1
fi

if ! grep -q "BEGIN CERTIFICATE" "ssl/cert.pem"; then
  echo "ssl/cert.pem 内容可能错误：未检测到 BEGIN CERTIFICATE。请确认证书文件内容正确后再部署。" >&2
  exit 1
fi

if [ ! -s "ssl/key.pem" ]; then
  echo "未检测到 SSL 私钥：ssl/key.pem（文件不存在或为空）。请先将私钥放到项目根目录 ssl/key.pem 后再部署。" >&2
  exit 1
fi

if ! grep -q "BEGIN" "ssl/key.pem" || ! grep -q "PRIVATE KEY" "ssl/key.pem"; then
  echo "ssl/key.pem 内容可能错误：未检测到私钥完整标记（BEGIN / PRIVATE KEY）。请确认私钥文件内容正确后再部署。" >&2
  exit 1
fi

get_env_value() {
  key="$1"
  awk -F= -v key="$key" '
    $1 == key {
      sub(/^[^=]*=[[:space:]]*/, "", $0)
      print $0
      exit
    }
  ' .env
}

require_env_value() {
  key="$1"
  value="$(get_env_value "$key" | tr -d '\r')"
  if [ -z "$value" ]; then
    echo "${key} 未配置，请先检查 .env" >&2
    exit 1
  fi
  if echo "$value" | grep -q "CHANGE_ME"; then
    echo "${key} 仍为占位值，请先替换 .env 中对应值（不允许 CHANGE_ME）" >&2
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

APP_ENV_VALUE="$(get_env_value APP_ENV | tr -d '\r')"
if [ "$APP_ENV_VALUE" != "production" ]; then
  echo "部署 quick-cloud 前必须设置 APP_ENV=production" >&2
  exit 1
fi

echo "环境预检完成。"

TRIAL_BASE_URL="${TRIAL_BASE_URL:-${BASE_URL:-https://localhost}}"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "DRY RUN：仅做预检，不执行发布动作。"
  echo "将执行:"
  echo " - docker compose -f docker-compose.yml -f docker-compose.prod.yml config"
  echo " - docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build"
  echo " - docker compose -f docker-compose.yml -f docker-compose.prod.yml ps"
  echo " - ./scripts/check_trial_stack.sh \"$TRIAL_BASE_URL\""
  exit 0
fi

require_env_value POSTGRES_PASSWORD
require_env_value SECRET_KEY
require_env_value INIT_ADMIN_PASSWORD
require_env_value CORS_ORIGINS

SECRET_KEY_VALUE="$(get_env_value SECRET_KEY | tr -d '\r')"
if is_weak_secret_key "$SECRET_KEY_VALUE"; then
  echo "SECRET_KEY 过弱：长度必须 >= 32，且不能使用默认/示例值。请先更新 .env 后再部署。" >&2
  exit 1
fi

INIT_ADMIN_PASSWORD_VALUE="$(get_env_value INIT_ADMIN_PASSWORD | tr -d '\r')"
if is_weak_admin_password "$INIT_ADMIN_PASSWORD_VALUE"; then
  echo "INIT_ADMIN_PASSWORD 过弱：长度必须 >= 12，且不能使用默认/示例值。请先更新 .env 后再部署。" >&2
  exit 1
fi

docker compose -f docker-compose.yml -f docker-compose.prod.yml config
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

if ! ./scripts/check_trial_stack.sh "$TRIAL_BASE_URL"; then
  echo "健康检查失败，输出关键诊断信息"
  docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
  docker compose -f docker-compose.yml -f docker-compose.prod.yml logs backend --tail 160
  docker compose -f docker-compose.yml -f docker-compose.prod.yml logs nginx --tail 160
  exit 1
fi

echo "快速试跑健康检查通过: $TRIAL_BASE_URL"
