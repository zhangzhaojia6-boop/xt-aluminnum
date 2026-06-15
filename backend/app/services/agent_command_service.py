from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.business_time import resolve_production_business_date
from app.core.redaction import filter_sensitive_mapping
from app.core.scope import build_scope_summary
from app.core.templates.consumable_payload import flatten_payload, parse_payload
from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.consumable import DailyConsumableLog
from app.models.master import Workshop
from app.models.master import Equipment
from app.models.production import ShiftProductionData
from app.models.quality import DataQualityIssue, QualityIssueLog
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import agent_communication_service
from app.services import energy_service
from app.services import realtime_service
from app.services.rag_service import query_knowledge


class AgentCommandError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AgentCommandResult:
    trace_id: str
    status_color: str
    intent: str
    facts: dict[str, Any]
    answer: str
    rag: dict[str, Any]
    chat_inbox_id: int
    agent_run_id: int
    outbox_message_id: int | None


def handle_agent_command(
    db: Session,
    *,
    channel: str,
    group_id: str | None,
    sender_external_id: str | None,
    text: str,
    agent_code: str | None,
    trace_id: str | None,
    workshop: str | None = None,
    machine_code: str | None = None,
    queue_outbox: bool = False,
    source_payload: dict[str, Any] | None = None,
    current_user: User | None = None,
) -> AgentCommandResult:
    clean_text = _clean(text)
    if not clean_text:
        raise AgentCommandError('command_text_required')

    clean_channel = _clean(channel) or 'internal'
    clean_agent_code = _clean(agent_code) or 'factory_dispatch'
    clean_trace_id = _clean(trace_id) or uuid4().hex
    clean_workshop = _clean(workshop) or None
    clean_machine_code = _clean(machine_code) or None
    safe_source_payload = filter_sensitive_mapping(source_payload or {})

    inbox = ChatInboxMessage(
        channel=clean_channel,
        group_id=_clean(group_id) or None,
        sender_external_id=_clean(sender_external_id) or None,
        text=clean_text,
        agent_code=clean_agent_code,
        trace_id=clean_trace_id,
        source_payload=safe_source_payload,
    )
    db.add(inbox)
    db.flush()

    rag_payload = query_knowledge(
        db,
        query=clean_text,
        limit=5,
        user=current_user,
        workshop=clean_workshop,
        machine_code=clean_machine_code,
    )
    citations = rag_payload.get('citations') or []
    intent = _detect_intent(clean_text)
    facts = _load_business_facts(db, intent=intent, text=clean_text, current_user=current_user)
    status_color = _resolve_status_color(facts=facts, citations=citations)
    answer = _build_answer_for_intent(
        intent=intent,
        status_color=status_color,
        facts=facts,
        rag_answer=rag_payload.get('answer'),
        citations=citations,
    )

    result_payload = {
        'status_color': status_color,
        'intent': intent,
        'fact_status': facts.get('status', 'not_connected'),
        'facts': facts,
        'rag': {
            'answer': rag_payload.get('answer'),
            'citations': citations,
            'scope': {
                'workshop': clean_workshop,
                'machine_code': clean_machine_code,
            },
        },
        'source_payload': safe_source_payload,
    }
    run = AgentRun(
        trace_id=clean_trace_id,
        agent_code=clean_agent_code,
        chat_inbox_id=inbox.id,
        status='answered',
        status_color=status_color,
        answer=answer,
        rag_citation_count=len(citations),
        result_payload=result_payload,
    )
    db.add(run)
    db.flush()

    outbox_message_id: int | None = None
    if queue_outbox:
        channel_key = _clean(group_id)
        if not channel_key:
            raise AgentCommandError('group_id_required_for_outbox')
        try:
            message = agent_communication_service.queue_bound_message(
                db,
                agent_code=clean_agent_code,
                channel_key=channel_key,
                channel_type=clean_channel,
                title=_outbox_title_for_intent(clean_agent_code, intent),
                content=answer,
                source_summary=_outbox_source_summary_for_intent(intent),
                trace_id=clean_trace_id,
                payload={
                    'chat_inbox_id': inbox.id,
                    'agent_run_id': run.id,
                    'intent': intent,
                    'fact_status': facts.get('status', 'not_connected'),
                    'rag_citation_count': len(citations),
                },
                dedupe_key=_build_command_dedupe_key(
                    channel=clean_channel,
                    group_id=channel_key,
                    agent_code=clean_agent_code,
                    text=clean_text,
                ),
            )
        except agent_communication_service.AgentCommunicationError as exc:
            raise AgentCommandError(str(exc)) from exc
        outbox_message_id = message.id
        run.result_payload = {**result_payload, 'outbox_message_id': outbox_message_id}
        db.flush()

    return AgentCommandResult(
        trace_id=clean_trace_id,
        intent=intent,
        facts=facts,
        status_color=status_color,
        answer=answer,
        rag={
            'answer': rag_payload.get('answer'),
            'citations': citations,
            'items': rag_payload.get('items') or [],
            'scope': {
                'workshop': clean_workshop,
                'machine_code': clean_machine_code,
            },
        },
        chat_inbox_id=inbox.id,
        agent_run_id=run.id,
        outbox_message_id=outbox_message_id,
    )


