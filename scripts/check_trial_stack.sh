#!/usr/bin/env sh
set -eu

DRY_RUN=0
PARSED_BASE_URL=""

for arg in "$@"; do
  case "$arg" in
    --dry-run|--check-only)
      DRY_RUN=1
      ;;
    --help|-h)
      echo "用法: $0 [https://domain] [--dry-run]"
      exit 0
      ;;
    -*)
      echo "不支持的参数: $arg" >&2
      echo "用法: $0 [https://domain] [--dry-run]" >&2
      exit 1
      ;;
    *)
      if [ -n "$PARSED_BASE_URL" ]; then
        echo "不支持的参数: $arg" >&2
        echo "用法: $0 [https://domain] [--dry-run]" >&2
        exit 1
      fi
      PARSED_BASE_URL="$arg"
      ;;
  esac
done

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_ROOT"

BASE_URL="${PARSED_BASE_URL:-${BASE_URL:-https://localhost}}"
READY_RETRIES="${READY_RETRIES:-24}"
READY_INTERVAL_SECONDS="${READY_INTERVAL_SECONDS:-5}"

for compose_file in docker-compose.yml docker-compose.prod.yml; do
  if [ ! -f "$compose_file" ]; then
    echo "未检测到 ${compose_file}，请在项目根目录执行健康检查脚本并确保 compose 文件存在。" >&2
    exit 1
  fi
done

if [ ! -f ".env" ]; then
  echo "未检测到 .env，请先在项目根目录准备 .env 后再执行健康检查脚本。" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "未检测到 docker 命令，请先安装 Docker 后再执行健康检查脚本。" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose 不可用，请先安装并启用 Docker Compose Plugin（docker compose）后再执行健康检查脚本。" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon 未启动，请先启动 Docker 服务后再执行健康检查脚本。" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "未检测到 curl 命令，请先安装 curl 后再执行健康检查脚本。" >&2
  exit 1
fi

echo "运行环境检查通过。"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "DRY RUN：仅做预检，不发起网络探测。"
  echo "将检查:"
  echo " - /healthz 与 /readyz 的重试策略（默认 ${READY_RETRIES} 次 x ${READY_INTERVAL_SECONDS}s）"
  echo " - /、/entry、/manage/factory 路由访问与 id=\"app\" 校验"
  echo " - /api/v1/auth/login 入口可达性规则"
  echo " - db/backend/nginx 运行态"
  echo " - 运行命令: docker compose -f docker-compose.yml -f docker-compose.prod.yml ps"
  exit 0
fi

ATTEMPT=1
while :; do
  if curl -kfsS --max-time 10 "$BASE_URL/healthz" >/dev/null 2>&1 &&
    READY_PAYLOAD="$(curl -kfsS --max-time 10 "$BASE_URL/readyz" 2>/dev/null)" &&
    printf '%s\n' "$READY_PAYLOAD" | grep -Eq '"hard_gate_passed"[[:space:]]*:[[:space:]]*true'; then
    break
  fi

  if [ "$ATTEMPT" -ge "$READY_RETRIES" ]; then
    echo "健康检查失败：在 ${READY_RETRIES} 次重试后仍未就绪（/healthz 或 /readyz 未通过 hard_gate_passed=true）" >&2
    if [ -n "${READY_PAYLOAD:-}" ]; then
      echo "最后一次 readyz 响应: $READY_PAYLOAD" >&2
    fi
    exit 1
  fi

  echo "等待服务就绪（第 ${ATTEMPT}/${READY_RETRIES} 次未通过，${READY_INTERVAL_SECONDS}s 后重试）..." >&2
  ATTEMPT=$((ATTEMPT + 1))
  sleep "$READY_INTERVAL_SECONDS"
done

HOME_PAYLOAD="$(curl -kfsSL --max-time 15 "$BASE_URL/")"
if ! printf '%s\n' "$HOME_PAYLOAD" | grep -q 'id="app"'; then
  echo "首页可访问性检查失败：返回内容未包含前端挂载锚点（id=\"app\"）" >&2
  echo "首页响应: $HOME_PAYLOAD" >&2
  exit 1
fi

for ROUTE in entry manage/factory; do
  ROUTE_URL="${BASE_URL}/${ROUTE}"
  if ! ROUTE_PAYLOAD="$(curl -kfsSL --max-time 15 "$ROUTE_URL" 2>/dev/null)"; then
    echo "路由可访问性检查失败：无法访问 ${ROUTE_URL}，请检查前端服务是否可达" >&2
    exit 1
  fi
  if ! printf '%s\n' "$ROUTE_PAYLOAD" | grep -q 'id="app"'; then
    echo "路由可访问性检查失败：${ROUTE_URL} 返回内容未包含前端挂载锚点（id=\"app\"）" >&2
    echo "${ROUTE} 响应内容: $ROUTE_PAYLOAD" >&2
    exit 1
  fi
done

AUTH_LOGIN_STATUS="$(curl -ks --max-time 10 -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/auth/login")"
if [ "$AUTH_LOGIN_STATUS" = "404" ] || [ "$AUTH_LOGIN_STATUS" = "000" ] || [ "$AUTH_LOGIN_STATUS" -ge 500 ]; then
  echo "API 入口可达性检查失败：/api/v1/auth/login 返回 ${AUTH_LOGIN_STATUS}，请检查 API 入口是否可达或服务异常" >&2
  exit 1
fi

docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

RUNNING_SERVICES="$(docker compose -f docker-compose.yml -f docker-compose.prod.yml ps --services --status running)"

for service in db backend nginx; do
  if ! printf '%s\n' "$RUNNING_SERVICES" | grep -qx "$service"; then
    echo "服务未处于运行状态: $service" >&2
    echo "当前运行服务: ${RUNNING_SERVICES:-<none>}" >&2
    exit 1
  fi
done
