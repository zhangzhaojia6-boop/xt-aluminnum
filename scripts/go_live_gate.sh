#!/usr/bin/env sh
set -eu

DRY_RUN=0
SKIP_AI=0
SKIP_ROLE_SMOKE=0
PARSED_BASE_URL=""
PARSED_TARGET_DATE=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run|--check-only)
      DRY_RUN=1
      shift
      ;;
    --skip-ai)
      SKIP_AI=1
      shift
      ;;
    --skip-role-smoke)
      SKIP_ROLE_SMOKE=1
      shift
      ;;
    --date)
      if [ "$#" -lt 2 ]; then
        echo "参数错误：--date 需要 YYYY-MM-DD" >&2
        echo "用法: $0 [https://domain] [--date YYYY-MM-DD] [--skip-ai] [--skip-role-smoke] [--dry-run]" >&2
        exit 1
      fi
      PARSED_TARGET_DATE="$2"
      shift 2
      ;;
    --help|-h)
      echo "用法: $0 [https://domain] [--date YYYY-MM-DD] [--skip-ai] [--skip-role-smoke] [--dry-run]"
      exit 0
      ;;
    -*)
      echo "不支持的参数: $1" >&2
      echo "用法: $0 [https://domain] [--date YYYY-MM-DD] [--skip-ai] [--skip-role-smoke] [--dry-run]" >&2
      exit 1
      ;;
    *)
      if [ -n "$PARSED_BASE_URL" ]; then
        echo "不支持的参数: $1" >&2
        echo "用法: $0 [https://domain] [--date YYYY-MM-DD] [--skip-ai] [--skip-role-smoke] [--dry-run]" >&2
        exit 1
      fi
      PARSED_BASE_URL="$1"
      shift
      ;;
  esac
done

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_ROOT"

# Ensure `python` command is available across environments (bash on Windows often only has python3).
if ! command -v python >/dev/null 2>&1; then
  if command -v python3 >/dev/null 2>&1; then
    python() {
      python3 "$@"
    }
  elif command -v py >/dev/null 2>&1; then
    python() {
      py -3 "$@"
    }
  else
    echo "未检测到 python/python3/py，请先安装 Python 后再执行上线闸门。" >&2
    exit 1
  fi
fi

BASE_URL="${PARSED_BASE_URL:-${BASE_URL:-https://localhost}}"
TARGET_DATE="${PARSED_TARGET_DATE:-$(date +%Y-%m-%d)}"

FAIL_COUNT=0
PASS_LINES=""
FAIL_LINES=""

add_pass() {
  PASS_LINES="${PASS_LINES}\n- [$1] $2"
}

add_fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  FAIL_LINES="${FAIL_LINES}\n- [$1] $2"
}

run_gate() {
  gate_code="$1"
  gate_name="$2"
  shift 2
  echo "[$gate_code] 开始：$gate_name"
  if "$@"; then
    add_pass "$gate_code" "$gate_name"
    echo "[$gate_code] 通过"
    return 0
  fi
  add_fail "$gate_code" "$gate_name"
  echo "[$gate_code] 失败"
  return 1
}

check_ai_runtime_live() {
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python - <<'PY'
from datetime import date
import json
from app.config import Settings
from app.schemas.assistant import AssistantImageRequestIn, AssistantQueryRequestIn
from app.services.assistant_service import build_assistant_image, run_assistant_live_probe, run_assistant_query
from app.services.leader_summary_service import build_best_effort_leader_summary

settings = Settings()
result = {
    'llm_enabled': bool(settings.LLM_ENABLED),
    'llm_api_base_set': bool(str(settings.LLM_API_BASE or '').strip()),
    'llm_key_set': bool(str(settings.LLM_API_KEY or '').strip()),
    'llm_model_ref_set': bool(str(getattr(settings, 'LLM_ENDPOINT_ID', '') or settings.LLM_MODEL or '').strip()),
    'query_mock': True,
    'image_mock': True,
    'live_probe_image_ok': False,
    'live_probe_overall_ok': False,
    'leader_source': 'deterministic',
    'error': None,
}

if not result['llm_enabled']:
    result['error'] = 'LLM_ENABLED=false'
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(2)

if not (result['llm_api_base_set'] and result['llm_key_set'] and result['llm_model_ref_set']):
    result['error'] = 'LLM config incomplete'
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(3)

try:
    query = run_assistant_query(
        AssistantQueryRequestIn(mode='answer', query='上线门禁探针：一句总结今日风险', surface='review_home'),
        settings=settings,
    )
    image = build_assistant_image(
        AssistantImageRequestIn(prompt='上线门禁探针：生成今日简报图', image_type='daily_briefing_card', surface='review_home'),
        settings=settings,
    )
    live_probe = run_assistant_live_probe(settings=settings)
    summary = build_best_effort_leader_summary(
        report_date=date.today(),
        report_data={
            'total_output_weight': 120.5,
            'energy_per_ton': 1.2,
            'total_electricity_kwh': 320.0,
            'reporting_rate': 0.95,
            'total_attendance': 32,
            'anomaly_summary': {'total': 1, 'digest': '待核实'},
            'yield_matrix_lane': {'quality_status': 'ready', 'company_total_yield': 97.1},
            'contract_lane': {'daily_contract_weight': 88.0},
            'inventory_lane': [{'storage_prepared': 10.0, 'storage_finished': 5.0, 'shipment_weight': 8.0, 'storage_inbound_area': 12.0}],
        },
        settings=settings,
    )
    result['query_mock'] = bool(query.mock)
    result['image_mock'] = bool(image.mock)
    result['live_probe_image_ok'] = bool(live_probe.image_probe_ok)
    result['live_probe_overall_ok'] = bool(live_probe.overall_ok)
    result['leader_source'] = str(summary.get('summary_source') or '')
except Exception as exc:  # noqa: BLE001
    result['error'] = f'{exc.__class__.__name__}: {exc}'
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(4)

image_ok = (not result['image_mock']) or result['live_probe_image_ok']
ok = (not result['query_mock']) and image_ok and result['leader_source'] == 'llm'
print(json.dumps(result, ensure_ascii=False))
raise SystemExit(0 if ok else 5)
PY
}

