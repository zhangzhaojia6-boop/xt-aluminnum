from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.hermes_factory_brain import HermesLongTermRule
from app.models.system import User
from app.services.hermes_long_term_rule_service import (
    LongTermRuleCommand,
    classify_rule_command,
    create_or_confirm_rule,
    list_active_rules,
    lower_rule_priority,
)
from app.services.hermes_soul_service import load_default_soul_text


def _db() -> Session:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__, HermesLongTermRule.__table__])
    return Session(engine)


def test_soul_text_defines_funny_but_serious_boundary() -> None:
    text = load_default_soul_text()

    assert '有趣' in text
    assert '轻松' in text
    assert '诙谐' in text
    assert '不能拿生产事实开玩笑' in text


def test_classify_natural_language_rule_add() -> None:
    command = classify_rule_command('以后日报先看专项责任人发的钉钉文件')

    assert command.action == 'add'
    assert command.risk_level == 'high'
    assert command.structured_rule['rule_type'] == 'source_priority'


def test_classify_temporary_override_does_not_persist() -> None:
    command = classify_rule_command('今天按临时口径，不要记住')

    assert command.action == 'temporary_override'
    assert command.persist is False


def test_root_owner_rule_persists_raw_and_structured_rule() -> None:
    db = _db()
    command = LongTermRuleCommand(
        action='add',
        raw_text='以后回答我先给结论，再给数据来源',
        structured_rule={'rule_type': 'response_style', 'order': ['conclusion', 'sources']},
        scope_payload={'domain': 'all'},
        risk_level='low',
        persist=True,
        requires_confirmation=False,
    )

    rule = create_or_confirm_rule(db, command=command, actor_user_id=1, trace_id='trace-rule-001')
    db.commit()

    assert rule.status == 'active'
    assert rule.raw_text == '以后回答我先给结论，再给数据来源'
    assert rule.structured_rule['rule_type'] == 'response_style'


def test_lower_rule_priority_changes_status_and_priority() -> None:
    db = _db()
    db.add(
        HermesLongTermRule(
            rule_key='rule-001',
            raw_text='以后日报先看钉钉文件',
            structured_rule={'rule_type': 'source_priority'},
            scope_payload={'domain': 'daily_report'},
            status='active',
            risk_level='high',
            priority=100,
        )
    )
    db.commit()

    lowered = lower_rule_priority(db, rule_key='rule-001', actor_user_id=1)
    db.commit()

    assert lowered.status == 'lowered'
    assert lowered.priority == 200
    assert list_active_rules(db) == []
