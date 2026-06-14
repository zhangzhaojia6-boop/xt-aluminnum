from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.business_time import resolve_production_business_date
from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.system import User
from app.services import agent_communication_service
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

    inbox = ChatInboxMessage(
        channel=clean_channel,
        group_id=_clean(group_id) or None,
        sender_external_id=_clean(sender_external_id) or None,
        text=clean_text,
        agent_code=clean_agent_code,
        trace_id=clean_trace_id,
        source_payload=source_payload or {},
    )
    db.add(inbox)
    db.flush()

    rag_payload = query_knowledge(db, query=clean_text, limit=5, user=current_user)
    citations = rag_payload.get('citations') or []
    intent = _detect_intent(clean_text)
    facts = _load_business_facts(db, intent=intent, current_user=current_user)
    status_color = 'green' if (facts.get('status') == 'connected' or citations) else 'yellow'
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
        },
        'source_payload': source_payload or {},
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
                title=f'【{clean_agent_code}】知识库回复',
                content=answer,
                source_summary='agent_command_rag',
                trace_id=clean_trace_id,
                payload={
                    'chat_inbox_id': inbox.id,
                    'agent_run_id': run.id,
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
        rag={'answer': rag_payload.get('answer'), 'citations': citations, 'items': rag_payload.get('items') or []},
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
        ('consumable_usage', ('辅材', '耗材', '超耗', '消耗')),
        ('production_today', ('今日产量', '今天产量', '日产量', '产量')),
        ('anomaly_summary', ('异常', '哪个车间')),
    )
    for intent, keywords in checks:
        if any(keyword in value for keyword in keywords):
            return intent
    return 'general_knowledge'


def _load_business_facts(db: Session, *, intent: str, current_user: User | None) -> dict[str, Any]:
    if intent != 'production_today' or current_user is None:
        return {'status': 'not_connected'}

    business_date = resolve_production_business_date()
    try:
        payload = realtime_service.build_live_aggregation(
            db,
            business_date=business_date,
            workshop_id=None,
            current_user=current_user,
        )
    except SQLAlchemyError:
        return {
            'status': 'not_connected',
            'reason': 'live_aggregation_unavailable',
            'business_date': business_date.isoformat(),
        }

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
