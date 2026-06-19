from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.redaction import filter_sensitive_mapping, redact_secret_text
from app.models.hermes_data_audit import HermesCorrectionAction, HermesDataAuditRun
from app.services.mapping_reconciliation_service import parse_output_skill_reference_file


class OutputSkillSourceMissingError(RuntimeError):
    pass


class OutputSkillPathViolationError(ValueError):
    pass


class NoComparableDataError(RuntimeError):
    pass


class CorrectionApplyDisabledError(RuntimeError):
    pass


class DuplicateCorrectionActionError(RuntimeError):
    pass


class CorrectionHandlerMissingError(RuntimeError):
    pass


DEFAULT_MES_QUERY_KEYS = (
    'workshop_process_records',
    'stock_records',
    'finished_inbound_records',
    'material_records',
    'yield_records',
    'wip_totals',
)
DEFAULT_AUDIT_FIELDS = (
    'total_output',
    'workshop_output',
    'wip_total',
    'inbound_total',
    'total_electricity_kwh',
    'total_gas_m3',
    'yield_rate',
    'contract_amount',
    'ton_cost',
)
SUPPORTED_ACTION_TYPES = {
    'mapping_alias_upsert',
    'mapping_field_rule_upsert',
    'mapping_reconciliation_run',
    'daily_report_recalculate',
}

