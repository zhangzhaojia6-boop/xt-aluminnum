from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.agent_communication import AgentEvent, CommunicationChannel, MultimodalEvidence
from app.models.base import Base
from app.models.hermes_factory_brain import HermesDingTalkSamplingRule
from app.models.master import Team, Workshop
from app.models.system import User
from app.services.hermes_dingtalk_sampling_service import (
    adopt_registered_file_evidence,
    adopt_registered_message_evidence,
    sample_dingtalk_message,
)
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


CONTRACT_MESSAGE = '投料量：2050投料373吨 1850投料0吨 外加工0吨  中厚板25吨  当天合同875吨    热轧760吨   总余合同量5107吨'


def _registered_contract_rule() -> HermesDingTalkSamplingRule:
    return HermesDingTalkSamplingRule(
        rule_key='registered-message:plan-contract',
        channel_key='cid-plan',
        specialist_user_id='dt-plan-owner',
        content_types=['text'],
        time_window_payload={'mode': 'registered_message', 'days': 'daily', 'message_pattern': '当天合同'},
        priority='high',
        status='active',
    )


def _machine_only_message_evidence(
    *,
    event_time: str,
    text: str = CONTRACT_MESSAGE,
    sender: str = 'dt-plan-owner',
    trace_id: str = 'msg-plan-001',
) -> MultimodalEvidence:
    return MultimodalEvidence(
        evidence_type='text',
        recognized_text=text,
        confirmation_status='machine_only',
        payload={
            'source': 'dingtalk',
            'trace_id': trace_id,
            'group_id': 'cid-plan',
            'dingtalk_sender_id': sender,
            'parse_status': 'text_captured',
            'message_text': text,
            'event_time': event_time,
        },
    )


def test_registered_contract_message_is_auto_adopted_for_its_production_business_date() -> None:
    db = _db()
    db.add(_registered_contract_rule())
    evidence = _machine_only_message_evidence(event_time='2026-10-25 16:17:48')
    db.add(evidence)
    db.flush()

    rule_key = adopt_registered_message_evidence(db, evidence_id=evidence.id)

    assert rule_key == 'registered-message:plan-contract'
    assert evidence.confirmation_status == 'specialist_sampled'
    assert evidence.payload['business_date'] == '2026-10-25'
    updates = evidence.payload['fact_updates']
    assert updates['daily_contract_weight']['value'] == 875
    assert updates['daily_hot_roll_contract_weight']['value'] == 760
    assert updates['remaining_contract_weight']['value'] == 5107
    assert updates['cold_roll_input_daily']['value'] == 373
    assert updates['outsourced_input_daily']['value'] == 0
    assert updates['medium_plate_input_daily']['value'] == 25
    items = query_dingtalk_evidence(db, business_date=date(2026, 10, 25))
    assert [item.adoptable_as_fact for item in items] == [True]


def test_registered_message_before_production_day_start_belongs_to_previous_day() -> None:
    db = _db()
    db.add(_registered_contract_rule())
    evidence = _machine_only_message_evidence(event_time='2026-10-25 07:41:51')
    db.add(evidence)
    db.flush()

    adopt_registered_message_evidence(db, evidence_id=evidence.id)

    assert evidence.payload['business_date'] == '2026-10-24'


def test_later_registered_message_in_same_business_day_supersedes_earlier_one() -> None:
    db = _db()
    db.add(_registered_contract_rule())
    earlier = _machine_only_message_evidence(event_time='2026-10-25 09:00:00', trace_id='msg-plan-early')
    later = _machine_only_message_evidence(
        event_time='2026-10-25 16:17:48',
        text=CONTRACT_MESSAGE.replace('当天合同875吨', '当天合同900吨'),
        trace_id='msg-plan-late',
    )
    db.add_all([earlier, later])
    db.flush()

    assert adopt_registered_message_evidence(db, evidence_id=earlier.id) == 'registered-message:plan-contract'
    assert adopt_registered_message_evidence(db, evidence_id=later.id) == 'registered-message:plan-contract'

    assert earlier.confirmation_status == 'machine_only'
    assert earlier.payload['superseded_by_evidence_id'] == later.id
    assert 'fact_updates' not in earlier.payload
    assert later.payload['fact_updates']['daily_contract_weight']['value'] == 900
    adoptable = [item for item in query_dingtalk_evidence(db, business_date=date(2026, 10, 25)) if item.adoptable_as_fact]
    assert [item.evidence_id for item in adoptable] == [later.id]


def test_earlier_registered_message_processed_after_later_one_is_not_adopted() -> None:
    db = _db()
    db.add(_registered_contract_rule())
    earlier = _machine_only_message_evidence(event_time='2026-10-25 09:00:00', trace_id='msg-plan-early')
    later = _machine_only_message_evidence(event_time='2026-10-25 16:17:48', trace_id='msg-plan-late')
    db.add_all([earlier, later])
    db.flush()

    adopt_registered_message_evidence(db, evidence_id=later.id)

    assert adopt_registered_message_evidence(db, evidence_id=earlier.id) is None
    assert earlier.confirmation_status == 'machine_only'
    assert earlier.payload['superseded_by_evidence_id'] == later.id
    assert later.confirmation_status == 'specialist_sampled'


def test_message_from_unregistered_sender_or_without_pattern_stays_machine_only() -> None:
    db = _db()
    db.add(_registered_contract_rule())
    stranger = _machine_only_message_evidence(event_time='2026-10-25 16:17:48', sender='dt-someone-else')
    chatter = _machine_only_message_evidence(event_time='2026-10-25 08:39:06', text='报表输完', trace_id='msg-plan-chat')
    db.add_all([stranger, chatter])
    db.flush()

    assert adopt_registered_message_evidence(db, evidence_id=stranger.id) is None
    assert adopt_registered_message_evidence(db, evidence_id=chatter.id) is None
    assert stranger.confirmation_status == 'machine_only'
    assert chatter.confirmation_status == 'machine_only'
