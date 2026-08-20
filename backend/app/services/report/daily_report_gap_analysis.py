from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any
from urllib.parse import urlencode

from app.domain.daily_report_field_contract import daily_report_gap_action_for


def classify_daily_report_field_gap(field_name: str) -> dict[str, Any]:
    action = daily_report_gap_action_for(field_name)
    entry_fields = list(action.entry_fields)
    return {
        "field": action.field,
        "group": action.group,
        "source_lane": action.source_lane,
        "entry_route": action.entry_route,
        "fill_strategy": action.fill_strategy,
        "owner_role": action.owner_role,
        "deadline": action.deadline,
        "entry_fields": entry_fields,
        "entry_field": entry_fields[0] if entry_fields else None,
        "entry_workshop_types": list(action.entry_workshop_types),
        "next_step": action.next_step,
    }


def build_daily_report_gap_action_route(
    *,
    business_date: date,
    field: str,
    trace_id: str | None,
    action: Mapping[str, Any],
) -> str:
    normalized_trace_id = str(trace_id or "").strip()
    if str(action.get("entry_route") or "") != "/entry/fill":
        if not normalized_trace_id:
            return "/manage/alerts"
        return f"/manage/alerts?{urlencode({'trace_id': normalized_trace_id})}"

    entry_fields = [
        str(value).strip()
        for value in action.get("entry_fields") or []
        if str(value).strip()
    ]
    params = {
        "business_date": business_date.isoformat(),
        "field": str(field),
    }
    if entry_fields:
        params["entry_fields"] = ",".join(entry_fields)
        params["entry_field"] = entry_fields[0]
    owner_role = str(action.get("owner_role") or "").strip()
    if owner_role:
        params["owner_role"] = owner_role
    if normalized_trace_id:
        params["trace_id"] = normalized_trace_id
    return f"/entry/fill?{urlencode(params)}"


def build_daily_report_gap_plan(
    *,
    missing_fields: Sequence[str] | None = None,
    alignment: Mapping[str, Any] | None = None,
    sources: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    source_map = sources or {}

    for field_name in missing_fields or []:
        field = str(field_name)
        seen.add(field)
        items.append(
            _gap_item(
                field,
                problem_type="missing_field",
                actual=None,
                expected=None,
                source=source_map.get(field),
            )
        )

    for difference in _alignment_differences(alignment):
        field = str(difference.get("field") or "")
        if not field or field in seen:
            continue
        seen.add(field)
        items.append(
            _gap_item(
                field,
                problem_type="alignment_difference",
                actual=difference.get("actual"),
                expected=difference.get("expected"),
                source=source_map.get(field),
            )
        )

    group_counts = Counter(str(item["group"]) for item in items)
    lane_counts = Counter(str(item["source_lane"]) for item in items)
    return {
        "status": "needs_action" if items else "ready",
        "item_count": len(items),
        "summary": {
            "by_group": dict(sorted(group_counts.items())),
            "by_source_lane": dict(sorted(lane_counts.items())),
        },
        "items": items,
    }


def _alignment_differences(alignment: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not alignment:
        return []
    raw = alignment.get("differences")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _gap_item(
    field_name: str,
    *,
    problem_type: str,
    actual: Any,
    expected: Any,
    source: Any,
) -> dict[str, Any]:
    action = classify_daily_report_field_gap(field_name)
    current_source = source.get("source_type") or source.get("source") if isinstance(source, Mapping) else None
    return {
        **action,
        "problem_type": problem_type,
        "actual": actual,
        "expected": expected,
        "current_source": current_source,
        "blocking": True,
    }
