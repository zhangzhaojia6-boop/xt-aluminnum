from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal
from pathlib import Path
import sys
from typing import Any, Callable


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.adapters import get_mes_adapter
from app.core.redaction import redact_secret_text
from app.database import get_sessionmaker
from app.services.hermes_data_audit_service import HermesDataAuditService, NoComparableDataError
from app.services.hermes_mes_read_service import HermesMesReadService


DEFAULT_BACKFILL_FIELDS = (
    'total_output',
    'inbound_total',
    'total_electricity_kwh',
    'total_gas_m3',
    'yield_rate',
)

TABLE_HEADER = (
    'DATE        STATUS                         APPLY  MATCH   MES  HUB  OUTSKILL  DIFFS  NEXT'
)
FAILED_SUMMARY_STATUSES = {
    'failed',
    'no_comparable_data',
    'correction_blocked',
    'correction_failed',
    'correction_partial_failed',
}


def _parse_date(raw: str) -> date:
    return date.fromisoformat(str(raw).strip())


def _parse_csv_list(raw: str | None) -> list[str]:
    if raw is None:
        return []
    return [item.strip() for item in str(raw).split(',') if item.strip()]


def _date_range(start: date, end: date) -> list[date]:
    if start > end:
        raise ValueError('start_date must be on or before end_date')
    return [date.fromordinal(day) for day in range(start.toordinal(), end.toordinal() + 1)]


def _default_service_factory(db: Any) -> HermesDataAuditService:
    return HermesDataAuditService(
        db,
        mes_read_service=HermesMesReadService(get_mes_adapter()),
    )


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _count_diffs(diffs: Any) -> int:
    if not isinstance(diffs, dict):
        return 0
    count = 0
    for payload in diffs.values():
        if not isinstance(payload, dict):
            continue
        if str(payload.get('status') or '').strip() != 'matched':
            count += 1
    return count


def _safe_single_line_text(value: Any) -> str:
    return ' '.join(redact_secret_text(value).split())


def _source_status(run: Any, source_name: str, default: str = 'unknown') -> str:
    source_status = getattr(run, 'source_status', None)
    if not isinstance(source_status, dict):
        return default
    value = source_status.get(source_name)
    if value in (None, ''):
        return default
    return str(value)


def _has_source_error(run: Any) -> bool:
    source_errors = getattr(run, 'source_errors', None)
    if isinstance(source_errors, dict) and source_errors:
        return True
    return False


def _output_skill_missing(run: Any) -> bool:
    output_skill_status = _source_status(run, 'output_skill')
    source_errors = getattr(run, 'source_errors', None)
    return output_skill_status == 'missing' or (
        isinstance(source_errors, dict) and source_errors.get('output_skill') == 'output_skill_source_missing'
    )


def _next_step_from_run(run: Any, *, apply_summary: dict[str, Any] | None = None) -> str:
    if apply_summary is not None and int(apply_summary.get('applied_count', 0) or 0) > 0:
        return 'rerun_audit_to_verify'

    status = str(getattr(run, 'status', '') or '').strip()
    if status.startswith('correction_') or status == 'corrected':
        return 'rerun_audit_to_verify'
    if _output_skill_missing(run):
        return 'mount_output_skill_reference_and_rerun'

    mes_status = _source_status(run, 'mes')
    hub_status = _source_status(run, 'hub')
    output_skill_status = _source_status(run, 'output_skill')
    if _has_source_error(run) or mes_status in {'failed', 'partial_failed'} or hub_status == 'failed' or output_skill_status == 'failed':
        return 'fix_source_health_and_rerun'

    diff_count = _count_diffs(getattr(run, 'diffs', {}))
    action_count = len(getattr(run, 'suggested_actions', []) or [])
    if diff_count > 0 and action_count > 0:
        return 'review_low_risk_actions'
    if diff_count > 0:
        return 'review_diffs_or_expand_fields'
    return 'ready_for_hermes_test'


