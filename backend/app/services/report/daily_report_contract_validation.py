from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from app.core import templates as template_module
from app.domain import daily_report_field_contract as contract_module
from app.services.report import template_daily_field_contract


EXPECTED_FIELD_COUNT = contract_module.DAILY_REPORT_NORMATIVE_FIELD_COUNT
MAXIMUM_TOLERANCE = 20.0
EXPECTED_BUSINESS_TIME_STARTS = {
    contract_module.BUSINESS_TIME_STANDARD: "07:50",
    contract_module.BUSINESS_TIME_BILLET: "10:00",
}
EXPECTED_OWNER_DAILY_SUBMISSION_TIME = "09:30"
EXPECTED_OWNER_DAILY_LATE_TIME = "10:00"
EXPECTED_SOURCE_ORDER = tuple(contract_module.FACT_SOURCE_LANE_ORDER)
ENTRY_FILL_ROUTE = "/entry/fill"
_TEMPLATE_WRITABLE_SECTIONS = ("entry_fields", "shift_fields", "extra_fields", "qc_fields")
_OWNER_FIELD_GROUPS = {
    "utility_owner_fields": template_module.UTILITY_OWNER_FIELDS,
    "shipment_outflow_owner_fields": template_module.SHIPMENT_OUTFLOW_OWNER_FIELDS,
    "recovery_owner_fields": template_module.RECOVERY_OWNER_FIELDS,
    "overhaul_owner_fields": template_module.OVERHAUL_OWNER_FIELDS,
    "inventory_owner_fields": template_module.INVENTORY_OWNER_FIELDS,
    "qc_owner_fields": template_module.QC_OWNER_FIELDS,
    "contract_owner_fields": template_module.CONTRACT_OWNER_FIELDS,
    "contract_progress_fields": template_module.CONTRACT_PROGRESS_FIELDS,
}


def _normalize_writable_template_fields(
    writable_template_fields: Mapping[str, Sequence[str]] | Sequence[str],
) -> dict[str, tuple[str, ...]]:
    if isinstance(writable_template_fields, Mapping):
        normalized: dict[str, tuple[str, ...]] = {}
        for field_name, sources in writable_template_fields.items():
            name = str(field_name or "").strip()
            if not name:
                continue
            if isinstance(sources, Sequence) and not isinstance(sources, str):
                normalized[name] = tuple(sorted(str(item) for item in sources if str(item).strip()))
            else:
                normalized[name] = ()
        return normalized
    return {
        str(field_name): ()
        for field_name in writable_template_fields
        if str(field_name or "").strip()
    }


