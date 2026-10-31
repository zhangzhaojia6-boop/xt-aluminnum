from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.agent_communication import AgentEvent, CommunicationChannel, MultimodalEvidence
from app.models.base import Base
from app.models.hermes_factory_brain import HermesDingTalkSamplingRule
from app.models.master import Team, Workshop
from app.models.system import User
from app.services.hermes_dingtalk_sampling_service import adopt_registered_file_evidence, sample_dingtalk_message
from app.services.hermes_dingtalk_evidence_service import query_dingtalk_evidence


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
            time_window_payload={'mode': 'recent_days', 'days': 30, 'workshop_name': '铸二'},
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
    items = query_dingtalk_evidence(db, business_date=date(2026, 6, 25))
    assert len(items) == 1
    assert items[0].workshop_name == '铸二'
    assert items[0].parse_status == 'text_captured'
    assert items[0].adoptable_as_fact is True
    assert items[0].group_id == 'cid-production'
    assert items[0].conversation_id == 'cid-production'
    assert items[0].sender_id == 'dt-output-owner'
    assert items[0].event_time == datetime(2026, 6, 25, 8, 10, tzinfo=timezone.utc)


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


def _registered_yield_rule() -> HermesDingTalkSamplingRule:
    return HermesDingTalkSamplingRule(
        rule_key='registered-file:yield-workbook',
        channel_key='cid-yield',
        specialist_user_id='dt-yield-owner',
        content_types=['file'],
        time_window_payload={'mode': 'registered_file', 'days': 'daily', 'file_name_pattern': '各车间成品率'},
        priority='high',
        status='active',
    )


def _machine_only_file_evidence(*, sender: str = 'dt-yield-owner', file_name: str = '7月份各车间成品率(12).xlsx'):
    return MultimodalEvidence(
        evidence_type='attachment',
        recognized_text='[Sheet3] 7月份各车间成品率车间指标',
        confirmation_status='machine_only',
        payload={
            'source': 'dingtalk',
            'trace_id': 'msg-yield-001',
            'group_id': 'cid-yield',
            'dingtalk_sender_id': sender,
            'parse_status': 'text_captured',
            'file_name': file_name,
            'file_text': '[Sheet3] 7月份各车间成品率车间指标',
        },
    )


def test_registered_yield_file_is_auto_adopted_for_its_workbook_business_date() -> None:
    from tests.test_dingtalk_verified_fact_extractor import _workbook_bytes

    db = _db()
    db.add(_registered_yield_rule())
    evidence = _machine_only_file_evidence()
    db.add(evidence)
    db.flush()

    rule_key = adopt_registered_file_evidence(
        db,
        evidence_id=evidence.id,
        file_name='7月份各车间成品率(12).xlsx',
        content=_workbook_bytes(),
    )

    assert rule_key == 'registered-file:yield-workbook'
    assert evidence.confirmation_status == 'specialist_sampled'
    assert evidence.payload['business_date'] == '2026-07-12'
    assert evidence.payload['sampling_rule_key'] == 'registered-file:yield-workbook'
    assert evidence.payload['fact_updates']['daily_yield_rate']['value'] == 83.81
    items = query_dingtalk_evidence(db, business_date=date(2026, 7, 12))
    assert [item.adoptable_as_fact for item in items] == [True]


def test_file_from_unregistered_sender_stays_machine_only() -> None:
    from tests.test_dingtalk_verified_fact_extractor import _workbook_bytes

    db = _db()
    db.add(_registered_yield_rule())
    evidence = _machine_only_file_evidence(sender='dt-someone-else')
    db.add(evidence)
    db.flush()

    assert adopt_registered_file_evidence(
        db, evidence_id=evidence.id, file_name='7月份各车间成品率(12).xlsx', content=_workbook_bytes()
    ) is None
    assert evidence.confirmation_status == 'machine_only'
    assert 'fact_updates' not in evidence.payload


def test_registered_sender_file_outside_registered_name_stays_machine_only() -> None:
    from tests.test_dingtalk_verified_fact_extractor import _workbook_bytes

    db = _db()
    db.add(_registered_yield_rule())
    evidence = _machine_only_file_evidence(file_name='河南鑫泰合同报表.xlsx')
    db.add(evidence)
    db.flush()

    assert adopt_registered_file_evidence(
        db, evidence_id=evidence.id, file_name='河南鑫泰合同报表.xlsx', content=_workbook_bytes()
    ) is None
    assert evidence.confirmation_status == 'machine_only'


def test_registered_file_without_deterministic_facts_stays_machine_only() -> None:
    from tests.test_dingtalk_verified_fact_extractor import _workbook_bytes

    db = _db()
    db.add(_registered_yield_rule())
    evidence = _machine_only_file_evidence()
    db.add(evidence)
    db.flush()

    assert adopt_registered_file_evidence(
        db, evidence_id=evidence.id, file_name='7月份各车间成品率(12).xlsx', content=_workbook_bytes(month=6)
    ) is None
    assert evidence.confirmation_status == 'machine_only'
    assert 'fact_updates' not in evidence.payload