def _clean(value: str | None) -> str:
    return str(value or '').strip()


def _status_label(status_color: str) -> str:
    return {
        'green': '绿',
        'yellow': '黄',
        'orange': '橙',
        'red': '红',
    }.get(status_color, '黄')


def _detect_intent(text: str) -> str:
    value = _clean(text)
    checks = (
        ('quality_anomaly', ('质量', '缺陷', '门禁')),
        ('machine_stop', ('停机', '为什么停', '维修', '换辊')),
        ('energy_cost', ('能耗', '电耗', '吨耗', '电气', '成本')),
        ('consumable_usage', ('辅材', '耗材', '超耗', '消耗')),
        ('production_today', ('今日产量', '今天产量', '日产量', '产量')),
        ('anomaly_summary', ('异常', '哪个车间')),
    )
    for intent, keywords in checks:
        if any(keyword in value for keyword in keywords):
            return intent
    return 'general_knowledge'


def _load_business_facts(db: Session, *, intent: str, text: str, current_user: User | None) -> dict[str, Any]:
    if (
        intent
        not in {'production_today', 'anomaly_summary', 'consumable_usage', 'machine_stop', 'quality_anomaly', 'energy_cost'}
        or current_user is None
    ):
        return {'status': 'not_connected'}

    business_date = resolve_production_business_date()
    if intent == 'energy_cost':
        return _extract_energy_cost_facts(db, business_date=business_date, current_user=current_user)
    if intent == 'consumable_usage':
        return _extract_consumable_facts(db, business_date=business_date, current_user=current_user)
    if intent == 'machine_stop':
        return _extract_machine_stop_facts(
            db,
            business_date=business_date,
            command_text=text,
            current_user=current_user,
        )
    if intent == 'quality_anomaly':
        return _extract_quality_facts(db, business_date=business_date, current_user=current_user)

    try:
        payload = _load_live_aggregation(db, business_date=business_date, current_user=current_user)
    except SQLAlchemyError:
        return {
            'status': 'not_connected',
            'reason': 'live_aggregation_unavailable',
            'business_date': business_date.isoformat(),
        }

    if intent == 'anomaly_summary':
        return _extract_anomaly_facts(payload=payload, business_date=business_date)

    factory_total = payload.get('factory_total') or {}
    return {
        'status': 'connected',
        'business_date': payload.get('business_date') or business_date.isoformat(),
        'business_day_start': factory_total.get('business_day_start') or '07:30',
        'daily_output_tons': _number_or_zero(factory_total.get('daily_output')),
        'packaging_output_tons': _number_or_zero(factory_total.get('packaging_output')),
        'finished_inbound_output_tons': _number_or_zero(factory_total.get('finished_inbound_output')),
        'daily_output_source': factory_total.get('daily_output_source') or 'unknown',
        'finished_inbound_source': factory_total.get('finished_inbound_source') or 'unknown',
        'mes_sync_status': (payload.get('mes_sync_status') or {}).get('status'),
        'data_source': payload.get('data_source') or 'unknown',
    }


