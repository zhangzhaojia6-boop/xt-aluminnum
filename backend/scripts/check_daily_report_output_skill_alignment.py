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

from app.core.business_time import last_completed_production_business_date
from app.database import get_sessionmaker
from app.services.report.daily_fact_bundle import build_daily_fact_bundle


BundleBuilder = Callable[..., dict[str, Any]]


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
def temporary_output_skill_root(root: Path):
    previous = os.environ.get("OUTPUT_SKILL_ROOT")
    previous_mode = os.environ.get("OUTPUT_SKILL_REFERENCE_MODE")
    os.environ["OUTPUT_SKILL_ROOT"] = str(root)
    os.environ["OUTPUT_SKILL_REFERENCE_MODE"] = "adopt"
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
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with temporary_output_skill_root(output_skill_root):
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
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "business_date": business_date.isoformat(),
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
                f"- Fact closure status: {_fact_closure_status(row)}",
                f"- Bundle status: {row.get('bundle_status')}",
                f"- Field match rate: {row.get('field_match_rate')}",
                f"- Exact match: {row.get('exact_match')}",
                f"- Difference count: {difference_count}",
                f"- Missing field count: {row.get('missing_fields_count')}",
                "",
            ]
        )
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
        description="Check generated daily reports against D:/输出skill locked report text files."
    )
    parser.add_argument("--output-skill-root", help="Reference folder, for example D:/输出skill")
    parser.add_argument("--date", action="append", type=parse_business_date, help="Business date, repeatable")
    parser.add_argument("--end-date", type=parse_business_date, help="Last business date when --date is not provided")
    parser.add_argument("--days", type=int, default=3, help="How many recent completed business days to check")
    parser.add_argument("--artifact-dir", type=Path, help="Directory where alignment artifacts are written")
    parser.add_argument("--full-differences", action="store_true", help="Keep all alignment differences")
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
        )
    finally:
        db.close()

    payload = {
        "output_skill_root": str(output_skill_root),
        "business_dates": [item.isoformat() for item in business_dates],
        "passed": checks_passed(rows),
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


def _action_required_for_error(exc: Exception) -> str:
    text = str(exc)
    if "no such table" in text:
        return "run_migrations_or_use_production_database"
    return "inspect_error_and_rerun"


if __name__ == "__main__":
    raise SystemExit(main())
