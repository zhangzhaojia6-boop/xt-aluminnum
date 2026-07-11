from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Workshop
from app.models.mes import MesCoilSnapshot, MesDailyWipSnapshot, MesMaterialRecord, MesWipTotalSnapshot, MesWorkshopProcessRecord
from app.models.production import WorkOrder, WorkOrderEntry
from app.models.quality import QualityYieldDaily
from app.models.reports import DailyReport, DailyReportHistoryRecord
from app.services.report import template_daily_fact_sources
from app.services.report.template_daily_fact_sources import collect_template_daily_facts
from app.services.report.template_daily_report import REQUIRED_FIELDS


REPORT_DATE = date(2026, 6, 16)


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'template-daily-facts.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            MesMaterialRecord.__table__,
            MesWorkshopProcessRecord.__table__,
            MesWipTotalSnapshot.__table__,
            DailyReport.__table__,
            DailyReportHistoryRecord.__table__,
            QualityYieldDaily.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _seed_workshop_and_order(db):
    db.add_all(
        [
            Workshop(id=1, code="OWNER", name="日报负责人", workshop_type="owner", is_active=True),
            Workshop(id=2, code="HR", name="热轧车间", workshop_type="hot_roll", is_active=True),
            WorkOrder(id=1, tracking_card_no="OWNER-1", process_route_code="owner"),
            WorkOrder(id=2, tracking_card_no="HR-1", process_route_code="manual"),
        ]
    )


def _seed_owner_daily_payload(db, payload: dict):
    db.add(
        WorkOrderEntry(
            work_order_id=1,
            workshop_id=1,
            business_date=REPORT_DATE,
            entry_type="owner_daily",
            entry_status="submitted",
            extra_payload=payload,
        )
    )


def _seed_mes_process(db, *, source_id: str, text: str, output_tons: float, pass_count: int | None = None):
    db.add(
        MesWorkshopProcessRecord(
            source_id=source_id,
            source_path="sqlserver",
            workshop_name=text,
            process_name=text,
            device_name=text,
            output_weight_tons=output_tons,
            business_date=REPORT_DATE,
            source_payload={"pass_count": pass_count} if pass_count is not None else {},
        )
    )


def _seed_mes_material(
    db,
    *,
    source_id: str,
    workshop: str,
    line: str,
    weight_tons: float,
    production_date: datetime,
    status_name: str | None = None,
):
    db.add(
        MesMaterialRecord(
            source_id=source_id,
            source_path="sqlserver:material_records",
            material_code=source_id,
            workshop_name=workshop,
            line_name=line,
            weight_kg=weight_tons * 1000,
            weight_tons=weight_tons,
            production_date=production_date,
            status_name=status_name,
        )
    )


def test_source_priority_covers_current_template_fact_sources() -> None:
    expected_source_types = {
        "runtime_target_date",
        "mes_packaging_output",
        "mes_stock_header_records",
        "finished_inbound_output",
        "datahub_final_daily_report",
        "mes_delivery_records",
        "mes_wip_distribution",
        "mes_wip_total_snapshot",
        "contract_projection",
        "yield_projection",
        "owner_or_energy_summary",
        "energy_cost",
        "manual_mobile_coil",
        "owner_daily_month_sum",
        "quality_yield_daily",
        "recovery_daily",
        "overhaul_daily",
        "previous_final_report",
        "computed",
        "mes_stock_records",
        "mes_stock_records_missing",
        "mes_material_records",
        "mes_workshop_process_records",
        "owner_daily",
        "manual_workbook",
        "wms_direct",
        "mes_verified",
        "mes_evidence",
    }

    missing = expected_source_types - set(template_daily_fact_sources.SOURCE_PRIORITY)

    assert missing == set()


def test_set_value_keeps_owner_daily_when_lower_priority_mes_evidence_arrives() -> None:
    facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)

    template_daily_fact_sources._set_value(facts, "cold_1650_daily", 130.01, "owner_daily")
    template_daily_fact_sources._set_value(facts, "cold_1650_daily", 166.417, "mes_evidence")

    assert facts.values["cold_1650_daily"] == 130.01
    assert facts.sources["cold_1650_daily"]["source_type"] == "owner_daily"


def test_set_value_allows_same_priority_source_to_overwrite() -> None:
    facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)

    template_daily_fact_sources._set_value(facts, "finished_inbound_daily", 366, "manual_workbook")
    template_daily_fact_sources._set_value(facts, "finished_inbound_daily", 382, "manual_workbook")

    assert facts.values["finished_inbound_daily"] == 382
    assert facts.sources["finished_inbound_daily"]["source_type"] == "manual_workbook"


