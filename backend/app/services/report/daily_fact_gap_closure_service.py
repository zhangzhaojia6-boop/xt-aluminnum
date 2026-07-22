from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.business_time import local_now
from app.models.agent_communication import (
    AgentChannelBinding,
    AgentEvent,
    AgentProfile,
    CommunicationChannel,
)
from app.services import agent_communication_service
from app.services.report.daily_report_gap_analysis import classify_daily_report_field_gap
from app.services.report.template_daily_report import FACT_LABELS


EVENT_TYPE = "daily_fact_gap"
SOURCE_TYPE = "daily_fact_closure"
AGENT_CODE = "factory_dispatch"
OPEN_EVENT_STATUSES = {"new", "open", "pending"}
OUTBOX_DEDUPE_MINUTES = 24 * 60
CORE_FIELD_LABELS = {
    "total_output_daily": "全厂总产量",
    "finished_inbound_daily": "成品入库量",
    "wip_total": "在制料总量",
    "total_electricity_kwh": "全厂高压总用电量",
    "daily_yield_rate": "日成品率",
}
GROUP_LABELS = {
    "opening": "日报总览",
    "workshop_output": "车间产量",
    "manual_supplement": "专项补录",
    "wip": "在制料",
    "energy": "能源",
    "contract_input": "合同与投料",
    "yield": "成品率",
    "cost": "成本",
    "unclassified": "日报",
}
OWNER_ROLE_LABELS = {
    "factory_dispatch": "管理调度",
    "machine_operator": "机台主操",
    "quality_owner": "质检内勤",
    "planning_owner": "计划内勤",
    "energy_chief": "总电工",
    "storage_owner": "成品库",
    "shipment_outflow_owner": "园区剪切内勤",
    "recovery_owner": "回收内勤",
    "overhaul_owner": "大修内勤",
}


