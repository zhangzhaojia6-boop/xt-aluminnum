from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.master import Team, Workshop
from app.models.rag import RagDocument
from app.models.system import User


def _db_session():
    from app.models.hermes_factory_brain import (
        HermesCodexConstructionRun,
        HermesDingTalkSamplingRule,
        HermesKnowledgeUnit,
        HermesLongTermRule,
        HermesSoulProfile,
    )

    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Workshop.__table__,
            Team.__table__,
            User.__table__,
            RagDocument.__table__,
            HermesSoulProfile.__table__,
            HermesLongTermRule.__table__,
            HermesDingTalkSamplingRule.__table__,
            HermesKnowledgeUnit.__table__,
            HermesCodexConstructionRun.__table__,
        ],
    )
    SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    return SessionLocal()


def _create_user(db) -> User:
    user = User(
        username='factory-brain-owner',
        password_hash='hashed',
        name='智能大脑负责人',
        role='admin',
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_document(db, user_id: int) -> RagDocument:
    document = RagDocument(
        filename='factory-brain.md',
        source_name='factory-brain',
        encoding='utf-8',
        uploaded_by_id=user_id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def test_hermes_long_term_rule_can_persist_required_fields() -> None:
    from app.models.hermes_factory_brain import HermesLongTermRule

    db = _db_session()
    user = _create_user(db)

    rule = HermesLongTermRule(
        rule_key='daily-report-priority',
        raw_text='以后日报先看专项责任人文件',
        structured_rule={'mode': 'prefer_specialist_file'},
        scope_payload={'domain': 'daily_report'},
        status='active',
        risk_level='medium',
        created_by_id=user.id,
    )
    db.add(rule)
    db.commit()

    stored = db.query(HermesLongTermRule).filter(HermesLongTermRule.rule_key == 'daily-report-priority').one()

    assert stored.raw_text == '以后日报先看专项责任人文件'
    assert stored.structured_rule == {'mode': 'prefer_specialist_file'}
    assert stored.scope_payload == {'domain': 'daily_report'}
    assert stored.status == 'active'
    assert stored.risk_level == 'medium'
    assert stored.created_by_id == user.id


def test_hermes_dingtalk_sampling_rule_can_persist_required_fields() -> None:
    from app.models.hermes_factory_brain import HermesDingTalkSamplingRule

    db = _db_session()
    user = _create_user(db)

    rule = HermesDingTalkSamplingRule(
        rule_key='sampling-production-daily',
        channel_key='production_daily_group',
        specialist_user_id='dingtalk-user-1',
        content_types=['daily_report', 'exception_note'],
        time_window_payload={'days': 30},
        priority='high',
        status='active',
        created_by_id=user.id,
    )
    db.add(rule)
    db.commit()

    stored = db.query(HermesDingTalkSamplingRule).filter(HermesDingTalkSamplingRule.rule_key == 'sampling-production-daily').one()

    assert stored.channel_key == 'production_daily_group'
    assert stored.specialist_user_id == 'dingtalk-user-1'
    assert stored.content_types == ['daily_report', 'exception_note']
    assert stored.time_window_payload == {'days': 30}
    assert stored.priority == 'high'
    assert stored.status == 'active'
    assert stored.created_by_id == user.id


def test_hermes_knowledge_unit_can_persist_required_fields() -> None:
    from app.models.hermes_factory_brain import HermesKnowledgeUnit

    db = _db_session()
    user = _create_user(db)
    document = _create_document(db, user.id)

    unit = HermesKnowledgeUnit(
        unit_key='cold-roll-2050-energy',
        layer='site_process',
        unit_type='case',
        title='2050 冷轧吨电耗异常',
        content='检查开机时长、停机损耗和返工量。',
        status='approved',
        verification_payload={'verified_by': 'codex', 'method': 'trace'},
        verified_by='codex',
        document_id=document.id,
        created_by_id=user.id,
    )
    db.add(unit)
    db.commit()

    stored = db.query(HermesKnowledgeUnit).filter(HermesKnowledgeUnit.unit_key == 'cold-roll-2050-energy').one()

    assert stored.unit_key == 'cold-roll-2050-energy'
    assert stored.layer == 'site_process'
    assert stored.unit_type == 'case'
    assert stored.title == '2050 冷轧吨电耗异常'
    assert stored.content == '检查开机时长、停机损耗和返工量。'
    assert stored.status == 'approved'
    assert stored.verification_payload == {'verified_by': 'codex', 'method': 'trace'}
    assert stored.verified_by == 'codex'


def test_hermes_soul_profile_and_codex_construction_run_can_persist_required_fields() -> None:
    from app.models.hermes_factory_brain import HermesCodexConstructionRun, HermesSoulProfile

    db = _db_session()
    user = _create_user(db)

    profile = HermesSoulProfile(
        profile_key='default',
        version=1,
        soul_text='轻松表达，业务判断严肃。',
        status='active',
        created_by_id=user.id,
    )
    run = HermesCodexConstructionRun(
        trace_id='trace-factory-brain-001',
        request_text='帮我做鑫泰铝业智能大脑持久化模型',
        construction_type='light',
        authorization_level='root_owner',
        status='requested',
        payload={'task': 'persistence_models'},
        requested_by_id=user.id,
    )
    db.add(profile)
    db.add(run)
    db.commit()

    stored_profile = db.query(HermesSoulProfile).filter(HermesSoulProfile.profile_key == 'default').one()
    stored_run = db.query(HermesCodexConstructionRun).filter(
        HermesCodexConstructionRun.trace_id == 'trace-factory-brain-001'
    ).one()

    assert stored_profile.soul_text == '轻松表达，业务判断严肃。'
    assert stored_profile.version == 1
    assert stored_profile.status == 'active'
    assert stored_run.trace_id == 'trace-factory-brain-001'
    assert stored_run.request_text == '帮我做鑫泰铝业智能大脑持久化模型'
    assert stored_run.construction_type == 'light'
    assert stored_run.authorization_level == 'root_owner'
    assert stored_run.status == 'requested'
    assert stored_run.payload == {'task': 'persistence_models'}
    assert stored_run.requested_by_id == user.id
