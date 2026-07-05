from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from datetime import date, timedelta
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
from app.database import get_sessionmaker
from app.models.agent_communication import MultimodalEvidence
from app.models.mes import MesCoilSnapshot, MesDailyWipSnapshot, MesWipTotalSnapshot
from app.models.reports import DailyReport, DailyReportHistoryRecord
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
                fact_closure_status = str(fact_closure.get("status") or "missing")
                differences = list(alignment.get("differences") or [])
                if not full_differences:
                    differences = differences[:20]
                rows.append(
                    {
                        "business_date": business_date.isoformat(),
                        "reference_mode": reference_mode,
                        "status": _row_status(
                            alignment_status=alignment_status,
                            fact_closure_status=fact_closure_status,
                        ),
                        "alignment_status": alignment_status,
                        "fact_closure": fact_closure,
                        "bundle_status": bundle.get("status"),
                        "file_name": alignment.get("file_name"),
                        "field_match_rate": alignment.get("field_match_rate"),
                        "matched_fields": alignment.get("matched_fields"),
                        "expected_fields": alignment.get("expected_fields"),
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
                        "status": "error",
                        "alignment_status": "error",
                        "fact_closure": {},
                        "bundle_status": None,
                        "file_name": None,
                        "field_match_rate": None,
                        "matched_fields": None,
                        "expected_fields": None,
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
                f"- Fact closure status: {_fact_closure_status(row)}",
                f"- Bundle status: {row.get('bundle_status')}",
                f"- Field match rate: {row.get('field_match_rate')}",
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
            f"file={row['file_name']}"
        )
        if row.get("error"):
            line = f"{line} error={row['error']}"
        print(line)
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


def _row_status(*, alignment_status: str, fact_closure_status: str) -> str:
    if alignment_status == "passed" and fact_closure_status == "pass":
        return "passed"
    if alignment_status == "passed":
        return "blocked"
    return alignment_status or "missing"


def _row_passed(row: dict[str, Any]) -> bool:
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
        "dingtalk": _dingtalk_source_diagnostics(db, business_date),
        "datahub_final_report": _datahub_final_report_diagnostics(db, business_date),
    }


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
        confirmed_statuses = ("confirmed", "human_confirmed")
        start_at, end_at = production_business_window(business_date)
        confirmed_payload_rows = _count_query(
            db.query(MultimodalEvidence.id).filter(
                MultimodalEvidence.payload.isnot(None),
                MultimodalEvidence.confirmation_status.in_(confirmed_statuses),
            )
        )
        confirmed_rows_in_business_window = _count_query(
            db.query(MultimodalEvidence.id).filter(
                MultimodalEvidence.payload.isnot(None),
                MultimodalEvidence.confirmation_status.in_(confirmed_statuses),
                MultimodalEvidence.created_at >= start_at,
                MultimodalEvidence.created_at < end_at,
            )
        )
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__}
    return {
        "status": "ready",
        "confirmed_payload_rows": confirmed_payload_rows,
        "confirmed_payload_rows_in_business_window": confirmed_rows_in_business_window,
    }


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
        "latest_template_report_status": _template_report_payload_value(latest, "status"),
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
