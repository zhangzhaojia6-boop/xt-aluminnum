from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.redaction import redact_secret_text
from app.models.hermes_factory_brain import HermesLongTermRule


@dataclass(frozen=True, slots=True)
class LongTermRuleCommand:
    action: str
    raw_text: str
    structured_rule: dict
    scope_payload: dict
    risk_level: str
    persist: bool
    requires_confirmation: bool


def classify_rule_command(text: str) -> LongTermRuleCommand:
    clean = str(text or '').strip()
    if '不要记住' in clean or '临时口径' in clean or '只是临时' in clean:
        return LongTermRuleCommand(
            action='temporary_override',
            raw_text=clean,
            structured_rule={'rule_type': 'temporary_override'},
            scope_payload={'domain': 'current_task'},
            risk_level='low',
            persist=False,
            requires_confirmation=False,
        )
    if '删' in clean:
        return LongTermRuleCommand(
            action='delete',
            raw_text=clean,
            structured_rule={'rule_type': 'rule_deletion'},
            scope_payload={'domain': 'rule_management'},
            risk_level='high',
            persist=True,
            requires_confirmation=True,
        )
    if '降' in clean and '优先级' in clean:
        return LongTermRuleCommand(
            action='lower_priority',
            raw_text=clean,
            structured_rule={'rule_type': 'priority_lowering'},
            scope_payload={'domain': 'rule_management'},
            risk_level='high',
            persist=True,
            requires_confirmation=True,
        )
    if '钉钉' in clean and ('优先' in clean or '先看' in clean):
        return LongTermRuleCommand(
            action='add',
            raw_text=clean,
            structured_rule={'rule_type': 'source_priority', 'priority': ['dingtalk_specialist', 'hub', 'mes_wms']},
            scope_payload={'domain': 'daily_report'},
            risk_level='high',
            persist=True,
            requires_confirmation=True,
        )
    return LongTermRuleCommand(
        action='add',
        raw_text=clean,
        structured_rule={'rule_type': 'response_style', 'order': ['conclusion', 'sources']},
        scope_payload={'domain': 'all'},
        risk_level='low',
        persist=True,
        requires_confirmation=False,
    )


def create_or_confirm_rule(
    db: Session,
    *,
    command: LongTermRuleCommand,
    actor_user_id: int | None,
    trace_id: str | None,
) -> HermesLongTermRule:
    rule = HermesLongTermRule(
        rule_key=f'rule-{uuid4().hex}',
        raw_text=redact_secret_text(command.raw_text),
        structured_rule=command.structured_rule,
        scope_payload=command.scope_payload,
        status='pending_confirmation' if command.requires_confirmation else 'active',
        risk_level=command.risk_level,
        priority=100,
        created_by_id=actor_user_id,
        confirmed_by_id=None if command.requires_confirmation else actor_user_id,
        source_trace_id=trace_id,
    )
    db.add(rule)
    db.flush()
    return rule


def lower_rule_priority(db: Session, *, rule_key: str, actor_user_id: int | None) -> HermesLongTermRule:
    rule = db.query(HermesLongTermRule).filter(HermesLongTermRule.rule_key == rule_key).one()
    rule.status = 'lowered'
    rule.priority = max(int(rule.priority or 100), 100) + 100
    rule.confirmed_by_id = actor_user_id
    db.flush()
    return rule


def list_active_rules(db: Session) -> list[HermesLongTermRule]:
    return (
        db.query(HermesLongTermRule)
        .filter(HermesLongTermRule.status == 'active')
        .order_by(HermesLongTermRule.priority.asc(), HermesLongTermRule.id.asc())
        .all()
    )
