from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import AgentEvent, AgentOperationApproval, MultimodalEvidence
from app.services import agent_communication_service as communication_service
from app.services import agent_management_overview_service as overview_service


def _db_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def test_agent_management_overview_summarizes_closed_loop_without_secret_leak() -> None:
    db = _db_session()
    try:
        agent = communication_service.register_agent(db, code='factory_dispatch', name='全厂调度 Agent')
        channel = communication_service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='chat-secret-123456789',
            name='管理总控群',
            target_type='management',
            target_key='management',
            secret_ref='prod/dingtalk/robot',
            dry_run=True,
        )
        communication_service.bind_agent_to_channel(db, agent_code=agent.code, channel_key=channel.channel_key)
        event = AgentEvent(
            event_type='factory_overview',
            severity='warning',
            status='pending',
            scope_type='factory',
            source_type='unit_test',
            source_ref='trace-stage6',
            business_date=date(2026, 6, 13),
            occurred_at=datetime(2026, 6, 13, 8, 30, tzinfo=UTC),
            payload={'summary': '待确认异常'},
        )
        db.add(event)
        db.flush()
        communication_service.queue_bound_message(
            db,
            agent_code=agent.code,
            channel_key=channel.channel_key,
            title='阶段六汇报',
            content='只读概览测试',
            business_date=date(2026, 6, 13),
            source_summary='unit_test',
            trace_id='trace-stage6',
        )
        db.add(
            MultimodalEvidence(
                evidence_type='image',
                event_id=event.id,
                file_uri='dingtalk://media/image-001',
                recognized_text='图片证据',
                confirmation_status='machine_only',
                payload={'metric_write_allowed': False},
            )
        )
        db.add(
            AgentOperationApproval(
                operation_type='publish_daily_report',
                status='pending_confirmation',
                channel_id=channel.id,
                preview_payload={'metric_write_allowed': False, 'payload': {'report_id': 18}},
                result_payload={'actual_write': False, 'execution_status': 'not_executed'},
                trace_id='trace-stage6',
            )
        )
        db.commit()

        overview = overview_service.build_agent_management_overview(db)

        assert overview['summary']['agent_total'] == 1
        assert overview['summary']['active_channel_total'] == 1
        assert overview['summary']['pending_event_total'] == 1
        assert overview['summary']['evidence_total'] == 1
        assert overview['channels'][0]['channel_key_masked'].startswith('chat')
        assert '123456789' not in overview['channels'][0]['channel_key_masked']
        assert 'secret_ref' not in overview['channels'][0]
        assert overview['operation_approvals'][0]['metric_write_allowed'] is False
        assert overview['operation_approvals'][0]['actual_write'] is False
        assert overview['operation_approvals'][0]['execution_status'] == 'not_executed'
        assert overview['outbox'][0]['trace_id'] == 'trace-stage6'
    finally:
        db.close()


def test_agent_management_overview_empty_database_returns_safe_defaults() -> None:
    db = _db_session()
    try:
        overview = overview_service.build_agent_management_overview(db)

        assert overview['summary']['knowledge_entry_total'] >= 1
        assert {key: overview['summary'][key] for key in (
            'agent_total',
            'active_agent_total',
            'channel_total',
            'active_channel_total',
            'pending_event_total',
            'evidence_total',
            'pending_operation_total',
            'outbox_pending_total',
        )} == {
            'agent_total': 0,
            'active_agent_total': 0,
            'channel_total': 0,
            'active_channel_total': 0,
            'pending_event_total': 0,
            'evidence_total': 0,
            'pending_operation_total': 0,
            'outbox_pending_total': 0,
        }
        assert overview['agents'] == []
        assert overview['events'] == []
        assert overview['knowledge_entries']
        assert overview['safe_mode'] is True
    finally:
        db.close()