def test_set_value_keeps_high_priority_zero_against_lower_priority_source() -> None:
    facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)

    template_daily_fact_sources._set_value(facts, "total_output_daily", 0, "owner_daily")
    template_daily_fact_sources._set_value(facts, "total_output_daily", 999, "mes_packaging_output")

    assert facts.values["total_output_daily"] == 0
    assert facts.sources["total_output_daily"]["source_type"] == "owner_daily"


def test_wip_snapshot_weight_keeps_ton_values_and_converts_kg_values() -> None:
    assert template_daily_fact_sources._wip_snapshot_weight_tons(279.5) == 279.5
    assert template_daily_fact_sources._wip_snapshot_weight_tons(264254.65) == 264.25465


def test_datahub_final_daily_report_overrides_lower_priority_projection(tmp_path, monkeypatch) -> None:
    SessionLocal = _session(tmp_path)

    def fake_overview(_db, *, target_date: date, wip_date: date | None = None):
        return {
            "plant_output": {
                "daily_output": 111,
                "monthly_output": 111,
                "yesterday_output": 100,
            },
            "contracts": {},
            "yield_rates": {},
            "energy": {},
            "cost": {},
            "wip_distribution": [],
        }

    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "build_daily_production_overview",
        fake_overview,
    )
    monkeypatch.setattr(template_daily_fact_sources, "_wip_breakdown_from_total_snapshots", lambda *_args: {})

    report_text = (
        "6月16日，车间总产量日合计328吨（外加工0吨）比昨日↑22吨，"
        "月累计5014吨（外加工月累计270吨）。"
    )
    with SessionLocal() as db:
        db.add(
            DailyReport(
                report_date=REPORT_DATE,
                report_type="production",
                final_text_summary=report_text,
                is_final_version=True,
            )
        )
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["total_output_daily"] == 328
    assert facts.values["total_output_month"] == 5014
    assert facts.sources["total_output_daily"]["source_type"] == "datahub_final_daily_report"
    assert facts.sources["total_output_daily"]["source_table"] == "daily_reports"


def test_datahub_template_daily_report_text_is_used_when_ready(tmp_path, monkeypatch) -> None:
    SessionLocal = _session(tmp_path)
    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "build_daily_production_overview",
        lambda *_args, **_kwargs: {
            "plant_output": {"daily_output": 111, "monthly_output": 111},
            "contracts": {},
            "yield_rates": {},
            "energy": {},
            "cost": {},
            "wip_distribution": [],
        },
    )
    monkeypatch.setattr(template_daily_fact_sources, "_wip_breakdown_from_total_snapshots", lambda *_args: {})

    report_text = (
        "6月16日，车间总产量日合计328吨（外加工0吨）比昨日↑22吨，"
        "月累计5014吨（外加工月累计270吨）。"
    )
    with SessionLocal() as db:
        db.add(
            DailyReport(
                report_date=REPORT_DATE,
                report_type="production",
                report_data={
                    "template_daily_report": {
                        "status": "ready",
                        "text": report_text,
                    }
                },
            )
        )
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["total_output_daily"] == 328
    assert facts.values["total_output_month"] == 5014
    assert facts.sources["total_output_daily"]["source_type"] == "datahub_final_daily_report"
    assert facts.sources["total_output_daily"]["source_payload_key"] == "template_daily_report"


def test_datahub_template_daily_report_text_is_ignored_when_blocked(tmp_path, monkeypatch) -> None:
    SessionLocal = _session(tmp_path)
    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "build_daily_production_overview",
        lambda *_args, **_kwargs: {
            "plant_output": {"daily_output": 111, "monthly_output": 111},
            "contracts": {},
            "yield_rates": {},
            "energy": {},
            "cost": {},
            "wip_distribution": [],
        },
    )
    monkeypatch.setattr(template_daily_fact_sources, "_wip_breakdown_from_total_snapshots", lambda *_args: {})

    with SessionLocal() as db:
        db.add(
            DailyReport(
                report_date=REPORT_DATE,
                report_type="production",
                report_data={
                    "template_daily_report": {
                        "status": "blocked",
                        "text": "6月16日，车间总产量日合计328吨。",
                    }
                },
            )
        )
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["total_output_daily"] == 111
    assert facts.sources["total_output_daily"]["source_type"] != "datahub_final_daily_report"


