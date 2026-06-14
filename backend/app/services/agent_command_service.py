from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.system import User
from app.services.rag_service import query_knowledge


class AgentCommandError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AgentCommandResult:
    trace_id: str
    status_color: str
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
    status_color = 'green' if citations else 'yellow'
    answer = _format_answer(
        scope_label='全厂',
        status_color=status_color,
        conclusion='已按知识库资料生成回复' if citations else '数据不足，未找到可靠知识来源',
        key_numbers='无新增生产数字',
        reason=rag_payload.get('answer') or '数据不足，知识库没有找到可靠来源。',
        action='按来源资料核对现场情况' if citations else '补充资料后再查询',
        sources=_format_sources(citations),
    )

    result_payload = {
        'status_color': status_color,
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

    return AgentCommandResult(
        trace_id=clean_trace_id,
        status_color=status_color,
        answer=answer,
        rag={'answer': rag_payload.get('answer'), 'citations': citations, 'items': rag_payload.get('items') or []},
        chat_inbox_id=inbox.id,
        agent_run_id=run.id,
        outbox_message_id=None,
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


def _format_sources(citations: list[dict[str, Any]]) -> str:
    if not citations:
        return '无可靠来源'
    parts = []
    for item in citations[:3]:
        filename = item.get('filename') or '未知资料'
        source_ref = item.get('source_ref') or f"chunk-{item.get('chunk_index', '-')}"
        parts.append(f'{filename} / {source_ref}')
    return '；'.join(parts)


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
