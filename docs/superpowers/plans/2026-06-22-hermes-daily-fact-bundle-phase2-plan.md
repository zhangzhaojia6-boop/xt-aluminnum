# Hermes Daily Fact Bundle Phase-2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `DailyFactBundle` module that gives Hermes and the 数据中枢 one trusted business-day fact interface, with root_owner corrections, high-priority DingTalk supplements, traceable historical daily reports, monthly and annual cumulative facts, operation analysis, professional knowledge records, lightweight run records, formal snapshots, and first integration into Hermes Day-1.

**Architecture:** Start with a deep `DailyFactBundle` module: one interface, one fact priority resolver, one persistence path. Keep old report builders alive, but move Hermes Day-1 to consume the fact bundle first. Add a traceable history layer so every formal daily report can be replayed from its source snapshot, then compute month/year cumulative operation snapshots from archived daily facts instead of free-text guessing. Add natural-language intent parsing as a structure-only module: it turns flexible user text into validated tasks and never writes facts directly.

**Tech Stack:** FastAPI service layer, SQLAlchemy models, Alembic migration, pytest, existing `template_daily_report`, existing `MultimodalEvidence` / `ChatInboxMessage`, existing Hermes Day-1 services, existing output skill reconciliation.

---

## Scope Check

This plan intentionally keeps one integrated scope because the pieces depend on each other:

```text
DailyFactBundle contract
  -> priority resolver
  -> persistence
  -> Hermes Day-1 integration
  -> natural-language structured intent
  -> historical daily report archive
  -> monthly / annual cumulative operation snapshots
  -> monthly / annual operation analysis
  -> professional knowledge curation
```

Do not also redesign frontend pages, delete old report builders, or replace the runtime with LangGraph in this plan. Those are separate plans after the fact bundle is proven.

## Precondition

Implementation must start from a worktree that contains the Day-1 Hermes files merged to `origin/main`.

Required files must exist before Task 1:

```text
backend/app/services/hermes_day1_orchestrator.py
backend/app/services/hermes_day1_source_service.py
backend/app/services/hermes_day1_report_service.py
backend/app/services/hermes_day1_harness_service.py
backend/app/services/report/template_daily_report.py
backend/tests/test_hermes_day1_cli_dx.py
```

If the current branch does not contain those files, create a new worktree from `origin/main`:

```powershell
git fetch origin main
git worktree add .worktrees/hermes-daily-fact-bundle-phase2 origin/main
cd .worktrees/hermes-daily-fact-bundle-phase2
git switch -c feature/hermes-daily-fact-bundle-phase2
```

Expected: `git status -sb` prints a clean feature branch.

## File Structure

Create:

- `backend/app/services/report/daily_fact_bundle.py`
  Deep module for building one business-day fact bundle. Owns source priority, conflicts, missing fields, root_owner corrections, DingTalk supplements, output skill alignment, and optional persistence.

- `backend/tests/test_daily_fact_bundle_service.py`
  Contract tests for fact values, source priority, conflicts, DingTalk supplements, root_owner corrections, snapshots, and output skill alignment.

- `backend/tests/test_hermes_intent_service.py`
  Tests for flexible natural-language intent parsing into structured tasks.

- `backend/app/services/hermes_intent_service.py`
  Structure-only intent module. It parses user language and returns validated task dictionaries. It never writes facts or calls LLM directly in Phase 2.1.

- `backend/alembic/versions/0050_daily_fact_bundle.py`
  Adds run, snapshot, and correction tables.

- `backend/alembic/versions/0051_report_history_period_knowledge.py`
  Adds traceable daily report history, monthly/yearly operation snapshots, and professional Hermes knowledge entries.

- `backend/app/services/report/daily_report_history.py`
  Archives every formal daily report with the source snapshot id, payload hash, report text, source summary, and trace id.

- `backend/app/services/report/period_rollup.py`
  Builds month-to-date, year-to-date, full-month, and full-year cumulative facts from archived daily report facts.

- `backend/app/services/report/operation_analysis.py`
  Turns cumulative period facts into monthly and annual operating situation summaries, risk points, and comparison analysis.

- `backend/app/services/hermes_professional_knowledge_service.py`
  Curates professional knowledge records from output skill files, DingTalk text/files, report history, and approved domain rules.

Modify:

- `backend/app/models/reports.py`
  Add `DailyFactBundleRun`, `DailyFactBundleSnapshot`, `DailyFactCorrection`, `DailyReportHistoryRecord`, `OperationPeriodSnapshot`.

- `backend/app/models/__init__.py`
  Export the new models.

- `backend/app/models/rag.py`
  Add `HermesProfessionalKnowledgeEntry` so the knowledge base can distinguish professional facts, domain rules, report patterns, and DingTalk-derived evidence.

- `backend/app/services/hermes_day1_source_service.py`
  Use `build_daily_fact_bundle()` as the first fact source, keeping old fields for compatibility.

- `backend/app/services/hermes_day1_report_service.py`
  Read fact bundle facts/source summaries when present.

- `backend/app/services/hermes_day1_orchestrator.py`
  Preserve the fact bundle in `AgentRun.result_payload`.

- `backend/scripts/agent_cli.py`
  Let natural-language Day-1 text route through `hermes_intent_service` before the old strict parser.

- `backend/app/services/rag_service.py`
  Keep existing document ingestion, but let Hermes retrieve curated professional knowledge before generic chunk matches.

Do not modify:

- MES sync write path.
- WMS sync write path.
- mobile fill write path.
- old report pages.
- frontend.
- raw historical facts without a trace record.

---

### Task 1: Add Daily Fact Bundle Persistence Models

**Files:**
- Modify: `backend/app/models/reports.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0050_daily_fact_bundle.py`
- Test: `backend/tests/test_daily_fact_bundle_service.py`

- [ ] **Step 1: Write the failing model metadata test**

Add this file:

```python
from __future__ import annotations

from sqlalchemy import create_engine

from app.database import Base
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyFactCorrection


def test_daily_fact_bundle_tables_are_registered() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            DailyFactBundleRun.__table__,
            DailyFactBundleSnapshot.__table__,
            DailyFactCorrection.__table__,
        ],
    )

    table_names = set(Base.metadata.tables)
    assert "daily_fact_bundle_runs" in table_names
    assert "daily_fact_bundle_snapshots" in table_names
    assert "daily_fact_corrections" in table_names
    assert DailyFactBundleRun.__table__.c.business_date.index is True
    assert DailyFactCorrection.__table__.c.field_name.index is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest backend/tests/test_daily_fact_bundle_service.py::test_daily_fact_bundle_tables_are_registered -q
```

Expected: FAIL with import error for `DailyFactBundleRun` or missing table.

- [ ] **Step 3: Add the models**

Append these classes to `backend/app/models/reports.py` after `DailyReport`:

```python
class DailyFactBundleRun(Base):
    __tablename__ = 'daily_fact_bundle_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    requested_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='partial', index=True)
    source_status: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DailyFactBundleSnapshot(Base):
    __tablename__ = 'daily_fact_bundle_snapshots'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('daily_fact_bundle_runs.id'), nullable=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    snapshot_reason: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    facts: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    sources: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    conflicts: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    adopted_values: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    correction_refs: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    dingtalk_refs: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    output_skill_alignment: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DailyFactCorrection(Base):
    __tablename__ = 'daily_fact_corrections'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    value_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_value: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
```

In the same file, change this import:

```python
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
```

to:

```python
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
```

No new import is needed because the file already imports every type used above.

- [ ] **Step 4: Export the models**

Modify `backend/app/models/__init__.py`:

```python
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyFactCorrection, DailyReport
```

Add to `__all__`:

```python
'DailyFactBundleRun',
'DailyFactBundleSnapshot',
'DailyFactCorrection',
```

- [ ] **Step 5: Add Alembic migration**

Create `backend/alembic/versions/0050_daily_fact_bundle.py`:

```python
"""daily fact bundle

Revision ID: 0050_daily_fact_bundle
Revises: 0049_hermes_data_audit
Create Date: 2026-06-22
"""

from alembic import op
import sqlalchemy as sa

from app.models.base import json_object_type


revision = '0050_daily_fact_bundle'
down_revision = '0049_hermes_data_audit'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'daily_fact_bundle_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_key', sa.String(length=160), nullable=False),
        sa.Column('business_date', sa.Date(), nullable=False),
        sa.Column('requested_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('trace_id', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='partial'),
        sa.Column('source_status', json_object_type, nullable=False),
        sa.Column('missing_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('conflict_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('confidence', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_daily_fact_bundle_runs_run_key', 'daily_fact_bundle_runs', ['run_key'], unique=True)
    op.create_index('ix_daily_fact_bundle_runs_business_date', 'daily_fact_bundle_runs', ['business_date'])
    op.create_index('ix_daily_fact_bundle_runs_requested_by_id', 'daily_fact_bundle_runs', ['requested_by_id'])
    op.create_index('ix_daily_fact_bundle_runs_trace_id', 'daily_fact_bundle_runs', ['trace_id'])
    op.create_index('ix_daily_fact_bundle_runs_status', 'daily_fact_bundle_runs', ['status'])

    op.create_table(
        'daily_fact_bundle_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('daily_fact_bundle_runs.id'), nullable=True),
        sa.Column('business_date', sa.Date(), nullable=False),
        sa.Column('snapshot_reason', sa.String(length=64), nullable=False),
        sa.Column('facts', json_object_type, nullable=False),
        sa.Column('sources', json_object_type, nullable=False),
        sa.Column('conflicts', json_object_type, nullable=False),
        sa.Column('adopted_values', json_object_type, nullable=False),
        sa.Column('correction_refs', json_object_type, nullable=False),
        sa.Column('dingtalk_refs', json_object_type, nullable=False),
        sa.Column('output_skill_alignment', json_object_type, nullable=False),
        sa.Column('payload_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('trace_id', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_daily_fact_bundle_snapshots_run_id', 'daily_fact_bundle_snapshots', ['run_id'])
    op.create_index('ix_daily_fact_bundle_snapshots_business_date', 'daily_fact_bundle_snapshots', ['business_date'])
    op.create_index('ix_daily_fact_bundle_snapshots_snapshot_reason', 'daily_fact_bundle_snapshots', ['snapshot_reason'])
    op.create_index('ix_daily_fact_bundle_snapshots_payload_hash', 'daily_fact_bundle_snapshots', ['payload_hash'])
    op.create_index('ix_daily_fact_bundle_snapshots_created_by_id', 'daily_fact_bundle_snapshots', ['created_by_id'])
    op.create_index('ix_daily_fact_bundle_snapshots_trace_id', 'daily_fact_bundle_snapshots', ['trace_id'])

    op.create_table(
        'daily_fact_corrections',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('business_date', sa.Date(), nullable=False),
        sa.Column('field_name', sa.String(length=128), nullable=False),
        sa.Column('value_payload', json_object_type, nullable=False),
        sa.Column('unit', sa.String(length=32), nullable=True),
        sa.Column('source_text', sa.Text(), nullable=True),
        sa.Column('before_value', json_object_type, nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('trace_id', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_daily_fact_corrections_business_date', 'daily_fact_corrections', ['business_date'])
    op.create_index('ix_daily_fact_corrections_field_name', 'daily_fact_corrections', ['field_name'])
    op.create_index('ix_daily_fact_corrections_actor_user_id', 'daily_fact_corrections', ['actor_user_id'])
    op.create_index('ix_daily_fact_corrections_trace_id', 'daily_fact_corrections', ['trace_id'])
    op.create_index('ix_daily_fact_corrections_status', 'daily_fact_corrections', ['status'])


def downgrade() -> None:
    op.drop_table('daily_fact_corrections')
    op.drop_table('daily_fact_bundle_snapshots')
    op.drop_table('daily_fact_bundle_runs')
```

- [ ] **Step 6: Run the metadata test**

Run:

```powershell
python -m pytest backend/tests/test_daily_fact_bundle_service.py::test_daily_fact_bundle_tables_are_registered -q
```