def test_contract_projection_daily_input_fills_cold_roll_input(tmp_path, monkeypatch) -> None:
    SessionLocal = _session(tmp_path)
    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "build_daily_production_overview",
        lambda *_args, **_kwargs: {
            "plant_output": {},
            "contracts": {"daily_input": 237.0},
            "yield_rates": {},
            "energy": {},
            "cost": {},
            "wip_distribution": [],
        },
    )
    monkeypatch.setattr(template_daily_fact_sources, "_wip_breakdown_from_total_snapshots", lambda *_args: {})

    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["cold_roll_input_daily"] == 237.0
    assert facts.sources["cold_roll_input_daily"]["source_type"] == "contract_projection"


def test_total_output_stays_packaging_when_finished_inbound_diverges(tmp_path, monkeypatch) -> None:
    SessionLocal = _session(tmp_path)
    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "build_daily_production_overview",
        lambda *_args, **_kwargs: {
            "plant_output": {
                "daily_output": 6.5,
                "monthly_output": 372.0,
                "yesterday_output": 5.0,
                "finished_inbound_output": 53.24,
                "finished_inbound_monthly_output": 405.0,
                "finished_inbound_source": "mes_stock_header_records",
            },
            "contracts": {},
            "yield_rates": {},
            "energy": {},
            "cost": {"total": 4.0, "cost_per_ton": 203.0, "basis_weight": 6.5},
            "wip_distribution": [],
        },
    )
    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "_query_finished_inbound_totals_by_date",
        lambda *_args, **_kwargs: {REPORT_DATE - timedelta(days=1): 177.6},
    )
    monkeypatch.setattr(template_daily_fact_sources, "_wip_breakdown_from_total_snapshots", lambda *_args: {})

    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["total_output_daily"] == 6.5
    assert facts.values["total_output_month"] == 372.0
    assert facts.values["total_output_delta"] == 1.5
    assert facts.sources["total_output_daily"]["source_type"] == "mes_packaging_output"
    assert facts.values["finished_inbound_daily"] == 53.24
    assert facts.sources["finished_inbound_daily"]["source_type"] == "mes_stock_header_records"
    assert facts.values["cost_basis_weight"] == 6.5
    assert facts.values["cost_per_ton"] == 203.0


def test_total_output_delta_falls_back_to_previous_packaging_when_overview_yesterday_missing(tmp_path, monkeypatch) -> None:
    SessionLocal = _session(tmp_path)
    previous_date = REPORT_DATE - timedelta(days=1)
    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "build_daily_production_overview",
        lambda *_args, **_kwargs: {
            "plant_output": {
                "daily_output": 174.4,
                "monthly_output": 174.4,
                "yesterday_output": 0.0,
                "finished_inbound_output": 177.6,
                "finished_inbound_monthly_output": 177.6,
                "finished_inbound_source": "mes_stock_header_records",
            },
            "contracts": {},
            "yield_rates": {},
            "energy": {},
            "cost": {},
            "wip_distribution": [],
        },
    )
    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "_query_mes_packaging_output_by_date",
        lambda *_args, **_kwargs: {previous_date: 347.4},
    )
    monkeypatch.setattr(template_daily_fact_sources, "_wip_breakdown_from_total_snapshots", lambda *_args: {})

    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["total_output_daily"] == 174.4
    assert facts.values["total_output_delta"] == -173.0
    assert facts.sources["total_output_delta"]["source_type"] == "mes_packaging_output"


def test_total_output_delta_prefers_previous_packaging_when_current_day_has_inbound(tmp_path, monkeypatch) -> None:
    SessionLocal = _session(tmp_path)
    previous_date = REPORT_DATE - timedelta(days=1)
    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "build_daily_production_overview",
        lambda *_args, **_kwargs: {
            "plant_output": {
                "daily_output": 174.4,
                "monthly_output": 174.4,
                "yesterday_output": 0.0,
                "finished_inbound_output": 177.6,
                "finished_inbound_monthly_output": 177.6,
                "finished_inbound_source": "mes_stock_header_records",
            },
            "contracts": {},
            "yield_rates": {},
            "energy": {},
            "cost": {},
            "wip_distribution": [],
        },
    )
    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "_query_finished_inbound_totals_by_date",
        lambda *_args, **_kwargs: {previous_date: 347.4},
    )
    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "_query_mes_packaging_output_by_date",
        lambda *_args, **_kwargs: {previous_date: 285.6},
    )
    monkeypatch.setattr(template_daily_fact_sources, "_wip_breakdown_from_total_snapshots", lambda *_args: {})

    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["total_output_delta"] == -111.2


