from __future__ import annotations

from collections.abc import Mapping
from datetime import date
import re
from typing import Any
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.core.business_time import local_now
from app.models.agent_communication import AgentEvent


EVENT_TYPE = "machine_fact_gap"
SOURCE_TYPE = "hermes_machine_fact"
OPEN_STATUSES = {"new", "open", "pending"}


def sync_machine_fact_gap_event(
    db: Session,
    *,
    business_date: date,
    intent: str,
    machine_filter: str | None,
    facts: Mapping[str, Any],
    trace_id: str,
) -> AgentEvent | None:
    source_ref = _source_ref(business_date, intent, machine_filter)
    event = (
        db.query(AgentEvent)
        .filter(
            AgentEvent.event_type == EVENT_TYPE,
            AgentEvent.source_ref == source_ref,
            AgentEvent.business_date == business_date,
        )
        .first()
    )
    checked_at = local_now()
    previous_payload = (
        dict(event.payload)
        if event is not None and isinstance(event.payload, Mapping)
        else {}
    )
    has_required_fact = _has_required_fact(intent, facts)
    if event is None and has_required_fact:
        return None
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

    if has_required_fact:
        event.status = "resolved"
        event.severity = "info"
        event.payload = {
            **previous_payload,
            **_base_payload(
                business_date=business_date,
                intent=intent,
                machine_filter=machine_filter,
                trace_id=trace_id,
            ),
            "fact_status": "confirmed",
            "summary": _resolved_summary(intent, machine_filter),
            "automation_status": "resolved",
            "resolved_at": checked_at.isoformat(),
            "resolution_trace_id": trace_id,
            "last_checked_at": checked_at.isoformat(),
            "last_checked_trace_id": trace_id,
        }
    else:
        event.status = "open"
        event.severity = "warning"
        event.payload = {
            **previous_payload,
            **_base_payload(
                business_date=business_date,
                intent=intent,
                machine_filter=machine_filter,
                trace_id=trace_id,
            ),
            "fact_status": "missing",
            "first_detected_at": (
                previous_payload.get("first_detected_at") or checked_at.isoformat()
            ),
            "first_detected_trace_id": (
                previous_payload.get("first_detected_trace_id") or trace_id
            ),
            "last_checked_at": checked_at.isoformat(),
            "last_checked_trace_id": trace_id,
        }
    db.flush()
    return event


def resolve_machine_stop_gap_events(
    db: Session,
    *,
    business_date: date,
    records: list[dict[str, Any]],
    trace_id: str,
) -> int:
    resolved = 0
    events = (
        db.query(AgentEvent)
        .filter(
            AgentEvent.event_type == EVENT_TYPE,
            AgentEvent.business_date == business_date,
            AgentEvent.status.in_(OPEN_STATUSES),
        )
        .all()
    )
    for event in events:
        payload = dict(event.payload) if isinstance(event.payload, Mapping) else {}
        if payload.get("intent") != "machine_stop":
            continue
        machine_filter = str(payload.get("machine_filter") or "").strip() or None
        matching_records = [
            record
            for record in records
            if _record_matches_machine(record, machine_filter)
        ]
        if not _has_required_fact(
            "machine_stop",
            {"stop_count": len(matching_records), "top_stops": matching_records},
        ):
            continue
        sync_machine_fact_gap_event(
            db,
            business_date=business_date,
            intent="machine_stop",
            machine_filter=machine_filter,
            facts={"stop_count": len(matching_records), "top_stops": matching_records},
            trace_id=trace_id,
        )
        resolved += 1
    return resolved


def _base_payload(
    *,
    business_date: date,
    intent: str,
    machine_filter: str | None,
    trace_id: str,
) -> dict[str, Any]:
    machine_label = f"{machine_filter}号机" if machine_filter else "相关机器"
    if intent == "machine_stop":
        query = urlencode(
            {
                "business_date": business_date.isoformat(),
                "entry_fields": "machine_stop_records",
                "owner_role": "overhaul_owner",
                "trace_id": trace_id,
            }
        )
        return {
            "field": "machine_stop_records",
            "intent": intent,
            "machine_filter": machine_filter,
            "entry_route": "/entry/fill",
            "entry_fields": ["machine_stop_records"],
            "fill_strategy": "owner_daily_machine_stop",
            "owner_role": "overhaul_owner",
            "action_route": f"/entry/fill?{query}",
            "next_step": f"请补充{machine_label}的停机时长和原因。",
            "summary": f"{machine_label}缺少可信停机明细",
            "human_action_required": True,
            "automation_status": "waiting_for_owner",
            "notification_policy": "state_change_only_no_repeat",
        }
    query = urlencode({"trace_id": trace_id})
    return {
        "field": "machine_operation_detail",
        "intent": intent,
        "machine_filter": machine_filter,
        "entry_route": "/manage/alerts",
        "entry_fields": [],
        "fill_strategy": "mes_source_recheck",
        "owner_role": "factory_dispatch",
        "action_route": f"/manage/alerts?{query}",
        "next_step": (
            f"复查{machine_label}的 MES 生产起止记录；"
            "该记录不等同于物理通断电。"
        ),
        "summary": f"{machine_label}缺少 MES 生产起止记录",
        "human_action_required": False,
        "automation_status": "rechecking_sources",
        "notification_policy": "state_change_only_no_repeat",
    }


def _has_required_fact(intent: str, facts: Mapping[str, Any]) -> bool:
    fact_status = str(facts.get("fact_status") or "").strip()
    if fact_status:
        return fact_status == "confirmed"
    if intent == "machine_operation":
        return _safe_int(facts.get("record_count")) > 0
    if intent != "machine_stop" or _safe_int(facts.get("stop_count")) <= 0:
        return False
    records = facts.get("top_stops")
    if not isinstance(records, list) or not records:
        return False
    valid_records = [record for record in records if isinstance(record, Mapping)]
    return bool(valid_records) and all(
        str(record.get("downtime_reason") or "").strip() not in {"", "未填写原因"}
        for record in valid_records
    )


def _record_matches_machine(
    record: Mapping[str, Any],
    machine_filter: str | None,
) -> bool:
    if not machine_filter:
        return True
    token = str(machine_filter)
    name = str(record.get("machine_name") or record.get("equipment_name") or "")
    parsed_token = _machine_number(name)
    if parsed_token is not None:
        return parsed_token == token
    code = str(record.get("machine_code") or record.get("equipment_code") or "").strip()
    return code == token or code.endswith(f"-{token}") or code.endswith(f"#{token}")


def _machine_number(value: str) -> str | None:
    match = re.search(
        r"(\d+|[一二三四五六七八九十两]+)\s*(?:#|号)?\s*(?:机|机台|机列)",
        str(value or ""),
    )
    if match is None:
        return None
    raw = match.group(1)
    if raw.isdigit():
        return str(int(raw))
    digits = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if "十" in raw:
        left, right = raw.split("十", 1)
        return str(digits.get(left, 1) * 10 + digits.get(right, 0))
    number = digits.get(raw)
    return str(number) if number is not None else None


def _resolved_summary(intent: str, machine_filter: str | None) -> str:
    machine_label = f"{machine_filter}号机" if machine_filter else "相关机器"
    if intent == "machine_stop":
        return f"{machine_label}停机明细已补齐"
    return f"{machine_label}MES 生产起止记录已恢复"


def _source_ref(business_date: date, intent: str, machine_filter: str | None) -> str:
    machine_key = machine_filter or "all"
    return f"{EVENT_TYPE}:{business_date.isoformat()}:{intent}:{machine_key}"


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
