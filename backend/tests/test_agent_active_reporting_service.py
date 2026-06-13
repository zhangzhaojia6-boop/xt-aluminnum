from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import AgentEvent, AgentOutboxMessage
from app.services import agent_active_reporting_service as active_service
from app.services import agent_communication_service as communication_service


def _db_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def _bind_factory_channel(db) -> None:
    communication_service.register_agent(db, code='factory_dispatch', name='全厂调度 Agent')
    communication_service.register_channel(
        db,
        channel_type='dingtalk_group',
        channel_key='management-chat',
        name='管理总控群',
        target_type='management',
        target_key='management',
    )
    communication_service.bind_agent_to_channel(db, agent_code='factory_dispatch', channel_key='management-chat')


def _bind_workshop_channel(db, *, channel_key: str = 'workshop-2-chat', workshop_id: int = 2) -> None:
    communication_service.register_agent(
        db,
        code='workshop_status',
        name='车间汇报 Agent',
        scope_type='workshop',
        workshop_id=workshop_id,
    )
    communication_service.register_channel(
        db,
        channel_type='dingtalk_group',
        channel_key=channel_key,
        name='试点车间群',
        target_type='workshop',
        target_key=str(workshop_id),
        workshop_id=workshop_id,
    )
    communication_service.bind_agent_to_channel(db, agent_code='workshop_status', channel_key=channel_key)


def test_factory_overview_queues_traceable_management_report() -> None:
    db = _db_session()
    try:
        _bind_factory_channel(db)

        outcome = active_service.queue_factory_overview(
            db,
            business_date=date(2026, 6, 13),
            channel_key='management-chat',
            metrics={
                '全厂总产量': '128.50 吨',
                '包装产量': '36.20 吨',
                '缺报数量': '2 项',
            },
            anomalies=[{'title': '热轧停机待核查', 'severity': 'warning', 'value': '42 分钟'}],
            trace_id='trace-factory-001',
        )

        assert outcome.status == 'queued'
        assert outcome.event_id is not None
        assert outcome.outbox_message_id is not None

        event = db.get(AgentEvent, outcome.event_id)
        message = db.get(AgentOutboxMessage, outcome.outbox_message_id)
        assert event is not None
        assert event.event_type == 'factory_overview_report'
        assert event.scope_type == 'factory'
        assert event.status == 'queued'
        assert event.severity == 'warning'
        assert event.payload['source_summary'] == 'factory_active_report'
        assert message is not None
        assert message.event_id == event.id
        assert message.trace_id == 'trace-factory-001'
        assert message.source_summary == 'factory_active_report'
        assert '全厂总产量：128.50 吨' in message.content
        assert '热轧停机待核查：42 分钟' in message.content
    finally:
        db.close()


def test_workshop_report_rejects_channel_from_other_workshop() -> None:
    db = _db_session()
    try:
        _bind_workshop_channel(db, channel_key='workshop-2-chat', workshop_id=2)

        with pytest.raises(active_service.ActiveReportingError, match='channel_scope_mismatch'):
            active_service.queue_workshop_status(
                db,
                business_date=date(2026, 6, 13),
                channel_key='workshop-2-chat',
                workshop_id=3,
                workshop_name='铸三',
                metrics={'本车间产量': '20.00 吨'},
            )

        assert db.query(AgentOutboxMessage).count() == 0
    finally:
        db.close()


def test_workshop_report_queues_only_matching_workshop_scope() -> None:
    db = _db_session()
    try:
        _bind_workshop_channel(db, channel_key='workshop-2-chat', workshop_id=2)

        outcome = active_service.queue_workshop_status(
            db,
            business_date=date(2026, 6, 13),
            channel_key='workshop-2-chat',
            workshop_id=2,
            workshop_name='铸二',
            metrics={'本车间产量': '20.00 吨', '在制卷数': '8 卷'},
            anomalies=[],
            trace_id='trace-workshop-002',
        )

        event = db.get(AgentEvent, outcome.event_id)
        message = db.get(AgentOutboxMessage, outcome.outbox_message_id)
        assert outcome.status == 'queued'
        assert event is not None
        assert event.scope_type == 'workshop'
        assert event.workshop_id == 2
        assert event.status == 'queued'
        assert message is not None
        assert message.event_id == event.id
        assert message.trace_id == 'trace-workshop-002'
        assert '铸二车间主动汇报' in message.title
        assert '在制卷数：8 卷' in message.content
    finally:
        db.close()


def test_detect_basic_anomalies_marks_sync_missing_and_stop_risk() -> None:
    anomalies = active_service.detect_basic_anomalies(
        {
            'missing_report_count': 2,
            'production_gap_tons': 3.5,
            'mes_sync_status': 'stale',
            'stopped_machine_minutes': 45,
        }
    )

    assert [item['type'] for item in anomalies] == [
        'missing_report',
        'production_gap',
        'mes_sync_stale',
        'machine_stop',
    ]
    assert anomalies[-1]['severity'] == 'critical'


def test_duplicate_factory_report_is_suppressed_but_archived() -> None:
    db = _db_session()
    try:
        _bind_factory_channel(db)
        first = active_service.queue_factory_overview(
            db,
            business_date=date(2026, 6, 13),
            channel_key='management-chat',
            metrics={'全厂总产量': '128.50 吨'},
            occurred_at=datetime(2026, 6, 13, 8, 0, tzinfo=UTC),
        )
        second = active_service.queue_factory_overview(
            db,
            business_date=date(2026, 6, 13),
            channel_key='management-chat',
            metrics={'全厂总产量': '129.00 吨'},
            occurred_at=datetime(2026, 6, 13, 8, 5, tzinfo=UTC),
        )

        assert first.status == 'queued'
        assert second.status == 'suppressed'
        assert second.outbox_message_id is None
        assert db.query(AgentOutboxMessage).count() == 1
        suppressed_event = db.get(AgentEvent, second.event_id)
        assert suppressed_event is not None
        assert suppressed_event.status == 'suppressed'
        assert suppressed_event.payload['rate_limit_detail'] == 'rate_limited'
    finally:
        db.close()
