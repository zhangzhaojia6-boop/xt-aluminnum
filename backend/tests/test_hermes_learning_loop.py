from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.master import Workshop
from app.models.rag import (
    HermesApprovedLesson,
    HermesLearningEvent,
    HermesShortTermMemory,
    RagChunk,
    RagDocument,
    RagEmbedding,
    RagQueryLog,
)
from app.models.system import User
from app.services import hermes_memory_service, hermes_rag_service
from app.services.rag_service import query_knowledge


TABLES = [
    User.__table__,
    Workshop.__table__,
    RagDocument.__table__,
    RagChunk.__table__,
    RagQueryLog.__table__,
    RagEmbedding.__table__,
    HermesLearningEvent.__table__,
    HermesShortTermMemory.__table__,
    HermesApprovedLesson.__table__,
]


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'hermes-learning.db'}", future=True)
    Base.metadata.create_all(engine, tables=TABLES)
    return Session(engine)


def test_learning_candidate_does_not_affect_rag_until_approved(tmp_path) -> None:
    db = _session(tmp_path)
    try:
        event = hermes_rag_service.record_learning_event(
            db,
            question='园区精整归哪里',
            answer='园区精整归园区剪切。',
            human_correction='园区精整在数据中枢归为园区剪切，不归为精整。',
        )
        before = query_knowledge(db, query='园区精整 园区剪切', limit=3)
        assert before['items'] == []

        lesson = hermes_rag_service.approve_learning_event(db, event_id=event.id)
        after = query_knowledge(db, query='园区精整 园区剪切', limit=3)
        assert lesson.status == 'active'
        assert db.get(HermesLearningEvent, event.id).status == 'approved'
        assert after['items']
        assert '园区剪切' in after['answer']
    finally:
        db.close()


def test_short_term_memory_expires_and_policy_is_explicit(tmp_path) -> None:
    db = _session(tmp_path)
    try:
        memory = hermes_memory_service.remember_short_term(
            db,
            conversation_key='cid-test',
            memory_key='last_topic',
            memory_value={'topic': '6月17日报日'},
            ttl_minutes=1,
        )
        assert hermes_memory_service.recall_short_term(db, conversation_key='cid-test')
        memory.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert hermes_memory_service.purge_expired_short_term(db) == 1
        assert hermes_memory_service.recall_short_term(db, conversation_key='cid-test') == []

        policy = hermes_memory_service.memory_architecture()
        assert policy['temporary']['persisted'] is False
        assert policy['short_term']['storage'] == 'hermes_short_term_memories'
        assert policy['learning_candidate']['effective_before_approval'] is False
    finally:
        db.close()
