from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.core.scope import build_scope_summary
from app.models.assistant import AiContextPack
from app.services import factory_command_service


_SENSITIVE_KEY_PARTS = ('password', 'secret', 'token', 'credential', 'api_key', 'apikey')
_SYNC_DEGRADED_STATUSES = {'stale', 'failed', 'unconfigured', 'migration_missing', 'offline_or_blocked'}
_SYNC_CRITICAL_STATUSES = {'failed', 'migration_missing', 'offline_or_blocked'}
_SYNC_MISSING_DATA_KEYS = {
    'stale': 'mes_stale',
    'failed': 'mes_failed',
    'unconfigured': 'mes_unconfigured',
    'migration_missing': 'mes_projection_unready',
    'offline_or_blocked': 'mes_offline',
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                continue
            sanitized[str(key)] = _sanitize(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _source_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()[:32]


def _delay_hours(item: Mapping[str, Any]) -> float:
    try:
        return float(item.get('delay_hours') or 0)
    except (TypeError, ValueError):
        return 0.0


def _rules_for(coils: list[Mapping[str, Any]], freshness: Mapping[str, Any]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    freshness_status = str(freshness.get('status') or '')
    if freshness_status in _SYNC_DEGRADED_STATUSES:
        rules.append(
            {
                'key': 'sync_stale',
                'severity': 'critical' if freshness_status in _SYNC_CRITICAL_STATUSES else 'warning',
                'evidence_refs': [{'kind': 'sync', 'key': 'mes_projection'}],
                'recommended_next_actions': ['检查外部 MES 同步状态'],
            }
        )
    if any(_delay_hours(coil) > 0 for coil in coils):
        rules.append(
            {
                'key': 'delay_hours_high',
                'severity': 'warning',
                'evidence_refs': [
                    {'kind': 'coil', 'key': str(coil.get('coil_key') or '')}
                    for coil in coils
                    if _delay_hours(coil) > 0
                ][:5],
                'recommended_next_actions': ['查看停滞卷证据', '确认下一工序资源'],
            }
        )
    return rules


def _call_scoped(func, db: Session, *, scope):
    try:
        return func(db, scope=scope)
    except TypeError:
        return func(db)


def _filter_for_assistant_scope(
    *,
    machine_lines: list[Any],
    coils: list[Any],
    scope_payload: Mapping[str, Any],
) -> tuple[list[Any], list[Any]]:
    scope_type = str(scope_payload.get('type') or 'factory')
    scope_key = str(scope_payload.get('key') or 'all')
    if scope_type == 'factory' or scope_key == 'all':
        return machine_lines, coils
    if scope_type == 'machine':
        return (
            [line for line in machine_lines if str(line.get('line_code') or '') == scope_key],
            [
                coil
                for coil in coils
                if scope_key
                in {
                    str(coil.get('line_code') or ''),
                    str(coil.get('machine_code') or ''),
                }
            ],
        )
    if scope_type == 'coil':
        return (
            machine_lines,
            [
                coil
                for coil in coils
                if scope_key
                in {
                    str(coil.get('coil_key') or ''),
                    str(coil.get('tracking_card_no') or ''),
                    str(coil.get('batch_no') or ''),
                }
            ],
        )
    if scope_type in {'workshop', 'process'}:
        key_fields = ('current_workshop', 'workshop_name') if scope_type == 'workshop' else ('current_process', 'next_process')
        return (
            [
                line
                for line in machine_lines
                if scope_type != 'workshop' or str(line.get('workshop_name') or '') == scope_key
            ],
            [coil for coil in coils if any(str(coil.get(field) or '') == scope_key for field in key_fields)],
        )
    return machine_lines, coils


def build_context_pack(
    db: Session,
    *,
    user: Any,
    intent: str,
    scope: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or _now()
    scope_payload = scope or {'type': 'factory', 'key': 'all'}
    freshness = factory_command_service.build_freshness(db)
    data_scope = build_scope_summary(user)
    machine_lines = _sanitize(_call_scoped(factory_command_service.list_machine_lines, db, scope=data_scope))
    coils = _sanitize(_call_scoped(factory_command_service.list_coils, db, scope=data_scope))
    machine_lines, coils = _filter_for_assistant_scope(
        machine_lines=machine_lines,
        coils=coils,
        scope_payload=scope_payload,
    )
    top_abnormal_coils = [
        coil
        for coil in coils
        if isinstance(coil, Mapping) and (_delay_hours(coil) > 0 or not coil.get('current_process'))
    ][:8]
    route_refs = [
        {
            'coil_key': coil.get('coil_key'),
            'current_process': coil.get('current_process'),
            'next_process': coil.get('next_process'),
        }
        for coil in coils
        if isinstance(coil, Mapping)
    ][:12]
    known_missing_data = []
    missing_data_key = _SYNC_MISSING_DATA_KEYS.get(str(freshness.get('status') or ''))
    if missing_data_key:
        known_missing_data.append(missing_data_key)

    pack = {
        'intent': intent,
        'scope': scope_payload,
        'freshness': freshness,
        'top_abnormal_coils': top_abnormal_coils,
        'machine_line_metrics': machine_lines,
        'route_refs': route_refs,
        'rules_fired': _rules_for(coils, freshness),
        'known_missing_data': known_missing_data,
        'created_at': current.isoformat(),
    }
    safe_pack = _sanitize(pack)
    if hasattr(db, 'add'):
        entity = AiContextPack(
            owner_user_id=getattr(user, 'id', None),
            intent=intent,
            scope_payload=scope_payload,
            payload=safe_pack,
            source_hash=_source_hash(safe_pack),
            expires_at=current + timedelta(minutes=10),
        )
        db.add(entity)
        if hasattr(db, 'flush'):
            db.flush()
    return safe_pack


def answer_from_context(
    db: Session,
    *,
    user: Any,
    question: str,
    intent: str = 'factory_status',
    scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pack = build_context_pack(db, user=user, intent=intent, scope=scope)
    missing_data = list(pack.get('known_missing_data') or [])
    freshness_status = (pack.get('freshness') or {}).get('status')
    confidence = 'high'
    if freshness_status in {'stale', 'unconfigured'}:
        confidence = 'medium'
    if freshness_status in _SYNC_CRITICAL_STATUSES:
        confidence = 'low'
    evidence_refs = []
    for rule in pack.get('rules_fired') or []:
        evidence_refs.extend(rule.get('evidence_refs') or [])
    if not evidence_refs and pack.get('machine_line_metrics'):
        first_line = pack['machine_line_metrics'][0]
        evidence_refs.append({'kind': 'machine', 'key': str(first_line.get('line_code') or '')})

    if pack.get('top_abnormal_coils'):
        answer = f"已找到 {len(pack['top_abnormal_coils'])} 条需关注卷，建议先看停滞和缺下工序记录。"
    else:
        answer = '当前上下文未发现明确异常，建议继续查看同步新鲜度和机列负荷。'

    return {
        'answer': answer,
        'confidence': confidence,
        'evidence_refs': evidence_refs[:8],
        'missing_data': missing_data,
        'recommended_next_actions': ['查看证据卷', '打开工厂总览', '创建关注项'],
        'can_create_watch': True,
    }