def _extract_energy_cost_facts(db: Session, *, business_date, current_user: User) -> dict[str, Any]:
    scoped_workshop_id = _scoped_workshop_id_for_facts(current_user)
    try:
        summary = energy_service.summarize_energy_for_date(
            db,
            business_date=business_date,
            workshop_id=scoped_workshop_id,
        )
    except SQLAlchemyError:
        return {
            'status': 'not_connected',
            'reason': 'energy_summary_unavailable',
            'business_date': business_date.isoformat(),
        }

    total_energy = _number_or_zero(summary.get('total_energy'))
    energy_per_ton = _optional_number(summary.get('energy_per_ton'))
    return {
        'status': 'connected',
        'status_color': 'green' if total_energy > 0 else 'yellow',
        'business_date': business_date.isoformat(),
        'business_day_start': '07:30',
        'electricity_kwh': _number_or_zero(summary.get('electricity_value')),
        'gas_m3': _number_or_zero(summary.get('gas_value')),
        'water_ton': _number_or_zero(summary.get('water_value')),
        'total_energy': total_energy,
        'output_weight_tons': _number_or_zero(summary.get('total_output_weight')),
        'output_basis': summary.get('output_basis') or 'unknown',
        'energy_per_ton': round(energy_per_ton, 2) if energy_per_ton is not None else None,
        'primary_source': summary.get('primary_source') or 'none',
        'mobile_row_count': _int_or_zero((summary.get('mobile_totals') or {}).get('row_count')),
        'owner_row_count': _int_or_zero((summary.get('owner_totals') or {}).get('row_count')),
        'system_row_count': _int_or_zero((summary.get('system_totals') or {}).get('row_count')),
        'cost_status': 'unconfigured',
        'cost_value': None,
        'data_source': 'energy_service.summarize_energy_for_date',
    }


def _extract_machine_stop_facts(
    db: Session,
    *,
    business_date,
    command_text: str,
    current_user: User,
) -> dict[str, Any]:
    machine_filter = _extract_machine_filter(command_text)
    scoped_workshop_id = _scoped_workshop_id_for_facts(current_user)
    query = (
        db.query(ShiftProductionData, Workshop, Equipment, ShiftConfig)
        .join(Workshop, Workshop.id == ShiftProductionData.workshop_id)
        .outerjoin(Equipment, Equipment.id == ShiftProductionData.equipment_id)
        .outerjoin(ShiftConfig, ShiftConfig.id == ShiftProductionData.shift_config_id)
        .filter(
            ShiftProductionData.business_date == business_date,
            ShiftProductionData.downtime_minutes > 0,
            ShiftProductionData.data_status != 'voided',
        )
    )
    if scoped_workshop_id is not None:
        query = query.filter(ShiftProductionData.workshop_id == scoped_workshop_id)
    rows = query.order_by(ShiftProductionData.downtime_minutes.desc(), Workshop.sort_order.asc()).all()
    stop_items = []
    for row, workshop, equipment, shift in rows:
        if machine_filter and not _matches_machine_filter(equipment, machine_filter):
            continue
        minutes = _int_or_zero(row.downtime_minutes)
        stop_items.append({
            'workshop_name': workshop.name,
            'workshop_code': workshop.code,
            'equipment_name': equipment.name if equipment else '未标记机列',
            'equipment_code': equipment.code if equipment else '',
            'shift_name': shift.name if shift else '未标记班次',
            'downtime_minutes': minutes,
            'downtime_reason': row.downtime_reason or '未填写原因',
            'data_status': row.data_status,
            'data_source': row.data_source,
        })

    max_minutes = max([item['downtime_minutes'] for item in stop_items], default=0)
    return {
        'status': 'connected',
        'status_color': _machine_stop_status_color(max_minutes),
        'business_date': business_date.isoformat(),
        'business_day_start': '07:30',
        'machine_filter': machine_filter,
        'stop_count': len(stop_items),
        'max_downtime_minutes': max_minutes,
        'top_stops': stop_items[:5],
        'data_source': 'shift_production_data',
    }


def _scoped_workshop_id_for_facts(current_user: User | None) -> int | None:
    if current_user is None:
        return None
    scope = build_scope_summary(current_user)
    if scope.is_admin or scope.data_scope_type == 'all':
        return None
    return scope.workshop_id


def _extract_machine_filter(text: str) -> str | None:
    value = _clean(text)
    match = re.search(r'(\d+)\s*(?:#|号)?\s*机', value)
    if match:
        return match.group(1)
    return None


def _matches_machine_filter(equipment: Equipment | None, machine_filter: str) -> bool:
    if equipment is None:
        return False
    token = str(machine_filter)
    name = str(equipment.name or '')
    code = str(equipment.code or '')
    return (
        f'{token}号' in name
        or f'{token}#' in name
        or name.strip() == token
        or code.endswith(f'-{token}')
        or code.endswith(f'#{token}')
        or code == token
    )


