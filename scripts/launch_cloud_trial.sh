#!/usr/bin/env sh
set -eu

DRY_RUN=0
SKIP_AI=0
SKIP_ROLE_SMOKE=0
SKIP_PULL=1
PARSED_BASE_URL=""
PARSED_TARGET_DATE=""
EXTRA_GATE_ARGS=""

usage() {
  cat <<'EOF'
用法: scripts/launch_cloud_trial.sh [https://domain] [--date YYYY-MM-DD] [--pull] [--skip-pull] [--skip-ai] [--skip-role-smoke] [--dry-run]

说明:
- 默认不执行 git pull，避免意外覆盖本地改动。
- 加上 --pull 时先执行 git pull，再执行部署与上线闸门。
- --dry-run 仅打印将执行的命令，不实际触发部署和闸门探测。
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run|--check-only)
      DRY_RUN=1
      EXTRA_GATE_ARGS="$EXTRA_GATE_ARGS --check-only"
      shift
      ;;
    --skip-ai)
      SKIP_AI=1
      EXTRA_GATE_ARGS="$EXTRA_GATE_ARGS --skip-ai"
      shift
      ;;
    --skip-role-smoke)
      SKIP_ROLE_SMOKE=1
      EXTRA_GATE_ARGS="$EXTRA_GATE_ARGS --skip-role-smoke"
      shift
      ;;
    --date)
      if [ "$#" -lt 2 ]; then
        echo "参数错误：--date 需要 YYYY-MM-DD" >&2
        echo "用法: $0 [https://domain] [--date YYYY-MM-DD] [--pull] [--skip-pull] [--skip-ai] [--skip-role-smoke] [--dry-run]"
        exit 1
      fi
      PARSED_TARGET_DATE="$2"
      EXTRA_GATE_ARGS="$EXTRA_GATE_ARGS --date $2"
      shift 2
      ;;
    --pull)
      SKIP_PULL=0
      shift
      ;;
    --skip-pull)
      SKIP_PULL=1
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
cd "$REPO_ROOT"

BASE_URL="${PARSED_BASE_URL:-${TRIAL_BASE_URL:-${BASE_URL:-https://localhost}}}"
DATE_ARG="$([ -n "$PARSED_TARGET_DATE" ] && echo " --date $PARSED_TARGET_DATE" || true)"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "云端快速试跑（检查模式）"
  echo "BASE_URL=$BASE_URL"
  echo "执行计划:"
  echo "1) ./scripts/deploy_trial.sh --dry-run"
  echo "2) ./scripts/go_live_gate.sh $BASE_URL $DATE_ARG$EXTRA_GATE_ARGS"
  exit 0
fi

echo "开始一键试跑链路：$BASE_URL"

if [ "$SKIP_PULL" -eq 0 ]; then
  if [ -d ".git" ] && command -v git >/dev/null 2>&1; then
    echo "[1/3] git pull"
    git pull
  else
    echo "跳过 git pull：未检测到 .git 或 git 命令不可用。"
  fi
else
  echo "[1/3] 跳过 git pull（如需同步远端，请加 --pull）"
fi

echo "[2/3] 部署脚本校验与启动"
./scripts/deploy_trial.sh

echo "[3/3] 上线闸门总检"
./scripts/go_live_gate.sh "$BASE_URL" $DATE_ARG $EXTRA_GATE_ARGS

echo "一键链路完成，结果请参考 go_live_gate 输出。"