def sync_daily_fact_gap_events(
    db: Session,
    *,
    business_date: date,
    bundle: Mapping[str, Any],
    trace_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    checked_at = local_now(now)
    gap_items = _real_source_gap_items(bundle)
    existing_events = (
        db.query(AgentEvent)
        .filter(
            AgentEvent.event_type == EVENT_TYPE,
            AgentEvent.business_date == business_date,
        )
        .order_by(AgentEvent.id.asc())
        .all()
    )
    existing_by_ref = {
        str(event.source_ref): event
        for event in existing_events
        if event.source_ref
    }

    created = 0
    reopened = 0
    open_events: list[AgentEvent] = []
    active_refs: set[str] = set()
    for item in gap_items:
        field = item["field"]
        source_ref = _event_source_ref(business_date, field)
        active_refs.add(source_ref)
        event = existing_by_ref.get(source_ref)
        previous_payload = dict(event.payload) if event is not None and isinstance(event.payload, Mapping) else {}
        was_reopened = False
        if event is None:
            event = AgentEvent(
                event_type=EVENT_TYPE,
                severity="warning",
                status="open",
                scope_type="factory",
                source_type=SOURCE_TYPE,
                source_ref=source_ref,
                business_date=business_date,
                occurred_at=checked_at,
            )
            db.add(event)
            existing_events.append(event)
            existing_by_ref[source_ref] = event
            created += 1
        elif event.status not in OPEN_EVENT_STATUSES:
            event.status = "open"
            reopened += 1
            was_reopened = True

        event.severity = "warning"
        event.payload = {
            **previous_payload,
            **item,
            "summary": f"{_field_label(field)} 缺少可信事实",
            "trace_id": trace_id,
            "first_detected_trace_id": previous_payload.get("first_detected_trace_id") or trace_id,
            "first_detected_at": previous_payload.get("first_detected_at") or checked_at.isoformat(),
            "last_checked_at": checked_at.isoformat(),
            "last_checked_trace_id": trace_id,
        }
        if was_reopened:
            event.payload = {**event.payload, "reopened_at": checked_at.isoformat()}
        open_events.append(event)

    resolved_events: list[AgentEvent] = []
    for event in existing_events:
        if event.source_ref in active_refs or event.status not in OPEN_EVENT_STATUSES:
            continue
        payload = dict(event.payload) if isinstance(event.payload, Mapping) else {}
        field = str(payload.get("field") or "unknown")
        event.status = "resolved"
        event.severity = "info"
        event.payload = {
            **payload,
            "summary": f"{_field_label(field)} 已补齐可信事实",
            "fact_status": "confirmed",
            "resolved_at": checked_at.isoformat(),
            "resolution_trace_id": trace_id,
            "last_checked_at": checked_at.isoformat(),
            "last_checked_trace_id": trace_id,
        }
        resolved_events.append(event)

    db.flush()
    delivery_status = "not_needed"
    outbox_message_id: int | None = None
    if open_events or resolved_events:
        channel = _preferred_bound_channel(db)
        if channel is None:
            delivery_status = "channel_unavailable"
        else:
            message = agent_communication_service.queue_bound_message(
                db,
                agent_code=AGENT_CODE,
                channel_key=channel.channel_key,
                channel_type=channel.channel_type,
                title=f"【Hermes 事实闭环】{business_date.isoformat()}",
                content=_outbox_content(
                    business_date=business_date,
                    gap_items=gap_items,
                    resolved_count=len(resolved_events),
                    trace_id=trace_id,
                ),
                business_date=business_date,
                source_summary=SOURCE_TYPE,
                trace_id=trace_id,
                event_id=(open_events or resolved_events)[0].id,
                payload={
                    "event_type": EVENT_TYPE,
                    "event_ids": [event.id for event in open_events],
                    "open_event_ids": [event.id for event in open_events],
                    "resolved_event_ids": [event.id for event in resolved_events],
                    "entry_route": "/entry/fill",
                    "gap_signature": _gap_signature(gap_items),
                    "assignments": [
                        {
                            "field": item["field"],
                            "owner_role": item["owner_role"],
                            "entry_route": item["entry_route"],
                            "entry_fields": item["entry_fields"],
                            "fill_strategy": item["fill_strategy"],
                        }
                        for item in gap_items
                    ],
                },
                dedupe_key=_outbox_dedupe_key(business_date, gap_items),
                dedupe_window_minutes=OUTBOX_DEDUPE_MINUTES,
                now=checked_at,
                commit=False,
            )
            outbox_message_id = message.id
            delivery_status = message.status

        for event in [*open_events, *resolved_events]:
            event.payload = {
                **(event.payload or {}),
                "delivery_status": delivery_status,
                "outbox_message_id": outbox_message_id,
            }
        db.flush()

    return {
        "created": created,
        "reopened": reopened,
        "resolved": len(resolved_events),
        "open": len(open_events),
        "delivery_status": delivery_status,
        "outbox_message_id": outbox_message_id,
    }


def list_open_daily_fact_gap_dates(db: Session, *, limit: int = 7) -> list[date]:
    rows = (
        db.query(AgentEvent.business_date)
        .filter(
            AgentEvent.event_type == EVENT_TYPE,
            AgentEvent.status.in_(OPEN_EVENT_STATUSES),
            AgentEvent.business_date.is_not(None),
        )
        .distinct()
        .order_by(AgentEvent.business_date.desc())
        .limit(max(1, min(int(limit or 7), 31)))
        .all()
    )
    return [row[0] for row in rows if row[0] is not None]


def has_open_daily_fact_gap(db: Session, *, business_date: date) -> bool:
    return (
        db.query(AgentEvent.id)
        .filter(
            AgentEvent.event_type == EVENT_TYPE,
            AgentEvent.status.in_(OPEN_EVENT_STATUSES),
            AgentEvent.business_date == business_date,
        )
        .first()
        is not None
    )


def _real_source_gap_items(bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    missing_fields = [str(field) for field in bundle.get("missing_fields") or [] if str(field).strip()]
    plan_items = bundle.get("gap_plan") if isinstance(bundle.get("gap_plan"), Mapping) else {}
    plan_by_field = {
        str(item.get("field")): item
        for item in plan_items.get("items", [])
        if isinstance(item, Mapping) and item.get("problem_type") == "missing_field" and item.get("field")
    }
    fact_status_by_field: dict[str, str] = {}
    closure = bundle.get("fact_closure") if isinstance(bundle.get("fact_closure"), Mapping) else {}
    for raw in closure.get("critical_fields", []):
        if not isinstance(raw, Mapping):
            continue
        field = str(raw.get("field") or "").strip()
        status = str(raw.get("status") or "").strip()
        if field and status in {"missing", "needs_evidence"}:
            fact_status_by_field[field] = status
            if field not in missing_fields:
                missing_fields.append(field)

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for field in missing_fields:
        if field in seen:
            continue
        seen.add(field)
        action = classify_daily_report_field_gap(field)
        raw_action = plan_by_field.get(field)
        if isinstance(raw_action, Mapping):
            for key in ("source_lane", "next_step"):
                if raw_action.get(key):
                    action[key] = raw_action[key]
        items.append(
            {
                "field": field,
                "fact_status": fact_status_by_field.get(field, "missing"),
                "problem_type": "missing_field",
                "source_lane": str(action.get("source_lane") or "unknown"),
                "entry_route": str(action.get("entry_route") or "/entry/fill"),
                "fill_strategy": str(action.get("fill_strategy") or "source_recheck"),
                "owner_role": str(action.get("owner_role") or "factory_dispatch"),
                "entry_fields": list(action.get("entry_fields") or []),
                "entry_field": action.get("entry_field"),
                "next_step": str(action.get("next_step") or "请负责人补充可信事实并保留来源。"),
            }
        )
    return items


def _preferred_bound_channel(db: Session) -> CommunicationChannel | None:
    agent = (
        db.query(AgentProfile)
        .filter(AgentProfile.code == AGENT_CODE, AgentProfile.is_active.is_(True))
        .first()
    )
    if agent is None:
        return None
    channels = (
        db.query(CommunicationChannel)
        .join(AgentChannelBinding, AgentChannelBinding.channel_id == CommunicationChannel.id)
        .filter(
            AgentChannelBinding.agent_profile_id == agent.id,
            AgentChannelBinding.is_active.is_(True),
            CommunicationChannel.is_active.is_(True),
            CommunicationChannel.channel_type.in_((
                "dingtalk_custom_robot",
                "dingtalk_group",
                "dingtalk_work_notice",
            )),
        )
        .all()
    )
    if not channels:
        return None
    target_priority = {"management": 0, "factory": 1, "group": 1, "user": 2}
    channel_priority = {"dingtalk_custom_robot": 0, "dingtalk_group": 1, "dingtalk_work_notice": 2}
    return min(
        channels,
        key=lambda channel: (
            bool(channel.dry_run),
            target_priority.get(str(channel.target_type), 9),
            channel_priority.get(str(channel.channel_type), 9),
            int(channel.id or 0),
        ),
    )


def _event_source_ref(business_date: date, field: str) -> str:
    raw = f"{EVENT_TYPE}:{business_date.isoformat()}:{field}"
    if len(raw) <= 128:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{raw[:111]}:{digest}"


def _outbox_dedupe_key(business_date: date, gap_items: list[dict[str, Any]]) -> str:
    return f"{EVENT_TYPE}:{business_date.isoformat()}:{_gap_signature(gap_items)}"


def _gap_signature(gap_items: list[dict[str, Any]]) -> str:
    if not gap_items:
        return "resolved"
    raw = "|".join(sorted(f"{item['field']}:{item['fact_status']}" for item in gap_items))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _outbox_content(
    *,
    business_date: date,
    gap_items: list[dict[str, Any]],
    resolved_count: int,
    trace_id: str,
) -> str:
    if not gap_items:
        return (
            "鑫泰铝业智能大脑已重新核对 MES、数据中枢、扫码补录和钉钉证据。\n\n"
            f"- 业务日：{business_date.isoformat()}\n"
            "- 结果：日报缺失事实已补齐，相关事件已自动关闭\n"
            f"- 本轮关单：{resolved_count} 项\n"
            f"- 追踪号：{trace_id}"
        )
    item_lines = []
    for item in gap_items[:8]:
        owner_label = OWNER_ROLE_LABELS.get(str(item.get("owner_role")), "管理调度")
        item_lines.append(f"- {_field_label(item['field'])}（责任：{owner_label}）：{item['next_step']}")
    if len(gap_items) > 8:
        item_lines.append(f"- 另有 {len(gap_items) - 8} 项，请在异常中心查看")
    resolved_line = f"- 本轮已补齐：{resolved_count} 项\n" if resolved_count else ""
    return (
        "鑫泰铝业智能大脑已重新核对 MES、数据中枢、扫码补录和钉钉证据。\n\n"
        f"- 业务日：{business_date.isoformat()}\n"
        f"- 待补事实：{len(gap_items)} 项\n"
        f"{resolved_line}"
        + "\n".join(item_lines)
        + "\n- 填报入口：/entry/fill"
        + f"\n- 追踪号：{trace_id}"
    )


def _field_label(field: str) -> str:
    known_label = CORE_FIELD_LABELS.get(field) or FACT_LABELS.get(field)
    if known_label:
        return str(known_label)
    group = classify_daily_report_field_gap(field)["group"]
    return f"{GROUP_LABELS.get(group, '日报')}字段"
