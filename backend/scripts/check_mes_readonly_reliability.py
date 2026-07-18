from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sys
from typing import Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.adapters.factory import create_mes_adapter
from app.adapters.mes_adapter import set_mes_adapter
from app.core.business_time import last_completed_production_business_date, local_now
from app.database import get_sessionmaker
from app.services.mes_readonly_reliability_service import build_mes_readonly_reliability_report


PRODUCTION_OUTPUT_ROOT = Path('/var/lib/aluminum-bypass/acceptance')


def resolve_output_path(value: str, *, output_root: Path = PRODUCTION_OUTPUT_ROOT) -> Path:
    root = output_root.resolve()
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f'output must stay below acceptance output root: {root}')
    return resolved


def _business_dates(*, explicit: Sequence[str], days: int, now: datetime) -> tuple[date, ...]:
    if days != 3:
        raise ValueError('this production gate requires exactly --days 3')
    if explicit:
        if len(explicit) != 3:
            raise ValueError('provide exactly three --business-date values')
        parsed = tuple(date.fromisoformat(value) for value in explicit)
        if len(set(parsed)) != 3:
            raise ValueError('--business-date values must be unique')
        return tuple(sorted(parsed))
    latest = last_completed_production_business_date(local_now(now))
    return tuple(latest - timedelta(days=offset) for offset in (2, 1, 0))


def render_text(report: dict) -> str:
    lines = [
        f"MES read-only reliability: {report['status']}",
        f"business dates: {', '.join(report['business_dates'])}",
        f"source probes: {len(report['query_results'])}",
        f"blockers: {len(report['blockers'])}",
    ]
    lines.extend(f"  - {item['code']}" for item in report['blockers'])
    return '\n'.join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Run the three-business-date MES read-only reliability gate.')
    parser.add_argument('--days', type=int, default=3)
    parser.add_argument('--business-date', action='append', default=[])
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--output')
    parser.add_argument('--fault-drill', action='store_true')
    return parser


def run(
    argv: Sequence[str] | None = None,
    *,
    session_factory=None,
    adapter=None,
    now: datetime | None = None,
    output_root: Path = PRODUCTION_OUTPUT_ROOT,
) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    current = local_now(now)
    try:
        business_dates = _business_dates(explicit=args.business_date, days=args.days, now=current)
        output_path = resolve_output_path(args.output, output_root=output_root) if args.output else None
    except ValueError as exc:
        parser.error(str(exc))

    session = (session_factory or get_sessionmaker())()
    try:
        selected_adapter = adapter
        if selected_adapter is None:
            selected_adapter = create_mes_adapter()
            set_mes_adapter(selected_adapter)
        report = build_mes_readonly_reliability_report(
            session,
            adapter=selected_adapter,
            business_dates=business_dates,
            now=current,
            run_fault_drills=args.fault_drill,
        )
    finally:
        session.close()

    payload = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + '\n', encoding='utf-8')
    print(payload if args.json else render_text(report))
    return 0 if report['status'] == 'pass' else 1


def main() -> int:
    return run()


if __name__ == '__main__':
    raise SystemExit(main())
