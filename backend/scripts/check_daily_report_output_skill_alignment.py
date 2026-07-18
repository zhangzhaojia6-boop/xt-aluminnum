from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass

from sqlalchemy import and_, func, inspect, or_

from app.core.business_time import last_completed_production_business_date, production_business_window
from app.core.report_statuses import READY_REPORT_STATUSES
from app.database import get_sessionmaker
from app.domain.daily_report_field_contract import normative_daily_report_fields
from app.models.agent_communication import MultimodalEvidence
from app.models.mes import MesCoilSnapshot, MesDailyWipSnapshot, MesWipTotalSnapshot
from app.models.production import MobileShiftReport, WorkOrderEntry
from app.models.reports import DailyReport, DailyReportHistoryRecord
from app.services import energy_service
from app.services.report import template_daily_fact_sources, template_daily_report
from app.services.report.daily_fact_bundle import build_daily_fact_bundle
from app.services.report.output_skill_report_parser import parse_output_skill_daily_report


BundleBuilder = Callable[..., dict[str, Any]]
REFERENCE_MODE_COMPARE = "compare"
REFERENCE_MODE_ADOPT = "adopt"
REFERENCE_MODE_CHOICES = (REFERENCE_MODE_COMPARE, REFERENCE_MODE_ADOPT)
KEY_FACT_SOURCE_FIELDS = (
    "total_output_daily",
    "finished_inbound_daily",
    "wip_total",
    "total_electricity_kwh",
    "daily_yield_rate",
)
DATAHUB_TEMPLATE_REPORT_KEY = "template_daily_report"
DINGTALK_FILE_EVIDENCE_TYPES = {"file", "attachment", "dingtalk_file"}
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
NORMATIVE_FIELD_COUNT = len(normative_daily_report_fields())
SUBMITTED_ENTRY_STATUSES = ("submitted", "verified", "approved")
READY_MOBILE_REPORT_STATUSES = tuple(sorted(READY_REPORT_STATUSES))


def parse_business_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date: {value}, expected YYYY-MM-DD") from exc


