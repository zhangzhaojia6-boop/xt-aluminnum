from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.services import mes_sync_service


def main() -> int:
    parser = argparse.ArgumentParser(description='Check MES sync lag and latest sync status.')
    parser.add_argument('--json', action='store_true', help='Output JSON only')
    args = parser.parse_args()

    sessionmaker = get_sessionmaker()
    session = sessionmaker()
    try:
        payload = mes_sync_service.latest_sync_status(session)
    finally:
        session.close()

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"cursor_key={payload.get('cursor_key')}")
        print(f"last_run_status={payload.get('last_run_status')}")
        print(f"lag_seconds={payload.get('lag_seconds')}")
        print(f"last_synced_at={payload.get('last_synced_at')}")
        print(f"last_event_at={payload.get('last_event_at')}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
