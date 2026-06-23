from __future__ import annotations

from typing import cast

from sqlalchemy import Table, UniqueConstraint, create_engine

from app.database import Base
from app.models.rag import HermesProfessionalKnowledgeEntry
from app.models.reports import DailyReportHistoryRecord, OperationPeriodSnapshot


def _unique_constraint_names(table: Table) -> set[str]:
    names: set[str] = set()
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint):
            name = constraint.name
            if name is not None:
                names.add(str(name))
    return names


def _indexed_column_names(table: Table) -> set[str]:
    column_names: set[str] = set()
    for index in table.indexes:
        for column in index.columns:
            column_names.add(column.name)
    return column_names


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

    assert "uq_operation_period_snapshot_period" in _unique_constraint_names(
        cast(Table, OperationPeriodSnapshot.__table__)
    )
    assert "uq_hermes_professional_knowledge_source" in _unique_constraint_names(
        cast(Table, HermesProfessionalKnowledgeEntry.__table__)
    )

    assert {
        "facts_hash",
        "text_hash",
        "source_snapshot_id",
        "source_run_id",
    } <= _indexed_column_names(cast(Table, DailyReportHistoryRecord.__table__))
    assert {"payload_hash"} <= _indexed_column_names(cast(Table, OperationPeriodSnapshot.__table__))
    assert {
        "source_ref",
        "knowledge_type",
        "status",
    } <= _indexed_column_names(cast(Table, HermesProfessionalKnowledgeEntry.__table__))
