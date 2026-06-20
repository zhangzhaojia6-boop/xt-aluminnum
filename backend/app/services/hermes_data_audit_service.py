from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.business_time import production_business_window
from app.core.redaction import filter_sensitive_mapping, redact_secret_text
from app.models import ChatInboxMessage, MasterCodeAlias, RagDocument, RagSourceIngestion
from app.models.hermes_data_audit import HermesCorrectionAction, HermesDataAuditRun
from app.services.mapping_reconciliation_service import PARSEABLE_REFERENCE_EXTENSIONS, parse_output_skill_reference_file


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
ACTION_TARGET_TABLE_ALLOWLIST = {
    'mapping_alias_upsert': {'master_code_aliases'},
    'mapping_field_rule_upsert': {'mapping_field_rules'},
    'mapping_reconciliation_run': {'mapping_reconciliation_runs', 'data_hub_snapshot'},
    'daily_report_recalculate': {'daily_report_runs'},
}
REAL_APPLY_EXECUTOR_ACTIONS = {'mapping_alias_upsert'}
REUSABLE_ACTION_STATUSES = {'pending', 'dry_run'}
SAME_RUN_RETRYABLE_ACTION_STATUSES = REUSABLE_ACTION_STATUSES | {
    'failed',
    'blocked',
    'high_risk_blocked',
    'blocked_duplicate',
}
RERUN_REQUIRED_AUDIT_STATUSES = {'corrected', 'correction_partial_failed'}

TEXT_RAW_EXTENSIONS = {'.txt', '.md', '.log'}
CSV_EXTENSIONS = {'.csv'}
OUTPUT_SKILL_ALLOWED_EXTENSIONS = set(PARSEABLE_REFERENCE_EXTENSIONS) | CSV_EXTENSIONS
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
_AUDIT_HEAVY_KEY_TOKENS = {'raw', 'raw_text', 'records', 'rows', 'items', 'payload', 'content'}
_AUDIT_SAFE_ROOT_KEYS = {'before_value', 'after_value', 'evidence', 'rollback_payload'}
_AUDIT_PRESERVE_STRUCTURE_KEYS = {
    'before_value',
    'after_value',
    'evidence',
    'rollback_payload',
    'restore_before_value',
    'values',
}
_AUDIT_TEXT_SAMPLE_LIMIT = 160
_AUDIT_INLINE_TEXT_LIMIT = 200
_AUDIT_MAPPING_SUMMARY_LIMIT = 8
_AUDIT_LIST_SUMMARY_LIMIT = 4
_AUDIT_SAMPLE_ITEM_LIMIT = 2
_EVIDENCE_PRESERVE_KEYS = {'reason', 'source', 'field', 'field_name', 'evidence_ref', 'values'}
_ROLLBACK_PRESERVE_KEYS = {
    'mode',
    'reason',
    'restore_before_value',
    'rollback_available',
    'rollback_unavailable_reason',
}
_AUDIT_NESTED_MERGE_KEYS = {'values', 'restore_before_value'}
_DINGTALK_EVIDENCE_LIMIT = 5
_PRIMARY_AUDIT_SOURCE_ERROR_KEYS = {'mes', 'hub', 'output_skill'}


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


