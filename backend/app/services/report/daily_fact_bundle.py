from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.business_time import local_now
from app.core.redaction import filter_sensitive_mapping
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyFactCorrection
from app.models.system import User
from app.services.hermes_daily_fact_update_service import extract_daily_fact_update_candidates
from app.services.hermes_dingtalk_evidence_service import (
    DingTalkEvidenceItem,
    dingtalk_evidence_adoption_reason,
    query_dingtalk_evidence,
)
from app.services.hermes_day1_harness_service import build_output_skill_alignment, load_output_skill_daily_reference
from app.services.report.daily_fact_evidence_contracts import DailyFactEvidenceVerifier
from app.services.report.daily_report_fact_closure import build_daily_report_fact_closure
from app.services.report.daily_report_gap_analysis import build_daily_report_gap_plan
from app.services.report.output_skill_report_parser import parse_output_skill_daily_report
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
    "datahub_final_daily_report": 88,
    "official_daily_report": 88,
    "historical_report": 40,
    "rag": 30,
    "output_skill": 20,
}
MIN_DINGTALK_DAILY_REPORT_FIELDS = 3
DINGTALK_STRUCTURED_FACT_KEYS = ("fact_updates", "daily_facts", "facts", "extracted_facts", "fields")
DINGTALK_TEXT_KEYS = (
    "recognized_text",
    "recognized",
    "text",
    "content",
    "file_text",
    "parsed_text",
    "ocr_text",
    "extracted_text",
    "attachment_text",
    "message_text",
    "plain_text",
    "summary",
)
DINGTALK_TEXT_CONTAINER_KEYS = (
    "file",
    "files",
    "attachment",
    "attachments",
    "document",
    "documents",
    "workbook",
    "sheet",
    "sheets",
)

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
DIRECT_MES_WMS_SOURCE_TYPES = {
    "finished_inbound_output",
    "mes_verified",
    "wms",
    "wms_direct",
}
def build_daily_fact_bundle(
    db: Session,
    *,
    business_date: date,
    requested_by: User | None = None,
    trace_id: str | None = None,
    persist_run: bool = False,
    snapshot_reason: str | None = None,
    allow_output_skill_reference_adoption: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    effective_now = local_now(now)
    template_facts = template_daily_report.build_template_daily_report_facts(db, target_date=business_date)
    facts_payload = _facts_from_template(
        db,
        template_facts,
        business_date=business_date,
        now=effective_now,
    )
    bundle = _bundle_from_facts(
        business_date=business_date,
        facts_payload=facts_payload,
        template_facts=template_facts,
        trace_id=trace_id,
    )
    reference_only = allow_output_skill_reference_adoption and _should_adopt_output_skill_reference()
    bundle["reference_only"] = reference_only
    bundle = _apply_dingtalk_supplements(db, bundle=bundle, business_date=business_date)
    output_skill_root = _output_skill_root()
    if reference_only:
        bundle = _apply_output_skill_reference(
            bundle,
            output_skill_root=output_skill_root,
            business_date=business_date,
        )
    bundle = _apply_root_owner_corrections(db, bundle=bundle, business_date=business_date)
    rendered_text = _render_bundle_daily_text(bundle)
    bundle["output_skill_alignment"] = build_output_skill_alignment(
        rendered_text,
        output_skill_root,
        business_date,
    )
    bundle["gap_plan"] = build_daily_report_gap_plan(
        missing_fields=bundle.get("missing_fields") or [],
        alignment=bundle.get("output_skill_alignment") or {},
        sources=bundle.get("sources") or {},
    )
    bundle["fact_closure"] = build_daily_report_fact_closure(bundle)
    bundle["real_source_gate_passed"] = (
        not reference_only and bundle["fact_closure"].get("status") == "pass"
    )
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


def _facts_from_template(
    db: Session,
    template_facts: Mapping[str, Any],
    *,
    business_date: date,
    now: datetime,
) -> dict[str, Any]:
    values = dict(template_facts.get("values") or {})
    sources = dict(template_facts.get("sources") or {})
    evidence_verifier = DailyFactEvidenceVerifier(db, business_date=business_date)
    result: dict[str, Any] = {}
    for field_name, value in values.items():
        normalized_field_name = str(field_name)
        source_name, source_detail = _source_from_template(sources.get(field_name))
        unit = FIELD_UNITS.get(normalized_field_name)
        is_direct_source = _is_direct_mes_wms_source(source_name)
        if is_direct_source and source_detail.get("unit") not in (None, ""):
            unit = str(source_detail["unit"])
        fact = _fact_item(
            value=value,
            unit=unit,
            source=source_name,
            source_type=source_name,
            priority=_source_priority(source_name),
            freshness="current_business_day",
            confidence=_source_confidence(source_name),
            adoption_reason=f"来自 {source_name}",
            source_detail=source_detail,
            source_ref={"business_date": business_date.isoformat(), **source_detail},
        )
        if is_direct_source:
            evidence_gaps = _direct_source_evidence_gaps(
                db,
                field_name=normalized_field_name,
                business_date=business_date,
                fact_value=value,
                source_type=source_name,
                source_detail=source_detail,
                now=now,
                verifier=evidence_verifier,
            )
            fact["evidence_status"] = "confirmed" if not evidence_gaps else "needs_evidence"
            fact["evidence_gaps"] = evidence_gaps
        result[normalized_field_name] = fact
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
        "output_skill_refs": [],
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


def _is_direct_mes_wms_source(source_type: str) -> bool:
    return (
        source_type in DIRECT_MES_WMS_SOURCE_TYPES
        or source_type.startswith("mes_")
        or source_type.startswith("wms_")
    )


def _direct_source_evidence_gaps(
    db: Session,
    *,
    field_name: str,
    business_date: date,
    fact_value: Any,
    source_type: str,
    source_detail: Mapping[str, Any],
    now: datetime,
    verifier: DailyFactEvidenceVerifier,
) -> list[str]:
    if verifier.db is not db or verifier.business_date != business_date:
        raise ValueError("daily_fact_evidence_verifier_scope_mismatch")
    gaps: list[str] = []
    source_ref = next(
        (
            source_detail.get(key)
            for key in ("source_ref", "source_table", "projection_table", "adapter")
            if source_detail.get(key) not in (None, "")
        ),
        None,
    )
    if source_ref is None:
        gaps.append("missing_source_ref")
    for key in ("business_window", "unit", "trace_id", "metric_contract_version"):
        if source_detail.get(key) in (None, ""):
            gaps.append(f"missing_{key}")
    window_start: datetime | None = None
    window_end: datetime | None = None
    business_window = str(source_detail.get("business_window") or "")
    if business_window:
        try:
            window_start, window_end = (
                datetime.fromisoformat(item)
                for item in business_window.split("/", 1)
            )
        except (TypeError, ValueError):
            gaps.append("invalid_business_window")
        else:
            if window_start.tzinfo is None or window_end.tzinfo is None or window_end < window_start:
                gaps.append("invalid_business_window")
            elif window_end > now.astimezone(window_end.tzinfo):
                gaps.append("business_window_not_closed")
    row_count = source_detail.get("row_count")
    sync_run_id = source_detail.get("sync_run_id")
    try:
        has_rows = int(row_count or 0) > 0
    except (TypeError, ValueError):
        has_rows = False
    has_projection_read = has_rows and verifier.verify_projection(
        field_name=field_name,
        source_type=source_type,
        fact_value=fact_value,
        source_detail=source_detail,
    )
    has_sync_metadata = any(
        source_detail.get(key) not in (None, "")
        for key in ("sync_run_id", "cursor_key", "sync_trace_id")
    ) or str(source_detail.get("trace_id") or "").startswith("mes-sync-run:")
    has_valid_sync = not has_sync_metadata or verifier.verify_sync(
        field_name=field_name,
        source_type=source_type,
        source_ref=str(source_ref or ""),
        sync_run_id=sync_run_id,
        cursor_key=source_detail.get("cursor_key"),
        trace_id=source_detail.get("sync_trace_id") or source_detail.get("trace_id"),
        window_start=window_start,
        window_end=window_end,
    )
    if not has_projection_read or not has_valid_sync:
        gaps.append("missing_read_evidence")
    return gaps


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
    run_query = db.query(DailyFactBundleRun).filter(DailyFactBundleRun.run_key == run_key)
    run = run_query.with_for_update().one_or_none()
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
            run = run_query.with_for_update().one_or_none()
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
        snapshot_values = {
            "facts": _json_safe(bundle.get("facts") or {}),
            "sources": _json_safe(bundle.get("sources") or {}),
            "conflicts": _json_safe(bundle.get("conflicts") or []),
            "adopted_values": _adopted_values(bundle),
            "correction_refs": _json_safe(bundle.get("correction_refs") or []),
            "dingtalk_refs": _json_safe(bundle.get("dingtalk_refs") or []),
            "output_skill_alignment": _json_safe(bundle.get("output_skill_alignment") or {}),
            "payload_hash": _payload_hash(bundle),
            "created_by_id": getattr(requested_by, "id", None),
            "trace_id": trace_id,
        }
        snapshot_key = (
            f"scheduled_daily_closure:{run.run_key}"
            if snapshot_reason == "scheduled_daily_closure"
            else None
        )
        snapshot = None
        if snapshot_key is not None:
            snapshot = (
                db.query(DailyFactBundleSnapshot)
                .filter(DailyFactBundleSnapshot.snapshot_key == snapshot_key)
                .with_for_update()
                .one_or_none()
            )
        if snapshot is None:
            candidate = DailyFactBundleSnapshot(
                run_id=run.id,
                snapshot_key=snapshot_key,
                business_date=business_date,
                snapshot_reason=snapshot_reason,
                **snapshot_values,
            )
            if snapshot_key is None:
                db.add(candidate)
                snapshot = candidate
            else:
                try:
                    with db.begin_nested():
                        db.add(candidate)
                        db.flush()
                    snapshot = candidate
                except IntegrityError:
                    snapshot = (
                        db.query(DailyFactBundleSnapshot)
                        .filter(DailyFactBundleSnapshot.snapshot_key == snapshot_key)
                        .with_for_update()
                        .one_or_none()
                    )
                    if snapshot is None:
                        raise
        for field_name, value in snapshot_values.items():
            setattr(snapshot, field_name, value)
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


def _apply_output_skill_reference(
    bundle: dict[str, Any],
    *,
    output_skill_root: str | None,
    business_date: date,
) -> dict[str, Any]:
    reference = load_output_skill_daily_reference(output_skill_root, business_date)
    if not reference:
        return bundle

    parsed_values = parse_output_skill_daily_report(str(reference.get("text") or ""))
    if not parsed_values:
        return bundle

    facts = dict(bundle.get("facts") or {})
    conflicts = list(bundle.get("conflicts") or [])
    output_skill_refs = list(bundle.get("output_skill_refs") or [])
    file_name = str(reference.get("file_name") or "")
    business_date_text = business_date.isoformat()
    source_detail = {
        "source": "official_daily_report",
        "source_type": "official_daily_report",
        "reference_kind": "output_skill_daily_report",
        "file_name": file_name,
        "business_date": business_date_text,
    }
    applied_fields: list[str] = []

    ordered_fields = [
        *[field for field in template_daily_report.REQUIRED_FIELDS if field in parsed_values],
        *[field for field in parsed_values if field not in template_daily_report.REQUIRED_FIELDS],
    ]
    for field_name in ordered_fields:
        new_value = parsed_values.get(field_name)
        if not _has_fact_value(new_value):
            continue

        old_fact = facts.get(field_name)
        old_value = old_fact.get("value") if isinstance(old_fact, Mapping) else None
        old_source = None
        old_priority = 0
        old_unit = _field_unit(field_name)
        if isinstance(old_fact, Mapping):
            old_source = old_fact.get("source_type") or old_fact.get("source")
            old_priority = int(old_fact.get("priority") or 0)
            old_unit = old_fact.get("unit") or old_unit

        if old_priority >= SOURCE_PRIORITY["dingtalk_supplement"]:
            if _json_safe(old_value) != _json_safe(new_value):
                conflicts.append(
                    {
                        "field": field_name,
                        "type": "official_daily_report_not_applied",
                        "previous_source": old_source,
                        "previous_value": old_value,
                        "candidate_source": "official_daily_report",
                        "candidate_value": new_value,
                        "file_name": file_name,
                        "reason": "higher_priority_fact_exists",
                    }
                )
            continue

        facts[field_name] = _fact_item(
            value=new_value,
            unit=old_unit,
            source="official_daily_report",
            source_type="official_daily_report",
            priority=_source_priority("official_daily_report"),
            freshness="locked_reference",
            confidence=_source_confidence("official_daily_report"),
            adoption_reason="采用输出skill正式日报参考事实补齐字段对齐门禁",
            source_detail=source_detail,
            source_ref=source_detail,
        )
        applied_fields.append(field_name)

    if not applied_fields:
        bundle["conflicts"] = conflicts
        return _refresh_bundle_metadata(bundle)

    bundle["facts"] = facts
    bundle["conflicts"] = conflicts
    output_skill_refs.append(
        {
            "file_name": file_name,
            "field_count": len(applied_fields),
            "field_names": applied_fields,
        }
    )
    bundle["output_skill_refs"] = output_skill_refs
    _remove_applied_missing_fields(bundle, set(applied_fields))
    return _refresh_bundle_metadata(bundle)


def _apply_dingtalk_supplements(
    db: Session,
    *,
    bundle: dict[str, Any],
    business_date: date,
) -> dict[str, Any]:
    items = query_dingtalk_evidence(
        db,
        business_date=business_date,
        include_outside_business_context=True,
    )
    if not items:
        return bundle

    facts = dict(bundle.get("facts") or {})
    conflicts = list(bundle.get("conflicts") or [])
    dingtalk_refs = list(bundle.get("dingtalk_refs") or [])
    applied_field_names: set[str] = set()

    for item in items:
        payload = dict(item.payload)
        structured_updates = _dingtalk_structured_fact_updates(payload)
        if "fact_updates" in payload and structured_updates is None:
            continue

        has_structured_updates = structured_updates is not None
        if has_structured_updates:
            update_items = _iter_fact_updates(structured_updates)
        else:
            candidates = _dingtalk_daily_report_candidates(item, payload)
            if not candidates:
                candidates = extract_daily_fact_update_candidates(
                    {
                        "id": item.evidence_id,
                        "trace_id": item.trace_id,
                        "recognized_text": item.text,
                        "payload": payload,
                    }
                )
            if not candidates:
                continue
            update_items = [
                (str(candidate.get("field") or "").strip(), candidate)
                for candidate in candidates
                if str(candidate.get("field") or "").strip()
            ]

        if not item.adoptable_as_fact:
            reason = dingtalk_evidence_adoption_reason(item, business_date=business_date)
            for field_name, candidate in update_items:
                if _has_fact_value(candidate.get("value")):
                    _append_unapplied_dingtalk_candidate(
                        conflicts,
                        evidence=item,
                        candidate={**dict(candidate), "field": field_name},
                        reason=reason,
                    )
            continue

        applied_fields: list[str] = []
        for field_name, candidate in update_items:
            old_fact = facts.get(field_name)
            old_value = old_fact.get("value") if isinstance(old_fact, Mapping) else None
            old_source = None
            old_unit = FIELD_UNITS.get(field_name)
            old_priority = 0
            if isinstance(old_fact, Mapping):
                old_source = old_fact.get("source_type") or old_fact.get("source")
                old_unit = old_fact.get("unit") or old_unit
                old_priority = int(old_fact.get("priority") or 0)

            new_value = candidate.get("value")
            if not _has_fact_value(new_value):
                continue
            new_unit = candidate.get("unit") or old_unit
            reason = str(candidate.get("reason") or "钉钉补充事实")
            new_priority = SOURCE_PRIORITY["dingtalk_supplement"]
            if old_priority > new_priority:
                _append_unapplied_dingtalk_candidate(
                    conflicts,
                    evidence=item,
                    candidate={**dict(candidate), "field": field_name},
                    reason="higher_priority_fact_exists",
                )
                continue
            if old_priority == new_priority:
                if _json_safe(old_value) != _json_safe(new_value):
                    _append_unapplied_dingtalk_candidate(
                        conflicts,
                        evidence=item,
                        candidate={**dict(candidate), "field": field_name},
                        reason="same_priority_fact_exists",
                    )
                continue

            source_detail = {
                "source": "dingtalk_supplement",
                "evidence_id": item.evidence_id,
                "source_user_id": item.source_user_id,
                "file_uri": item.file_uri,
                "evidence_type": item.evidence_type,
                "source_key": item.source_key,
                "recognized_text": candidate.get("raw_text") or _dingtalk_evidence_text(item, payload),
                "business_date": business_date.isoformat(),
            }
            field_source_ref = candidate.get("source_ref")
            if isinstance(field_source_ref, Mapping):
                source_detail["field_source_ref"] = _json_safe(field_source_ref)
            trace_id = str(candidate.get("trace_id") or item.trace_id or "").strip()
            if trace_id:
                source_detail["trace_id"] = trace_id
            facts[field_name] = _fact_item(
                value=new_value,
                unit=new_unit,
                source="dingtalk_supplement",
                source_type="dingtalk_supplement",
                priority=new_priority,
                freshness="supplemented",
                confidence=0.95 if has_structured_updates else _candidate_confidence(candidate),
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
            dingtalk_refs.append({"id": item.evidence_id, "field_names": applied_fields})

    bundle["facts"] = facts
    bundle["conflicts"] = conflicts
    bundle["dingtalk_refs"] = dingtalk_refs
    if applied_field_names:
        _remove_applied_missing_fields(bundle, applied_field_names)
    return _refresh_bundle_metadata(bundle)


def _dingtalk_structured_fact_updates(payload: Mapping[str, Any]) -> Any | None:
    for key in DINGTALK_STRUCTURED_FACT_KEYS:
        if key not in payload:
            continue
        value = payload.get(key)
        if _iter_fact_updates(value):
            return value
    return None


def _dingtalk_daily_report_candidates(
    evidence: DingTalkEvidenceItem,
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    raw_text = _dingtalk_evidence_text(evidence, payload)
    parsed_values = parse_output_skill_daily_report(raw_text)
    candidates = [
        {
            "field": str(field_name),
            "value": value,
            "unit": _field_unit(str(field_name)),
            "confidence": 0.95,
            "source": "dingtalk_supplement",
            "trace_id": str(evidence.trace_id or ""),
            "raw_text": raw_text,
            "reason": "钉钉日报正文解析",
        }
        for field_name, value in parsed_values.items()
        if field_name != "report_date" and _has_fact_value(value)
    ]
    if len(candidates) < MIN_DINGTALK_DAILY_REPORT_FIELDS:
        return []
    return candidates


def _dingtalk_evidence_text(evidence: DingTalkEvidenceItem, payload: Mapping[str, Any]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    _append_dingtalk_text_part(evidence.text, parts=parts, seen=seen)
    _collect_dingtalk_payload_text(payload, parts=parts, seen=seen)
    return "\n".join(parts)


def _collect_dingtalk_payload_text(
    value: Any,
    *,
    parts: list[str],
    seen: set[str],
    depth: int = 0,
) -> None:
    if depth > 4:
        return
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key or "").strip().lower()
            if key in DINGTALK_TEXT_KEYS or key.endswith("_text"):
                _append_dingtalk_text_part(item, parts=parts, seen=seen)
        for key in DINGTALK_TEXT_CONTAINER_KEYS:
            if key in value:
                _collect_dingtalk_payload_text(value.get(key), parts=parts, seen=seen, depth=depth + 1)
        return
    if isinstance(value, list):
        for item in value:
            _collect_dingtalk_payload_text(item, parts=parts, seen=seen, depth=depth + 1)


def _append_dingtalk_text_part(value: Any, *, parts: list[str], seen: set[str]) -> None:
    if not isinstance(value, str):
        return
    text = value.strip()
    if text and text not in seen:
        parts.append(text)
        seen.add(text)


def _append_unapplied_dingtalk_candidate(
    conflicts: list[Any],
    *,
    evidence: DingTalkEvidenceItem,
    candidate: Mapping[str, Any],
    reason: str = "payload_business_date_missing_or_mismatch",
) -> None:
    field_name = str(candidate.get("field") or "").strip()
    if not field_name:
        return
    conflicts.append(
        {
            "field": field_name,
            "type": "dingtalk_candidate_not_applied",
            "candidate_value": candidate.get("value"),
            "reason": reason,
            "trace_id": candidate.get("trace_id") or evidence.trace_id or "",
            "evidence_id": evidence.evidence_id,
        }
    )


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
        "output_skill_refs": _json_safe(bundle.get("output_skill_refs") or []),
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


def _should_adopt_output_skill_reference() -> bool:
    return str(os.getenv("OUTPUT_SKILL_REFERENCE_MODE") or "").strip().lower() == "adopt"


def _field_unit(field_name: str) -> str | None:
    return FIELD_UNITS.get(field_name) or template_daily_report._fact_unit(field_name)


def _source_from_template(source: Any) -> tuple[str, Mapping[str, Any]]:
    if isinstance(source, Mapping):
        safe_value = _json_safe(source)
        safe_source = dict(safe_value) if isinstance(safe_value, Mapping) else {}
        source_name = str(safe_source.get("source_type") or safe_source.get("source") or "computed")
        return source_name, safe_source
    source_name = str(source or "computed")
    return source_name, {"source": source_name}