def recent_business_dates(*, end_date: date, days: int) -> list[date]:
    if days <= 0:
        raise ValueError("days must be greater than 0")
    return [end_date - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def resolve_output_skill_root(raw_root: str | None) -> Path | None:
    if raw_root:
        return Path(raw_root)
    env_root = os.getenv("OUTPUT_SKILL_ROOT") or os.getenv("OUTPUT_SKILL_REFERENCE_ROOT")
    if env_root:
        return Path(env_root)
    default_root = Path("D:/输出skill")
    if default_root.exists():
        return default_root
    return None


@contextmanager
def temporary_output_skill_root(root: Path, *, reference_mode: str = REFERENCE_MODE_COMPARE):
    if reference_mode not in REFERENCE_MODE_CHOICES:
        raise ValueError(f"unsupported output skill reference mode: {reference_mode}")
    previous = os.environ.get("OUTPUT_SKILL_ROOT")
    previous_mode = os.environ.get("OUTPUT_SKILL_REFERENCE_MODE")
    os.environ["OUTPUT_SKILL_ROOT"] = str(root)
    if reference_mode == REFERENCE_MODE_ADOPT:
        os.environ["OUTPUT_SKILL_REFERENCE_MODE"] = REFERENCE_MODE_ADOPT
    else:
        os.environ.pop("OUTPUT_SKILL_REFERENCE_MODE", None)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("OUTPUT_SKILL_ROOT", None)
        else:
            os.environ["OUTPUT_SKILL_ROOT"] = previous
        if previous_mode is None:
            os.environ.pop("OUTPUT_SKILL_REFERENCE_MODE", None)
        else:
            os.environ["OUTPUT_SKILL_REFERENCE_MODE"] = previous_mode


def run_alignment_checks(
    db: Any,
    *,
    business_dates: Sequence[date],
    output_skill_root: Path,
    bundle_builder: BundleBuilder = build_daily_fact_bundle,
    full_differences: bool = False,
    reference_mode: str = REFERENCE_MODE_COMPARE,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with temporary_output_skill_root(output_skill_root, reference_mode=reference_mode):
        for business_date in business_dates:
            try:
                bundle = bundle_builder(db, business_date=business_date, persist_run=False)
                alignment = bundle.get("output_skill_alignment") or {}
                fact_closure = bundle.get("fact_closure") or {}
                alignment_status = str(alignment.get("status") or "missing")
                reference_only = reference_mode == REFERENCE_MODE_ADOPT or bool(bundle.get("reference_only"))
                if reference_only:
                    fact_closure = {
                        **fact_closure,
                        "status": "blocked",
                        "reference_only": True,
                    }
                fact_closure_status = str(fact_closure.get("status") or "missing")
                row_status = _row_status(
                    alignment_status=alignment_status,
                    fact_closure_status=fact_closure_status,
                    reference_only=reference_only,
                )
                differences = list(alignment.get("differences") or [])
                if not full_differences:
                    differences = differences[:20]
                rows.append(
                    {
                        "business_date": business_date.isoformat(),
                        "reference_mode": reference_mode,
                        "reference_only": reference_only,
                        "real_source_gate_passed": row_status == "passed" and not reference_only,
                        "status": row_status,
                        "alignment_status": alignment_status,
                        "fact_closure": fact_closure,
                        "bundle_status": bundle.get("status"),
                        "file_name": alignment.get("file_name"),
                        "field_match_rate": alignment.get("field_match_rate"),
                        "matched_fields": alignment.get("matched_fields"),
                        "expected_fields": alignment.get("expected_fields"),
                        "reference_present_fields": alignment.get("reference_present_fields"),
                        "declared_na_fields": alignment.get("declared_na_fields") or [],
                        "invalid_na_fields": alignment.get("invalid_na_fields") or [],
                        "reference_absent_fields": alignment.get("reference_absent_fields") or [],
                        "reference_absent_count": alignment.get("reference_absent_count"),
                        "normative_fields": alignment.get("normative_fields"),
                        "normative_denominator": alignment.get("normative_denominator"),
                        "normative_matched_fields": alignment.get("normative_matched_fields"),
                        "normative_coverage_rate": alignment.get("normative_coverage_rate"),
                        "numeric_tolerance": alignment.get("numeric_tolerance"),
                        "field_tolerances": alignment.get("field_tolerances") or {},
                        "tolerance_matched_fields": alignment.get("tolerance_matched_fields"),
                        "difference_count": alignment.get("difference_count"),
                        "differences": differences,
                        "char_match_rate": alignment.get("char_match_rate"),
                        "exact_match": bool(alignment.get("exact_match")),
                        "threshold": alignment.get("threshold"),
                        "missing_fields_count": len(bundle.get("missing_fields") or bundle.get("missing") or []),
                        "gap_plan": bundle.get("gap_plan") or {},
                        "source_summary": _source_summary(bundle),
                        "source_diagnostics": _source_diagnostics(db, business_date),
                        "key_fact_sources": _key_fact_sources(bundle, fact_closure),
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "business_date": business_date.isoformat(),
                        "reference_mode": reference_mode,
                        "reference_only": reference_mode == REFERENCE_MODE_ADOPT,
                        "real_source_gate_passed": False,
                        "status": "error",
                        "alignment_status": "error",
                        "fact_closure": {},
                        "bundle_status": None,
                        "file_name": None,
                        "field_match_rate": None,
                        "matched_fields": None,
                        "expected_fields": None,
                        "reference_present_fields": None,
                        "declared_na_fields": [],
                        "invalid_na_fields": [],
                        "reference_absent_fields": [],
                        "reference_absent_count": None,
                        "normative_fields": NORMATIVE_FIELD_COUNT,
                        "normative_denominator": None,
                        "normative_matched_fields": None,
                        "normative_coverage_rate": None,
                        "numeric_tolerance": None,
                        "field_tolerances": {},
                        "tolerance_matched_fields": None,
                        "difference_count": None,
                        "differences": [],
                        "char_match_rate": None,
                        "exact_match": False,
                        "threshold": None,
                        "missing_fields_count": None,
                        "gap_plan": {},
                        "source_summary": {},
                        "source_diagnostics": _source_diagnostics(db, business_date),
                        "key_fact_sources": {},
                        "action_required": _action_required_for_error(exc),
                        "error": str(exc),
                    }
                )
    return rows


def checks_passed(rows: Sequence[dict[str, Any]]) -> bool:
    return bool(rows) and all(_row_passed(row) for row in rows)


def render_alignment_markdown(rows: Sequence[dict[str, Any]]) -> str:
    lines = ["# Daily Report Alignment", ""]
    for row in rows:
        differences = row.get("differences") or []
        difference_count = row.get("difference_count")
        lines.extend(
            [
                f"## {row.get('business_date')}",
                "",
                f"- Status: {row.get('status')}",
                f"- Alignment status: {row.get('alignment_status')}",
                f"- Reference mode: {row.get('reference_mode')}",
                f"- Reference only: {bool(row.get('reference_only'))}",
                f"- Real-source gate passed: {bool(row.get('real_source_gate_passed'))}",
                f"- Fact closure status: {_fact_closure_status(row)}",
                f"- Bundle status: {row.get('bundle_status')}",
                "- Answer key role: comparison-only; it is never a fact source.",
                f"- Field match rate: {row.get('field_match_rate')}",
                f"- Reference present fields: {row.get('reference_present_fields')}",
                f"- Declared N/A fields: {', '.join(str(item) for item in row.get('declared_na_fields') or [])}",
                f"- Invalid N/A fields: {', '.join(str(item) for item in row.get('invalid_na_fields') or [])}",
                f"- Reference absent count: {row.get('reference_absent_count')}",
                f"- Reference absent fields: {', '.join(str(item) for item in row.get('reference_absent_fields') or [])}",
                f"- Normative fields: {row.get('normative_fields')}",
                f"- Normative denominator: {row.get('normative_denominator')}",
                f"- Normative matched fields: {row.get('normative_matched_fields')}",
                f"- Normative coverage rate: {row.get('normative_coverage_rate')}",
                f"- Field tolerances: {row.get('field_tolerances') or {}}",
                f"- Tolerance matched fields: {row.get('tolerance_matched_fields')}",
                f"- Exact match: {row.get('exact_match')}",
                f"- Difference count: {difference_count}",
                f"- Missing field count: {row.get('missing_fields_count')}",
                "",
            ]
        )
        source_summary = row.get("source_summary") if isinstance(row.get("source_summary"), dict) else {}
        source_counts = source_summary.get("source_counts") if isinstance(source_summary, dict) else None
        if isinstance(source_counts, dict) and source_counts:
            lines.extend(
                [
                    f"- Source counts: {_source_counts_text(source_counts)}",
                    f"- Datahub final daily report fields: {source_summary.get('datahub_final_daily_report_field_count', 0)}",
                    "",
                ]
            )
        source_diagnostics = row.get("source_diagnostics") if isinstance(row.get("source_diagnostics"), dict) else {}
        if source_diagnostics:
            lines.extend(_render_source_diagnostics(source_diagnostics))
            lines.append("")
        if row.get("error"):
            lines.extend(
                [
                    f"- Error: {row.get('error')}",
                    f"- Action required: {row.get('action_required')}",
                    "",
                ]
            )
        if isinstance(difference_count, int) and difference_count > len(differences):
            lines.extend(
                [
                    f"- Differences shown: {len(differences)} of {difference_count}",
                    "- This artifact is truncated; use --full-differences for all rows.",
                    "",
                ]
            )
        if row.get("status") == "error" and not differences:
            lines.append("")
            continue
        fact_closure = row.get("fact_closure") if isinstance(row.get("fact_closure"), dict) else {}
        critical_fields = fact_closure.get("critical_fields") if isinstance(fact_closure, dict) else None
        if isinstance(critical_fields, list) and critical_fields:
            lines.extend(
                [
                    "| Critical field | Closure status | Source | Trace | Action |",
                    "|---|---|---|---|---|",
                ]
            )
            for item in critical_fields:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            _markdown_cell(item.get("field")),
                            _markdown_cell(item.get("status")),
                            _markdown_cell(item.get("source")),
                            _markdown_cell(item.get("trace_id")),
                            _markdown_cell(item.get("action")),
                        ]
                    )
                    + " |"
            )
            lines.append("")
        key_fact_sources = row.get("key_fact_sources") if isinstance(row.get("key_fact_sources"), dict) else {}
        if key_fact_sources:
            lines.extend(
                [
                    "| Key fact | Value | Source | Source type | Source ref |",
                    "|---|---|---|---|---|",
                ]
            )
            for field_name, item in key_fact_sources.items():
                if not isinstance(item, dict):
                    continue
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            _markdown_cell(field_name),
                            _markdown_cell(item.get("value")),
                            _markdown_cell(item.get("source")),
                            _markdown_cell(item.get("source_type")),
                            _markdown_cell(item.get("source_ref")),
                        ]
                    )
                    + " |"
                )
            lines.append("")
        lines.extend(
            [
                "| Field | Expected | Actual | Source | Status | Action |",
                "|---|---|---|---|---|---|",
            ]
        )
        if differences:
            for diff in differences:
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            _markdown_cell(diff.get("field")),
                            _markdown_cell(diff.get("expected")),
                            _markdown_cell(diff.get("actual")),
                            _markdown_cell(diff.get("source")),
                            _markdown_cell(diff.get("status")),
                            _markdown_cell(diff.get("action") or diff.get("action_required")),
                        ]
                    )
                    + " |"
                )
        else:
            lines.append("|  |  |  |  |  |  |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_alignment_artifacts(rows: Sequence[dict[str, Any]], artifact_dir: Path) -> dict[str, str]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    json_path = artifact_dir / "daily_report_alignment.json"
    md_path = artifact_dir / "daily_report_alignment.md"
    json_path.write_text(json.dumps(list(rows), ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    md_path.write_text(render_alignment_markdown(rows), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check generated daily reports against D:/输出skill answer-key report text files."
    )
    parser.add_argument("--output-skill-root", help="Reference folder, for example D:/输出skill")
    parser.add_argument("--date", action="append", type=parse_business_date, help="Business date, repeatable")
    parser.add_argument("--end-date", type=parse_business_date, help="Last business date when --date is not provided")
    parser.add_argument("--days", type=int, default=3, help="How many recent completed business days to check")
    parser.add_argument("--artifact-dir", type=Path, help="Directory where alignment artifacts are written")
    parser.add_argument("--full-differences", action="store_true", help="Keep all alignment differences")
    parser.add_argument(
        "--reference-mode",
        choices=REFERENCE_MODE_CHOICES,
        default=REFERENCE_MODE_COMPARE,
        help=(
            "compare keeps D:/输出skill as an answer key only; "
            "adopt allows official daily report facts to fill the bundle for parser/rendering regression."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    return parser


def _selected_dates(args: argparse.Namespace) -> list[date]:
    if args.date:
        return list(args.date)
    end_date = args.end_date or last_completed_production_business_date()
    return recent_business_dates(end_date=end_date, days=args.days)


def _print_text(payload: dict[str, Any]) -> None:
    print(f"output_skill_root={payload['output_skill_root']}")
    artifacts = payload.get("artifacts") or {}
    if artifacts:
        print(f"artifacts json={artifacts.get('json')} markdown={artifacts.get('markdown')}")
    for row in payload["results"]:
        line = (
            f"{row['business_date']} status={row['status']} "
            f"alignment={row.get('alignment_status')} "
            f"fact_closure={_fact_closure_status(row)} "
            f"field_match_rate={row['field_match_rate']} "
            f"matched={row['matched_fields']}/{row['expected_fields']} "
            f"normative={row.get('normative_matched_fields')}/{row.get('normative_denominator')} "
            f"normative_coverage_rate={row.get('normative_coverage_rate')} "
            f"file={row['file_name']}"
        )
        if row.get("error"):
            line = f"{line} error={row['error']}"
        print(line)
        print("  answer_key_role=comparison-only")
        reference_absent = row.get("reference_absent_fields") or []
        if reference_absent:
            print(f"  reference_absent={','.join(str(item) for item in reference_absent)}")
        invalid_na = row.get("invalid_na_fields") or []
        if invalid_na:
            print(f"  invalid_na={','.join(str(item) for item in invalid_na)}")
        gap_plan = row.get("gap_plan") or {}
        if gap_plan.get("item_count"):
            print(
                f"  gap_plan status={gap_plan.get('status')} "
                f"items={gap_plan.get('item_count')} summary={gap_plan.get('summary')}"
            )
        for diff in row.get("differences") or []:
            print(f"  diff field={diff.get('field')} actual={diff.get('actual')} expected={diff.get('expected')}")
    print(f"passed={payload['passed']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        business_dates = _selected_dates(args)
    except ValueError as exc:
        parser.error(str(exc))

    output_skill_root = resolve_output_skill_root(args.output_skill_root)
    if output_skill_root is None:
        parser.error("output skill root is missing; pass --output-skill-root or set OUTPUT_SKILL_ROOT")
    if not output_skill_root.exists():
        parser.error(f"output skill root does not exist: {output_skill_root}")

    sessionmaker = get_sessionmaker()
    db = sessionmaker()
    try:
        rows = run_alignment_checks(
            db,
            business_dates=business_dates,
            output_skill_root=output_skill_root,
            full_differences=args.full_differences,
            reference_mode=args.reference_mode,
        )
    finally:
        db.close()

    payload = {
        "output_skill_root": str(output_skill_root),
        "business_dates": [item.isoformat() for item in business_dates],
        "passed": checks_passed(rows),
        "reference_mode": args.reference_mode,
        "results": rows,
    }
    if args.artifact_dir:
        payload["artifacts"] = write_alignment_artifacts(rows, args.artifact_dir)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        _print_text(payload)
    return 0 if payload["passed"] else 1


def _markdown_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "\\|")


def _row_status(
    *,
    alignment_status: str,
    fact_closure_status: str,
    reference_only: bool = False,
) -> str:
    if reference_only:
        return "reference_only"
    if alignment_status == "passed" and fact_closure_status == "pass":
        return "passed"
    if alignment_status == "passed":
        return "blocked"
    return alignment_status or "missing"


def _row_passed(row: dict[str, Any]) -> bool:
    if row.get("reference_only") or row.get("real_source_gate_passed") is False:
        return False
    return row.get("status") == "passed" and _fact_closure_status(row) == "pass"


def _fact_closure_status(row: dict[str, Any]) -> str:
    fact_closure = row.get("fact_closure")
    if not isinstance(fact_closure, dict):
        return "missing"
    return str(fact_closure.get("status") or "missing")


def _source_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    facts = bundle.get("facts") if isinstance(bundle, dict) else None
    if not isinstance(facts, dict):
        return {"source_counts": {}, "datahub_final_daily_report_field_count": 0}

    counts: dict[str, int] = {}
    datahub_fields: list[str] = []
    for field_name, fact in facts.items():
        if not isinstance(fact, dict):
            continue
        source = str(fact.get("source_type") or fact.get("source") or "unknown")
        counts[source] = counts.get(source, 0) + 1
        if source == "datahub_final_daily_report":
            datahub_fields.append(str(field_name))

    return {
        "source_counts": dict(sorted(counts.items())),
        "datahub_final_daily_report_field_count": len(datahub_fields),
        "datahub_final_daily_report_fields": sorted(datahub_fields)[:50],
    }


def _source_diagnostics(db: Any, business_date: date, *, wip_date: date | None = None) -> dict[str, Any]:
    if not hasattr(db, "query"):
        return {"status": "unavailable", "reason": "db_session_missing"}
    effective_wip_date = wip_date or (business_date + timedelta(days=1))
    return {
        "status": "ready",
        "business_date": business_date.isoformat(),
        "wip_date": effective_wip_date.isoformat(),
        "wip": _wip_source_diagnostics(db, effective_wip_date),
        "energy": _energy_source_diagnostics(db, business_date),
        "manual_entries": _manual_entry_source_diagnostics(db, business_date),
        "dingtalk": _dingtalk_source_diagnostics(db, business_date),
        "datahub_final_report": _datahub_final_report_diagnostics(db, business_date),
    }


def _manual_entry_source_diagnostics(db: Any, business_date: date) -> dict[str, Any]:
    work_order_table_exists = _table_exists(db, WorkOrderEntry.__tablename__)
    mobile_shift_table_exists = _table_exists(db, MobileShiftReport.__tablename__)
    result: dict[str, Any] = {
        "status": "ready" if work_order_table_exists or mobile_shift_table_exists else "missing_table",
        "work_order_entries_status": "ready" if work_order_table_exists else "missing_table",
        "mobile_shift_reports_status": "ready" if mobile_shift_table_exists else "missing_table",
        "submitted_rows": 0,
        "rows_by_entry_type": {},
        "owner_daily_rows": 0,
        "owner_daily_recognized_fields": [],
        "owner_daily_recognized_field_count": 0,
        "mobile_coil_rows": 0,
        "mobile_coil_rows_with_output_weight": 0,
        "mobile_coil_rows_with_energy": 0,
        "mobile_shift_rows": 0,
        "mobile_shift_rows_with_output_weight": 0,
        "mobile_shift_rows_with_electricity": 0,
        "mobile_shift_rows_with_gas": 0,
    }
    try:
        if work_order_table_exists:
            entries = (
                db.query(
                    WorkOrderEntry.entry_type,
                    WorkOrderEntry.extra_payload,
                    WorkOrderEntry.output_weight,
                    WorkOrderEntry.energy_kwh,
                )
                .filter(
                    WorkOrderEntry.business_date == business_date,
                    WorkOrderEntry.entry_status.in_(SUBMITTED_ENTRY_STATUSES),
                )
                .all()
            )
            result["submitted_rows"] = len(entries)
            rows_by_entry_type: dict[str, int] = {}
            owner_fields: set[str] = set()
            for entry in entries:
                entry_type = str(entry.entry_type or "unknown")
                rows_by_entry_type[entry_type] = rows_by_entry_type.get(entry_type, 0) + 1
                if entry_type == "owner_daily":
                    result["owner_daily_rows"] += 1
                    owner_fields.update(_recognized_owner_daily_fields(entry.extra_payload))
                if entry_type == "mobile_coil":
                    result["mobile_coil_rows"] += 1
                    result["mobile_coil_rows_with_output_weight"] += int(_has_value(entry.output_weight))
                    result["mobile_coil_rows_with_energy"] += int(_has_value(entry.energy_kwh))
            result["rows_by_entry_type"] = dict(sorted(rows_by_entry_type.items()))
            result["owner_daily_recognized_fields"] = sorted(owner_fields)
            result["owner_daily_recognized_field_count"] = len(owner_fields)

        if mobile_shift_table_exists:
            shift_rows = (
                db.query(
                    MobileShiftReport.output_weight,
                    MobileShiftReport.electricity_daily,
                    MobileShiftReport.gas_daily,
                )
                .filter(
                    MobileShiftReport.business_date == business_date,
                    MobileShiftReport.report_status.in_(READY_MOBILE_REPORT_STATUSES),
                )
                .all()
            )
            result["mobile_shift_rows"] = len(shift_rows)
            result["mobile_shift_rows_with_output_weight"] = sum(
                int(_has_value(row.output_weight)) for row in shift_rows
            )
            result["mobile_shift_rows_with_electricity"] = sum(
                int(_has_value(row.electricity_daily)) for row in shift_rows
            )
            result["mobile_shift_rows_with_gas"] = sum(int(_has_value(row.gas_daily)) for row in shift_rows)
    except Exception as exc:
        result["status"] = "error"
        result["error"] = type(exc).__name__
    return result


def _recognized_owner_daily_fields(payload: Any) -> set[str]:
    if not isinstance(payload, dict):
        return set()
    recognized: set[str] = set()
    for target_field in template_daily_report.REQUIRED_FIELDS:
        source_fields = (
            target_field,
            *template_daily_fact_sources.OWNER_FIELD_ALIASES.get(target_field, ()),
        )
        if any(_has_value(payload.get(source_field)) for source_field in source_fields if source_field in payload):
            recognized.add(target_field)
    for target_field, source_fields in template_daily_fact_sources.OWNER_MONTH_SUM_ALIASES.items():
        if any(_has_value(payload.get(source_field)) for source_field in source_fields if source_field in payload):
            recognized.add(target_field)
    return recognized


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _wip_source_diagnostics(db: Any, business_date: date) -> dict[str, Any]:
    return {
        "mes_daily_wip_snapshots": _daily_wip_snapshot_diagnostics(db, business_date),
        "mes_coil_snapshots": _coil_snapshot_diagnostics(db, business_date),
        "mes_wip_total_snapshots": _wip_total_snapshot_diagnostics(db, business_date),
    }


def _daily_wip_snapshot_diagnostics(db: Any, business_date: date) -> dict[str, Any]:
    if not _table_exists(db, MesDailyWipSnapshot.__tablename__):
        return {"status": "missing_table"}
    try:
        usable_filter = or_(
            MesDailyWipSnapshot.source.is_(None),
            MesDailyWipSnapshot.source != "output_skill_daily_report",
        )
        total_rows = _count_query(
            db.query(MesDailyWipSnapshot.id).filter(MesDailyWipSnapshot.business_date == business_date)
        )
        usable_rows = _count_query(
            db.query(MesDailyWipSnapshot.id).filter(
                MesDailyWipSnapshot.business_date == business_date,
                usable_filter,
            )
        )
        output_skill_rows = _count_query(
            db.query(MesDailyWipSnapshot.id).filter(
                MesDailyWipSnapshot.business_date == business_date,
                MesDailyWipSnapshot.source == "output_skill_daily_report",
            )
        )
        usable_weight = db.query(func.coalesce(func.sum(MesDailyWipSnapshot.material_weight_tons), 0)).filter(
            MesDailyWipSnapshot.business_date == business_date,
            usable_filter,
        ).scalar()
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__}
    return {
        "status": "ready",
        "total_rows": total_rows,
        "usable_rows": usable_rows,
        "output_skill_rows_excluded": output_skill_rows,
        "usable_weight_tons": round(_safe_float(usable_weight), 3),
    }


def _coil_snapshot_diagnostics(db: Any, business_date: date) -> dict[str, Any]:
    if not _table_exists(db, MesCoilSnapshot.__tablename__):
        return {"status": "missing_table"}
    try:
        def present(column):
            return and_(column.isnot(None), column != "")

        base_filter = MesCoilSnapshot.business_date == business_date
        not_finished_stock = and_(
            MesCoilSnapshot.in_stock_date.is_(None),
            or_(MesCoilSnapshot.status_name.is_(None), MesCoilSnapshot.status_name != "已入库"),
        )
        has_process = or_(present(MesCoilSnapshot.current_process), present(MesCoilSnapshot.next_process))
        eligible_filters = (
            base_filter,
            MesCoilSnapshot.delivery_date.is_(None),
            MesCoilSnapshot.allocation_date.is_(None),
            not_finished_stock,
            has_process,
        )
        total_rows = _count_query(db.query(MesCoilSnapshot.id).filter(base_filter))
        with_weight_rows = _count_query(
            db.query(MesCoilSnapshot.id).filter(base_filter, MesCoilSnapshot.material_weight > 0)
        )
        with_process_rows = _count_query(db.query(MesCoilSnapshot.id).filter(base_filter, has_process))
        excluded_finished_rows = _count_query(
            db.query(MesCoilSnapshot.id).filter(
                base_filter,
                or_(MesCoilSnapshot.in_stock_date.isnot(None), MesCoilSnapshot.status_name == "已入库"),
            )
        )
        excluded_delivery_or_allocation_rows = _count_query(
            db.query(MesCoilSnapshot.id).filter(
                base_filter,
                or_(MesCoilSnapshot.delivery_date.isnot(None), MesCoilSnapshot.allocation_date.isnot(None)),
            )
        )
        eligible_rows = _count_query(db.query(MesCoilSnapshot.id).filter(*eligible_filters))
        eligible_weight_kg = db.query(func.coalesce(func.sum(MesCoilSnapshot.material_weight), 0)).filter(
            *eligible_filters
        ).scalar()
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__}
    return {
        "status": "ready",
        "total_rows": total_rows,
        "with_weight_rows": with_weight_rows,
        "with_process_rows": with_process_rows,
        "excluded_finished_rows": excluded_finished_rows,
        "excluded_delivery_or_allocation_rows": excluded_delivery_or_allocation_rows,
        "eligible_rows": eligible_rows,
        "eligible_weight_tons": round(_safe_float(eligible_weight_kg) / 1000, 3),
    }


def _wip_total_snapshot_diagnostics(db: Any, business_date: date) -> dict[str, Any]:
    if not _table_exists(db, MesWipTotalSnapshot.__tablename__):
        return {"status": "missing_table"}
    try:
        start_at, end_at = production_business_window(business_date)
        rows = _count_query(
            db.query(MesWipTotalSnapshot.id).filter(
                MesWipTotalSnapshot.snapshot_at >= start_at,
                MesWipTotalSnapshot.snapshot_at < end_at,
            )
        )
        weight = db.query(func.coalesce(func.sum(MesWipTotalSnapshot.doing_weight_tons), 0)).filter(
            MesWipTotalSnapshot.snapshot_at >= start_at,
            MesWipTotalSnapshot.snapshot_at < end_at,
        ).scalar()
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__}
    return {"status": "ready", "rows": rows, "weight_tons": round(_safe_float(weight), 3)}


def _dingtalk_source_diagnostics(db: Any, business_date: date) -> dict[str, Any]:
    if not _table_exists(db, MultimodalEvidence.__tablename__):
        return {"status": "missing_table"}
    try:
        confirmed_statuses = ("confirmed", "human_confirmed", "specialist_sampled")
        start_at, end_at = production_business_window(business_date)
        rows = (
            db.query(
                MultimodalEvidence.evidence_type,
                MultimodalEvidence.file_uri,
                MultimodalEvidence.recognized_text,
                MultimodalEvidence.confirmation_status,
                MultimodalEvidence.payload,
            )
            .filter(
                MultimodalEvidence.payload.isnot(None),
                MultimodalEvidence.created_at >= start_at,
                MultimodalEvidence.created_at < end_at,
                or_(
                    MultimodalEvidence.payload["source"].as_string() == "dingtalk",
                    MultimodalEvidence.evidence_type.like("dingtalk/_%", escape="/"),
                    MultimodalEvidence.file_uri.like("dingtalk://%"),
                ),
            )
            .all()
        )
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__}
    file_rows = [row for row in rows if _is_dingtalk_file_evidence(row)]
    machine_file_rows = [
        row
        for row in file_rows
        if str(row.confirmation_status or "").strip().lower() == "machine_only"
    ]
    confirmed_rows = [
        row for row in rows if str(row.confirmation_status or "").strip().lower() in confirmed_statuses
    ]
    confirmed_file_rows = [row for row in confirmed_rows if _is_dingtalk_file_evidence(row)]
    parseable_confirmed_files = _parseable_dingtalk_file_count(confirmed_file_rows)
    return {
        "status": "ready",
        "scope": "business_window",
        "business_window": f"{start_at.isoformat()}/{end_at.isoformat()}",
        "payload_rows_in_business_window": len(rows),
        "file_payload_rows_in_business_window": len(file_rows),
        "machine_only_file_payload_rows_in_business_window": len(machine_file_rows),
        "machine_only_parseable_file_payload_rows_in_business_window": _parseable_dingtalk_file_count(
            machine_file_rows
        ),
        "confirmed_payload_rows": len(confirmed_rows),
        "confirmed_payload_rows_in_business_window": len(confirmed_rows),
        "confirmed_file_payload_rows": len(confirmed_file_rows),
        "confirmed_file_payload_rows_in_business_window": len(confirmed_file_rows),
        "parseable_file_payload_rows": parseable_confirmed_files,
        "parseable_file_payload_rows_in_business_window": parseable_confirmed_files,
    }


def _is_dingtalk_file_evidence(row: Any) -> bool:
    evidence_type = str(row.evidence_type or "").strip().lower()
    if evidence_type in DINGTALK_FILE_EVIDENCE_TYPES:
        return True
    if row.file_uri:
        return True
    payload = row.payload if isinstance(row.payload, dict) else {}
    return bool(payload.get("file_name") or payload.get("dingtalk_media_id"))


def _parseable_dingtalk_file_count(rows: Sequence[Any]) -> int:
    count = 0
    for row in rows:
        if _parseable_field_count(_dingtalk_evidence_text(row)) >= MIN_DINGTALK_PARSEABLE_FIELDS:
            count += 1
    return count


MIN_DINGTALK_PARSEABLE_FIELDS = 3


def _dingtalk_evidence_text(row: Any) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    _append_dingtalk_text_part(row.recognized_text, parts=parts, seen=seen)
    payload = row.payload if isinstance(row.payload, dict) else {}
    _collect_dingtalk_payload_text(payload, parts=parts, seen=seen)
    return "\n".join(parts)


def _collect_dingtalk_payload_text(value: Any, *, parts: list[str], seen: set[str], depth: int = 0) -> None:
    if depth > 4:
        return
    if isinstance(value, dict):
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


def _energy_source_diagnostics(db: Any, business_date: date) -> dict[str, Any]:
    try:
        summary = energy_service.summarize_energy_for_date(db, business_date=business_date)
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__}
    rows = summary.get("rows") if isinstance(summary.get("rows"), list) else []
    by_source: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "system")
        bucket = by_source.setdefault(
            source,
            {
                "source": source,
                "row_count": 0,
                "electricity_value": 0.0,
                "gas_value": 0.0,
                "water_value": 0.0,
                "total_energy": 0.0,
                "output_weight": 0.0,
            },
        )
        bucket["row_count"] += 1
        bucket["electricity_value"] += _safe_float(row.get("electricity_value"))
        bucket["gas_value"] += _safe_float(row.get("gas_value"))
        bucket["water_value"] += _safe_float(row.get("water_value"))
        bucket["total_energy"] += _safe_float(row.get("total_energy"))
        bucket["output_weight"] += _safe_float(row.get("output_weight"))
    return {
        "status": "ready",
        "primary_source": summary.get("primary_source"),
        "output_basis": summary.get("output_basis"),
        "electricity_value": round(_safe_float(summary.get("electricity_value")), 3),
        "gas_value": round(_safe_float(summary.get("gas_value")), 3),
        "total_energy": round(_safe_float(summary.get("total_energy")), 3),
        "total_output_weight": round(_safe_float(summary.get("total_output_weight")), 3),
        "system_totals": _energy_totals(summary.get("system_totals")),
        "owner_totals": _energy_totals(summary.get("owner_totals")),
        "mobile_totals": _energy_totals(summary.get("mobile_totals")),
        "rows_by_source": [
            {key: round(value, 3) if isinstance(value, float) else value for key, value in item.items()}
            for item in sorted(by_source.values(), key=lambda entry: entry["source"])
        ],
    }