def _machine_stop_status_color(minutes: int) -> str:
    if minutes >= 60:
        return 'red'
    if minutes >= 30:
        return 'orange'
    if minutes >= 10:
        return 'yellow'
    return 'green'


def _extract_quality_facts(db: Session, *, business_date, current_user: User) -> dict[str, Any]:
    scoped_workshop_id = _scoped_workshop_id_for_facts(current_user)
    scoped_workshop = db.get(Workshop, int(scoped_workshop_id)) if scoped_workshop_id is not None else None
    quality_rows = (
        db.query(DataQualityIssue)
        .filter(
            DataQualityIssue.business_date == business_date,
            DataQualityIssue.status == 'open',
        )
        .order_by(DataQualityIssue.issue_level.asc(), DataQualityIssue.id.desc())
        .all()
    )
    if scoped_workshop is not None:
        quality_rows = [
            item
            for item in quality_rows
            if _data_quality_issue_visible_to_workshop(item, scoped_workshop)
        ]

    issue_query = (
        db.query(QualityIssueLog, Workshop)
        .outerjoin(Workshop, Workshop.id == QualityIssueLog.workshop_id)
        .filter(QualityIssueLog.business_date == business_date)
    )
    if scoped_workshop_id is not None:
        issue_query = issue_query.filter(QualityIssueLog.workshop_id == scoped_workshop_id)
    issue_rows = issue_query.order_by(QualityIssueLog.id.desc()).all()
    blockers = [item for item in quality_rows if item.issue_level in {'blocker', 'blocked', 'critical', 'red'}]
    warnings = [item for item in quality_rows if item not in blockers]
    status_color = 'red' if blockers else ('yellow' if warnings or issue_rows else 'green')
    return {
        'status': 'connected',
        'status_color': status_color,
        'business_date': business_date.isoformat(),
        'business_day_start': '07:30',
        'blocker_count': len(blockers),
        'warning_count': len(warnings),
        'quality_issue_count': len(issue_rows),
        'top_blockers': [_quality_gate_item(item) for item in blockers[:5]],
        'top_quality_issues': [_quality_log_item(item, workshop) for item, workshop in issue_rows[:5]],
        'data_source': 'data_quality_issues+quality_issue_log',
    }


def _data_quality_issue_visible_to_workshop(item: DataQualityIssue, workshop: Workshop) -> bool:
    dimension_key = _clean(item.dimension_key).casefold()
    if not dimension_key.startswith('workshop:'):
        return True
    requested = dimension_key.split(':', 1)[1].strip()
    allowed = {
        str(workshop.id).casefold(),
        str(workshop.code or '').strip().casefold(),
        str(workshop.name or '').strip().casefold(),
    }
    return requested in allowed


def _quality_gate_item(item: DataQualityIssue) -> dict[str, Any]:
    return {
        'issue_type': item.issue_type,
        'issue_level': item.issue_level,
        'source_type': item.source_type,
        'dimension_key': item.dimension_key,
        'field_name': item.field_name,
        'issue_desc': item.issue_desc,
    }


def _quality_log_item(item: QualityIssueLog, workshop: Workshop | None) -> dict[str, Any]:
    return {
        'workshop_name': workshop.name if workshop else '未标记车间',
        'tracking_card_no': item.tracking_card_no or '',
        'quality_issue_type': item.quality_issue_type or '',
        'quality_issue_desc': item.quality_issue_desc or '未填写描述',
    }


CONSUMABLE_TARGET_GROUPS: tuple[tuple[str, str, str], ...] = (
    ('hydraulic_oil', '液压油', '桶'),
    ('gear_oil', '齿轮油', '桶'),
)


