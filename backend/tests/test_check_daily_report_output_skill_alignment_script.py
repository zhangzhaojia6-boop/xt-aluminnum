from __future__ import annotations

from datetime import date
import json
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


def test_write_alignment_artifacts_creates_json_and_markdown_files(tmp_path) -> None:
    artifact_dir = tmp_path / "nested" / "artifacts"
    rows = [
        {
            "business_date": "2026-06-29",
            "status": "review_needed",
            "bundle_status": "ready",
            "field_match_rate": 98.5,
            "exact_match": False,
            "missing_fields_count": 1,
            "differences": [
                {
                    "field": "total_output_daily",
                    "expected": "100",
                    "actual": "99",
                    "source": "DailyFactBundle",
                    "status": "conflict",
                    "action": "review_source",
                }
            ],
        }
    ]

    paths = script.write_alignment_artifacts(rows, artifact_dir)

    json_path = artifact_dir / "daily_report_alignment.json"
    markdown_path = artifact_dir / "daily_report_alignment.md"
    assert artifact_dir.exists()
    assert paths == {"json": str(json_path), "markdown": str(markdown_path)}
    assert json_path.exists()
    assert markdown_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8")) == rows
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "2026-06-29" in markdown
    assert "ready" in markdown
    assert "98.5" in markdown
    assert "False" in markdown
    assert "1" in markdown
    assert "total_output_daily" in markdown
    assert "DailyFactBundle" in markdown
    assert "review_source" in markdown


def test_run_alignment_checks_keeps_all_differences_when_enabled(tmp_path) -> None:
    differences = [{"field": f"field_{index}"} for index in range(25)]

    def fake_builder(db, *, business_date, persist_run=False):
        return {
            "status": "ready",
            "output_skill_alignment": {
                "status": "review_needed",
                "differences": differences,
            },
        }

    rows = script.run_alignment_checks(
        "db",
        business_dates=[date(2026, 6, 29)],
        output_skill_root=tmp_path,
        bundle_builder=fake_builder,
        full_differences=True,
    )

    assert rows[0]["differences"] == differences


def test_run_alignment_checks_truncates_differences_by_default(tmp_path) -> None:
    differences = [{"field": f"field_{index}"} for index in range(25)]

    def fake_builder(db, *, business_date, persist_run=False):
        return {
            "status": "ready",
            "output_skill_alignment": {
                "status": "review_needed",
                "differences": differences,
            },
        }

    rows = script.run_alignment_checks(
        "db",
        business_dates=[date(2026, 6, 29)],
        output_skill_root=tmp_path,
        bundle_builder=fake_builder,
    )

    assert rows[0]["differences"] == differences[:20]


def test_checks_passed_requires_all_rows_passed() -> None:
    assert script.checks_passed([{"status": "passed"}, {"status": "passed"}]) is True
    assert script.checks_passed([{"status": "passed"}, {"status": "review_needed"}]) is False
    assert script.checks_passed([]) is False
