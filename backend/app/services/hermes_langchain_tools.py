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
from app.models.system import User
from app.services.hermes_codex_construction_service import request_codex_construction
from app.services.hermes_data_audit_service import HermesDataAuditService
from app.services.hermes_fact_priority_service import PRIORITY as FACT_SOURCE_PRIORITY
from app.services.hermes_long_term_rule_service import list_active_rules
from app.services.hermes_mes_read_service import HermesMesReadService
from app.services.hermes_fact_source_map_service import find_fact_source, source_summary_for_metric
from app.services.rag_service import query_knowledge
from app.services.report import template_daily_report


ToolResult = dict[str, Any]
ToolCallable = Callable[..., ToolResult]

_DINGTALK_EVIDENCE_TYPES = ('text', 'file', 'image', 'attachment', 'dingtalk_file', 'dingtalk_text')
_DINGTALK_TEXT_EVIDENCE_TYPES = {'text', 'dingtalk_text'}
_DINGTALK_FILE_EVIDENCE_TYPES = {'file', 'attachment', 'dingtalk_file'}
_TOOL_GUIDANCE_HINTS: dict[str, dict[str, object]] = {
    'dingtalk_group_content': {
        'priority': FACT_SOURCE_PRIORITY['dingtalk_group_content'],
        'usage': '当前工具优先读取钉钉群聊天和群文件证据。',
    },
    'mes_wms_readonly': {
        'priority': FACT_SOURCE_PRIORITY['mes_wms'],
        'usage': '当前工具读取 MES/WMS 只读事实，不写回外部系统。',
    },
    'data_hub': {
        'priority': FACT_SOURCE_PRIORITY['hub'],
        'usage': '当前工具读取数据中枢 bundle、投影和汇总结果。',
    },
    'rag': {
        'priority': 4,
        'usage': '当前工具只用于规则、定义、历史上下文，不作为当前实时数字事实来源。',
    },
    'fact_source_map': {
        'usage': '具体指标来源以 facts 里的 priority_sources 和 summary 为准。',
    },
}
_METRIC_SOURCE_LABELS: dict[str, str] = {
    'dingtalk_group_content': '钉钉群聊天/群文件',
    'dingtalk_specialist': '钉钉专项责任人证据',
    'mes/wms readonly': 'MES/WMS 只读事实',
    'wms final document': 'WMS 最终单据',
    'data_hub_projection': '数据中枢投影',
    'data_hub_manual': '数据中枢人工录入',
    'dailyfactbundle': 'DailyFactBundle',
    'daily_reports': '历史日报',
    'historical_report': '历史日报',
    'rag': 'RAG 规则/定义/历史上下文',
    'computed': '计算口径',
    'root_owner': '最高权限负责人修正',
    'operationperiodsnapshot': '周期快照',
    'dailyreporthistoryrecord': '日报历史记录',
    'multimodal_evidence': '多模态证据',
    'data_quality_issues': '数据质量问题记录',
    'authorized_group': '授权群条件',
    'specialist_sender': '专项责任人发送条件',
    'content_type': '内容类型条件',
    'time_range': '时间范围条件',
    'iot_energy_future': '后续物联网能耗来源',
}


@dataclass(frozen=True, slots=True)
class HermesToolAdapters:
    hub_query: ToolCallable
    mes_wms_read: ToolCallable
    dingtalk_evidence: ToolCallable
    rag_route: ToolCallable
    history_report: ToolCallable
    output_skill_alignment: ToolCallable
    long_term_rules: ToolCallable
    system_optimization: ToolCallable
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
        'system_optimization': adapters.system_optimization,
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
    current_user: User | None = None,
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
        system_optimization=partial(_system_optimization_tool, db=db, current_user=current_user),
        source_map=_source_map_tool,
    )


def _hub_query_tool(*, db: Session, **kwargs: object) -> ToolResult:
    try:
        business_date = _parse_business_date(kwargs.get('business_date'))
        payload = template_daily_report.build_template_daily_report_payload(db, target_date=business_date)
        return _tool_result(
            status=payload.get('status', 'ok'),
            source='data_hub',
            kwargs=kwargs,
            facts=payload.get('facts') or payload.get('hermes_fact_bundle') or {},
        )
    except Exception as exc:
        return _unavailable('data_hub', kwargs, exc)