Expected: `1 passed`.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/models/reports.py backend/app/models/__init__.py backend/alembic/versions/0050_daily_fact_bundle.py backend/tests/test_daily_fact_bundle_service.py
git commit -m "feat: add daily fact bundle persistence models"
```

---

### Task 2: Add DailyFactBundle Contract and Template Adapter

**Files:**
- Create: `backend/app/services/report/daily_fact_bundle.py`
- Modify: `backend/tests/test_daily_fact_bundle_service.py`

- [ ] **Step 1: Add failing contract test**

Append to `backend/tests/test_daily_fact_bundle_service.py`:

```python
from datetime import date

from sqlalchemy.orm import Session


def test_build_daily_fact_bundle_uses_template_facts(monkeypatch, db_session: Session) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_payload(db, *, target_date, wip_date=None):
        assert target_date == date(2026, 6, 19)
        return {
            "status": "ready",
            "text": "6月19日，车间总产量日合计366吨。",
            "missing_fields": [],
            "conflicts": [],
            "facts": {
                "values": {
                    "total_output_daily": 366,
                    "total_electricity_kwh": 146500,
                },
                "sources": {
                    "total_output_daily": "mes_packaging_output",
                    "total_electricity_kwh": "owner_or_energy_summary",
                },
                "conflicts": [],
            },
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_payload",
        fake_template_payload,
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["business_date"] == "2026-06-19"
    assert bundle["status"] == "ready"
    assert bundle["facts"]["total_output_daily"]["value"] == 366
    assert bundle["facts"]["total_output_daily"]["unit"] == "吨"
    assert bundle["facts"]["total_output_daily"]["source"] == "mes_packaging_output"
    assert bundle["facts"]["total_output_daily"]["confidence"] == 0.85
    assert bundle["missing"] == []
    assert bundle["conflicts"] == []
```

If this test file does not already have a `db_session` fixture, add this fixture above the tests:

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.agent_communication import ChatInboxMessage, MultimodalEvidence
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyFactCorrection
from app.models.system import User


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            ChatInboxMessage.__table__,
            MultimodalEvidence.__table__,
            DailyFactBundleRun.__table__,
            DailyFactBundleSnapshot.__table__,
            DailyFactCorrection.__table__,
        ],
    )
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest backend/tests/test_daily_fact_bundle_service.py::test_build_daily_fact_bundle_uses_template_facts -q
```

Expected: FAIL with `cannot import name daily_fact_bundle`.

- [ ] **Step 3: Create the contract module**

Create `backend/app/services/report/daily_fact_bundle.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.redaction import filter_sensitive_mapping
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot
from app.models.system import User
from app.services.report import template_daily_report


SOURCE_PRIORITY = {
    "root_owner_correction": 100,
    "dingtalk_supplement": 90,
    "mes_wms": 80,
    "mes_packaging_output": 80,
    "mes_wip_distribution": 80,
    "finished_inbound_output": 80,
    "owner_or_energy_summary": 70,
    "manual_mobile_coil": 70,
    "owner_daily": 70,
    "computed": 60,
    "energy_cost": 60,
    "historical_report": 40,
    "rag": 30,
    "output_skill": 20,
}

FIELD_UNITS = {
    "total_output_daily": "吨",
    "total_output_month": "吨",
    "total_electricity_kwh": "度",
    "total_gas_m3": "m³",
    "daily_yield_rate": "%",
    "monthly_yield_rate": "%",
    "cost_per_ton": "元/吨",
}


def build_daily_fact_bundle(
    db: Session,
    *,
    business_date: date,
    requested_by: User | None = None,
    trace_id: str | None = None,
    persist_run: bool = False,
    snapshot_reason: str | None = None,
) -> dict[str, Any]:
    template_payload = template_daily_report.build_template_daily_report_payload(db, target_date=business_date)
    facts_payload = _facts_from_template(template_payload, business_date=business_date)
    bundle = _bundle_from_facts(
        business_date=business_date,
        facts_payload=facts_payload,
        template_payload=template_payload,
        trace_id=trace_id,
    )
    if persist_run or snapshot_reason:
        _persist_bundle(
            db,
            bundle=bundle,
            business_date=business_date,
            requested_by=requested_by,
            trace_id=trace_id,
            snapshot_reason=snapshot_reason,
        )
    return bundle


def _facts_from_template(template_payload: Mapping[str, Any], *, business_date: date) -> dict[str, Any]:
    facts = dict(template_payload.get("facts") or {})
    values = dict(facts.get("values") or {})
    sources = dict(facts.get("sources") or {})
    result: dict[str, Any] = {}
    for field_name, value in values.items():
        source = str(sources.get(field_name) or "computed")
        result[str(field_name)] = _fact_item(
            value=value,
            unit=FIELD_UNITS.get(str(field_name)),
            source=source,
            priority=_source_priority(source),
            freshness="current_business_day",
            confidence=_source_confidence(source),
            adoption_reason=f"来自 {source}",
            source_ref={"source": source, "business_date": business_date.isoformat()},
        )
    return result


def _bundle_from_facts(
    *,
    business_date: date,
    facts_payload: dict[str, Any],
    template_payload: Mapping[str, Any],
    trace_id: str | None,
) -> dict[str, Any]:
    missing = [str(item) for item in template_payload.get("missing_fields") or []]
    conflicts = [_json_safe(item) for item in template_payload.get("conflicts") or []]
    status = "blocked" if missing else ("partial" if conflicts else str(template_payload.get("status") or "partial"))
    confidence_values = [
        float(item.get("confidence"))
        for item in facts_payload.values()
        if isinstance(item, Mapping) and item.get("confidence") is not None
    ]
    confidence = round(sum(confidence_values) / len(confidence_values), 4) if confidence_values else None
    return {
        "business_date": business_date.isoformat(),
        "status": status,
        "facts": facts_payload,
        "sources": {key: value.get("source") for key, value in facts_payload.items()},
        "missing": missing,
        "conflicts": conflicts,
        "freshness": {key: value.get("freshness") for key, value in facts_payload.items()},
        "confidence": confidence,
        "correction_refs": [],
        "dingtalk_refs": [],
        "output_skill_alignment": {},
        "trace_id": trace_id,
    }


def _fact_item(
    *,
    value: Any,
    unit: str | None,
    source: str,
    priority: int,
    freshness: str,
    confidence: float,
    adoption_reason: str,
    source_ref: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "value": _json_safe(value),
        "unit": unit,
        "source": source,
        "priority": priority,
        "freshness": freshness,
        "confidence": confidence,
        "adoption_reason": adoption_reason,
        "source_ref": _json_safe(source_ref),
    }


def _source_priority(source: str) -> int:
    return SOURCE_PRIORITY.get(source, SOURCE_PRIORITY.get(str(source).split(":")[0], 50))


def _source_confidence(source: str) -> float:
    priority = _source_priority(source)
    if priority >= 100:
        return 1.0
    if priority >= 90:
        return 0.95
    if priority >= 80:
        return 0.85
    if priority >= 70:
        return 0.75
    if priority >= 60:
        return 0.65
    return 0.5


def _persist_bundle(
    db: Session,
    *,
    bundle: dict[str, Any],
    business_date: date,
    requested_by: User | None,
    trace_id: str | None,
    snapshot_reason: str | None,
) -> tuple[DailyFactBundleRun, DailyFactBundleSnapshot | None]:
    run = DailyFactBundleRun(
        run_key=_run_key(business_date=business_date, trace_id=trace_id),
        business_date=business_date,
        requested_by_id=getattr(requested_by, "id", None),
        trace_id=trace_id,
        status=str(bundle.get("status") or "partial"),
        source_status={"sources": bundle.get("sources") or {}},
        missing_count=len(bundle.get("missing") or []),
        conflict_count=len(bundle.get("conflicts") or []),
        confidence=_confidence_percent(bundle.get("confidence")),
    )
    db.add(run)
    db.flush()
    snapshot = None
    if snapshot_reason:
        payload_hash = _payload_hash(bundle)
        snapshot = DailyFactBundleSnapshot(
            run_id=run.id,
            business_date=business_date,
            snapshot_reason=snapshot_reason,
            facts=bundle.get("facts") or {},
            sources=bundle.get("sources") or {},
            conflicts=bundle.get("conflicts") or [],
            adopted_values=_adopted_values(bundle),
            correction_refs=bundle.get("correction_refs") or [],
            dingtalk_refs=bundle.get("dingtalk_refs") or [],
            output_skill_alignment=bundle.get("output_skill_alignment") or {},
            payload_hash=payload_hash,
            created_by_id=getattr(requested_by, "id", None),
            trace_id=trace_id,
        )
        db.add(snapshot)
        db.flush()
    return run, snapshot


def _confidence_percent(value: Any) -> int | None:
    if value is None:
        return None
    return int(round(float(value) * 100))


def _adopted_values(bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item.get("value") for key, item in dict(bundle.get("facts") or {}).items() if isinstance(item, Mapping)}


def _run_key(*, business_date: date, trace_id: str | None) -> str:
    raw = f"{business_date.isoformat()}:{trace_id or 'manual'}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _payload_hash(value: Any) -> str:
    encoded = json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized = filter_sensitive_mapping(value)
        return {str(key): _json_safe(item) for key, item in sanitized.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (date,)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
```

- [ ] **Step 4: Run the contract test**

Run:

```powershell
python -m pytest backend/tests/test_daily_fact_bundle_service.py::test_build_daily_fact_bundle_uses_template_facts -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/report/daily_fact_bundle.py backend/tests/test_daily_fact_bundle_service.py
git commit -m "feat: add daily fact bundle contract"
```

---

### Task 3: Apply root_owner Corrections with Highest Priority

**Files:**
- Modify: `backend/app/services/report/daily_fact_bundle.py`
- Modify: `backend/tests/test_daily_fact_bundle_service.py`

- [ ] **Step 1: Write failing correction test**

Append:

```python
def test_root_owner_correction_overrides_template_fact(monkeypatch, db_session: Session) -> None:
    from app.models.reports import DailyFactCorrection
    from app.services.report import daily_fact_bundle

    def fake_template_payload(db, *, target_date, wip_date=None):
        return {
            "status": "ready",
            "text": "模板日报",
            "missing_fields": [],
            "conflicts": [],
            "facts": {
                "values": {"total_output_daily": 355},
                "sources": {"total_output_daily": "mes_packaging_output"},
                "conflicts": [],
            },
        }

    monkeypatch.setattr(daily_fact_bundle.template_daily_report, "build_template_daily_report_payload", fake_template_payload)
    db_session.add(
        DailyFactCorrection(
            business_date=date(2026, 6, 19),
            field_name="total_output_daily",
            value_payload={"value": 366},
            unit="吨",
            source_text="6月19日车间总产量改成366吨，直接按这个发。",
            before_value={"value": 355, "source": "mes_packaging_output"},
            reason="root_owner 钉钉确认",
            actor_user_id=983,
            trace_id="trace-root-owner-correction",
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    fact = bundle["facts"]["total_output_daily"]
    assert fact["value"] == 366
    assert fact["source"] == "root_owner_correction"
    assert fact["priority"] == 100
    assert fact["confidence"] == 1.0
    assert fact["adoption_reason"] == "root_owner 钉钉确认"
    assert bundle["correction_refs"] == [{"id": 1, "field_name": "total_output_daily", "trace_id": "trace-root-owner-correction"}]
    assert bundle["conflicts"][0]["field"] == "total_output_daily"
    assert bundle["conflicts"][0]["adopted_source"] == "root_owner_correction"
```

- [ ] **Step 2: Run it to verify failure**

Run:

```powershell
python -m pytest backend/tests/test_daily_fact_bundle_service.py::test_root_owner_correction_overrides_template_fact -q
```

Expected: FAIL because corrections are ignored.

- [ ] **Step 3: Implement correction overlay**

In `daily_fact_bundle.py`, import the model:

```python
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyFactCorrection
```

In `build_daily_fact_bundle()`, after `bundle = _bundle_from_facts(...)`, add:

```python
    _apply_root_owner_corrections(db, bundle=bundle, business_date=business_date)
```

Add these functions:

```python
def _apply_root_owner_corrections(db: Session, *, bundle: dict[str, Any], business_date: date) -> None:
    rows = (
        db.query(DailyFactCorrection)
        .filter(
            DailyFactCorrection.business_date == business_date,
            DailyFactCorrection.status == "active",
        )
        .order_by(DailyFactCorrection.created_at.asc(), DailyFactCorrection.id.asc())
        .all()
    )
    if not rows:
        return
    facts = dict(bundle.get("facts") or {})
    conflicts = list(bundle.get("conflicts") or [])
    correction_refs = list(bundle.get("correction_refs") or [])
    for row in rows:
        field_name = str(row.field_name)
        old_fact = facts.get(field_name)
        old_value = old_fact.get("value") if isinstance(old_fact, Mapping) else None
        new_value = dict(row.value_payload or {}).get("value")
        if old_fact is not None and old_value != new_value:
            conflicts.append(
                {
                    "field": field_name,
                    "type": "root_owner_correction",
                    "adopted_source": "root_owner_correction",
                    "adopted_value": new_value,
                    "previous_source": old_fact.get("source") if isinstance(old_fact, Mapping) else None,
                    "previous_value": old_value,
                    "reason": row.reason,
                }
            )
        facts[field_name] = _fact_item(
            value=new_value,
            unit=row.unit,
            source="root_owner_correction",
            priority=SOURCE_PRIORITY["root_owner_correction"],
            freshness="confirmed",
            confidence=1.0,
            adoption_reason=row.reason,
            source_ref={
                "correction_id": row.id,
                "actor_user_id": row.actor_user_id,
                "trace_id": row.trace_id,
                "source_text": row.source_text,
            },
        )
        correction_refs.append({"id": row.id, "field_name": field_name, "trace_id": row.trace_id})
    bundle["facts"] = facts
    bundle["sources"] = {key: value.get("source") for key, value in facts.items()}
    bundle["conflicts"] = conflicts
    bundle["correction_refs"] = correction_refs
```

- [ ] **Step 4: Run correction tests**

Run:

```powershell
python -m pytest backend/tests/test_daily_fact_bundle_service.py::test_root_owner_correction_overrides_template_fact backend/tests/test_daily_fact_bundle_service.py::test_build_daily_fact_bundle_uses_template_facts -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/report/daily_fact_bundle.py backend/tests/test_daily_fact_bundle_service.py
git commit -m "feat: apply root owner daily fact corrections"
```

---

### Task 4: Treat DingTalk Supplements as High-Priority Facts

**Files:**
- Modify: `backend/app/services/report/daily_fact_bundle.py`
- Modify: `backend/tests/test_daily_fact_bundle_service.py`

- [ ] **Step 1: Write failing DingTalk supplement test**

Append:

```python
def test_dingtalk_supplement_overrides_mes_and_keeps_conflict(monkeypatch, db_session: Session) -> None:
    from app.models.agent_communication import MultimodalEvidence
    from app.services.report import daily_fact_bundle

    def fake_template_payload(db, *, target_date, wip_date=None):
        return {
            "status": "ready",
            "text": "模板日报",
            "missing_fields": [],
            "conflicts": [],
            "facts": {
                "values": {"total_gas_m3": 50000},
                "sources": {"total_gas_m3": "mes_wms"},
                "conflicts": [],
            },
        }

    monkeypatch.setattr(daily_fact_bundle.template_daily_report, "build_template_daily_report_payload", fake_template_payload)
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_file",
            source_user_id=12,
            file_uri="dingtalk://gas/2026-06-19.xlsx",
            recognized_text="6月19日天然气共计50578m³",
            confirmation_status="confirmed",
            payload={
                "business_date": "2026-06-19",
                "include_in_daily_sample": True,
                "evidence_kind": "fact",
                "fact_updates": [
                    {
                        "field_name": "total_gas_m3",
                        "value": 50578,
                        "unit": "m³",
                        "reason": "能源负责人钉钉补充",
                    }
                ],
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    fact = bundle["facts"]["total_gas_m3"]
    assert fact["value"] == 50578
    assert fact["source"] == "dingtalk_supplement"
    assert fact["priority"] == 90
    assert fact["adoption_reason"] == "能源负责人钉钉补充"
    assert bundle["dingtalk_refs"] == [{"id": 1, "field_names": ["total_gas_m3"]}]
    assert bundle["conflicts"][0]["previous_value"] == 50000
    assert bundle["conflicts"][0]["adopted_value"] == 50578
```

- [ ] **Step 2: Run it to verify failure**

Run:

```powershell
python -m pytest backend/tests/test_daily_fact_bundle_service.py::test_dingtalk_supplement_overrides_mes_and_keeps_conflict -q
```

Expected: FAIL because DingTalk evidence is ignored.

- [ ] **Step 3: Implement DingTalk supplement overlay**

In `daily_fact_bundle.py`, import:

```python
from app.models.agent_communication import MultimodalEvidence
```

In `build_daily_fact_bundle()`, after `_apply_root_owner_corrections(...)`, add:

```python
    _apply_dingtalk_supplements(db, bundle=bundle, business_date=business_date)
```

Add:

```python
def _apply_dingtalk_supplements(db: Session, *, bundle: dict[str, Any], business_date: date) -> None:
    business_date_text = business_date.isoformat()
    rows = (
        db.query(MultimodalEvidence)
        .filter(MultimodalEvidence.payload.is_not(None))
        .order_by(MultimodalEvidence.created_at.asc(), MultimodalEvidence.id.asc())
        .all()
    )
    facts = dict(bundle.get("facts") or {})
    conflicts = list(bundle.get("conflicts") or [])
    dingtalk_refs = list(bundle.get("dingtalk_refs") or [])
    for row in rows:
        payload = dict(row.payload or {})
        if payload.get("business_date") != business_date_text:
            continue
        if not payload.get("include_in_daily_sample"):
            continue
        updates = [item for item in payload.get("fact_updates") or [] if isinstance(item, Mapping)]
        if not updates:
            continue
        applied_fields: list[str] = []
        for update in updates:
            field_name = str(update.get("field_name") or "").strip()
            if not field_name:
                continue
            new_value = update.get("value")
            old_fact = facts.get(field_name)
            old_value = old_fact.get("value") if isinstance(old_fact, Mapping) else None
            reason = str(update.get("reason") or "钉钉补充数据")
            if old_fact is not None and old_value != new_value:
                conflicts.append(
                    {
                        "field": field_name,
                        "type": "dingtalk_supplement",
                        "adopted_source": "dingtalk_supplement",
                        "adopted_value": new_value,
                        "previous_source": old_fact.get("source") if isinstance(old_fact, Mapping) else None,
                        "previous_value": old_value,
                        "reason": reason,
                    }
                )
            facts[field_name] = _fact_item(
                value=new_value,
                unit=str(update.get("unit") or FIELD_UNITS.get(field_name) or ""),
                source="dingtalk_supplement",
                priority=SOURCE_PRIORITY["dingtalk_supplement"],
                freshness="supplemented",
                confidence=0.95,
                adoption_reason=reason,
                source_ref={
                    "evidence_id": row.id,
                    "source_user_id": row.source_user_id,
                    "file_uri": row.file_uri,
                    "recognized_text": row.recognized_text,
                },
            )
            applied_fields.append(field_name)
        if applied_fields:
            dingtalk_refs.append({"id": row.id, "field_names": applied_fields})
    bundle["facts"] = facts
    bundle["sources"] = {key: value.get("source") for key, value in facts.items()}
    bundle["conflicts"] = conflicts
    bundle["dingtalk_refs"] = dingtalk_refs
```

- [ ] **Step 4: Run DingTalk and correction tests**

Run:

```powershell
python -m pytest backend/tests/test_daily_fact_bundle_service.py -q
```

Expected: all tests in file pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/report/daily_fact_bundle.py backend/tests/test_daily_fact_bundle_service.py
git commit -m "feat: apply dingtalk supplements to daily fact bundle"
```

---

### Task 5: Persist Lightweight Runs and Formal Snapshots

**Files:**
- Modify: `backend/app/services/report/daily_fact_bundle.py`
- Modify: `backend/tests/test_daily_fact_bundle_service.py`

- [ ] **Step 1: Write failing persistence test**

Append:

```python
def test_daily_fact_bundle_persists_light_run_and_formal_snapshot(monkeypatch, db_session: Session) -> None:
    from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot
    from app.services.report import daily_fact_bundle

    def fake_template_payload(db, *, target_date, wip_date=None):
        return {
            "status": "ready",
            "text": "模板日报",
            "missing_fields": [],
            "conflicts": [],
            "facts": {
                "values": {"total_output_daily": 366},
                "sources": {"total_output_daily": "mes_packaging_output"},
                "conflicts": [],
            },
        }

    monkeypatch.setattr(daily_fact_bundle.template_daily_report, "build_template_daily_report_payload", fake_template_payload)

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 6, 19),
        trace_id="trace-fact-bundle-persist",
        persist_run=True,
        snapshot_reason="formal_daily_report",
    )
    db_session.commit()

    run = db_session.query(DailyFactBundleRun).one()
    snapshot = db_session.query(DailyFactBundleSnapshot).one()
    assert run.business_date.isoformat() == "2026-06-19"
    assert run.trace_id == "trace-fact-bundle-persist"
    assert run.missing_count == 0
    assert run.conflict_count == 0
    assert snapshot.snapshot_reason == "formal_daily_report"
    assert snapshot.facts == bundle["facts"]
    assert len(snapshot.payload_hash) == 64
