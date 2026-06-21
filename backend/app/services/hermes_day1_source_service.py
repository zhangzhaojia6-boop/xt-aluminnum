from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.adapters import get_mes_adapter
from app.core.redaction import filter_sensitive_mapping, redact_secret_text
from app.models.agent_communication import ChatInboxMessage, MultimodalEvidence
from app.models.reports import DailyReport
from app.models.system import User
from app.services.hermes_data_audit_service import (
    DEFAULT_AUDIT_FIELDS,
    HermesDataAuditService,
    NoComparableDataError,
)
from app.services.hermes_mes_read_service import HermesMesReadService
from app.services.rag_service import query_knowledge
from app.services.report import template_daily_report


DAY1_MES_QUERY_KEYS = (
    'workshop_process_records',
    'stock_records',
    'finished_inbound_records',
    'delivery_records',
    'material_records',
    'yield_records',
    'wip_totals',
)

_DINGTALK_SCAN_LIMIT = 200
_DINGTALK_MESSAGE_LIMIT = 20
_HISTORICAL_REPORT_LIMIT = 7


def collect_day1_sources(
    db: Session,
    *,
    business_date: date,
    actor: User | None,
    trace_id: str,
) -> dict[str, Any]:
    template_payload = template_daily_report.build_template_daily_report_payload(db, target_date=business_date)
    mes_reader = HermesMesReadService(get_mes_adapter())
    mes_payload = mes_reader.read_sources(
        business_date=business_date,
        query_keys=DAY1_MES_QUERY_KEYS,
    )
    audit_payload = _create_audit_payload(
        db,
        business_date=business_date,
        actor=actor,
        mes_reader=mes_reader,
        template_payload=template_payload,
    )
    rag_payload = query_knowledge(
        db,
        query=f'{business_date.isoformat()} 日报 模板 WMS_InStock MES 路线 数据来源',
        limit=5,
        user=actor,
    )

    return {
        'trace_id': trace_id,
        'business_date': business_date.isoformat(),
        'template_daily_report': template_payload,
        'mes_wms': mes_payload,
        'audit_run': audit_payload,
        'dingtalk_evidence': _list_dingtalk_evidence(db, business_date=business_date),
        'dingtalk_messages': _list_dingtalk_messages(db, business_date=business_date, trace_id=trace_id),
        'historical_reports': _list_historical_reports(db, business_date=business_date),
        'rag': {
            'answer': rag_payload.get('answer'),
            'citations': rag_payload.get('citations') or [],
        },
    }


def _build_hub_snapshot_reader(template_payload: Mapping[str, Any]):
    values = dict((template_payload.get('facts') or {}).get('values') or {})

    def _reader(_business_date: date, fields: Sequence[str]) -> dict[str, Any]:
        return {field: values.get(field) for field in fields if field in values}

    return _reader


