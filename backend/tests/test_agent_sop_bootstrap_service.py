from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import AgentProfile
from app.services.agent_personal_bootstrap_service import ensure_zhang_zhaojia_personal_agents
from app.services.agent_sop_bootstrap_service import ensure_zzj_agent_sop


def _session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    return SessionLocal()


def test_sop_preview_does_not_write() -> None:
    db = _session()
    try:
        ensure_zhang_zhaojia_personal_agents(db, apply=True)
        outcome = ensure_zzj_agent_sop(db, apply=False)

        assert outcome.applied is False
        assert outcome.agent_total == 6
        assert outcome.workflow_total >= 6
        agent = db.query(AgentProfile).filter(AgentProfile.code == 'daily_report_secretary_zzj').one()
        assert 'workflow' not in (agent.config_payload or {})
    finally:
        db.close()


def test_sop_apply_adds_workflows_without_removing_capabilities() -> None:
    db = _session()
    try:
        ensure_zhang_zhaojia_personal_agents(db, apply=True)
        outcome = ensure_zzj_agent_sop(db, apply=True)

        assert outcome.applied is True
        secretary = db.query(AgentProfile).filter(AgentProfile.code == 'daily_report_secretary_zzj').one()
        payload = secretary.config_payload or {}
        assert payload['capabilities'] == ['daily_report_preview', 'report_publish_approval_required']
        assert payload['workflow']['initial_report_time'] == '07:30'
        assert payload['workflow']['correction_report_time'] == '09:35'
        assert payload['workflow']['requires_outbox'] is True
        assert payload['workflow']['can_direct_send_dingtalk'] is False
    finally:
        db.close()
