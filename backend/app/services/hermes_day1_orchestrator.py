from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.redaction import filter_sensitive_mapping, redact_secret_text
from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.reports import DailyReport
from app.models.system import User
from app.services import hermes_memory_service, hermes_rag_service
from app.services.audit_service import log_action
from app.services.hermes_day1_harness_service import evaluate_day1_run_payload, summarize_harness_results
from app.services.hermes_day1_intent_service import HermesDay1Command
from app.services.hermes_day1_report_service import build_day1_three_part_report, _alignment_threshold as _report_alignment_threshold
from app.services.hermes_day1_source_service import collect_day1_sources
from app.services.hermes_governance_service import FACTORY_PROFILE_CODE
from app.services.report.daily_fact_bundle import persist_daily_fact_bundle_snapshot
from app.services.report.daily_report_history import archive_daily_report
from app.services.report.period_rollup import build_operation_period_snapshot

DAY1_TOOLS_CALLED = [
    'template_daily_report',
    'daily_fact_bundle',
    'source_map',
    'mes_wms_read',
    'hermes_data_audit',
    'dingtalk_evidence_scan',
    'dingtalk_message_scan',
    'historical_reports_scan',
    'rag_query',
    'output_skill_alignment',
    'build_day1_three_part_report',
]


@dataclass(frozen=True, slots=True)
class HermesDay1Result:
    trace_id: str
    status: str
    answer: str
    reply_messages: list[str]
    agent_run_id: int
    report_id: int
    payload: dict[str, Any]


def run_day1_super_brain(
    db: Session,
    *,
    command: HermesDay1Command,
    actor: User,
    trace_id: str,
    chat_inbox: ChatInboxMessage | None = None,
) -> HermesDay1Result:
    sources = collect_day1_sources(
        db,
        business_date=command.business_date,
        actor=actor,
        trace_id=trace_id,
    )
    product = build_day1_three_part_report(
        business_date=command.business_date,
        sources=sources,
    )
    report = _upsert_daily_report(
        db,
        command=command,
        actor=actor,
        product=product,
        sources=sources,
    )
    archive_trace = _archive_ready_day1_report(
        db,
        command=command,
        actor=actor,
        product=product,
        sources=sources,
        trace_id=trace_id,
    )
    if archive_trace:
        _attach_archive_trace_to_report(report, archive_trace)

    learning_payload = {
        'event_recorded': True,
        'tools_called': DAY1_TOOLS_CALLED,
        'source_trace': [name for name in sources.keys() if name not in {'trace_id', 'business_date'}],
    }
    correction_action_policy = {
        'mode': 'audit_only',
        'default_execution': 'disabled',
        'note': 'correction action 只审计设计，不默认执行',
    }
    harness_results = evaluate_day1_run_payload(
        {
            'sources': sources,
            'missing_fields': product.get('missing_fields') or [],
            'conflicts': product.get('conflicts') or [],
            'formal_text': product.get('formal_text') or '',
            'output_skill_alignment': sources.get('output_skill_alignment') or {},
            'learning': learning_payload,
            'correction_action_policy': correction_action_policy,
        },
        answer=str(product.get('text') or ''),
        min_field_match_rate=_alignment_threshold(sources),
    )
    payload = _agent_result_payload(
        command=command,
        product=product,
        sources=sources,
        report_id=report.id,
        learning_payload=learning_payload,
        correction_action_policy=correction_action_policy,
        harness_results=harness_results,
    )
    run = AgentRun(
        trace_id=trace_id,
        agent_code=FACTORY_PROFILE_CODE,
        chat_inbox_id=getattr(chat_inbox, 'id', None),
        status='answered' if product.get('status') == 'ready' else 'blocked',
        status_color='green' if product.get('status') == 'ready' else 'yellow',
        answer=str(product.get('dingtalk_answer') or ''),
        rag_citation_count=len((_as_mapping(sources.get('rag')).get('citations') or [])),
        result_payload=payload,
    )
    db.add(run)
    db.flush()

    hermes_memory_service.remember_short_term(
        db,
        conversation_key=f'user:{actor.id}',
        memory_key='last_day1_super_brain_report',
        memory_value={
            'business_date': command.business_date.isoformat(),
            'status': str(product.get('status') or ''),
            'report_id': report.id,
            'agent_run_id': run.id,
        },
        actor=actor,
        trace_id=trace_id,
    )
    hermes_rag_service.record_learning_event(
        db,
        question=_command_raw_text(command),
        answer=_growth_feedback_text(command=command, product=product),
        trace_id=trace_id,
        tools_called=DAY1_TOOLS_CALLED,
        sources=_learning_sources(sources),
        actor=actor,
    )
    log_action(
        db,
        user_id=actor.id,
        user_name=actor.name,
        action='hermes_day1_super_brain_report',
        module='hermes',
        table_name='daily_reports',
        record_id=report.id,
        old_value=None,
        new_value={
            'trace_id': trace_id,
            'status': str(product.get('status') or ''),
            'business_date': command.business_date.isoformat(),
        },
        reason='root_owner 触发 Hermes Day-1 Super Brain MVP',
        auto_commit=False,
    )
    db.flush()

    return HermesDay1Result(
        trace_id=trace_id,
        status=str(product.get('status') or ''),
        answer=str(product.get('dingtalk_answer') or ''),
        reply_messages=[str(message) for message in product.get('dingtalk_messages') or []],
        agent_run_id=run.id,
        report_id=report.id,
        payload=run.result_payload or {},
    )