```

- [ ] **Step 2: Run it**

Run:

```powershell
python -m pytest backend/tests/test_daily_fact_bundle_service.py::test_daily_fact_bundle_persists_light_run_and_formal_snapshot -q
```

Expected: FAIL if Task 2 persistence had not fully passed SQLite model behavior.

- [ ] **Step 3: Fix SQLite confidence type if needed**

If the failure says `confidence` expects integer but received non-integer, keep the current percent storage. If the model field type is changed, use:

```python
confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

The run row stores confidence as `0..100`; the bundle payload stores confidence as `0.0..1.0`.

- [ ] **Step 4: Run persistence tests**

Run:

```powershell
python -m pytest backend/tests/test_daily_fact_bundle_service.py::test_daily_fact_bundle_persists_light_run_and_formal_snapshot backend/tests/test_daily_fact_bundle_service.py::test_build_daily_fact_bundle_uses_template_facts -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/models/reports.py backend/app/services/report/daily_fact_bundle.py backend/tests/test_daily_fact_bundle_service.py
git commit -m "feat: persist daily fact bundle runs and snapshots"
```

---

### Task 6: Add Output Skill Alignment to the Fact Bundle

**Files:**
- Modify: `backend/app/services/report/daily_fact_bundle.py`
- Modify: `backend/tests/test_daily_fact_bundle_service.py`

- [ ] **Step 1: Write failing alignment test**

Append:

```python
def test_daily_fact_bundle_includes_output_skill_alignment(monkeypatch, tmp_path, db_session: Session) -> None:
    from app.services.report import daily_fact_bundle

    expected = "6月19日，车间总产量日合计366吨。"
    (tmp_path / "2026-6-19_日报正文.txt").write_text(expected, encoding="utf-8")

    def fake_template_payload(db, *, target_date, wip_date=None):
        return {
            "status": "ready",
            "text": expected,
            "missing_fields": [],
            "conflicts": [],
            "facts": {
                "values": {"total_output_daily": 366},
                "sources": {"total_output_daily": "mes_packaging_output"},
                "conflicts": [],
            },
        }

    monkeypatch.setenv("OUTPUT_SKILL_ROOT", str(tmp_path))
    monkeypatch.setattr(daily_fact_bundle.template_daily_report, "build_template_daily_report_payload", fake_template_payload)

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["output_skill_alignment"]["status"] == "passed"
    assert bundle["output_skill_alignment"]["file_name"] == "2026-6-19_日报正文.txt"
    assert bundle["output_skill_alignment"]["field_match_rate"] == 100.0
```

- [ ] **Step 2: Run it**

Run:

