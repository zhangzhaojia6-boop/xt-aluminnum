from __future__ import annotations

from datetime import date
from typing import cast

from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyReportHistoryRecord
from app.services.report.daily_report_history import archive_daily_report


def test_archive_daily_report_keeps_snapshot_and_hash_trace() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, DailyFactBundleRun.__table__),
            cast(Table, DailyFactBundleSnapshot.__table__),
            cast(Table, DailyReportHistoryRecord.__table__),
        ],
    )
    db = Session(engine)
    run = DailyFactBundleRun(
        run_key="2026-06-19:trace-history",
        business_date=date(2026, 6, 19),
        status="ready",
        source_status={"mes": "ok"},
        missing_count=0,
        conflict_count=0,
        confidence=95,
    )
    db.add(run)
    db.flush()
    snapshot = DailyFactBundleSnapshot(
        run_id=run.id,
        business_date=date(2026, 6, 19),
        snapshot_reason="formal_daily_report",
        facts={"total_output_daily": {"value": 366.0, "unit": "吨"}},
        sources={"source_status": {"mes": "ok"}},
        conflicts=[],
        adopted_values={},
        correction_refs=[],
        dingtalk_refs=[],
        output_skill_alignment={"status": "matched"},
        payload_hash="a" * 64,
    )
    db.add(snapshot)
    db.flush()

    row = archive_daily_report(
        db,
        business_date=date(2026, 6, 19),
        report_text="6月19日，车间总产量日合计366吨。",
        report_payload={"facts": snapshot.facts, "formal_text": "6月19日，车间总产量日合计366吨。"},
        source_snapshot=snapshot,
        trace_id="trace-history",
    )
    db.commit()

    saved = db.query(DailyReportHistoryRecord).one()
    assert row.id == saved.id
    assert saved.business_date == date(2026, 6, 19)
    assert saved.source_snapshot_id == snapshot.id
    assert saved.source_run_id == run.id
    assert saved.report_type == "daily"
    assert saved.facts_hash == snapshot.payload_hash
    assert len(saved.text_hash) == 64
    assert saved.source_summary["source_status"] == {"mes": "ok"}
