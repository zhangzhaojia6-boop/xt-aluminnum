from __future__ import annotations

from datetime import date, datetime
import json
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from scripts import check_daily_report_output_skill_alignment as script


def test_recent_business_dates_returns_oldest_to_newest() -> None:
    assert script.recent_business_dates(end_date=date(2026, 6, 29), days=3) == [
        date(2026, 6, 27),
        date(2026, 6, 28),
        date(2026, 6, 29),
    ]


def test_run_alignment_checks_uses_compare_mode_by_default(tmp_path) -> None:
    previous = os.environ.get("OUTPUT_SKILL_ROOT")
    previous_mode = os.environ.get("OUTPUT_SKILL_REFERENCE_MODE")
    os.environ["OUTPUT_SKILL_REFERENCE_MODE"] = "adopt"
    calls: list[date] = []

    def fake_builder(db, *, business_date, persist_run=False):
        assert db == "db"
        assert persist_run is False
        assert os.environ["OUTPUT_SKILL_ROOT"] == str(tmp_path)
        assert "OUTPUT_SKILL_REFERENCE_MODE" not in os.environ
        calls.append(business_date)
        return {
            "status": "ready",
            "missing_fields": [],
            "facts": {
                "total_output_daily": {
                    "value": 100,
                    "source": "mes_packaging_output",
                    "source_type": "mes_packaging_output",
                    "priority": 80,
                    "source_ref": {"business_date": business_date.isoformat()},
                }
            },
            "gap_plan": {"status": "ready", "item_count": 0, "summary": {}, "items": []},
            "fact_closure": {"status": "pass", "critical_fields": []},
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
    assert [row["reference_mode"] for row in rows] == ["compare", "compare"]
    assert [row["alignment_status"] for row in rows] == ["passed", "passed"]
    assert rows[0]["fact_closure"]["status"] == "pass"
    assert rows[0]["source_summary"]["source_counts"] == {"mes_packaging_output": 1}
    assert rows[0]["key_fact_sources"]["total_output_daily"]["source_type"] == "mes_packaging_output"
    assert rows[0]["gap_plan"]["status"] == "ready"
    assert calls == [date(2026, 6, 28), date(2026, 6, 29)]
    assert os.environ.get("OUTPUT_SKILL_ROOT") == previous
    assert os.environ.get("OUTPUT_SKILL_REFERENCE_MODE") == "adopt"
    if previous_mode is None:
        os.environ.pop("OUTPUT_SKILL_REFERENCE_MODE", None)
    else:
        os.environ["OUTPUT_SKILL_REFERENCE_MODE"] = previous_mode


def test_run_alignment_checks_can_enable_adopt_mode_explicitly(tmp_path) -> None:
    previous = os.environ.get("OUTPUT_SKILL_ROOT")
    previous_mode = os.environ.get("OUTPUT_SKILL_REFERENCE_MODE")

    def fake_builder(db, *, business_date, persist_run=False):
        assert os.environ["OUTPUT_SKILL_ROOT"] == str(tmp_path)
        assert os.environ["OUTPUT_SKILL_REFERENCE_MODE"] == "adopt"
        return {
            "status": "ready",
            "missing_fields": [],
            "gap_plan": {"status": "ready", "item_count": 0, "summary": {}, "items": []},
            "fact_closure": {"status": "pass", "critical_fields": []},
            "output_skill_alignment": {
                "status": "passed",
                "field_match_rate": 100.0,
                "matched_fields": 130,
                "expected_fields": 130,
                "difference_count": 0,
                "differences": [],
            },
        }

    rows = script.run_alignment_checks(
        "db",
        business_dates=[date(2026, 6, 29)],
        output_skill_root=tmp_path,
        bundle_builder=fake_builder,
        reference_mode="adopt",
    )

    assert rows[0]["status"] == "passed"
    assert rows[0]["reference_mode"] == "adopt"
    assert os.environ.get("OUTPUT_SKILL_ROOT") == previous
    assert os.environ.get("OUTPUT_SKILL_REFERENCE_MODE") == previous_mode


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
            "difference_count": 1,
            "missing_fields_count": 1,
            "alignment_status": "review_needed",
            "fact_closure": {
                "status": "blocked",
                "critical_fields": [
                    {
                        "field": "total_output_daily",
                        "status": "mismatch",
                        "source": "DailyFactBundle",
                        "trace_id": "trace-output",
                        "action": "review_source",
                    }
                ],
            },
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
    assert "Fact closure status: blocked" in markdown
    assert "Reference mode" in markdown
    assert "trace-output" in markdown
    assert "1" in markdown
    assert "total_output_daily" in markdown
    assert "DailyFactBundle" in markdown
    assert "review_source" in markdown


def test_render_alignment_markdown_shows_difference_count_and_truncation_notice() -> None:
    rows = [
        {
            "business_date": "2026-06-29",
            "status": "review_needed",
            "bundle_status": "ready",
            "field_match_rate": 80.0,
            "exact_match": False,
            "difference_count": 25,
            "missing_fields_count": 0,
            "alignment_status": "review_needed",
            "fact_closure": {"status": "blocked", "critical_fields": []},
            "differences": [{"field": f"field_{index}"} for index in range(20)],
        }
    ]

    markdown = script.render_alignment_markdown(rows)

    assert "Difference count: 25" in markdown
    assert "truncated" in markdown
    assert "--full-differences" in markdown
    assert "all rows" in markdown


def test_render_alignment_markdown_shows_error_details() -> None:
    rows = [
        {
            "business_date": "2026-06-29",
            "status": "error",
            "bundle_status": None,
            "field_match_rate": None,
            "exact_match": False,
            "difference_count": None,
            "missing_fields_count": None,
            "differences": [],
            "error": "no such table: multimodal_evidence",
            "action_required": "run_migrations_or_use_production_database",
        }
    ]

    markdown = script.render_alignment_markdown(rows)

    assert "Status: error" in markdown
    assert "Error: no such table: multimodal_evidence" in markdown
    assert "Action required: run_migrations_or_use_production_database" in markdown


def test_run_alignment_checks_keeps_all_differences_when_enabled(tmp_path) -> None:
    differences = [{"field": f"field_{index}"} for index in range(25)]

    def fake_builder(db, *, business_date, persist_run=False):
        return {
            "status": "ready",
            "fact_closure": {"status": "blocked", "critical_fields": []},
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
            "fact_closure": {"status": "blocked", "critical_fields": []},
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
    assert script.checks_passed(
        [
            {"status": "passed", "fact_closure": {"status": "pass"}},
            {"status": "passed", "fact_closure": {"status": "pass"}},
        ]
    ) is True
    assert script.checks_passed(
        [
            {"status": "passed", "fact_closure": {"status": "pass"}},
            {"status": "review_needed", "fact_closure": {"status": "pass"}},
        ]
    ) is False
    assert script.checks_passed(
        [{"status": "passed", "fact_closure": {"status": "blocked"}}]
    ) is False
    assert script.checks_passed([{"status": "passed"}]) is False
    assert script.checks_passed([]) is False


def test_run_alignment_checks_blocks_when_fact_closure_is_blocked(tmp_path) -> None:
    def fake_builder(db, *, business_date, persist_run=False):
        return {
            "status": "ready",
            "missing_fields": [],
            "gap_plan": {"status": "ready", "item_count": 0, "summary": {}, "items": []},
            "fact_closure": {
                "status": "blocked",
                "critical_fields": [
                    {
                        "field": "total_electricity_kwh",
                        "status": "missing",
                        "source": None,
                        "trace_id": "trace-missing-energy",
                        "action": "补充高压总用电量",
                    }
                ],
            },
            "output_skill_alignment": {
                "status": "passed",
                "file_name": "2026-6-29.txt",
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
        business_dates=[date(2026, 6, 29)],
        output_skill_root=tmp_path,
        bundle_builder=fake_builder,
    )

    assert rows[0]["alignment_status"] == "passed"
    assert rows[0]["status"] == "blocked"
    assert rows[0]["fact_closure"]["status"] == "blocked"
    assert script.checks_passed(rows) is False


def test_source_diagnostics_reports_real_wip_candidates(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'alignment-diagnostics.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            script.MesCoilSnapshot.__table__,
            script.MesDailyWipSnapshot.__table__,
            script.MesWipTotalSnapshot.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, future=True)
    db = Session()
    business_date = date(2026, 6, 29)
    try:
        db.add_all(
            [
                script.MesDailyWipSnapshot(
                    business_date=business_date,
                    workshop_name="精整",
                    process_name="精整",
                    material_weight_tons=10,
                    source="mes_coil_snapshot",
                ),
                script.MesDailyWipSnapshot(
                    business_date=business_date,
                    workshop_name="精整",
                    process_name="精整-答案",
                    material_weight_tons=999,
                    source="output_skill_daily_report",
                ),
                script.MesCoilSnapshot(
                    coil_id="coil-eligible",
                    tracking_card_no="card-eligible",
                    business_date=business_date,
                    material_weight=2000,
                    current_workshop="精整",
                    current_process="精整",
                ),
                script.MesCoilSnapshot(
                    coil_id="coil-finished",
                    tracking_card_no="card-finished",
                    business_date=business_date,
                    material_weight=3000,
                    current_workshop="精整",
                    current_process="精整",
                    status_name="已入库",
                ),
                script.MesWipTotalSnapshot(
                    source_id="wip-total-1",
                    workshop_name="精整",
                    process_name="精整",
                    doing_weight_tons=4,
                    snapshot_at=datetime(2026, 6, 29, 12, 0),
                ),
            ]
        )
        db.commit()

        diagnostics = script._source_diagnostics(db, business_date, wip_date=business_date)
    finally:
        db.close()

    assert diagnostics["status"] == "ready"
    wip = diagnostics["wip"]
    assert wip["mes_daily_wip_snapshots"]["usable_rows"] == 1
    assert wip["mes_daily_wip_snapshots"]["output_skill_rows_excluded"] == 1
    assert wip["mes_coil_snapshots"]["eligible_rows"] == 1
    assert wip["mes_coil_snapshots"]["excluded_finished_rows"] == 1
    assert wip["mes_coil_snapshots"]["eligible_weight_tons"] == 2
    assert wip["mes_wip_total_snapshots"]["rows"] == 1
    assert wip["mes_wip_total_snapshots"]["weight_tons"] == 4
    assert diagnostics["dingtalk"]["status"] == "missing_table"


def test_source_diagnostics_reports_datahub_final_report_parseability(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'alignment-datahub-diagnostics.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            script.DailyReport.__table__,
            script.DailyReportHistoryRecord.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, future=True)
    db = Session()
    business_date = date(2026, 6, 29)
    report_text = "6月29日车间总产量日合计100吨，入库成品日合计98吨，日成品率83.2%。"
    try:
        db.add(
            script.DailyReport(
                report_date=business_date,
                report_type="production",
                final_text_summary=report_text,
                text_summary="6月29日车间总产量日合计90吨。",
                report_data={
                    "other_payload": {"status": "ready"},
                    "template_daily_report": {
                        "status": "ready",
                        "text": report_text,
                        "values": {"total_output_daily": 100, "empty_field": None},
                        "missing_fields": ["total_gas_m3"],
                    }
                },
            )
        )
        db.add(
            script.DailyReportHistoryRecord(
                report_type="daily",
                business_date=business_date,
                report_text=report_text,
                report_payload={},
                source_summary={},
                facts_hash="facts",
                text_hash="text",
            )
        )
        db.commit()

        diagnostics = script._source_diagnostics(db, business_date, wip_date=business_date)
    finally:
        db.close()

    datahub = diagnostics["datahub_final_report"]
    assert datahub["status"] == "ready"
    assert datahub["daily_report"]["production_rows"] == 1
    assert datahub["daily_report"]["production_final_text_rows"] == 1
    assert datahub["daily_report"]["latest_final_text_parseable_fields"] >= 3
    assert datahub["daily_report"]["latest_report_data_keys"] == ["other_payload", "template_daily_report"]
    assert datahub["daily_report"]["latest_template_report_status"] == "ready"
    assert datahub["daily_report"]["latest_template_payload_keys"] == [
        "missing_fields",
        "status",
        "text",
        "values",
    ]
    assert datahub["daily_report"]["latest_template_values_count"] == 1
    assert datahub["daily_report"]["latest_template_missing_count"] == 1
    assert datahub["daily_report"]["latest_template_text_parseable_fields"] >= 3
    assert datahub["history"]["daily_rows"] == 1
    assert datahub["history"]["latest_report_text_parseable_fields"] >= 3


def test_source_diagnostics_reports_parseable_dingtalk_file_payloads(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'alignment-dingtalk-diagnostics.db'}", future=True)
    Base.metadata.create_all(engine, tables=[script.MultimodalEvidence.__table__])
    Session = sessionmaker(bind=engine, future=True)
    db = Session()
    business_date = date(2026, 6, 29)
    try:
        db.add(
            script.MultimodalEvidence(
                evidence_type="attachment",
                file_uri="dingtalk://media/daily-20260629",
                recognized_text="日报文件已上传",
                confirmation_status="human_confirmed",
                created_at=datetime(2026, 6, 29, 10, 0),
                payload={
                    "source": "dingtalk",
                    "file_name": "6月29日生产日报.xlsx",
                    "attachments": [
                        {
                            "parsed_text": (
                                "6月29日生产日报\n"
                                "车间总产量日合计100吨。\n"
                                "入库成品日合计98吨。\n"
                                "日成品率83.2%。"
                            )
                        }
                    ],
                },
            )
        )
        db.add(
            script.MultimodalEvidence(
                evidence_type="attachment",
                file_uri="dingtalk://media/machine-only-daily-20260629",
                recognized_text="机器采样文件",
                confirmation_status="machine_only",
                created_at=datetime(2026, 6, 29, 10, 5),
                payload={
                    "source": "dingtalk",
                    "file_name": "6月29日机器采样日报.txt",
                    "file_text": (
                        "6月29日生产日报\n"
                        "车间总产量日合计100吨。\n"
                        "入库成品日合计98吨。\n"
                        "日成品率83.2%。"
                    ),
                },
            )
        )
        db.commit()

        diagnostics = script._source_diagnostics(db, business_date, wip_date=business_date)
    finally:
        db.close()

    dingtalk = diagnostics["dingtalk"]
    assert dingtalk["status"] == "ready"
    assert dingtalk["all_file_payload_rows"] == 2
    assert dingtalk["machine_only_file_payload_rows"] == 1
    assert dingtalk["machine_only_parseable_file_payload_rows"] == 1
    assert dingtalk["confirmed_file_payload_rows"] == 1
    assert dingtalk["confirmed_file_payload_rows_in_business_window"] == 1
    assert dingtalk["parseable_file_payload_rows"] == 1
    assert dingtalk["parseable_file_payload_rows_in_business_window"] == 1


def test_energy_source_diagnostics_groups_rows_by_source(monkeypatch) -> None:
    def fake_summary(_db, *, business_date):
        assert business_date == date(2026, 6, 29)
        return {
            "primary_source": "mobile_shift_report",
            "output_basis": "mes_packaging_output",
            "electricity_value": 1200,
            "gas_value": 300,
            "total_energy": 1500,
            "total_output_weight": 100,
            "system_totals": {"row_count": 1, "total_energy": 800, "total_output_weight": 100},
            "owner_totals": {"row_count": 0, "total_energy": 0},
            "mobile_totals": {"row_count": 2, "total_energy": 1500, "total_output_weight": 100},
            "rows": [
                {"source": "mobile_shift_report", "electricity_value": 500, "gas_value": 100, "total_energy": 600},
                {"source": "mobile_shift_report", "electricity_value": 700, "gas_value": 200, "total_energy": 900},
                {"source": "energy_import", "electricity_value": 800, "gas_value": 0, "total_energy": 800},
            ],
        }

    monkeypatch.setattr(script.energy_service, "summarize_energy_for_date", fake_summary)

    diagnostics = script._energy_source_diagnostics(object(), date(2026, 6, 29))

    assert diagnostics["status"] == "ready"
    assert diagnostics["primary_source"] == "mobile_shift_report"
    assert diagnostics["electricity_value"] == 1200
    assert diagnostics["mobile_totals"]["row_count"] == 2
    assert diagnostics["rows_by_source"] == [
        {
            "source": "energy_import",
            "row_count": 1,
            "electricity_value": 800.0,
            "gas_value": 0.0,
            "water_value": 0.0,
            "total_energy": 800.0,
            "output_weight": 0.0,
        },
        {
            "source": "mobile_shift_report",
            "row_count": 2,
            "electricity_value": 1200.0,
            "gas_value": 300.0,
            "water_value": 0.0,
            "total_energy": 1500.0,
            "output_weight": 0.0,
        },
    ]