def _mes_wms_read_tool(*, mes_read_service: HermesMesReadService | None, **kwargs: object) -> ToolResult:
    query_keys = _string_list(kwargs.get('query_keys'), ['workshop_process_records', 'finished_inbound_records'])
    if mes_read_service is None:
        return _tool_result(
            status='unavailable',
            source='mes_wms_readonly',
            kwargs=kwargs,
            facts={},
            reason='mes_read_service_missing',
            source_health=_mes_read_health(
                mes_read_service=None,
                query_keys=query_keys,
                facts={},
                fallback_errors={'service': 'mes_read_service_missing'},
                service_status='missing',
            ),
        )
    try:
        business_date = _parse_business_date(kwargs.get('business_date'))
        facts = mes_read_service.read_sources(
            business_date=business_date,
            query_keys=query_keys,
            workshop_name=str(kwargs.get('workshop_name') or '').strip() or None,
        )
        return _tool_result(
            status='ok',
            source='mes_wms_readonly',
            kwargs=kwargs,
            facts=facts,
            source_health=_mes_read_health(
                mes_read_service=mes_read_service,
                query_keys=query_keys,
                facts=facts,
            ),
        )
    except Exception as exc:
        return _unavailable(
            'mes_wms_readonly',
            kwargs,
            exc,
            source_health=_mes_read_health(
                mes_read_service=mes_read_service,
                query_keys=query_keys,
                facts={},
                fallback_errors={'service': redact_secret_text(str(exc))},
                service_status='failed',
            ),
        )


def _dingtalk_evidence_tool(*, db: Session, **kwargs: object) -> ToolResult:
    try:
        limit = _int_arg(kwargs.get('limit'), default=20, minimum=1, maximum=100)
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
        return _tool_result(
            status='ok',
            source='dingtalk_group_content',
            kwargs=kwargs,
            facts=[fact for _sort_key, fact in candidates[:limit]],
        )
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


def _rag_route_tool(*, db: Session, current_user: User | None, **kwargs: object) -> ToolResult:
    try:
        result = query_knowledge(
            db,
            query=str(kwargs.get('query') or kwargs.get('text') or ''),
            limit=_int_arg(kwargs.get('limit'), default=5, minimum=1, maximum=50),
            user=current_user,
            workshop=str(kwargs.get('workshop') or '').strip() or None,
            machine_code=str(kwargs.get('machine_code') or '').strip() or None,
        )
        return _tool_result(status='ok', source='rag', kwargs=kwargs, facts=result)
    except Exception as exc:
        return _unavailable('rag', kwargs, exc)


def _history_report_tool(*, db: Session, **kwargs: object) -> ToolResult:
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
        return _tool_result(status='ok', source='daily_reports', kwargs=kwargs, facts=facts)
    except Exception as exc:
        return _unavailable('daily_reports', kwargs, exc)


def _output_skill_alignment_tool(
    *,
    db: Session,
    output_skill_root: str | Path | None,
    **kwargs: object,
) -> ToolResult:
    try:
        service = HermesDataAuditService(db, output_skill_root=output_skill_root)
        run = service.create_run(
            business_date=_parse_business_date(kwargs.get('business_date')),
            fields=_string_list(kwargs.get('fields'), []),
            mes_query_keys=_string_list(kwargs.get('mes_query_keys'), []),
        )
        return _tool_result(
            status=run.status,
            source='output_skill_alignment',
            kwargs=kwargs,
            facts={'run_id': run.id},
        )
    except Exception as exc:
        return _unavailable('output_skill_alignment', kwargs, exc)


def _long_term_rules_tool(*, db: Session, **kwargs: object) -> ToolResult:
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
        return _tool_result(status='ok', source='long_term_rules', kwargs=kwargs, facts=facts)
    except Exception as exc:
        return _unavailable('long_term_rules', kwargs, exc)


def _source_map_tool(**kwargs: object) -> ToolResult:
    try:
        metric_key = str(kwargs.get('metric_key') or '').strip()
        item = find_fact_source(metric_key)
        return _tool_result(
            status='ok',
            source='fact_source_map',
            kwargs=kwargs,
            facts={**item, 'summary': source_summary_for_metric(metric_key)},
        )
    except Exception as exc:
        return _unavailable('fact_source_map', kwargs, exc)


def _system_optimization_tool(*, db: Session, current_user: User | None, **kwargs: object) -> ToolResult:
    if current_user is None:
        return _tool_result(
            status='denied',
            source='system_optimization',
            kwargs=kwargs,
            facts={'message': '缺少最高权限负责人身份'},
        )
    result = request_codex_construction(
        db,
        actor=current_user,
        request_text=str(kwargs.get('raw_text') or kwargs.get('text') or ''),
        trace_id=str(kwargs.get('trace_id') or ''),
        construction_type=str(kwargs.get('construction_type') or 'light'),
    )
    return _tool_result(
        status=result.status,
        source='system_optimization',
        kwargs=kwargs,
        facts={'run_id': result.run_id, 'message': result.message},
    )


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


