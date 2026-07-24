from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Workshop
from app.models.mes import MesMaterialRecord, MesWorkshopProcessRecord
from app.models.production import WorkOrder, WorkOrderEntry
from app.services.report import template_daily_report


REPORT_DATE = date(2026, 6, 16)


def _template_text() -> str:
    return (Path(__file__).resolve().parents[1].parent / "docs" / "模板.md").read_text(encoding="utf-8").strip()


def _complete_values() -> dict:
    return {
        "report_date": REPORT_DATE,
        "total_output_daily": 328,
        "outsourced_daily": 0,
        "total_output_delta": 22,
        "total_output_month": 5014,
        "outsourced_month": 270,
        "cast_roll_active_lines": 4,
        "cast_roll_daily": 81,
        "cast_roll_month": 1340,
        "foundry_daily": 346,
        "foundry_month": 4672,
        "hot_roll_daily": 275,
        "hot_roll_month": 4215,
        "cold_1650_daily": 144,
        "cold_1650_month": 2529,
        "cold_1650_pass_daily": 55,
        "cold_1650_pass_month": 799,
        "cold_1850_daily": 33,
        "cold_1850_month": 699,
        "cold_1850_pass_daily": 15,
        "cold_1850_pass_month": 347,
        "cold_2050_daily": 96,
        "cold_2050_month": 2103,
        "cold_2050_pass_daily": 33,
        "cold_2050_pass_month": 1190,
        "rolling_daily": 272,
        "rolling_month": 5331,
        "rolling_pass_daily": 103,
        "rolling_pass_month": 2336,
        "online_anneal_daily": 253,
        "online_anneal_month": 5255,
        "straightening_daily": 188,
        "straightening_month": 2426,
        "finishing_daily": 86,
        "finishing_month": 1384,
        "shearing_daily": 87,
        "shearing_month": 1268,
        "coating_daily": 0,
        "coating_month": 0,
        "recovery_daily": 63,
        "recovery_month": 1123,
        "roller_grind_daily": 8,
        "roller_grind_month": 144,
        "wip_total": 879,
        "wip_1650_2050_cold": 63.5,
        "wip_1850_cold": 10.5,
        "wip_milling": 0,
        "wip_anneal_total": 228.5,
        "wip_new_north": 122,
        "wip_new_south": 26,
        "wip_park_anneal": 80.5,
        "wip_finishing_total": 576.5,
        "wip_straightening": 276,
        "wip_finishing": 250,
        "wip_park_finishing": 50.5,
        "wip_hot_plate_shearing": 0,
        "wip_coating": 0,
        "total_electricity_kwh": 168000,
        "subitem_electricity_kwh": 166533,
        "cast_roll_gas_m3": 12003,
        "cast_2_gas_m3": 4678,
        "cast_3_gas_m3": 7325,
        "smelting_gas_m3": 24554,
        "recovery_gas_m3": 1426,
        "hot_roll_furnace_gas_m3": 8194,
        "east_furnace_gas_m3": 4382,
        "west_furnace_gas_m3": 3812,
        "hot_roll_boiler_gas_m3": 1094,
        "anneal_gas_m3": 4209,
        "straightening_boiler_gas_m3": 1448,
        "new_north_gas_m3": 2804,
        "new_south_gas_m3": 0,
        "coating_gas_m3": 2034,
        "canteen_gas_m3": 10,
        "total_gas_m3": 57776,
        "cast_roll_electricity_per_ton_daily": 96.7,
        "cast_roll_electricity_per_ton_month": 80.6,
        "cast_roll_gas_per_ton_daily": 148.1,
        "cast_roll_gas_per_ton_month": 121.3,
        "foundry_electricity_per_ton_daily": 24.3,
        "foundry_electricity_per_ton_month": 28.0,
        "foundry_gas_per_ton_daily": 71.0,
        "foundry_gas_per_ton_month": 81.6,
        "hot_roll_electricity_per_ton_daily": 158.4,
        "hot_roll_electricity_per_ton_month": 131.7,
        "hot_roll_gas_per_ton_daily": 29.8,
        "hot_roll_gas_per_ton_month": 26.7,
        "cold_1650_electricity_per_ton_daily": 111.8,
        "cold_1650_electricity_per_ton_month": 83.6,
        "cold_1850_electricity_per_ton_daily": 117.8,
        "cold_1850_electricity_per_ton_month": 108.5,
        "cold_2050_electricity_per_ton_daily": 110.9,
        "cold_2050_electricity_per_ton_month": 152.8,
        "online_anneal_electricity_per_ton_daily": 66.9,
        "online_anneal_electricity_per_ton_month": 55.0,
        "straightening_electricity_per_ton_daily": 14.5,
        "straightening_electricity_per_ton_month": 16.5,
        "finishing_electricity_per_ton_daily": 11.5,
        "finishing_electricity_per_ton_month": 8.6,
        "shearing_electricity_per_ton_daily": 14.9,
        "shearing_electricity_per_ton_month": 15.6,
        "coating_electricity_per_ton_daily": 0.0,
        "coating_electricity_per_ton_month": 0.0,
        "coating_gas_per_ton_daily": 0.0,
        "coating_gas_per_ton_month": 0.0,
        "finished_inbound_daily": 328,
        "consignment_weight": 161,
        "finished_inbound_month": 5014,
        "daily_contract_weight": 66,
        "daily_hot_roll_contract_weight": 66,
        "cold_roll_input_daily": 197,
        "cold_2050_input_daily": 197,
        "cold_1850_input_daily": 0,
        "outsourced_input_daily": 0,
        "medium_plate_input_daily": 137,
        "remaining_contract_weight": 2569,
        "remaining_contract_delta": -130,
        "daily_yield_rate": 84.86,
        "daily_yield_delta": -1.38,
        "hot_roll_yield_rate": 84.86,
        "hot_roll_yield_delta": -0.92,
        "monthly_yield_rate": 86.00,
        "cast_roll_yield_rate": 92.02,
        "plate_coil_yield_rate": 92.02,
        "hot_roll_monthly_yield_rate": 84.46,
        "electricity_cost_10k": 13.44,
        "gas_cost_10k": 20.80,
        "total_cost_10k": 34.24,
        "cost_basis_weight": 328.033,
        "cost_per_ton": 1044,
    }