def _energy_totals(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for key in (
        "row_count",
        "electricity_value",
        "gas_value",
        "water_value",
        "total_energy",
        "total_output_weight",
        "energy_per_ton",
    ):
        if key not in value:
            continue
        item = value.get(key)
        result[key] = round(_safe_float(item), 3) if key != "row_count" else int(item or 0)
    return result


def _datahub_final_report_diagnostics(db: Any, business_date: date) -> dict[str, Any]:
    daily_report = _daily_report_diagnostics(db, business_date)
    history = _daily_report_history_diagnostics(db, business_date)
    if daily_report.get("status") == "missing_table" and history.get("status") == "missing_table":
        return {"status": "missing_table", "daily_report": daily_report, "history": history}
    return {"status": "ready", "daily_report": daily_report, "history": history}


def _daily_report_diagnostics(db: Any, business_date: date) -> dict[str, Any]:
    if not _table_exists(db, DailyReport.__tablename__):
        return {"status": "missing_table"}
    try:
        total_rows = _count_query(db.query(DailyReport.id).filter(DailyReport.report_date == business_date))
        production_rows = _count_query(
            db.query(DailyReport.id).filter(
                DailyReport.report_date == business_date,
                DailyReport.report_type == "production",
            )
        )
        production_final_text_rows = _count_query(
            db.query(DailyReport.id).filter(
                DailyReport.report_date == business_date,
                DailyReport.report_type == "production",
                DailyReport.final_text_summary.isnot(None),
                DailyReport.final_text_summary != "",
            )
        )
        production_text_rows = _count_query(
            db.query(DailyReport.id).filter(
                DailyReport.report_date == business_date,
                DailyReport.report_type == "production",
                DailyReport.text_summary.isnot(None),
                DailyReport.text_summary != "",
            )
        )
        latest = (
            db.query(DailyReport)
            .filter(DailyReport.report_date == business_date, DailyReport.report_type == "production")
            .order_by(
                DailyReport.final_confirmed_at.desc(),
                DailyReport.published_at.desc(),
                DailyReport.id.desc(),
            )
            .first()
        )
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__}
    return {
        "status": "ready",
        "rows": total_rows,
        "production_rows": production_rows,
        "production_final_text_rows": production_final_text_rows,
        "production_text_rows": production_text_rows,
        "latest_production_report_id": getattr(latest, "id", None),
        "latest_final_text_parseable_fields": _parseable_field_count(getattr(latest, "final_text_summary", None)),
        "latest_text_parseable_fields": _parseable_field_count(getattr(latest, "text_summary", None)),
        "latest_report_data_keys": _report_data_keys(latest),
        "latest_template_report_status": _template_report_payload_value(latest, "status"),
        "latest_template_payload_keys": _template_report_payload_keys(latest),
        "latest_template_values_count": _template_report_values_count(latest),
        "latest_template_missing_count": _template_report_missing_count(latest),
        "latest_template_text_parseable_fields": _parseable_field_count(
            _template_report_payload_value(latest, "text")
        ),
    }