def summarize_run(run: Any, apply_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    business_date = getattr(run, 'business_date', None)
    match_rate = _float_or_none(getattr(run, 'match_rate', None))
    applied_count = int((apply_summary or {}).get('applied_count', 0) or 0)
    summary = {
        'date': business_date.isoformat() if isinstance(business_date, date) else str(business_date or '--'),
        'status': str(getattr(run, 'status', 'unknown') or 'unknown'),
        'apply': 'yes' if applied_count > 0 else 'no',
        'match': match_rate,
        'mes': _source_status(run, 'mes'),
        'hub': _source_status(run, 'hub'),
        'outskill': _source_status(run, 'output_skill'),
        'diffs': _count_diffs(getattr(run, 'diffs', {})),
        'correction_action_count': len(getattr(run, 'suggested_actions', []) or []),
        'next': _next_step_from_run(run, apply_summary=apply_summary),
        'detail': '',
    }
    return summary


def format_backfill_row(summary: dict[str, Any]) -> str:
    match_value = summary.get('match')
    match_text = '--' if match_value is None else f'{float(match_value):.2f}'
    row = (
        f"{str(summary.get('date', '--')):<10}  "
        f"{str(summary.get('status', 'unknown')):<29}  "
        f"{str(summary.get('apply', 'no')):<5}  "
        f"{match_text:<6}  "
        f"{str(summary.get('mes', 'unknown')):<3}  "
        f"{str(summary.get('hub', 'unknown')):<3}  "
        f"{str(summary.get('outskill', 'unknown')):<8}  "
        f"{str(summary.get('diffs', '--')):<5}  "
        f"{str(summary.get('next', 'review_diffs_or_expand_fields'))}"
    )
    detail = str(summary.get('detail') or '').strip()
    if detail:
        row = f'{row}  {_safe_single_line_text(detail)}'
    return row


def _error_summary(*, business_date: date, status: str, detail: str, next_step: str) -> dict[str, Any]:
    return {
        'date': business_date.isoformat(),
        'status': status,
        'apply': 'no',
        'match': None,
        'mes': 'unknown',
        'hub': 'unknown',
        'outskill': 'unknown',
        'diffs': '--',
        'correction_action_count': 0,
        'next': next_step,
        'detail': _safe_single_line_text(detail),
    }


def _summary_is_failed(summary: dict[str, Any]) -> bool:
    return str(summary.get('status') or '').strip() in FAILED_SUMMARY_STATUSES


def run_backfill(
    *,
    start_date: date,
    end_date: date,
    fields: list[str] | None,
    mes_query_keys: list[str] | None = None,
    dry_run: bool = True,
    apply_corrections: bool = False,
    sessionmaker_factory: Callable[[], Any] | None = None,
    service_factory: Callable[[Any], Any] | None = None,
) -> list[dict[str, Any]]:
    if apply_corrections and dry_run:
        dry_run = False
    if not apply_corrections:
        dry_run = True

    resolved_fields = fields or list(DEFAULT_BACKFILL_FIELDS)
    resolved_sessionmaker_factory = sessionmaker_factory or get_sessionmaker
    resolved_service_factory = service_factory or _default_service_factory

    summaries: list[dict[str, Any]] = []
    session_factory = resolved_sessionmaker_factory()
    for business_date in _date_range(start_date, end_date):
        try:
            with session_factory() as db:
                service = resolved_service_factory(db)
                run = service.create_run(
                    business_date=business_date,
                    fields=resolved_fields,
                    mes_query_keys=mes_query_keys,
                )
                apply_summary = None
                actions = list(getattr(run, 'suggested_actions', []) or [])
                if apply_corrections and actions:
                    apply_summary = service.apply_corrections(
                        audit_run_id=run.id,
                        actions=actions,
                        dry_run=dry_run,
                    )
                summaries.append(summarize_run(run, apply_summary=apply_summary))
        except NoComparableDataError as exc:
            summaries.append(
                _error_summary(
                    business_date=business_date,
                    status='no_comparable_data',
                    detail=str(exc),
                    next_step='expand_fields_or_fix_sources',
                )
            )
        except Exception as exc:  # noqa: BLE001 - script should continue to the next day
            summaries.append(
                _error_summary(
                    business_date=business_date,
                    status='failed',
                    detail=f'{type(exc).__name__}: {exc}',
                    next_step='fix_source_health_and_rerun',
                )
            )
    return summaries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Run Hermes historical data audit backfill.')
    parser.add_argument('--start-date', required=True, type=_parse_date)
    parser.add_argument('--end-date', required=True, type=_parse_date)
    parser.add_argument('--fields', default=None)
    parser.add_argument('--mes-query-keys', default=None)
    parser.add_argument('--dry-run', action='store_true', help='Compatibility flag; backfill defaults to dry-run.')
    parser.add_argument('--apply-corrections', action='store_true', help='Apply low-risk corrections for each day.')
    parser.add_argument('--verbose', action='store_true', help='Print the current date before running it.')
    args = parser.parse_args(argv)

    if args.apply_corrections and args.dry_run:
        parser.error('--dry-run cannot be combined with --apply-corrections')

    try:
        fields = _parse_csv_list(args.fields) or list(DEFAULT_BACKFILL_FIELDS)
        mes_query_keys = _parse_csv_list(args.mes_query_keys)
        days = _date_range(args.start_date, args.end_date)
    except ValueError as exc:
        parser.error(str(exc))

    if args.verbose:
        for business_date in days:
            print(f'running {business_date.isoformat()}')

    summaries = run_backfill(
        start_date=args.start_date,
        end_date=args.end_date,
        fields=fields,
        mes_query_keys=mes_query_keys or None,
        dry_run=not args.apply_corrections,
        apply_corrections=args.apply_corrections,
    )

    print(TABLE_HEADER)
    for summary in summaries:
        print(format_backfill_row(summary))

    has_failures = any(_summary_is_failed(summary) for summary in summaries)
    return 1 if has_failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