def _facts(values: dict | None = None) -> dict:
    payload = dict(_complete_values())
    if values:
        payload.update(values)
    return {
        "target_date": REPORT_DATE.isoformat(),
        "values": payload,
        "sources": {key: {"source_type": "test"} for key in payload},
        "missing_fields": [],
        "conflicts": [],
    }


def test_render_template_daily_report_matches_locked_template() -> None:
    text = template_daily_report.render_template_daily_report(_facts())

    assert text == _template_text()


def test_validate_template_daily_report_blocks_missing_fields_without_rendering_text() -> None:
    facts = _facts()
    facts["values"].pop("total_output_daily")
    facts["values"].pop("wip_total")

    result = template_daily_report.validate_template_daily_report_facts(facts)

    assert result["status"] == "blocked"
    assert "total_output_daily" in result["missing_fields"]
    assert "wip_total" in result["missing_fields"]
    assert result["text"] is None


def test_validate_template_daily_report_blocks_conflicts_without_rendering_text() -> None:
    facts = _facts()
    facts["conflicts"] = [{"field": "total_output_daily", "reason": "source_mismatch"}]

    result = template_daily_report.validate_template_daily_report_facts(facts)

    assert result["status"] == "blocked"
    assert result["missing_fields"] == []
    assert result["conflicts"] == facts["conflicts"]
    assert result["text"] is None


def test_optional_display_fields_do_not_block_or_render_placeholders() -> None:
    facts = _facts()
    facts["values"].pop("cast_roll_active_lines")
    facts["values"].pop("finished_inbound_month")

    result = template_daily_report.validate_template_daily_report_facts(facts)

    assert result["status"] == "ready"
    assert "cast_roll_active_lines" not in result["missing_fields"]
    assert "finished_inbound_month" not in result["missing_fields"]
    assert "铸轧分厂日产量81吨" in result["text"]
    assert "铸轧分厂开机" not in result["text"]
    assert "入库成品日合计328吨（寄存161吨）。当天接合同" in result["text"]


def test_all_template_required_fields_have_contract_metadata() -> None:
    from app.services.report.template_daily_field_contract import field_group

    missing = [key for key in template_daily_report.REQUIRED_FIELDS if field_group(key) == "unclassified"]

    assert missing == []


