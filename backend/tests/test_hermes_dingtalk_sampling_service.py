from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.agent_communication import AgentEvent, CommunicationChannel, MultimodalEvidence
from app.models.base import Base
from app.models.hermes_factory_brain import HermesDingTalkSamplingRule
from app.models.master import Team, Workshop
from app.models.system import User
from app.services.hermes_dingtalk_sampling_service import sample_dingtalk_message


def _db() -> Session:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Workshop.__table__,
            Team.__table__,
            User.__table__,
            CommunicationChannel.__table__,
            AgentEvent.__table__,
            MultimodalEvidence.__table__,
            HermesDingTalkSamplingRule.__table__,
        ],
    )
    return Session(engine)


def test_four_conditions_promote_specialist_file_to_high_priority_evidence() -> None:
    db = _db()
    db.add(
        HermesDingTalkSamplingRule(
            rule_key='daily-production',
            channel_key='cid-production',
            specialist_user_id='dt-output-owner',
            content_types=['production_table'],
            time_window_payload={'mode': 'recent_days', 'days': 30},
            priority='high',
            status='active',
            created_by_id=1,
        )
    )
    db.commit()

    result = sample_dingtalk_message(
        db,
        channel_key='cid-production',
        sender_user_id='dt-output-owner',
        message_text='每日产量表已发',
        file_name='每日产量.xlsx',
        message_time=datetime(2026, 6, 25, 8, 10, tzinfo=timezone.utc),
        content_type='production_table',
        trace_id='trace-sampling-001',
    )
    db.commit()

    assert result.matched is True
    assert result.priority == 'high'
    evidence = db.query(MultimodalEvidence).one()
    assert evidence.evidence_type == 'dingtalk_file'
    assert evidence.payload['sampling_priority'] == 'high'


def test_missing_specialist_does_not_promote_to_high_priority() -> None:
    db = _db()
    db.add(
        HermesDingTalkSamplingRule(
            rule_key='daily-production',
            channel_key='cid-production',
            specialist_user_id='dt-output-owner',
            content_types=['production_table'],
            time_window_payload={'mode': 'recent_days', 'days': 30},
            priority='high',
            status='active',
            created_by_id=1,
        )
    )
    db.commit()

    result = sample_dingtalk_message(
        db,
        channel_key='cid-production',
        sender_user_id='dt-other-user',
        message_text='每日产量表已发',
        file_name='每日产量.xlsx',
        message_time=datetime(2026, 6, 25, 8, 10, tzinfo=timezone.utc),
        content_type='production_table',
        trace_id='trace-sampling-002',
    )

    assert result.matched is False
    assert result.priority == 'low'
    assert db.query(MultimodalEvidence).count() == 0
