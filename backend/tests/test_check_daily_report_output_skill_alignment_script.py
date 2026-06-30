from __future__ import annotations

from datetime import date
import os

from scripts import check_daily_report_output_skill_alignment as script


def test_recent_business_dates_returns_oldest_to_newest() -> None:
    assert script.recent_business_dates(end_date=date(2026, 6, 29), days=3) == [
        date(2026, 6, 27),
        date(2026, 6, 28),
        date(2026, 6, 29),
    ]


def test_run_alignment_checks_sets_output_skill_root_temporarily(tmp_path) -> None:
    previous = os.environ.get("OUTPUT_SKILL_ROOT")
    calls: list[date] = []

    def fake_builder(db, *, business_date, persist_run=False):
        assert db == "db"
        assert persist_run is False
        assert os.environ["OUTPUT_SKILL_ROOT"] == str(tmp_path)
        calls.append(business_date)
        return {
            "status": "ready",
            "missing_fields": [],
            "gap_plan": {"status": "ready", "item_count": 0, "summary": {}, "items": []},
            "output_skill_alignment": {
                "status": "passed",
                "file_name": f"{business_date.month}-{business_date.day}.txt",
                "field_match_rate": 100.0,
                "matched_fields": 130,
                "expected_fields": 130,
                "difference_count": 0,
                "differences": [],
                "char_match_rate": 100.0,
                "exact_match": True,
                "threshold": 95.0,
            },
        }

    rows = script.run_alignment_checks(
        "db",
        business_dates=[date(2026, 6, 28), date(2026, 6, 29)],
        output_skill_root=tmp_path,
        bundle_builder=fake_builder,
    )

    assert [row["status"] for row in rows] == ["passed", "passed"]
    assert rows[0]["gap_plan"]["status"] == "ready"
    assert calls == [date(2026, 6, 28), date(2026, 6, 29)]
    assert os.environ.get("OUTPUT_SKILL_ROOT") == previous


def test_run_alignment_checks_explains_missing_local_table(tmp_path) -> None:
    def fake_builder(db, *, business_date, persist_run=False):
        raise RuntimeError("no such table: multimodal_evidence")

    rows = script.run_alignment_checks(
        "db",
        business_dates=[date(2026, 6, 29)],
        output_skill_root=tmp_path,
        bundle_builder=fake_builder,
    )

    assert rows[0]["status"] == "error"
    assert rows[0]["action_required"] == "run_migrations_or_use_production_database"


def test_checks_passed_requires_all_rows_passed() -> None:
    assert script.checks_passed([{"status": "passed"}, {"status": "passed"}]) is True
    assert script.checks_passed([{"status": "passed"}, {"status": "review_needed"}]) is False
    assert script.checks_passed([]) is False