def _daily_report_history_diagnostics(db: Any, business_date: date) -> dict[str, Any]:
    if not _table_exists(db, DailyReportHistoryRecord.__tablename__):
        return {"status": "missing_table"}
    try:
        total_rows = _count_query(
            db.query(DailyReportHistoryRecord.id).filter(DailyReportHistoryRecord.business_date == business_date)
        )
        daily_rows = _count_query(
            db.query(DailyReportHistoryRecord.id).filter(
                DailyReportHistoryRecord.business_date == business_date,
                DailyReportHistoryRecord.report_type == "daily",
            )
        )
        latest = (
            db.query(DailyReportHistoryRecord)
            .filter(
                DailyReportHistoryRecord.business_date == business_date,
                DailyReportHistoryRecord.report_type == "daily",
            )
            .order_by(DailyReportHistoryRecord.created_at.desc(), DailyReportHistoryRecord.id.desc())
            .first()
        )
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__}
    return {
        "status": "ready",
        "rows": total_rows,
        "daily_rows": daily_rows,
        "latest_daily_history_id": getattr(latest, "id", None),
        "latest_report_text_parseable_fields": _parseable_field_count(getattr(latest, "report_text", None)),
    }


def _parseable_field_count(text: Any) -> int:
    clean = str(text or "").strip()
    if not clean:
        return 0
    return len(parse_output_skill_daily_report(clean))


