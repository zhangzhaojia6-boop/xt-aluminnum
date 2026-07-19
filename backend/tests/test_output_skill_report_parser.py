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


def test_contract_outsourced_input_does_not_reuse_outsourced_output() -> None:
    parsed = parse_output_skill_daily_report(
        "7月16日，车间总产量日合计344吨（外加工76吨）。"
        "冷轧日投料460吨（2050投386吨、1850投5吨、外加工69吨），中厚板106吨。"
    )

    assert parsed["outsourced_daily"] == 76
    assert parsed["outsourced_input_daily"] == 69


def test_energy_per_ton_parser_stays_inside_each_workshop_segment() -> None:
    parsed = parse_output_skill_daily_report(
        "铸轧分厂日产量81吨，月累计产量1607吨；铸锭车间日产量310吨，"
        "月累计产量4789吨；热轧车间日产量346吨，月累计产量4251吨。"
        "铸轧分厂日吨电耗84.1度，月吨电耗81.0度，日吨气耗137.3m³，月吨气耗119.5m³；"
        "铸锭车间日吨电耗28.6度，月吨电耗30.9度，日吨气耗79.2m³，月吨气耗94.3m³；"
        "热轧车间日吨电耗128.4度，月吨电耗136.5度，日吨气耗28.6m³，月吨气耗29.8m³。"
    )

    assert parsed["cast_roll_gas_per_ton_daily"] == 137.3
    assert parsed["cast_roll_gas_per_ton_month"] == 119.5
    assert parsed["foundry_gas_per_ton_daily"] == 79.2
    assert parsed["foundry_gas_per_ton_month"] == 94.3
    assert parsed["hot_roll_gas_per_ton_daily"] == 28.6
    assert parsed["hot_roll_gas_per_ton_month"] == 29.8
