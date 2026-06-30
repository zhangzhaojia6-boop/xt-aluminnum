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
    os.environ["OUTPUT_SKILL_ROOT"] = str(root)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("OUTPUT_SKILL_ROOT", None)
        else:
            os.environ["OUTPUT_SKILL_ROOT"] = previous


def run_alignment_checks(
    db: Any,
    *,
    business_dates: Sequence[date],
    output_skill_root: Path,
    bundle_builder: BundleBuilder = build_daily_fact_bundle,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with temporary_output_skill_root(output_skill_root):
        for business_date in business_dates:
            try:
                bundle = bundle_builder(db, business_date=business_date, persist_run=False)
                alignment = bundle.get("output_skill_alignment") or {}
                rows.append(
                    {
                        "business_date": business_date.isoformat(),
                        "status": alignment.get("status") or "missing",
                        "bundle_status": bundle.get("status"),
                        "file_name": alignment.get("file_name"),
                        "field_match_rate": alignment.get("field_match_rate"),
                        "matched_fields": alignment.get("matched_fields"),
                        "expected_fields": alignment.get("expected_fields"),
                        "difference_count": alignment.get("difference_count"),
                        "differences": list(alignment.get("differences") or [])[:20],
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
    return bool(rows) and all(row.get("status") == "passed" for row in rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check generated daily reports against D:/输出skill locked report text files."
    )
    parser.add_argument("--output-skill-root", help="Reference folder, for example D:/输出skill")
    parser.add_argument("--date", action="append", type=parse_business_date, help="Business date, repeatable")
    parser.add_argument("--end-date", type=parse_business_date, help="Last business date when --date is not provided")
    parser.add_argument("--days", type=int, default=3, help="How many recent completed business days to check")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    return parser


def _selected_dates(args: argparse.Namespace) -> list[date]:
    if args.date:
        return list(args.date)
    end_date = args.end_date or last_completed_production_business_date()
    return recent_business_dates(end_date=end_date, days=args.days)


def _print_text(payload: dict[str, Any]) -> None:
    print(f"output_skill_root={payload['output_skill_root']}")
    for row in payload["results"]:
        line = (
            f"{row['business_date']} status={row['status']} "
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
        )
    finally:
        db.close()

    payload = {
        "output_skill_root": str(output_skill_root),
        "business_dates": [item.isoformat() for item in business_dates],
        "passed": checks_passed(rows),
        "results": rows,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        _print_text(payload)
    return 0 if payload["passed"] else 1


def _action_required_for_error(exc: Exception) -> str:
    text = str(exc)
    if "no such table" in text:
        return "run_migrations_or_use_production_database"
    return "inspect_error_and_rerun"


if __name__ == "__main__":
    raise SystemExit(main())