def test_owner_daily_keeps_priority_over_datahub_final_daily_report(tmp_path, monkeypatch) -> None:
    SessionLocal = _session(tmp_path)

    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "build_daily_production_overview",
        lambda *_args, **_kwargs: {
            "plant_output": {},
            "contracts": {},
            "yield_rates": {},
            "energy": {},
            "cost": {},
            "wip_distribution": [],
        },
    )
    monkeypatch.setattr(template_daily_fact_sources, "_wip_breakdown_from_total_snapshots", lambda *_args: {})

    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        _seed_owner_daily_payload(db, {"total_output_daily": 400})
        db.add(
            DailyReportHistoryRecord(
                report_type="daily",
                business_date=REPORT_DATE,
                report_text=(
                    "6月16日，车间总产量日合计328吨（外加工0吨）比昨日↑22吨，"
                    "月累计5014吨（外加工月累计270吨）。"
                ),
                report_payload={},
                source_summary={},
                facts_hash="facts",
                text_hash="text",
            )
        )
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["total_output_daily"] == 400
    assert facts.values["total_output_month"] == 5014
    assert facts.sources["total_output_daily"]["source_type"] == "owner_daily"
    assert facts.sources["total_output_month"]["source_type"] == "datahub_final_daily_report"


def test_hot_roll_daily_uses_mes_material_business_window(tmp_path) -> None:
    SessionLocal = _session(tmp_path)
    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        _seed_owner_daily_payload(db, {"hot_roll_daily": 275})
        _seed_mes_process(db, source_id="hot-roll-mes", text="热轧", output_tons=123)
        db.add_all(
            [
                WorkOrder(id=3, tracking_card_no="HR-2", process_route_code="manual"),
                WorkOrder(id=4, tracking_card_no="HR-3", process_route_code="manual"),
                WorkOrderEntry(
                    work_order_id=2,
                    workshop_id=2,
                    business_date=REPORT_DATE,
                    input_weight=11000,
                    output_weight=0,
                    entry_type="mobile_coil",
                    entry_status="submitted",
            submitted_at=datetime(2026, 6, 16, 9, 59),
                ),
                WorkOrderEntry(
                    work_order_id=3,
                    workshop_id=2,
                    business_date=REPORT_DATE,
                    input_weight=70000,
                    output_weight=0,
                    entry_type="mobile_coil",
                    entry_status="submitted",
            submitted_at=datetime(2026, 6, 16, 10, 0),
                ),
                WorkOrderEntry(
                    work_order_id=4,
                    workshop_id=2,
                    business_date=REPORT_DATE,
                    input_weight=12000,
                    output_weight=0,
                    entry_type="mobile_coil",
                    entry_status="submitted",
            submitted_at=datetime(2026, 6, 17, 10, 0),
                ),
            ]
        )
        _seed_mes_material(
            db,
            source_id="hot-before-window",
            workshop="热轧车间",
            line="1#",
            weight_tons=11,
            production_date=datetime(2026, 6, 16, 9, 59),
        )
        _seed_mes_material(
            db,
            source_id="hot-in-window",
            workshop="热轧车间",
            line="1#",
            weight_tons=70,
            production_date=datetime(2026, 6, 16, 10, 0),
            status_name="已使用",
        )
        _seed_mes_material(
            db,
            source_id="hot-invalid-status",
            workshop="热轧车间",
            line="1#",
            weight_tons=999,
            production_date=datetime(2026, 6, 16, 11, 0),
            status_name="作废",
        )
        _seed_mes_material(
            db,
            source_id="hot-window-end",
            workshop="热轧车间",
            line="1#",
            weight_tons=12,
            production_date=datetime(2026, 6, 17, 10, 0),
        )
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["hot_roll_daily"] == 70
    assert facts.sources["hot_roll_daily"]["source_type"] == "mes_material_records"


