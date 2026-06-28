from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any, Callable, Mapping

from sqlalchemy.orm import Session

from app.core.redaction import redact_secret_text
from app.models.agent_communication import ChatInboxMessage, MultimodalEvidence
from app.models.reports import DailyReport
from app.services.hermes_codex_construction_service import request_codex_construction
from app.services.hermes_data_audit_service import HermesDataAuditService
from app.services.hermes_long_term_rule_service import list_active_rules
from app.services.hermes_mes_read_service import HermesMesReadService
from app.services.hermes_fact_source_map_service import find_fact_source, source_summary_for_metric
from app.services.rag_service import query_knowledge
from app.services.report import template_daily_report


ToolCallable = Callable[..., object]

_DINGTALK_EVIDENCE_TYPES = ('text', 'file', 'image', 'attachment', 'dingtalk_file', 'dingtalk_text')
_DINGTALK_TEXT_EVIDENCE_TYPES = {'text', 'dingtalk_text'}
_DINGTALK_FILE_EVIDENCE_TYPES = {'file', 'attachment', 'dingtalk_file'}


@dataclass(frozen=True, slots=True)
class HermesToolAdapters:
    hub_query: ToolCallable
    mes_wms_read: ToolCallable
    dingtalk_evidence: ToolCallable
    rag_route: ToolCallable
    history_report: ToolCallable
    output_skill_alignment: ToolCallable
    long_term_rules: ToolCallable
    codex_construction: ToolCallable
    source_map: ToolCallable


def build_tool_registry(adapters: HermesToolAdapters) -> dict[str, ToolCallable]:
    return {
        'hub_query': adapters.hub_query,
        'mes_wms_read': adapters.mes_wms_read,
        'dingtalk_evidence': adapters.dingtalk_evidence,
        'rag_route': adapters.rag_route,
        'history_report': adapters.history_report,
        'output_skill_alignment': adapters.output_skill_alignment,
        'long_term_rules': adapters.long_term_rules,
        'codex_construction': adapters.codex_construction,
        'source_map': adapters.source_map,
    }


def require_tool(name: str, registry: Mapping[str, ToolCallable]) -> ToolCallable:
    if name not in registry:
        raise ValueError(f'unregistered_hermes_tool:{name}')
    return registry[name]


def build_production_tool_adapters(
    db: Session,
    *,
    mes_read_service: HermesMesReadService | None = None,
    current_user: object | None = None,
    output_skill_root: str | Path | None = None,
) -> HermesToolAdapters:
    return HermesToolAdapters(
        hub_query=partial(_hub_query_tool, db=db),
        mes_wms_read=partial(_mes_wms_read_tool, mes_read_service=mes_read_service),
        dingtalk_evidence=partial(_dingtalk_evidence_tool, db=db),
        rag_route=partial(_rag_route_tool, db=db, current_user=current_user),
        history_report=partial(_history_report_tool, db=db),
        output_skill_alignment=partial(_output_skill_alignment_tool, db=db, output_skill_root=output_skill_root),
        long_term_rules=partial(_long_term_rules_tool, db=db),
        codex_construction=partial(_codex_construction_tool, db=db, current_user=current_user),
        source_map=_source_map_tool,
    )


def _hub_query_tool(*, db: Session, **kwargs: object) -> dict[str, object]:
    try:
        business_date = _parse_business_date(kwargs.get('business_date'))
        payload = template_daily_report.build_template_daily_report_payload(db, target_date=business_date)
        return {
            'status': payload.get('status', 'ok'),
            'source': 'data_hub',
            'request': _request_payload(kwargs),
            'facts': payload.get('facts') or payload.get('hermes_fact_bundle') or {},
        }
    except Exception as exc:
        return _unavailable('data_hub', kwargs, exc)


def _mes_wms_read_tool(*, mes_read_service: HermesMesReadService | None, **kwargs: object) -> dict[str, object]:
    if mes_read_service is None:
        return {
            'status': 'unavailable',
            'source': 'mes_wms_readonly',
            'request': _request_payload(kwargs),
            'facts': {},
            'reason': 'mes_read_service_missing',
        }
    try:
        business_date = _parse_business_date(kwargs.get('business_date'))
        query_keys = _string_list(kwargs.get('query_keys'), ['workshop_process_records', 'finished_inbound_records'])
        return {
            'status': 'ok',
            'source': 'mes_wms_readonly',
            'request': _request_payload(kwargs),
            'facts': mes_read_service.read_sources(
                business_date=business_date,
                query_keys=query_keys,
                workshop_name=str(kwargs.get('workshop_name') or '').strip() or None,
            ),
        }
    except Exception as exc:
        return _unavailable('mes_wms_readonly', kwargs, exc)


