#!/usr/bin/env bash
# HUD guardrails — run from repo root. See Task 7 in
# docs/superpowers/plans/2026-05-10-high-tech-frontend-reform-plan.md
set -euo pipefail

cd "$(dirname "$0")/.."

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

echo "[1/6] scope guard"
grep -cE '^\s*(:root)?\[data-xt-theme="hud"\]' frontend/src/design/xt-hud.css >/dev/null \
  || fail "xt-hud.css is empty or out of scope"
! grep -nE '^(\.el-card|\.el-dialog|\.el-drawer)\s*\{' frontend/src/design/xt-hud.css \
  || fail "xt-hud.css contains global Element Plus override (scope violation)"
! grep -n '!important' frontend/src/design/xt-hud.css \
  || fail "!important present in xt-hud.css"

echo "[2/6] forbidden lexicon (user-facing code only)"
# Product code and templates must never render these words. Docs, plans,
# specs, and tests legitimately reference them as negative constraints.
! grep -rniE --include='*.vue' --include='*.js' --include='*.ts' --include='*.css' \
    'cyberpunk|palantir|quantum|sci-?fi' \
    frontend/src \
  || fail "forbidden product lexicon in frontend/src"
! grep -rniE --include='*.py' \
    'cyberpunk|palantir|quantum|sci-?fi' \
    backend/app \
  || fail "forbidden product lexicon in backend/app"

echo "[3/6] frontend unit tests"
( cd frontend && npm run --silent test >/dev/null ) \
  || fail "frontend tests failed"

echo "[4/6] frontend build + three chunk"
( cd frontend && npm run --silent build >/dev/null ) \
  || fail "frontend build failed"
ls frontend/dist/assets/ 2>/dev/null | grep -qE 'vendor-three' \
  || fail "three.js not code-split into vendor-three chunk"

echo "[5/6] backend preferences tests"
if [ -f backend/tests/test_user_preferences.py ]; then
  ( cd backend && python -m pytest tests/test_user_preferences.py -q >/dev/null ) \
    || fail "backend user_preferences tests failed"
else
  echo "  skipped (Task 6 not merged yet)"
fi

echo "[6/6] docs guard (plan B marked superseded)"
grep -q 'SUPERSEDED' docs/superpowers/plans/2026-05-10-aesthetic-dynamic-landing.md \
  || fail "aesthetic-dynamic-landing plan must be marked SUPERSEDED"

echo "ALL HUD GUARDRAILS PASS"