def _upsert_daily_report(
    db: Session,
    *,
    command: HermesDay1Command,
    actor: User,
    product: dict[str, Any],
    sources: dict[str, Any],
) -> DailyReport:
    report = (
        db.query(DailyReport)
        .filter(
            DailyReport.report_date == command.business_date,
            DailyReport.report_type == 'production',
        )
        .one_or_none()
    )
    if report is None:
        report = DailyReport(
            report_date=command.business_date,
            report_type='production',
            generated_scope='hermes_day1',
            output_mode='text',
            status='draft',
        )
        db.add(report)
        db.flush()

    report_data = dict(report.report_data or {})
    report_data['hermes_day1_super_brain'] = _json_safe(
        {
            'status': product.get('status'),
            'three_part_text': product.get('text'),
            'brain_judgment': product.get('brain_judgment'),
            'workshop_details': product.get('workshop_details'),
            'dingtalk_messages': product.get('dingtalk_messages'),
            'missing_fields': product.get('missing_fields'),
            'conflicts': product.get('conflicts'),
            'source_status': _as_mapping(sources.get('audit_run')).get('source_status'),
            'output_skill_alignment': _output_skill_alignment_payload(
                sources.get('output_skill_alignment')
            ),
        }
    )
    report.report_data = report_data
    report.text_summary = str(product.get('text') or '')
    report.generated_at = datetime.now(timezone.utc)

    is_ready = product.get('status') == 'ready'
    has_formal_text = bool(str(product.get('formal_text') or '').strip())
    report.status = 'generated' if is_ready else 'draft'
    report.quality_gate_status = 'passed' if is_ready else 'blocked'
    report.quality_gate_summary = (
        'Hermes Day-1 三段式日报已生成'
        if is_ready
        else '缺字段或冲突，未生成正式日报正文'
    )
    if is_ready and has_formal_text:
        report.final_text_summary = str(product.get('formal_text') or '').strip()
        report.final_confirmed_by = actor.id
        report.final_confirmed_at = datetime.now(timezone.utc)
        report.is_final_version = True
        report.delivery_ready = True
    else:
        report.reviewed_by = None
        report.reviewed_at = None
        report.published_by = None
        report.published_at = None
        report.final_text_summary = None
        report.final_confirmed_by = None
        report.final_confirmed_at = None
        report.is_final_version = False
        report.delivery_ready = False

    db.flush()
    return report


def _archive_ready_day1_report(
    db: Session,
    *,
    command: HermesDay1Command,
    actor: User,
    product: dict[str, Any],
    sources: dict[str, Any],
    trace_id: str,
) -> dict[str, Any]:
    if product.get('status') != 'ready':
        return {}
    formal_text = str(product.get('formal_text') or '').strip()
    if not formal_text:
        return {}
    daily_fact_bundle = _as_mapping(sources.get('daily_fact_bundle'))
    if not daily_fact_bundle:
        return {}

    _, source_snapshot = persist_daily_fact_bundle_snapshot(
        db,
        bundle=daily_fact_bundle,
        business_date=command.business_date,
        requested_by=actor,
        trace_id=trace_id,
        snapshot_reason='formal_daily_report',
    )
    history = archive_daily_report(
        db,
        business_date=command.business_date,
        report_text=formal_text,
        report_payload=_formal_history_payload(
            product=product,
            daily_fact_bundle=daily_fact_bundle,
            output_skill_alignment=(
                _as_mapping(sources.get('output_skill_alignment'))
                or _as_mapping(daily_fact_bundle.get('output_skill_alignment'))
            ),
        ),
        source_snapshot=source_snapshot,
        trace_id=trace_id,
        created_by_id=actor.id,
    )
    month_snapshot = build_operation_period_snapshot(
        db,
        period_type='month',
        target_date=command.business_date,
        trace_id=trace_id,
        created_by_id=actor.id,
    )
    year_snapshot = build_operation_period_snapshot(
        db,
        period_type='year',
        target_date=command.business_date,
        trace_id=trace_id,
        created_by_id=actor.id,
    )

    daily_fact_summary = dict(daily_fact_bundle)
    daily_fact_summary['formal_snapshot_id'] = source_snapshot.id
    daily_fact_summary['formal_history_record_id'] = history.id
    sources['daily_fact_bundle'] = daily_fact_summary
    sources['formal_daily_report_snapshot'] = {
        'id': source_snapshot.id,
        'run_id': source_snapshot.run_id,
        'snapshot_reason': source_snapshot.snapshot_reason,
        'payload_hash': source_snapshot.payload_hash,
        'history_record_id': history.id,
        'period_snapshot_ids': {
            'month': month_snapshot.id,
            'year': year_snapshot.id,
        },
    }
    return {
        'source_snapshot_id': source_snapshot.id,
        'source_run_id': source_snapshot.run_id,
        'history_record_id': history.id,
        'month_snapshot_id': month_snapshot.id,
        'year_snapshot_id': year_snapshot.id,
    }