def _dingtalk_evidence_tool(*, db: Session, **kwargs: object) -> dict[str, object]:
    try:
        limit = max(1, min(int(kwargs.get('limit') or 20), 100))
        row_limit = max(100, limit * 5)
        evidence_rows = (
            db.query(MultimodalEvidence)
            .filter(MultimodalEvidence.evidence_type.in_(_DINGTALK_EVIDENCE_TYPES))
            .order_by(MultimodalEvidence.created_at.desc(), MultimodalEvidence.id.desc())
            .limit(row_limit)
            .all()
        )
        chat_rows = (
            db.query(ChatInboxMessage)
            .filter(ChatInboxMessage.channel == 'dingtalk_group')
            .order_by(ChatInboxMessage.created_at.desc(), ChatInboxMessage.id.desc())
            .limit(limit)
            .all()
        )
        candidates: list[tuple[tuple[int, float, int], dict[str, object]]] = []
        for row in evidence_rows:
            if not _is_dingtalk_multimodal_evidence(row):
                continue
            candidates.append(
                (
                    _dingtalk_sort_key(row, tier=_dingtalk_multimodal_tier(row)),
                    _dingtalk_multimodal_fact(row),
                )
            )
        for row in chat_rows:
            candidates.append(
                (
                    _dingtalk_sort_key(row, tier=0),
                    {
                        'source_key': 'dingtalk_group_chat',
                        'source_type': 'dingtalk_group_content',
                        'priority': 10,
                        'channel': row.channel,
                        'group_id': row.group_id,
                        'sender_external_id': row.sender_external_id,
                        'text': row.text,
                        'trace_id': row.trace_id,
                        'created_at': row.created_at.isoformat() if row.created_at else None,
                    },
                )
            )
        candidates.sort(key=lambda item: item[0])
        return {
            'status': 'ok',
            'source': 'dingtalk_group_content',
            'request': _request_payload(kwargs),
            'facts': [fact for _sort_key, fact in candidates[:limit]],
        }
    except Exception as exc:
        return _unavailable('dingtalk_group_content', kwargs, exc)


def _is_dingtalk_multimodal_evidence(row: MultimodalEvidence) -> bool:
    evidence_type = str(row.evidence_type or '').strip().lower()
    if evidence_type.startswith('dingtalk_'):
        return True
    if _value_marks_dingtalk(row.file_uri):
        return True
    payload = row.payload if isinstance(row.payload, Mapping) else {}
    return _payload_marks_dingtalk(payload)


def _payload_marks_dingtalk(payload: Mapping[object, object]) -> bool:
    for key, value in payload.items():
        key_text = str(key).strip().lower()
        if key_text.startswith('dingtalk_'):
            return True
        if key_text in {'source', 'channel', 'source_type'} and _value_marks_dingtalk(value):
            return True
    return False


def _value_marks_dingtalk(value: object) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    return (
        text == 'dingtalk'
        or text == 'dingtalk_group'
        or text.startswith('dingtalk_')
        or text.startswith('dingtalk:')
        or text.startswith('dingtalk://')
        or text.startswith('dingtalk-')
        or 'dingtalk.com' in text
    )


def _dingtalk_multimodal_tier(row: MultimodalEvidence) -> int:
    evidence_type = str(row.evidence_type or '').strip().lower()
    if evidence_type in _DINGTALK_TEXT_EVIDENCE_TYPES:
        return 0
    if evidence_type in _DINGTALK_FILE_EVIDENCE_TYPES:
        return 1
    return 2


def _dingtalk_multimodal_fact(row: MultimodalEvidence) -> dict[str, object]:
    evidence_type = str(row.evidence_type or '').strip().lower()
    return {
        'source_key': 'dingtalk_group_chat' if evidence_type in _DINGTALK_TEXT_EVIDENCE_TYPES else 'dingtalk_group_file',
        'source_type': 'dingtalk_group_content',
        'priority': 10,
        'evidence_type': row.evidence_type,
        'confirmation_status': row.confirmation_status,
        'recognized_text': row.recognized_text,
        'file_uri': row.file_uri,
        'payload': row.payload or {},
        'created_at': row.created_at.isoformat() if row.created_at else None,
    }


def _dingtalk_sort_key(row: object, *, tier: int) -> tuple[int, float, int]:
    created_at = getattr(row, 'created_at', None)
    timestamp = created_at.timestamp() if created_at else 0.0
    row_id = int(getattr(row, 'id', 0) or 0)
    return (tier, -timestamp, -row_id)