def _create_audit_payload(
    db: Session,
    *,
    business_date: date,
    actor: User | None,
    mes_reader: HermesMesReadService,
    template_payload: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        run = HermesDataAuditService(
            db,
            mes_read_service=mes_reader,
            hub_snapshot_reader=_build_hub_snapshot_reader(template_payload),
        ).create_run(
            business_date=business_date,
            fields=DEFAULT_AUDIT_FIELDS,
            mes_query_keys=DAY1_MES_QUERY_KEYS,
            created_by_id=getattr(actor, 'id', None),
        )
        return _audit_run_payload(run)
    except NoComparableDataError as exc:
        return _failed_audit_payload(exc)
    except Exception as exc:
        return _failed_audit_payload(exc)


def _audit_run_payload(run: Any) -> dict[str, Any]:
    payload = {
        'id': getattr(run, 'id', None),
        'status': getattr(run, 'status', None),
        'match_rate': _float_or_none(getattr(run, 'match_rate', None)),
        'source_status': _json_safe(getattr(run, 'source_status', {}) or {}),
        'source_errors': _json_safe(getattr(run, 'source_errors', {}) or {}),
        'diffs': _json_safe(getattr(run, 'diffs', {}) or {}),
        'suggested_actions': _json_safe(getattr(run, 'suggested_actions', []) or []),
    }
    output_skill_snapshot = getattr(run, 'output_skill_snapshot', None)
    if output_skill_snapshot is not None:
        payload['output_skill_snapshot'] = _safe_output_skill_snapshot(output_skill_snapshot)
    return payload


def _failed_audit_payload(exc: Exception) -> dict[str, Any]:
    return {
        'id': None,
        'status': 'failed',
        'match_rate': None,
        'source_status': {'audit': 'failed'},
        'source_errors': {'audit': redact_secret_text(str(exc))},
        'diffs': {},
        'suggested_actions': [],
        'output_skill_snapshot': {'status': 'unknown'},
    }


def _safe_output_skill_snapshot(snapshot: Any) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        return {'status': 'unknown', 'summary': redact_secret_text(str(snapshot))}
    safe = _json_safe(snapshot)
    allowed_keys = {
        'status',
        'files',
        'parsed',
        'issues',
        'payload_hash',
        'raw_payload_truncated',
        'field_values',
        'field_count',
    }
    return {key: safe.get(key) for key in allowed_keys if key in safe}


def _list_dingtalk_evidence(db: Session, *, business_date: date) -> list[dict[str, Any]]:
    business_date_text = business_date.isoformat()
    rows = (
        db.query(MultimodalEvidence)
        .filter(MultimodalEvidence.payload.is_not(None))
        .order_by(MultimodalEvidence.created_at.desc(), MultimodalEvidence.id.desc())
        .limit(_DINGTALK_SCAN_LIMIT)
        .all()
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row.payload or {})
        if payload.get('business_date') != business_date_text:
            continue
        if not payload.get('include_in_daily_sample'):
            continue
        result.append(
            {
                'id': row.id,
                'evidence_type': row.evidence_type,
                'recognized_text': row.recognized_text,
                'file_uri': row.file_uri,
                'payload': _json_safe(payload),
            }
        )
    return result


def _list_dingtalk_messages(db: Session, *, business_date: date, trace_id: str) -> list[dict[str, Any]]:
    business_date_text = business_date.isoformat()
    rows = (
        db.query(ChatInboxMessage)
        .order_by(ChatInboxMessage.created_at.desc(), ChatInboxMessage.id.desc())
        .limit(_DINGTALK_SCAN_LIMIT)
        .all()
    )
    matched_rows = [
        row
        for row in rows
        if row.trace_id == trace_id or _source_payload_business_date(row.source_payload) == business_date_text
    ]
    selected_rows = matched_rows if matched_rows else rows
    return [_chat_message_payload(row) for row in selected_rows[:_DINGTALK_MESSAGE_LIMIT]]


def _source_payload_business_date(payload: Mapping[str, Any] | None) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    value = payload.get('business_date')
    return str(value) if value is not None else None


def _chat_message_payload(row: ChatInboxMessage) -> dict[str, Any]:
    return {
        'id': row.id,
        'channel': row.channel,
        'group_id': row.group_id,
        'sender_external_id': row.sender_external_id,
        'text': row.text,
        'trace_id': row.trace_id,
        'created_at': row.created_at.isoformat() if row.created_at else None,
    }


def _list_historical_reports(db: Session, *, business_date: date) -> list[dict[str, Any]]:
    rows = (
        db.query(DailyReport)
        .filter(DailyReport.report_type == 'production')
        .filter(DailyReport.report_date <= business_date)
        .order_by(DailyReport.report_date.desc(), DailyReport.id.desc())
        .limit(_HISTORICAL_REPORT_LIMIT)
        .all()
    )
    return [
        {
            'id': row.id,
            'report_date': row.report_date.isoformat(),
            'status': row.status,
            'quality_gate_status': row.quality_gate_status,
            'has_final_text': bool(row.final_text_summary),
            'delivery_ready': bool(row.delivery_ready),
        }
        for row in rows
    ]


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in filter_sensitive_mapping(value).items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        return redact_secret_text(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return redact_secret_text(str(value))