def test_template_daily_facts_default_to_next_day_wip_snapshot(monkeypatch) -> None:
    seen: dict[str, date] = {}

    def fake_overview(_db, *, target_date: date, wip_date: date | None = None):
        seen["target_date"] = target_date
        seen["wip_date"] = wip_date
        return {
            "plant_output": {},
            "contracts": {},
            "yield_rates": {},
            "energy": {},
            "cost": {},
            "wip_business_date": wip_date.isoformat() if wip_date else None,
            "wip_distribution": [{"total_weight": 879.0}],
        }

    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "build_daily_production_overview",
        fake_overview,
    )
    monkeypatch.setattr(template_daily_fact_sources, "_owner_daily_payload_values", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(template_daily_fact_sources, "_copy_owner_values", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(template_daily_fact_sources, "collect_owner_rollup_facts", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(template_daily_fact_sources, "collect_manual_workshop_facts", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(template_daily_fact_sources, "collect_mes_workshop_facts", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(template_daily_fact_sources, "collect_recovery_and_overhaul_facts", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(template_daily_fact_sources, "collect_quality_yield_facts", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(template_daily_fact_sources, "collect_yesterday_comparison_facts", lambda *_args, **_kwargs: None)

    facts = template_daily_fact_sources.collect_template_daily_facts(
        object(),
        target_date=date(2026, 6, 16),
        required_fields=("wip_total",),
    )

    assert seen == {"target_date": date(2026, 6, 16), "wip_date": date(2026, 6, 17)}
    assert facts.values["wip_total"] == 879.0
    assert facts.sources["wip_total"]["business_date"] == "2026-06-17"
    assert facts.as_dict()["wip_date"] == "2026-06-17"


def test_opening_facts_do_not_publish_impossible_yield_projection(monkeypatch) -> None:
    def fake_overview(_db, *, target_date: date, wip_date: date | None = None):
        return {
            "plant_output": {},
            "contracts": {},
            "yield_rates": {"daily": 1741.86, "monthly": 233.26},
            "energy": {},
            "cost": {},
            "wip_distribution": [],
        }

    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "build_daily_production_overview",
        fake_overview,
    )
    monkeypatch.setattr(template_daily_fact_sources, "_wip_breakdown_from_total_snapshots", lambda *_args: {})

    facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
    template_daily_fact_sources.collect_opening_facts(object(), facts)

    assert "daily_yield_rate" not in facts.values
    assert "monthly_yield_rate" not in facts.values


def test_opening_facts_fill_wip_breakdown_from_current_wip_total_snapshot(tmp_path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'template-daily-wip-breakdown.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesWipTotalSnapshot.__table__])
    SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    with SessionLocal() as db:
        rows = [
            ("1650车间", "冷轧", 8190.5),
            ("2050车间", "冷轧", 17542.2),
            ("1850车间", "冷轧", 14612.9),
            ("铣床车间", "铣床", 1010.5),
            ("在线车间", "北线退火", 5192.0),
            ("新厂在线车间", "南线退火", 5738.8),
            ("园区在线车间", "在线退火", 15612.4),
            ("拉矫车间", "包装", 258865.8),
            ("精整", "包装", 264254.65),
            ("园区精整", "包装", 227786.28),
            ("热轧", "中厚板剪切", 1206.5),
            ("彩涂", "本厂滚涂", 3652.0),
        ]
        db.add_all(
            [
                MesWipTotalSnapshot(
                    source_id=f"{workshop}:{process}",
                    workshop_name=workshop,
                    process_name=process,
                    doing_count=1,
                    doing_weight_tons=weight,
                    snapshot_at=datetime(2026, 6, 17, 8, 0, tzinfo=UTC),
                )
                for workshop, process, weight in rows
            ]
        )
        db.commit()

    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "build_daily_production_overview",
        lambda *_args, **_kwargs: {
            "plant_output": {},
            "contracts": {},
            "yield_rates": {},
            "energy": {},
            "cost": {},
            "wip_business_date": "2026-06-17",
            "wip_distribution": [],
        },
    )

    with SessionLocal() as db:
        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        template_daily_fact_sources.collect_opening_facts(db, facts, wip_date=date(2026, 6, 17))

    assert facts.values["wip_1650_2050_cold"] == 25.733
    assert facts.values["wip_1850_cold"] == 14.613
    assert facts.values["wip_milling"] == 1.01
    assert facts.values["wip_anneal_total"] == 26.543
    assert facts.values["wip_finishing_total"] == 750.907
    assert facts.values["wip_hot_plate_shearing"] == 1.206
    assert facts.values["wip_coating"] == 3.652
    assert facts.values["wip_total"] == 823.665
    assert facts.sources["wip_total"]["business_date"] == "2026-06-17"


def test_opening_facts_prefer_daily_wip_snapshot_for_historical_breakdown(tmp_path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'template-daily-wip-daily-first.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesDailyWipSnapshot.__table__, MesWipTotalSnapshot.__table__])
    SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    with SessionLocal() as db:
        db.add_all(
            [
                MesDailyWipSnapshot(
                    business_date=date(2026, 6, 17),
                    workshop_name="1650车间",
                    process_name="冷轧",
                    coil_count=10,
                    material_weight_tons=279.5,
                    source="mes_coil_snapshot",
                ),
                MesDailyWipSnapshot(
                    business_date=date(2026, 6, 17),
                    workshop_name="1850车间",
                    process_name="冷轧",
                    coil_count=4,
                    material_weight_tons=87.5,
                    source="mes_coil_snapshot",
                ),
                MesDailyWipSnapshot(
                    business_date=date(2026, 6, 17),
                    workshop_name="新厂在线车间",
                    process_name="北线退火",
                    coil_count=5,
                    material_weight_tons=201.0,
                    source="mes_coil_snapshot",
                ),
                MesWipTotalSnapshot(
                    source_id="partial-total",
                    workshop_name="拉矫车间",
                    process_name="包装",
                    doing_count=1,
                    doing_weight_tons=9.5,
                    snapshot_at=datetime(2026, 6, 17, 8, 0, tzinfo=UTC),
                ),
            ]
        )
        db.commit()

    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "build_daily_production_overview",
        lambda *_args, **_kwargs: {
            "plant_output": {},
            "contracts": {},
            "yield_rates": {},
            "energy": {},
            "cost": {},
            "wip_business_date": "2026-06-17",
            "wip_distribution": [],
        },
    )

    with SessionLocal() as db:
        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        template_daily_fact_sources.collect_opening_facts(db, facts, wip_date=date(2026, 6, 17))

    assert facts.values["wip_1650_2050_cold"] == 279.5
    assert facts.values["wip_1850_cold"] == 87.5
    assert facts.values["wip_new_north"] == 201.0
    assert facts.values["wip_total"] == 568.0
    assert facts.sources["wip_total"]["source_type"] == "mes_daily_wip_snapshot"


def test_opening_facts_do_not_use_output_skill_wip_snapshot_source(tmp_path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'template-daily-wip-no-output-skill.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesDailyWipSnapshot.__table__, MesWipTotalSnapshot.__table__])
    SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    with SessionLocal() as db:
        db.add(
            MesDailyWipSnapshot(
                business_date=date(2026, 6, 17),
                workshop_name="1650车间",
                process_name="冷轧",
                coil_count=10,
                material_weight_tons=999.0,
                source="output_skill_daily_report",
            )
        )
        db.add(
            MesWipTotalSnapshot(
                source_id="real-total",
                workshop_name="1650车间",
                process_name="冷轧",
                doing_count=1,
                doing_weight_tons=12.5,
                snapshot_at=datetime(2026, 6, 17, 8, 0, tzinfo=UTC),
            )
        )
        db.commit()

    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "build_daily_production_overview",
        lambda *_args, **_kwargs: {
            "plant_output": {},
            "contracts": {},
            "yield_rates": {},
            "energy": {},
            "cost": {},
            "wip_business_date": "2026-06-17",
            "wip_distribution": [],
        },
    )

    with SessionLocal() as db:
        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        template_daily_fact_sources.collect_opening_facts(db, facts, wip_date=date(2026, 6, 17))

    assert facts.values["wip_1650_2050_cold"] == 12.5
    assert facts.values["wip_total"] == 12.5
    assert facts.sources["wip_total"]["source_type"] == "mes_wip_total_snapshot"


def test_opening_facts_use_coil_snapshot_before_partial_wip_total(tmp_path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'template-daily-wip-coil-before-total.db'}", future=True)
    Base.metadata.create_all(engine, tables=[MesCoilSnapshot.__table__, MesWipTotalSnapshot.__table__])
    SessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    with SessionLocal() as db:
        db.add_all(
            [
                MesCoilSnapshot(
                    coil_id="MES:1650",
                    tracking_card_no="1650",
                    business_date=date(2026, 6, 17),
                    current_workshop="1650车间",
                    current_process="冷轧",
                    material_weight=279_500.0,
                ),
                MesCoilSnapshot(
                    coil_id="MES:1850",
                    tracking_card_no="1850",
                    business_date=date(2026, 6, 17),
                    current_workshop="1850车间",
                    current_process="冷轧",
                    material_weight=87_500.0,
                ),
                MesCoilSnapshot(
                    coil_id="MES:NORTH",
                    tracking_card_no="NORTH",
                    business_date=date(2026, 6, 17),
                    current_workshop="新厂在线车间",
                    current_process="北线退火",
                    material_weight=201_000.0,
                ),
                MesCoilSnapshot(
                    coil_id="MES:STOCK",
                    tracking_card_no="STOCK",
                    business_date=date(2026, 6, 17),
                    current_workshop="精整",
                    current_process="包装",
                    material_weight=999_000.0,
                    status_name="已入库",
                ),
                MesWipTotalSnapshot(
                    source_id="partial-total",
                    workshop_name="拉矫车间",
                    process_name="包装",
                    doing_count=1,
                    doing_weight_tons=9.5,
                    snapshot_at=datetime(2026, 6, 17, 8, 0, tzinfo=UTC),
                ),
            ]
        )
        db.commit()

    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "build_daily_production_overview",
        lambda *_args, **_kwargs: {
            "plant_output": {},
            "contracts": {},
            "yield_rates": {},
            "energy": {},
            "cost": {},
            "wip_business_date": "2026-06-17",
            "wip_distribution": [],
        },
    )

    with SessionLocal() as db:
        facts = template_daily_fact_sources.TemplateDailyFacts(target_date=REPORT_DATE)
        template_daily_fact_sources.collect_opening_facts(db, facts, wip_date=date(2026, 6, 17))

    assert facts.values["wip_1650_2050_cold"] == 279.5
    assert facts.values["wip_1850_cold"] == 87.5
    assert facts.values["wip_new_north"] == 201.0
    assert facts.values["wip_finishing"] == 0.0
    assert facts.values["wip_total"] == 568.0
    assert facts.sources["wip_total"]["source_type"] == "mes_coil_snapshot_business_date"


def test_mes_mapped_workshop_outputs_use_explicit_process_mapping(tmp_path) -> None:
    SessionLocal = _session(tmp_path)
    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        _seed_mes_process(db, source_id="1650-1", text="1650冷轧", output_tons=143.95, pass_count=55)
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["cold_1650_daily"] == 143.95
    assert facts.values["cold_1650_pass_daily"] == 55
    assert facts.sources["cold_1650_daily"]["source_type"] == "mes_workshop_process_records"


def test_mes_report_mapping_uses_device_name_for_cold_roll_rows(tmp_path) -> None:
    SessionLocal = _session(tmp_path)
    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        db.add_all(
            [
                MesWorkshopProcessRecord(
                    source_id="raw-1650-device",
                    source_path="sqlserver",
                    workshop_name="2050车间",
                    process_name="冷轧",
                    device_name="1650冷轧（WAN）",
                    output_weight_tons=141.74,
                    business_date=REPORT_DATE,
                ),
                MesWorkshopProcessRecord(
                    source_id="raw-2050-device",
                    source_path="sqlserver",
                    workshop_name="2050车间",
                    process_name="冷轧",
                    device_name="2050冷轧（WAN）",
                    output_weight_tons=167.9,
                    business_date=REPORT_DATE,
                ),
            ]
        )
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["cold_1650_daily"] == 141.74
    assert facts.values["cold_2050_daily"] == 167.9


def test_owner_daily_wins_over_mes_process_output_for_cold_roll(tmp_path) -> None:
    SessionLocal = _session(tmp_path)
    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        _seed_owner_daily_payload(
            db,
            {
                "cold_1650_daily": 130.01,
                "cold_1850_daily": 45.75,
                "cold_2050_daily": 80.4,
            },
        )
        _seed_mes_process(db, source_id="mes-1650", text="1650冷轧", output_tons=166.417)
        _seed_mes_process(db, source_id="mes-1850", text="1850冷轧", output_tons=99.99)
        _seed_mes_process(db, source_id="mes-2050", text="2050冷轧", output_tons=207.29)
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["cold_1650_daily"] == 130.01
    assert facts.values["cold_1850_daily"] == 45.75
    assert facts.values["cold_2050_daily"] == 80.4
    assert facts.sources["cold_1650_daily"]["source_type"] == "owner_daily"


def test_rolling_total_is_sum_of_report_mapped_1650_1850_2050(tmp_path) -> None:
    SessionLocal = _session(tmp_path)
    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        _seed_mes_process(db, source_id="1650-1", text="1650冷轧", output_tons=143.95, pass_count=55)
        _seed_mes_process(db, source_id="1850-1", text="1850冷轧", output_tons=32.68, pass_count=15)
        _seed_mes_process(db, source_id="2050-1", text="2050冷轧", output_tons=95.72, pass_count=33)
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["rolling_daily"] == 272.35
    assert facts.values["rolling_pass_daily"] == 103


def test_mes_row_cannot_count_into_multiple_report_fields(tmp_path) -> None:
    SessionLocal = _session(tmp_path)
    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        _seed_mes_process(db, source_id="mixed-1", text="2050冷轧精整", output_tons=10)
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    counted = [
        facts.values.get("cold_2050_daily"),
        facts.values.get("finishing_daily"),
    ]
    assert sum(1 for value in counted if value == 10) <= 1


def test_park_finishing_mes_rows_fill_shearing_not_finishing(tmp_path) -> None:
    SessionLocal = _session(tmp_path)
    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        db.add_all(
            [
                MesWorkshopProcessRecord(
                    source_id="jz-packaging",
                    source_path="sqlserver",
                    workshop_name="精整",
                    process_name="包装",
                    device_name="PC",
                    output_weight_tons=84.163,
                    business_date=REPORT_DATE,
                ),
                MesWorkshopProcessRecord(
                    source_id="jz-slitting",
                    source_path="sqlserver",
                    workshop_name="精整",
                    process_name="纵剪",
                    device_name="精整纵剪（WAN）",
                    output_weight_tons=44.5,
                    business_date=REPORT_DATE,
                ),
                MesWorkshopProcessRecord(
                    source_id="park-packaging",
                    source_path="sqlserver",
                    workshop_name="园区精整",
                    process_name="包装",
                    device_name="PC",
                    output_weight_tons=149.976,
                    business_date=REPORT_DATE,
                ),
            ]
        )
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["finishing_daily"] == 128.663
    assert facts.values["shearing_daily"] == 149.976


def test_owner_daily_payload_aliases_fill_template_fields(tmp_path) -> None:
    SessionLocal = _session(tmp_path)
    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        _seed_owner_daily_payload(
            db,
            {
                "plant_wide_yield_rate": 84.86,
                "heating_furnace_gas_m3": 8194,
                "daily_input_weight": 197,
            },
        )
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["daily_yield_rate"] == 84.86
    assert facts.values["hot_roll_furnace_gas_m3"] == 8194
    assert facts.values["cold_roll_input_daily"] == 197


def test_template_daily_facts_keep_daily_yield_missing_without_independent_source(tmp_path, monkeypatch) -> None:
    SessionLocal = _session(tmp_path)
    monkeypatch.setattr(
        template_daily_fact_sources.daily_overview_builder,
        "build_daily_production_overview",
        lambda *_args, **_kwargs: {
            "plant_output": {},
            "contracts": {},
            "yield_rates": {"daily": None, "owner_daily": None},
            "energy": {},
            "cost": {},
            "wip_distribution": [],
        },
    )

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=["daily_yield_rate"])

    assert "daily_yield_rate" not in facts.values
    assert "daily_yield_rate" in facts.missing_fields


def test_owner_recovery_weight_fills_daily_and_month_sum(tmp_path) -> None:
    SessionLocal = _session(tmp_path)
    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        _seed_owner_daily_payload(db, {"recovery_weight": 63})
        db.add(
            WorkOrderEntry(
                work_order_id=1,
                workshop_id=1,
                business_date=date(2026, 6, 15),
                entry_type="owner_daily",
                entry_status="submitted",
                extra_payload={"recovery_weight": 65},
            )
        )
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["recovery_daily"] == 63
    assert facts.values["recovery_month"] == 128
    assert facts.sources["recovery_daily"]["field"] == "recovery_weight"
    assert facts.sources["recovery_month"]["source_type"] == "owner_daily_month_sum"


def test_quality_yield_daily_fills_template_yield_breakdown(tmp_path) -> None:
    SessionLocal = _session(tmp_path)
    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        db.add_all(
            [
                QualityYieldDaily(
                    business_date=date(2026, 6, 15),
                    workshop_code="HOT_ROLL",
                    yield_daily=85.78,
                ),
                QualityYieldDaily(
                    business_date=REPORT_DATE,
                    workshop_code="FACTORY",
                    yield_daily=84.86,
                    yield_monthly=86.00,
                    yield_target_p_casting=92.02,
                    yield_target_p_hot_roll=84.46,
                ),
                QualityYieldDaily(
                    business_date=REPORT_DATE,
                    workshop_code="HOT_ROLL",
                    yield_daily=84.86,
                    yield_monthly=84.46,
                ),
            ]
        )
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["daily_yield_rate"] == 84.86
    assert facts.values["monthly_yield_rate"] == 86.00
    assert facts.values["hot_roll_yield_rate"] == 84.86
    assert facts.values["hot_roll_yield_delta"] == -0.92
    assert facts.values["cast_roll_yield_rate"] == 92.02
    assert facts.values["plate_coil_yield_rate"] == 92.02
    assert facts.values["hot_roll_monthly_yield_rate"] == 84.46


def test_missing_energy_fields_block_template_report(tmp_path) -> None:
    SessionLocal = _session(tmp_path)
    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert "total_electricity_kwh" in facts.missing_fields
