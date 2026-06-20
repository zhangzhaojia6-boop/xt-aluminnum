from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters import get_mes_adapter
from app.core.deps import get_current_user, get_db
from app.core.scope import build_scope_summary
from app.models.hermes_data_audit import HermesCorrectionAction, HermesDataAuditRun
from app.models.system import User
from app.schemas.hermes_data_audit import (
    HermesDataAuditApplyResponseOut,
    HermesDataAuditCorrectionsRequest,
    HermesDataAuditRunCreateRequest,
    HermesDataAuditRunEnvelopeOut,
)
from app.services.hermes_data_audit_service import (
    ACTION_TARGET_TABLE_ALLOWLIST,
    REAL_APPLY_EXECUTOR_ACTIONS,
    RERUN_REQUIRED_AUDIT_STATUSES,
    SUPPORTED_ACTION_TYPES,
    HermesDataAuditService,
    NoComparableDataError,
)
from app.services.hermes_mes_read_service import HermesMesReadService

router = APIRouter(tags=['hermes-data-audit'])

_TRUE_VALUES = {'1', 'true', 'yes', 'on'}
_PENDING_CORRECTION_ACTION_STATUSES = {'pending', 'suggested'}
_RETRYABLE_TERMINAL_CORRECTION_ACTION_STATUSES = {'failed', 'blocked', 'high_risk_blocked', 'blocked_duplicate'}
_PRIMARY_AUDIT_SOURCE_ERROR_KEYS = {'mes', 'hub', 'output_skill'}
_ACTION_GATE_REASON_PRIORITY = {
    'executor_not_supported': 0,
    'mes_target_read_only': 1,
    'target_table_not_allowed_for_action': 2,
    'unsupported_action_type': 3,
    'incomplete_correction_audit_payload': 4,
    'high_risk': 5,
    'blocked_correction_action': 6,
    'blocked_duplicate': 7,
}


def get_hermes_data_audit_service(db: Session = Depends(get_db)) -> HermesDataAuditService:
    return HermesDataAuditService(
        db,
        mes_read_service=HermesMesReadService(get_mes_adapter()),
    )


def _ensure_admin_access(user: User) -> None:
    if not build_scope_summary(user).is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Hermes data audit access denied',
        )


def _error_detail(*, reason: str, message: str | None = None) -> dict[str, str]:
    detail = {'reason': reason}
    if message:
        detail['message'] = message
    return detail


def _reason_from_value_error(exc: ValueError) -> str:
    message = str(exc).strip()
    if message == 'business_date is required':
        return 'business_date_required'
    return message or 'invalid_request'


def _get_run_or_404(db: Session, run_id: int) -> HermesDataAuditRun:
    run = db.get(HermesDataAuditRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_detail(reason='run_not_found', message='Hermes data audit run not found'),
        )
    return run


def _apply_enabled_flag() -> bool:
    return str(os.getenv('HERMES_DATA_AUDIT_APPLY_ENABLED', 'false')).strip().lower() in _TRUE_VALUES


