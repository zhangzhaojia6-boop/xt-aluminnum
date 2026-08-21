from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_communication import (
    AgentChannelBinding,
    AgentProfile,
    CommunicationChannel,
)

AGENT_CODE = "factory_dispatch"
CHANNEL_TYPE = "dingtalk_work_notice"


def resolve_daily_fact_notification_routes(
    db: Session,
    *,
    assignments: list[dict[str, Any]],
) -> dict[str, list[Any]]:
    channels = _eligible_channels(db)
    specialist_channels = [
        channel
        for channel in channels
        if _metadata(channel).get("daily_fact_notification") is True
    ]
    fallback_channels = [
        channel
        for channel in channels
        if _metadata(channel).get("daily_fact_admin_fallback") is True
    ]
    route_assignments: dict[tuple[int, str], list[dict[str, Any]]] = {}
    unresolved = []
    for assignment in assignments:
        field = str(assignment.get("field") or "").strip()
        owner_role = str(assignment.get("owner_role") or "").strip()
        matched_channels = [
            channel
            for channel in specialist_channels
            if field in _metadata_values(channel, "daily_fact_fields")
        ]
        routing_status = "field_match"
        if not matched_channels:
            matched_channels = [
                channel
                for channel in specialist_channels
                if owner_role in _metadata_values(channel, "daily_fact_owner_roles")
            ]
            routing_status = "owner_role_match"
        if matched_channels:
            for channel in matched_channels:
                route_assignments.setdefault((channel.id, routing_status), []).append(assignment)
            continue
        unresolved.append(assignment)

    if unresolved and len(fallback_channels) == 1:
        fallback = fallback_channels[0]
        route_assignments[(fallback.id, "unresolved")] = list(unresolved)

    channels_by_id = {channel.id: channel for channel in channels}
    routes = [
        {
            "channel": channels_by_id[channel_id],
            "assignments": matched,
            "routing_status": routing_status,
        }
        for (channel_id, routing_status), matched in route_assignments.items()
    ]
    return {
        "routes": routes,
        "unresolved": unresolved,
    }


def _metadata(channel: CommunicationChannel) -> Mapping[str, Any]:
    return channel.metadata_payload if isinstance(channel.metadata_payload, Mapping) else {}


def _metadata_values(channel: CommunicationChannel, key: str) -> set[str]:
    return {
        str(value).strip()
        for value in _metadata(channel).get(key) or []
        if str(value).strip()
    }


def _eligible_channels(db: Session) -> list[CommunicationChannel]:
    agent = (
        db.query(AgentProfile)
        .filter(AgentProfile.code == AGENT_CODE, AgentProfile.is_active.is_(True))
        .first()
    )
    if agent is None:
        return []
    return (
        db.query(CommunicationChannel)
        .join(AgentChannelBinding, AgentChannelBinding.channel_id == CommunicationChannel.id)
        .filter(
            AgentChannelBinding.agent_profile_id == agent.id,
            AgentChannelBinding.is_active.is_(True),
            CommunicationChannel.is_active.is_(True),
            CommunicationChannel.dry_run.is_(False),
            CommunicationChannel.channel_type == CHANNEL_TYPE,
        )
        .order_by(CommunicationChannel.id.asc())
        .all()
    )
