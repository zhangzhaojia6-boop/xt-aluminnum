from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.redaction import filter_sensitive_mapping
from app.models.rag import HermesShortTermMemory
from app.models.system import User


DEFAULT_SHORT_TERM_TTL_MINUTES = 120


def memory_architecture() -> dict[str, Any]:
    return {
        'temporary': {
            'storage': 'process_state_only',
            'persisted': False,
            'purpose': '一次工具调用中的问题、计划、工具返回和错误信息',
        },
        'short_term': {
            'storage': 'hermes_short_term_memories',
            'persisted': True,
            'default_ttl_minutes': DEFAULT_SHORT_TERM_TTL_MINUTES,
            'purpose': '一个钉钉群或一段对话内的最近上下文',
        },
        'long_term': {
            'storage': 'rag_documents/rag_chunks/daily_reports/hermes_approved_lessons',
            'persisted': True,
            'purpose': '稳定知识、历史日报、MES 路线、SOP 和已审核经验',
        },
        'learning_candidate': {
            'storage': 'hermes_learning_events',
            'persisted': True,
            'effective_before_approval': False,
            'purpose': '用户纠错和人工改写，审批前不影响正式回答',
        },
    }


def remember_short_term(
    db: Session,
    *,
    conversation_key: str,
    memory_key: str,
    memory_value: dict[str, Any],
    actor: User | None = None,
    trace_id: str | None = None,
    ttl_minutes: int = DEFAULT_SHORT_TERM_TTL_MINUTES,
) -> HermesShortTermMemory:
    now = datetime.now(timezone.utc)
    memory = HermesShortTermMemory(
        conversation_key=str(conversation_key or '').strip() or 'unknown',
        memory_key=str(memory_key or '').strip() or 'context',
        memory_value=filter_sensitive_mapping(memory_value),
        trace_id=trace_id,
        actor_user_id=getattr(actor, 'id', None),
        expires_at=now + timedelta(minutes=max(1, int(ttl_minutes or DEFAULT_SHORT_TERM_TTL_MINUTES))),
    )
    db.add(memory)
    db.flush()
    return memory


def recall_short_term(db: Session, *, conversation_key: str, limit: int = 10) -> list[HermesShortTermMemory]:
    now = datetime.now(timezone.utc)
    return (
        db.query(HermesShortTermMemory)
        .filter(
            HermesShortTermMemory.conversation_key == str(conversation_key or '').strip(),
            HermesShortTermMemory.expires_at > now,
        )
        .order_by(HermesShortTermMemory.created_at.desc(), HermesShortTermMemory.id.desc())
        .limit(max(1, min(int(limit or 10), 50)))
        .all()
    )


def purge_expired_short_term(db: Session) -> int:
    now = datetime.now(timezone.utc)
    count = (
        db.query(HermesShortTermMemory)
        .filter(HermesShortTermMemory.expires_at <= now)
        .delete(synchronize_session=False)
    )
    db.flush()
    return int(count or 0)