```powershell
python -m pytest backend/tests/test_daily_fact_bundle_service.py::test_daily_fact_bundle_includes_output_skill_alignment -q
```

Expected: FAIL because alignment is `{}`.

- [ ] **Step 3: Implement alignment**

In `daily_fact_bundle.py`, add imports:

```python
import os
from app.services.hermes_day1_harness_service import build_output_skill_alignment
```

In `build_daily_fact_bundle()`, before persistence:

```python
    bundle["output_skill_alignment"] = build_output_skill_alignment(
        str(template_payload.get("text") or ""),
        _output_skill_root(),
        business_date,
    )
```

Add:

```python
def _output_skill_root() -> str | None:
    return os.getenv("OUTPUT_SKILL_ROOT") or os.getenv("OUTPUT_SKILL_REFERENCE_ROOT")
```

- [ ] **Step 4: Run alignment tests**

Run:

```powershell
python -m pytest backend/tests/test_daily_fact_bundle_service.py::test_daily_fact_bundle_includes_output_skill_alignment -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/report/daily_fact_bundle.py backend/tests/test_daily_fact_bundle_service.py
git commit -m "feat: align daily fact bundle with output skill"
```

---

### Task 7: Integrate DailyFactBundle into Hermes Day-1 Source Collection

**Files:**
- Modify: `backend/app/services/hermes_day1_source_service.py`
- Modify: `backend/app/services/hermes_day1_orchestrator.py`
- Test: `backend/tests/test_hermes_day1_source_service.py` or create if missing

- [ ] **Step 1: Write failing Hermes source test**

Create `backend/tests/test_hermes_day1_source_service.py` if it does not exist, then add:

```python
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.agent_communication import ChatInboxMessage, MultimodalEvidence
from app.models.rag import RagChunk, RagDocument, RagQueryLog
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyFactCorrection, DailyReport
from app.models.system import User


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            ChatInboxMessage.__table__,
            MultimodalEvidence.__table__,
            RagDocument.__table__,
            RagChunk.__table__,
            RagQueryLog.__table__,
            DailyReport.__table__,
            DailyFactBundleRun.__table__,
            DailyFactBundleSnapshot.__table__,
            DailyFactCorrection.__table__,
        ],
    )
    return sessionmaker(bind=engine)()


def test_collect_day1_sources_includes_daily_fact_bundle(monkeypatch) -> None:
    from app.services import hermes_day1_source_service

    db = _session()
    actor = SimpleNamespace(id=1)

    monkeypatch.setattr(
        hermes_day1_source_service,
        "build_daily_fact_bundle",
        lambda db, business_date, requested_by=None, trace_id=None, persist_run=False, snapshot_reason=None: {
            "business_date": business_date.isoformat(),
            "status": "ready",
            "facts": {"total_output_daily": {"value": 366, "source": "root_owner_correction"}},
            "missing": [],
            "conflicts": [],
            "output_skill_alignment": {"status": "passed", "field_match_rate": 100.0},
        },
    )
    monkeypatch.setattr(
        hermes_day1_source_service.template_daily_report,
        "build_template_daily_report_payload",
        lambda db, target_date: {"status": "ready", "text": "模板日报", "facts": {"values": {}, "sources": {}}},
    )
    monkeypatch.setattr(
        hermes_day1_source_service.HermesMesReadService,
        "__init__",
        lambda self, adapter: None,
    )
    monkeypatch.setattr(
        hermes_day1_source_service.HermesMesReadService,
        "read_sources",
        lambda self, business_date, query_keys: {"source_status": {"mes": "ok"}, "records": {}},
    )
    monkeypatch.setattr(
        hermes_day1_source_service,
        "get_mes_adapter",
        lambda: object(),
    )
    monkeypatch.setattr(
        hermes_day1_source_service,
        "_create_audit_payload",
        lambda *args, **kwargs: {"status": "matched", "source_status": {}},
    )
    monkeypatch.setattr(
        hermes_day1_source_service,
        "_query_day1_rag",
        lambda *args, **kwargs: {"answer": "", "citations": []},
    )

    payload = hermes_day1_source_service.collect_day1_sources(
        db,
        business_date=date(2026, 6, 19),
        actor=actor,
        trace_id="trace-day1-fact-bundle",
    )

    assert payload["daily_fact_bundle"]["facts"]["total_output_daily"]["value"] == 366
    assert payload["output_skill_alignment"]["status"] == "passed"
```

- [ ] **Step 2: Run it**

Run:

```powershell
python -m pytest backend/tests/test_hermes_day1_source_service.py::test_collect_day1_sources_includes_daily_fact_bundle -q
```

Expected: FAIL because `daily_fact_bundle` is not included.

- [ ] **Step 3: Modify source collection**

In `backend/app/services/hermes_day1_source_service.py`, add import:

```python
from app.services.report.daily_fact_bundle import build_daily_fact_bundle
```

In `collect_day1_sources()`, after `template_payload = ...`, add:

```python
    daily_fact_payload = build_daily_fact_bundle(
        db,
        business_date=business_date,
        requested_by=actor,
        trace_id=trace_id,
        persist_run=True,
        snapshot_reason=None,
    )
```

Change the output skill alignment assignment to prefer the fact bundle:

```python
    output_skill_alignment = daily_fact_payload.get('output_skill_alignment') or build_output_skill_alignment(
        str(template_payload.get('text') or ''),
        _output_skill_reference_root(),
        business_date,
    )
```

In the returned dict, add:

```python
        'daily_fact_bundle': daily_fact_payload,
```

- [ ] **Step 4: Preserve fact bundle in orchestrator payload**

In `backend/app/services/hermes_day1_orchestrator.py`, inside `_source_summary`, add:

```python
    daily_fact_bundle = _as_mapping(sources.get('daily_fact_bundle'))
```

and include this key in the returned dict:

```python
        'daily_fact_bundle': {
            'status': _summary_safe(daily_fact_bundle.get('status')),
            'missing_count': len(daily_fact_bundle.get('missing') or []),
            'conflict_count': len(daily_fact_bundle.get('conflicts') or []),
            'fact_count': len(_as_mapping(daily_fact_bundle.get('facts'))),
        },
```

- [ ] **Step 5: Run Hermes source test**

Run:

```powershell
python -m pytest backend/tests/test_hermes_day1_source_service.py::test_collect_day1_sources_includes_daily_fact_bundle -q
```

Expected: `1 passed`.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/hermes_day1_source_service.py backend/app/services/hermes_day1_orchestrator.py backend/tests/test_hermes_day1_source_service.py
git commit -m "feat: include daily fact bundle in hermes day1 sources"
```

---

### Task 8: Let Day-1 Report Rendering Prefer DailyFactBundle Facts

**Files:**
- Modify: `backend/app/services/hermes_day1_report_service.py`
- Modify: `backend/tests/test_hermes_day1_report_service.py`

- [ ] **Step 1: Add failing report preference test**

Append to `backend/tests/test_hermes_day1_report_service.py`:

```python
from datetime import date


def test_day1_report_uses_daily_fact_bundle_correction_for_judgment() -> None:
    from app.services.hermes_day1_report_service import build_day1_three_part_report

    product = build_day1_three_part_report(
        business_date=date(2026, 6, 19),
        sources={
            "template_daily_report": {
                "status": "ready",
                "text": "6月19日，车间总产量日合计355吨。",
                "facts": {
                    "values": {"total_output_daily": 355},
                    "sources": {"total_output_daily": "mes_packaging_output"},
                },
                "missing_fields": [],
                "conflicts": [],
            },
            "daily_fact_bundle": {
                "status": "ready",
                "facts": {
                    "total_output_daily": {
                        "value": 366,
                        "unit": "吨",
                        "source": "root_owner_correction",
                        "adoption_reason": "root_owner 钉钉确认",
                    }
                },
                "missing": [],
                "conflicts": [
                    {
                        "field": "total_output_daily",
                        "type": "root_owner_correction",
                        "adopted_source": "root_owner_correction",
                        "adopted_value": 366,
                        "previous_source": "mes_packaging_output",
                        "previous_value": 355,
                    }
                ],
                "output_skill_alignment": {"status": "passed", "field_match_rate": 100.0, "threshold": 95.0},
            },
            "audit_run": {"status": "matched", "source_status": {}, "diffs": {}, "suggested_actions": []},
            "mes_wms": {"source_status": {"mes": "ok"}, "records": {}},
            "output_skill_alignment": {"status": "passed", "field_match_rate": 100.0, "threshold": 95.0},
        },
    )

    assert product["brain_judgment"]["risks"][0].startswith("发现冲突")
    assert "total_output_daily" in product["text"]
    assert "root_owner_correction" in product["text"]
```

- [ ] **Step 2: Run it**

Run:

```powershell
python -m pytest backend/tests/test_hermes_day1_report_service.py::test_day1_report_uses_daily_fact_bundle_correction_for_judgment -q
```

Expected: FAIL because the report does not surface the fact bundle conflict.

- [ ] **Step 3: Merge daily fact bundle conflicts into report conflicts**

In `backend/app/services/hermes_day1_report_service.py`, modify `_collect_conflicts()` near the top:

```python
    daily_fact_bundle = _as_mapping(sources.get('daily_fact_bundle'))
    for item in _as_list(daily_fact_bundle.get('conflicts')):
        conflicts.append(_normalise_conflict(item, conflict_type='daily_fact_bundle_conflict', source='daily_fact_bundle'))
```

- [ ] **Step 4: Add fact bundle source names**

In `_source_names()`, include:

```python
    if sources.get('daily_fact_bundle') is not None:
        names.append('日报事实包')
```

If `_source_names()` uses a different local shape, keep the same behavior: source names must include `日报事实包` when present.

- [ ] **Step 5: Run the Day-1 report tests**

Run:

```powershell
python -m pytest backend/tests/test_hermes_day1_report_service.py::test_day1_report_uses_daily_fact_bundle_correction_for_judgment backend/tests/test_hermes_day1_report_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/hermes_day1_report_service.py backend/tests/test_hermes_day1_report_service.py
git commit -m "feat: surface daily fact bundle in day1 report"
```

---

### Task 9: Add Flexible Hermes Intent Parsing

**Files:**
- Create: `backend/app/services/hermes_intent_service.py`
- Create: `backend/tests/test_hermes_intent_service.py`

- [ ] **Step 1: Write failing intent tests**

Create `backend/tests/test_hermes_intent_service.py`:

```python
from __future__ import annotations

from datetime import date


def test_parse_daily_report_intent_from_flexible_text() -> None:
    from app.services.hermes_intent_service import parse_hermes_intent

    intent = parse_hermes_intent("6月19日按最终口径重新来一版", default_year=2026)

    assert intent["intent"] == "daily_report"
    assert intent["business_date"] == "2026-06-19"
    assert intent["audience"] == "root_owner"
    assert intent["mode"] == "final"
    assert intent["requested_corrections"] == []


def test_parse_direct_root_owner_correction_intent() -> None:
    from app.services.hermes_intent_service import parse_hermes_intent

    intent = parse_hermes_intent("6月19日车间总产量改成366吨，直接按这个发。", default_year=2026)

    assert intent["intent"] == "daily_report"
    assert intent["business_date"] == "2026-06-19"
    assert intent["correction_policy"] == "root_owner_direct"
    assert intent["requested_corrections"] == [
        {
            "field_name": "total_output_daily",
            "value": 366.0,
            "unit": "吨",
            "reason": "root_owner 自然语言修正",
            "requires_confirmation": False,
        }
    ]


def test_parse_ambiguous_correction_requires_confirmation() -> None:
    from app.services.hermes_intent_service import parse_hermes_intent

    intent = parse_hermes_intent("6月19日车间总产量改成366吨", default_year=2026)

    assert intent["correction_policy"] == "root_owner_confirm"
    assert intent["requested_corrections"][0]["requires_confirmation"] is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest backend/tests/test_hermes_intent_service.py -q
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement rule-based intent parsing**

Create `backend/app/services/hermes_intent_service.py`:

```python
from __future__ import annotations

from datetime import date
import re
from typing import Any


FIELD_PATTERNS = (
    ("total_output_daily", re.compile(r"(?:车间总产量|总产量|产量日合计)\s*(?:改成|改为|按|用)\s*(?P<value>\d+(?:\.\d+)?)\s*吨")),
    ("total_gas_m3", re.compile(r"(?:天然气|用气|总气量|共计)\s*(?:改成|改为|按|用)\s*(?P<value>\d+(?:\.\d+)?)\s*(?:m³|方|立方)")),
    ("total_electricity_kwh", re.compile(r"(?:用电|总用电|全厂高压总用电量)\s*(?:改成|改为|按|用)\s*(?P<value>\d+(?:\.\d+)?)\s*(?:度|kwh|KWH)")),
)


def parse_hermes_intent(text: str, *, default_year: int) -> dict[str, Any]:
    clean = str(text or "").strip()
    business_date = _extract_business_date(clean, default_year=default_year)
    requested_corrections = _extract_corrections(clean)
    is_direct = any(marker in clean for marker in ("直接", "不用确认", "免确认", "按这个发"))
    is_daily_report = bool(business_date and ("日报" in clean or "来一版" in clean or "按这个发" in clean or requested_corrections))
    if not is_daily_report:
        return {
            "intent": "unknown",
            "business_date": business_date.isoformat() if business_date else None,
            "raw_text": clean,
            "requested_corrections": requested_corrections,
        }
    for item in requested_corrections:
        item["requires_confirmation"] = not is_direct
    return {
        "intent": "daily_report",
        "business_date": business_date.isoformat(),
        "audience": "root_owner",
        "mode": "final",
        "evidence_policy": "include_dingtalk_supplement",
        "correction_policy": "root_owner_direct" if requested_corrections and is_direct else ("root_owner_confirm" if requested_corrections else "none"),
        "requested_corrections": requested_corrections,
        "raw_text": clean,
    }


def _extract_corrections(text: str) -> list[dict[str, Any]]:
    corrections: list[dict[str, Any]] = []
    for field_name, pattern in FIELD_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        unit = "吨" if field_name == "total_output_daily" else ("m³" if field_name == "total_gas_m3" else "度")
        corrections.append(
            {
                "field_name": field_name,
                "value": float(match.group("value")),
                "unit": unit,
                "reason": "root_owner 自然语言修正",
                "requires_confirmation": True,
            }
        )
    return corrections


def _extract_business_date(text: str, *, default_year: int) -> date | None:
    iso_match = re.search(r"(?P<year>\d{4})[-_.](?P<month>\d{1,2})[-_.](?P<day>\d{1,2})", text)
    if iso_match:
        return date(int(iso_match.group("year")), int(iso_match.group("month")), int(iso_match.group("day")))
    chinese_match = re.search(r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日", text)
    if chinese_match:
        return date(default_year, int(chinese_match.group("month")), int(chinese_match.group("day")))
    return None
```

- [ ] **Step 4: Run intent tests**

Run:

```powershell
python -m pytest backend/tests/test_hermes_intent_service.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/hermes_intent_service.py backend/tests/test_hermes_intent_service.py
git commit -m "feat: parse flexible hermes intents"
```

---

### Task 10: Route Agent CLI Day-1 Text Through Flexible Intent

**Files:**
- Modify: `backend/scripts/agent_cli.py`
- Modify: `backend/tests/test_agent_cli.py`
- Modify: `backend/tests/test_hermes_day1_cli_dx.py`

- [ ] **Step 1: Add failing CLI routing test**

Append to `backend/tests/test_agent_cli.py`:

```python
def test_dingtalk_command_flexible_final_report_text_routes_to_day1(monkeypatch, tmp_path, capsys) -> None:
    from backend.scripts import agent_cli

    def fake_day1_report(_db, args, auth, **_kwargs):
        return {
            "action": "day1-report",
            "reply": "flexible day1 ok",
            "trace_id": "trace-flexible-day1",
            "data": {"business_date": "2026-06-19"},
        }

    monkeypatch.setattr(agent_cli, "_cmd_day1_report", fake_day1_report)

    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv("HERMES_OWNER_DINGTALK_USER_IDS", "dt-owner")
    monkeypatch.setenv("HERMES_DAY1_ENABLED", "true")
    try:
        db.add(User(id=983, username="zzj", password_hash="x", name="张兆嘉", role="admin", is_active=True, dingtalk_user_id="dt-owner"))
        db.commit()

        code = agent_cli.main(
            [
                "dingtalk-command",
                "--text",
                "6月19日按最终口径重新来一版",
                "--dingtalk-user-id",
                "dt-owner",
                "--trace-id",
                "trace-flexible-day1",
            ]
        )

        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["action"] == "day1-report"
    finally:
        db.close()
```

- [ ] **Step 2: Run it**

Run:

```powershell
python -m pytest backend/tests/test_agent_cli.py::test_dingtalk_command_flexible_final_report_text_routes_to_day1 -q
```

Expected: FAIL because old natural language detection requires `日报`.

- [ ] **Step 3: Modify CLI routing**

In `backend/scripts/agent_cli.py`, add:

```python
from app.services.hermes_intent_service import parse_hermes_intent
```

In `_cmd_dingtalk_command`, before the old `_is_natural_language_day1_text(text)` block, add:

```python
    flexible_intent = parse_hermes_intent(text, default_year=_day1_default_year(args))
    if flexible_intent.get("intent") == "daily_report":
        parsed_command = HermesDay1Command(
            source_text=text,
            business_date=date.fromisoformat(str(flexible_intent["business_date"])),
            report_type="daily_report",
            audience=str(flexible_intent.get("audience") or "root_owner"),
            output_format="three_part",
        )
        return _cmd_day1_report(db, args, auth, parsed_command=parsed_command)
```

If `date` is not imported, add:

```python
from datetime import date
```

This file already imports `date`; do not duplicate the import.

- [ ] **Step 4: Run CLI routing tests**

Run:

```powershell
python -m pytest backend/tests/test_agent_cli.py::test_dingtalk_command_flexible_final_report_text_routes_to_day1 backend/tests/test_hermes_day1_cli_dx.py -q
```

Expected: selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/scripts/agent_cli.py backend/tests/test_agent_cli.py backend/tests/test_hermes_day1_cli_dx.py
git commit -m "feat: route flexible hermes day1 intents"
```

---

### Task 11: Store Direct root_owner Corrections from Intent

**Files:**
- Modify: `backend/scripts/agent_cli.py`
- Modify: `backend/tests/test_hermes_day1_cli_dx.py`

- [ ] **Step 1: Add failing direct correction persistence test**

In `backend/tests/test_hermes_day1_cli_dx.py`, update the reports import:

```python
from app.models.reports import DailyFactCorrection, DailyReport
```

Add this table to `TABLES` after `DailyReport.__table__`:

```python
DailyFactCorrection.__table__,
```

Append to `backend/tests/test_hermes_day1_cli_dx.py`:

```python
def test_day1_direct_root_owner_correction_is_persisted_before_run(tmp_path, monkeypatch, capsys) -> None:
    db = _install_db(tmp_path, monkeypatch)
    monkeypatch.setenv("HERMES_OWNER_DINGTALK_USER_IDS", "dt-owner")
    monkeypatch.setenv("HERMES_DAY1_ENABLED", "true")
    _add_user(db, user_id=983, name="张兆嘉", dingtalk_user_id="dt-owner")

    def fake_run_day1(_db, *, command, actor, trace_id, chat_inbox=None):
        from app.services.hermes_day1_orchestrator import HermesDay1Result
        return HermesDay1Result(
            trace_id=trace_id,
            status="ready",
            answer="ok",
            reply_messages=["ok"],
            agent_run_id=1,
            report_id=1,
            payload={},
        )

    monkeypatch.setattr(agent_cli, "run_day1_super_brain", fake_run_day1)

    try:
        code = agent_cli.main(
            [
                "day1-report",
                "--text",
                "6月19日车间总产量改成366吨，直接按这个发。",
                "--dingtalk-user-id",
                "dt-owner",
                "--trace-id",
                "trace-direct-correction",
            ]
        )

        assert code == 0
        row = db.query(DailyFactCorrection).one()
        assert row.business_date.isoformat() == "2026-06-19"
        assert row.field_name == "total_output_daily"
        assert row.value_payload == {"value": 366.0}
        assert row.reason == "root_owner 自然语言修正"
        assert row.trace_id == "trace-direct-correction"
    finally:
        db.close()
```

- [ ] **Step 2: Run it**

Run:

```powershell
python -m pytest backend/tests/test_hermes_day1_cli_dx.py::test_day1_direct_root_owner_correction_is_persisted_before_run -q
```

Expected: FAIL because the CLI does not create `DailyFactCorrection`.

- [ ] **Step 3: Persist direct corrections**

In `backend/scripts/agent_cli.py`, import:

```python
from app.models.reports import DailyFactCorrection
from app.services.hermes_intent_service import parse_hermes_intent
```

In `_cmd_day1_report`, after `command` is resolved and after `require_root_owner_for_day1_report(decision)`, add:

```python
    flexible_intent = parse_hermes_intent(args.text or args.query or getattr(command, "source_text", ""), default_year=_day1_default_year(args))
    _persist_direct_root_owner_corrections(db, args=args, auth=auth, command=command, intent=flexible_intent)
```

Add helper near `_cmd_day1_report_doctor`:

```python
def _persist_direct_root_owner_corrections(
    db: Session,
    *,
    args: argparse.Namespace,
    auth: HermesAuth,
    command: HermesDay1Command,
    intent: dict[str, Any],
) -> None:
    if intent.get("correction_policy") != "root_owner_direct":
        return
    for item in intent.get("requested_corrections") or []:
        if not isinstance(item, dict):
            continue
        field_name = str(item.get("field_name") or "").strip()
        if not field_name:
            continue
        db.add(
            DailyFactCorrection(
                business_date=command.business_date,
                field_name=field_name,
                value_payload={"value": item.get("value")},
                unit=str(item.get("unit") or "") or None,
                source_text=str(intent.get("raw_text") or ""),
                before_value=None,
                reason=str(item.get("reason") or "root_owner 自然语言修正"),
                actor_user_id=getattr(auth.user, "id", None),
                trace_id=_trace_id(args),
            )
        )
    db.flush()
```

- [ ] **Step 4: Run correction CLI test**

Run:

```powershell
python -m pytest backend/tests/test_hermes_day1_cli_dx.py::test_day1_direct_root_owner_correction_is_persisted_before_run -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/scripts/agent_cli.py backend/tests/test_hermes_day1_cli_dx.py
git commit -m "feat: persist root owner correction intents"
```

---

### Task 12: Add Traceable History, Period, and Professional Knowledge Models

**Files:**
- Modify: `backend/app/models/reports.py`
- Modify: `backend/app/models/rag.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/0051_report_history_period_knowledge.py`
- Test: `backend/tests/test_report_history_period_knowledge_models.py`

- [ ] **Step 1: Write failing model metadata test**

Create `backend/tests/test_report_history_period_knowledge_models.py`:

```python
from __future__ import annotations

from sqlalchemy import create_engine

from app.database import Base
from app.models.rag import HermesProfessionalKnowledgeEntry
from app.models.reports import DailyReportHistoryRecord, OperationPeriodSnapshot


def test_history_period_and_knowledge_tables_are_registered() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            DailyReportHistoryRecord.__table__,
            OperationPeriodSnapshot.__table__,
            HermesProfessionalKnowledgeEntry.__table__,
        ],
    )

    assert "daily_report_history_records" in Base.metadata.tables
    assert "operation_period_snapshots" in Base.metadata.tables
    assert "hermes_professional_knowledge_entries" in Base.metadata.tables
    assert DailyReportHistoryRecord.__table__.c.business_date.index is True
    assert OperationPeriodSnapshot.__table__.c.period_type.index is True
    assert HermesProfessionalKnowledgeEntry.__table__.c.domain.index is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m pytest backend/tests/test_report_history_period_knowledge_models.py::test_history_period_and_knowledge_tables_are_registered -q
