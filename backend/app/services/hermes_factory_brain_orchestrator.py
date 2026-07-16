from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.redaction import filter_sensitive_mapping
from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.system import User
from app.services.hermes_langgraph_app import build_factory_brain_graph, initial_factory_brain_state


@dataclass(frozen=True, slots=True)
class FactoryBrainTurnResult:
    trace_id: str
    status: str
    answer: str
    chat_inbox_id: int
    agent_run_id: int
    result_payload: dict[str, Any]


def run_factory_brain_turn(
    db: Session,
    *,
    text: str,
    channel: str,
    group_id: str | None,
    sender_external_id: str | None,
    current_user: User,
    trace_id: str | None,
    source_payload: dict[str, Any] | None,
    chat_inbox: ChatInboxMessage | None = None,
) -> FactoryBrainTurnResult:
    clean_trace_id = str(trace_id or '').strip() or uuid4().hex
    clean_text = str(text or '').strip()
    inbox = chat_inbox
    if inbox is None:
        inbox = ChatInboxMessage(
            channel=str(channel or '').strip() or 'internal',
            group_id=str(group_id or '').strip() or None,
            sender_external_id=str(sender_external_id or '').strip() or None,
            text=clean_text,
            agent_code='factory_brain',
            trace_id=clean_trace_id,
            source_payload=filter_sensitive_mapping(source_payload or {}),
        )
        db.add(inbox)
        db.flush()
    else:
        inbox.agent_code = 'factory_brain'
        inbox.source_payload = filter_sensitive_mapping(
            {
                **dict(inbox.source_payload or {}),
                **(source_payload or {}),
                'factory_brain': True,
            }
        )
        db.add(inbox)

    graph = build_factory_brain_graph(checkpointer=None)
    state = initial_factory_brain_state(
        trace_id=clean_trace_id,
        text=clean_text,
        actor_user_id=getattr(current_user, 'id', None),
        channel=inbox.channel,
    )
    graph_result = graph.invoke(state)
    answer = str(graph_result.get('response_text') or 'Hermes 已收到。')
    result_payload = {
        'factory_brain': {
            'status': graph_result.get('status'),
            'state_trace': graph_result.get('state_trace') or [],
            'tool_trace': graph_result.get('tool_trace') or [],
            'intent': graph_result.get('intent') or {},
            'normalized_request': graph_result.get('normalized_request') or {},
            'data_references': graph_result.get('data_references') or [],
            'evidence_gap': graph_result.get('evidence_gap'),
            'artifact_requests': graph_result.get('artifact_requests') or [],
            'progress_cards': graph_result.get('progress_cards') or [],
        }
    }
    run = AgentRun(
        trace_id=clean_trace_id,
        agent_code='factory_brain',
        chat_inbox_id=inbox.id,
        status='answered',
        status_color='green',
        answer=answer,
        rag_citation_count=0,
        result_payload=result_payload,
    )
    db.add(run)
    db.flush()
    return FactoryBrainTurnResult(
        trace_id=clean_trace_id,
        status=str(graph_result.get('status') or 'replied'),
        answer=answer,
        chat_inbox_id=inbox.id,
        agent_run_id=run.id,
        result_payload=result_payload,
    )