def _best_effort_row_count(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if not isinstance(payload, dict):
        return 0
    for key in ('row_count', 'count', 'field_count'):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    records = payload.get('records')
    if isinstance(records, list):
        return len(records)
    if isinstance(records, dict):
        return sum(_best_effort_row_count(item) for item in records.values())
    records_count_by_source = payload.get('records_count_by_source')
    if isinstance(records_count_by_source, dict):
        return sum(int(value) for value in records_count_by_source.values() if isinstance(value, (int, float)))
    parsed = payload.get('parsed')
    if isinstance(parsed, dict):
        return len(parsed)
    field_values = payload.get('field_values')
    if isinstance(field_values, dict):
        return len(field_values)
    return 0


def _source_error_value(source_errors: Any, source_name: str) -> Any:
    if not isinstance(source_errors, dict):
        return None
    value = source_errors.get(source_name)
    if isinstance(value, list) and value and isinstance(value[0], dict) and value[0].get('code'):
        return str(value[0]['code'])
    if isinstance(value, dict) and value.get('code'):
        return str(value['code'])
    return value


def _rollback_available(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if isinstance(payload.get('rollback_available'), bool):
        return bool(payload.get('rollback_available'))
    return payload.get('restore_before_value') not in (None, {}, [])


def _serialize_action_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': payload.get('id'),
        'idempotency_key': payload.get('idempotency_key'),
        'action_type': payload.get('action_type'),
        'risk_level': payload.get('risk_level'),
        'status': payload.get('status') or 'suggested',
        'target_table': payload.get('target_table'),
        'target_key': payload.get('target_key'),
        'before_value': payload.get('before_value'),
        'after_value': payload.get('after_value'),
        'evidence': payload.get('evidence'),
        'rollback_payload': payload.get('rollback_payload'),
        'rollback_available': _rollback_available(payload.get('rollback_payload')),
    }


def _correction_action_payload_from_row(row: HermesCorrectionAction) -> dict[str, Any]:
    return {
        'idempotency_key': row.idempotency_key,
        'action_type': row.action_type,
        'risk_level': row.risk_level,
        'target_table': row.target_table,
        'target_key': row.target_key,
        'field_name': row.field_name,
        'before_value': row.before_value,
        'after_value': row.after_value,
        'evidence': row.evidence,
        'rollback_payload': row.rollback_payload,
    }


def _is_retryable_terminal_correction_action_status(status: str | None) -> bool:
    return str(status or '').strip().lower() in _RETRYABLE_TERMINAL_CORRECTION_ACTION_STATUSES


def _serialize_correction_actions(db: Session, run: HermesDataAuditRun) -> list[dict[str, Any]]:
    rows = (
        db.query(HermesCorrectionAction)
        .filter(HermesCorrectionAction.audit_run_id == run.id)
        .order_by(HermesCorrectionAction.id.asc())
        .all()
    )
    serialized_rows = [
        {
            'id': row.id,
            'idempotency_key': row.idempotency_key,
            'action_type': row.action_type,
            'risk_level': row.risk_level,
            'status': row.status,
            'target_table': row.target_table,
            'target_key': row.target_key,
            'before_value': row.before_value,
            'after_value': row.after_value,
            'evidence': row.evidence,
            'rollback_payload': row.rollback_payload,
            'rollback_available': _rollback_available(row.rollback_payload),
        }
        for row in rows
    ]
    serialized_rows_by_key = {
        str(item['idempotency_key']): item
        for item in serialized_rows
        if item.get('idempotency_key') not in (None, '')
    }
    seen_idempotency_keys = {
        str(item['idempotency_key'])
        for item in serialized_rows
        if item.get('idempotency_key') not in (None, '')
    }
    seen_action_targets = {
        (
            row.action_type,
            row.target_table,
            row.target_key,
            row.field_name,
        )
        for row in rows
    }

    merged_actions = list(serialized_rows)
    added_retry_suggestion_keys: set[str] = set()
    for payload in run.suggested_actions or []:
        if not isinstance(payload, dict):
            continue
        idempotency_key = payload.get('idempotency_key')
        if idempotency_key not in (None, ''):
            normalized_key = str(idempotency_key)
            if normalized_key in seen_idempotency_keys:
                existing_row = serialized_rows_by_key.get(normalized_key)
                if (
                    existing_row is not None
                    and _is_retryable_terminal_correction_action_status(existing_row.get('status'))
                    and normalized_key not in added_retry_suggestion_keys
                ):
                    merged_actions.append(_serialize_action_payload(payload))
                    added_retry_suggestion_keys.add(normalized_key)
                continue
            seen_idempotency_keys.add(normalized_key)
        else:
            action_target = (
                payload.get('action_type'),
                payload.get('target_table'),
                payload.get('target_key'),
                payload.get('field_name'),
            )
            if action_target in seen_action_targets:
                continue
            seen_action_targets.add(action_target)
        merged_actions.append(_serialize_action_payload(payload))
    return merged_actions


def _pending_correction_actions(correction_actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending_actions: list[dict[str, Any]] = []
    for item in correction_actions:
        status_name = str(item.get('status') or 'suggested').strip()
        if status_name in _PENDING_CORRECTION_ACTION_STATUSES:
            pending_actions.append(item)
    return pending_actions


def _action_gate_block_reason(action: dict[str, Any]) -> str | None:
    action_type = str(action.get('action_type') or '').strip()
    target_table = str(action.get('target_table') or '').strip()
    if action_type not in SUPPORTED_ACTION_TYPES:
        return 'unsupported_action_type'
    if target_table not in ACTION_TARGET_TABLE_ALLOWLIST.get(action_type, set()):
        if target_table.startswith('mes_'):
            return 'mes_target_read_only'
        return 'target_table_not_allowed_for_action'
    if not _has_complete_action_audit_payload(action):
        return 'incomplete_correction_audit_payload'
    if action_type not in REAL_APPLY_EXECUTOR_ACTIONS:
        return 'executor_not_supported'
    if (action.get('risk_level') or '').lower() != 'low':
        return 'high_risk'
    return None


def _has_complete_action_audit_payload(action: dict[str, Any]) -> bool:
    if not action.get('idempotency_key') or not action.get('target_table') or not action.get('target_key'):
        return False
    if not action.get('risk_level'):
        return False
    if action.get('before_value') in (None, {}) or action.get('after_value') in (None, {}):
        return False
    evidence = action.get('evidence')
    if evidence in (None, {}) or not isinstance(evidence, dict):
        return False
    if not any(
        evidence.get(key) not in (None, '', {}, [])
        for key in ('reason', 'source', 'evidence_ref', 'field', 'field_name', 'values', 'handler')
    ):
        return False
    rollback_payload = action.get('rollback_payload')
    if rollback_payload in (None, {}):
        return False
    if isinstance(rollback_payload, dict):
        if rollback_payload.get('restore_before_value') not in (None, {}):
            return True
        if rollback_payload.get('reason') or rollback_payload.get('mode') == 'not_available':
            return True
        rollback_unavailable_reason = str(rollback_payload.get('rollback_unavailable_reason') or '').strip()
        rollback_available = rollback_payload.get('rollback_available')
        rollback_available_false = rollback_available is False or (
            isinstance(rollback_available, str) and rollback_available.strip().lower() == 'false'
        )
        return bool(rollback_available_false and rollback_unavailable_reason)
    return True


def _pending_action_gate_reason(pending_actions: list[dict[str, Any]]) -> str | None:
    block_reasons = [
        reason
        for reason in (_action_gate_block_reason(item) for item in pending_actions)
        if reason is not None
    ]
    if not block_reasons:
        return None
    return min(block_reasons, key=lambda reason: _ACTION_GATE_REASON_PRIORITY.get(reason, 999))


def _blocked_action_gate_reason(correction_actions: list[dict[str, Any]]) -> str | None:
    block_reasons: list[str] = []
    for item in correction_actions:
        status_name = str(item.get('status') or '').strip().lower()
        evidence = item.get('evidence') if isinstance(item.get('evidence'), dict) else {}
        blocked_reason = str(evidence.get('blocked_reason') or '').strip()
        if status_name == 'high_risk_blocked':
            block_reasons.append(blocked_reason or 'high_risk')
            continue
        if status_name == 'blocked':
            block_reasons.append(blocked_reason or 'blocked_correction_action')
            continue
        if status_name == 'blocked_duplicate':
            block_reasons.append(blocked_reason or 'blocked_duplicate')
            continue
        if status_name == 'failed' and blocked_reason:
            block_reasons.append(blocked_reason)
    if not block_reasons:
        return None
    return min(block_reasons, key=lambda reason: _ACTION_GATE_REASON_PRIORITY.get(reason, 999))


def _source_gate_reason(run: HermesDataAuditRun) -> str | None:
    source_errors = {
        key: value
        for key, value in (run.source_errors or {}).items()
        if key in _PRIMARY_AUDIT_SOURCE_ERROR_KEYS
    }
    if source_errors.get('output_skill') == 'output_skill_source_missing':
        return 'output_skill_source_missing'
    if source_errors:
        return 'source_unhealthy'
    source_status = run.source_status or {}
    if source_status.get('output_skill') == 'missing':
        return 'output_skill_source_missing'
    if any(source_status.get(name) in {'failed', 'partial_failed', 'missing', 'empty', 'unsupported'} for name in ('mes', 'hub', 'output_skill')):
        return 'source_unhealthy'
    return None


def _build_decision_gate(
    *,
    run: HermesDataAuditRun,
    correction_actions: list[dict[str, Any]],
    apply_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    apply_enabled = (
        bool(apply_summary.get('apply_enabled', _apply_enabled_flag()))
        if apply_summary is not None
        else _apply_enabled_flag()
    )
    reason = _source_gate_reason(run)
    if reason:
        return {'can_apply': False, 'reason': reason, 'apply_enabled': apply_enabled}
    if run.status in RERUN_REQUIRED_AUDIT_STATUSES:
        return {'can_apply': False, 'reason': 'rerun_audit_required', 'apply_enabled': apply_enabled}
    if not correction_actions:
        return {'can_apply': False, 'reason': 'no_correction_actions', 'apply_enabled': apply_enabled}
    pending_actions = _pending_correction_actions(correction_actions)
    if not pending_actions:
        blocked_reason = _blocked_action_gate_reason(correction_actions)
        if blocked_reason is not None:
            return {'can_apply': False, 'reason': blocked_reason, 'apply_enabled': apply_enabled}
        return {'can_apply': False, 'reason': 'no_pending_correction_actions', 'apply_enabled': apply_enabled}
    pending_gate_reason = _pending_action_gate_reason(pending_actions)
    if pending_gate_reason is not None:
        return {'can_apply': False, 'reason': pending_gate_reason, 'apply_enabled': apply_enabled}
    if not apply_enabled:
        return {'can_apply': False, 'reason': 'apply_disabled', 'apply_enabled': apply_enabled}
    return {'can_apply': True, 'reason': 'ready_to_apply', 'apply_enabled': apply_enabled}


def _recommended_next_step(*, run: HermesDataAuditRun, decision_gate: dict[str, Any], apply_summary: dict[str, Any] | None = None) -> str:
    if run.status in RERUN_REQUIRED_AUDIT_STATUSES:
        return 'rerun_audit_to_verify'
    if apply_summary is not None and int(apply_summary.get('applied_count', 0) or 0) > 0:
        return 'rerun_audit_to_verify'
    reason = decision_gate.get('reason')
    if reason == 'output_skill_source_missing':
        return 'mount_output_skill_reference_and_rerun'
    if reason == 'source_unhealthy':
        return 'fix_source_health_and_rerun'
    if reason in {'no_correction_actions', 'no_pending_correction_actions'}:
        return 'review_diffs_or_expand_fields'
    if reason == 'apply_disabled':
        return 'review_low_risk_actions'
    if reason in {
        'review_required',
        'high_risk',
        'executor_not_supported',
        'mes_target_read_only',
        'target_table_not_allowed_for_action',
        'unsupported_action_type',
    }:
        return 'review_low_risk_actions'
    if run.status.startswith('correction_'):
        return 'rerun_audit_to_verify'
    return 'review_low_risk_actions'


def _known_correction_payloads(
    db: Session,
    run: HermesDataAuditRun,
) -> tuple[dict[int, dict[str, Any]], dict[str, dict[str, Any]]]:
    rows = (
        db.query(HermesCorrectionAction)
        .filter(HermesCorrectionAction.audit_run_id == run.id)
        .order_by(HermesCorrectionAction.id.asc())
        .all()
    )
    payloads_by_id: dict[int, dict[str, Any]] = {}
    payloads_by_key: dict[str, dict[str, Any]] = {}
    row_status_by_key: dict[str, str] = {}
    for row in rows:
        payload = _correction_action_payload_from_row(row)
        payloads_by_id[row.id] = payload
        key = str(row.idempotency_key or '').strip()
        if key:
            payloads_by_key[key] = payload
            row_status_by_key[key] = str(row.status or '')

    for payload in run.suggested_actions or []:
        if not isinstance(payload, dict):
            continue
        key = str(payload.get('idempotency_key') or '').strip()
        if not key:
            continue
        if key in payloads_by_key and not _is_retryable_terminal_correction_action_status(row_status_by_key.get(key)):
            continue
        payloads_by_key[key] = payload
    return payloads_by_id, payloads_by_key


def _resolve_requested_correction_actions(
    db: Session,
    run: HermesDataAuditRun,
    body: HermesDataAuditCorrectionsRequest,
) -> list[dict[str, Any]]:
    payloads_by_id, payloads_by_key = _known_correction_payloads(db, run)
    selectors: list[tuple[str, int | str]] = []
    invalid_legacy_selector = False

    for action_id in body.action_ids:
        selectors.append(('id', int(action_id)))
    for idempotency_key in body.idempotency_keys:
        normalized_key = str(idempotency_key or '').strip()
        if normalized_key:
            selectors.append(('key', normalized_key))

    for payload in body.actions:
        raw_id = payload.get('id')
        if raw_id not in (None, ''):
            try:
                selectors.append(('id', int(raw_id)))
            except (TypeError, ValueError):
                invalid_legacy_selector = True
            continue
        idempotency_key = str(payload.get('idempotency_key') or '').strip()
        if idempotency_key:
            selectors.append(('key', idempotency_key))
            continue
        invalid_legacy_selector = True

    if not selectors:
        reason = 'unknown_correction_action' if body.actions or invalid_legacy_selector else 'no_actions_selected'
        message = 'Correction action not found for this run' if reason == 'unknown_correction_action' else 'No correction actions selected'
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(reason=reason, message=message),
        )

    if invalid_legacy_selector:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(
                reason='unknown_correction_action',
                message='Correction action not found for this run',
            ),
        )

    resolved_actions: list[dict[str, Any]] = []
    seen_action_keys: set[str] = set()
    for selector_type, selector_value in selectors:
        if selector_type == 'id':
            payload = payloads_by_id.get(int(selector_value))
            fallback_key = f'id:{selector_value}'
        else:
            payload = payloads_by_key.get(str(selector_value))
            fallback_key = f'key:{selector_value}'
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_error_detail(
                    reason='unknown_correction_action',
                    message='Correction action not found for this run',
                ),
            )
        resolved_key = str(payload.get('idempotency_key') or fallback_key)
        if resolved_key in seen_action_keys:
            continue
        seen_action_keys.add(resolved_key)
        resolved_actions.append(payload)
    return resolved_actions


