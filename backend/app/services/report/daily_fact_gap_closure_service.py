from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.orm import Session

from app.config import settings
from app.core.business_time import local_now
from app.domain.daily_report_field_contract import daily_report_field_contract_for
from app.models.agent_communication import (
    AgentEvent,
    AgentOutboxMessage,
)
from app.services import agent_communication_service
from app.services.report.daily_fact_notification_routing import (
    resolve_daily_fact_notification_routes,
)
from app.services.report.daily_report_gap_analysis import (
    build_daily_report_gap_action_route,
    classify_daily_report_field_gap,
)
from app.services.report.template_daily_report import FACT_LABELS

EVENT_TYPE = "daily_fact_gap"
SOURCE_TYPE = "daily_fact_closure"
AGENT_CODE = "factory_dispatch"
OPEN_EVENT_STATUSES = {"new", "open", "pending"}
OUTBOX_DEDUPE_MINUTES = 31 * 24 * 60
DELIVERY_STATUS_PRIORITY = ("dead_letter", "retrying", "pending", "failed", "sent", "dry_run")
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
    for item in gap_items:
        item["action_route"] = build_daily_report_gap_action_route(
            business_date=business_date,
            field=item["field"],
            trace_id=trace_id,
            action=item,
        )
        item["human_action_required"] = _human_action_required(item)
        item["automation_status"] = _automation_status(item)
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
        payload_item = dict(item)
        for key in ("deadline", "contract_version"):
            if _has_payload_value(previous_payload.get(key)):
                payload_item[key] = previous_payload[key]
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
            **payload_item,
            "summary": f"{_field_label(field)} 缺少可信事实",
            "trace_id": trace_id,
            "first_detected_trace_id": previous_payload.get("first_detected_trace_id") or trace_id,
            "first_detected_at": previous_payload.get("first_detected_at") or checked_at.isoformat(),
            "last_checked_at": checked_at.isoformat(),
            "last_checked_trace_id": trace_id,
            "automation_check_count": (
                0
                if item["human_action_required"]
                else _safe_count(previous_payload.get("automation_check_count")) + 1
            ),
            "notification_policy": "action_change_or_full_closure",
        }
        if (
            item["human_action_required"]
            and not was_reopened
            and not event.payload.get("action_notified_at")
            and previous_payload.get("outbox_message_id")
            and _human_action_required(previous_payload)
        ):
            event.payload = {
                **event.payload,
                "action_notified_at": (
                    previous_payload.get("first_detected_at")
                    or previous_payload.get("last_checked_at")
                    or checked_at.isoformat()
                ),
                "action_notification_outbox_id": previous_payload["outbox_message_id"],
            }
        if was_reopened:
            event.payload = {
                **event.payload,
                "reopened_at": checked_at.isoformat(),
            }
            event.payload.pop("action_notified_at", None)
            event.payload.pop("action_notification_outbox_id", None)
            event.payload.pop("closure_notified_at", None)
            event.payload.pop("closure_notification_outbox_id", None)
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
            "human_action_required": False,
            "automation_status": "resolved",
            "resolved_at": checked_at.isoformat(),
            "resolution_trace_id": trace_id,
            "last_checked_at": checked_at.isoformat(),
            "last_checked_trace_id": trace_id,
        }
        resolved_events.append(event)

    db.flush()
    delivery_status = "not_needed"
    outbox_message_id: int | None = None
    actionable_events = [
        event
        for event in open_events
        if _human_action_required(event.payload or {})
    ]
    full_closure = not gap_items and bool(resolved_events)
    closure_already_notified = any(
        (event.payload or {}).get("closure_notified_at")
        for event in existing_events
    )
    should_notify = bool(actionable_events) or (
        full_closure and not closure_already_notified
    )

    if should_notify:
        notification_events = [*open_events, *resolved_events]
        previous_outbox_ids_by_event = {
            event.id: _event_notification_outbox_ids(event)
            for event in notification_events
        }
        previous_notification_outbox_ids = set().union(*previous_outbox_ids_by_event.values())
        notification_state = "resolved" if full_closure else "blocked"
        assignments = []
        for event in actionable_events:
            payload = event.payload or {}
            assignments.append(
                {
                    "field": payload["field"],
                    "owner_role": payload["owner_role"],
                    "deadline": payload["deadline"],
                    "contract_version": payload["contract_version"],
                    "entry_route": payload["entry_route"],
                    "entry_fields": list(payload.get("entry_fields") or []),
                    "fill_strategy": payload["fill_strategy"],
                    "business_date": business_date.isoformat(),
                    "trace_id": payload["trace_id"],
                    "action_route": payload["action_route"],
                }
            )
        routing_assignments = assignments or ([{"field": "__full_closure__"}] if full_closure else [])
        routing = resolve_daily_fact_notification_routes(db, assignments=routing_assignments)
        outbox_messages = []
        routed_messages = []
        for route in routing["routes"]:
            channel = route["channel"]
            route_assignments = [
                assignment
                for assignment in route["assignments"]
                if assignment.get("field") != "__full_closure__"
            ]
            route_fields = {assignment["field"] for assignment in route_assignments}
            route_gap_items = [item for item in gap_items if item["field"] in route_fields]
            metadata = channel.metadata_payload if isinstance(channel.metadata_payload, Mapping) else {}
            recipient_mode = _recipient_mode(metadata)
            route_entry_route = _route_entry_route(
                recipient_mode=recipient_mode,
                route_assignments=route_assignments,
            )
            route_action_route = _route_action_route(
                business_date=business_date,
                trace_id=trace_id,
                recipient_mode=recipient_mode,
                route_assignments=route_assignments,
            )
            message = agent_communication_service.queue_bound_message(
                db,
                agent_code=AGENT_CODE,
                channel_key=channel.channel_key,
                channel_type=channel.channel_type,
                title=f"【Hermes 事实闭环】{business_date.isoformat()}",
                content=_outbox_content(
                    business_date=business_date,
                    gap_items=gap_items,
                    assignment_fields=route_fields,
                    resolved_count=len(resolved_events),
                    trace_id=trace_id,
                    recipient_mode=recipient_mode,
                    route_action_route=route_action_route,
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
                    "gap_signature": _gap_signature(route_gap_items),
                    "recipient_name": metadata.get("recipient_name"),
                    "organization_path": metadata.get("organization_path"),
                    "recipient_mode": recipient_mode,
                    "routing_status": route["routing_status"],
                    "entry_route": route_entry_route,
                    "action_route": route_action_route,
                    "assignments": route_assignments,
                    "auto_recheck_event_ids": [
                        event.id
                        for event in open_events
                        if (event.payload or {}).get("automation_status") == "rechecking_sources"
                    ],
                    "dependency_event_ids": [
                        event.id
                        for event in open_events
                        if (event.payload or {}).get("automation_status") == "waiting_for_dependencies"
                    ],
                    "notification_state": notification_state,
                },
                dedupe_key=_outbox_dedupe_key(
                    business_date,
                    notification_state,
                    route_assignments,
                ),
                dedupe_window_minutes=OUTBOX_DEDUPE_MINUTES,
                now=checked_at,
                commit=False,
            )
            outbox_messages.append(message)
            routed_messages.append((route, route_assignments, message))

        if not outbox_messages:
            delivery_status = "channel_unavailable"
        else:
            preferred_message = _preferred_outbox_message(outbox_messages)
            outbox_message_id = preferred_message.id
            delivery_status = _aggregate_delivery_status(
                outbox_messages,
                previous_outbox_ids=previous_notification_outbox_ids,
            )

        outbox_message_ids = [message.id for message in outbox_messages]
        notification_target_keys = [
            route["channel"].channel_key
            for route in routing["routes"]
        ]
        target_keys_by_field: dict[str, list[str]] = {}
        outbox_ids_by_field: dict[str, list[int]] = {}
        messages_by_field: dict[str, list[AgentOutboxMessage]] = {}
        targets_by_field: dict[str, list[dict[str, Any]]] = {}
        notification_targets: list[dict[str, Any]] = []
        routing_status_by_field: dict[str, str] = {}
        for route, route_assignments, message in routed_messages:
            channel = route["channel"]
            metadata = channel.metadata_payload if isinstance(channel.metadata_payload, Mapping) else {}
            target_snapshot = {
                "target_key": channel.target_key,
                "channel_id": channel.id,
                "recipient_name": metadata.get("recipient_name"),
                "organization_path": metadata.get("organization_path"),
                "recipient_mode": _recipient_mode(metadata),
                "routing_status": route["routing_status"],
            }
            notification_targets.append(target_snapshot)
            for assignment in route_assignments:
                field = assignment["field"]
                target_keys_by_field.setdefault(field, []).append(channel.channel_key)
                outbox_ids_by_field.setdefault(field, []).append(message.id)
                messages_by_field.setdefault(field, []).append(message)
                targets_by_field.setdefault(field, []).append(target_snapshot)
                routing_status_by_field[field] = route["routing_status"]
        for assignment in routing["unresolved"]:
            routing_status_by_field.setdefault(assignment["field"], "unresolved")

        for event in [*open_events, *resolved_events]:
            event_field = str((event.payload or {}).get("field") or "")
            event_messages = outbox_messages if full_closure else messages_by_field.get(event_field, [])
            event_target_keys = notification_target_keys if full_closure else target_keys_by_field.get(event_field, [])
            event_outbox_ids = outbox_message_ids if full_closure else outbox_ids_by_field.get(event_field, [])
            event_targets = notification_targets if full_closure else targets_by_field.get(event_field, [])
            event_preferred_message = _preferred_outbox_message(event_messages)
            event_delivery_status = _aggregate_delivery_status(
                event_messages,
                previous_outbox_ids=previous_outbox_ids_by_event.get(event.id, set()),
            )
            event_routing_status = routing_status_by_field.get(event_field)
            if event_routing_status is None:
                event_routing_status = routing["routes"][0]["routing_status"] if full_closure and routing["routes"] else "unresolved"
            event_payload = {
                **(event.payload or {}),
                "delivery_status": event_delivery_status,
                "outbox_message_id": event_preferred_message.id if event_preferred_message is not None else None,
                "notification_target_keys": event_target_keys,
                "notification_targets": event_targets,
                "action_notification_outbox_ids": event_outbox_ids,
                "routing_status": event_routing_status,
            }
            if not event_outbox_ids:
                event_payload.pop("action_notification_outbox_id", None)
            event.payload = event_payload
        if outbox_message_id is not None and full_closure:
            for event in resolved_events:
                event.payload = {
                    **(event.payload or {}),
                    "closure_notified_at": checked_at.isoformat(),
                    "closure_notification_outbox_id": outbox_message_id,
                }
        elif outbox_message_id is not None:
            for event in actionable_events:
                event_outbox_message_id = (event.payload or {}).get("outbox_message_id")
                if event_outbox_message_id is None:
                    continue
                event.payload = {
                    **(event.payload or {}),
                    "action_notified_at": checked_at.isoformat(),
                    "action_notification_outbox_id": event_outbox_message_id,
                }
        db.flush()
    elif gap_items and not actionable_events:
        delivery_status = "auto_rechecking"
    elif gap_items:
        delivery_status = "unchanged"
        outbox_message_id = _latest_action_outbox_id(actionable_events)

    return {
        "created": created,
        "reopened": reopened,
        "resolved": len(resolved_events),
        "open": len(open_events),
        "delivery_status": delivery_status,
        "outbox_message_id": outbox_message_id,
        "outbox_message_ids": (
            outbox_message_ids
            if should_notify
            else ([outbox_message_id] if outbox_message_id is not None else [])
        ),
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
                "deadline": str(action.get("deadline") or ""),
                "contract_version": _gap_contract_version(field, raw_action),
                "entry_fields": list(action.get("entry_fields") or []),
                "entry_field": action.get("entry_field"),
                "next_step": str(action.get("next_step") or "请负责人补充可信事实并保留来源。"),
            }
        )
    return items


