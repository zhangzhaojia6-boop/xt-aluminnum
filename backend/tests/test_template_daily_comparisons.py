from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Workshop
from app.models.production import WorkOrder, WorkOrderEntry
from app.models.reports import DailyReport
from app.services.report.template_daily_fact_sources import collect_template_daily_facts
from app.services.report.template_daily_report import REQUIRED_FIELDS


REPORT_DATE = date(2026, 6, 16)


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'template-daily-comparison.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            DailyReport.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _seed_owner_daily_payload(db, payload: dict):
    db.add_all(
        [
            Workshop(id=1, code="OWNER", name="日报负责人", workshop_type="owner", is_active=True),
            WorkOrder(id=1, tracking_card_no="OWNER-1", process_route_code="owner"),
            WorkOrderEntry(
                work_order_id=1,
                workshop_id=1,
                business_date=REPORT_DATE,
                entry_type="owner_daily",
                entry_status="submitted",
                extra_payload=payload,
            ),
        ]
    )


def test_total_output_delta_uses_yesterday_final_display_value(tmp_path) -> None:
    SessionLocal = _session(tmp_path)
    with SessionLocal() as db:
        _seed_owner_daily_payload(db, {"total_output_daily": 328})
        db.add(
            DailyReport(
                report_date=date(2026, 6, 15),
                report_type="production",
                final_text_summary="6月15日，车间总产量日合计306吨（外加工0吨）比昨日↑85吨，月累计4686吨（外加工月累计270吨）。",
            )
        )
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["total_output_delta"] == 22
    assert facts.sources["total_output_delta"]["source_type"] == "previous_final_report"


def test_contract_and_yield_deltas_use_yesterday_final_display_value(tmp_path) -> None:
    SessionLocal = _session(tmp_path)
    yesterday_text = (
        "6月15日，车间总产量日合计306吨（外加工0吨）比昨日↑85吨，月累计4686吨（外加工月累计270吨）。\n\n"
        "入库成品日合计306吨（寄存180吨），月累计4686吨。当天接合同303吨（含热轧271吨）；"
        "冷轧日投料152吨（2050投120吨、1850投0吨、外加工32吨），中厚板17吨，总余合同量2699吨，比昨日↑67吨。\n\n"
        "日成品率86.24%，比昨日↓1.29%；热轧成品率85.78%，比昨日↑0.03%；月成品率86.09%（铸轧成品率92.00%，普板、卷成品率92.00%，热轧成品率84.43%）。"
    )
    with SessionLocal() as db:
        _seed_owner_daily_payload(
            db,
            {
                "remaining_contract_weight": 2569,
                "daily_yield_rate": 84.86,
                "hot_roll_yield_rate": 84.86,
            },
        )
        db.add(DailyReport(report_date=date(2026, 6, 15), report_type="production", final_text_summary=yesterday_text))
        db.commit()

    with SessionLocal() as db:
        facts = collect_template_daily_facts(db, target_date=REPORT_DATE, required_fields=REQUIRED_FIELDS)

    assert facts.values["remaining_contract_delta"] == -130
    assert facts.values["daily_yield_delta"] == -1.38
    assert facts.values["hot_roll_yield_delta"] == -0.92