def collect_writable_template_fields(
    *,
    template_definitions: Mapping[str, Mapping[str, Any]] | None = None,
    owner_field_groups: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> dict[str, tuple[str, ...]]:
    selected_templates = (
        template_module.DEFAULT_WORKSHOP_TEMPLATES
        if template_definitions is None
        else template_definitions
    )
    selected_owner_groups = _OWNER_FIELD_GROUPS if owner_field_groups is None else owner_field_groups
    sources: dict[str, set[str]] = {}

    def add_field(field: Mapping[str, Any], source: str) -> None:
        name = str(field.get("name") or "").strip()
        if not name:
            return
        sources.setdefault(name, set()).add(source)

    for template_key, template in selected_templates.items():
        for section_name in _TEMPLATE_WRITABLE_SECTIONS:
            for field in template.get(section_name, ()) or ():
                if isinstance(field, Mapping):
                    add_field(
                        field,
                        f"DEFAULT_WORKSHOP_TEMPLATES.{template_key}.{section_name}",
                    )

    for group_name, fields in selected_owner_groups.items():
        for field in fields:
            if isinstance(field, Mapping):
                add_field(field, group_name)

    return {
        field_name: tuple(sorted(field_sources))
        for field_name, field_sources in sorted(sources.items())
    }


def validate_daily_report_contract(
    *,
    fields: Sequence[str] | None = None,
    contracts: Mapping[str, Any] | None = None,
    business_time_starts: Mapping[str, str] | None = None,
    owner_daily_submission_time: str | None = None,
    owner_daily_late_time: str | None = None,
    source_order: Sequence[str] | None = None,
    writable_template_fields: Mapping[str, Sequence[str]] | Sequence[str] | None = None,
    document_path: Path | None = None,
    document_checker: Callable[[Path], bool] | None = None,
    check_document: bool = True,
) -> dict[str, Any]:
    selected_fields = list(
        contract_module.normative_daily_report_fields() if fields is None else fields
    )
    selected_contracts = dict(
        contract_module.DAILY_REPORT_FIELD_CONTRACTS if contracts is None else contracts
    )
    selected_business_times = dict(
        contract_module.BUSINESS_TIME_STARTS
        if business_time_starts is None
        else business_time_starts
    )
    selected_submission_time = (
        contract_module.OWNER_DAILY_SUBMISSION_TIME
        if owner_daily_submission_time is None
        else owner_daily_submission_time
    )
    selected_late_time = (
        contract_module.OWNER_DAILY_LATE_TIME
        if owner_daily_late_time is None
        else owner_daily_late_time
    )
    selected_source_order = tuple(
        contract_module.FACT_SOURCE_LANE_ORDER if source_order is None else source_order
    )
    selected_writable_fields = (
        collect_writable_template_fields()
        if writable_template_fields is None
        else _normalize_writable_template_fields(writable_template_fields)
    )
    errors: list[dict[str, Any]] = []

    def add(code: str, detail: Any, *, field: str | None = None) -> None:
        item: dict[str, Any] = {"code": code, "detail": detail}
        if field is not None:
            item["field"] = field
        errors.append(item)

    if len(selected_fields) != EXPECTED_FIELD_COUNT:
        add(
            "field_count_mismatch",
            {"expected": EXPECTED_FIELD_COUNT, "actual": len(selected_fields)},
        )

    duplicates = sorted(
        field_name
        for field_name, count in Counter(selected_fields).items()
        if count > 1
    )
    if duplicates:
        add("duplicate_fields", duplicates)

    field_set = set(selected_fields)
    contract_set = set(selected_contracts)
    if field_set != contract_set:
        add(
            "contract_field_mismatch",
            {
                "missing_contracts": sorted(field_set - contract_set),
                "extra_contracts": sorted(contract_set - field_set),
            },
        )

    if selected_business_times != EXPECTED_BUSINESS_TIME_STARTS:
        add(
            "business_time_drift",
            {"expected": EXPECTED_BUSINESS_TIME_STARTS, "actual": selected_business_times},
        )
    if (
        selected_submission_time != EXPECTED_OWNER_DAILY_SUBMISSION_TIME
        or selected_late_time != EXPECTED_OWNER_DAILY_LATE_TIME
    ):
        add(
            "owner_time_drift",
            {
                "expected_submission": EXPECTED_OWNER_DAILY_SUBMISSION_TIME,
                "actual_submission": selected_submission_time,
                "expected_late": EXPECTED_OWNER_DAILY_LATE_TIME,
                "actual_late": selected_late_time,
            },
        )
    if selected_source_order != EXPECTED_SOURCE_ORDER:
        add(
            "source_order_drift",
            {"expected": list(EXPECTED_SOURCE_ORDER), "actual": list(selected_source_order)},
        )
    if contract_module.SOURCE_LANE_OUTPUT_SKILL_REFERENCE in selected_source_order:
        add(
            "output_skill_in_fact_source_order",
            contract_module.SOURCE_LANE_OUTPUT_SKILL_REFERENCE,
        )

    for field_name, contract in selected_contracts.items():
        missing_metadata = sorted(
            attribute
            for attribute in ("owner_role", "deadline", "entry_route", "contract_version")
            if not str(getattr(contract, attribute, "") or "").strip()
        )
        if missing_metadata:
            add(
                "missing_action_metadata",
                {"missing": missing_metadata},
                field=field_name,
            )

        contract_version = str(getattr(contract, "contract_version", "") or "").strip()
        if (
            contract_version
            and contract_version != contract_module.DAILY_REPORT_FIELD_CONTRACT_VERSION
        ):
            add(
                "contract_version_drift",
                {
                    "expected": contract_module.DAILY_REPORT_FIELD_CONTRACT_VERSION,
                    "actual": contract_version,
                },
                field=field_name,
            )

        unit = str(getattr(contract, "unit", "") or "").strip()
        if not unit:
            add("invalid_unit", field_name)

        try:
            tolerance = float(getattr(contract, "tolerance"))
        except (TypeError, ValueError):
            add("invalid_tolerance", field_name)
            continue
        if tolerance < 0:
            add("negative_tolerance", {"field": field_name, "tolerance": tolerance})
        if tolerance > MAXIMUM_TOLERANCE:
            add(
                "tolerance_above_maximum",
                {"field": field_name, "tolerance": tolerance, "maximum": MAXIMUM_TOLERANCE},
            )

        if getattr(contract, "reference_role", None) != contract_module.REFERENCE_ROLE_COMPARE_ONLY:
            add("invalid_reference_role", field_name)

        contract_source_order = tuple(getattr(contract, "source_lanes", ()))
        if contract_source_order != EXPECTED_SOURCE_ORDER:
            add(
                "field_source_order_drift",
                {
                    "expected": list(EXPECTED_SOURCE_ORDER),
                    "actual": list(contract_source_order),
                },
                field=field_name,
            )
        if contract_module.SOURCE_LANE_OUTPUT_SKILL_REFERENCE in contract_source_order:
            add(
                "output_skill_in_contract_source_order",
                contract_module.SOURCE_LANE_OUTPUT_SKILL_REFERENCE,
                field=field_name,
            )

        entry_route = str(getattr(contract, "entry_route", "") or "").strip()
        entry_fields = tuple(
            str(value).strip()
            for value in getattr(contract, "entry_fields", ())
            if str(value).strip()
        )
        if entry_route == ENTRY_FILL_ROUTE and not entry_fields:
            add(
                "missing_entry_fields",
                {"entry_route": ENTRY_FILL_ROUTE},
                field=field_name,
            )
        for alias in entry_fields:
            owner_role = str(getattr(contract, "owner_role", "") or "").strip()
            if alias not in template_module.role_writable_field_names(owner_role):
                add(
                    "unknown_entry_field_alias",
                    {"alias": alias, "entry_route": entry_route},
                    field=field_name,
                )

    actual_document_path = document_path
    document_fresh = True
    if check_document and actual_document_path is not None and document_checker is not None:
        document_fresh = bool(document_checker(actual_document_path))
        if not document_fresh:
            add("stale_generated_document", str(actual_document_path))

    return {
        "contract_version": contract_module.DAILY_REPORT_FIELD_CONTRACT_VERSION,
        "contract_count": len(selected_fields),
        "template_field_count": len(template_daily_field_contract.all_contract_fields()),
        "writable_template_field_count": len(selected_writable_fields),
        "maximum_tolerance": MAXIMUM_TOLERANCE,
        "business_time_starts": selected_business_times,
        "owner_daily_submission_time": selected_submission_time,
        "owner_daily_late_time": selected_late_time,
        "source_order": list(selected_source_order),
        "document": str(actual_document_path) if actual_document_path is not None else None,
        "document_fresh": document_fresh,
        "errors": errors,
    }
