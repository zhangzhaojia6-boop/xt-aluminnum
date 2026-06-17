from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import AgentChannelBinding, AgentProfile, CommunicationChannel
from app.services.agent_personal_bootstrap_service import ensure_zhang_zhaojia_personal_agents
from app.services.agent_robot_bootstrap_service import (
    ZZJ_CUSTOM_ROBOT_SPECS,
    ensure_zzj_custom_robot_channels,
)


def _db_session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    return Session()


def test_zzj_custom_robot_plan_does_not_write_without_apply() -> None:
    db = _db_session()
    try:
        ensure_zhang_zhaojia_personal_agents(db, apply=True)
        outcome = ensure_zzj_custom_robot_channels(db, apply=False)

        assert outcome.applied is False
        assert outcome.channel_total == 6
        assert outcome.binding_total == 6
        assert db.query(CommunicationChannel).filter(CommunicationChannel.channel_type == 'dingtalk_custom_robot').count() == 0
    finally:
        db.close()


def test_zzj_custom_robot_apply_creates_dry_run_env_ref_channels() -> None:
    db = _db_session()
    try:
        ensure_zhang_zhaojia_personal_agents(db, apply=True)

        outcome = ensure_zzj_custom_robot_channels(db, apply=True)

        assert outcome.applied is True
        assert outcome.channel_total == 6
        assert outcome.binding_total == 6

        channels = (
            db.query(CommunicationChannel)
            .filter(CommunicationChannel.channel_type == 'dingtalk_custom_robot')
            .order_by(CommunicationChannel.channel_key.asc())
            .all()
        )
        assert len(channels) == 6
        spec_by_key = {item['channel_key']: item for item in ZZJ_CUSTOM_ROBOT_SPECS}
        for channel in channels:
            spec = spec_by_key[channel.channel_key]
            assert channel.target_type == 'debug_group'
            assert channel.target_key == 'zzj-debug-agent-group'
            assert channel.dry_run is True
            assert channel.secret_ref == spec['secret_ref']
            assert not channel.channel_key.startswith('https://')
            assert not str(channel.secret_ref).startswith('SEC')
            assert channel.metadata_payload['stores_plain_secret'] is False
            assert channel.metadata_payload['stores_plain_webhook'] is False
    finally:
        db.close()


def test_zzj_custom_robot_apply_can_enable_real_send_after_confirmation() -> None:
    db = _db_session()
    try:
        ensure_zhang_zhaojia_personal_agents(db, apply=True)

        outcome = ensure_zzj_custom_robot_channels(db, apply=True, dry_run=False)

        assert outcome.applied is True
        channels = (
            db.query(CommunicationChannel)
            .filter(CommunicationChannel.channel_type == 'dingtalk_custom_robot')
            .all()
        )
        assert len(channels) == 6
        assert all(channel.dry_run is False for channel in channels)
        assert all(not channel.channel_key.startswith('https://') for channel in channels)
        assert all(not str(channel.secret_ref).startswith('SEC') for channel in channels)
    finally:
        db.close()


def test_zzj_custom_robot_apply_is_idempotent_and_preserves_personal_channel() -> None:
    db = _db_session()
    try:
        ensure_zhang_zhaojia_personal_agents(db, apply=True)
        personal = (
            db.query(CommunicationChannel)
            .filter(CommunicationChannel.channel_type == 'dingtalk_work_notice')
            .one()
        )

        first = ensure_zzj_custom_robot_channels(db, apply=True)
        second = ensure_zzj_custom_robot_channels(db, apply=True)

        assert first.channel_total == second.channel_total == 6
        assert first.binding_total == second.binding_total == 6
        assert db.query(AgentProfile).count() == 6
        assert db.query(CommunicationChannel).count() == 7
        assert db.query(AgentChannelBinding).count() == 12

        db.refresh(personal)
        assert personal.channel_type == 'dingtalk_work_notice'
        assert personal.target_type == 'user'
        assert personal.dry_run is True
    finally:
        db.close()
