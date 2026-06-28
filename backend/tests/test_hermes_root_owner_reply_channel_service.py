import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.agent_communication import (
    AgentChannelBinding,
    AgentProfile,
    CommunicationChannel,
)
from app.services.hermes_root_owner_reply_channel_service import ensure_root_owner_private_reply_channel


def _db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def test_ensure_root_owner_private_reply_channel_is_user_scoped_and_real_send_capable() -> None:
    db = _db_session()
    try:
        outcome = ensure_root_owner_private_reply_channel(
            db,
            agent_code="factory_dispatch",
            dingtalk_user_id="dt-root-001",
            owner_name="root_owner",
        )

        assert outcome["channel_type"] == "dingtalk_work_notice"
        assert outcome["channel_key"] == "dt-root-001"
        assert outcome["dry_run"] is False

        agent = db.query(AgentProfile).filter(AgentProfile.code == "factory_dispatch").one()
        channel = (
            db.query(CommunicationChannel)
            .filter(CommunicationChannel.channel_key == "dt-root-001")
            .one()
        )
        binding = db.query(AgentChannelBinding).one()

        assert agent.is_active is True
        assert channel.target_type == "user"
        assert channel.target_key == "dt-root-001"
        assert channel.dry_run is False
        assert channel.metadata_payload["root_owner_reply_channel"] is True
        assert binding.agent_profile_id == agent.id
        assert binding.channel_id == channel.id
    finally:
        db.close()


def test_ensure_root_owner_private_reply_channel_is_idempotent() -> None:
    db = _db_session()
    try:
        first = ensure_root_owner_private_reply_channel(
            db,
            agent_code="factory_dispatch",
            dingtalk_user_id="dt-root-001",
            owner_name="root_owner",
        )
        second = ensure_root_owner_private_reply_channel(
            db,
            agent_code="factory_dispatch",
            dingtalk_user_id="dt-root-001",
            owner_name="root_owner",
        )

        assert first == second
        assert db.query(AgentProfile).count() == 1
        assert db.query(CommunicationChannel).count() == 1
        assert db.query(AgentChannelBinding).count() == 1
    finally:
        db.close()


def test_ensure_root_owner_private_reply_channel_requires_dingtalk_user_id() -> None:
    db = _db_session()
    try:
        with pytest.raises(ValueError, match="root_owner_dingtalk_user_id_required"):
            ensure_root_owner_private_reply_channel(
                db,
                agent_code="factory_dispatch",
                dingtalk_user_id=" ",
                owner_name="root_owner",
            )
    finally:
        db.close()