def _template_report_payload_value(report: Any, key: str) -> Any:
    if report is None:
        return None
    report_data = getattr(report, "report_data", None)
    if not isinstance(report_data, dict):
        return None
    payload = report_data.get(DATAHUB_TEMPLATE_REPORT_KEY)
    if not isinstance(payload, dict):
        return None
    return payload.get(key)


def _report_data_keys(report: Any) -> list[str]:
    report_data = getattr(report, "report_data", None)
    if not isinstance(report_data, dict):
        return []
    return sorted(str(key) for key in report_data.keys())


def _template_report_payload_keys(report: Any) -> list[str]:
    report_data = getattr(report, "report_data", None)
    if not isinstance(report_data, dict):
        return []
    payload = report_data.get(DATAHUB_TEMPLATE_REPORT_KEY)
    if not isinstance(payload, dict):
        return []
    return sorted(str(key) for key in payload.keys())


def _template_report_values_count(report: Any) -> int:
    values = _template_report_payload_value(report, "values")
    if isinstance(values, dict):
        return len([key for key, value in values.items() if value not in (None, "")])
    facts = _template_report_payload_value(report, "facts")
    if isinstance(facts, dict):
        fact_values = facts.get("values")
        if isinstance(fact_values, dict):
            return len([key for key, value in fact_values.items() if value not in (None, "")])
    return 0