def _int_arg(value: object, *, default: int, minimum: int, maximum: int) -> int:
    if value is None or value == '':
        parsed = default
    elif isinstance(value, bool):
        parsed = int(value)
    elif isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        parsed = int(value)
    elif isinstance(value, str):
        try:
            parsed = int(value.strip() or default)
        except ValueError:
            parsed = default
    else:
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError, OverflowError):
            parsed = default
    return max(minimum, min(parsed, maximum))


def _tool_result(
    *,
    status: str,
    source: str,
    kwargs: Mapping[str, object],
    facts: object,
    **extra: object,
) -> ToolResult:
    payload: ToolResult = {
        'status': status,
        'source': source,
        'request': _request_payload(kwargs),
        'facts': facts,
        'source_guidance': _source_guidance(source, kwargs),
    }
    payload.update(extra)
    return payload


def _source_guidance(source: str, kwargs: Mapping[str, object]) -> dict[str, object]:
    hint = _TOOL_GUIDANCE_HINTS.get(source, {})
    guidance = {
        'tool_source': source,
        'tool_priority': hint.get('priority'),
        'tool_usage': hint.get('usage', '当前工具不会改变四层来源优先级，只提供补充信息。'),
        'source_rules': [
            '钉钉群聊天/群文件优先于一般汇总结果时，应按来源地图和 trace 判断。',
            'MES/WMS 只读来源只能读，不能写回外部系统。',
            'RAG 只用于规则、定义、历史上下文，不作为当前实时数字事实来源。',
        ],
    }
    metric_key = str(kwargs.get('metric_key') or '').strip()
    if metric_key and source != 'fact_source_map':
        priority_order = _metric_priority_order(metric_key)
        if priority_order is not None:
            guidance['metric_key'] = metric_key
            guidance['priority_order'] = priority_order
    return guidance


def _metric_priority_order(metric_key: str) -> list[dict[str, object]] | None:
    try:
        item = find_fact_source(metric_key)
    except KeyError:
        return None
    priority_sources = item.get('priority_sources')
    if not isinstance(priority_sources, list):
        return None
    result: list[dict[str, object]] = []
    for index, source_name in enumerate(priority_sources, start=1):
        source_text = str(source_name)
        result.append(
            {
                'priority': index,
                'source_key': source_text,
                'label': _metric_source_label(source_text),
                'current_numeric_fact': _metric_source_is_current_fact(source_text),
            }
        )
    return result


def _metric_source_label(source_name: str) -> str:
    clean_name = str(source_name).strip()
    return _METRIC_SOURCE_LABELS.get(clean_name.lower(), clean_name)


def _metric_source_is_current_fact(source_name: str) -> bool:
    return 'rag' not in str(source_name).strip().lower()


def _mes_read_health(
    *,
    mes_read_service: HermesMesReadService | None,
    query_keys: list[str],
    facts: Mapping[str, object],
    fallback_errors: Mapping[str, str] | None = None,
    service_status: str | None = None,
) -> dict[str, object]:
    source_errors = _sanitize_source_errors(facts.get('source_errors') or fallback_errors or {})
    adapter = getattr(mes_read_service, '_adapter', None) if mes_read_service is not None else None
    return {
        'adapter': type(adapter).__name__ if adapter is not None else (
            type(mes_read_service).__name__ if mes_read_service is not None else 'service_missing'
        ),
        'readonly': True,
        'query_keys': query_keys,
        'source_errors': source_errors,
        'record_count': _record_count((facts.get('records') or {})) if isinstance(facts, Mapping) else 0,
        'service_status': service_status
        or str(((facts.get('source_status') or {}) if isinstance(facts, Mapping) else {}).get('mes') or 'unknown'),
    }


def _sanitize_source_errors(source_errors: object) -> dict[str, str]:
    if not isinstance(source_errors, Mapping):
        return {}
    return {
        str(key): redact_secret_text(str(value))
        for key, value in source_errors.items()
    }


def _record_count(records: object) -> int:
    if isinstance(records, Mapping):
        return sum(_record_count(value) for value in records.values())
    if isinstance(records, list):
        return len(records)
    if records is None:
        return 0
    return 1


def _unavailable(source: str, kwargs: Mapping[str, object], exc: Exception, **extra: object) -> ToolResult:
    return _tool_result(
        status='unavailable',
        source=source,
        kwargs=kwargs,
        facts={},
        reason=redact_secret_text(str(exc)),
        **extra,
    )