def _formal_history_payload(
    *,
    product: dict[str, Any],
    daily_fact_bundle: Mapping[str, Any],
    output_skill_alignment: Mapping[str, Any],
) -> dict[str, Any]:
    return _json_safe(
        {
            'status': product.get('status'),
            'formal_text': product.get('formal_text'),
            'three_part_text': product.get('text'),
            'brain_judgment': product.get('brain_judgment'),
            'workshop_details': product.get('workshop_details'),
            'missing_fields': product.get('missing_fields') or [],
            'conflicts': product.get('conflicts') or [],
            'facts': daily_fact_bundle.get('facts') or {},
            'sources': daily_fact_bundle.get('sources') or {},
            'correction_refs': daily_fact_bundle.get('correction_refs') or [],
            'dingtalk_refs': daily_fact_bundle.get('dingtalk_refs') or [],
            'output_skill_alignment': _output_skill_alignment_payload(output_skill_alignment),
        }
    )


def _attach_archive_trace_to_report(report: DailyReport, archive_trace: Mapping[str, Any]) -> None:
    report_data = dict(report.report_data or {})
    day1_payload = dict(_as_mapping(report_data.get('hermes_day1_super_brain')))
    day1_payload.update(_json_safe(archive_trace))
    report_data['hermes_day1_super_brain'] = day1_payload
    report.report_data = report_data


def _agent_result_payload(
    *,
    command: HermesDay1Command,
    product: dict[str, Any],
    sources: dict[str, Any],
    report_id: int,
    learning_payload: dict[str, Any],
    correction_action_policy: dict[str, Any],
    harness_results: list[Any],
) -> dict[str, Any]:
    messages = [str(message) for message in product.get('dingtalk_messages') or []]
    alignment_payload = _output_skill_alignment_payload(sources.get('output_skill_alignment'))
    harness_summary = summarize_harness_results(harness_results)
    return {
        'hermes_day1': _json_safe(
            {
                'command': _command_summary(command),
                'status': product.get('status'),
                'report_id': report_id,
                'sources': _source_summary(sources),
                'missing_fields': product.get('missing_fields'),
                'conflicts': product.get('conflicts'),
                'brain_judgment': product.get('brain_judgment'),
                'dingtalk_reply': {
                    'message_count': len(messages),
                    'first_message_chars': len(messages[0]) if messages else 0,
                },
                'output_skill_alignment': alignment_payload,
                'learning': learning_payload,
                'correction_action_policy': correction_action_policy,
                'harness': {
                    'summary': harness_summary,
                    'cases': [asdict(item) for item in harness_results],
                },
            }
        )
    }


def _command_summary(command: HermesDay1Command) -> dict[str, Any]:
    return {
        'raw_text': _command_raw_text(command),
        'business_date': command.business_date.isoformat(),
        'report_type': getattr(command, 'report_type', None),
        'audience': getattr(command, 'audience', None),
        'output_style': getattr(command, 'output_style', None) or getattr(command, 'output_format', None),
        'intent': getattr(command, 'intent', None) or getattr(command, 'report_type', None),
    }


def _command_raw_text(command: HermesDay1Command) -> str:
    return str(getattr(command, 'raw_text', None) or getattr(command, 'source_text', '') or '').strip()