def _payload_sha256(value: Any) -> str:
    encoded = json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _iso_datetime(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if value in (None, ''):
        return None
    return redact_secret_text(str(value))


def _coerce_datetime(value: Any, *, fallback_tz: Any = None) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None and fallback_tz is not None:
            return value.replace(tzinfo=fallback_tz)
        return value
    if value in (None, ''):
        return None
    if isinstance(value, (int, float)):
        raw_value = float(value)
        if raw_value > 10**12:
            raw_value /= 1000.0
        return datetime.fromtimestamp(raw_value, tz=fallback_tz or timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        numeric_value = float(text)
    except ValueError:
        numeric_value = None
    if numeric_value is not None:
        if numeric_value > 10**12:
            numeric_value /= 1000.0
        return datetime.fromtimestamp(numeric_value, tz=fallback_tz or timezone.utc)
    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None and fallback_tz is not None:
        return parsed.replace(tzinfo=fallback_tz)
    return parsed


def _redacted_sample_text(value: Any, *, limit: int = _AUDIT_TEXT_SAMPLE_LIMIT) -> str:
    redacted = redact_secret_text(str(value or ''))
    sample = redacted[:limit]
    if '<redacted>' in redacted and '<redacted>' not in sample:
        marker = ' <redacted>'
        sample = f"{sample[: max(limit - len(marker), 0)]}{marker}"
    return sample


def _iter_string_values(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        items: list[str] = []
        for nested in value.values():
            items.extend(_iter_string_values(nested))
        return items
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for nested in value:
            items.extend(_iter_string_values(nested))
        return items
    if value in (None, ''):
        return []
    return [str(value)]


def _contains_dingtalk_marker(*values: Any) -> bool:
    return any('dingtalk' in item.lower() for value in values for item in _iter_string_values(value))


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


def _is_high_risk_audit_key(field_name: str | None) -> bool:
    if field_name is None:
        return False
    normalized = str(field_name).strip().lower()
    if normalized in _AUDIT_SAFE_ROOT_KEYS:
        return False
    if normalized in _AUDIT_HEAVY_KEY_TOKENS:
        return True
    tokens = [token for token in re.split(r'[^a-z0-9]+', normalized) if token]
    return any(token in _AUDIT_HEAVY_KEY_TOKENS for token in tokens)


def _summarize_audit_text(value: str) -> dict[str, Any]:
    redacted = redact_secret_text(value)
    sample = redacted[:_AUDIT_TEXT_SAMPLE_LIMIT]
    if '<redacted>' in redacted and '<redacted>' not in sample:
        marker = ' <redacted>'
        sample = f"{sample[: max(_AUDIT_TEXT_SAMPLE_LIMIT - len(marker), 0)]}{marker}"
    return {
        'summary_type': 'text',
        'length': len(redacted),
        'sha256': hashlib.sha256(redacted.encode('utf-8')).hexdigest(),
        'sample': sample,
        'summarized': True,
        'truncated': len(redacted) > _AUDIT_TEXT_SAMPLE_LIMIT,
    }


def _should_preserve_audit_mapping_structure(field_name: str | None) -> bool:
    if field_name is None:
        return False
    return str(field_name).strip().lower() in _AUDIT_PRESERVE_STRUCTURE_KEYS


def _slim_correction_audit_value(value: Any, *, field_name: str | None = None, depth: int = 0) -> Any:
    safe_value = _json_safe(value)
    if isinstance(safe_value, Mapping):
        preserve_mapping_structure = _should_preserve_audit_mapping_structure(field_name)
        if not preserve_mapping_structure and (_is_high_risk_audit_key(field_name) or len(safe_value) > _AUDIT_MAPPING_SUMMARY_LIMIT):
            sample: dict[str, Any] = {}
            for index, (key, item) in enumerate(safe_value.items()):
                if index >= _AUDIT_SAMPLE_ITEM_LIMIT:
                    break
                sample[str(key)] = _slim_correction_audit_value(item, field_name=str(key), depth=depth + 1)
            return {
                'summary_type': 'mapping',
                'count': len(safe_value),
                'sha256': _payload_sha256(safe_value),
                'sample': sample,
                'summarized': True,
            }
        return {
            str(key): _slim_correction_audit_value(item, field_name=str(key), depth=depth + 1)
            for key, item in safe_value.items()
        }
    if isinstance(safe_value, list):
        if _is_high_risk_audit_key(field_name) or len(safe_value) > _AUDIT_LIST_SUMMARY_LIMIT:
            return {
                'summary_type': 'list',
                'count': len(safe_value),
                'sha256': _payload_sha256(safe_value),
                'sample': [
                    _slim_correction_audit_value(item, depth=depth + 1)
                    for item in safe_value[:_AUDIT_SAMPLE_ITEM_LIMIT]
                ],
                'summarized': True,
            }
        return [_slim_correction_audit_value(item, depth=depth + 1) for item in safe_value]
    if isinstance(safe_value, str):
        redacted = redact_secret_text(safe_value)
        if _is_high_risk_audit_key(field_name) or len(redacted) > _AUDIT_INLINE_TEXT_LIMIT:
            return _summarize_audit_text(redacted)
        return redacted
    return safe_value


def _is_empty_audit_merge_value(value: Any) -> bool:
    return value in (None, '', {}, [])


def _merge_nested_audit_mapping(original: Mapping[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
    merged = {str(key): _json_safe(item) for key, item in original.items()}
    for key, item in incoming.items():
        normalized_key = str(key)
        safe_item = _json_safe(item)
        existing_item = merged.get(normalized_key)
        if isinstance(existing_item, Mapping) and isinstance(safe_item, Mapping):
            merged[normalized_key] = _merge_nested_audit_mapping(existing_item, safe_item)
            continue
        if _is_empty_audit_merge_value(safe_item) and not _is_empty_audit_merge_value(existing_item):
            continue
        merged[normalized_key] = safe_item
    return merged


def _merge_audit_metadata_mapping(
    original: Any,
    incoming: Any,
    *,
    preserve_keys: set[str],
) -> Any:
    safe_incoming = _json_safe(incoming)
    if not isinstance(safe_incoming, Mapping):
        return safe_incoming
    if not safe_incoming:
        return {}

    safe_original = _json_safe(original or {})
    if not isinstance(safe_original, Mapping):
        safe_original = {}

    merged = {str(key): item for key, item in safe_original.items()}
    for key, item in safe_incoming.items():
        normalized_key = str(key)
        safe_item = _json_safe(item)
        existing_item = merged.get(normalized_key)
        if (
            normalized_key in _AUDIT_NESTED_MERGE_KEYS
            and isinstance(existing_item, Mapping)
            and isinstance(safe_item, Mapping)
        ):
            merged[normalized_key] = _merge_nested_audit_mapping(existing_item, safe_item)
            continue
        if normalized_key in preserve_keys and _is_empty_audit_merge_value(safe_item) and not _is_empty_audit_merge_value(
            existing_item
        ):
            continue
        merged[normalized_key] = safe_item
    return merged


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
        if business_date is None:
            raise ValueError('business_date is required')
        normalized_fields = self._normalize_fields(fields)
        now = datetime.now(timezone.utc)
        mes_result, hub_snapshot, hub_status, hub_error, output_skill_snapshot = self._collect_sources(
            business_date=business_date,
            fields=normalized_fields,
            mes_query_keys=mes_query_keys,
        )
        dingtalk_evidence = self._read_dingtalk_evidence(business_date=business_date)
        safe_dingtalk_evidence = {
            source_name: {key: value for key, value in payload.items() if key != 'error'}
            for source_name, payload in dingtalk_evidence.items()
        }
        mes_field_values = self._extract_mes_field_values(mes_result.get('records', {}), normalized_fields)
        hub_field_values = self._extract_direct_field_values(hub_snapshot, normalized_fields)
        output_field_values = self._extract_direct_field_values(output_skill_snapshot.get('parsed', {}), normalized_fields)

        source_status = {
            'mes': mes_result.get('source_status', {}).get('mes', 'empty'),
            'hub': hub_status,
            'output_skill': output_skill_snapshot.get('status', 'missing'),
            'mes_sources': mes_result.get('source_status', {}).get('sources', {}),
            'dingtalk_text': dingtalk_evidence.get('dingtalk_text', {}).get('status', 'empty'),
            'dingtalk_file': dingtalk_evidence.get('dingtalk_file', {}).get('status', 'empty'),
            'dingtalk_evidence': safe_dingtalk_evidence,
        }
        source_errors = self._merge_source_errors(
            mes_errors=mes_result.get('source_errors', {}),
            hub_error=hub_error,
            output_skill_snapshot=output_skill_snapshot,
            dingtalk_errors={
                source_name: payload.get('error')
                for source_name, payload in dingtalk_evidence.items()
                if source_name in {'dingtalk_text', 'dingtalk_file'} and payload.get('error')
            },
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
            dingtalk_evidence_identity={
                'dingtalk_text': {
                    'status': dingtalk_evidence.get('dingtalk_text', {}).get('status'),
                    'payload_hash': dingtalk_evidence.get('dingtalk_text', {}).get('payload_hash'),
                },
                'dingtalk_file': {
                    'status': dingtalk_evidence.get('dingtalk_file', {}).get('status'),
                    'payload_hash': dingtalk_evidence.get('dingtalk_file', {}).get('payload_hash'),
                },
            },
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
        planned_idempotency_keys: list[str] = []

        if not dry_run and run.status in RERUN_REQUIRED_AUDIT_STATUSES:
            summary['reason'] = 'rerun_audit_required'
            for payload in actions:
                idempotency_key = str(payload.get('idempotency_key') or '').strip()
                if not idempotency_key:
                    raise ValueError('idempotency_key is required')
                summary['blocked_count'] += 1
                summary['action_statuses'].append(
                    {
                        'idempotency_key': idempotency_key,
                        'status': 'blocked',
                        'reason': 'rerun_audit_required',
                    }
                )
            return summary

        if dry_run:
            for payload in actions:
                idempotency_key = str(payload.get('idempotency_key') or '').strip()
                if not idempotency_key:
                    raise ValueError('idempotency_key is required')
                existing = (
                    self._db.query(HermesCorrectionAction)
                    .filter(HermesCorrectionAction.idempotency_key == idempotency_key)
                    .one_or_none()
                )
                duplicate_status = self._duplicate_action_status(
                    audit_run_id=audit_run_id,
                    idempotency_key=idempotency_key,
                    existing=existing,
                )
                if duplicate_status is not None:
                    self._record_preview_status(summary=summary, status_entry=duplicate_status)
                    continue

                preview_action = HermesCorrectionAction(
                    audit_run_id=audit_run_id,
                    idempotency_key=idempotency_key,
                    rollback_status='not_requested',
                )
                self._sync_action_from_payload(preview_action, audit_run_id=audit_run_id, payload=payload)
                status, blocked_reason = self._determine_action_status(action=preview_action, dry_run=True)
                if status == 'executable':
                    summary['dry_run_count'] += 1
                    summary['action_statuses'].append({'idempotency_key': idempotency_key, 'status': 'dry_run'})
                    continue

                status_entry = {'idempotency_key': idempotency_key, 'status': status}
                if blocked_reason:
                    status_entry['reason'] = blocked_reason
                self._record_preview_status(summary=summary, status_entry=status_entry)
            return summary

        for payload in actions:
            idempotency_key = str(payload.get('idempotency_key') or '').strip()
            if not idempotency_key:
                raise ValueError('idempotency_key is required')

            existing = (
                self._db.query(HermesCorrectionAction)
                .filter(HermesCorrectionAction.idempotency_key == idempotency_key)
                .one_or_none()
            )
            duplicate_status = self._duplicate_action_status(
                audit_run_id=audit_run_id,
                idempotency_key=idempotency_key,
                existing=existing,
            )
            if duplicate_status is not None:
                self._record_preview_status(summary=summary, status_entry=duplicate_status)
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
            planned_idempotency_keys.append(idempotency_key)
            if is_new_action:
                summary['created_count'] += 1

        planned_actions = []
        if planned_idempotency_keys:
            planned_actions = (
                self._db.query(HermesCorrectionAction)
                .filter(HermesCorrectionAction.audit_run_id == audit_run_id)
                .filter(HermesCorrectionAction.idempotency_key.in_(planned_idempotency_keys))
                .order_by(HermesCorrectionAction.id.asc())
                .all()
            )

        executable_actions: list[HermesCorrectionAction] = []
        batch_has_non_executable_action = False
        for action in planned_actions:
            status, blocked_reason = self._determine_action_status(action=action, dry_run=dry_run)
            if status == 'executable':
                executable_actions.append(action)
                continue
            batch_has_non_executable_action = True
            action.status = status
            if blocked_reason:
                action.evidence = {**(action.evidence or {}), 'blocked_reason': blocked_reason}
            if status == 'dry_run':
                summary['dry_run_count'] += 1
            elif 'blocked' in status:
                summary['blocked_count'] += 1
                if blocked_reason and summary['reason'] is None:
                    summary['reason'] = blocked_reason
            status_entry = {'idempotency_key': action.idempotency_key, 'status': status}
            if blocked_reason:
                status_entry['reason'] = blocked_reason
            summary['action_statuses'].append(status_entry)

        batch_has_gate_issue = batch_has_non_executable_action
        if not dry_run and executable_actions and batch_has_gate_issue:
            if summary['reason'] is None:
                summary['reason'] = 'batch_not_all_executable'
            for action in executable_actions:
                action.status = 'blocked'
                action.evidence = {**(action.evidence or {}), 'blocked_reason': 'batch_not_all_executable'}
                summary['blocked_count'] += 1
                summary['action_statuses'].append(
                    {'idempotency_key': action.idempotency_key, 'status': 'blocked'}
                )
            executable_actions = []

        if not dry_run and executable_actions:
            handler_new_ids = {id(item) for item in self._db.new}
            savepoint = self._db.begin_nested()
            execution_results: dict[str, Mapping[str, Any]] = {}
            projected_actions: dict[str, HermesCorrectionAction] = {}
            batch_error: str | None = None
            try:
                for action in executable_actions:
                    execution_result = _json_safe(self._execute_correction_action(action) or {})
                    execution_results[action.idempotency_key] = (
                        execution_result if isinstance(execution_result, Mapping) else {}
                    )
                for action in executable_actions:
                    projected_action = self._project_action_with_execution_result(
                        action=action,
                        execution_result=execution_results.get(action.idempotency_key, {}),
                    )
                    projected_actions[action.idempotency_key] = projected_action
                    if not self._has_complete_correction_audit_payload(projected_action):
                        raise ValueError('invalid_executor_audit_payload')
                savepoint.commit()
            except Exception as exc:
                savepoint.rollback()
                self._cleanup_failed_handler_side_effects(existing_new_ids=handler_new_ids)
                if str(exc) == 'invalid_executor_audit_payload':
                    batch_error = 'invalid_executor_audit_payload'
                else:
                    batch_error = redact_secret_text(str(exc))

            if batch_error is not None:
                for action in executable_actions:
                    action.status = 'failed'
                    action.evidence = {**(action.evidence or {}), 'error': batch_error}
                    summary['failed_count'] += 1
                    summary['action_statuses'].append({'idempotency_key': action.idempotency_key, 'status': 'failed'})
            else:
                for action in executable_actions:
                    projected_action = projected_actions[action.idempotency_key]
                    if projected_action.before_value is not None:
                        action.before_value = _slim_correction_audit_value(
                            projected_action.before_value,
                            field_name='before_value',
                        )
                    if projected_action.after_value is not None:
                        action.after_value = _slim_correction_audit_value(
                            projected_action.after_value,
                            field_name='after_value',
                        )
                    if projected_action.evidence is not None:
                        action.evidence = _slim_correction_audit_value(
                            projected_action.evidence,
                            field_name='evidence',
                        )
                    if projected_action.rollback_payload is not None:
                        action.rollback_payload = _slim_correction_audit_value(
                            projected_action.rollback_payload,
                            field_name='rollback_payload',
                        )
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

    def _read_dingtalk_evidence(self, *, business_date: date) -> dict[str, Any]:
        text_items, text_status, text_error = self._read_dingtalk_text_evidence(business_date=business_date)
        file_items, file_status, file_error = self._read_dingtalk_file_evidence(business_date=business_date)
        return {
            'dingtalk_text': {
                'status': text_status,
                'count': len(text_items),
                'items': text_items,
                'payload_hash': _payload_hash(text_items),
                'error': text_error,
            },
            'dingtalk_file': {
                'status': file_status,
                'count': len(file_items),
                'items': file_items,
                'payload_hash': _payload_hash(file_items),
                'error': file_error,
            },
        }

    def _read_dingtalk_text_evidence(self, *, business_date: date) -> tuple[list[dict[str, Any]], str, str | None]:
        window_start, window_end = production_business_window(business_date)
        candidate_start = window_start - timedelta(days=1)
        candidate_end = window_end + timedelta(days=1)
        try:
            rows = (
                self._db.query(ChatInboxMessage)
                .filter(
                    ChatInboxMessage.channel == 'dingtalk_group',
                    ChatInboxMessage.created_at >= candidate_start,
                    ChatInboxMessage.created_at < candidate_end,
                )
                .order_by(ChatInboxMessage.created_at.desc(), ChatInboxMessage.id.desc())
                .limit(_DINGTALK_EVIDENCE_LIMIT * 4)
                .all()
            )
        except Exception as exc:
            return [], 'failed', redact_secret_text(str(exc))

        items: list[dict[str, Any]] = []
        for row in rows:
            sent_at = self._dingtalk_message_datetime(row, fallback_tz=window_start.tzinfo)
            if sent_at is None or sent_at < window_start or sent_at >= window_end:
                continue
            redacted_text = redact_secret_text(row.text or '')
            items.append(
                {
                    'source': 'dingtalk_text',
                    'channel': redact_secret_text(row.channel or ''),
                    'group_id': redact_secret_text(row.group_id or '') or None,
                    'trace_id': redact_secret_text(row.trace_id or ''),
                    'sender_external_id': redact_secret_text(row.sender_external_id or '') or None,
                    'sent_at': _iso_datetime(sent_at),
                    'created_at': _iso_datetime(row.created_at),
                    'text_sample': _redacted_sample_text(redacted_text),
                    'text_hash': hashlib.sha256(redacted_text.encode('utf-8')).hexdigest(),
                }
            )
            if len(items) >= _DINGTALK_EVIDENCE_LIMIT:
                break
        return items, 'ok' if items else 'empty', None

    def _read_dingtalk_file_evidence(self, *, business_date: date) -> tuple[list[dict[str, Any]], str, str | None]:
        window_start, window_end = production_business_window(business_date)
        try:
            rows = (
                self._db.query(RagDocument, RagSourceIngestion)
                .join(RagSourceIngestion, RagSourceIngestion.document_id == RagDocument.id)
                .filter(
                    RagDocument.status == 'active',
                    RagSourceIngestion.status == 'active',
                    RagSourceIngestion.created_at >= window_start,
                    RagSourceIngestion.created_at < window_end,
                )
                .order_by(RagSourceIngestion.created_at.desc(), RagSourceIngestion.id.desc(), RagDocument.id.desc())
                .limit(_DINGTALK_EVIDENCE_LIMIT * 2)
                .all()
            )
        except Exception as exc:
            return [], 'failed', redact_secret_text(str(exc))

        items: list[dict[str, Any]] = []
        seen_document_ids: set[int] = set()
        for document, ingestion in rows:
            if document.id in seen_document_ids:
                continue
            if not self._is_dingtalk_file_document(document=document, ingestion=ingestion):
                continue
            seen_document_ids.add(document.id)
            source_type = self._dingtalk_source_type(document=document, ingestion=ingestion)
            source_ref = self._dingtalk_source_ref(document=document, ingestion=ingestion)
            items.append(
                {
                    'source': 'dingtalk_file',
                    'document_id': document.id,
                    'filename': redact_secret_text(document.filename),
                    'source_name': redact_secret_text(document.source_name),
                    'file_size': document.file_size,
                    'created_at': _iso_datetime(document.created_at),
                    'source_ref': source_ref,
                    'source_type': source_type,
                }
            )
            if len(items) >= _DINGTALK_EVIDENCE_LIMIT:
                break
        return items, 'ok' if items else 'empty', None

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

        matched_files = [path for path in matched_files if self._is_allowed_output_skill_extension(path)]
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

        if 'failed' in statuses:
            status = 'failed'
        elif 'parsed' in statuses:
            status = 'parsed'
        elif 'unsupported' in statuses:
            status = 'unsupported'
        else:
            status = 'empty'

        if status == 'parsed' and not combined_fields and not raw_text_parts:
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

        try:
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
        except Exception as exc:
            return {
                'status': 'failed',
                'files': [str(resolved_path)],
                'raw_text': '',
                'parsed': {},
                'issues': [
                    {
                        'code': 'output_skill_parse_failed',
                        'message': redact_secret_text(str(exc)),
                    }
                ],
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
                'rollback_payload': {
                    'mode': 'manual',
                    'reason': 'hub_snapshot_reconciliation_requires_manual_restore',
                    'restore_before_value': {'hub': values.get('hub')},
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
        dingtalk_errors: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        source_errors: dict[str, Any] = {}
        if mes_errors:
            source_errors['mes'] = _redact_issue_payload(mes_errors)
        if hub_error:
            source_errors['hub'] = hub_error
        for source_name, error in (dingtalk_errors or {}).items():
            if error:
                source_errors[str(source_name)] = redact_secret_text(str(error))
        output_status = output_skill_snapshot.get('status')
        output_issues = output_skill_snapshot.get('issues') or []
        if output_status == 'missing':
            source_errors['output_skill'] = 'output_skill_source_missing'
        elif output_status == 'unsupported':
            source_errors['output_skill'] = _redact_issue_payload(output_issues)
        elif output_issues:
            source_errors['output_skill'] = _redact_issue_payload(output_issues)
        return source_errors

    @staticmethod
    def _dingtalk_message_datetime(message: ChatInboxMessage, *, fallback_tz: Any = None) -> datetime | None:
        payload = message.source_payload or {}
        for key in ('sent_at', 'sentAt', 'message_time', 'messageTime', 'msgTime', 'timestamp'):
            if key in payload and payload[key] not in (None, ''):
                parsed = _coerce_datetime(payload[key], fallback_tz=fallback_tz)
                if parsed is not None:
                    return parsed
        return _coerce_datetime(message.created_at, fallback_tz=fallback_tz)

    @staticmethod
    def _is_dingtalk_file_document(*, document: RagDocument, ingestion: RagSourceIngestion | None) -> bool:
        if ingestion is None or ingestion.status != 'active':
            return False
        return _contains_dingtalk_marker(
            getattr(ingestion, 'source_type', None),
            getattr(ingestion, 'source_ref', None),
            getattr(ingestion, 'metadata_payload', None),
        )

    @staticmethod
    def _dingtalk_source_type(*, document: RagDocument, ingestion: RagSourceIngestion | None) -> str | None:
        if ingestion is not None and ingestion.source_type:
            return redact_secret_text(ingestion.source_type)
        metadata_payload = document.metadata_payload or {}
        source_type = metadata_payload.get('source_type') or metadata_payload.get('source')
        if source_type in (None, ''):
            return None
        return redact_secret_text(str(source_type))

    @staticmethod
    def _dingtalk_source_ref(*, document: RagDocument, ingestion: RagSourceIngestion | None) -> str | None:
        if ingestion is not None and ingestion.source_ref:
            return redact_secret_text(ingestion.source_ref)
        metadata_payload = document.metadata_payload or {}
        source_ref = metadata_payload.get('source_ref')
        if source_ref in (None, ''):
            return None
        return redact_secret_text(str(source_ref))

    def _output_skill_root_path(self) -> Path | None:
        raw_value = self._output_skill_root or os.getenv('OUTPUT_SKILL_ROOT')
        if raw_value is None or str(raw_value).strip() == '':
            return None
        return Path(raw_value)

    @staticmethod
    def _is_allowed_output_skill_extension(path: Path) -> bool:
        return path.suffix.lower() in OUTPUT_SKILL_ALLOWED_EXTENSIONS

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
        dingtalk_evidence_identity: Mapping[str, Any] | None = None,
    ) -> str:
        payload = {
            'business_date': business_date.isoformat(),
            'fields': _stable_string_list(fields),
            'mes_query_keys': _stable_string_list(mes_query_keys or DEFAULT_MES_QUERY_KEYS),
            'mes_snapshot_hash': (mes_snapshot or {}).get('payload_hash'),
            'hub_source_identity': {
                'status': (hub_snapshot or {}).get('status'),
                'source_errors': (hub_snapshot or {}).get('source_errors'),
                'payload_hash': (hub_snapshot or {}).get('payload_hash'),
            },
            'output_skill_identity': _json_safe(output_skill_identity or {}),
            'dingtalk_evidence_identity': _json_safe(dingtalk_evidence_identity or {}),
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
        source_identity = {
            'snapshot': hub_snapshot,
            'status': hub_status,
            'source_errors': hub_error,
        }
        return _redact_issue_payload(
            {
                'status': hub_status,
                'field_values': field_values,
                'source_errors': hub_error,
                'field_count': len(hub_snapshot),
                'payload_hash': _payload_hash(source_identity),
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
        primary_source_errors = {
            key: value
            for key, value in (source_errors or {}).items()
            if key in _PRIMARY_AUDIT_SOURCE_ERROR_KEYS
        }
        if mes_status in {'failed', 'partial_failed'} or hub_status == 'failed':
            return 'completed_with_source_error'
        if primary_source_errors and primary_source_errors != {'output_skill': 'output_skill_source_missing'}:
            return 'completed_with_source_error'
        if mes_status == 'empty' or hub_status == 'empty' or output_status in {'missing', 'empty', 'unsupported'}:
            return 'completed_with_missing_source'
        return 'completed'

    def _cleanup_failed_handler_side_effects(self, *, existing_new_ids: set[int]) -> None:
        for item in list(self._db.new):
            if id(item) not in existing_new_ids:
                self._db.expunge(item)
        self._db.expire_all()

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
        action.risk_level = str(payload.get('risk_level') or '').strip()
        action.target_table = str(payload.get('target_table') or '')
        action.target_key = str(payload.get('target_key') or '')
        action.field_name = str(payload.get('field_name')) if payload.get('field_name') is not None else None
        action.before_value = _slim_correction_audit_value(payload.get('before_value'), field_name='before_value')
        action.after_value = _slim_correction_audit_value(payload.get('after_value'), field_name='after_value')
        action.evidence = _slim_correction_audit_value(payload.get('evidence') or {}, field_name='evidence')
        action.rollback_payload = _slim_correction_audit_value(
            payload.get('rollback_payload'),
            field_name='rollback_payload',
        )

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
        if action.action_type not in SUPPORTED_ACTION_TYPES:
            return 'blocked', 'unsupported_action_type'
        if not action.risk_level:
            return 'blocked', 'missing_risk_level'
        if not self._is_allowed_target_for_action(action.action_type, action.target_table):
            if str(action.target_table).strip().startswith('mes_'):
                return 'blocked', 'mes_target_read_only'
            return 'blocked', 'target_table_not_allowed_for_action'
        if not self._has_complete_correction_audit_payload(action):
            return 'blocked', 'incomplete_correction_audit_payload'
        if not self._has_internal_executor(action.action_type):
            return 'blocked', 'executor_not_supported'
        if action.risk_level.lower() != 'low':
            return 'high_risk_blocked', 'high_risk'
        if not dry_run and not self._apply_enabled:
            return 'blocked', 'apply_disabled'
        return 'executable', None

    @staticmethod
    def _is_reusable_action_status(status: str | None) -> bool:
        return str(status or '').strip() in REUSABLE_ACTION_STATUSES

    @staticmethod
    def _is_same_run_retryable_action_status(status: str | None) -> bool:
        return str(status or '').strip() in SAME_RUN_RETRYABLE_ACTION_STATUSES

    def _duplicate_action_status(
        self,
        *,
        audit_run_id: int,
        idempotency_key: str,
        existing: HermesCorrectionAction | None,
    ) -> dict[str, Any] | None:
        if existing is None:
            return None
        same_run = existing.audit_run_id == audit_run_id
        if same_run and self._is_same_run_retryable_action_status(existing.status):
            return None
        if same_run:
            return {
                'idempotency_key': idempotency_key,
                'status': 'skipped_duplicate',
            }
        if self._is_reusable_action_status(existing.status):
            return {
                'idempotency_key': idempotency_key,
                'status': 'blocked_duplicate',
                'reason': 'duplicate_in_other_run_pending',
                'existing_audit_run_id': existing.audit_run_id,
                'existing_action_status': existing.status,
            }
        return {
            'idempotency_key': idempotency_key,
            'status': 'skipped_duplicate',
            'reason': 'duplicate_in_other_run_terminal',
            'existing_audit_run_id': existing.audit_run_id,
            'existing_action_status': existing.status,
        }

    @staticmethod
    def _record_preview_status(
        *,
        summary: dict[str, Any],
        status_entry: Mapping[str, Any],
    ) -> None:
        summary['action_statuses'].append(dict(status_entry))
        status = str(status_entry.get('status') or '').strip()
        reason = status_entry.get('reason')
        if status == 'dry_run':
            summary['dry_run_count'] += 1
            return
        if status == 'skipped_duplicate':
            summary['skipped_count'] += 1
            return
        if 'blocked' in status:
            summary['blocked_count'] += 1
            if reason and summary['reason'] is None:
                summary['reason'] = str(reason)

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

    @staticmethod
    def _project_action_with_execution_result(
        *,
        action: HermesCorrectionAction,
        execution_result: Mapping[str, Any],
    ) -> HermesCorrectionAction:
        projected = HermesCorrectionAction(
            audit_run_id=action.audit_run_id,
            idempotency_key=action.idempotency_key,
            action_type=action.action_type,
            risk_level=action.risk_level,
            target_table=action.target_table,
            target_key=action.target_key,
            field_name=action.field_name,
            before_value=action.before_value,
            after_value=action.after_value,
            evidence=action.evidence,
            rollback_payload=action.rollback_payload,
            rollback_status=action.rollback_status,
            status=action.status,
        )
        if 'before_value' in execution_result:
            projected.before_value = _merge_audit_metadata_mapping(
                action.before_value,
                execution_result.get('before_value'),
                preserve_keys=set(),
            )
        if 'after_value' in execution_result:
            projected.after_value = _merge_audit_metadata_mapping(
                action.after_value,
                execution_result.get('after_value'),
                preserve_keys=set(),
            )
        if 'evidence' in execution_result:
            projected.evidence = _merge_audit_metadata_mapping(
                action.evidence,
                execution_result.get('evidence'),
                preserve_keys=_EVIDENCE_PRESERVE_KEYS,
            )
        if 'rollback_payload' in execution_result:
            projected.rollback_payload = _merge_audit_metadata_mapping(
                action.rollback_payload,
                execution_result.get('rollback_payload'),
                preserve_keys=_ROLLBACK_PRESERVE_KEYS,
            )
        return projected

    @staticmethod
    def _has_internal_executor(action_type: str | None) -> bool:
        return str(action_type or '').strip() in REAL_APPLY_EXECUTOR_ACTIONS

    def _execute_correction_action(self, action: HermesCorrectionAction) -> Mapping[str, Any]:
        if action.action_type == 'mapping_alias_upsert':
            return self._execute_mapping_alias_upsert(action)
        raise ValueError('executor_not_supported')

    def _execute_mapping_alias_upsert(self, action: HermesCorrectionAction) -> Mapping[str, Any]:
        after_value = action.after_value or {}
        if not isinstance(after_value, Mapping):
            raise ValueError('invalid_after_value')

        entity_type = str(after_value.get('entity_type') or '').strip()
        canonical_code = str(after_value.get('canonical_code') or '').strip()
        alias_code = str(after_value.get('alias_code') or '').strip()
        source_type = str(after_value.get('source_type') or 'hermes').strip() or 'hermes'
        alias_name_raw = after_value.get('alias_name')
        alias_name = str(alias_name_raw).strip() if alias_name_raw not in (None, '') else None
        is_active_raw = after_value.get('is_active', True)
        if isinstance(is_active_raw, str):
            is_active = is_active_raw.strip().lower() in _TRUE_VALUES
        else:
            is_active = bool(is_active_raw)

        missing_fields = [
            field_name
            for field_name, value in (
                ('entity_type', entity_type),
                ('canonical_code', canonical_code),
                ('alias_code', alias_code),
            )
            if not value
        ]
        if missing_fields:
            raise ValueError(f"missing_after_value_fields:{','.join(missing_fields)}")

        alias_row = (
            self._db.query(MasterCodeAlias)
            .filter(MasterCodeAlias.entity_type == entity_type)
            .filter(MasterCodeAlias.alias_code == alias_code)
            .filter(MasterCodeAlias.source_type == source_type)
            .one_or_none()
        )
        operation = 'update' if alias_row is not None else 'insert'
        before_value = self._serialize_master_code_alias(alias_row) if alias_row is not None else None
        if alias_row is None:
            alias_row = MasterCodeAlias(
                entity_type=entity_type,
                canonical_code=canonical_code,
                alias_code=alias_code,
                alias_name=alias_name,
                source_type=source_type,
                is_active=is_active,
            )
            self._db.add(alias_row)
        else:
            alias_row.canonical_code = canonical_code
            alias_row.alias_name = alias_name
            alias_row.is_active = is_active

        self._db.flush()

        restore_before_value = before_value or {
            'record_existed': False,
            'entity_type': entity_type,
            'alias_code': alias_code,
            'source_type': source_type,
        }
        return {
            'before_value': restore_before_value,
            'after_value': self._serialize_master_code_alias(alias_row),
            'evidence': {
                'executor': 'mapping_alias_upsert',
                'operation': operation,
                'table': 'master_code_aliases',
                'row_id': alias_row.id,
            },
            'rollback_payload': {
                'mode': 'manual',
                'reason': 'restore alias before audit correction',
                'executor': 'mapping_alias_upsert',
                'table': 'master_code_aliases',
                'restore_before_value': restore_before_value,
                'rollback_available': True,
                'rollback_unavailable_reason': '',
            },
        }

    @staticmethod
    def _serialize_master_code_alias(alias_row: MasterCodeAlias | None) -> dict[str, Any]:
        if alias_row is None:
            return {}
        return {
            'id': alias_row.id,
            'entity_type': alias_row.entity_type,
            'canonical_code': alias_row.canonical_code,
            'alias_code': alias_row.alias_code,
            'alias_name': alias_row.alias_name,
            'source_type': alias_row.source_type,
            'is_active': alias_row.is_active,
            'record_existed': True,
        }

    @staticmethod
    def _has_complete_correction_audit_payload(action: HermesCorrectionAction) -> bool:
        if not action.idempotency_key or not action.target_table or not action.target_key:
            return False
        if not action.risk_level:
            return False
        if action.before_value in (None, {}) or action.after_value in (None, {}):
            return False
        evidence = action.evidence
        if evidence in (None, {}) or not isinstance(evidence, Mapping):
            return False
        if not any(
            evidence.get(key) not in (None, '', {}, [])
            for key in ('reason', 'source', 'evidence_ref', 'field', 'field_name', 'values', 'handler')
        ):
            return False
        rollback_payload = action.rollback_payload
        if rollback_payload in (None, {}):
            return False
        if isinstance(rollback_payload, Mapping):
            if rollback_payload.get('restore_before_value') not in (None, {}):
                return True
            if rollback_payload.get('reason') or rollback_payload.get('mode') == 'not_available':
                return True
            rollback_unavailable_reason = str(rollback_payload.get('rollback_unavailable_reason') or '').strip()
            rollback_available = rollback_payload.get('rollback_available')
            rollback_available_false = rollback_available is False or (
                isinstance(rollback_available, str) and rollback_available.strip().lower() == 'false'
            )
            if rollback_available_false and rollback_unavailable_reason:
                return True
            return False
        return True

    @staticmethod
    def _is_allowed_target_for_action(action_type: str | None, target_table: str | None) -> bool:
        normalized_action = str(action_type or '').strip()
        normalized_target = str(target_table or '').strip()
        return normalized_target in ACTION_TARGET_TABLE_ALLOWLIST.get(normalized_action, set())
