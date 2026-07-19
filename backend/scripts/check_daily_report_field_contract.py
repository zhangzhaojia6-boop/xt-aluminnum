from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import sys
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domain import daily_report_field_contract as contract_module
from scripts import render_daily_report_field_contract as renderer


EXPECTED_FIELD_COUNT = 125
EXPECTED_TEMPLATE_FIELD_COUNT = 130
MAXIMUM_TOLERANCE = 20.0
EXPECTED_BUSINESS_TIME_STARTS = {
    contract_module.BUSINESS_TIME_STANDARD: "07:50",
    contract_module.BUSINESS_TIME_BILLET: "10:00",
}
EXPECTED_OWNER_DAILY_SUBMISSION_TIME = "09:30"
EXPECTED_OWNER_DAILY_LATE_TIME = "10:00"
EXPECTED_SOURCE_ORDER = (
    "dingtalk_evidence",
    "authorized_correction",
    "mes_wms_readonly",
    "scan_supplement",
    "data_hub_projection",
    "historical_record",
    "rag_explanation_only",
)


def collect_contract_issues(
    *,
    fields: Sequence[str] | None = None,
    contracts: Mapping[str, Any] | None = None,
    business_time_starts: Mapping[str, str] | None = None,
    owner_daily_submission_time: str | None = None,
    owner_daily_late_time: str | None = None,
    source_order: Sequence[str] | None = None,
    document_path: Path | None = None,
    check_document: bool = True,
) -> list[dict[str, Any]]:
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
    issues: list[dict[str, Any]] = []

    def add(code: str, detail: Any) -> None:
        issues.append({"code": code, "detail": detail})

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

    template_fields = [
        field_name
        for group_fields in contract_module.FIELD_GROUPS.values()
        for field_name in group_fields
    ]
    if len(template_fields) != EXPECTED_TEMPLATE_FIELD_COUNT:
        add(
            "template_field_count_mismatch",
            {"expected": EXPECTED_TEMPLATE_FIELD_COUNT, "actual": len(template_fields)},
        )
    template_only = set(template_fields) - field_set
    if template_only != set(contract_module.TEMPLATE_ONLY_FIELD_REASONS):
        add(
            "template_only_field_mismatch",
            {
                "expected": sorted(contract_module.TEMPLATE_ONLY_FIELD_REASONS),
                "actual": sorted(template_only),
            },
        )

    for field_name, contract in selected_contracts.items():
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
        if tuple(getattr(contract, "source_lanes", ())) != EXPECTED_SOURCE_ORDER:
            add("field_source_order_drift", field_name)

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
        add("output_skill_in_fact_source_order", contract_module.SOURCE_LANE_OUTPUT_SKILL_REFERENCE)

    if check_document:
        path = document_path or renderer.DEFAULT_OUTPUT_PATH
        if not renderer.contract_document_is_current(path):
            add("stale_generated_document", str(path))
    return issues


def build_gate_payload(
    *,
    document_path: Path | None = None,
    issues: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    actual_issues = list(
        collect_contract_issues(document_path=document_path)
        if issues is None
        else issues
    )
    payload = renderer.build_contract_payload()
    document_fresh = not any(
        item.get("code") == "stale_generated_document" for item in actual_issues
    )
    return {
        "status": "pass" if not actual_issues else "blocked",
        "passed": not actual_issues,
        "contract_version": payload["contract_version"],
        "normative_field_count": payload["normative_field_count"],
        "template_field_count": payload["template_field_count"],
        "maximum_tolerance": payload["maximum_tolerance"],
        "business_time_starts": payload["business_time_starts"],
        "owner_daily_submission_time": payload["owner_daily_submission_time"],
        "owner_daily_late_time": payload["owner_daily_late_time"],
        "source_order": payload["source_order"],
        "document": str(document_path or renderer.DEFAULT_OUTPUT_PATH),
        "document_fresh": document_fresh,
        "issues": actual_issues,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check the canonical daily report field contract.")
    parser.add_argument("--document", type=Path, default=renderer.DEFAULT_OUTPUT_PATH)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_gate_payload(document_path=args.document)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"status={payload['status']} fields={payload['normative_field_count']} "
            f"template_fields={payload['template_field_count']} "
            f"max_tolerance={payload['maximum_tolerance']} document_fresh={payload['document_fresh']}"
        )
        for issue in payload["issues"]:
            print(f"issue={issue['code']} detail={issue['detail']}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
