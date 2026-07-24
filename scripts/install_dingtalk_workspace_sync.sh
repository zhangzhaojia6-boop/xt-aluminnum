#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/srv/aluminum-bypass}"
DWS_BIN="${DWS_BIN:-$(command -v dws || true)}"
SERVICE_NAME="xintai-dingtalk-workspace-sync"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "must_run_as_root" >&2
  exit 1
fi
if [[ ! -x "$REPO_ROOT/backend/.venv/bin/python" ]]; then
  echo "backend_python_missing" >&2
  exit 1
fi
if [[ -z "$DWS_BIN" || ! -x "$DWS_BIN" ]]; then
  echo "dws_cli_missing" >&2
  exit 1
fi

auth_status="$("$DWS_BIN" auth status --format json)"
python3 -c '
import json
import sys
payload = json.load(sys.stdin)
if not payload.get("authenticated") or not payload.get("token_valid"):
    raise SystemExit("dws_auth_invalid")
' <<<"$auth_status"

cat >"/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=Xintai DingTalk all-conversation evidence sync
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=oneshot
User=root
WorkingDirectory=${REPO_ROOT}/backend
Environment=HOME=/root
Environment=PYTHONPATH=${REPO_ROOT}/backend
Environment=NO_PROXY=127.0.0.1,localhost,.dingtalk.com
Environment=no_proxy=127.0.0.1,localhost,.dingtalk.com
UMask=0077
ExecStart=${REPO_ROOT}/backend/.venv/bin/python scripts/sync_dingtalk_workspace_history.py --dws-bin ${DWS_BIN} --lookback-minutes 120 --max-pages 20
TimeoutStartSec=10min
Nice=10

[Install]
WantedBy=multi-user.target
EOF

cat >"/etc/systemd/system/${SERVICE_NAME}.timer" <<EOF
[Unit]
Description=Run DingTalk all-conversation evidence sync every five minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
RandomizedDelaySec=20s
AccuracySec=20s
Persistent=true
Unit=${SERVICE_NAME}.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.timer"
systemctl start "${SERVICE_NAME}.service"
systemctl is-active "${SERVICE_NAME}.timer"