```

Expected: FAIL with import error for `DailyReportHistoryRecord`, `OperationPeriodSnapshot`, or `HermesProfessionalKnowledgeEntry`.

- [ ] **Step 3: Add report history and period models**

Append to `backend/app/models/reports.py` after `DailyFactCorrection`:

```python
class DailyReportHistoryRecord(Base):
    __tablename__ = 'daily_report_history_records'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_type: Mapped[str] = mapped_column(String(32), nullable=False, default='daily', index=True)
    business_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    period_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    source_snapshot_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('daily_fact_bundle_snapshots.id'), nullable=True, index=True)
    source_run_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('daily_fact_bundle_runs.id'), nullable=True, index=True)
    report_text: Mapped[str] = mapped_column(Text, nullable=False)
    report_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    source_summary: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    facts_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OperationPeriodSnapshot(Base):
    __tablename__ = 'operation_period_snapshots'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    period_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='ready', index=True)
    cumulative_metrics: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    analysis_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    source_daily_report_ids: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    source_snapshot_ids: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    missing_dates: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('period_type', 'period_start', 'period_end', name='uq_operation_period_snapshot_period'),
    )
```

- [ ] **Step 4: Add professional knowledge model**

In `backend/app/models/rag.py`, extend imports:

```python
from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
```

Append this class after the existing Hermes knowledge/memory models:

```python
class HermesProfessionalKnowledgeEntry(Base):
    __tablename__ = 'hermes_professional_knowledge_entries'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_ref: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active', index=True)
    created_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('domain', 'topic', 'knowledge_type', 'source_ref', name='uq_hermes_professional_knowledge_source'),
    )
```

- [ ] **Step 5: Export the models**

Modify `backend/app/models/__init__.py`:

```python
from app.models.rag import HermesProfessionalKnowledgeEntry
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyFactCorrection, DailyReport, DailyReportHistoryRecord, OperationPeriodSnapshot
```

Add to `__all__`:

```python
'DailyReportHistoryRecord',
'OperationPeriodSnapshot',
'HermesProfessionalKnowledgeEntry',
```

- [ ] **Step 6: Add Alembic migration**

Create `backend/alembic/versions/0051_report_history_period_knowledge.py`:

```python
"""report history period knowledge

Revision ID: 0051_report_history_period_knowledge
Revises: 0050_daily_fact_bundle
Create Date: 2026-06-23
"""

from alembic import op
import sqlalchemy as sa

from app.models.base import json_object_type


