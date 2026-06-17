from __future__ import annotations

from datetime import date
from pathlib import Path

from app.services.report.output_skill_report_parser import parse_output_skill_daily_report
from app.services.report.template_daily_report import REQUIRED_FIELDS


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "output_skill_daily_reports"


def fixture_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parse_output_skill_daily_report_20260616_key_fields() -> None:
    parsed = parse_output_skill_daily_report(fixture_text("2026-6-16_日报正文.txt"))

    assert parsed["report_date"] == date(2026, 6, 16)
    assert parsed["total_output_daily"] == 328
    assert parsed["outsourced_daily"] == 0
    assert parsed["total_output_delta"] == 22
    assert parsed["cold_1650_daily"] == 144
    assert parsed["cold_1850_daily"] == 33
    assert parsed["cold_2050_daily"] == 96
    assert parsed["rolling_daily"] == 272
    assert parsed["daily_yield_rate"] == 84.86
    assert parsed["daily_yield_delta"] == -1.38
    assert parsed["cost_basis_weight"] == 328.033
    assert parsed["cost_per_ton"] == 1044


def test_parse_output_skill_daily_report_extracts_all_required_fields() -> None:
    parsed = parse_output_skill_daily_report(fixture_text("2026-6-16_日报正文.txt"))

    missing = [field for field in REQUIRED_FIELDS if field not in parsed]

    assert missing == []