def _extract_consumable_facts(db: Session, *, business_date, current_user: User) -> dict[str, Any]:
    scoped_workshop_id = _scoped_workshop_id_for_facts(current_user)
    query = (
        db.query(DailyConsumableLog, Workshop)
        .join(Workshop, Workshop.id == DailyConsumableLog.workshop_id)
        .filter(DailyConsumableLog.business_date == business_date)
    )
    if scoped_workshop_id is not None:
        query = query.filter(DailyConsumableLog.workshop_id == scoped_workshop_id)
    rows = query.order_by(Workshop.sort_order.asc(), Workshop.id.asc()).all()
    over_quota: list[dict[str, Any]] = []
    checked_count = 0
    unchecked_value_count = 0
    for log, workshop in rows:
        payload = flatten_payload(parse_payload(dict(log.payload or {})))
        for prefix, label, unit in CONSUMABLE_TARGET_GROUPS:
            daily = _optional_number(payload.get(f'{prefix}_daily'))
            target = _optional_number(payload.get(f'{prefix}_target'))
            if daily is None:
                continue
            if target is None or target <= 0:
                unchecked_value_count += 1
                continue
            checked_count += 1
            ratio = round(daily / target * 100, 2)
            if ratio < 110:
                continue
            over_quota.append({
                'workshop_name': workshop.name,
                'workshop_code': workshop.code,
                'field': prefix,
                'label': label,
                'daily': round(daily, 2),
                'target': round(target, 2),
                'unit': unit,
                'ratio': ratio,
                'status_color': 'orange' if ratio >= 120 else 'yellow',
            })

        unchecked_value_count += _count_unchecked_consumable_values(payload)

    over_quota.sort(key=lambda item: (-float(item['ratio']), str(item['workshop_name']), str(item['label'])))
    status_color = _consumable_status_color(over_quota)
    return {
        'status': 'connected',
        'status_color': status_color,
        'business_date': business_date.isoformat(),
        'business_day_start': '07:30',
        'log_count': len(rows),
        'checked_target_count': checked_count,
        'unchecked_value_count': unchecked_value_count,
        'over_quota_count': len(over_quota),
        'top_over_quota': over_quota[:5],
        'data_source': 'daily_consumable_logs',
    }


def _optional_number(value: Any) -> float | None:
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _count_unchecked_consumable_values(payload: dict[str, Any]) -> int:
    count = 0
    for key, value in payload.items():
        if value in (None, ''):
            continue
        if key.endswith(('_target', '_compare', '_monthly')):
            continue
        if any(key == f'{prefix}_daily' for prefix, _label, _unit in CONSUMABLE_TARGET_GROUPS):
            continue
        if _optional_number(value) is not None:
            count += 1
    return count


def _consumable_status_color(items: list[dict[str, Any]]) -> str:
    if any(item.get('status_color') == 'orange' for item in items):
        return 'orange'
    if items:
        return 'yellow'
    return 'green'


def _load_live_aggregation(db: Session, *, business_date, current_user: User) -> dict:
    return realtime_service.build_live_aggregation(
        db,
        business_date=business_date,
        workshop_id=None,
        current_user=current_user,
    )


def _resolve_status_color(*, facts: dict[str, Any], citations: list[dict[str, Any]]) -> str:
    if facts.get('status_color'):
        return str(facts['status_color'])
    if facts.get('status') == 'connected':
        return 'green'
    return 'green' if citations else 'yellow'


def _extract_anomaly_facts(*, payload: dict[str, Any], business_date) -> dict[str, Any]:
    pending_assignment = ((payload.get('overall_progress') or {}).get('pending_assignment') or {})
    missing_output = ((payload.get('data_quality') or {}).get('missing_output_weight') or {})
    pending_count = _int_or_zero(pending_assignment.get('entry_count'))
    missing_output_count = _int_or_zero(missing_output.get('entry_count'))
    anomaly_count = pending_count + missing_output_count
    top_workshops = _top_anomaly_workshops(pending_assignment=pending_assignment, missing_output=missing_output)
    status_color = 'orange' if anomaly_count else 'green'
    return {
        'status': 'connected',
        'status_color': status_color,
        'business_date': payload.get('business_date') or business_date.isoformat(),
        'business_day_start': '07:30',
        'anomaly_count': anomaly_count,
        'pending_assignment_count': pending_count,
        'missing_output_weight_count': missing_output_count,
        'pending_assignment_workshop_count': _int_or_zero(pending_assignment.get('workshop_count')),
        'top_workshops': top_workshops,
        'mes_sync_status': (payload.get('mes_sync_status') or {}).get('status'),
        'data_source': payload.get('data_source') or 'unknown',
    }