def _template_report_missing_count(report: Any) -> int:
    missing = _template_report_payload_value(report, "missing_fields")
    if isinstance(missing, list):
        return len(missing)
    facts = _template_report_payload_value(report, "facts")
    if isinstance(facts, dict):
        fact_missing = facts.get("missing_fields")
        if isinstance(fact_missing, list):
            return len(fact_missing)
    return 0


def _render_source_diagnostics(source_diagnostics: dict[str, Any]) -> list[str]:
    if source_diagnostics.get("status") != "ready":
        return [f"- Source diagnostics: {source_diagnostics.get('status')}"]
    lines = [
        "- Source diagnostics: "
        f"business_date={source_diagnostics.get('business_date')}, "
        f"wip_date={source_diagnostics.get('wip_date')}"
    ]
    wip = source_diagnostics.get("wip") if isinstance(source_diagnostics.get("wip"), dict) else {}
    for name, item in wip.items():
        if not isinstance(item, dict):
            continue
        lines.append(f"  - {name}: {_source_diagnostic_item_text(item)}")
    energy = source_diagnostics.get("energy") if isinstance(source_diagnostics.get("energy"), dict) else {}
    if energy:
        lines.append(f"  - energy: {_source_diagnostic_item_text(energy)}")
    manual_entries = (
        source_diagnostics.get("manual_entries")
        if isinstance(source_diagnostics.get("manual_entries"), dict)
        else {}
    )
    if manual_entries:
        lines.append(f"  - manual_entries: {_source_diagnostic_item_text(manual_entries)}")
    dingtalk = source_diagnostics.get("dingtalk") if isinstance(source_diagnostics.get("dingtalk"), dict) else {}
    if dingtalk:
        lines.append(f"  - dingtalk: {_source_diagnostic_item_text(dingtalk)}")
    datahub = (
        source_diagnostics.get("datahub_final_report")
        if isinstance(source_diagnostics.get("datahub_final_report"), dict)
        else {}
    )
    if datahub:
        lines.append(f"  - datahub_final_report: {_source_diagnostic_item_text(datahub)}")
    return lines


