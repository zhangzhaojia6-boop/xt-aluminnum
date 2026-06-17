from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import AgentChannelBinding, AgentProfile, CommunicationChannel
from app.services import agent_communication_service
from app.services.agent_personal_bootstrap_service import (
    ZHANG_ZHAOJIA_CHANNEL_KEY,
    ZHANG_ZHAOJIA_DINGTALK_USER_ID,
    ensure_zhang_zhaojia_personal_agents,
)


def _db_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def test_zhang_zhaojia_personal_agent_plan_does_not_write_without_apply() -> None:
    db = _db_session()
    try:
        outcome = ensure_zhang_zhaojia_personal_agents(db, apply=False)

        assert outcome.applied is False
        assert outcome.dingtalk_user_id == ZHANG_ZHAOJIA_DINGTALK_USER_ID
        assert outcome.channel_key == ZHANG_ZHAOJIA_CHANNEL_KEY
        assert outcome.channel_dry_run is True
        assert outcome.agent_total == 6
        assert db.query(AgentProfile).count() == 0
        assert db.query(CommunicationChannel).count() == 0
        assert db.query(AgentChannelBinding).count() == 0
    finally:
        db.close()


def test_zhang_zhaojia_personal_agent_apply_creates_only_user_scoped_dry_run_channel() -> None:
    db = _db_session()
    try:
        outcome = ensure_zhang_zhaojia_personal_agents(db, apply=True)

        assert outcome.applied is True
        assert outcome.agent_total == 6
        assert outcome.binding_total == 6

        channel = (
            db.query(CommunicationChannel)
            .filter(CommunicationChannel.channel_key == ZHANG_ZHAOJIA_CHANNEL_KEY)
            .one()
        )
        assert channel.channel_type == 'dingtalk_work_notice'
        assert channel.target_type == 'user'
        assert channel.target_key == ZHANG_ZHAOJIA_DINGTALK_USER_ID
        assert channel.dry_run is True
        assert channel.workshop_id is None
        assert channel.team_id is None
        assert channel.metadata_payload['owner_name'] == '张兆嘉'
        assert channel.metadata_payload['real_send_enabled'] is False

        agents = db.query(AgentProfile).order_by(AgentProfile.code.asc()).all()
        assert len(agents) == 6
        assert all(agent.scope_type == 'user' for agent in agents)
        assert all(agent.workshop_id is None for agent in agents)
        assert all(agent.team_id is None for agent in agents)
        assert all(agent.config_payload['owner_name'] == '张兆嘉' for agent in agents)
        assert all(agent.config_payload['requires_outbox'] is True for agent in agents)
    finally:
        db.close()


def test_zhang_zhaojia_personal_agent_apply_is_idempotent_and_preserves_existing_channels() -> None:
    db = _db_session()
    try:
        existing = agent_communication_service.register_channel(
            db,
            channel_type='dingtalk_group',
            channel_key='management-chat',
            name='管理层群',
            target_type='management',
            target_key='management',
            dry_run=False,
        )

        first = ensure_zhang_zhaojia_personal_agents(db, apply=True)
        second = ensure_zhang_zhaojia_personal_agents(db, apply=True)

        assert first.agent_total == second.agent_total == 6
        assert first.binding_total == second.binding_total == 6
        assert db.query(AgentProfile).count() == 6
        assert db.query(CommunicationChannel).count() == 2
        assert db.query(AgentChannelBinding).count() == 6

        db.refresh(existing)
        assert existing.channel_key == 'management-chat'
        assert existing.target_type == 'management'
        assert existing.dry_run is False
    finally:
        db.close()
