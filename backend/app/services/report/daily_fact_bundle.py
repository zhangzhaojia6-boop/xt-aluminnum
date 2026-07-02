from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
import re
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.redaction import filter_sensitive_mapping
from app.models.agent_communication import MultimodalEvidence
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyFactCorrection
from app.models.system import User
from app.services.hermes_daily_fact_update_service import extract_daily_fact_update_candidates
from app.services.hermes_day1_harness_service import build_output_skill_alignment
from app.services.report.daily_report_fact_closure import build_daily_report_fact_closure
from app.services.report.daily_report_gap_analysis import build_daily_report_gap_plan
from app.services.report import template_daily_report


SOURCE_PRIORITY = {
    "root_owner_correction": 100,
    "dingtalk_supplement": 90,
    "mes_wms": 80,
    "mes_packaging_output": 80,
    "mes_wip_distribution": 80,
    "mes_workshop_process_records": 80,
    "wms": 80,
    "finished_inbound_output": 80,
    "owner_or_energy_summary": 70,
    "manual_mobile_coil": 70,
    "owner_daily": 70,
    "manual": 70,
    "recovery_daily": 70,
    "overhaul_daily": 70,
    "computed": 60,
    "energy_cost": 60,
    "contract_projection": 60,
    "yield_projection": 60,
    "historical_report": 40,
    "rag": 30,
    "output_skill": 20,
}

FIELD_UNITS = {
    "total_output_daily": "吨",
    "finished_inbound_daily": "吨",
    "wip_total": "吨",
    "total_output_month": "吨",
    "total_electricity_kwh": "度",
    "total_gas_m3": "m³",
    "daily_yield_rate": "%",
    "monthly_yield_rate": "%",
    "verified_cost_total": "万元",
    "cost_per_ton": "元/吨",
}


def build_daily_fact_bundle(
    db: Session,
    *,
    business_date: date,
    requested_by: User | None = None,
    trace_id: str | None = None,
    persist_run: bool = False,
    snapshot_reason: str | None = None,
) -> dict[str, Any]:
    template_facts = template_daily_report.build_template_daily_report_facts(db, target_date=business_date)
    facts_payload = _facts_from_template(template_facts, business_date=business_date)
    bundle = _bundle_from_facts(
        business_date=business_date,
        facts_payload=facts_payload,
        template_facts=template_facts,
        trace_id=trace_id,
    )
    bundle = _apply_dingtalk_supplements(db, bundle=bundle, business_date=business_date)
    bundle = _apply_root_owner_corrections(db, bundle=bundle, business_date=business_date)
    rendered_text = _render_bundle_daily_text(bundle)
    bundle["output_skill_alignment"] = build_output_skill_alignment(
        rendered_text,
        _output_skill_root(),
        business_date,
    )
    bundle["gap_plan"] = build_daily_report_gap_plan(
        missing_fields=bundle.get("missing_fields") or [],
        alignment=bundle.get("output_skill_alignment") or {},
        sources=bundle.get("sources") or {},
    )
    bundle["fact_closure"] = build_daily_report_fact_closure(bundle)
    if persist_run or snapshot_reason:
        _persist_bundle(
            db,
            bundle=bundle,
            business_date=business_date,
            requested_by=requested_by,
            trace_id=trace_id,
            snapshot_reason=snapshot_reason,
        )
    return bundle


def persist_daily_fact_bundle_snapshot(
    db: Session,
    *,
    bundle: Mapping[str, Any],
    business_date: date,
    requested_by: User | None = None,
    trace_id: str | None = None,
    snapshot_reason: str,
) -> tuple[DailyFactBundleRun, DailyFactBundleSnapshot]:
    run, snapshot = _persist_bundle(
        db,
        bundle=_refresh_bundle_metadata(dict(bundle)),
        business_date=business_date,
        requested_by=requested_by,
        trace_id=trace_id,
        snapshot_reason=snapshot_reason,
    )
    if snapshot is None:
        raise ValueError("snapshot_reason_required")
    return run, snapshot


