from __future__ import annotations

from sqlalchemy.orm import Session

from app.services import agent_communication_service


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

    agent_communication_service.register_agent(
        db,
        code=clean_agent_code,
        name="Hermes root_owner 私聊 Agent",
        agent_type="factory_brain",
        scope_type="user",
        config_payload={
            "owner_name": clean_owner_name,
            "owner_dingtalk_user_id": clean_user_id,
            "capabilities": [
                "root_owner_private_reply",
                "evidence_trace",
                "readonly_source_query",
            ],
            "requires_outbox": True,
        },
    )
    channel = agent_communication_service.register_channel(
        db,
        channel_type="dingtalk_work_notice",
        channel_key=clean_user_id,
        name=f"{clean_owner_name} root_owner 私聊回复通道",
        target_type="user",
        target_key=clean_user_id,
        dry_run=False,
        metadata_payload={
            "root_owner_reply_channel": True,
            "owner_name": clean_owner_name,
            "owner_dingtalk_user_id": clean_user_id,
            "managed_by": "ensure_root_owner_private_reply_channel",
        },
    )
    agent_communication_service.bind_agent_to_channel(
        db,
        agent_code=clean_agent_code,
        channel_key=channel.channel_key,
        channel_type=channel.channel_type,
        min_severity="info",
    )
    return {
        "agent_code": clean_agent_code,
        "channel_type": channel.channel_type,
        "channel_key": channel.channel_key,
        "target_key": channel.target_key,
        "dry_run": channel.dry_run,
    }
