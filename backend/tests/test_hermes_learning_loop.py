from __future__ import annotations

from datetime import datetime, timedelta, timezone
from importlib import import_module

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.agent_communication import AgentRun
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
from app.models.reports import DailyReport
from app.models.system import AuditLog, User
from app.services import hermes_memory_service, hermes_rag_service
from app.services.hermes_day1_intent_service import HermesDay1Command
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


def _orchestrator_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(engine)
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


def test_day1_orchestrator_records_learning_candidate_with_tools_and_sources(monkeypatch) -> None:
    service = import_module('app.services.hermes_day1_orchestrator')
    db = _orchestrator_session()
    try:
        actor = User(
            username='root-owner',
            password_hash='hash',
            name='张兆嘉',
            role='admin',
            data_scope_type='factory',
        )
        db.add(actor)
        db.flush()

        sources = {
            'trace_id': 'trace-learning-day1',
            'template_daily_report': {'status': 'ready', 'text': '模板日报'},
            'audit_run': {'status': 'completed', 'source_status': {'mes': 'ok', 'hub': 'ok'}},
            'rag': {'answer': '路线说明', 'citations': [{'source_ref': 'doc#1'}]},
        }
        product = {
            'status': 'ready',
            'text': '三段式日报',
            'formal_text': '正式日报',
            'brain_judgment': {'summary': '可以发布', 'risks': []},
            'workshop_details': [],
            'dingtalk_answer': '日报回复',
            'dingtalk_messages': ['日报回复'],
            'missing_fields': [],
            'conflicts': [],
        }
        monkeypatch.setattr(service, 'collect_day1_sources', lambda *args, **kwargs: sources)
        monkeypatch.setattr(service, 'build_day1_three_part_report', lambda **kwargs: product)

        service.run_day1_super_brain(
            db,
            command=HermesDay1Command(source_text='生成 2026-06-21 日报', business_date=datetime(2026, 6, 21).date()),
            actor=actor,
            trace_id='trace-learning-day1',
        )

        event = db.query(HermesLearningEvent).one()
        assert event.status == 'candidate'
        assert event.tools_called == ['collect_day1_sources', 'build_day1_three_part_report']
        assert event.sources
        assert event.actor_user_id == actor.id
        assert db.query(DailyReport).count() == 1
        assert db.query(AgentRun).count() == 1
        assert db.query(AuditLog).count() == 1
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
