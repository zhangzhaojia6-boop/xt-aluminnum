import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base
from app.models.agent_communication import (
    AgentChannelBinding,
    AgentProfile,
    CommunicationChannel,
)
from app.services import agent_communication_service
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
        assert outcome["channel_key"] == "root_owner:factory_dispatch:dt-root-001"
        assert outcome["target_key"] == "dt-root-001"
        assert outcome["dry_run"] is False

        agent = db.query(AgentProfile).filter(AgentProfile.code == "factory_dispatch").one()
        channel = (
            db.query(CommunicationChannel)
            .filter(CommunicationChannel.channel_key == "root_owner:factory_dispatch:dt-root-001")
            .one()
        )
        binding = db.query(AgentChannelBinding).one()

        assert agent.is_active is True
        assert channel.channel_key == "root_owner:factory_dispatch:dt-root-001"
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


def test_ensure_root_owner_private_reply_channel_replaces_previous_root_owner_binding() -> None:
    db = _db_session()
    try:
        ensure_root_owner_private_reply_channel(
            db,
            agent_code="factory_dispatch",
            dingtalk_user_id="dt-root-001",
            owner_name="root_owner",
        )
        outcome = ensure_root_owner_private_reply_channel(
            db,
            agent_code="factory_dispatch",
            dingtalk_user_id="dt-root-002",
            owner_name="root_owner",
        )

        assert outcome["channel_key"] == "root_owner:factory_dispatch:dt-root-002"
        assert outcome["target_key"] == "dt-root-002"

        agent = db.query(AgentProfile).filter(AgentProfile.code == "factory_dispatch").one()
        rows = (
            db.query(AgentChannelBinding, CommunicationChannel)
            .join(CommunicationChannel, AgentChannelBinding.channel_id == CommunicationChannel.id)
            .filter(
                AgentChannelBinding.agent_profile_id == agent.id,
                CommunicationChannel.channel_type == "dingtalk_work_notice",
            )
            .all()
        )
        root_owner_rows = [
            (binding, channel)
            for binding, channel in rows
            if (channel.metadata_payload or {}).get("root_owner_reply_channel") is True
        ]
        active_rows = [
            (binding, channel)
            for binding, channel in root_owner_rows
            if binding.is_active is True
        ]
        old_binding = next(
            binding
            for binding, channel in root_owner_rows
            if channel.channel_key == "root_owner:factory_dispatch:dt-root-001"
        )
        old_channel = next(
            channel
            for binding, channel in root_owner_rows
            if channel.channel_key == "root_owner:factory_dispatch:dt-root-001"
        )

        assert len(active_rows) == 1
        assert active_rows[0][1].channel_key == "root_owner:factory_dispatch:dt-root-002"
        assert old_binding.is_active is False
        assert old_channel.is_active is False
        assert active_rows[0][1].is_active is True
    finally:
        db.close()


def test_ensure_root_owner_private_reply_channel_deactivates_old_channel_with_pending_message() -> None:
    db = _db_session()
    try:
        ensure_root_owner_private_reply_channel(
            db,
            agent_code="factory_dispatch",
            dingtalk_user_id="dt-root-001",
            owner_name="root_owner",
        )
        old_channel = (
            db.query(CommunicationChannel)
            .filter(
                CommunicationChannel.channel_type == "dingtalk_work_notice",
                CommunicationChannel.channel_key == "root_owner:factory_dispatch:dt-root-001",
            )
            .one()
        )
        pending_message = agent_communication_service.queue_bound_message(
            db,
            agent_code="factory_dispatch",
            channel_key="root_owner:factory_dispatch:dt-root-001",
            channel_type="dingtalk_work_notice",
            title="old root owner message",
            content="pending before rebind",
        )
        retrying_message = agent_communication_service.queue_bound_message(
            db,
            agent_code="factory_dispatch",
            channel_key="root_owner:factory_dispatch:dt-root-001",
            channel_type="dingtalk_work_notice",
            title="old retrying root owner message",
            content="retrying before rebind",
        )
        retrying_message.status = "retrying"
        retrying_message.attempts = 1
        retrying_message.next_retry_at = None
        db.commit()

        ensure_root_owner_private_reply_channel(
            db,
            agent_code="factory_dispatch",
            dingtalk_user_id="dt-root-002",
            owner_name="root_owner",
        )

        new_channel = (
            db.query(CommunicationChannel)
            .filter(
                CommunicationChannel.channel_type == "dingtalk_work_notice",
                CommunicationChannel.channel_key == "root_owner:factory_dispatch:dt-root-002",
            )
            .one()
        )
        db.refresh(old_channel)
        sent_calls = []

        def sender(channel_key: str, payload: dict):
            sent_calls.append((channel_key, payload))
            return True, "sent"

        pending_outcome = agent_communication_service.dispatch_outbox_message(
            db,
            pending_message.id,
            sender=sender,
        )
        retrying_outcome = agent_communication_service.dispatch_outbox_message(
            db,
            retrying_message.id,
            sender=sender,
        )

        assert pending_message.channel_id == old_channel.id
        assert retrying_message.channel_id == old_channel.id
        assert old_channel.is_active is False
        assert new_channel.is_active is True
        assert pending_outcome.status == "retrying"
        assert pending_outcome.detail == "channel_not_available"
        assert retrying_outcome.status == "retrying"
        assert retrying_outcome.detail == "channel_not_available"
        assert sent_calls == []
    finally:
        db.close()