def _gap_contract_version(field: str, payload: Mapping[str, Any] | None = None) -> str | None:
    if isinstance(payload, Mapping):
        explicit = str(payload.get("contract_version") or "").strip()
        if explicit:
            return explicit
    try:
        return daily_report_field_contract_for(field).contract_version
    except KeyError:
        return None


def _event_source_ref(business_date: date, field: str) -> str:
    raw = f"{EVENT_TYPE}:{business_date.isoformat()}:{field}"
    if len(raw) <= 128:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{raw[:111]}:{digest}"


def _outbox_dedupe_key(
    business_date: date,
    notification_state: str,
    assignments: list[dict[str, Any]],
) -> str:
    return (
        f"{EVENT_TYPE}:{business_date.isoformat()}:{notification_state}:"
        f"{_assignment_signature(assignments)}"
    )


def _assignment_signature(assignments: list[dict[str, Any]]) -> str:
    stable_assignments = [
        {
            "field": assignment.get("field"),
            "owner_role": assignment.get("owner_role"),
            "deadline": assignment.get("deadline"),
            "contract_version": assignment.get("contract_version"),
            "entry_route": assignment.get("entry_route"),
            "entry_fields": list(assignment.get("entry_fields") or []),
            "fill_strategy": assignment.get("fill_strategy"),
        }
        for assignment in assignments
    ]
    raw = json.dumps(stable_assignments, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _gap_signature(gap_items: list[dict[str, Any]]) -> str:
    if not gap_items:
        return "resolved"
    raw = "|".join(sorted(f"{item['field']}:{item['fact_status']}" for item in gap_items))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _outbox_content(
    *,
    business_date: date,
    gap_items: list[dict[str, Any]],
    assignment_fields: set[str],
    resolved_count: int,
    trace_id: str,
    recipient_mode: str,
    route_action_route: str | None,
) -> str:
    if not gap_items:
        return (
            "鑫泰铝业智能大脑完成本轮事实核对。\n\n"
            f"- 业务日：{business_date.isoformat()}\n"
            "- 结果：日报缺失事实已补齐，相关事件已自动关闭\n"
            f"- 本轮关单：{resolved_count} 项\n"
            f"- 追踪号：{trace_id}"
        )
    action_items = [
        item
        for item in _human_action_items(gap_items)
        if item["field"] in assignment_fields
    ]
    source_recheck_count = sum(
        item.get("automation_status") == "rechecking_sources"
        for item in gap_items
    )
    dependency_count = sum(
        item.get("automation_status") == "waiting_for_dependencies"
        for item in gap_items
    )
    item_lines = []
    for item in action_items[:8]:
        owner_label = OWNER_ROLE_LABELS.get(str(item.get("owner_role")), "管理调度")
        if recipient_mode == "supervisor":
            action_route = route_action_route or _supervisor_action_route(
                business_date=business_date,
                trace_id=trace_id,
            )
            action_label = "查看并跟进"
        else:
            action_route = _outbox_action_route(str(item["action_route"]))
            action_label = "立即补录"
        action_url = _public_action_url(action_route)
        item_lines.append(
            f"- {_field_label(item['field'])}（责任：{owner_label}）："
            f"{item['next_step']} [{action_label}]({action_url})"
        )
    if len(action_items) > 8:
        item_lines.append(f"- 另有 {len(action_items) - 8} 项可在异常中心查看")
    resolved_line = f"- 本轮已补齐：{resolved_count} 项\n" if resolved_count else ""
    return (
        "鑫泰铝业智能大脑完成本轮事实核对。\n\n"
        f"- 业务日：{business_date.isoformat()}\n"
        f"- 需要人工补录：{len(action_items)} 项\n"
        f"- 后台处理中：来源复查 {source_recheck_count} 项，"
        f"依赖补齐 {dependency_count} 项；状态不变不会重复提醒\n"
        f"{resolved_line}"
        + "\n".join(item_lines)
        + f"\n- 追踪号：{trace_id}"
    )


def _human_action_required(item: Mapping[str, Any]) -> bool:
    return (
        str(item.get("entry_route") or "") == "/entry/fill"
        and bool(item.get("entry_fields"))
    )


def _human_action_items(gap_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in gap_items if _human_action_required(item)]


def _automation_status(item: Mapping[str, Any]) -> str:
    if _human_action_required(item):
        return "waiting_for_owner"
    if str(item.get("fill_strategy") or "") == "dependency_fill":
        return "waiting_for_dependencies"
    return "rechecking_sources"


def _safe_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _has_payload_value(value: Any) -> bool:
    return bool(str(value or "").strip())


def _latest_action_outbox_id(events: list[AgentEvent]) -> int | None:
    message_ids = [
        _safe_count(
            (event.payload or {}).get("action_notification_outbox_id")
            or (event.payload or {}).get("outbox_message_id")
        )
        for event in events
    ]
    return max(message_ids, default=0) or None


def _preferred_outbox_message(
    messages: list[AgentOutboxMessage],
) -> AgentOutboxMessage | None:
    for status in DELIVERY_STATUS_PRIORITY:
        for message in messages:
            if message.status == status:
                return message
    return messages[0] if messages else None


def _aggregate_delivery_status(
    messages: list[AgentOutboxMessage],
    *,
    previous_outbox_ids: set[int],
) -> str:
    if not messages:
        return "channel_unavailable"
    current_outbox_ids = {message.id for message in messages}
    if current_outbox_ids.issubset(previous_outbox_ids):
        return "unchanged"
    statuses = {message.status for message in messages}
    for status in DELIVERY_STATUS_PRIORITY:
        if status in statuses:
            return status
    return "mixed"


def _event_notification_outbox_ids(event: AgentEvent) -> set[int]:
    payload = event.payload or {}
    values = list(payload.get("action_notification_outbox_ids") or [])
    values.extend((payload.get("action_notification_outbox_id"), payload.get("outbox_message_id")))
    return {_safe_count(value) for value in values if _safe_count(value)}


def _outbox_action_route(action_route: str) -> str:
    parsed = urlsplit(action_route)
    query = urlencode([
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key != "field"
    ])
    return urlunsplit(("", "", parsed.path, query, ""))


def _public_action_url(action_route: str) -> str:
    base_url = str(settings.PUBLIC_APP_BASE_URL or "").strip().rstrip("/")
    if not base_url:
        return action_route
    return f"{base_url}{action_route}"


def _recipient_mode(metadata: Mapping[str, Any]) -> str:
    mode = str(metadata.get("daily_fact_recipient_mode") or "").strip().lower()
    return "supervisor" if mode == "supervisor" else "specialist"


def _route_entry_route(
    *,
    recipient_mode: str,
    route_assignments: list[dict[str, Any]],
) -> str | None:
    if recipient_mode == "supervisor":
        return "/manage/workshop-dashboard"
    if not route_assignments:
        return None
    entry_route = str(route_assignments[0].get("entry_route") or "").strip()
    return entry_route or None


def _route_action_route(
    *,
    business_date: date,
    trace_id: str,
    recipient_mode: str,
    route_assignments: list[dict[str, Any]],
) -> str | None:
    if recipient_mode == "supervisor":
        return _supervisor_action_route(business_date=business_date, trace_id=trace_id)
    if not route_assignments:
        return None
    action_route = str(route_assignments[0].get("action_route") or "").strip()
    if action_route:
        return _outbox_action_route(action_route)
    entry_route = str(route_assignments[0].get("entry_route") or "").strip()
    if not entry_route:
        return None
    query = urlencode({
        "business_date": business_date.isoformat(),
        "trace_id": trace_id,
    })
    return f"{entry_route}?{query}"


def _supervisor_action_route(*, business_date: date, trace_id: str) -> str:
    query = urlencode({
        "business_date": business_date.isoformat(),
        "trace_id": trace_id,
    })
    return f"/manage/workshop-dashboard?{query}"


def _field_label(field: str) -> str:
    known_label = CORE_FIELD_LABELS.get(field) or FACT_LABELS.get(field)
    if known_label:
        return str(known_label)
    group = classify_daily_report_field_gap(field)["group"]
    return f"{GROUP_LABELS.get(group, '日报')}字段"