TEXT_RAW_EXTENSIONS = {'.txt', '.md', '.log'}
CSV_EXTENSIONS = {'.csv'}
_TRUE_VALUES = {'1', 'true', 'yes', 'on'}
_NARRATIVE_PATTERNS = {
    'inbound_total': re.compile(r'入库成品日合计\s*([0-9]+(?:\.[0-9]+)?)\s*吨'),
    'yield_rate': re.compile(r'(?:日成品率|成材率|成品率)\s*([0-9]+(?:\.[0-9]+)?)\s*%'),
    'total_output': re.compile(r'(?:车间总产量日合计|总产量日合计|产量日合计)\s*([0-9]+(?:\.[0-9]+)?)\s*吨'),
    'wip_total': re.compile(r'(?:在制料|在制总量|在制)\s*([0-9]+(?:\.[0-9]+)?)\s*吨'),
    'total_electricity_kwh': re.compile(r'(?:全厂高压总用电量|全厂用电|总用电量)\s*([0-9]+(?:\.[0-9]+)?)\s*度'),
    'total_gas_m3': re.compile(r'(?:共计|天然气总量)\s*([0-9]+(?:\.[0-9]+)?)\s*m[3³]'),
    'contract_amount': re.compile(r'当天接合同\s*([0-9]+(?:\.[0-9]+)?)\s*吨'),
    'remaining_contract_amount': re.compile(r'(?:总余合同量|余合同量)\s*([0-9]+(?:\.[0-9]+)?)\s*吨'),
}
_ROW_FIELD_ALIASES = {
    'total_electricity_kwh': ('total_electricity_kwh', 'electricity_monthly', 'energy_kwh'),
    'total_gas_m3': ('total_gas_m3', 'gas_monthly', 'gas_m3'),
    'wip_total': ('wip_total',),
    'total_output': ('total_output', 'output_tons'),
    'inbound_total': ('inbound_total',),
    'yield_rate': ('yield_rate',),
    'contract_amount': ('contract_amount', 'daily_contract_weight'),
    'remaining_contract_amount': ('remaining_contract_amount', 'remaining_contract_weight'),
}
_SUM_FIELDS = {
    'total_electricity_kwh',
    'total_gas_m3',
    'total_output',
    'inbound_total',
}
_CSV_HEADER_ALIASES = {
    '日期': 'business_date',
    'date': 'business_date',
    '产量(吨)': 'output_tons',
    '总产量': 'total_output',
    '成品率': 'yield_rate',
    '成材率': 'yield_rate',
    '日成品率': 'yield_rate',
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized = filter_sensitive_mapping(value)
        return {str(key): _json_safe(item) for key, item in sanitized.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _redact_issue_payload(value: Any) -> Any:
    safe_value = _json_safe(value)
    if isinstance(safe_value, Mapping):
        return {str(key): _redact_issue_payload(item) for key, item in safe_value.items()}
    if isinstance(safe_value, list):
        return [_redact_issue_payload(item) for item in safe_value]
    if isinstance(safe_value, str):
        return redact_secret_text(safe_value)
    return safe_value


def _stable_string_list(values: Sequence[str] | None) -> list[str]:
    if not values:
        return []
    normalized = {str(value).strip() for value in values if str(value).strip()}
    return sorted(normalized)


def _payload_hash(value: Any) -> str:
    encoded = json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True).encode('utf-8')
    return hashlib.sha1(encoded).hexdigest()


def _numeric_value(value: Any) -> float | None:
    if value is None or value == '':
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(',', '')
    if text.endswith('%'):
        text = text[:-1]
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _values_match(left: Any, right: Any) -> bool:
    left_number = _numeric_value(left)
    right_number = _numeric_value(right)
    if left_number is not None and right_number is not None:
        tolerance = max(0.01, max(abs(left_number), abs(right_number)) * 0.001)
        return abs(left_number - right_number) <= tolerance
    return str(left).strip() == str(right).strip()


class HermesDataAuditService:
    def __init__(
        self,
        db: Session,
        *,
        mes_read_service: Any | None = None,
        output_skill_root: str | Path | None = None,
        hub_snapshot_reader: Callable[[date, Sequence[str]], Mapping[str, Any]] | None = None,
        apply_enabled: bool | None = None,
        correction_handler: Callable[[Mapping[str, Any]], Mapping[str, Any] | None] | None = None,
    ) -> None:
        self._db = db
        self._mes_read_service = mes_read_service
        self._output_skill_root = output_skill_root
        self._hub_snapshot_reader = hub_snapshot_reader
        self._apply_enabled = self._env_flag_enabled() if apply_enabled is None else bool(apply_enabled)
        self._correction_handler = correction_handler

    def create_run(
        self,
        *,
        business_date: date,
        fields: Sequence[str] | None,
        mes_query_keys: Sequence[str] | None = None,
        created_by_id: int | None = None,
    ) -> HermesDataAuditRun:
        normalized_fields = self._normalize_fields(fields)
        now = datetime.now(timezone.utc)
        mes_result, hub_snapshot, hub_status, hub_error, output_skill_snapshot = self._collect_sources(
            business_date=business_date,
            fields=normalized_fields,
            mes_query_keys=mes_query_keys,
        )
        mes_field_values = self._extract_mes_field_values(mes_result.get('records', {}), normalized_fields)
        hub_field_values = self._extract_direct_field_values(hub_snapshot, normalized_fields)
        output_field_values = self._extract_direct_field_values(output_skill_snapshot.get('parsed', {}), normalized_fields)

        source_status = {
            'mes': mes_result.get('source_status', {}).get('mes', 'empty'),
            'hub': hub_status,
            'output_skill': output_skill_snapshot.get('status', 'missing'),
            'mes_sources': mes_result.get('source_status', {}).get('sources', {}),
        }
        source_errors = self._merge_source_errors(
            mes_errors=mes_result.get('source_errors', {}),
            hub_error=hub_error,
            output_skill_snapshot=output_skill_snapshot,
        )
        mes_snapshot = self._build_mes_snapshot(mes_result=mes_result, field_values=mes_field_values)
        safe_hub_snapshot = self._build_hub_snapshot(
            hub_snapshot=hub_snapshot,
            hub_status=hub_status,
            field_values=hub_field_values,
            hub_error=hub_error,
        )
        safe_output_snapshot = self._build_output_skill_snapshot(
            output_skill_snapshot=output_skill_snapshot,
            field_values=output_field_values,
        )
        run_key = self._build_run_key(
            business_date,
            normalized_fields,
            mes_query_keys,
            mes_snapshot=mes_snapshot,
            hub_snapshot=safe_hub_snapshot,
            output_skill_identity=self._output_skill_identity(output_skill_snapshot),
        )
        existing_run = self._db.query(HermesDataAuditRun).filter(HermesDataAuditRun.run_key == run_key).one_or_none()
        if existing_run is not None:
            return existing_run

        diffs, comparable_count, matched_count = self._build_diffs(
            fields=normalized_fields,
            mes_values=mes_field_values,
            hub_values=hub_field_values,
            output_values=output_field_values,
        )
        suggested_actions = self._build_suggested_actions(
            business_date=business_date,
            diffs=diffs,
        )

        run = HermesDataAuditRun(
            run_key=run_key,
            business_date=business_date,
            status='running',
            source_status=source_status,
            source_errors=source_errors,
            mes_snapshot=mes_snapshot,
            hub_snapshot=safe_hub_snapshot,
            output_skill_snapshot=safe_output_snapshot,
            diffs=diffs,
            suggested_actions=suggested_actions,
            created_by_id=created_by_id,
            started_at=now,
        )
        self._db.add(run)
        self._db.flush()

        if comparable_count == 0:
            run.status = 'failed'
            run.match_rate = None
            run.completed_at = now
            self._db.commit()
            self._db.refresh(run)
            raise NoComparableDataError(f'No comparable data for audit run {run.id}')

        run.match_rate = matched_count / comparable_count
        run.status = self._completed_run_status(source_status=source_status, source_errors=source_errors)
        run.completed_at = now
        self._db.commit()
        self._db.refresh(run)
        return run

    def apply_corrections(
        self,
        *,
        audit_run_id: int,
        actions: Sequence[Mapping[str, Any]],
        dry_run: bool = True,
        applied_by_id: int | None = None,
    ) -> dict[str, Any]:
        run = self._db.get(HermesDataAuditRun, audit_run_id)
        if run is None:
            raise LookupError(f'Hermes data audit run {audit_run_id} not found')

        summary = {
            'audit_run_id': audit_run_id,
            'apply_enabled': self._apply_enabled,
            'reason': None,
            'created_count': 0,
            'dry_run_count': 0,
            'applied_count': 0,
            'blocked_count': 0,
            'skipped_count': 0,
            'failed_count': 0,
            'action_statuses': [],
        }
        now = datetime.now(timezone.utc)

        for payload in actions:
            idempotency_key = str(payload.get('idempotency_key') or '').strip()
            if not idempotency_key:
                raise ValueError('idempotency_key is required')

            existing = (
                self._db.query(HermesCorrectionAction)
                .filter(HermesCorrectionAction.idempotency_key == idempotency_key)
                .one_or_none()
            )
            if existing is not None and not (existing.status == 'dry_run' and not dry_run):
                summary['skipped_count'] += 1
                summary['action_statuses'].append({'idempotency_key': idempotency_key, 'status': 'skipped_duplicate'})
                continue

            is_new_action = existing is None
            action = existing or HermesCorrectionAction(
                audit_run_id=audit_run_id,
                idempotency_key=idempotency_key,
                rollback_status='not_requested',
            )
            self._sync_action_from_payload(action, audit_run_id=audit_run_id, payload=payload)
            action.status = 'pending'
            if is_new_action:
                self._db.add(action)
            self._db.flush()
            if is_new_action:
                summary['created_count'] += 1

        planned_actions = (
            self._db.query(HermesCorrectionAction)
            .filter(HermesCorrectionAction.audit_run_id == audit_run_id)
            .filter(HermesCorrectionAction.idempotency_key.in_([str(payload.get('idempotency_key') or '').strip() for payload in actions]))
            .order_by(HermesCorrectionAction.id.asc())
            .all()
        )

        executable_actions: list[HermesCorrectionAction] = []
        for action in planned_actions:
            status, blocked_reason = self._determine_action_status(action=action, dry_run=dry_run)
            if status == 'executable':
                executable_actions.append(action)
                continue
            action.status = status
            if blocked_reason:
                action.evidence = {**(action.evidence or {}), 'blocked_reason': blocked_reason}
            if status == 'dry_run':
                summary['dry_run_count'] += 1
            elif 'blocked' in status:
                summary['blocked_count'] += 1
                if blocked_reason == 'apply_disabled':
                    summary['reason'] = 'apply_disabled'
            summary['action_statuses'].append({'idempotency_key': action.idempotency_key, 'status': status})

        if not dry_run and executable_actions:
            handler_new_ids = {id(item) for item in self._db.new}
            savepoint = self._db.begin_nested()
            handler_results: dict[str, Mapping[str, Any]] = {}
            batch_error: str | None = None
            try:
                for action in executable_actions:
                    handler_result = _json_safe(self._correction_handler(_json_safe(self._action_payload(action))) or {})
                    handler_results[action.idempotency_key] = handler_result if isinstance(handler_result, Mapping) else {}
                savepoint.commit()
            except Exception as exc:
                savepoint.rollback()
                self._cleanup_failed_handler_side_effects(existing_new_ids=handler_new_ids)
                batch_error = redact_secret_text(str(exc))

            if batch_error is not None:
                for action in executable_actions:
                    action.status = 'failed'
                    action.evidence = {**(action.evidence or {}), 'error': batch_error}
                    summary['failed_count'] += 1
                    summary['action_statuses'].append({'idempotency_key': action.idempotency_key, 'status': 'failed'})
            else:
                for action in executable_actions:
                    handler_result = handler_results.get(action.idempotency_key, {})
                    if 'before_value' in handler_result:
                        action.before_value = _json_safe(handler_result.get('before_value'))
                    if 'after_value' in handler_result:
                        action.after_value = _json_safe(handler_result.get('after_value'))
                    if 'evidence' in handler_result:
                        action.evidence = _json_safe(handler_result.get('evidence') or {})
                    if 'rollback_payload' in handler_result:
                        action.rollback_payload = _json_safe(handler_result.get('rollback_payload'))
                    action.status = 'applied'
                    action.applied_by_id = applied_by_id
                    action.applied_at = now
                    summary['applied_count'] += 1
                    summary['action_statuses'].append({'idempotency_key': action.idempotency_key, 'status': 'applied'})

        if summary['applied_count'] and (summary['failed_count'] or summary['blocked_count']):
            run.status = 'correction_partial_failed'
            run.completed_at = now
        elif summary['failed_count'] and summary['blocked_count']:
            run.status = 'correction_partial_failed'
            run.completed_at = now
        elif summary['applied_count']:
            run.status = 'corrected'
            run.completed_at = now
        elif summary['failed_count']:
            run.status = 'correction_failed'
            run.completed_at = now
        elif summary['blocked_count']:
            run.status = 'correction_blocked'
            run.completed_at = now

        self._db.commit()
        return summary

    def _collect_sources(
        self,
        *,
        business_date: date,
        fields: Sequence[str],
        mes_query_keys: Sequence[str] | None,
    ) -> tuple[dict[str, Any], Mapping[str, Any], str, str | None, dict[str, Any]]:
        mes_result = self._read_mes_sources(business_date=business_date, mes_query_keys=mes_query_keys)
        hub_snapshot, hub_status, hub_error = self._read_hub_snapshot(business_date=business_date, fields=fields)
        output_skill_snapshot = self._read_output_skill_business_date(business_date)
        return mes_result, hub_snapshot, hub_status, hub_error, output_skill_snapshot

    def _read_mes_sources(self, *, business_date: date, mes_query_keys: Sequence[str] | None) -> dict[str, Any]:
        if self._mes_read_service is None:
            return {
                'business_date': business_date.isoformat(),
                'window': {},
                'records': {},
                'source_status': {'mes': 'empty', 'sources': {}},
                'source_errors': {},
            }
        try:
            return self._mes_read_service.read_sources(
                business_date=business_date,
                query_keys=list(mes_query_keys or DEFAULT_MES_QUERY_KEYS),
            )
        except Exception as exc:
            return {
                'business_date': business_date.isoformat(),
                'window': {},
                'records': {},
                'source_status': {'mes': 'failed', 'sources': {}},
                'source_errors': {'mes': redact_secret_text(str(exc))},
            }

    def _read_hub_snapshot(
        self,
        *,
        business_date: date,
        fields: Sequence[str],
    ) -> tuple[Mapping[str, Any], str, str | None]:
        if self._hub_snapshot_reader is None:
            return {}, 'empty', None
        try:
            snapshot = self._hub_snapshot_reader(business_date, fields) or {}
        except Exception as exc:
            return {}, 'failed', redact_secret_text(str(exc))
        return snapshot, 'ok' if snapshot else 'empty', None

    def _read_output_skill_business_date(self, business_date: date) -> dict[str, Any]:
        root = self._output_skill_root_path()
        if root is None or not root.exists() or not root.is_dir():
            return {
                'status': 'missing',
                'files': [],
                'raw_text': '',
                'parsed': {},
                'issues': [{'code': 'output_skill_source_missing'}],
            }

        matched_files = sorted(
            [
                path
                for path in root.rglob('*')
                if path.is_file() and self._filename_matches_business_date(path.name, business_date)
            ]
        )
        if not matched_files:
            return {
                'status': 'missing',
                'files': [],
                'raw_text': '',
                'parsed': {},
                'issues': [{'code': 'output_skill_source_missing'}],
            }

        files: list[str] = []
        raw_text_parts: list[str] = []
        combined_fields: dict[str, Any] = {}
        issues: list[dict[str, Any]] = []
        statuses: list[str] = []

        for path in matched_files:
            payload = self._read_output_skill_file(path.relative_to(root))
            files.extend(payload.get('files', []))
            if payload.get('raw_text'):
                raw_text_parts.append(str(payload['raw_text']))
            statuses.append(str(payload.get('status') or 'missing'))
            issues.extend(payload.get('issues', []))
            for field_name, value in payload.get('parsed', {}).items():
                if field_name not in combined_fields:
                    combined_fields[field_name] = value
                elif not _values_match(combined_fields[field_name], value):
                    issues.append(
                        {
                            'code': 'conflicting_field_value',
                            'field_name': field_name,
                            'kept_value': combined_fields[field_name],
                            'ignored_value': value,
                        }
                    )

        status = 'parsed' if 'parsed' in statuses else 'empty'
        if not combined_fields and not raw_text_parts and 'unsupported' in statuses:
            status = 'unsupported'
        elif not combined_fields and status == 'parsed':
            status = 'empty'

        return {
            'status': status,
            'files': files,
            'raw_text': '\n'.join(raw_text_parts),
            'parsed': combined_fields,
            'issues': issues,
        }

    def _read_output_skill_file(self, relative_path: str | Path) -> dict[str, Any]:
        root = self._output_skill_root_path()
        if root is None or not root.exists() or not root.is_dir():
            return {
                'status': 'missing',
                'files': [],
                'raw_text': '',
                'parsed': {},
                'issues': [{'code': 'output_skill_source_missing'}],
            }

        resolved_root = root.resolve()
        candidate = Path(relative_path)
        resolved_path = candidate.resolve() if candidate.is_absolute() else (resolved_root / candidate).resolve()
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError as exc:
            raise OutputSkillPathViolationError(f'Output skill path escaped root: {relative_path}') from exc

        if not resolved_path.exists() or not resolved_path.is_file():
            return {
                'status': 'missing',
                'files': [],
                'raw_text': '',
                'parsed': {},
                'issues': [{'code': 'output_skill_file_missing', 'path': str(candidate)}],
            }

        if resolved_path.suffix.lower() in CSV_EXTENSIONS:
            parsed = self._parse_csv_output_skill_file(resolved_path)
        else:
            parsed = parse_output_skill_reference_file(resolved_path)
        raw_text = self._read_text_file(resolved_path) if resolved_path.suffix.lower() in TEXT_RAW_EXTENSIONS else ''
        extracted_fields, extraction_issues = self._extract_output_skill_fields(parsed.get('rows', []), raw_text)
        issues = [*_json_safe(parsed.get('issues', [])), *extraction_issues]

        status = str(parsed.get('status') or 'missing')
        if status == 'parsed' and not parsed.get('rows') and not extracted_fields:
            status = 'empty'

        return {
            'status': status,
            'files': [str(resolved_path)],
            'raw_text': raw_text,
            'parsed': extracted_fields,
            'issues': issues,
        }

    @staticmethod
    def _read_text_file(path: Path) -> str:
        for encoding in ('utf-8', 'utf-8-sig', 'gb18030', 'gbk'):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return path.read_text(encoding='utf-8', errors='ignore')

    def _extract_output_skill_fields(
        self,
        rows: Sequence[Mapping[str, Any]],
        raw_text: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        collected: dict[str, list[Any]] = defaultdict(list)
        for row in rows:
            for target_field, aliases in _ROW_FIELD_ALIASES.items():
                for alias in aliases:
                    if alias in row and row[alias] not in (None, ''):
                        collected[target_field].append(row[alias])

        for field_name, pattern in _NARRATIVE_PATTERNS.items():
            match = pattern.search(raw_text)
            if match:
                collected[field_name].append(match.group(1))

        parsed: dict[str, Any] = {}
        issues: list[dict[str, Any]] = []
        for field_name, values in collected.items():
            resolved = self._resolve_output_field(field_name, values)
            if resolved is not None:
                parsed[field_name] = resolved
            elif values:
                issues.append({'code': 'unsupported_field_value', 'field_name': field_name})
        return parsed, issues

    @staticmethod
    def _resolve_output_field(field_name: str, values: Sequence[Any]) -> Any:
        numeric_values = [number for value in values if (number := _numeric_value(value)) is not None]
        if numeric_values:
            if field_name in _SUM_FIELDS:
                return round(sum(numeric_values), 4)
            return numeric_values[0]
        for value in values:
            if value not in (None, ''):
                return str(value).strip()
        return None

    @staticmethod
    def _extract_mes_field_values(records: Mapping[str, Any], fields: Sequence[str]) -> dict[str, Any]:
        requested = set(fields)
        collected: dict[str, list[Any]] = defaultdict(list)
        for group in records.values():
            if not isinstance(group, list):
                continue
            for row in group:
                if not isinstance(row, Mapping):
                    continue
                field_name = row.get('field')
                if field_name in requested and row.get('value') not in (None, ''):
                    collected[str(field_name)].append(row.get('value'))
                for requested_field in requested:
                    if requested_field in row and row[requested_field] not in (None, ''):
                        collected[requested_field].append(row[requested_field])

        return {
            field_name: HermesDataAuditService._resolve_output_field(field_name, values)
            for field_name, values in collected.items()
            if values
        }

    @staticmethod
    def _extract_direct_field_values(snapshot: Mapping[str, Any], fields: Sequence[str]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for field_name in fields:
            if field_name in snapshot and snapshot[field_name] not in (None, ''):
                value = snapshot[field_name]
                number = _numeric_value(value)
                values[field_name] = number if number is not None else value
        return values

    @staticmethod
    def _build_diffs(
        *,
        fields: Sequence[str],
        mes_values: Mapping[str, Any],
        hub_values: Mapping[str, Any],
        output_values: Mapping[str, Any],
    ) -> tuple[dict[str, Any], int, int]:
        diffs: dict[str, Any] = {}
        comparable_count = 0
        matched_count = 0

        for field_name in fields:
            mes_value = mes_values.get(field_name)
            hub_value = hub_values.get(field_name)
            output_value = output_values.get(field_name)
            values = {
                source_name: value
                for source_name, value in (
                    ('mes', mes_value),
                    ('hub', hub_value),
                    ('output_skill', output_value),
                )
                if value is not None
            }
            if len(values) >= 2:
                comparable_count += 1

            if mes_value is None:
                status = 'mes_missing'
            elif hub_value is None:
                status = 'hub_missing'
            elif output_value is None:
                status = 'output_skill_missing'
            elif _values_match(mes_value, hub_value) and _values_match(mes_value, output_value):
                status = 'matched'
                matched_count += 1
            elif _values_match(mes_value, output_value) and not _values_match(mes_value, hub_value):
                status = 'hub_mismatch'
            else:
                status = 'cannot_decide'

            diffs[field_name] = {'status': status, 'values': values}

        return diffs, comparable_count, matched_count

    def _build_suggested_actions(
        self,
        *,
        business_date: date,
        diffs: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for field_name, diff in diffs.items():
            if diff.get('status') != 'hub_mismatch':
                continue
            values = diff.get('values') or {}
            suggested_value = values.get('mes', values.get('output_skill'))
            action_payload = {
                'action_type': 'mapping_reconciliation_run',
                'risk_level': 'low',
                'field_name': field_name,
                'target_table': 'data_hub_snapshot',
                'target_key': f'{business_date.isoformat()}:{field_name}',
                'before_value': {'hub': values.get('hub')},
                'after_value': {'suggested_value': suggested_value},
                'evidence': {
                    'field_name': field_name,
                    'values': values,
                },
            }
            action_payload['idempotency_key'] = self._build_action_idempotency_key(action_payload)
            actions.append(action_payload)
        return actions

    @staticmethod
    def _merge_source_errors(
        *,
        mes_errors: Mapping[str, Any],
        hub_error: str | None,
        output_skill_snapshot: Mapping[str, Any],
    ) -> dict[str, Any]:
        source_errors: dict[str, Any] = {}
        if mes_errors:
            source_errors['mes'] = _redact_issue_payload(mes_errors)
        if hub_error:
            source_errors['hub'] = hub_error
        output_status = output_skill_snapshot.get('status')
        output_issues = output_skill_snapshot.get('issues') or []
        if output_status == 'missing':
            source_errors['output_skill'] = 'output_skill_source_missing'
        elif output_status == 'unsupported':
            source_errors['output_skill'] = _redact_issue_payload(output_issues)
        elif output_issues:
            source_errors['output_skill'] = _redact_issue_payload(output_issues)
        return source_errors

    def _output_skill_root_path(self) -> Path | None:
        raw_value = self._output_skill_root or os.getenv('OUTPUT_SKILL_ROOT')
        if raw_value is None or str(raw_value).strip() == '':
            return None
        return Path(raw_value)

    @staticmethod
    def _filename_matches_business_date(file_name: str, business_date: date) -> bool:
        month = business_date.month
        day = business_date.day
        patterns = (
            rf'(?<!\d){business_date.year}[-_.]0?{month}[-_.]0?{day}(?!\d)',
            rf'(?<!\d){business_date.year}年0?{month}月0?{day}日',
            rf'(?<!\d)0?{month}月0?{day}日',
        )
        return any(re.search(pattern, file_name) for pattern in patterns)

    @staticmethod
    def _env_flag_enabled() -> bool:
        return str(os.getenv('HERMES_DATA_AUDIT_APPLY_ENABLED', 'false')).strip().lower() in _TRUE_VALUES

    @staticmethod
    def _build_run_key(
        business_date: date,
        fields: Sequence[str],
        mes_query_keys: Sequence[str] | None,
        mes_snapshot: Mapping[str, Any] | None = None,
        hub_snapshot: Mapping[str, Any] | None = None,
        output_skill_identity: Mapping[str, Any] | None = None,
    ) -> str:
        payload = {
            'business_date': business_date.isoformat(),
            'fields': _stable_string_list(fields),
            'mes_query_keys': _stable_string_list(mes_query_keys or DEFAULT_MES_QUERY_KEYS),
            'mes_snapshot_hash': (mes_snapshot or {}).get('payload_hash'),
            'hub_snapshot_hash': (hub_snapshot or {}).get('payload_hash'),
            'output_skill_identity': _json_safe(output_skill_identity or {}),
        }
        digest = hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[:16]
        return f'hermes-audit-{business_date.isoformat()}-{digest}'

    @staticmethod
    def _build_action_idempotency_key(payload: Mapping[str, Any]) -> str:
        digest = hashlib.sha1(json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[
            :16
        ]
        return f"{payload.get('action_type', 'action')}:{digest}"

    @staticmethod
    def _build_mes_snapshot(
        *,
        mes_result: Mapping[str, Any],
        field_values: Mapping[str, Any],
    ) -> dict[str, Any]:
        records = mes_result.get('records') or {}
        records_count_by_source = {
            str(source_name): len(source_rows) if isinstance(source_rows, list) else 0
            for source_name, source_rows in records.items()
        }
        return _redact_issue_payload(
            {
                'business_date': mes_result.get('business_date'),
                'window': mes_result.get('window') or {},
                'source_status': mes_result.get('source_status') or {},
                'source_errors': mes_result.get('source_errors') or {},
                'records_count_by_source': records_count_by_source,
                'field_values': field_values,
                'payload_hash': _payload_hash(
                    {
                        'window': mes_result.get('window'),
                        'records': mes_result.get('records'),
                        'source_status': mes_result.get('source_status'),
                        'source_errors': mes_result.get('source_errors'),
                    }
                ),
                'raw_payload_truncated': True,
            }
        )

    @staticmethod
    def _build_hub_snapshot(
        *,
        hub_snapshot: Mapping[str, Any],
        hub_status: str,
        field_values: Mapping[str, Any],
        hub_error: str | None,
    ) -> dict[str, Any]:
        return _redact_issue_payload(
            {
                'status': hub_status,
                'field_values': field_values,
                'source_errors': hub_error,
                'field_count': len(hub_snapshot),
                'payload_hash': _payload_hash(hub_snapshot),
                'raw_payload_truncated': True,
            }
        )

    @staticmethod
    def _build_output_skill_snapshot(
        *,
        output_skill_snapshot: Mapping[str, Any],
        field_values: Mapping[str, Any],
    ) -> dict[str, Any]:
        return _redact_issue_payload(
            {
                'status': output_skill_snapshot.get('status', 'missing'),
                'files': output_skill_snapshot.get('files') or [],
                'parsed': field_values,
                'issues': output_skill_snapshot.get('issues') or [],
                'payload_hash': _payload_hash(
                    {
                        'files': output_skill_snapshot.get('files'),
                        'raw_text': output_skill_snapshot.get('raw_text'),
                        'parsed': output_skill_snapshot.get('parsed'),
                        'issues': output_skill_snapshot.get('issues'),
                    }
                ),
                'raw_payload_truncated': 'raw_text' in output_skill_snapshot,
            }
        )

    @staticmethod
    def _output_skill_identity(output_skill_snapshot: Mapping[str, Any]) -> dict[str, Any]:
        return {
            'status': output_skill_snapshot.get('status', 'missing'),
            'files': sorted(str(item) for item in output_skill_snapshot.get('files') or []),
            'payload_hash': _payload_hash(
                {
                    'files': output_skill_snapshot.get('files'),
                    'raw_text': output_skill_snapshot.get('raw_text'),
                    'parsed': output_skill_snapshot.get('parsed'),
                    'issues': output_skill_snapshot.get('issues'),
                }
            ),
        }

    @staticmethod
    def _completed_run_status(
        *,
        source_status: Mapping[str, Any],
        source_errors: Mapping[str, Any],
    ) -> str:
        mes_status = source_status.get('mes')
        hub_status = source_status.get('hub')
        output_status = source_status.get('output_skill')
        if mes_status in {'failed', 'partial_failed'} or hub_status == 'failed':
            return 'completed_with_source_error'
        if source_errors and source_errors != {'output_skill': 'output_skill_source_missing'}:
            return 'completed_with_source_error'
        if hub_status == 'empty' or output_status in {'missing', 'empty', 'unsupported'}:
            return 'completed_with_missing_source'
        return 'completed'

    def _cleanup_failed_handler_side_effects(self, *, existing_new_ids: set[int]) -> None:
        for item in list(self._db.new):
            if id(item) not in existing_new_ids:
                self._db.expunge(item)
        self._db.expire_all()

    @staticmethod
    def _is_controlled_handler(handler: Callable[[Mapping[str, Any]], Mapping[str, Any] | None]) -> bool:
        return bool(getattr(handler, 'hermes_controlled_transaction', False))

    @staticmethod
    def _sync_action_from_payload(
        action: HermesCorrectionAction,
        *,
        audit_run_id: int,
        payload: Mapping[str, Any],
    ) -> None:
        action.audit_run_id = audit_run_id
        action.idempotency_key = str(payload.get('idempotency_key') or '').strip()
        action.action_type = str(payload.get('action_type') or 'unknown')
        action.risk_level = str(payload.get('risk_level') or 'low')
        action.target_table = str(payload.get('target_table') or '')
        action.target_key = str(payload.get('target_key') or '')
        action.field_name = str(payload.get('field_name')) if payload.get('field_name') is not None else None
        action.before_value = _json_safe(payload.get('before_value'))
        action.after_value = _json_safe(payload.get('after_value'))
        action.evidence = _json_safe(payload.get('evidence') or {})
        action.rollback_payload = _json_safe(payload.get('rollback_payload'))

    @staticmethod
    def _normalize_fields(fields: Sequence[str] | None) -> list[str]:
        normalized = [str(field).strip() for field in (fields or []) if str(field).strip()]
        return normalized or list(DEFAULT_AUDIT_FIELDS)

    def _parse_csv_output_skill_file(self, path: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        with path.open('r', encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            for raw_row in reader:
                row: dict[str, Any] = {}
                for header, value in raw_row.items():
                    normalized_header = _CSV_HEADER_ALIASES.get(str(header).strip(), str(header).strip())
                    if value in (None, ''):
                        continue
                    if normalized_header == 'business_date':
                        row['business_date'] = str(value).strip()
                    elif normalized_header in {'output_tons', 'total_output'}:
                        number = _numeric_value(value)
                        if number is not None:
                            row[normalized_header] = number
                    elif normalized_header == 'yield_rate':
                        number = _numeric_value(value)
                        if number is not None:
                            row['yield_rate'] = number
                if row:
                    rows.append(row)
        return {
            'status': 'parsed',
            'source_file': str(path),
            'source_type': 'output_skill_csv',
            'rows': rows,
            'issues': [],
        }

    def _determine_action_status(self, *, action: HermesCorrectionAction, dry_run: bool) -> tuple[str, str | None]:
        if dry_run:
            return 'dry_run', None
        if action.action_type not in SUPPORTED_ACTION_TYPES:
            return 'blocked', 'unsupported_action_type'
        if not self._apply_enabled:
            return 'blocked', 'apply_disabled'
        if action.risk_level.lower() != 'low':
            return 'high_risk_blocked', 'high_risk'
        if self._correction_handler is None:
            return 'blocked', 'handler_missing'
        if not self._is_controlled_handler(self._correction_handler):
            return 'blocked', 'handler_not_controlled'
        return 'executable', None

    @staticmethod
    def _action_payload(action: HermesCorrectionAction) -> dict[str, Any]:
        return {
            'idempotency_key': action.idempotency_key,
            'action_type': action.action_type,
            'risk_level': action.risk_level,
            'target_table': action.target_table,
            'target_key': action.target_key,
            'field_name': action.field_name,
            'before_value': action.before_value,
            'after_value': action.after_value,
            'evidence': action.evidence,
            'rollback_payload': action.rollback_payload,
        }