def _facts_from_template(template_facts: Mapping[str, Any], *, business_date: date) -> dict[str, Any]:
    values = dict(template_facts.get("values") or {})
    sources = dict(template_facts.get("sources") or {})
    result: dict[str, Any] = {}
    for field_name, value in values.items():
        source_name, source_detail = _source_from_template(sources.get(field_name))
        result[str(field_name)] = _fact_item(
            value=value,
            unit=FIELD_UNITS.get(str(field_name)),
            source=source_name,
            source_type=source_name,
            priority=_source_priority(source_name),
            freshness="current_business_day",
            confidence=_source_confidence(source_name),
            adoption_reason=f"来自 {source_name}",
            source_detail=source_detail,
            source_ref={"business_date": business_date.isoformat(), **source_detail},
        )
    return result


def _bundle_from_facts(
    *,
    business_date: date,
    facts_payload: dict[str, Any],
    template_facts: Mapping[str, Any],
    trace_id: str | None,
) -> dict[str, Any]:
    missing = [str(item) for item in template_facts.get("missing_fields") or []]
    conflicts = [_json_safe(item) for item in template_facts.get("conflicts") or []]
    bundle = {
        "business_date": business_date.isoformat(),
        "status": str(template_facts.get("status") or "ready"),
        "facts": facts_payload,
        "sources": {},
        "missing_fields": missing,
        "missing": missing,
        "conflicts": conflicts,
        "freshness": {},
        "confidence": None,
        "correction_refs": [],
        "dingtalk_refs": [],
        "output_skill_alignment": {},
        "gap_plan": {},
        "trace_id": trace_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return _refresh_bundle_metadata(bundle)


def _fact_item(
    *,
    value: Any,
    unit: str | None,
    source: str,
    source_type: str,
    priority: int,
    freshness: str,
    confidence: float,
    adoption_reason: str,
    source_detail: Mapping[str, Any],
    source_ref: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "value": _json_safe(value),
        "unit": unit,
        "source": source,
        "source_type": source_type,
        "priority": priority,
        "freshness": freshness,
        "confidence": confidence,
        "adoption_reason": adoption_reason,
        "source_detail": _json_safe(source_detail),
        "source_ref": _json_safe(source_ref),
    }


def _source_priority(source: str) -> int:
    source_key = str(source or "")
    if source_key.startswith("mes_") or source_key.startswith("wms_"):
        return 80
    return SOURCE_PRIORITY.get(source_key, SOURCE_PRIORITY.get(source_key.split(":")[0], 50))


def _source_confidence(source: str) -> float:
    priority = _source_priority(source)
    if priority >= 100:
        return 1.0
    if priority >= 90:
        return 0.95
    if priority >= 80:
        return 0.85
    if priority >= 70:
        return 0.75
    if priority >= 60:
        return 0.65
    return 0.5


def _persist_bundle(
    db: Session,
    *,
    bundle: dict[str, Any],
    business_date: date,
    requested_by: User | None,
    trace_id: str | None,
    snapshot_reason: str | None,
) -> tuple[DailyFactBundleRun, DailyFactBundleSnapshot | None]:
    run_key = _run_key(business_date=business_date, trace_id=trace_id)
    run = db.query(DailyFactBundleRun).filter(DailyFactBundleRun.run_key == run_key).one_or_none()
    if run is None:
        try:
            with db.begin_nested():
                run = DailyFactBundleRun(
                    run_key=run_key,
                    business_date=business_date,
                    requested_by_id=getattr(requested_by, "id", None),
                    trace_id=trace_id,
                )
                db.add(run)
                db.flush()
        except IntegrityError:
            run = db.query(DailyFactBundleRun).filter(DailyFactBundleRun.run_key == run_key).one_or_none()
            if run is None:
                raise
    run.status = str(bundle.get("status") or "partial")
    run.source_status = {"sources": _json_safe(bundle.get("sources") or {})}
    run.missing_count = len(bundle.get("missing") or [])
    run.conflict_count = len(bundle.get("conflicts") or [])
    run.confidence = _confidence_percent(bundle.get("confidence"))
    db.flush()

    snapshot = None
    if snapshot_reason is not None:
        snapshot = DailyFactBundleSnapshot(
            run_id=run.id,
            business_date=business_date,
            snapshot_reason=snapshot_reason,
            facts=_json_safe(bundle.get("facts") or {}),
            sources=_json_safe(bundle.get("sources") or {}),
            conflicts=_json_safe(bundle.get("conflicts") or []),
            adopted_values=_adopted_values(bundle),
            correction_refs=_json_safe(bundle.get("correction_refs") or []),
            dingtalk_refs=_json_safe(bundle.get("dingtalk_refs") or []),
            output_skill_alignment=_json_safe(bundle.get("output_skill_alignment") or {}),
            payload_hash=_payload_hash(bundle),
            created_by_id=getattr(requested_by, "id", None),
            trace_id=trace_id,
        )
        db.add(snapshot)
        db.flush()
    return run, snapshot


def _apply_root_owner_corrections(
    db: Session,
    *,
    bundle: dict[str, Any],
    business_date: date,
) -> dict[str, Any]:
    corrections = (
        db.query(DailyFactCorrection)
        .filter(DailyFactCorrection.business_date == business_date)
        .filter(DailyFactCorrection.status == "active")
        .order_by(DailyFactCorrection.created_at.asc(), DailyFactCorrection.id.asc())
        .all()
    )
    if not corrections:
        return bundle

    facts = dict(bundle.get("facts") or {})
    conflicts = list(bundle.get("conflicts") or [])
    correction_refs = list(bundle.get("correction_refs") or [])

    for row in corrections:
        field_name = str(row.field_name)
        old_fact = facts.get(field_name)
        old_value = old_fact.get("value") if isinstance(old_fact, Mapping) else None
        old_source = None
        old_unit = None
        if isinstance(old_fact, Mapping):
            old_source = old_fact.get("source_type") or old_fact.get("source")
            old_unit = old_fact.get("unit")

        new_value = None
        if isinstance(row.value_payload, Mapping):
            new_value = row.value_payload.get("value")
        new_unit = row.unit or old_unit
        source_detail = {
            "source": "root_owner_correction",
            "correction_id": row.id,
            "actor_user_id": row.actor_user_id,
            "trace_id": row.trace_id,
            "source_text": row.source_text,
            "business_date": business_date,
        }
        facts[field_name] = _fact_item(
            value=new_value,
            unit=new_unit,
            source="root_owner_correction",
            source_type="root_owner_correction",
            priority=100,
            freshness="confirmed",
            confidence=1.0,
            adoption_reason=row.reason,
            source_detail=source_detail,
            source_ref=source_detail,
        )
        correction_refs.append(
            {
                "id": row.id,
                "field_name": field_name,
                "trace_id": row.trace_id,
            }
        )
        if old_value != new_value:
            conflicts.append(
                {
                    "field": field_name,
                    "type": "root_owner_correction",
                    "adopted_source": "root_owner_correction",
                    "previous_source": old_source,
                    "previous_value": old_value,
                    "adopted_value": new_value,
                    "reason": row.reason,
                }
            )

    bundle["facts"] = facts
    bundle["conflicts"] = conflicts
    bundle["correction_refs"] = correction_refs
    return _refresh_bundle_metadata(bundle)


def _apply_dingtalk_supplements(
    db: Session,
    *,
    bundle: dict[str, Any],
    business_date: date,
) -> dict[str, Any]:
    rows = (
        db.query(MultimodalEvidence)
        .filter(MultimodalEvidence.payload.is_not(None))
        .filter(MultimodalEvidence.confirmation_status == "confirmed")
        .order_by(MultimodalEvidence.created_at.asc(), MultimodalEvidence.id.asc())
        .all()
    )
    if not rows:
        return bundle

    facts = dict(bundle.get("facts") or {})
    conflicts = list(bundle.get("conflicts") or [])
    dingtalk_refs = list(bundle.get("dingtalk_refs") or [])
    business_date_text = business_date.isoformat()
    applied_field_names: set[str] = set()

    for row in rows:
        payload = row.payload if isinstance(row.payload, Mapping) else {}
        if payload.get("include_in_daily_sample") is not True:
            continue
        if str(payload.get("evidence_kind") or "") != "fact":
            continue

        has_structured_updates = "fact_updates" in payload
        if has_structured_updates:
            update_items = _iter_fact_updates(payload.get("fact_updates"))
            if not _payload_business_date_matches(payload, business_date_text):
                for field_name, item in update_items:
                    if _has_fact_value(item.get("value")):
                        _append_unapplied_dingtalk_candidate(
                            conflicts,
                            row=row,
                            candidate={
                                "field": field_name,
                                "value": item.get("value"),
                                "trace_id": _payload_trace_id(payload, row),
                            },
                        )
                continue
        else:
            candidates = extract_daily_fact_update_candidates(
                {
                    "id": row.id,
                    "recognized_text": row.recognized_text,
                    "payload": payload,
                }
            )
            if not candidates:
                continue
            if not _candidate_business_date_matches(
                payload,
                row=row,
                candidates=candidates,
                business_date=business_date,
            ):
                for candidate in candidates:
                    _append_unapplied_dingtalk_candidate(conflicts, row=row, candidate=candidate)
                continue
            update_items = [
                (str(candidate.get("field") or "").strip(), candidate)
                for candidate in candidates
                if str(candidate.get("field") or "").strip()
            ]

        applied_fields: list[str] = []
        for field_name, item in update_items:
            old_fact = facts.get(field_name)
            old_value = old_fact.get("value") if isinstance(old_fact, Mapping) else None
            old_source = None
            old_unit = FIELD_UNITS.get(field_name)
            if isinstance(old_fact, Mapping):
                old_source = old_fact.get("source_type") or old_fact.get("source")
                old_unit = old_fact.get("unit") or old_unit

            new_value = item.get("value")
            if not _has_fact_value(new_value):
                continue
            new_unit = item.get("unit") or old_unit
            reason = str(item.get("reason") or "钉钉补充事实")
            source_detail = {
                "source": "dingtalk_supplement",
                "evidence_id": row.id,
                "source_user_id": row.source_user_id,
                "file_uri": row.file_uri,
                "evidence_type": row.evidence_type,
                "recognized_text": row.recognized_text,
                "business_date": business_date_text,
            }
            if not has_structured_updates:
                source_detail["recognized_text"] = item.get("raw_text") or row.recognized_text
                trace_id = item.get("trace_id")
                if trace_id:
                    source_detail["trace_id"] = trace_id
            else:
                trace_id = item.get("trace_id") or _payload_explicit_trace_id(payload)
                if trace_id:
                    source_detail["trace_id"] = trace_id
            facts[field_name] = _fact_item(
                value=new_value,
                unit=new_unit,
                source="dingtalk_supplement",
                source_type="dingtalk_supplement",
                priority=90,
                freshness="supplemented",
                confidence=0.95 if has_structured_updates else _candidate_confidence(item),
                adoption_reason=reason,
                source_detail=source_detail,
                source_ref=source_detail,
            )
            applied_fields.append(field_name)
            applied_field_names.add(field_name)
            if old_value != new_value:
                conflicts.append(
                    {
                        "field": field_name,
                        "type": "dingtalk_supplement",
                        "previous_source": old_source,
                        "previous_value": old_value,
                        "adopted_source": "dingtalk_supplement",
                        "adopted_value": new_value,
                        "reason": reason,
                    }
                )

        if applied_fields:
            dingtalk_refs.append({"id": row.id, "field_names": applied_fields})

    bundle["facts"] = facts
    bundle["conflicts"] = conflicts
    bundle["dingtalk_refs"] = dingtalk_refs
    if applied_field_names:
        _remove_applied_missing_fields(bundle, applied_field_names)
    return _refresh_bundle_metadata(bundle)


def _payload_business_date_matches(payload: Mapping[str, Any], business_date_text: str) -> bool:
    for key in ("business_date", "target_date", "date"):
        if str(payload.get(key) or "") == business_date_text:
            return True
    return False


def _candidate_business_date_matches(
    payload: Mapping[str, Any],
    *,
    row: MultimodalEvidence,
    candidates: list[Mapping[str, Any]],
    business_date: date,
) -> bool:
    business_date_text = business_date.isoformat()
    if _payload_business_date_matches(payload, business_date_text):
        return True
    if _payload_has_business_date(payload):
        return False
    raw_text = " ".join(
        str(text or "")
        for text in [
            row.recognized_text,
            *(candidate.get("raw_text") for candidate in candidates),
        ]
    )
    return _recognized_text_matches_business_date(raw_text, business_date)


def _payload_has_business_date(payload: Mapping[str, Any]) -> bool:
    return any(payload.get(key) not in (None, "") for key in ("business_date", "target_date", "date"))


def _recognized_text_matches_business_date(text: str, business_date: date) -> bool:
    clean = str(text or "")
    if "今日" in clean or "今天" in clean:
        return True
    month = business_date.month
    day = business_date.day
    month_day_patterns = (
        rf"(?<!\d)0?{month}\s*月\s*0?{day}\s*日",
        rf"{business_date.year}\s*年\s*0?{month}\s*月\s*0?{day}\s*日",
        re.escape(business_date.isoformat()),
    )
    return any(re.search(pattern, clean) for pattern in month_day_patterns)


def _append_unapplied_dingtalk_candidate(
    conflicts: list[Any],
    *,
    row: MultimodalEvidence,
    candidate: Mapping[str, Any],
) -> None:
    field_name = str(candidate.get("field") or "").strip()
    if not field_name:
        return
    conflicts.append(
        {
            "field": field_name,
            "type": "dingtalk_candidate_not_applied",
            "candidate_value": candidate.get("value"),
            "reason": "payload_business_date_missing_or_mismatch",
            "trace_id": candidate.get("trace_id") or "",
            "evidence_id": row.id,
        }
    )


def _payload_trace_id(payload: Mapping[str, Any], row: MultimodalEvidence) -> str:
    trace_id = _payload_explicit_trace_id(payload)
    if trace_id:
        return trace_id
    return str(row.id or "")


def _payload_explicit_trace_id(payload: Mapping[str, Any]) -> str:
    for key in ("trace_id", "id"):
        value = payload.get(key)
        if value is not None and value != "":
            return str(value)
    return ""


def _candidate_confidence(candidate: Mapping[str, Any]) -> float:
    try:
        return float(candidate.get("confidence"))
    except (TypeError, ValueError):
        return 0.95


def _remove_applied_missing_fields(bundle: dict[str, Any], applied_fields: set[str]) -> None:
    missing_fields = [field for field in bundle.get("missing_fields") or [] if field not in applied_fields]
    missing = [field for field in bundle.get("missing") or [] if field not in applied_fields]
    bundle["missing_fields"] = missing_fields
    bundle["missing"] = missing


def _has_fact_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def _iter_fact_updates(fact_updates: Any) -> list[tuple[str, Mapping[str, Any]]]:
    if isinstance(fact_updates, Mapping):
        if "field" in fact_updates or "field_name" in fact_updates:
            field_name = str(fact_updates.get("field") or fact_updates.get("field_name") or "").strip()
            return [(field_name, fact_updates)] if field_name else []
        updates: list[tuple[str, Mapping[str, Any]]] = []
        for raw_field_name, item in fact_updates.items():
            if not isinstance(item, Mapping):
                continue
            if "field" in item or "field_name" in item:
                field_name = str(item.get("field") or item.get("field_name") or "").strip()
            else:
                field_name = str(raw_field_name or "").strip()
            if field_name:
                updates.append((field_name, item))
        return updates
    if isinstance(fact_updates, list):
        updates = []
        for item in fact_updates:
            if not isinstance(item, Mapping):
                continue
            field_name = str(item.get("field") or item.get("field_name") or "").strip()
            if field_name:
                updates.append((field_name, item))
        return updates
    return []


def _confidence_percent(value: Any) -> int | None:
    if value is None:
        return None
    return int(round(float(value) * 100))


def _adopted_values(bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: item.get("value")
        for key, item in dict(bundle.get("facts") or {}).items()
        if isinstance(item, Mapping)
    }


def _refresh_bundle_metadata(bundle: dict[str, Any]) -> dict[str, Any]:
    facts = dict(bundle.get("facts") or {})
    sources: dict[str, Any] = {}
    freshness: dict[str, Any] = {}
    confidence_values: list[float] = []
    for field_name, fact in facts.items():
        if not isinstance(fact, Mapping):
            continue
        source_detail = fact.get("source_detail")
        if isinstance(source_detail, Mapping):
            sources[str(field_name)] = _json_safe(source_detail)
        else:
            source = fact.get("source_type") or fact.get("source") or "unknown"
            sources[str(field_name)] = {"source": _json_safe(source)}
        freshness[str(field_name)] = _json_safe(fact.get("freshness"))
        confidence = fact.get("confidence")
        if isinstance(confidence, (int, float)):
            confidence_values.append(float(confidence))

    missing_source = bundle["missing_fields"] if "missing_fields" in bundle else bundle.get("missing") or []
    missing = [str(item) for item in missing_source]
    conflicts = [_json_safe(item) for item in bundle.get("conflicts") or []]
    if missing:
        status = "blocked"
    elif any(_conflict_blocks_ready(item) for item in conflicts):
        status = "partial"
    else:
        current_status = str(bundle.get("status") or "")
        status = current_status if current_status and current_status not in {"blocked", "partial"} else "ready"

    bundle["sources"] = sources
    bundle["freshness"] = freshness
    bundle["confidence"] = round(sum(confidence_values) / len(confidence_values), 4) if confidence_values else None
    bundle["missing_fields"] = missing
    bundle["missing"] = missing
    bundle["conflicts"] = conflicts
    bundle["status"] = status
    return bundle


def _conflict_blocks_ready(conflict: Any) -> bool:
    if not isinstance(conflict, Mapping):
        return True
    conflict_type = str(conflict.get("type") or "").strip()
    if conflict_type in {"root_owner_correction", "dingtalk_supplement", "dingtalk_candidate_not_applied"}:
        return False
    if conflict_type == "source_error":
        return True
    status = str(conflict.get("status") or "").strip().lower()
    if status and status not in {"matched", "match", "same", "equal", "ok", "ready", "passed"}:
        return True
    return conflict_type not in {"", "adopted_override"}


def _run_key(*, business_date: date, trace_id: str | None) -> str:
    raw = f"{business_date.isoformat()}:{trace_id or 'manual'}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _payload_hash(bundle: Mapping[str, Any]) -> str:
    payload = {
        "facts": _json_safe(bundle.get("facts") or {}),
        "sources": _json_safe(bundle.get("sources") or {}),
        "conflicts": _json_safe(bundle.get("conflicts") or []),
        "adopted_values": _json_safe(_adopted_values(bundle)),
        "correction_refs": _json_safe(bundle.get("correction_refs") or []),
        "dingtalk_refs": _json_safe(bundle.get("dingtalk_refs") or []),
        "output_skill_alignment": _json_safe(bundle.get("output_skill_alignment") or {}),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized = filter_sensitive_mapping(value)
        return {str(key): _json_safe(item) for key, item in sanitized.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _render_bundle_daily_text(bundle: Mapping[str, Any]) -> str:
    try:
        facts = dict(bundle.get("facts") or {})
        values = {
            str(field_name): fact.get("value")
            for field_name, fact in facts.items()
            if isinstance(fact, Mapping)
        }
        return template_daily_report.render_template_daily_report({"values": values})
    except Exception:
        return ""


def _output_skill_root() -> str | None:
    return os.getenv("OUTPUT_SKILL_ROOT") or os.getenv("OUTPUT_SKILL_REFERENCE_ROOT")


def _source_from_template(source: Any) -> tuple[str, Mapping[str, Any]]:
    if isinstance(source, Mapping):
        safe_value = _json_safe(source)
        safe_source = dict(safe_value) if isinstance(safe_value, Mapping) else {}
        source_name = str(safe_source.get("source_type") or safe_source.get("source") or "computed")
        return source_name, safe_source
    source_name = str(source or "computed")
    return source_name, {"source": source_name}