def _source_summary(sources: dict[str, Any]) -> dict[str, Any]:
    template = _as_mapping(sources.get('template_daily_report'))
    daily_fact_bundle = _as_mapping(sources.get('daily_fact_bundle'))
    source_map = _as_mapping(sources.get('source_map'))
    mes_wms = _as_mapping(sources.get('mes_wms'))
    audit = _as_mapping(sources.get('audit_run'))
    rag = _as_mapping(sources.get('rag'))
    return {
        'trace_id': _summary_safe(sources.get('trace_id')),
        'business_date': _summary_safe(sources.get('business_date')),
        'template_daily_report': {
            'status': _summary_safe(template.get('status')),
            'missing_count': len(template.get('missing_fields') or []),
            'conflict_count': len(template.get('conflicts') or []),
        },
        'daily_fact_bundle': {
            'status': _summary_safe(daily_fact_bundle.get('status')),
            'missing_count': len(daily_fact_bundle.get('missing_fields') or daily_fact_bundle.get('missing') or []),
            'conflict_count': len(daily_fact_bundle.get('conflicts') or []),
            'fact_count': len(_as_mapping(daily_fact_bundle.get('facts'))),
            'correction_ref_count': len(daily_fact_bundle.get('correction_refs') or []),
            'dingtalk_ref_count': len(daily_fact_bundle.get('dingtalk_refs') or []),
            'formal_snapshot_id': daily_fact_bundle.get('formal_snapshot_id'),
            'formal_history_record_id': daily_fact_bundle.get('formal_history_record_id'),
        },
        'source_map': _source_map_summary(source_map),
        'mes_wms': {
            'status': _source_status(mes_wms),
            'source_status': _summary_safe(mes_wms.get('source_status')),
            'source_errors': _summary_safe(mes_wms.get('source_errors')),
            'record_groups': len(_as_mapping(mes_wms.get('records'))),
        },
        'audit_run': {
            'id': audit.get('id'),
            'status': _summary_safe(audit.get('status')),
            'source_status': _summary_safe(audit.get('source_status')),
            'source_errors': _summary_safe(audit.get('source_errors')),
            'match_rate': _summary_safe(audit.get('match_rate')),
        },
        'rag': {
            'status': _source_status(rag),
            'source_status': _summary_safe(rag.get('source_status')),
            'source_errors': _summary_safe(rag.get('source_errors')),
            'citation_count': len(rag.get('citations') or []),
        },
        'dingtalk_evidence': _evidence_summary(sources.get('dingtalk_evidence')),
        'dingtalk_messages': _message_summary(sources.get('dingtalk_messages')),
        'historical_reports': _historical_report_summary(sources.get('historical_reports')),
        'output_skill_alignment': _output_skill_alignment_payload(sources.get('output_skill_alignment'), include_differences=False),
    }


def _source_map_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    facts = [item for item in _as_list(value.get('facts')) if isinstance(item, Mapping)]
    delete_protection = sorted(
        {
            str(item.get('delete_protection'))
            for item in facts
            if item.get('delete_protection') not in (None, '')
        }
    )
    return {
        'status': _summary_safe(value.get('status')),
        'metric_count': len(facts),
        'metric_keys': [str(item) for item in _as_list(value.get('metric_keys')) if str(item).strip()],
        'source_explanation_count': len(_as_list(value.get('source_explanations'))),
        'delete_protection': delete_protection,
    }


def _evidence_summary(value: Any) -> dict[str, Any]:
    rows = value if isinstance(value, list) else []
    return {
        'count': len(rows),
        'items': [_pointer_item(row, keys=('id', 'file_uri')) for row in rows[:20] if isinstance(row, Mapping)],
    }


def _message_summary(value: Any) -> dict[str, Any]:
    rows = value if isinstance(value, list) else []
    return {
        'count': len(rows),
        'items': [_pointer_item(row, keys=('id',)) for row in rows[:20] if isinstance(row, Mapping)],
    }


def _historical_report_summary(value: Any) -> dict[str, Any]:
    rows = value if isinstance(value, list) else []
    return {
        'count': len(rows),
        'items': [_pointer_item(row, keys=('id', 'file_uri')) for row in rows[:20] if isinstance(row, Mapping)],
    }


def _pointer_item(item: Mapping[str, Any], *, keys: tuple[str, ...]) -> dict[str, Any]:
    pointer = {
        key: _summary_safe(item.get(key))
        for key in keys
        if item.get(key) not in (None, '')
    }
    pointer.update(_hash_from_payload(item))
    return pointer