def _rag_route_tool(*, db: Session, current_user: object | None, **kwargs: object) -> dict[str, object]:
    try:
        result = query_knowledge(
            db,
            query=str(kwargs.get('query') or kwargs.get('text') or ''),
            limit=int(kwargs.get('limit') or 5),
            user=current_user,
            workshop=str(kwargs.get('workshop') or '').strip() or None,
            machine_code=str(kwargs.get('machine_code') or '').strip() or None,
        )
        return {'status': 'ok', 'source': 'rag', 'request': _request_payload(kwargs), 'facts': result}
    except Exception as exc:
        return _unavailable('rag', kwargs, exc)


def _history_report_tool(*, db: Session, **kwargs: object) -> dict[str, object]:
    try:
        business_date = _parse_business_date(kwargs.get('business_date'))
        reports = db.query(DailyReport).filter(DailyReport.report_date == business_date).all()
        facts = [
            {
                'id': report.id,
                'workshop_id': getattr(report, 'workshop_id', None),
                'status': getattr(report, 'report_status', None),
                'final_text_summary': getattr(report, 'final_text_summary', None),
                'report_data': getattr(report, 'report_data', None),
            }
            for report in reports
        ]
        return {'status': 'ok', 'source': 'daily_reports', 'request': _request_payload(kwargs), 'facts': facts}
    except Exception as exc:
        return _unavailable('daily_reports', kwargs, exc)


def _output_skill_alignment_tool(
    *,
    db: Session,
    output_skill_root: str | Path | None,
    **kwargs: object,
) -> dict[str, object]:
    try:
        service = HermesDataAuditService(db, output_skill_root=output_skill_root)
        run = service.create_run(
            business_date=_parse_business_date(kwargs.get('business_date')),
            fields=_string_list(kwargs.get('fields'), []),
            mes_query_keys=_string_list(kwargs.get('mes_query_keys'), []),
        )
        return {
            'status': run.status,
            'source': 'output_skill_alignment',
            'request': _request_payload(kwargs),
            'facts': {'run_id': run.id},
        }
    except Exception as exc:
        return _unavailable('output_skill_alignment', kwargs, exc)


def _long_term_rules_tool(*, db: Session, **kwargs: object) -> dict[str, object]:
    try:
        rules = list_active_rules(db)
        category = str(kwargs.get('category') or '').strip()
        if category:
            rules = [rule for rule in rules if (rule.scope_payload or {}).get('domain') == category]
        facts = [
            {
                'rule_key': rule.rule_key,
                'raw_text': rule.raw_text,
                'structured_rule': rule.structured_rule,
                'scope_payload': rule.scope_payload,
                'priority': rule.priority,
            }
            for rule in rules
        ]
        return {'status': 'ok', 'source': 'long_term_rules', 'request': _request_payload(kwargs), 'facts': facts}
    except Exception as exc:
        return _unavailable('long_term_rules', kwargs, exc)


def _source_map_tool(**kwargs: object) -> dict[str, object]:
    try:
        metric_key = str(kwargs.get('metric_key') or '').strip()
        item = find_fact_source(metric_key)
        return {
            'status': 'ok',
            'source': 'fact_source_map',
            'request': _request_payload(kwargs),
            'facts': {**item, 'summary': source_summary_for_metric(metric_key)},
        }
    except Exception as exc:
        return _unavailable('fact_source_map', kwargs, exc)


def _codex_construction_tool(*, db: Session, current_user: object | None, **kwargs: object) -> dict[str, object]:
    if current_user is None:
        return {
            'status': 'denied',
            'source': 'codex_construction',
            'request': _request_payload(kwargs),
            'facts': {'message': '缺少 root_owner 身份'},
        }
    result = request_codex_construction(
        db,
        actor=current_user,
        request_text=str(kwargs.get('raw_text') or kwargs.get('text') or ''),
        trace_id=str(kwargs.get('trace_id') or ''),
        construction_type=str(kwargs.get('construction_type') or 'light'),
    )
    return {
        'status': result.status,
        'source': 'codex_construction',
        'request': _request_payload(kwargs),
        'facts': {'run_id': result.run_id, 'message': result.message},
    }


def _parse_business_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _request_payload(kwargs: Mapping[str, object]) -> dict[str, str]:
    return {str(key): str(value) for key, value in kwargs.items()}


def _string_list(value: object, default: list[str]) -> list[str]:
    if value is None or value == '':
        return default
    if isinstance(value, str):
        return [item.strip() for item in value.split(',') if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _unavailable(source: str, kwargs: Mapping[str, object], exc: Exception) -> dict[str, object]:
    return {
        'status': 'unavailable',
        'source': source,
        'request': _request_payload(kwargs),
        'facts': {},
        'reason': redact_secret_text(str(exc)),
    }
