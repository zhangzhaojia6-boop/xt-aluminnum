from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.services.mobile_report.flow_enrichment import enrich_mobile_coil_flow_context


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Backfill external flow context for submitted mobile coil entries.')
    parser.add_argument('--business-date', required=True, help='Business date to scan, formatted as YYYY-MM-DD.')
    parser.add_argument('--apply', action='store_true', help='Persist the enrichment. Defaults to dry-run.')
    parser.add_argument('--limit', type=int, default=None, help='Maximum candidate rows to report or update.')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON.')
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    business_date = date.fromisoformat(args.business_date)
    session_factory = get_sessionmaker()
    with session_factory() as db:
        result = enrich_mobile_coil_flow_context(
            db,
            business_date=business_date,
            apply=bool(args.apply),
            limit=args.limit,
        )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        mode = 'APPLY' if result['apply'] else 'DRY-RUN'
        print(f'{mode} mobile coil flow enrichment for {result["business_date"]}')
        print(f'scanned={result["scanned_count"]} candidates={result["candidate_count"]} updated={result["updated_count"]}')
        print(f'skipped_existing_flow={result["skipped_existing_flow_count"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
