"""Dry-run template daily reports against OutputSkill target text.

Usage:
    python scripts/dry_run_template_daily_reports.py --start-date 2026-06-10 --end-date 2026-06-16 --output-skill-dir D:\\输出skill
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.services.report import template_daily_report
from app.services.report.output_skill_reconciliation import reconcile_rendered_daily_report


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _iter_dates(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _target_file(output_skill_dir: Path, target_date: date) -> Path:
    return output_skill_dir / f"{target_date.year}-{target_date.month}-{target_date.day}_日报正文.txt"


def _first_issue(row: dict[str, Any]) -> str:
    missing_fields = row.get("missing_fields") or []
    if missing_fields:
        return f"缺失: {missing_fields[0]}"
    differences = row.get("differences") or []
    if differences:
        first = differences[0]
        return f"{first.get('field')}: {first.get('actual')} != {first.get('expected')}"
    if row.get("reference_found") is False:
        return "未找到输出skill目标文本"
    return ""


def dry_run_one(db, *, target_date: date, output_skill_dir: Path) -> dict[str, Any]:
    payload = template_daily_report.build_template_daily_report_payload(db, target_date=target_date)
    reference_path = _target_file(output_skill_dir, target_date)
    reference_text = reference_path.read_text(encoding="utf-8") if reference_path.exists() else ""
    generated_text = str(payload.get("text") or "")
    reconciliation = (
        reconcile_rendered_daily_report(generated_text, reference_text)
        if generated_text and reference_text
        else {
            "exact_match": False,
            "char_match_rate": None,
            "field_match_rate": None,
            "matched_fields": 0,
            "expected_fields": 0,
            "differences": [],
        }
    )
    missing_fields = list(payload.get("missing_fields") or [])
    return {
        "date": target_date.isoformat(),
        "status": payload.get("status") or "blocked",
        "reference_found": bool(reference_text),
        "missing_count": len(missing_fields),
        "missing_fields": missing_fields,
        "conflict_count": len(payload.get("conflicts") or []),
        "exact_match": reconciliation["exact_match"],
        "char_match_rate": reconciliation["char_match_rate"],
        "field_match_rate": reconciliation["field_match_rate"],
        "matched_fields": reconciliation["matched_fields"],
        "expected_fields": reconciliation["expected_fields"],
        "differences": reconciliation["differences"][:10],
    }


def dry_run_range(*, start_date: date, end_date: date, output_skill_dir: Path) -> list[dict[str, Any]]:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        return [
            dry_run_one(db, target_date=target_date, output_skill_dir=output_skill_dir)
            for target_date in _iter_dates(start_date, end_date)
        ]


def _display_rate(value: Any) -> str:
    return "-" if value is None else f"{float(value):.2f}%"


def print_table(rows: list[dict[str, Any]]) -> None:
    print("日期 | 状态 | 缺失数 | 字段匹配率 | 字符匹配率 | 首个问题")
    print("--- | --- | ---: | ---: | ---: | ---")
    for row in rows:
        print(
            " | ".join(
                [
                    str(row["date"]),
                    str(row["status"]),
                    str(row["missing_count"]),
                    _display_rate(row["field_match_rate"]),
                    _display_rate(row["char_match_rate"]),
                    _first_issue(row),
                ]
            )
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run template daily reports and compare OutputSkill text.")
    parser.add_argument("--start-date", required=True, type=_parse_date)
    parser.add_argument("--end-date", required=True, type=_parse_date)
    parser.add_argument("--output-skill-dir", required=True, type=Path)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")

    try:
        rows = dry_run_range(
            start_date=args.start_date,
            end_date=args.end_date,
            output_skill_dir=args.output_skill_dir,
        )
    except SQLAlchemyError as exc:
        print(f"数据库连接或查询失败，无法 dry-run：{exc.__class__.__name__}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))
    else:
        print_table(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
