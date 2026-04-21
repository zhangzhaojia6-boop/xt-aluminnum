#!/usr/bin/env sh
set -eu

if [ "${1:-}" = "" ]; then
  echo "Usage: scripts/check_trial_stack.sh <base-url>" >&2
  exit 1
fi

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$REPO_ROOT"

BASE_URL="$1"

curl -kfsS "$BASE_URL/healthz"
curl -kfsS "$BASE_URL/readyz"
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