revision = '0051_report_history_period_knowledge'
down_revision = '0050_daily_fact_bundle'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'daily_report_history_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('report_type', sa.String(length=32), nullable=False, server_default='daily'),
        sa.Column('business_date', sa.Date(), nullable=True),
        sa.Column('period_type', sa.String(length=32), nullable=True),
        sa.Column('period_start', sa.Date(), nullable=True),
        sa.Column('period_end', sa.Date(), nullable=True),
        sa.Column('source_snapshot_id', sa.Integer(), sa.ForeignKey('daily_fact_bundle_snapshots.id'), nullable=True),
        sa.Column('source_run_id', sa.Integer(), sa.ForeignKey('daily_fact_bundle_runs.id'), nullable=True),
        sa.Column('report_text', sa.Text(), nullable=False),
        sa.Column('report_payload', json_object_type, nullable=False),
        sa.Column('source_summary', json_object_type, nullable=False),
        sa.Column('facts_hash', sa.String(length=64), nullable=False),
        sa.Column('text_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('trace_id', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_daily_report_history_records_report_type', 'daily_report_history_records', ['report_type'])
    op.create_index('ix_daily_report_history_records_business_date', 'daily_report_history_records', ['business_date'])
    op.create_index('ix_daily_report_history_records_period_type', 'daily_report_history_records', ['period_type'])
    op.create_index('ix_daily_report_history_records_period_start', 'daily_report_history_records', ['period_start'])
    op.create_index('ix_daily_report_history_records_period_end', 'daily_report_history_records', ['period_end'])
    op.create_index('ix_daily_report_history_records_source_snapshot_id', 'daily_report_history_records', ['source_snapshot_id'])
    op.create_index('ix_daily_report_history_records_source_run_id', 'daily_report_history_records', ['source_run_id'])
    op.create_index('ix_daily_report_history_records_facts_hash', 'daily_report_history_records', ['facts_hash'])
    op.create_index('ix_daily_report_history_records_text_hash', 'daily_report_history_records', ['text_hash'])
    op.create_index('ix_daily_report_history_records_created_by_id', 'daily_report_history_records', ['created_by_id'])
    op.create_index('ix_daily_report_history_records_trace_id', 'daily_report_history_records', ['trace_id'])

    op.create_table(
        'operation_period_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('period_type', sa.String(length=32), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='ready'),
        sa.Column('cumulative_metrics', json_object_type, nullable=False),
        sa.Column('analysis_payload', json_object_type, nullable=False),
        sa.Column('source_daily_report_ids', json_object_type, nullable=False),
        sa.Column('source_snapshot_ids', json_object_type, nullable=False),
        sa.Column('missing_dates', json_object_type, nullable=False),
        sa.Column('payload_hash', sa.String(length=64), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('trace_id', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('period_type', 'period_start', 'period_end', name='uq_operation_period_snapshot_period'),
    )
    op.create_index('ix_operation_period_snapshots_period_type', 'operation_period_snapshots', ['period_type'])
    op.create_index('ix_operation_period_snapshots_period_start', 'operation_period_snapshots', ['period_start'])
    op.create_index('ix_operation_period_snapshots_period_end', 'operation_period_snapshots', ['period_end'])
    op.create_index('ix_operation_period_snapshots_status', 'operation_period_snapshots', ['status'])
    op.create_index('ix_operation_period_snapshots_payload_hash', 'operation_period_snapshots', ['payload_hash'])
    op.create_index('ix_operation_period_snapshots_created_by_id', 'operation_period_snapshots', ['created_by_id'])
    op.create_index('ix_operation_period_snapshots_trace_id', 'operation_period_snapshots', ['trace_id'])

    op.create_table(
        'hermes_professional_knowledge_entries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('domain', sa.String(length=64), nullable=False),
        sa.Column('topic', sa.String(length=128), nullable=False),
        sa.Column('knowledge_type', sa.String(length=64), nullable=False),
        sa.Column('source_type', sa.String(length=64), nullable=False),
        sa.Column('source_ref', sa.String(length=256), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('structured_payload', json_object_type, nullable=False),
        sa.Column('confidence', sa.Integer(), nullable=False, server_default='80'),
        sa.Column('valid_from', sa.Date(), nullable=True),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('trace_id', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('domain', 'topic', 'knowledge_type', 'source_ref', name='uq_hermes_professional_knowledge_source'),
    )
    op.create_index('ix_hermes_professional_knowledge_entries_domain', 'hermes_professional_knowledge_entries', ['domain'])
    op.create_index('ix_hermes_professional_knowledge_entries_topic', 'hermes_professional_knowledge_entries', ['topic'])
    op.create_index('ix_hermes_professional_knowledge_entries_knowledge_type', 'hermes_professional_knowledge_entries', ['knowledge_type'])
    op.create_index('ix_hermes_professional_knowledge_entries_source_type', 'hermes_professional_knowledge_entries', ['source_type'])
    op.create_index('ix_hermes_professional_knowledge_entries_source_ref', 'hermes_professional_knowledge_entries', ['source_ref'])
    op.create_index('ix_hermes_professional_knowledge_entries_valid_from', 'hermes_professional_knowledge_entries', ['valid_from'])
    op.create_index('ix_hermes_professional_knowledge_entries_valid_to', 'hermes_professional_knowledge_entries', ['valid_to'])
    op.create_index('ix_hermes_professional_knowledge_entries_status', 'hermes_professional_knowledge_entries', ['status'])
    op.create_index('ix_hermes_professional_knowledge_entries_created_by_id', 'hermes_professional_knowledge_entries', ['created_by_id'])
    op.create_index('ix_hermes_professional_knowledge_entries_trace_id', 'hermes_professional_knowledge_entries', ['trace_id'])


def downgrade() -> None:
    op.drop_table('hermes_professional_knowledge_entries')
    op.drop_table('operation_period_snapshots')
    op.drop_table('daily_report_history_records')
```

- [ ] **Step 7: Run the model metadata test**

Run:

```powershell
python -m pytest backend/tests/test_report_history_period_knowledge_models.py::test_history_period_and_knowledge_tables_are_registered -q
```

Expected: `1 passed`.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/models/reports.py backend/app/models/rag.py backend/app/models/__init__.py backend/alembic/versions/0051_report_history_period_knowledge.py backend/tests/test_report_history_period_knowledge_models.py
git commit -m "feat: add traceable report history period knowledge models"
```

---

### Task 13: Archive Formal Daily Reports with Source Trace

**Files:**
- Create: `backend/app/services/report/daily_report_history.py`
- Test: `backend/tests/test_daily_report_history_service.py`

- [ ] **Step 1: Write failing archive test**

Create `backend/tests/test_daily_report_history_service.py`:

```python
from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyReportHistoryRecord
from app.services.report.daily_report_history import archive_daily_report


def test_archive_daily_report_keeps_snapshot_and_hash_trace() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            DailyFactBundleRun.__table__,
            DailyFactBundleSnapshot.__table__,
            DailyReportHistoryRecord.__table__,
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
        sources={"total_output_daily": "root_owner_correction"},
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
    assert saved.business_date.isoformat() == "2026-06-19"
    assert saved.source_snapshot_id == snapshot.id
    assert saved.source_run_id == run.id
    assert saved.report_type == "daily"
    assert saved.facts_hash == snapshot.payload_hash
    assert len(saved.text_hash) == 64
    assert saved.source_summary["source_status"] == {"mes": "ok"}
```

- [ ] **Step 2: Run the test**

Run:

```powershell
python -m pytest backend/tests/test_daily_report_history_service.py::test_archive_daily_report_keeps_snapshot_and_hash_trace -q
```

Expected: FAIL because `daily_report_history.py` does not exist.

- [ ] **Step 3: Implement archive service**

Create `backend/app/services/report/daily_report_history.py`:

```python
from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.reports import DailyFactBundleSnapshot, DailyReportHistoryRecord


def archive_daily_report(
    db: Session,
    *,
    business_date: date,
    report_text: str,
    report_payload: dict[str, Any],
    source_snapshot: DailyFactBundleSnapshot,
    trace_id: str | None = None,
    created_by_id: int | None = None,
) -> DailyReportHistoryRecord:
    source_summary = {
        "snapshot_id": source_snapshot.id,
        "run_id": source_snapshot.run_id,
        "snapshot_reason": source_snapshot.snapshot_reason,
        "payload_hash": source_snapshot.payload_hash,
        "source_status": _source_status(source_snapshot),
        "conflicts": source_snapshot.conflicts,
        "correction_refs": source_snapshot.correction_refs,
        "dingtalk_refs": source_snapshot.dingtalk_refs,
    }
    row = DailyReportHistoryRecord(
        report_type="daily",
        business_date=business_date,
        period_type="day",
        period_start=business_date,
        period_end=business_date,
        source_snapshot_id=source_snapshot.id,
        source_run_id=source_snapshot.run_id,
        report_text=report_text,
        report_payload=report_payload,
        source_summary=source_summary,
        facts_hash=source_snapshot.payload_hash,
        text_hash=_hash_text(report_text),
        created_by_id=created_by_id,
        trace_id=trace_id,
    )
    db.add(row)
    db.flush()
    return row


def _source_status(source_snapshot: DailyFactBundleSnapshot) -> dict[str, Any]:
    payload = source_snapshot.sources or {}
    status = payload.get("source_status") if isinstance(payload, dict) else None
    return status if isinstance(status, dict) else {}


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_payload(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run archive test**

Run:

```powershell
python -m pytest backend/tests/test_daily_report_history_service.py::test_archive_daily_report_keeps_snapshot_and_hash_trace -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/report/daily_report_history.py backend/tests/test_daily_report_history_service.py
git commit -m "feat: archive daily reports with source trace"
```

---

### Task 14: Build Monthly and Annual Cumulative Rollups

**Files:**
- Create: `backend/app/services/report/period_rollup.py`
- Test: `backend/tests/test_period_rollup_service.py`

- [ ] **Step 1: Write failing month/year rollup test**

Create `backend/tests/test_period_rollup_service.py`:

```python
from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.reports import DailyReportHistoryRecord, OperationPeriodSnapshot
from app.services.report.period_rollup import build_operation_period_snapshot


def _history_row(day: date, output: float, cost: float) -> DailyReportHistoryRecord:
    return DailyReportHistoryRecord(
        report_type="daily",
        business_date=day,
        period_type="day",
        period_start=day,
        period_end=day,
        report_text=f"{day.isoformat()} 日报",
        report_payload={
            "facts": {
                "total_output_daily": {"value": output, "unit": "吨"},
                "verified_cost_total": {"value": cost, "unit": "元"},
            }
        },
        source_summary={"source_status": {"mes": "ok"}},
        facts_hash=f"{day.strftime('%Y%m%d'):0<64}"[:64],
        text_hash=f"{day.strftime('%d%m%Y'):0<64}"[:64],
    )


def test_build_month_and_year_rollups_from_archived_daily_reports() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine, tables=[DailyReportHistoryRecord.__table__, OperationPeriodSnapshot.__table__])
    db = Session(engine)
    db.add_all([
        _history_row(date(2026, 6, 1), 100.0, 80000.0),
        _history_row(date(2026, 6, 19), 366.0, 299300.0),
        _history_row(date(2026, 1, 1), 50.0, 50000.0),
    ])
    db.commit()

    month_snapshot = build_operation_period_snapshot(db, period_type="month", target_date=date(2026, 6, 19), trace_id="trace-month")
    year_snapshot = build_operation_period_snapshot(db, period_type="year", target_date=date(2026, 6, 19), trace_id="trace-year")

    assert month_snapshot.period_start.isoformat() == "2026-06-01"
    assert month_snapshot.period_end.isoformat() == "2026-06-19"
    assert month_snapshot.cumulative_metrics["total_output"]["value"] == 466.0
    assert month_snapshot.cumulative_metrics["verified_cost_total"]["value"] == 379300.0
    assert year_snapshot.period_start.isoformat() == "2026-01-01"
    assert year_snapshot.cumulative_metrics["total_output"]["value"] == 516.0
    assert year_snapshot.trace_id == "trace-year"
```

- [ ] **Step 2: Run the test**

Run:

```powershell
python -m pytest backend/tests/test_period_rollup_service.py::test_build_month_and_year_rollups_from_archived_daily_reports -q
```

Expected: FAIL because `period_rollup.py` does not exist.

- [ ] **Step 3: Implement period rollup service**

Create `backend/app/services/report/period_rollup.py`:

```python
from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.reports import DailyReportHistoryRecord, OperationPeriodSnapshot
from app.services.report.daily_report_history import hash_payload


def build_operation_period_snapshot(
    db: Session,
    *,
    period_type: str,
    target_date: date,
    trace_id: str | None = None,
    created_by_id: int | None = None,
) -> OperationPeriodSnapshot:
    period_start, period_end = _period_bounds(period_type, target_date)
    rows = (
        db.query(DailyReportHistoryRecord)
        .filter(DailyReportHistoryRecord.report_type == "daily")
        .filter(DailyReportHistoryRecord.business_date >= period_start)
        .filter(DailyReportHistoryRecord.business_date <= period_end)
        .order_by(DailyReportHistoryRecord.business_date.asc(), DailyReportHistoryRecord.id.asc())
        .all()
    )
    metrics = _sum_daily_metrics(rows)
    payload = {
        "period_type": period_type,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "cumulative_metrics": metrics,
        "source_daily_report_ids": [row.id for row in rows],
        "source_snapshot_ids": [row.source_snapshot_id for row in rows if row.source_snapshot_id is not None],
        "missing_dates": _missing_dates(rows, period_start, period_end),
    }
    snapshot = OperationPeriodSnapshot(
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        status="ready",
        cumulative_metrics=metrics,
        analysis_payload={},
        source_daily_report_ids=payload["source_daily_report_ids"],
        source_snapshot_ids=payload["source_snapshot_ids"],
        missing_dates=payload["missing_dates"],
        payload_hash=hash_payload(payload),
        created_by_id=created_by_id,
        trace_id=trace_id,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def _period_bounds(period_type: str, target_date: date) -> tuple[date, date]:
    if period_type == "month":
        return date(target_date.year, target_date.month, 1), target_date
    if period_type == "full_month":
        last_day = monthrange(target_date.year, target_date.month)[1]
        return date(target_date.year, target_date.month, 1), date(target_date.year, target_date.month, last_day)
    if period_type == "year":
        return date(target_date.year, 1, 1), target_date
    if period_type == "full_year":
        return date(target_date.year, 1, 1), date(target_date.year, 12, 31)
    raise ValueError(f"unsupported period_type: {period_type}")


def _sum_daily_metrics(rows: list[DailyReportHistoryRecord]) -> dict[str, dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    field_map = {
        "total_output_daily": "total_output",
        "verified_cost_total": "verified_cost_total",
        "electricity_fee": "electricity_fee",
        "gas_fee": "gas_fee",
    }
    for row in rows:
        facts = row.report_payload.get("facts") if isinstance(row.report_payload, dict) else {}
        if not isinstance(facts, dict):
            continue
        for source_field, target_field in field_map.items():
            item = facts.get(source_field)
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            if not isinstance(value, (int, float)):
                continue
            unit = item.get("unit")
            bucket = totals.setdefault(target_field, {"value": 0.0, "unit": unit, "source_fields": []})
            bucket["value"] = round(float(bucket["value"]) + float(value), 4)
            if source_field not in bucket["source_fields"]:
                bucket["source_fields"].append(source_field)
    return totals


def _missing_dates(rows: list[DailyReportHistoryRecord], period_start: date, period_end: date) -> list[str]:
    present = {row.business_date.isoformat() for row in rows if row.business_date is not None}
    cursor = period_start
    missing: list[str] = []
    while cursor <= period_end:
        value = cursor.isoformat()
        if value not in present:
            missing.append(value)
        cursor = date.fromordinal(cursor.toordinal() + 1)
    return missing
```

- [ ] **Step 4: Run rollup test**

Run:

```powershell
python -m pytest backend/tests/test_period_rollup_service.py::test_build_month_and_year_rollups_from_archived_daily_reports -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/report/period_rollup.py backend/tests/test_period_rollup_service.py
git commit -m "feat: build monthly and annual operation rollups"
```

---

### Task 15: Add Monthly and Annual Operating Situation Analysis

**Files:**
- Create: `backend/app/services/report/operation_analysis.py`
- Modify: `backend/app/services/report/period_rollup.py`
- Test: `backend/tests/test_operation_analysis_service.py`

- [ ] **Step 1: Write failing operation analysis test**

Create `backend/tests/test_operation_analysis_service.py`:

```python
from __future__ import annotations

from datetime import date

from app.models.reports import OperationPeriodSnapshot
from app.services.report.operation_analysis import analyze_operation_period


def test_analyze_monthly_operation_situation_returns_business_sections() -> None:
    snapshot = OperationPeriodSnapshot(
        period_type="month",
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 19),
        cumulative_metrics={
            "total_output": {"value": 5971.0, "unit": "吨"},
            "verified_cost_total": {"value": 4880207.0, "unit": "元"},
            "electricity_fee": {"value": 117200.0, "unit": "元"},
            "gas_fee": {"value": 182100.0, "unit": "元"},
        },
        source_daily_report_ids=[1, 2, 3],
        source_snapshot_ids=[10, 11, 12],
        missing_dates=[],
        analysis_payload={},
        payload_hash="b" * 64,
    )

    analysis = analyze_operation_period(snapshot)

    assert analysis["period_label"] == "2026-06-01 至 2026-06-19"
    assert analysis["sections"]["production"]["total_output"] == "5971.0吨"
    assert analysis["sections"]["cost"]["cost_per_ton"] == "817.31元/吨"
    assert analysis["sections"]["trace"]["daily_report_count"] == 3
    assert analysis["risks"] == []
```

- [ ] **Step 2: Run the test**

Run:

```powershell
python -m pytest backend/tests/test_operation_analysis_service.py::test_analyze_monthly_operation_situation_returns_business_sections -q
```

Expected: FAIL because `operation_analysis.py` does not exist.

- [ ] **Step 3: Implement operation analysis**

Create `backend/app/services/report/operation_analysis.py`:

```python
from __future__ import annotations

from typing import Any

from app.models.reports import OperationPeriodSnapshot


def analyze_operation_period(snapshot: OperationPeriodSnapshot) -> dict[str, Any]:
    metrics = snapshot.cumulative_metrics or {}
    output = _metric_value(metrics, "total_output")
    cost_total = _metric_value(metrics, "verified_cost_total")
    cost_per_ton = round(cost_total / output, 2) if output else None
    risks: list[str] = []
    if snapshot.missing_dates:
        risks.append(f"缺少{len(snapshot.missing_dates)}天历史日报，月/年累计可能不完整")
    if output == 0:
        risks.append("累计产量为0，无法计算吨成本")

    return {
        "period_type": snapshot.period_type,
        "period_label": f"{snapshot.period_start.isoformat()} 至 {snapshot.period_end.isoformat()}",
        "sections": {
            "production": {
                "total_output": _format_metric(output, _metric_unit(metrics, "total_output")),
            },
            "cost": {
                "verified_cost_total": _format_metric(cost_total, _metric_unit(metrics, "verified_cost_total")),
                "cost_per_ton": f"{cost_per_ton}元/吨" if cost_per_ton is not None else None,
            },
            "energy": {
                "electricity_fee": _format_metric(_metric_value(metrics, "electricity_fee"), _metric_unit(metrics, "electricity_fee")),
                "gas_fee": _format_metric(_metric_value(metrics, "gas_fee"), _metric_unit(metrics, "gas_fee")),
            },
            "trace": {
                "daily_report_count": len(snapshot.source_daily_report_ids or []),
                "source_snapshot_count": len(snapshot.source_snapshot_ids or []),
                "missing_dates": snapshot.missing_dates or [],
            },
        },
        "risks": risks,
    }


def _metric_value(metrics: dict[str, Any], key: str) -> float:
    item = metrics.get(key)
    if isinstance(item, dict) and isinstance(item.get("value"), (int, float)):
        return float(item["value"])
    return 0.0


def _metric_unit(metrics: dict[str, Any], key: str) -> str:
    item = metrics.get(key)
    if isinstance(item, dict) and item.get("unit"):
        return str(item["unit"])
    return ""


def _format_metric(value: float, unit: str) -> str:
    return f"{round(value, 2)}{unit}"
```

- [ ] **Step 4: Attach analysis to period rollup snapshots**

In `backend/app/services/report/period_rollup.py`, add:

```python
from app.services.report.operation_analysis import analyze_operation_period
```

After creating `snapshot` and before `db.add(snapshot)`, add:

```python
    snapshot.analysis_payload = analyze_operation_period(snapshot)
```

- [ ] **Step 5: Run analysis tests**

Run:

```powershell
python -m pytest backend/tests/test_operation_analysis_service.py backend/tests/test_period_rollup_service.py -q
```

Expected: selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/report/operation_analysis.py backend/app/services/report/period_rollup.py backend/tests/test_operation_analysis_service.py
git commit -m "feat: analyze monthly and annual operation snapshots"
```

---

### Task 16: Professionalize Hermes Knowledge Base

**Files:**
- Create: `backend/app/services/hermes_professional_knowledge_service.py`
- Modify: `backend/app/services/rag_service.py`
- Test: `backend/tests/test_hermes_professional_knowledge_service.py`

- [ ] **Step 1: Write failing professional knowledge test**

Create `backend/tests/test_hermes_professional_knowledge_service.py`:

```python
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.rag import HermesProfessionalKnowledgeEntry, RagQueryLog
from app.services.rag_service import query_knowledge
from app.services.hermes_professional_knowledge_service import search_professional_knowledge, upsert_professional_knowledge


def test_professional_knowledge_search_prefers_active_high_confidence_entries() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine, tables=[HermesProfessionalKnowledgeEntry.__table__])
    db = Session(engine)
    upsert_professional_knowledge(
        db,
        domain="daily_report",
        topic="成本核算",
        knowledge_type="calculation_rule",
        source_type="output_skill",
        source_ref="D:/输出skill/2026-6-19.txt",
        content="成本核算按已核电费、气费合计除以入库成品吨数。",
        structured_payload={"formula": "(electricity_fee + gas_fee) / finished_goods_tons"},
        confidence=95,
        trace_id="trace-knowledge",
    )
    db.commit()

    matches = search_professional_knowledge(db, domain="daily_report", query="成本怎么按吨算")

    assert len(matches) == 1
    assert matches[0]["topic"] == "成本核算"
    assert matches[0]["source_type"] == "output_skill"
    assert matches[0]["confidence"] == 95


def test_query_knowledge_uses_professional_entries_before_generic_chunks() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine, tables=[HermesProfessionalKnowledgeEntry.__table__, RagQueryLog.__table__])
    db = Session(engine)
    upsert_professional_knowledge(
        db,
        domain="daily_report",
        topic="日报模板",
        knowledge_type="report_pattern",
        source_type="dingtalk_file",
        source_ref="dingtalk://file/daily-report-template",
        content="日报先输出总产量、月累计，再输出各车间明细和成本核算。",
        confidence=90,
    )
    db.commit()

    payload = query_knowledge(db, query="日报要先写什么", limit=5)

    assert payload["source"] == "professional_knowledge"
    assert "总产量" in payload["answer"]
    assert payload["citations"][0]["source_type"] == "dingtalk_file"
```

- [ ] **Step 2: Run the test**

Run:

```powershell
python -m pytest backend/tests/test_hermes_professional_knowledge_service.py::test_professional_knowledge_search_prefers_active_high_confidence_entries -q
```

Expected: FAIL because `hermes_professional_knowledge_service.py` does not exist.

- [ ] **Step 3: Implement professional knowledge service**

Create `backend/app/services/hermes_professional_knowledge_service.py`:

```python
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.rag import HermesProfessionalKnowledgeEntry


def upsert_professional_knowledge(
    db: Session,
    *,
    domain: str,
    topic: str,
    knowledge_type: str,
    source_type: str,
    source_ref: str,
    content: str,
    structured_payload: dict[str, Any] | None = None,
    confidence: int = 80,
    valid_from: date | None = None,
    valid_to: date | None = None,
    trace_id: str | None = None,
    created_by_id: int | None = None,
) -> HermesProfessionalKnowledgeEntry:
    row = (
        db.query(HermesProfessionalKnowledgeEntry)
        .filter(HermesProfessionalKnowledgeEntry.domain == domain)
        .filter(HermesProfessionalKnowledgeEntry.topic == topic)
        .filter(HermesProfessionalKnowledgeEntry.knowledge_type == knowledge_type)
        .filter(HermesProfessionalKnowledgeEntry.source_ref == source_ref)
        .one_or_none()
    )
    if row is None:
        row = HermesProfessionalKnowledgeEntry(
            domain=domain,
            topic=topic,
            knowledge_type=knowledge_type,
            source_type=source_type,
            source_ref=source_ref,
            content=content,
            structured_payload=structured_payload or {},
            confidence=confidence,
            valid_from=valid_from,
            valid_to=valid_to,
            status="active",
            trace_id=trace_id,
            created_by_id=created_by_id,
        )
        db.add(row)
    else:
        row.source_type = source_type
        row.content = content
        row.structured_payload = structured_payload or {}
        row.confidence = confidence
        row.valid_from = valid_from
        row.valid_to = valid_to
        row.status = "active"
        row.trace_id = trace_id
    db.flush()
    return row


def search_professional_knowledge(db: Session, *, domain: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
    terms = _query_terms(query)
    if not terms:
        return []
    rows = (
        db.query(HermesProfessionalKnowledgeEntry)
        .filter(HermesProfessionalKnowledgeEntry.domain == domain)
        .filter(HermesProfessionalKnowledgeEntry.status == "active")
        .order_by(HermesProfessionalKnowledgeEntry.confidence.desc(), HermesProfessionalKnowledgeEntry.updated_at.desc())
        .limit(50)
        .all()
    )
    scored: list[tuple[int, HermesProfessionalKnowledgeEntry]] = []
    for row in rows:
        haystack = f"{row.topic} {row.knowledge_type} {row.content}"
        hits = sum(1 for term in terms if term in haystack)
        if hits:
            scored.append((row.confidence + hits * 10, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "id": row.id,
            "domain": row.domain,
            "topic": row.topic,
            "knowledge_type": row.knowledge_type,
            "source_type": row.source_type,
            "source_ref": row.source_ref,
            "content": row.content,
            "structured_payload": row.structured_payload,
            "confidence": row.confidence,
        }
        for _, row in scored[:limit]
    ]


def _query_terms(query: str) -> list[str]:
    clean = str(query or "").replace("，", " ").replace("。", " ").strip()
    split_terms = [item for item in clean.split() if item]
    compact = "".join(split_terms)
    grams = [compact[index:index + 2] for index in range(max(0, len(compact) - 1))]
    return sorted(set(split_terms + grams), key=len, reverse=True)
```

- [ ] **Step 4: Route Hermes RAG to professional knowledge first**

In `backend/app/services/rag_service.py`, add this import:

```python
from app.services.hermes_professional_knowledge_service import search_professional_knowledge
```

In `query_knowledge()`, after the empty-query block and before `tokens = _query_tokens(clean_query)`, add:

```python
    professional_matches = search_professional_knowledge(db, domain="daily_report", query=clean_query, limit=5)
    if professional_matches:
        citations = [
            {
                "source_type": item["source_type"],
                "source_ref": item["source_ref"],
                "topic": item["topic"],
                "confidence": item["confidence"],
            }
            for item in professional_matches
        ]
        answer = "\n".join(item["content"] for item in professional_matches)
        _write_query_log(db, query_text=clean_query, answer=answer, citations=citations, user=user)
        return {
            "answer": "\n".join(item["content"] for item in professional_matches),
            "citations": citations,
            "items": professional_matches,
            "source": "professional_knowledge",
        }
```

Keep the existing generic RAG path as the fallback after this block.

- [ ] **Step 5: Run knowledge tests**

Run:

```powershell
python -m pytest backend/tests/test_hermes_professional_knowledge_service.py -q
```

Expected: selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/hermes_professional_knowledge_service.py backend/app/services/rag_service.py backend/tests/test_hermes_professional_knowledge_service.py
git commit -m "feat: add professional hermes knowledge layer"
```

---

### Task 17: Verification, Documentation, and Rollout Guard

**Files:**
- Modify: `docs/superpowers/specs/2026-06-22-hermes-daily-fact-bundle-phase2-design.md`
- Modify: `docs/deploy/current-state.md` only if deployment is completed in a later deploy step

- [ ] **Step 1: Run focused backend tests**

Run:

```powershell
python -m pytest `
  backend/tests/test_daily_fact_bundle_service.py `
  backend/tests/test_hermes_intent_service.py `
  backend/tests/test_hermes_day1_source_service.py `
  backend/tests/test_hermes_day1_report_service.py `
  backend/tests/test_hermes_day1_cli_dx.py `
  backend/tests/test_agent_cli.py `
  backend/tests/test_report_history_period_knowledge_models.py `
  backend/tests/test_daily_report_history_service.py `
  backend/tests/test_period_rollup_service.py `
  backend/tests/test_operation_analysis_service.py `
  backend/tests/test_hermes_professional_knowledge_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run compile check**

Run:

```powershell
python -m compileall backend/app backend/scripts
```

Expected: command exits `0`.

- [ ] **Step 3: Run full backend tests if time allows**

Run:

```powershell
python -m pytest backend/tests -q
```

Expected: existing suite passes or only pre-existing unrelated failures are reported with exact test names.

- [ ] **Step 4: Update spec implementation status**

Append this section to `docs/superpowers/specs/2026-06-22-hermes-daily-fact-bundle-phase2-design.md`:

```markdown
## 17. Implementation Status

Phase 2.1 implementation added the `DailyFactBundle` module, persistence models, source priority handling, root_owner corrections, DingTalk supplements, output skill alignment, Hermes Day-1 source integration, flexible intent parsing, traceable historical daily report archive, monthly and annual cumulative operation snapshots, monthly and annual operating situation analysis, and the professional Hermes knowledge layer.

Production rollout remains behind the existing Hermes Day-1 gate until focused tests, historical trace checks, period rollup checks, knowledge retrieval checks, and production doctor checks pass.
```

- [ ] **Step 5: Run diff check**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 6: Commit verification docs**

```powershell
git add docs/superpowers/specs/2026-06-22-hermes-daily-fact-bundle-phase2-design.md
git commit -m "docs: record hermes fact history analysis implementation status"
```

- [ ] **Step 7: Final rollout guard**

Before deploying, run:

```powershell
git status -sb
git log -5 --oneline
```

Expected:

```text
## feature/hermes-daily-fact-bundle-phase2
```

with only intentional commits from this plan.

Do not enable `HERMES_DAY1_ENABLED=true` as part of this plan. That remains a separate production decision after doctor checks.

---

## Self-Review

### Spec Coverage

- DailyFactBundle single interface: Task 2.
- Business-day fact bundle: Task 2.
- root_owner corrections: Task 3 and Task 11.
- DingTalk high-priority supplements: Task 4.
- Source priority and conflicts: Task 3 and Task 4.
- Lightweight run records and formal snapshots: Task 1 and Task 5.
- Output skill alignment: Task 6.
- Hermes Day-1 integration: Task 7 and Task 8.
- Flexible natural-language intent: Task 9 and Task 10.
- Data hub subtraction: Task 7 and Task 17 start the migration without deleting old paths.
- Volume optimization: Task 5 stores light runs and snapshot-only formal bundles.
- Traceable historical daily reports: Task 12 and Task 13.
- Monthly cumulative facts and annual cumulative facts: Task 14.
- Monthly operating situation and annual operating situation analysis: Task 15.
- Professional knowledge base: Task 12 and Task 16.

### Placeholder Scan

Every task has exact files, code, commands, and expected results. There are no unfinished placeholder steps.

### Type Consistency

The plan uses these stable names throughout:

- `build_daily_fact_bundle`
- `DailyFactBundleRun`
- `DailyFactBundleSnapshot`
- `DailyFactCorrection`
- `parse_hermes_intent`
- `root_owner_correction`
- `dingtalk_supplement`
- `archive_daily_report`
- `build_operation_period_snapshot`
- `analyze_operation_period`
- `upsert_professional_knowledge`
- `search_professional_knowledge`

The bundle payload stores `confidence` as `0.0..1.0`; the run row stores `confidence` as integer percent `0..100`.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 offline merged pass | APPLIED | Plan expanded from "daily report facts" to "factory operation brain": historical daily reports, month/year cumulative facts, monthly/yearly operating situation, and professional knowledge are now in scope. |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | SKIPPED | User requested plan optimization, not an outside-model challenge; no code implementation was changed. |
| Eng Review | `/plan-eng-review` | Architecture & tests | 1 offline merged pass | APPLIED | Added explicit models, migrations, services, focused tests, source trace, hash trace, period rollups, and exact `query_knowledge()` insertion point. |
| Design Review | `/plan-design-review` | Information architecture | 1 offline merged pass | APPLIED | No frontend UI scope was added; plan information structure now separates daily facts, historical archive, period snapshots, operation analysis, and professional knowledge. |
| DX Review | `/plan-devex-review` | Developer execution quality | 1 offline merged pass | APPLIED | Added exact file paths, test names, commands, expected results, and reduced ambiguity around RAG integration and historical trace behavior. |

- **UNRESOLVED:** 0.
- **VERDICT:** CEO + ENG + DESIGN + DEVEX findings applied to the plan. Ready for `subagent-driven-development` or `executing-plans` implementation from an `origin/main` worktree containing Day-1 files.
