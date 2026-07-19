from __future__ import annotations

from dataclasses import replace
import json

from app.domain import daily_report_field_contract as contract_module
from scripts import check_daily_report_field_contract as checker
from scripts import render_daily_report_field_contract as renderer
from scripts.hermes_fact_source_map_export import render_fact_source_map_markdown


def test_renderer_is_deterministic_and_contains_contract_boundaries() -> None:
    payload = renderer.build_contract_payload()

    first = renderer.render_contract_markdown(payload)
    second = renderer.render_contract_markdown(payload)

    assert first == second
    assert payload["contract_version"] == contract_module.DAILY_REPORT_FIELD_CONTRACT_VERSION
    assert payload["normative_field_count"] == 127
    assert payload["template_field_count"] == 130
    assert payload["maximum_tolerance"] == 20.0
    assert payload["business_time_starts"] == {"production_07_50": "07:50", "billet_10_00": "10:00"}
    assert payload["owner_daily_submission_time"] == "09:30"
    assert payload["owner_daily_late_time"] == "10:00"
    assert payload["source_order"] == list(contract_module.FACT_SOURCE_LANE_ORDER)
    assert len(payload["fields"]) == 127
    assert "D:\\输出skill" in first
    assert "compare-only" in first
    assert "RAG" in first
    assert "不能生成实时数字" in first


def test_renderer_check_mode_detects_missing_and_stale_document(tmp_path) -> None:
    output_path = tmp_path / "daily-report-field-contract.md"

    assert renderer.main(["--output", str(output_path), "--check"]) == 1
    assert renderer.main(["--output", str(output_path)]) == 0
    expected = output_path.read_text(encoding="utf-8")
    assert renderer.main(["--output", str(output_path), "--check"]) == 0

    output_path.write_text(expected + "stale\n", encoding="utf-8")
    assert renderer.main(["--output", str(output_path), "--check"]) == 1


def test_static_gate_json_is_machine_readable(tmp_path, capsys) -> None:
    document_path = tmp_path / "daily-report-field-contract.md"
    document_path.write_text(renderer.render_contract_markdown(), encoding="utf-8")

    exit_code = checker.main(["--document", str(document_path), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["passed"] is True
    assert payload["status"] == "pass"
    assert payload["contract_version"] == contract_module.DAILY_REPORT_FIELD_CONTRACT_VERSION
    assert payload["normative_field_count"] == 127
    assert payload["template_field_count"] == 130
    assert payload["maximum_tolerance"] == 20.0
    assert payload["document_fresh"] is True
    assert payload["issues"] == []


def test_static_gate_rejects_contract_and_document_drift() -> None:
    fields = list(contract_module.normative_daily_report_fields())
    contracts = dict(contract_module.DAILY_REPORT_FIELD_CONTRACTS)
    contracts[fields[0]] = replace(contracts[fields[0]], unit="", tolerance=21.0)
    contracts.pop(fields[1])
    business_times = dict(contract_module.BUSINESS_TIME_STARTS)
    business_times[contract_module.BUSINESS_TIME_STANDARD] = "25:99"

    issues = checker.collect_contract_issues(
        fields=[*fields, fields[0]],
        contracts=contracts,
        business_time_starts=business_times,
        owner_daily_submission_time="25:00",
        owner_daily_late_time="09:00",
        source_order=tuple(reversed(contract_module.FACT_SOURCE_LANE_ORDER)),
        check_document=False,
    )
    codes = {item["code"] for item in issues}

    assert "field_count_mismatch" in codes
    assert "duplicate_fields" in codes
    assert "contract_field_mismatch" in codes
    assert "invalid_unit" in codes
    assert "tolerance_above_maximum" in codes
    assert "business_time_drift" in codes
    assert "owner_time_drift" in codes
    assert "source_order_drift" in codes


def test_fact_source_map_links_to_generated_daily_contract() -> None:
    markdown = render_fact_source_map_markdown()

    assert "[日报 127 字段合同](daily-report-field-contract.md)" in markdown
