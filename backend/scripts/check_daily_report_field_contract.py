from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import sys
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.report import daily_report_contract_validation as validation
from scripts import render_daily_report_field_contract as renderer


def build_gate_payload(
    *,
    document_path: Path | None = None,
    validation_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    actual_validation = dict(
        validation.validate_daily_report_contract(
            document_path=document_path or renderer.DEFAULT_OUTPUT_PATH,
            document_checker=renderer.contract_document_is_current,
        )
        if validation_result is None
        else validation_result
    )
    return {
        "status": "pass" if not actual_validation["errors"] else "blocked",
        "passed": not actual_validation["errors"],
        "contract_version": actual_validation["contract_version"],
        "contract_count": actual_validation["contract_count"],
        "template_field_count": actual_validation["template_field_count"],
        "maximum_tolerance": actual_validation["maximum_tolerance"],
        "business_time_starts": actual_validation["business_time_starts"],
        "owner_daily_submission_time": actual_validation["owner_daily_submission_time"],
        "owner_daily_late_time": actual_validation["owner_daily_late_time"],
        "source_order": actual_validation["source_order"],
        "validation": {
            "document": actual_validation["document"],
            "document_fresh": actual_validation["document_fresh"],
            "writable_template_field_count": actual_validation.get(
                "writable_template_field_count"
            ),
            "errors": actual_validation["errors"],
        },
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
            f"status={payload['status']} contract_count={payload['contract_count']} "
            f"template_fields={payload['template_field_count']} "
            f"max_tolerance={payload['maximum_tolerance']} "
            f"document_fresh={payload['validation']['document_fresh']} "
            f"errors={len(payload['validation']['errors'])}"
        )
        for error in payload["validation"]["errors"]:
            print(f"error={error['code']} detail={error['detail']}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