run_role_smoke_tests() {
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python -m pytest \
    tests/test_reviewer_scope_permissions.py \
    tests/test_mobile_scope_isolation.py \
    tests/test_work_order_write_guards.py \
    -q
}

run_restore_dry_run() {
  latest_backup_file="$1"
  ./scripts/restore_db.sh --dry-run "$latest_backup_file"
}

echo "开始执行上线闸门检查：BASE_URL=$BASE_URL, TARGET_DATE=$TARGET_DATE"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "DRY RUN：仅输出将执行的门禁步骤，不实际探测。"
  echo "将执行:"
  echo " - GATE_STACK: ./scripts/check_trial_stack.sh \"$BASE_URL\""
  echo " - GATE_PILOT: docker compose ... exec -T backend python scripts/check_pilot_config.py --date \"$TARGET_DATE\" --json"
  if [ "$SKIP_AI" -eq 0 ]; then
    echo " - GATE_AI: backend AI live 探针（assistant query/image + leader summary）"
  fi
  if [ "$SKIP_ROLE_SMOKE" -eq 0 ]; then
    echo " - GATE_ROLE_SMOKE: pytest reviewer/mobile scope/write guard"
  fi
  echo " - GATE_ROLLBACK_PRECHECK: ./scripts/backup_db.sh --dry-run"
  echo " - GATE_ROLLBACK_MATERIAL: 检查 backups/*.dump 存在"
  echo " - GATE_ROLLBACK_RESTORE: ./scripts/restore_db.sh --dry-run <latest-backup>"
  exit 0
fi

if ! run_gate "GATE_STACK" "站点就绪（healthz/readyz/路由）" ./scripts/check_trial_stack.sh "$BASE_URL"; then
  :
fi

echo "[GATE_PILOT] 开始：试点配置硬门槛"
set +e
PILOT_OUTPUT="$(docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python scripts/check_pilot_config.py --date "$TARGET_DATE" --json 2>&1)"
PILOT_STATUS=$?
set -e
printf '%s\n' "$PILOT_OUTPUT"
if [ "$PILOT_STATUS" -eq 0 ]; then
  add_pass "GATE_PILOT" "试点配置硬门槛"
  echo "[GATE_PILOT] 通过"
else
  add_fail "GATE_PILOT" "试点配置硬门槛（check_pilot_config）"
  echo "[GATE_PILOT] 失败"
fi

if [ "$SKIP_AI" -eq 0 ]; then
  echo "[GATE_AI] 开始：AI 功能 live 探针"
  set +e
  AI_OUTPUT="$(check_ai_runtime_live 2>&1)"
  AI_STATUS=$?
  set -e
  printf '%s\n' "$AI_OUTPUT"
  if [ "$AI_STATUS" -eq 0 ]; then
    add_pass "GATE_AI" "AI 功能 live 探针"
    echo "[GATE_AI] 通过"
  else
    add_fail "GATE_AI" "AI 功能 live 探针（assistant/summary 未全量 live）"
    echo "[GATE_AI] 失败"
  fi
else
  add_pass "GATE_AI" "已跳过（--skip-ai）"
fi

if [ "$SKIP_ROLE_SMOKE" -eq 0 ]; then
  if ! run_gate "GATE_ROLE_SMOKE" "角色权限与写入边界 smoke" run_role_smoke_tests; then
    :
  fi
else
  add_pass "GATE_ROLE_SMOKE" "已跳过（--skip-role-smoke）"
fi

if ! run_gate "GATE_ROLLBACK_PRECHECK" "回滚前置预检（backup dry-run）" ./scripts/backup_db.sh --dry-run; then
  :
fi

LATEST_BACKUP_FILE="$(ls -1t backups/*.dump 2>/dev/null | head -n 1 || true)"
if [ -z "$LATEST_BACKUP_FILE" ]; then
  add_fail "GATE_ROLLBACK_MATERIAL" "未找到可用于恢复校验的备份文件（backups/*.dump）"
  echo "[GATE_ROLLBACK_MATERIAL] 失败：未找到 backups/*.dump"
else
  add_pass "GATE_ROLLBACK_MATERIAL" "已发现备份文件：$LATEST_BACKUP_FILE"
  if ! run_gate "GATE_ROLLBACK_RESTORE" "恢复脚本前置预检（restore dry-run）" run_restore_dry_run "$LATEST_BACKUP_FILE"; then
    :
  fi
fi

echo
echo "======== Go-Live Gate 结果 ========"
if [ -n "$PASS_LINES" ]; then
  printf '通过项:%b\n' "$PASS_LINES"
else
  echo "通过项: 无"
fi

if [ -n "$FAIL_LINES" ]; then
  printf '失败项:%b\n' "$FAIL_LINES"
else
  echo "失败项: 无"
fi

if [ "$FAIL_COUNT" -eq 0 ]; then
  echo "结论：GO_LIVE_READY=true（可进入下一步上线动作）"
  exit 0
fi

echo "结论：GO_LIVE_READY=false（请先修复失败项）"
exit 2
