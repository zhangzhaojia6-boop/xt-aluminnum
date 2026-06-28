from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.agent_communication import (
    AgentChannelBinding,
    AgentProfile,
    CommunicationChannel,
)


ROOT_OWNER_REPLY_CHANNEL_TYPE = "dingtalk_work_notice"


def ensure_root_owner_private_reply_channel(
    db: Session,
    *,
    agent_code: str,
    dingtalk_user_id: str,
    owner_name: str,
) -> dict:
    clean_agent_code = str(agent_code or "").strip() or "factory_dispatch"
    clean_user_id = str(dingtalk_user_id or "").strip()
    clean_owner_name = str(owner_name or "").strip() or "root_owner"
    if not clean_user_id:
        raise ValueError("root_owner_dingtalk_user_id_required")
    channel_key = _root_owner_reply_channel_key(clean_agent_code, clean_user_id)

    agent = db.query(AgentProfile).filter(AgentProfile.code == clean_agent_code).first()
    if agent is None:
        agent = AgentProfile(
            code=clean_agent_code,
            name="Hermes root_owner 私聊 Agent",
            agent_type="factory_brain",
            scope_type="user",
        )
        db.add(agent)
    agent.name = "Hermes root_owner 私聊 Agent"
    agent.agent_type = "factory_brain"
    agent.scope_type = "user"
    agent.workshop_id = None
    agent.team_id = None
    agent.config_payload = {
        "owner_name": clean_owner_name,
        "owner_dingtalk_user_id": clean_user_id,
        "capabilities": [
            "root_owner_private_reply",
            "evidence_trace",
            "readonly_source_query",
        ],
        "requires_outbox": True,
    }
    agent.is_active = True
    db.flush()

    channel = (
        db.query(CommunicationChannel)
        .filter(
            CommunicationChannel.channel_type == ROOT_OWNER_REPLY_CHANNEL_TYPE,
            CommunicationChannel.channel_key == channel_key,
        )
        .first()
    )
    if channel is None:
        channel = CommunicationChannel(
            channel_type=ROOT_OWNER_REPLY_CHANNEL_TYPE,
            channel_key=channel_key,
            name=f"{clean_owner_name} root_owner 私聊回复通道",
            target_type="user",
        )
        db.add(channel)
    channel.name = f"{clean_owner_name} root_owner 私聊回复通道"
    channel.target_type = "user"
    channel.target_key = clean_user_id
    channel.workshop_id = None
    channel.team_id = None
    channel.dry_run = False
    channel.secret_ref = None
    channel.metadata_payload = {
        "root_owner_reply_channel": True,
        "owner_name": clean_owner_name,
        "owner_dingtalk_user_id": clean_user_id,
        "managed_by": "ensure_root_owner_private_reply_channel",
    }
    channel.is_active = True
    db.flush()

    rows = (
        db.query(AgentChannelBinding, CommunicationChannel)
        .join(CommunicationChannel, AgentChannelBinding.channel_id == CommunicationChannel.id)
        .filter(
            AgentChannelBinding.agent_profile_id == agent.id,
            CommunicationChannel.channel_type == ROOT_OWNER_REPLY_CHANNEL_TYPE,
        )
        .all()
    )
    for binding, bound_channel in rows:
        if binding.channel_id == channel.id:
            continue
        if (bound_channel.metadata_payload or {}).get("root_owner_reply_channel") is True:
            binding.is_active = False
            bound_channel.is_active = False

    binding = (
        db.query(AgentChannelBinding)
        .filter(
            AgentChannelBinding.agent_profile_id == agent.id,
            AgentChannelBinding.channel_id == channel.id,
        )
        .first()
    )
    if binding is None:
        binding = AgentChannelBinding(agent_profile_id=agent.id, channel_id=channel.id)
        db.add(binding)
    binding.is_active = True
    binding.min_severity = "info"
    db.flush()
    db.commit()
    db.refresh(channel)

    return {
        "agent_code": clean_agent_code,
        "channel_type": channel.channel_type,
        "channel_key": channel.channel_key,
        "target_key": channel.target_key,
        "dry_run": channel.dry_run,
    }


def _root_owner_reply_channel_key(agent_code: str, dingtalk_user_id: str) -> str:
    return f"root_owner:{agent_code}:{dingtalk_user_id}"