def test_ensure_root_owner_private_reply_channel_keeps_unrelated_bindings_active() -> None:
    db = _db_session()
    try:
        agent_communication_service.register_agent(
            db,
            code="factory_dispatch",
            name="Factory Dispatch",
            agent_type="factory_brain",
            scope_type="user",
        )
        group_channel = agent_communication_service.register_channel(
            db,
            channel_type="dingtalk_group",
            channel_key="group-001",
            name="Factory Group",
            target_type="group",
            target_key="group-001",
            metadata_payload={"purpose": "factory_group"},
        )
        group_binding = agent_communication_service.bind_agent_to_channel(
            db,
            agent_code="factory_dispatch",
            channel_key=group_channel.channel_key,
            channel_type=group_channel.channel_type,
            min_severity="info",
        )
        work_notice_channel = agent_communication_service.register_channel(
            db,
            channel_type="dingtalk_work_notice",
            channel_key="dt-work-notice-001",
            name="Other Work Notice",
            target_type="user",
            target_key="dt-work-notice-001",
            metadata_payload={"purpose": "other_work_notice"},
        )
        work_notice_binding = agent_communication_service.bind_agent_to_channel(
            db,
            agent_code="factory_dispatch",
            channel_key=work_notice_channel.channel_key,
            channel_type=work_notice_channel.channel_type,
            min_severity="info",
        )

        ensure_root_owner_private_reply_channel(
            db,
            agent_code="factory_dispatch",
            dingtalk_user_id="dt-root-001",
            owner_name="root_owner",
        )
        ensure_root_owner_private_reply_channel(
            db,
            agent_code="factory_dispatch",
            dingtalk_user_id="dt-root-002",
            owner_name="root_owner",
        )

        agent = db.query(AgentProfile).filter(AgentProfile.code == "factory_dispatch").one()
        rows = (
            db.query(AgentChannelBinding, CommunicationChannel)
            .join(CommunicationChannel, AgentChannelBinding.channel_id == CommunicationChannel.id)
            .filter(AgentChannelBinding.agent_profile_id == agent.id)
            .all()
        )
        binding_by_channel_key = {
            channel.channel_key: binding
            for binding, channel in rows
        }

        assert binding_by_channel_key["root_owner:factory_dispatch:dt-root-001"].is_active is False
        assert binding_by_channel_key["root_owner:factory_dispatch:dt-root-002"].is_active is True
        assert group_binding.is_active is True
        assert group_channel.is_active is True
        assert work_notice_binding.is_active is True
        assert work_notice_channel.is_active is True
    finally:
        db.close()


def test_ensure_root_owner_private_reply_channel_does_not_touch_other_agent_personal_channel() -> None:
    db = _db_session()
    try:
        agent_communication_service.register_agent(
            db,
            code="other_agent",
            name="Other Agent",
            agent_type="reporting",
            scope_type="user",
        )
        ordinary_channel = agent_communication_service.register_channel(
            db,
            channel_type="dingtalk_work_notice",
            channel_key="dt-root-001",
            name="Other Agent Personal Work Notice",
            target_type="user",
            target_key="dt-root-001",
            dry_run=True,
            metadata_payload={"purpose": "ordinary_personal_work_notice"},
        )
        ordinary_binding = agent_communication_service.bind_agent_to_channel(
            db,
            agent_code="other_agent",
            channel_key=ordinary_channel.channel_key,
            channel_type=ordinary_channel.channel_type,
            min_severity="info",
        )
        pending_message = agent_communication_service.queue_bound_message(
            db,
            agent_code="other_agent",
            channel_key="dt-root-001",
            channel_type="dingtalk_work_notice",
            title="ordinary personal message",
            content="pending ordinary message",
        )

        ensure_root_owner_private_reply_channel(
            db,
            agent_code="factory_dispatch",
            dingtalk_user_id="dt-root-001",
            owner_name="root_owner",
        )
        ensure_root_owner_private_reply_channel(
            db,
            agent_code="factory_dispatch",
            dingtalk_user_id="dt-root-002",
            owner_name="root_owner",
        )

        old_root_channel = (
            db.query(CommunicationChannel)
            .filter(
                CommunicationChannel.channel_type == "dingtalk_work_notice",
                CommunicationChannel.channel_key == "root_owner:factory_dispatch:dt-root-001",
            )
            .one()
        )
        new_root_channel = (
            db.query(CommunicationChannel)
            .filter(
                CommunicationChannel.channel_type == "dingtalk_work_notice",
                CommunicationChannel.channel_key == "root_owner:factory_dispatch:dt-root-002",
            )
            .one()
        )
        db.refresh(ordinary_channel)
        db.refresh(ordinary_binding)
        sent_calls = []

        def sender(channel_key: str, payload: dict):
            sent_calls.append((channel_key, payload))
            return True, "sent"

        outcome = agent_communication_service.dispatch_outbox_message(
            db,
            pending_message.id,
            sender=sender,
        )

        assert ordinary_channel.is_active is True
        assert ordinary_channel.dry_run is True
        assert ordinary_binding.is_active is True
        assert pending_message.channel_id == ordinary_channel.id
        assert ordinary_channel.target_key == "dt-root-001"
        assert outcome.status == "dry_run"
        assert outcome.detail != "channel_not_available"
        assert sent_calls == []
        assert old_root_channel.is_active is False
        assert new_root_channel.is_active is True
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
