from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Workshop
from app.models.mes import MesWipTotalSnapshot, MesWorkshopProcessRecord
from app.models.production import WorkOrder, WorkOrderEntry
from app.models.quality import QualityYieldDaily
from app.models.reports import DailyReport
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
            MesWorkshopProcessRecord.__table__,
            MesWipTotalSnapshot.__table__,
            DailyReport.__table__,
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


def test_owner_daily_wins_for_manual_workshop_outputs(tmp_path) -> None:
    SessionLocal = _session(tmp_path)
    with SessionLocal() as db:
        _seed_workshop_and_order(db)
        _seed_owner_daily_payload(db, {"hot_roll_daily": 275})
        db.add(
            WorkOrderEntry(
                work_order_id=2,
                workshop_id=2,
                business_date=REPORT_DATE,
                output_weight=999000,
                entry_type="mobile_coil",
                entry_status="submitted",
            )
        )
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["hot_roll_daily"] == 275
    assert facts.sources["hot_roll_daily"]["source_type"] == "owner_daily"


def test_template_daily_facts_default_to_current_business_date_for_wip(monkeypatch) -> None:
    seen: dict[str, date] = {}

    monkeypatch.setattr(
        template_daily_fact_sources,
        "resolve_production_business_date",
        lambda: date(2026, 6, 17),
    )

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