def _top_anomaly_workshops(*, pending_assignment: dict[str, Any], missing_output: dict[str, Any]) -> list[str]:
    counts: dict[str, int] = {}
    for row in pending_assignment.get('rows') or []:
        name = _clean(row.get('workshop_name')) or '未标记车间'
        counts[name] = counts.get(name, 0) + _int_or_zero(row.get('entry_count'))
    for item in missing_output.get('items') or []:
        name = _clean(item.get('workshop_name')) or '未标记车间'
        counts[name] = counts.get(name, 0) + 1
    return [
        name
        for name, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _number_or_zero(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _build_answer_for_intent(
    *,
    intent: str,
    status_color: str,
    facts: dict[str, Any],
    rag_answer: Any,
    citations: list[dict[str, Any]],
) -> str:
    if intent == 'production_today' and facts.get('status') == 'connected':
        return _format_answer(
            scope_label='全厂',
            status_color=status_color,
            conclusion='已读取今日生产聚合',
            key_numbers=(
                f"包装产量 {_format_tons(facts.get('daily_output_tons'))} 吨；"
                f"全厂入库产量 {_format_tons(facts.get('finished_inbound_output_tons'))} 吨；"
                f"业务日 {facts.get('business_date')}"
            ),
            reason=(
                '包装产量复用生产大屏同口径，优先取外部 MES 包装数据；'
                '全厂入库产量保留内勤成品入库对照。'
            ),
            action='如数字异常，请查看生产大屏、昨日日报和来源标签。',
            sources=_format_fact_sources(facts, citations),
        )

    if intent == 'anomaly_summary' and facts.get('status') == 'connected':
        anomaly_count = _int_or_zero(facts.get('anomaly_count'))
        top_workshops = facts.get('top_workshops') or []
        conclusion = '当前发现需处理异常' if anomaly_count else '当前未发现实时异常'
        return _format_answer(
            scope_label='全厂',
            status_color=status_color,
            conclusion=conclusion,
            key_numbers=(
                f"未匹配机列/班次 {_int_or_zero(facts.get('pending_assignment_count'))} 条；"
                f"缺下机量 {_int_or_zero(facts.get('missing_output_weight_count'))} 条；"
                f"重点车间 {_format_workshop_list(top_workshops)}"
            ),
            reason='复用生产大屏实时异常口径，统计未匹配机列/班次和缺下机量两类待处理项。',
            action='先处理重点车间待分配卷和缺下机量记录，再刷新生产大屏复核。',
            sources='实时聚合 / overall_progress.pending_assignment；实时聚合 / data_quality.missing_output_weight',
        )

    if intent == 'consumable_usage' and facts.get('status') == 'connected':
        over_quota_count = _int_or_zero(facts.get('over_quota_count'))
        conclusion = '发现辅材超耗' if over_quota_count else '未发现超过报警阈值的辅材'
        return _format_answer(
            scope_label='全厂',
            status_color=status_color,
            conclusion=conclusion,
            key_numbers=(
                f"超耗 {over_quota_count} 项；"
                f"已校验 {facts.get('checked_target_count') or 0} 项；"
                f"无定额无法判定 {facts.get('unchecked_value_count') or 0} 项；"
                f"重点 {_format_consumable_over_quota(facts.get('top_over_quota') or [])}"
            ),
            reason='按 daily_consumable_logs 中已配置目标值的辅材项计算，达到 110% 预警、120% 升级。',
            action='先核对超耗车间的辅材填报和定额配置；无定额字段需补定额后才能自动判定。',
            sources='辅材日报 / daily_consumable_logs',
        )

    if intent == 'energy_cost' and facts.get('status') == 'connected':
        return _format_answer(
            scope_label='全厂',
            status_color=status_color,
            conclusion='已读取今日能耗汇总' if _number_or_zero(facts.get('total_energy')) > 0 else '当前未收到有效能耗汇总',
            key_numbers=(
                f"电量 {_format_tons(facts.get('electricity_kwh'))} 度；"
                f"气量 {_format_tons(facts.get('gas_m3'))} 立方；"
                f"产量分母 {_format_tons(facts.get('output_weight_tons'))} 吨；"
                f"吨耗 {_format_energy_per_ton(facts.get('energy_per_ton'))}；"
                f"成本金额{_format_cost_value(facts)}"
            ),
            reason=(
                '能耗复用管理端能耗汇总口径，优先采用电工班次填报和机台明细，'
                '再保留内勤每日一录、旧导入和物联网影子来源。'
            ),
            action='先核对能耗页来源标签；成本单价未配置前，只看电量、气量和吨耗，不自动估算金额。',
            sources=_format_energy_sources(facts),
        )

    if (
        intent == 'machine_stop'
        and facts.get('status') == 'connected'
        and (_int_or_zero(facts.get('stop_count')) > 0 or not citations)
    ):
        stop_count = _int_or_zero(facts.get('stop_count'))
        conclusion = '发现停机记录' if stop_count else '当前未找到匹配停机记录'
        return _format_answer(
            scope_label='全厂',
            status_color=status_color,
            conclusion=conclusion,
            key_numbers=(
                f"停机 {stop_count} 条；"
                f"最长 {_int_or_zero(facts.get('max_downtime_minutes'))} 分钟；"
                f"重点 {_format_machine_stop_list(facts.get('top_stops') or [])}"
            ),
            reason=_format_machine_stop_reason(facts.get('top_stops') or []),
            action='超过 30 分钟需车间负责人确认恢复时间；超过 60 分钟需升级到总控群。',
            sources='班次生产数据 / shift_production_data',
        )

    if intent == 'quality_anomaly' and facts.get('status') == 'connected':
        blocker_count = _int_or_zero(facts.get('blocker_count'))
        quality_issue_count = _int_or_zero(facts.get('quality_issue_count'))
        conclusion = '质量门禁阻断' if blocker_count else ('发现现场质量问题' if quality_issue_count else '当前未发现质量异常')
        return _format_answer(
            scope_label='全厂',
            status_color=status_color,
            conclusion=conclusion,
            key_numbers=(
                f"门禁阻断 {blocker_count} 条；"
                f"数据预警 {_int_or_zero(facts.get('warning_count'))} 条；"
                f"现场质量问题 {quality_issue_count} 条；"
                f"重点 {_format_quality_focus(facts)}"
            ),
            reason=_format_quality_reason(facts),
            action='门禁阻断需先处理后再发布日报；现场质量问题请责任车间补充处理结论。',
            sources='质量门禁 / data_quality_issues；现场质量 / quality_issue_log',
        )

    return _format_answer(
        scope_label='全厂',
        status_color=status_color,
        conclusion='已按知识库资料生成回复' if citations else '数据不足，未找到可靠知识来源',
        key_numbers='无新增生产数字',
        reason=rag_answer or '数据不足，知识库没有找到可靠来源。',
        action='按来源资料核对现场情况' if citations else '补充资料后再查询',
        sources=_format_sources(citations),
    )


def _format_tons(value: Any) -> str:
    return f'{_number_or_zero(value):.2f}'


def _format_workshop_list(workshops: Any) -> str:
    if not workshops:
        return '无'
    return '、'.join(str(item) for item in list(workshops)[:5])


def _format_consumable_over_quota(items: list[dict[str, Any]]) -> str:
    if not items:
        return '无'
    parts = []
    for item in items[:3]:
        parts.append(
            f"{item.get('workshop_name')} {item.get('label')} "
            f"{_format_tons(item.get('daily'))}/{_format_tons(item.get('target'))}{item.get('unit') or ''} "
            f"({item.get('ratio')}%)"
        )
    return '；'.join(parts)


def _format_machine_stop_list(items: list[dict[str, Any]]) -> str:
    if not items:
        return '无'
    parts = []
    for item in items[:3]:
        parts.append(
            f"{item.get('workshop_name')} {item.get('equipment_name')} "
            f"{_int_or_zero(item.get('downtime_minutes'))} 分钟"
        )
    return '；'.join(parts)


def _format_machine_stop_reason(items: list[dict[str, Any]]) -> str:
    if not items:
        return '当天业务日没有找到匹配停机记录。'
    first = items[0]
    return (
        f"{first.get('workshop_name')} {first.get('equipment_name')} "
        f"原因：{first.get('downtime_reason') or '未填写原因'}。"
    )


def _format_energy_per_ton(value: Any) -> str:
    number = _optional_number(value)
    if number is None:
        return '暂无'
    return f'{number:.2f}'


def _format_cost_value(facts: dict[str, Any]) -> str:
    cost_value = _optional_number(facts.get('cost_value'))
    if cost_value is None:
        return '暂无'
    return f'{cost_value:.2f} 元'


def _format_energy_sources(facts: dict[str, Any]) -> str:
    source_labels = {
        'mobile_shift_report': '电工填报和机台明细',
        'owner_only': '内勤每日一录',
        'system': '旧能耗导入',
        'energy_import': '旧能耗导入',
        'none': '无主来源',
    }
    basis_labels = {
        'mes_packaging_output': 'MES包装产量分母',
        'factory_final_packaging_inbound': '全厂入库产量分母',
        'energy_rows': '能耗行产量分母',
        'unknown': '未知产量分母',
    }
    primary_source = str(facts.get('primary_source') or 'none')
    output_basis = str(facts.get('output_basis') or 'unknown')
    return (
        f"能耗汇总 / {source_labels.get(primary_source, primary_source)}；"
        f"吨耗分母 / {basis_labels.get(output_basis, output_basis)}"
    )


def _format_quality_focus(facts: dict[str, Any]) -> str:
    blockers = facts.get('top_blockers') or []
    if blockers:
        return '；'.join(str(item.get('issue_desc') or '未填写门禁原因') for item in blockers[:2])
    issues = facts.get('top_quality_issues') or []
    if issues:
        return '；'.join(
            f"{item.get('workshop_name')} {item.get('quality_issue_desc') or '未填写描述'}"
            for item in issues[:2]
        )
    return '无'


def _format_quality_reason(facts: dict[str, Any]) -> str:
    blockers = facts.get('top_blockers') or []
    if blockers:
        return str(blockers[0].get('issue_desc') or '存在质量门禁阻断。')
    if _int_or_zero(facts.get('warning_count')) > 0:
        return '存在未关闭的数据质量预警。'
    if _int_or_zero(facts.get('quality_issue_count')) > 0:
        return '存在现场质量问题记录，需跟进处理结论。'
    return '当天业务日没有找到未关闭质量门禁或现场质量问题。'


def _format_fact_sources(facts: dict[str, Any], citations: list[dict[str, Any]]) -> str:
    parts = [
        f"实时聚合 / {facts.get('daily_output_source') or 'unknown'}",
        f"入库对照 / {facts.get('finished_inbound_source') or 'unknown'}",
    ]
    rag_sources = _format_sources(citations)
    if rag_sources != '无可靠来源':
        parts.append(rag_sources)
    return '；'.join(parts)


def _format_sources(citations: list[dict[str, Any]]) -> str:
    if not citations:
        return '无可靠来源'
    parts = []
    for item in citations[:3]:
        filename = item.get('filename') or '未知资料'
        source_ref = item.get('source_ref') or f"chunk-{item.get('chunk_index', '-')}"
        parts.append(f'{filename} / {source_ref}')
    return '；'.join(parts)


def _outbox_title_for_intent(agent_code: str, intent: str) -> str:
    labels = {
        'production_today': '今日产量回复',
        'anomaly_summary': '异常汇总回复',
        'consumable_usage': '辅材消耗回复',
        'machine_stop': '停机查询回复',
        'quality_anomaly': '质量异常回复',
        'energy_cost': '能耗成本回复',
        'general_knowledge': '知识库回复',
    }
    return f"【{agent_code}】{labels.get(intent, '现场问答回复')}"


def _outbox_source_summary_for_intent(intent: str) -> str:
    if intent == 'general_knowledge':
        return 'agent_command_rag'
    return f'agent_command_{intent}'


def _build_command_dedupe_key(*, channel: str, group_id: str, agent_code: str, text: str) -> str:
    text_digest = hashlib.sha256(_clean(text).encode('utf-8')).hexdigest()[:16]
    return ':'.join(
        [
            'agent_command',
            _key_component(channel),
            _key_component(group_id),
            _key_component(agent_code),
            text_digest,
        ]
    )


def _key_component(value: str | None) -> str:
    return _clean(value).replace('\n', ' ').replace('\r', ' ') or 'unknown'


def _format_answer(
    *,
    scope_label: str,
    status_color: str,
    conclusion: str,
    key_numbers: str,
    reason: str,
    action: str,
    sources: str,
) -> str:
    observed_at = datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M')
    status_label = _status_label(status_color)
    return (
        f'【{scope_label}｜{observed_at}】'
        f'状态：{status_label}；'
        f'结论：{conclusion}；'
        f'关键数字：{key_numbers}；'
        f'原因：{reason}；'
        f'建议动作：{action}；'
        f'数据来源：{sources}；'
        f'可回复命令：详情 / 今日产量 / 异常明细。'
    )