def _hash_from_payload(item: Mapping[str, Any]) -> dict[str, Any]:
    payload = _as_mapping(item.get('payload')) or _as_mapping(item.get('source_payload'))
    for key in ('hash', 'payload_hash', 'content_hash'):
        value = payload.get(key)
        if value not in (None, ''):
            return {'hash': _summary_safe(value)}
    return {}


def _growth_feedback_text(*, command: HermesDay1Command, product: dict[str, Any]) -> str:
    status = str(product.get('status') or 'unknown')
    summary = _as_mapping(product.get('brain_judgment')).get('summary') or '暂无判断摘要'
    missing_fields = [str(item) for item in product.get('missing_fields') or [] if str(item).strip()]
    conflicts = product.get('conflicts') or []
    pieces = [
        f"{command.business_date.isoformat()} Day-1 三段式日报生成状态：{status}。",
        f"Hermes 判断：{summary}。",
    ]
    if missing_fields:
        pieces.append(f"缺失字段：{'、'.join(missing_fields)}。")
    if conflicts:
        pieces.append(f"冲突数量：{len(conflicts)}。")
    pieces.append('已记录本次来源收集和三段式生成路径，后续同类日报可复用该查证流程。')
    return redact_secret_text(''.join(pieces))


def _learning_sources(sources: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for name, payload in sources.items():
        if name in {'trace_id', 'business_date'}:
            continue
        item: dict[str, Any] = {'name': str(name), 'status': _source_status(payload)}
        if isinstance(payload, Mapping):
            citations = payload.get('citations')
            records = payload.get('records')
            if isinstance(citations, list):
                item['citation_count'] = len(citations)
            if isinstance(records, Mapping):
                item['record_groups'] = len(records)
            if 'source_status' in payload:
                item['source_status'] = _json_safe(payload.get('source_status'))
        elif isinstance(payload, list):
            item['item_count'] = len(payload)
        result.append(item)
    return result


def _output_skill_alignment_payload(value: Any, *, include_differences: bool = True) -> dict[str, Any]:
    alignment = _as_mapping(value)
    if not alignment:
        return {}
    payload = {
        'status': alignment.get('status'),
        'file_name': alignment.get('file_name'),
        'field_match_rate': alignment.get('field_match_rate'),
        'matched_fields': alignment.get('matched_fields'),
        'expected_fields': alignment.get('expected_fields'),
        'difference_count': alignment.get('difference_count'),
        'char_match_rate': alignment.get('char_match_rate'),
        'exact_match': alignment.get('exact_match'),
        'threshold': alignment.get('threshold'),
        'reference_present_fields': alignment.get('reference_present_fields'),
        'declared_na_fields': alignment.get('declared_na_fields') or [],
        'invalid_na_fields': alignment.get('invalid_na_fields') or [],
        'reference_absent_fields': alignment.get('reference_absent_fields') or [],
        'reference_absent_count': alignment.get('reference_absent_count'),
        'normative_fields': alignment.get('normative_fields'),
        'normative_denominator': alignment.get('normative_denominator'),
        'normative_matched_fields': alignment.get('normative_matched_fields'),
        'normative_coverage_rate': alignment.get('normative_coverage_rate'),
    }
    if include_differences:
        payload['differences'] = [
            {
                'field': item.get('field'),
                'actual': item.get('actual'),
                'expected': item.get('expected'),
            }
            for item in _as_list(alignment.get('differences'))
            if isinstance(item, Mapping)
        ]
    return payload


def _alignment_threshold(sources: dict[str, Any]) -> float:
    alignment = _as_mapping(sources.get('output_skill_alignment'))
    return _report_alignment_threshold(alignment)


def _source_status(payload: Any) -> str:
    if isinstance(payload, Mapping):
        status = payload.get('status')
        if status not in (None, ''):
            return str(status)
        source_status = payload.get('source_status')
        if isinstance(source_status, Mapping):
            values = [str(value) for value in source_status.values() if value not in (None, '')]
            if values:
                return ','.join(values[:3])
        if payload:
            return 'available'
        return 'empty'
    if isinstance(payload, list):
        return 'available' if payload else 'empty'
    return 'available' if payload not in (None, '') else 'empty'


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in filter_sensitive_mapping(dict(value)).items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        return redact_secret_text(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return redact_secret_text(str(value))


def _summary_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _summary_safe(item)
            for key, item in filter_sensitive_mapping(dict(value)).items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_summary_safe(item) for item in list(value)[:20] if item not in (None, '')]
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        return _truncate_summary(redact_secret_text(value))
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return _truncate_summary(redact_secret_text(str(value)))


def _truncate_summary(value: str) -> str:
    return value if len(value) <= 160 else value[:157] + '...'


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]