def test_build_facts_uses_manual_final_output_and_ignores_raw_mes_process_values(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'template-daily-report.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            MesMaterialRecord.__table__,
            MesWorkshopProcessRecord.__table__,
        ],
    )
    SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    with SessionLocal() as db:
        db.add_all(
            [
                Workshop(id=1, code="HR", name="热轧车间", workshop_type="hot_roll", is_active=True),
                Workshop(id=2, code="C1650", name="1650车间", workshop_type="cold_roll", is_active=True),
                WorkOrder(id=1, tracking_card_no="HR-1", process_route_code="manual"),
                WorkOrder(id=3, tracking_card_no="HR-2", process_route_code="manual"),
                WorkOrderEntry(
                    work_order_id=1,
                    workshop_id=1,
                    business_date=REPORT_DATE,
                    input_weight=88000,
                    output_weight=0,
                    entry_type="mobile_coil",
                    entry_status="submitted",
                    submitted_at=datetime(2026, 6, 16, 8, 0),
                ),
                WorkOrderEntry(
                    work_order_id=3,
                    workshop_id=1,
                    business_date=REPORT_DATE,
                    input_weight=12000,
                    output_weight=0,
                    entry_type="mobile_coil",
                    entry_status="submitted",
                    submitted_at=datetime(2026, 6, 17, 8, 0),
                ),
                MesWorkshopProcessRecord(
                    source_id="mes-hot-roll",
                    source_path="sqlserver",
                    workshop_name="热轧车间",
                    process_name="热轧",
                    output_weight_tons=12,
                    business_date=REPORT_DATE,
                ),
                MesMaterialRecord(
                    source_id="mat-hot-roll",
                    source_path="sqlserver:material_records",
                    material_code="mat-hot-roll",
                    workshop_name="热轧车间",
                    line_name="1#",
                    weight_kg=88000,
                    weight_tons=88,
                    production_date=datetime(2026, 6, 16, 8, 0),
                ),
                MesMaterialRecord(
                    source_id="mat-hot-roll-next",
                    source_path="sqlserver:material_records",
                    material_code="mat-hot-roll-next",
                    workshop_name="热轧车间",
                    line_name="1#",
                    weight_kg=12000,
                    weight_tons=12,
                    production_date=datetime(2026, 6, 17, 8, 0),
                ),
                MesWorkshopProcessRecord(
                    source_id="mes-1650",
                    source_path="sqlserver",
                    workshop_name="1650车间",
                    process_name="冷轧",
                    output_weight_tons=33,
                    business_date=REPORT_DATE,
                ),
            ]
        )
        db.commit()

    with SessionLocal() as db:
        facts = template_daily_report.build_template_daily_report_facts(db, target_date=REPORT_DATE)

    assert facts["values"]["hot_roll_daily"] == 0.0
    assert facts["sources"]["hot_roll_daily"]["source_type"] == "manual_mobile_coil"
    assert facts["sources"]["hot_roll_daily"]["business_window"] == (
        "2026-06-16T10:00:00+08:00/2026-06-17T10:00:00+08:00"
    )
    assert "cold_1650_daily" not in facts["values"]
    assert "cold_1650_daily" not in facts["sources"]
    assert "cold_1650_daily" in facts["missing_fields"]
    assert "coating_daily" not in facts["values"]
    assert "coating_daily" not in facts["sources"]
    assert "coating_daily" in facts["missing_fields"]


def test_apply_template_daily_report_stores_slim_hermes_bundle(monkeypatch) -> None:
    monkeypatch.setattr(
        template_daily_report,
        "build_template_daily_report_payload",
        lambda *_args, **_kwargs: {
            "status": "ready",
            "text": "日报正文",
            "wip_date": None,
            "missing_fields": [],
            "conflicts": [],
            "sources": {},
            "hermes_fact_bundle": {
                "target_date": REPORT_DATE.isoformat(),
                "source": "template_daily_report_facts",
                "facts": [
                    {
                        "key": "total_output_daily",
                        "label": "车间总产量日合计",
                        "value": 328,
                        "unit": "吨",
                        "group": "opening",
                        "business_date": REPORT_DATE.isoformat(),
                        "source": {"source_type": "mes_packaging_output", "source_table": "MES_ProductProcessRecord"},
                        "difference_note": "核对业务日。",
                    }
                ],
                "mes_fact_bundle": {"audit_gaps": [{"key": "follow_card_page_total_feeding"}], "debug": {"raw": True}},
            },
        },
    )
    report = SimpleNamespace(report_data={}, final_text_summary=None)

    template_daily_report.apply_template_daily_report_to_report(
        SimpleNamespace(),
        report=report,
        target_date=REPORT_DATE,
    )

    stored = report.report_data[template_daily_report.TEMPLATE_REPORT_KEY]["hermes_fact_bundle"]
    assert stored["facts"][0]["key"] == "total_output_daily"
    assert stored["facts"][0]["source_type"] == "mes_packaging_output"
    assert "source" not in stored["facts"][0]
    assert "mes_fact_bundle" not in stored