def _serialize_run(
    db: Session,
    run: HermesDataAuditRun,
    *,
    apply_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    diffs = run.diffs or {}
    categories: dict[str, int] = {}
    matched_fields = 0
    missing_source = 0
    cannot_decide = 0
    for item in diffs.values():
        if not isinstance(item, dict):
            continue
        status_name = str(item.get('status') or 'unknown')
        categories[status_name] = categories.get(status_name, 0) + 1
        if status_name == 'matched':
            matched_fields += 1
        if status_name.endswith('_missing'):
            missing_source += 1
        if status_name == 'cannot_decide':
            cannot_decide += 1

    correction_actions = _serialize_correction_actions(db, run)
    decision_gate = _build_decision_gate(run=run, correction_actions=correction_actions, apply_summary=apply_summary)
    source_errors = run.source_errors or {}

    return {
        'id': run.id,
        'headline_status': run.status,
        'business_date': run.business_date.isoformat(),
        'decision_gate': decision_gate,
        'source_health': {
            'mes': {
                'status': str((run.source_status or {}).get('mes') or 'unknown'),
                'row_count': _best_effort_row_count(run.mes_snapshot or {}),
                'error': _source_error_value(source_errors, 'mes'),
            },
            'hub': {
                'status': str((run.source_status or {}).get('hub') or 'unknown'),
                'row_count': _best_effort_row_count(run.hub_snapshot or {}),
                'error': _source_error_value(source_errors, 'hub'),
            },
            'output_skill': {
                'status': str((run.source_status or {}).get('output_skill') or 'unknown'),
                'row_count': _best_effort_row_count(run.output_skill_snapshot or {}),
                'error': _source_error_value(source_errors, 'output_skill'),
            },
        },
        'match_summary': {
            'match_rate': float(run.match_rate) if run.match_rate is not None else None,
            'matched_fields': matched_fields,
            'unmatched_fields': max(len(diffs) - matched_fields, 0),
            'regressed': False,
        },
        'diff_summary': {
            'categories': categories,
            'missing_source': missing_source,
            'cannot_decide': cannot_decide,
        },
        'correction_actions': correction_actions,
        'recommended_next_step': _recommended_next_step(run=run, decision_gate=decision_gate, apply_summary=apply_summary),
    }


@router.post('/runs', response_model=HermesDataAuditRunEnvelopeOut)
def create_hermes_data_audit_run(
    body: HermesDataAuditRunCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: HermesDataAuditService = Depends(get_hermes_data_audit_service),
) -> dict[str, Any]:
    _ensure_admin_access(current_user)
    try:
        run = service.create_run(
            business_date=body.business_date,
            fields=body.fields,
            mes_query_keys=body.mes_query_keys,
            created_by_id=current_user.id,
        )
    except NoComparableDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(reason='no_comparable_data', message=str(exc)),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(reason=_reason_from_value_error(exc), message=str(exc)),
        ) from exc
    return _serialize_run(db, run)


@router.get('/runs/{run_id}', response_model=HermesDataAuditRunEnvelopeOut)
def get_hermes_data_audit_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = current_user
    run = _get_run_or_404(db, run_id)
    return _serialize_run(db, run)


@router.post('/runs/{run_id}/corrections', response_model=HermesDataAuditApplyResponseOut)
def apply_hermes_data_audit_corrections(
    run_id: int,
    body: HermesDataAuditCorrectionsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: HermesDataAuditService = Depends(get_hermes_data_audit_service),
) -> dict[str, Any]:
    _ensure_admin_access(current_user)
    run = _get_run_or_404(db, run_id)
    resolved_actions = _resolve_requested_correction_actions(db, run, body)
    try:
        apply_summary = service.apply_corrections(
            audit_run_id=run_id,
            actions=resolved_actions,
            dry_run=body.dry_run,
            applied_by_id=current_user.id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_detail(reason='run_not_found', message=str(exc)),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_detail(reason=_reason_from_value_error(exc), message=str(exc)),
        ) from exc

    payload = _serialize_run(db, run, apply_summary=apply_summary)
    payload['apply_summary'] = apply_summary
    return payload