def _source_diagnostic_item_text(item: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in item.items())


def _table_exists(db: Any, table_name: str) -> bool:
    try:
        return inspect(db.get_bind()).has_table(table_name)
    except Exception:
        return False


def _count_query(query: Any) -> int:
    return int(query.count())


def _safe_float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _key_fact_sources(bundle: dict[str, Any], fact_closure: dict[str, Any]) -> dict[str, Any]:
    facts = bundle.get("facts") if isinstance(bundle, dict) else None
    if not isinstance(facts, dict):
        return {}

    fields = list(KEY_FACT_SOURCE_FIELDS)
    critical_fields = fact_closure.get("critical_fields") if isinstance(fact_closure, dict) else None
    if isinstance(critical_fields, list):
        for item in critical_fields:
            if isinstance(item, dict) and item.get("field"):
                field_name = str(item["field"])
                if field_name not in fields:
                    fields.append(field_name)

    result: dict[str, Any] = {}
    for field_name in fields:
        fact = facts.get(field_name)
        if not isinstance(fact, dict):
            result[field_name] = {"status": "missing"}
            continue
        result[field_name] = {
            "value": fact.get("value"),
            "source": fact.get("source"),
            "source_type": fact.get("source_type"),
            "priority": fact.get("priority"),
            "source_ref": fact.get("source_ref"),
        }
    return result


def _source_counts_text(source_counts: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in source_counts.items())


def _action_required_for_error(exc: Exception) -> str:
    text = str(exc)
    if "no such table" in text:
        return "run_migrations_or_use_production_database"
    return "inspect_error_and_rerun"


if __name__ == "__main__":
    raise SystemExit(main())
