from __future__ import annotations

from typing import cast

from sqlalchemy import Table, create_engine

from app.database import Base
from app.models.rag import HermesProfessionalKnowledgeEntry
from app.models.reports import DailyReportHistoryRecord, OperationPeriodSnapshot


def test_history_period_and_knowledge_tables_are_registered() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, DailyReportHistoryRecord.__table__),
            cast(Table, OperationPeriodSnapshot.__table__),
            cast(Table, HermesProfessionalKnowledgeEntry.__table__),
        ],
    )

    assert "daily_report_history_records" in Base.metadata.tables
    assert "operation_period_snapshots" in Base.metadata.tables
    assert "hermes_professional_knowledge_entries" in Base.metadata.tables
    assert DailyReportHistoryRecord.__table__.c.business_date.index is True
    assert OperationPeriodSnapshot.__table__.c.period_type.index is True
    assert HermesProfessionalKnowledgeEntry.__table__.c.domain.index is True
