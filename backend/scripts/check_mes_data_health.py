"""Check MES data health: weekly fetch trend, fallback ratio, field completeness.

Complements check_mes_sync_lag.py (which only inspects the latest run). This
script answers: over the past N days, is the MES upstream giving us cleaner
data, the same, or worse?

Usage:
    PYTHONPATH=. python scripts/check_mes_data_health.py
    PYTHONPATH=. python scripts/check_mes_data_health.py --days 14 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import func

from app.database import get_sessionmaker
from app.models.mes import MesCoilSnapshot, MesSyncRunLog


FALLBACK_PREFIX = 'fallback:'
COIL_SYNC_CURSOR_KEYS = ('coil_snapshots',)


def collect_health(session, *, days: int) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    fetch_total = (
        session.query(func.coalesce(func.sum(MesSyncRunLog.fetched_count), 0))
        .filter(MesSyncRunLog.cursor_key.in_(COIL_SYNC_CURSOR_KEYS))
        .filter(MesSyncRunLog.started_at >= cutoff)
        .scalar()
        or 0
    )
    run_count = (
        session.query(func.count(MesSyncRunLog.id))
        .filter(MesSyncRunLog.cursor_key.in_(COIL_SYNC_CURSOR_KEYS))
        .filter(MesSyncRunLog.started_at >= cutoff)
        .scalar()
        or 0
    )

    snapshot_total = session.query(func.count(MesCoilSnapshot.id)).scalar() or 0
    fallback_total = (
        session.query(func.count(MesCoilSnapshot.id))
        .filter(MesCoilSnapshot.coil_id.like(f'{FALLBACK_PREFIX}%'))
        .scalar()
        or 0
    )
    machine_code_filled = (
        session.query(func.count(MesCoilSnapshot.id))
        .filter(MesCoilSnapshot.machine_code.isnot(None))
        .filter(MesCoilSnapshot.machine_code != '')
        .scalar()
        or 0
    )
    workshop_filled = (
        session.query(func.count(MesCoilSnapshot.id))
        .filter(MesCoilSnapshot.current_workshop.isnot(None))
        .filter(MesCoilSnapshot.current_workshop != '')
        .scalar()
        or 0
    )
    process_filled = (
        session.query(func.count(MesCoilSnapshot.id))
        .filter(MesCoilSnapshot.current_process.isnot(None))
        .filter(MesCoilSnapshot.current_process != '')
        .scalar()
        or 0
    )

    def pct(part: int, whole: int) -> float:
        return round((part / whole) * 100, 1) if whole else 0.0

    fallback_pct = pct(fallback_total, snapshot_total)
    machine_code_pct = pct(machine_code_filled, snapshot_total)
    workshop_pct = pct(workshop_filled, snapshot_total)
    process_pct = pct(process_filled, snapshot_total)

    blockers: list[dict] = []
    if run_count == 0:
        blockers.append({'code': 'NO_RUNS', 'message': f'past {days}d has zero MES sync runs'})
    elif fetch_total == 0:
        blockers.append({'code': 'ZERO_FETCH', 'message': f'past {days}d ran {run_count}x but fetched 0 rows'})
    if snapshot_total > 0 and fallback_pct >= 99.0:
        blockers.append({
            'code': 'FALLBACK_SATURATED',
            'message': f'fallback coil_id ratio is {fallback_pct}% — MES upstream is not giving real coil_id',
        })
    if snapshot_total > 0 and workshop_pct < 50.0:
        blockers.append({
            'code': 'WORKSHOP_MISSING',
            'message': f'only {workshop_pct}% of snapshots have workshop — route inference will fail for the rest',
        })

    return {
        'window_days': days,
        'window_start': cutoff.isoformat(),
        'sync_runs_in_window': run_count,
        'fetched_in_window': fetch_total,
        'snapshot_total': snapshot_total,
        'fallback_coil_id_count': fallback_total,
        'fallback_coil_id_pct': fallback_pct,
        'machine_code_filled_count': machine_code_filled,
        'machine_code_filled_pct': machine_code_pct,
        'workshop_filled_pct': workshop_pct,
        'process_filled_pct': process_pct,
        'blockers': blockers,
        'ok': len(blockers) == 0,
    }


def render_text(report: dict) -> str:
    lines = [
        f"MES data health (past {report['window_days']}d)",
        f"  sync runs:           {report['sync_runs_in_window']}",
        f"  rows fetched:        {report['fetched_in_window']}",
        f"  snapshots in db:     {report['snapshot_total']}",
        f"  fallback coil_id:    {report['fallback_coil_id_count']} ({report['fallback_coil_id_pct']}%)",
        f"  machine_code filled: {report['machine_code_filled_count']} ({report['machine_code_filled_pct']}%)",
        f"  workshop filled:     {report['workshop_filled_pct']}%",
        f"  process filled:      {report['process_filled_pct']}%",
    ]
    if report['blockers']:
        lines.append('')
        lines.append('blockers:')
        for b in report['blockers']:
            lines.append(f"  - [{b['code']}] {b['message']}")
    else:
        lines.append('')
        lines.append('ok: no blockers')
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='Check MES upstream data health (trend + completeness).')
    parser.add_argument('--days', type=int, default=7, help='look-back window in days (default 7)')
    parser.add_argument('--json', action='store_true', help='emit JSON only')
    args = parser.parse_args()

    sessionmaker = get_sessionmaker()
    session = sessionmaker()
    try:
        report = collect_health(session, days=args.days)
    finally:
        session.close()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print(render_text(report))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
