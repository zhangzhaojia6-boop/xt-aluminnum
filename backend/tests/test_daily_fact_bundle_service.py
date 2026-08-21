from __future__ import annotations

from collections.abc import Iterator
import importlib.util
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Table, create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.domain.daily_report_field_contract import normative_daily_report_fields
from app.models.agent_communication import ChatInboxMessage, MultimodalEvidence
from app.models.energy import EnergyImportRecord
from app.models.imports import ImportBatch, ImportedDailyMetricFact, ImportRow
from app.models.mes import (
    MesCoilSnapshot,
    MesMaterialRecord,
    MesStockRecord,
    MesSyncCursor,
    MesSyncRunLog,
    MesWorkshopProcessRecord,
)
from app.models.reports import DailyFactBundleRun, DailyFactBundleSnapshot, DailyFactCorrection
from app.models.system import User
from app.services.report.output_skill_report_parser import parse_output_skill_daily_report


EXPECTED_CRITICAL_DAILY_FACT_FIELDS = {
    "total_output_daily",
    "finished_inbound_daily",
    "wip_total",
    "total_electricity_kwh",
    "daily_yield_rate",
}


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, User.__table__),
            cast(Table, ChatInboxMessage.__table__),
            cast(Table, MultimodalEvidence.__table__),
            cast(Table, ImportBatch.__table__),
            cast(Table, ImportRow.__table__),
            cast(Table, ImportedDailyMetricFact.__table__),
            cast(Table, EnergyImportRecord.__table__),
            cast(Table, MesMaterialRecord.__table__),
            cast(Table, MesStockRecord.__table__),
            cast(Table, MesCoilSnapshot.__table__),
            cast(Table, MesWorkshopProcessRecord.__table__),
            cast(Table, MesSyncCursor.__table__),
            cast(Table, MesSyncRunLog.__table__),
            cast(Table, DailyFactBundleRun.__table__),
            cast(Table, DailyFactBundleSnapshot.__table__),
            cast(Table, DailyFactCorrection.__table__),
        ],
    )
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _fact_closure_field(bundle: dict[str, Any], field_name: str) -> dict[str, Any]:
    return next(
        item
        for item in bundle["fact_closure"]["critical_fields"]
        if item["field"] == field_name
    )


def test_daily_fact_bundle_tables_are_registered() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            cast(Table, DailyFactBundleRun.__table__),
            cast(Table, DailyFactBundleSnapshot.__table__),
            cast(Table, DailyFactCorrection.__table__),
        ],
    )

    _assert_daily_fact_bundle_schema(inspect(engine), expect_snapshot_key=True)


def test_daily_fact_bundle_migration_creates_sqlite_tables_and_indexes(monkeypatch) -> None:
    migration = _load_daily_fact_bundle_migration()
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        sa.Table("users", sa.MetaData(), sa.Column("id", sa.Integer(), primary_key=True)).create(connection)
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        monkeypatch.setattr(migration, "op", operations)

        migration.upgrade()
        _assert_daily_fact_bundle_schema(inspect(connection), expect_snapshot_key=False)

        migration.upgrade()
        _assert_daily_fact_bundle_schema(inspect(connection), expect_snapshot_key=False)

        migration.downgrade()
        table_names = set(inspect(connection).get_table_names())
        assert "daily_fact_bundle_runs" not in table_names
        assert "daily_fact_bundle_snapshots" not in table_names
        assert "daily_fact_corrections" not in table_names


def test_daily_fact_bundle_snapshot_key_migration_adds_unique_nullable_key(monkeypatch) -> None:
    base_migration = _load_daily_fact_bundle_migration()
    snapshot_key_migration = _load_snapshot_key_migration()
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        sa.Table("users", sa.MetaData(), sa.Column("id", sa.Integer(), primary_key=True)).create(connection)
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        monkeypatch.setattr(base_migration, "op", operations)
        monkeypatch.setattr(snapshot_key_migration, "op", operations)

        base_migration.upgrade()
        snapshot_key_migration.upgrade()
        _assert_daily_fact_bundle_schema(inspect(connection), expect_snapshot_key=True)

        snapshot_key_migration.downgrade()
        _assert_daily_fact_bundle_schema(inspect(connection), expect_snapshot_key=False)


def test_build_daily_fact_bundle_uses_template_facts(monkeypatch, db_session: Session) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        assert target_date == date(2026, 6, 19)
        return {
            "values": {
                "total_output_daily": 366,
                "total_electricity_kwh": 146500,
            },
            "sources": {
                "total_output_daily": "mes_packaging_output",
                "total_electricity_kwh": "owner_or_energy_summary",
            },
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["business_date"] == "2026-06-19"
    assert bundle["status"] == "ready"
    assert isinstance(bundle["generated_at"], str)
    fact = bundle["facts"]["total_output_daily"]
    assert fact["value"] == 366
    assert fact["unit"] == "吨"
    assert fact["source"] == "mes_packaging_output"
    assert fact["source_type"] == "mes_packaging_output"
    assert fact["priority"] == 80
    assert fact["confidence"] == 0.85
    assert fact["adoption_reason"] == "来自 mes_packaging_output"
    assert fact["source_detail"] == {"source": "mes_packaging_output"}
    assert fact["evidence_status"] == "needs_evidence"
    assert "missing_trace_id" in fact["evidence_gaps"]
    assert bundle["missing_fields"] == []
    assert bundle["missing"] == []
    assert bundle["conflicts"] == []
    assert "fact_closure" in bundle
    assert {
        item["field"]
        for item in bundle["fact_closure"]["critical_fields"]
    } == EXPECTED_CRITICAL_DAILY_FACT_FIELDS


def test_daily_fact_bundle_empty_mes_projection_needs_evidence_without_forged_metadata(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"total_output_daily": 0},
            "sources": {
                "total_output_daily": {
                    "source_type": "mes_packaging_output",
                    "source_table": "MES_ProductProcessRecord",
                    "row_count": 0,
                }
            },
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
    )

    fact = bundle["facts"]["total_output_daily"]
    assert fact["source_detail"] == {
        "source_type": "mes_packaging_output",
        "source_table": "MES_ProductProcessRecord",
        "row_count": 0,
    }
    assert _fact_closure_field(bundle, "total_output_daily")["status"] == "needs_evidence"


def test_daily_fact_bundle_direct_source_requires_row_or_sync_evidence(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_output_daily": 366},
            "sources": {
                "total_output_daily": {
                    "source_type": "mes_packaging_output",
                    "source_ref": "MES_ProductProcessRecord",
                    "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
                    "unit": "吨",
                    "trace_id": "projection-read:packaging:2026-07-07",
                    "metric_contract_version": "2026-07-11",
                }
            },
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
    )

    fact = bundle["facts"]["total_output_daily"]
    assert fact["evidence_status"] == "needs_evidence"
    assert "missing_read_evidence" in fact["evidence_gaps"]
    assert _fact_closure_field(bundle, "total_output_daily")["status"] == "needs_evidence"


def test_daily_fact_bundle_confirms_locked_promoted_output_workbook(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.domain.metric_contracts import DAILY_REPORT_METRIC_CONTRACT_VERSION
    from app.services.daily_production_canonical_service import build_daily_production_lineage_hash
    from app.services.report import daily_fact_bundle

    anchors = [{"row_index": 39, "sheet_name": "2026-7-17", "column_index": 26}]
    mapped_data = {
        "business_date": "2026-07-17",
        "quality_status": "ready",
        "report_metrics": [
            {
                "field_name": "total_output_daily",
                "value": 286,
                "unit": "吨",
                "source_anchors": anchors,
            }
        ],
    }
    mapped_data["lineage_hash"] = build_daily_production_lineage_hash(mapped_data)
    batch = ImportBatch(
        batch_no="IMP-OUTPUT-EVIDENCE-20260717",
        import_type="daily_production_report",
        source_type="daily_production_report_locked",
        file_name="daily-production-2026-07-17.xlsx",
        status="completed",
        quality_status="ready",
        parsed_successfully=True,
    )
    db_session.add(batch)
    db_session.flush()
    import_row = ImportRow(
        batch_id=batch.id,
        row_number=1,
        status="success",
        mapped_data=mapped_data,
    )
    db_session.add(import_row)
    db_session.flush()
    metric_fact = ImportedDailyMetricFact(
        business_date=date(2026, 7, 17),
        field_name="total_output_daily",
        metric_value=286,
        unit="吨",
        source_kind="daily_production_report",
        import_batch_id=batch.id,
        import_row_id=import_row.id,
        source_anchors=anchors,
        lineage_hash=mapped_data["lineage_hash"],
        metric_contract_version="2026-07-18",
        data_status="confirmed",
    )
    db_session.add(metric_fact)
    db_session.commit()
    trace_id = (
        f"import-read:imported_daily_metric_facts:{metric_fact.id}:"
        f"total_output_daily:{metric_fact.lineage_hash[:12]}"
    )
    source = {
        "source_type": "manual_workbook",
        "source_ref": "imported_daily_metric_facts",
        "metric_fact_id": metric_fact.id,
        "import_batch_id": batch.id,
        "import_row_id": import_row.id,
        "business_date": "2026-07-17",
        "business_window": "2026-07-17T07:50:00+08:00/2026-07-18T07:50:00+08:00",
        "unit": "吨",
        "row_anchors": anchors,
        "lineage_hash": metric_fact.lineage_hash,
        "metric_contract_version": DAILY_REPORT_METRIC_CONTRACT_VERSION,
        "field_contract_version": "2026-07-18",
        "trace_id": trace_id,
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_output_daily": 286},
            "sources": {"total_output_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 17),
        now=datetime(2026, 7, 18, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    fact = bundle["facts"]["total_output_daily"]
    assert fact["evidence_status"] == "confirmed"
    assert fact["evidence_gaps"] == []
    assert _fact_closure_field(bundle, "total_output_daily")["status"] == "confirmed"

    source["metric_fact_id"] = metric_fact.id + 999
    rejected = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 17),
        now=datetime(2026, 7, 18, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    assert rejected["facts"]["total_output_daily"]["evidence_status"] == "needs_evidence"


def test_daily_fact_bundle_confirms_locked_energy_workbook_rows(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.domain.metric_contracts import DAILY_REPORT_METRIC_CONTRACT_VERSION
    from app.services.report import daily_fact_bundle

    batch = ImportBatch(
        batch_no="IMP-ENERGY-EVIDENCE-20260717",
        import_type="energy",
        source_type="daily_energy_report_locked",
        file_name="daily-energy-2026-07-17.xls",
        file_size=1024,
        file_path=json.dumps(
                {
                    "electricity_file": "workshop-electricity.xls",
                    "gas_file": "furnace-gas.xls",
                },
            ensure_ascii=False,
        ),
        total_rows=3,
        success_rows=2,
        failed_rows=0,
        skipped_rows=1,
        status="completed",
        quality_status="ready",
        parsed_successfully=True,
    )
    db_session.add(batch)
    db_session.flush()
    component_raw = {
        "source_kind": "workshop_electricity",
        "source_file": "workshop-electricity.xls",
        "source_sheet": "日电量",
        "source_row_no": 8,
        "source_label": "铸锭",
        "energy_value": 100000,
        "unit": "kWh",
    }
    component_row = ImportRow(
        batch_id=batch.id,
        row_number=1,
        status="success",
        raw_data=component_raw,
        mapped_data={
            **component_raw,
            "business_date": "2026-07-17",
            "workshop_code": "ZD",
            "shift_code": None,
            "status": "success",
            "report_field": None,
        },
    )
    total_raw = {
        "source_kind": "workshop_electricity",
        "source_file": "workshop-electricity.xls",
        "source_sheet": "日电量",
        "source_row_no": 29,
        "source_label": "高压合计",
        "energy_value": 173500,
        "unit": "kWh",
    }
    import_row = ImportRow(
        batch_id=batch.id,
        row_number=26,
        status="skipped",
        raw_data=total_raw,
        mapped_data={
            **total_raw,
            "business_date": "2026-07-17",
            "workshop_code": None,
            "shift_code": None,
            "status": "skipped",
            "report_field": "total_electricity_kwh",
        },
        error_msg="unmapped energy label: 高压合计",
    )
    component_row.mapped_data["energy_type"] = "electricity"
    import_row.mapped_data["energy_type"] = "electricity"
    legacy_gas_raw = {
        "source_kind": "furnace_gas",
        "source_file": "furnace-gas.xls",
        "source_sheet": "日报",
        "source_row_no": 9,
        "source_label": "热轧/1#加热炉东",
        "energy_value": 12000,
        "unit": "Nm3",
    }
    legacy_gas_row = ImportRow(
        batch_id=batch.id,
        row_number=2,
        status="success",
        raw_data=legacy_gas_raw,
        mapped_data={
            **legacy_gas_raw,
            "business_date": "2026-07-17",
            "workshop_code": "RZ",
            "shift_code": None,
            "energy_type": "gas",
            "status": "success",
            "report_field": "hot_roll_furnace_gas_m3",
        },
    )
    db_session.add_all([component_row, legacy_gas_row, import_row])
    db_session.flush()
    promoted_record = EnergyImportRecord(
        import_batch_id=batch.id,
        business_date=date(2026, 7, 17),
        workshop_code="ZD",
        shift_code=None,
        energy_type="electricity",
        energy_value=100000,
        unit="kWh",
        source_row_no=8,
        raw_payload=component_raw,
    )
    legacy_gas_record = EnergyImportRecord(
        import_batch_id=batch.id,
        business_date=date(2026, 7, 17),
        workshop_code="RZ",
        shift_code=None,
        energy_type="gas",
        energy_value=12000,
        unit="Nm3",
        source_row_no=9,
        raw_payload=legacy_gas_raw,
    )
    db_session.add_all([promoted_record, legacy_gas_record])
    db_session.commit()
    trace_id = f"import-read:import_rows:{batch.id}:total_electricity_kwh:{import_row.id}"
    source = {
        "source_type": "manual_workbook",
        "source_ref": "import_rows",
        "import_batch_id": batch.id,
        "business_date": "2026-07-17",
        "business_window": "2026-07-17T07:50:00+08:00/2026-07-18T07:50:00+08:00",
        "unit": "度",
        "row_count": 1,
        "row_anchors": [{"import_row_id": import_row.id}],
        "metric_contract_version": DAILY_REPORT_METRIC_CONTRACT_VERSION,
        "field_contract_version": "2026-07-18",
        "trace_id": trace_id,
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_electricity_kwh": 173500},
            "sources": {"total_electricity_kwh": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 17),
        now=datetime(2026, 7, 18, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    fact = bundle["facts"]["total_electricity_kwh"]
    assert fact["evidence_status"] == "confirmed"
    assert fact["evidence_gaps"] == []
    assert _fact_closure_field(bundle, "total_electricity_kwh")["status"] == "confirmed"

    promoted_record.raw_payload = {"tampered": True}
    db_session.commit()
    rejected = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 17),
        now=datetime(2026, 7, 18, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    assert rejected["facts"]["total_electricity_kwh"]["evidence_status"] == "needs_evidence"

    promoted_record.raw_payload = component_raw
    db_session.commit()
    source["row_anchors"] = [{"import_row_id": import_row.id + 999}]
    rejected = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 17),
        now=datetime(2026, 7, 18, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    assert rejected["facts"]["total_electricity_kwh"]["evidence_status"] == "needs_evidence"


def test_daily_fact_bundle_rejects_named_mes_trace_even_with_positive_row_count(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    source = {
        "source_type": "mes_material_records",
        "source_ref": "mes_material_records",
        "business_window": "2026-07-07T10:00:00+08:00/2026-07-08T10:00:00+08:00",
        "unit": "吨",
        "row_count": 1,
        "trace_id": "mes:total_output_daily:2026-07-07",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_output_daily": 70},
            "sources": {"total_output_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 10, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    fact = bundle["facts"]["total_output_daily"]
    assert fact["evidence_status"] == "needs_evidence"
    assert "missing_read_evidence" in fact["evidence_gaps"]


@pytest.mark.parametrize(
    ("source_ref", "latest_row_id_offset", "trace_table", "trace_count"),
    [
        ("mes_material_records", 0, "mes_stock_records", 1),
        ("mes_material_records", 999, "mes_material_records", 1),
        ("mes_material_records", 0, "mes_material_records", 2),
    ],
)
def test_daily_fact_bundle_rejects_unverifiable_projection_trace(
    monkeypatch,
    db_session: Session,
    source_ref: str,
    latest_row_id_offset: int,
    trace_table: str,
    trace_count: int,
) -> None:
    from app.services.report import daily_fact_bundle

    row = MesMaterialRecord(
        source_id="trace-validation-material",
        source_path="sqlserver:MES_Material",
        workshop_name="热轧车间",
        weight_tons=70,
        production_date=datetime(2026, 7, 8, 9, 30),
        business_date=date(2026, 7, 7),
    )
    db_session.add(row)
    db_session.commit()
    claimed_row_id = row.id + latest_row_id_offset
    source = {
        "source_type": "mes_material_records",
        "source_ref": source_ref,
        "source_table": "MES_Material",
        "business_window": "2026-07-07T10:00:00+08:00/2026-07-08T10:00:00+08:00",
        "unit": "吨",
        "row_count": 1,
        "latest_row_id": claimed_row_id,
        "trace_id": f"projection-read:{trace_table}:{claimed_row_id}:{trace_count}",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_output_daily": 70},
            "sources": {"total_output_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 10, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    fact = bundle["facts"]["total_output_daily"]
    assert fact["evidence_status"] == "needs_evidence"
    assert "missing_read_evidence" in fact["evidence_gaps"]


def test_daily_fact_bundle_rejects_unknown_mes_sync_run_as_read_evidence(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_output_daily": 366},
            "sources": {
                "total_output_daily": {
                    "source_type": "mes_packaging_output",
                    "source_ref": "MES_ProductProcessRecord",
                    "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
                    "unit": "吨",
                    "sync_run_id": 999,
                    "trace_id": "mes-sync-run:999",
                    "metric_contract_version": "2026-07-11",
                }
            },
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
    )

    fact = bundle["facts"]["total_output_daily"]
    assert fact["evidence_status"] == "needs_evidence"
    assert "missing_read_evidence" in fact["evidence_gaps"]
    assert _fact_closure_field(bundle, "total_output_daily")["status"] == "needs_evidence"


@pytest.mark.parametrize(
    ("evidence_cursor_key", "evidence_trace_id", "expected_status"),
    [
        ("mes_workshop_process_records_between", None, "needs_evidence"),
        ("mes_stock_records_between", None, "needs_evidence"),
        ("mes_workshop_process_records_between", "mes-sync-run:999", "needs_evidence"),
    ],
)
def test_daily_fact_bundle_only_accepts_matching_completed_mes_sync_run(
    monkeypatch,
    db_session: Session,
    evidence_cursor_key: str,
    evidence_trace_id: str | None,
    expected_status: str,
) -> None:
    from app.services.report import daily_fact_bundle

    sync_run = MesSyncRunLog(
        cursor_key="mes_workshop_process_records_between",
        started_at=datetime(2026, 7, 8, 7, 55, tzinfo=ZoneInfo("Asia/Shanghai")),
        finished_at=datetime(2026, 7, 8, 7, 56, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="success",
        fetched_count=3,
        metadata_json={"window_started_at": "2026-07-07T07:50:00+08:00"},
    )
    db_session.add(
        MesSyncCursor(
            cursor_key="mes_workshop_process_records_between",
            last_synced_at=datetime(2026, 7, 8, 7, 55, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    )
    db_session.add(sync_run)
    db_session.commit()
    source = {
        "source_type": "mes_packaging_output",
        "source_ref": "MES_ProductProcessRecord",
        "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
        "unit": "吨",
        "sync_run_id": sync_run.id,
        "cursor_key": evidence_cursor_key,
        "trace_id": evidence_trace_id or f"mes-sync-run:{sync_run.id}",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_output_daily": 366},
            "sources": {"total_output_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    fact = bundle["facts"]["total_output_daily"]
    assert fact["evidence_status"] == expected_status
    assert ("missing_read_evidence" in fact["evidence_gaps"]) is (expected_status == "needs_evidence")


def test_daily_fact_bundle_rejects_valid_sync_run_without_matching_field_value(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    cursor_key = "mes_workshop_process_records_between"
    cursor = MesSyncCursor(
        cursor_key=cursor_key,
        last_synced_at=datetime(2026, 7, 8, 7, 55, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    run = MesSyncRunLog(
        cursor_key=cursor_key,
        started_at=datetime(2026, 7, 8, 7, 54, tzinfo=ZoneInfo("Asia/Shanghai")),
        finished_at=datetime(2026, 7, 8, 7, 56, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="success",
        fetched_count=3,
        metadata_json={"window_started_at": "2026-07-07T07:50:00+08:00"},
    )
    db_session.add_all([cursor, run])
    db_session.commit()
    source = {
        "source_type": "mes_packaging_output",
        "source_ref": "MES_ProductProcessRecord",
        "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
        "unit": "吨",
        "row_count": 0,
        "sync_run_id": run.id,
        "cursor_key": cursor_key,
        "trace_id": f"mes-sync-run:{run.id}",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_output_daily": 999999},
            "sources": {"total_output_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert bundle["facts"]["total_output_daily"]["evidence_status"] == "needs_evidence"


@pytest.mark.parametrize(
    ("evidence_cursor_key", "expected_status"),
    [
        ("mes_workshop_process_records_between", "confirmed"),
        ("mes_stock_records_between", "needs_evidence"),
    ],
)
def test_daily_fact_bundle_validates_attached_sync_metadata_after_projection(
    monkeypatch,
    db_session: Session,
    evidence_cursor_key: str,
    expected_status: str,
) -> None:
    from app.services.report import daily_fact_bundle

    row = MesWorkshopProcessRecord(
        source_id="projection-with-mismatched-sync",
        source_path="sqlserver:workshop_process_records",
        workshop_name="精整",
        process_name="包装",
        output_weight_tons=100,
        business_date=date(2026, 7, 7),
    )
    cursor_key = "mes_workshop_process_records_between"
    cursor = MesSyncCursor(
        cursor_key=cursor_key,
        last_synced_at=datetime(2026, 7, 8, 7, 55, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    run = MesSyncRunLog(
        cursor_key=cursor_key,
        started_at=datetime(2026, 7, 8, 7, 54, tzinfo=ZoneInfo("Asia/Shanghai")),
        finished_at=datetime(2026, 7, 8, 7, 56, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="success",
        fetched_count=1,
        metadata_json={"window_started_at": "2026-07-07T07:50:00+08:00"},
    )
    db_session.add_all([row, cursor, run])
    db_session.commit()
    source = {
        "source_type": "mes_packaging_output",
        "source_ref": "mes_workshop_process_records",
        "source_table": "MES_ProductProcessRecord",
        "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
        "unit": "吨",
        "row_count": 1,
        "latest_row_id": row.id,
        "trace_id": f"projection-read:mes_workshop_process_records:{row.id}:1",
        "metric_contract_version": "2026-07-11",
        "sync_run_id": run.id,
        "cursor_key": evidence_cursor_key,
        "sync_trace_id": f"mes-sync-run:{run.id}",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_output_daily": 100},
            "sources": {"total_output_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert bundle["facts"]["total_output_daily"]["evidence_status"] == expected_status


def test_daily_fact_bundle_rejects_sync_run_without_real_cursor(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    sync_run = MesSyncRunLog(
        cursor_key="mes_workshop_process_records_between",
        started_at=datetime(2026, 7, 8, 7, 55, tzinfo=ZoneInfo("Asia/Shanghai")),
        finished_at=datetime(2026, 7, 8, 7, 56, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="success",
        fetched_count=3,
    )
    db_session.add(sync_run)
    db_session.commit()
    source = {
        "source_type": "mes_packaging_output",
        "source_ref": "MES_ProductProcessRecord",
        "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
        "unit": "吨",
        "sync_run_id": sync_run.id,
        "cursor_key": sync_run.cursor_key,
        "trace_id": f"mes-sync-run:{sync_run.id}",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_output_daily": 366},
            "sources": {"total_output_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert bundle["facts"]["total_output_daily"]["evidence_status"] == "needs_evidence"


def test_daily_fact_bundle_rejects_sync_run_that_does_not_cover_business_window(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    cursor_key = "mes_workshop_process_records_between"
    cursor = MesSyncCursor(
        cursor_key=cursor_key,
        last_synced_at=datetime(2026, 7, 8, 7, 55, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    run = MesSyncRunLog(
        cursor_key=cursor_key,
        started_at=datetime(2026, 7, 8, 7, 55, tzinfo=ZoneInfo("Asia/Shanghai")),
        finished_at=datetime(2026, 7, 8, 7, 56, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="success",
        fetched_count=3,
        metadata_json={"window_started_at": "2026-07-08T07:00:00+08:00"},
    )
    db_session.add_all([cursor, run])
    db_session.commit()
    source = {
        "source_type": "mes_verified",
        "source_ref": "MES_ProductProcessRecord",
        "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
        "unit": "吨",
        "sync_run_id": run.id,
        "cursor_key": cursor_key,
        "trace_id": f"mes-sync-run:{run.id}",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_output_daily": 366},
            "sources": {"total_output_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert bundle["facts"]["total_output_daily"]["evidence_status"] == "needs_evidence"


def test_daily_fact_bundle_does_not_confirm_unclosed_1000_business_window(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    source = {
        "source_type": "mes_material_records",
        "source_ref": "MES_MaterialRecord",
        "business_window": "2026-07-07T10:00:00+08:00/2026-07-08T10:00:00+08:00",
        "unit": "吨",
        "row_count": 3,
        "trace_id": "projection-read:mes_material_records:2026-07-07:3",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_output_daily": 70},
            "sources": {"total_output_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    fact = bundle["facts"]["total_output_daily"]
    assert fact["source_detail"]["business_window"] == source["business_window"]
    assert fact["evidence_status"] == "needs_evidence"
    assert "business_window_not_closed" in fact["evidence_gaps"]
    assert _fact_closure_field(bundle, "total_output_daily")["status"] == "needs_evidence"


def test_daily_fact_bundle_keeps_raw_mes_material_as_evidence_only_after_window_closes(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    row = MesMaterialRecord(
        source_id="real-material-projection",
        source_path="sqlserver:MES_Material",
        workshop_name="热轧车间",
        weight_tons=70,
        production_date=datetime(2026, 7, 8, 9, 30),
        business_date=date(2026, 7, 7),
    )
    db_session.add(row)
    db_session.commit()
    source = {
        "source_type": "mes_material_records",
        "source_ref": "mes_material_records",
        "source_table": "MES_Material",
        "business_window": "2026-07-07T10:00:00+08:00/2026-07-08T10:00:00+08:00",
        "unit": "吨",
        "row_count": 1,
        "latest_row_id": row.id,
        "trace_id": f"projection-read:mes_material_records:{row.id}:1",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"hot_roll_daily": 70},
            "sources": {"hot_roll_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 10, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    fact = bundle["facts"]["hot_roll_daily"]
    assert fact["unit"] == "吨"
    assert fact["evidence_status"] == "needs_evidence"
    assert "raw_mes_process_is_evidence_only" in fact["evidence_gaps"]


def test_daily_fact_bundle_keeps_generated_raw_material_trace_as_evidence_only(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle, template_daily_fact_sources

    row = MesMaterialRecord(
        source_id="generated-material-projection",
        source_path="sqlserver:MES_Material",
        workshop_name="热轧车间",
        weight_tons=70,
        production_date=datetime(2026, 7, 7, 10, 30),
        business_date=date(2026, 7, 7),
        status_name="已使用",
    )
    db_session.add(row)
    db_session.commit()
    facts = template_daily_fact_sources.TemplateDailyFacts(target_date=date(2026, 7, 7))
    template_daily_fact_sources.collect_mes_material_workshop_facts(db_session, facts)
    generated_source = facts.sources["hot_roll_daily"]
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"hot_roll_daily": facts.values["hot_roll_daily"]},
            "sources": {"hot_roll_daily": generated_source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 10, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert generated_source["latest_row_id"] == row.id
    assert generated_source["trace_id"] == f"projection-read:mes_material_records:{row.id}:1"
    fact = bundle["facts"]["hot_roll_daily"]
    assert fact["evidence_status"] == "needs_evidence"
    assert "raw_mes_process_is_evidence_only" in fact["evidence_gaps"]


def test_daily_fact_bundle_confirms_packaging_projection_only_for_exact_field_query(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    packaging = MesWorkshopProcessRecord(
        source_id="contract-packaging",
        source_path="sqlserver:workshop_process_records",
        workshop_name="精整",
        process_name="包装",
        output_weight_tons=366,
        business_date=date(2026, 7, 7),
    )
    unrelated = MesWorkshopProcessRecord(
        source_id="contract-cold-roll",
        source_path="sqlserver:workshop_process_records",
        workshop_name="冷轧1650",
        process_name="冷轧",
        output_weight_tons=999,
        business_date=date(2026, 7, 7),
    )
    db_session.add_all([packaging, unrelated])
    db_session.commit()
    source = {
        "source_type": "mes_packaging_output",
        "source_ref": "mes_workshop_process_records",
        "source_table": "MES_ProductProcessRecord",
        "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
        "unit": "吨",
        "row_count": 1,
        "latest_row_id": packaging.id,
        "trace_id": f"projection-read:mes_workshop_process_records:{packaging.id}:1",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_output_daily": 366},
            "sources": {"total_output_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert bundle["facts"]["total_output_daily"]["evidence_status"] == "confirmed"


@pytest.mark.parametrize(
    ("claimed_value", "expected_status"),
    [
        (119.99, "needs_evidence"),
        (100.0004, "confirmed"),
    ],
)
def test_daily_fact_bundle_uses_projection_precision_not_alignment_tolerance(
    monkeypatch,
    db_session: Session,
    claimed_value: float,
    expected_status: str,
) -> None:
    from app.services.report import daily_fact_bundle

    row = MesWorkshopProcessRecord(
        source_id=f"precision-{claimed_value}",
        source_path="sqlserver:workshop_process_records",
        workshop_name="精整",
        process_name="包装",
        output_weight_tons=100,
        business_date=date(2026, 7, 7),
    )
    db_session.add(row)
    db_session.commit()
    source = {
        "source_type": "mes_packaging_output",
        "source_ref": "mes_workshop_process_records",
        "source_table": "MES_ProductProcessRecord",
        "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
        "unit": "吨",
        "row_count": 1,
        "latest_row_id": row.id,
        "trace_id": f"projection-read:mes_workshop_process_records:{row.id}:1",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_output_daily": claimed_value},
            "sources": {"total_output_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert bundle["facts"]["total_output_daily"]["evidence_status"] == expected_status


@pytest.mark.parametrize(
    ("unit", "metric_contract_version"),
    [
        ("kg", "2026-07-11"),
        ("吨", "fake-version"),
    ],
)
def test_daily_fact_bundle_rejects_projection_with_wrong_unit_or_contract_version(
    monkeypatch,
    db_session: Session,
    unit: str,
    metric_contract_version: str,
) -> None:
    from app.services.report import daily_fact_bundle

    row = MesWorkshopProcessRecord(
        source_id=f"contract-metadata-{unit}-{metric_contract_version}",
        source_path="sqlserver:workshop_process_records",
        workshop_name="精整",
        process_name="包装",
        output_weight_tons=100,
        business_date=date(2026, 7, 7),
    )
    db_session.add(row)
    db_session.commit()
    source = {
        "source_type": "mes_packaging_output",
        "source_ref": "mes_workshop_process_records",
        "source_table": "MES_ProductProcessRecord",
        "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
        "unit": unit,
        "row_count": 1,
        "latest_row_id": row.id,
        "trace_id": f"projection-read:mes_workshop_process_records:{row.id}:1",
        "metric_contract_version": metric_contract_version,
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_output_daily": 100},
            "sources": {"total_output_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert bundle["facts"]["total_output_daily"]["evidence_status"] == "needs_evidence"


def test_daily_fact_bundle_confirms_wms_detail_projection_for_exact_inbound_query(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    row = MesStockRecord(
        source_id="wms-detail-contract",
        source_path="sqlserver:stock_records",
        net_weight_tons=126.4,
        business_date=date(2026, 7, 7),
    )
    db_session.add(row)
    db_session.commit()
    source = {
        "source_type": "mes_stock_records",
        "source_ref": "mes_stock_records",
        "source_table": "WMS_InStockDetail",
        "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
        "unit": "吨",
        "row_count": 1,
        "latest_row_id": row.id,
        "trace_id": f"projection-read:mes_stock_records:{row.id}:1",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"finished_inbound_daily": 126.4},
            "sources": {"finished_inbound_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert bundle["facts"]["finished_inbound_daily"]["evidence_status"] == "confirmed"


def test_daily_fact_bundle_accepts_display_rounding_for_verified_wms_inbound(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    row = MesStockRecord(
        source_id="wms-header-rounded",
        source_path="sqlserver:stock_header_records",
        net_weight_tons=320.768,
        business_date=date(2026, 7, 15),
    )
    db_session.add(row)
    db_session.commit()
    source = {
        "source_type": "mes_stock_header_records",
        "source_ref": "mes_stock_records",
        "source_table": "WMS_InStock",
        "business_window": "2026-07-15T07:50:00+08:00/2026-07-16T07:50:00+08:00",
        "unit": "吨",
        "row_count": 1,
        "latest_row_id": row.id,
        "trace_id": f"projection-read:mes_stock_records:{row.id}:1",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"finished_inbound_daily": 320.77},
            "sources": {"finished_inbound_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 15),
        now=datetime(2026, 7, 16, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    fact = bundle["facts"]["finished_inbound_daily"]
    assert fact["evidence_status"] == "confirmed"
    assert fact["evidence_gaps"] == []


def test_daily_fact_bundle_rejects_invented_local_wms_detail_path(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    row = MesStockRecord(
        source_id="invented-wms-detail",
        source_path="local:invented",
        net_weight_tons=126.4,
        business_date=date(2026, 7, 7),
    )
    db_session.add(row)
    db_session.commit()
    source = {
        "source_type": "mes_stock_records",
        "source_ref": "mes_stock_records",
        "source_table": "WMS_InStockDetail",
        "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
        "unit": "吨",
        "row_count": 1,
        "latest_row_id": row.id,
        "trace_id": f"projection-read:mes_stock_records:{row.id}:1",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"finished_inbound_daily": 126.4},
            "sources": {"finished_inbound_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert bundle["facts"]["finished_inbound_daily"]["evidence_status"] == "needs_evidence"


@pytest.mark.parametrize(
    ("workshop_name", "expected_status"),
    [
        ("熔铸车间", "needs_evidence"),
        ("冷轧1650", "needs_evidence"),
    ],
)
def test_daily_fact_bundle_validates_foundry_daily_and_month_projection_contracts(
    monkeypatch,
    db_session: Session,
    workshop_name: str,
    expected_status: str,
) -> None:
    from app.services.report import daily_fact_bundle

    row = MesWorkshopProcessRecord(
        source_id=f"foundry-contract-{workshop_name}",
        source_path="sqlserver:workshop_process_records",
        workshop_name=workshop_name,
        process_name="铸锭",
        output_weight_tons=88,
        business_date=date(2026, 7, 7),
    )
    db_session.add(row)
    db_session.commit()
    daily_source = {
        "source_type": "mes_workshop_process_records",
        "source_ref": "mes_workshop_process_records",
        "source_table": "MES_ProductProcessRecord",
        "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
        "unit": "吨",
        "row_count": 1,
        "latest_row_id": row.id,
        "trace_id": f"projection-read:mes_workshop_process_records:{row.id}:1",
        "metric_contract_version": "2026-07-11",
    }
    month_source = {
        **daily_source,
        "business_window": "2026-07-01T07:50:00+08:00/2026-07-08T07:50:00+08:00",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"foundry_daily": 88, "foundry_month": 88},
            "sources": {
                "foundry_daily": daily_source,
                "foundry_month": month_source,
            },
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert bundle["facts"]["foundry_daily"]["evidence_status"] == expected_status
    assert bundle["facts"]["foundry_month"]["evidence_status"] == expected_status


def test_cast_workshops_are_not_aggregated_or_verified_as_foundry(
    db_session: Session,
) -> None:
    from app.services.report import template_daily_fact_sources
    from app.services.report.daily_fact_evidence_contracts import DailyFactEvidenceVerifier
    from app.services.report.mes_workshop_mapping import resolve_mes_process_workshop_bucket

    process_rows = [
        MesWorkshopProcessRecord(
            source_id=source_id,
            source_path="sqlserver:workshop_process_records",
            workshop_name=workshop_name,
            process_name=process_name,
            output_weight_tons=output_weight,
            business_date=date(2026, 7, 7),
        )
        for source_id, workshop_name, process_name, output_weight in (
            ("same-day-foundry", "熔铸车间", "铸造", 88),
            ("same-day-cast-2", "铸二车间", "铸造", 100),
            ("same-day-cast-3", "铸三车间", "熔炼", 120),
        )
    ]
    material_rows = [
        MesMaterialRecord(
            source_id=source_id,
            source_path="sqlserver:MES_Material",
            workshop_name=workshop_name,
            weight_tons=weight_tons,
            production_date=datetime(2026, 7, 7, 10, 30),
            business_date=date(2026, 7, 7),
            status_name="已使用",
        )
        for source_id, workshop_name, weight_tons in (
            ("same-day-cast-2-material", "铸二车间", 100),
            ("same-day-cast-3-material", "铸三车间", 120),
        )
    ]
    db_session.add_all([*process_rows, *material_rows])
    db_session.commit()

    field_names = ("foundry_daily", "cast_2_daily", "cast_3_daily")
    facts = template_daily_fact_sources.TemplateDailyFacts(target_date=date(2026, 7, 7))
    template_daily_fact_sources.collect_mes_material_workshop_facts(db_session, facts)
    template_daily_fact_sources.collect_mes_workshop_facts(db_session, facts)
    verifier = DailyFactEvidenceVerifier(db_session, business_date=date(2026, 7, 7))

    assert {
        "aggregates": {field_name: facts.values[field_name] for field_name in field_names},
        "evidence_verified": {
            field_name: verifier.verify_projection(
                field_name=field_name,
                source_type=facts.sources[field_name]["source_type"],
                fact_value=facts.values[field_name],
                source_detail=facts.sources[field_name],
            )
            for field_name in field_names
        },
        "mapping": {
            "foundry": resolve_mes_process_workshop_bucket("熔铸车间", "铸造"),
            "cast_2": resolve_mes_process_workshop_bucket("铸二车间", "铸造"),
            "cast_3": resolve_mes_process_workshop_bucket("铸三车间", "熔炼"),
            "hot_roll": resolve_mes_process_workshop_bucket("热轧车间", "铸造"),
        },
    } == {
        "aggregates": {
            "foundry_daily": 88,
            "cast_2_daily": 100,
            "cast_3_daily": 120,
        },
        "evidence_verified": {
            "foundry_daily": True,
            "cast_2_daily": True,
            "cast_3_daily": True,
        },
        "mapping": {
            "foundry": "铸锭",
            "cast_2": "铸二",
            "cast_3": "铸三",
            "hot_roll": "热轧",
        },
    }


def test_daily_fact_bundle_confirms_coil_wip_for_next_business_date(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    snapshot_at = datetime(2026, 7, 8, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    row = MesCoilSnapshot(
        coil_id="wip-contract-coil",
        tracking_card_no="wip-contract-coil",
        business_date=date(2026, 7, 8),
        current_workshop="1650车间",
        current_process="冷轧",
        material_weight=568_000,
        last_synced_at=snapshot_at,
    )
    db_session.add(row)
    db_session.commit()
    source = {
        "source_type": "mes_coil_snapshot_business_date",
        "source_ref": "mes_coil_snapshots",
        "business_date": "2026-07-08",
        "business_window": "2026-07-08T08:00:00+08:00/2026-07-08T08:00:00+08:00",
        "unit": "吨",
        "row_count": 1,
        "latest_row_id": row.id,
        "trace_id": f"projection-read:mes_coil_snapshots:{row.id}:1",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"wip_total": 568},
            "sources": {"wip_total": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert bundle["facts"]["wip_total"]["evidence_status"] == "confirmed"


@pytest.mark.parametrize(
    "claim_kind",
    ["other_business_date", "other_workshop", "inflated_count", "wrong_value"],
)
def test_daily_fact_bundle_rejects_projection_evidence_outside_field_contract(
    monkeypatch,
    db_session: Session,
    claim_kind: str,
) -> None:
    from app.services.report import daily_fact_bundle

    target_row = MesMaterialRecord(
        source_id="contract-target-hot-roll",
        source_path="sqlserver:MES_Material",
        workshop_name="热轧车间",
        weight_tons=70,
        production_date=datetime(2026, 7, 7, 10, 30),
        business_date=date(2026, 7, 7),
        status_name="已使用",
    )
    other_date_row = MesMaterialRecord(
        source_id="contract-other-date",
        source_path="sqlserver:MES_Material",
        workshop_name="热轧车间",
        weight_tons=99,
        production_date=datetime(2026, 7, 6, 10, 30),
        business_date=date(2026, 7, 6),
        status_name="已使用",
    )
    other_workshop_row = MesMaterialRecord(
        source_id="contract-other-workshop",
        source_path="sqlserver:MES_Material",
        workshop_name="铸二车间",
        weight_tons=80,
        production_date=datetime(2026, 7, 7, 10, 30),
        business_date=date(2026, 7, 7),
        status_name="已使用",
    )
    db_session.add_all([target_row, other_date_row, other_workshop_row])
    db_session.commit()

    claimed_row = target_row
    claimed_count = 1
    claimed_value = 70
    if claim_kind == "other_business_date":
        claimed_row = other_date_row
        claimed_value = 99
    elif claim_kind == "other_workshop":
        claimed_row = other_workshop_row
        claimed_value = 80
    elif claim_kind == "inflated_count":
        claimed_count = 999
    elif claim_kind == "wrong_value":
        claimed_value = 700

    source = {
        "source_type": "mes_material_records",
        "source_ref": "mes_material_records",
        "source_table": "MES_Material",
        "business_window": "2026-07-07T10:00:00+08:00/2026-07-08T10:00:00+08:00",
        "unit": "吨",
        "row_count": claimed_count,
        "latest_row_id": claimed_row.id,
        "trace_id": f"projection-read:mes_material_records:{claimed_row.id}:{claimed_count}",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"hot_roll_daily": claimed_value},
            "sources": {"hot_roll_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 10, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert bundle["facts"]["hot_roll_daily"]["evidence_status"] == "needs_evidence"


@pytest.mark.parametrize(
    ("field_name", "source_ref", "cursor_key"),
    [
        ("mes_completely_unrelated_metric", "MES_ProductProcessRecord", "mes_workshop_process_records_between"),
        ("total_output_daily", "MES_CompletelyFake", "mes_workshop_process_records_between"),
        ("total_output_daily", "WMS_InStock", "mes_stock_records_between"),
    ],
)
def test_daily_fact_bundle_rejects_sync_run_outside_field_source_contract(
    monkeypatch,
    db_session: Session,
    field_name: str,
    source_ref: str,
    cursor_key: str,
) -> None:
    from app.services.report import daily_fact_bundle

    cursor = MesSyncCursor(
        cursor_key=cursor_key,
        last_synced_at=datetime(2026, 7, 8, 7, 55, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    run = MesSyncRunLog(
        cursor_key=cursor_key,
        started_at=datetime(2026, 7, 8, 7, 55, tzinfo=ZoneInfo("Asia/Shanghai")),
        finished_at=datetime(2026, 7, 8, 7, 56, tzinfo=ZoneInfo("Asia/Shanghai")),
        status="success",
        fetched_count=3,
    )
    db_session.add_all([cursor, run])
    db_session.commit()
    source = {
        "source_type": "mes_verified",
        "source_ref": source_ref,
        "business_window": "2026-07-07T07:50:00+08:00/2026-07-08T07:50:00+08:00",
        "unit": "吨",
        "sync_run_id": run.id,
        "cursor_key": cursor_key,
        "trace_id": f"mes-sync-run:{run.id}",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {field_name: 366},
            "sources": {field_name: source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 8, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert bundle["facts"][field_name]["evidence_status"] == "needs_evidence"


def test_daily_fact_bundle_caches_shared_projection_contract_queries(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    rows = [
        MesMaterialRecord(
            source_id=f"cached-{workshop}",
            source_path="sqlserver:MES_Material",
            workshop_name=workshop,
            weight_tons=value,
            production_date=datetime(2026, 7, 7, 10, 30),
            business_date=date(2026, 7, 7),
            status_name="已使用",
        )
        for workshop, value in (("热轧车间", 70), ("铸二车间", 80), ("铸三车间", 90))
    ]
    db_session.add_all(rows)
    db_session.commit()
    fields = ("hot_roll_daily", "cast_2_daily", "cast_3_daily")
    values = dict(zip(fields, (70, 80, 90), strict=True))
    sources = {
        field_name: {
            "source_type": "mes_material_records",
            "source_ref": "mes_material_records",
            "source_table": "MES_Material",
            "business_window": "2026-07-07T10:00:00+08:00/2026-07-08T10:00:00+08:00",
            "unit": "吨",
            "row_count": 1,
            "latest_row_id": row.id,
            "trace_id": f"projection-read:mes_material_records:{row.id}:1",
            "metric_contract_version": "2026-07-11",
        }
        for field_name, row in zip(fields, rows, strict=True)
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": values,
            "sources": sources,
            "missing_fields": [],
            "conflicts": [],
        },
    )
    statements: list[str] = []

    def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    sa.event.listen(db_session.get_bind(), "before_cursor_execute", capture_sql)
    try:
        bundle = daily_fact_bundle.build_daily_fact_bundle(
            db_session,
            business_date=date(2026, 7, 7),
            now=datetime(2026, 7, 8, 10, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
    finally:
        sa.event.remove(db_session.get_bind(), "before_cursor_execute", capture_sql)

    projection_selects = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith("SELECT") and "FROM mes_material_records" in statement
    ]
    assert all(bundle["facts"][field]["evidence_status"] == "needs_evidence" for field in fields)
    assert all(
        "raw_mes_process_is_evidence_only" in bundle["facts"][field]["evidence_gaps"]
        for field in fields
    )
    assert len(projection_selects) <= 1


def test_daily_fact_bundle_rejects_projection_anchor_missing_from_database(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    row = MesMaterialRecord(
        source_id="removed-material-projection",
        source_path="sqlserver:MES_Material",
        workshop_name="热轧车间",
        weight_tons=70,
        production_date=datetime(2026, 7, 7, 10, 30),
        business_date=date(2026, 7, 7),
    )
    db_session.add(row)
    db_session.commit()
    row_id = row.id
    db_session.execute(
        sa.delete(MesMaterialRecord)
        .where(MesMaterialRecord.id == row_id)
        .execution_options(synchronize_session=False)
    )
    source = {
        "source_type": "mes_material_records",
        "source_ref": "mes_material_records",
        "source_table": "MES_Material",
        "business_window": "2026-07-07T10:00:00+08:00/2026-07-08T10:00:00+08:00",
        "unit": "吨",
        "row_count": 1,
        "latest_row_id": row_id,
        "trace_id": f"projection-read:mes_material_records:{row_id}:1",
        "metric_contract_version": "2026-07-11",
    }
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"hot_roll_daily": 70},
            "sources": {"hot_roll_daily": source},
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
        now=datetime(2026, 7, 8, 10, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    assert bundle["facts"]["hot_roll_daily"]["evidence_status"] == "needs_evidence"


def test_daily_fact_bundle_does_not_forge_mes_trace_for_non_mes_source(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"total_electricity_kwh": 146500},
            "sources": {
                "total_electricity_kwh": {
                    "source_type": "owner_or_energy_summary",
                    "source_table": "mobile_shift_reports",
                },
            },
            "missing_fields": [],
            "conflicts": [],
        },
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 7),
    )

    fact = bundle["facts"]["total_electricity_kwh"]
    assert "trace_id" not in fact["source_detail"]
    assert "metric_contract_version" not in fact["source_detail"]
    assert "trace_id" not in fact["source_ref"]


def test_daily_fact_bundle_does_not_confirm_sources_without_real_field_traces(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {
                "total_output_daily": 384,
                "finished_inbound_daily": 126.4,
                "wip_total": 1136,
                "total_electricity_kwh": 133201,
                "daily_yield_rate": 0.88,
            },
            "sources": {
                "total_output_daily": "mes_packaging_output",
                "finished_inbound_daily": "finished_inbound_output",
                "wip_total": "mes_wip_distribution",
                "total_electricity_kwh": "owner_or_energy_summary",
                "daily_yield_rate": "computed_same_basis",
            },
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    closure = bundle["fact_closure"]
    assert closure["status"] == "blocked"
    assert closure["counts"]["confirmed"] == 0
    assert closure["counts"]["needs_evidence"] == 5
    assert _fact_closure_field(bundle, "total_output_daily")["status"] == "needs_evidence"
    assert _fact_closure_field(bundle, "finished_inbound_daily")["status"] == "needs_evidence"
    assert _fact_closure_field(bundle, "wip_total")["status"] == "needs_evidence"
    assert _fact_closure_field(bundle, "total_electricity_kwh")["status"] == "needs_evidence"
    assert _fact_closure_field(bundle, "daily_yield_rate")["status"] == "needs_evidence"
    assert {
        item["field"]
        for item in closure["critical_fields"]
    } == EXPECTED_CRITICAL_DAILY_FACT_FIELDS


def test_daily_fact_bundle_fact_closure_blocks_missing_critical_field(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {
                "total_output_daily": 384,
                "finished_inbound_daily": 126.4,
                "wip_total": 1136,
                "daily_yield_rate": 0.88,
            },
            "sources": {
                "total_output_daily": "mes_packaging_output",
                "finished_inbound_daily": "finished_inbound_output",
                "wip_total": "mes_wip_distribution",
                "daily_yield_rate": "computed",
            },
            "missing_fields": ["total_electricity_kwh"],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["fact_closure"]["status"] == "blocked"
    assert _fact_closure_field(bundle, "total_electricity_kwh")["status"] == "missing"


def test_root_owner_correction_overrides_template_fact(monkeypatch, db_session: Session) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        assert target_date == date(2026, 6, 19)
        return {
            "values": {"total_output_daily": 355},
            "sources": {"total_output_daily": "mes_packaging_output"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        User(
            id=983,
            username="root_owner",
            password_hash="hashed",
            name="root_owner",
            role="admin",
        )
    )
    db_session.flush()
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
    assert fact["source_type"] == "root_owner_correction"
    assert fact["priority"] == 90
    assert fact["confidence"] == 0.95
    assert fact["freshness"] == "confirmed"
    assert fact["adoption_reason"] == "root_owner 钉钉确认"
    assert fact["source_detail"] == {
        "source": "root_owner_correction",
        "correction_id": 1,
        "actor_user_id": 983,
        "trace_id": "trace-root-owner-correction",
        "source_text": "6月19日车间总产量改成366吨，直接按这个发。",
        "business_date": "2026-06-19",
    }
    assert fact["source_ref"] == {
        "source": "root_owner_correction",
        "correction_id": 1,
        "actor_user_id": 983,
        "trace_id": "trace-root-owner-correction",
        "source_text": "6月19日车间总产量改成366吨，直接按这个发。",
        "business_date": "2026-06-19",
    }
    assert bundle["sources"]["total_output_daily"]["source"] == "root_owner_correction"
    assert bundle["correction_refs"] == [
        {"id": 1, "field_name": "total_output_daily", "trace_id": "trace-root-owner-correction"}
    ]
    assert bundle["conflicts"][0] == {
        "field": "total_output_daily",
        "type": "root_owner_correction",
        "adopted_source": "root_owner_correction",
        "previous_source": "mes_packaging_output",
        "previous_value": 355,
        "adopted_value": 366,
        "reason": "root_owner 钉钉确认",
    }
    assert bundle["confidence"] == 0.95
    assert bundle["status"] == "ready"
    closure_field = _fact_closure_field(bundle, "total_output_daily")
    assert closure_field["status"] == "needs_evidence"
    assert closure_field["source"] == "root_owner_correction"
    assert closure_field["trace_id"] == "trace-root-owner-correction"


def test_verified_owner_daily_correction_closes_its_assigned_fact(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        assert target_date == date(2026, 6, 19)
        return {
            "values": {"daily_yield_rate": 84.00},
            "sources": {"daily_yield_rate": "owner_daily"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        User(
            id=984,
            username="quality-owner",
            password_hash="hashed",
            name="质检责任人",
            role="quality_owner",
        )
    )
    db_session.flush()
    correction = DailyFactCorrection(
        business_date=date(2026, 6, 19),
        field_name="daily_yield_rate",
        value_payload={
            "value": 84.86,
            "source_type": "verified_owner_daily",
            "entry_id": 9419,
            "event_id": 671,
            "entry_field": "plant_wide_yield_rate",
            "owner_role": "quality_owner",
        },
        unit="%",
        source_text="owner_daily_entry:9419",
        before_value=None,
        reason="assigned_daily_fact_gap_owner_submission",
        actor_user_id=984,
        trace_id="daily-fact-closure:2026-06-19",
    )
    db_session.add(correction)
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 6, 19),
    )

    fact = bundle["facts"]["daily_yield_rate"]
    assert fact["value"] == 84.86
    assert fact["source_type"] == "verified_owner_daily"
    assert fact["priority"] == 70
    assert fact["confidence"] == 0.75
    assert fact["evidence_status"] == "confirmed"
    assert fact["evidence_gaps"] == []
    assert fact["source_detail"]["source"] == "verified_owner_daily"
    assert fact["source_detail"]["source_key"] == "scan_supplement"
    assert fact["source_detail"]["correction_id"] == correction.id
    assert fact["source_detail"]["entry_id"] == 9419
    assert fact["source_detail"]["event_id"] == 671
    assert fact["source_detail"]["actor_user_id"] == 984
    assert fact["source_detail"]["entry_field"] == "plant_wide_yield_rate"
    assert fact["source_detail"]["owner_role"] == "quality_owner"
    assert fact["source_detail"]["field"] == "daily_yield_rate"
    assert fact["source_detail"]["trace_id"] == "daily-fact-closure:2026-06-19"
    assert fact["source_detail"]["business_date"] == "2026-06-19"
    assert fact["source_detail"]["business_window"]
    assert fact["source_detail"]["metric_contract_version"] == "2026-07-11"
    closure_field = _fact_closure_field(bundle, "daily_yield_rate")
    assert closure_field["status"] == "confirmed"
    assert closure_field["source"] == "verified_owner_daily"
    conflict = next(item for item in bundle["conflicts"] if item["type"] == "verified_owner_daily")
    assert conflict["previous_value"] == 84.00
    assert conflict["adopted_value"] == 84.86
    assert daily_fact_bundle._conflict_blocks_ready(conflict) is False


def test_dingtalk_supplement_needs_its_own_trace_for_fact_closure(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"total_electricity_kwh": 133000},
            "sources": {"total_electricity_kwh": "owner_or_energy_summary"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        User(
            id=12,
            username="energy_owner",
            password_hash="hashed",
            name="energy_owner",
            role="admin",
        )
    )
    db_session.flush()
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_file",
            source_user_id=12,
            file_uri="dingtalk://energy/2026-06-19.xlsx",
            recognized_text="6月19日高压电 133201 度",
            confirmation_status="confirmed",
            payload={
                "business_date": "2026-06-19",
                "include_in_daily_sample": True,
                "evidence_kind": "fact",
                "parse_status": "text_captured",
                "fact_updates": {
                    "total_electricity_kwh": {
                        "value": 133201,
                        "unit": "度",
                        "reason": "能源负责人钉钉确认",
                    }
                },
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 6, 19),
        trace_id="trace-dingtalk-energy",
    )

    closure_field = _fact_closure_field(bundle, "total_electricity_kwh")
    assert closure_field["status"] == "needs_evidence"
    assert bundle["facts"]["total_electricity_kwh"]["source"] == "owner_or_energy_summary"
    assert closure_field["source"] is None
    assert closure_field["trace_id"] is None
    assert bundle["dingtalk_refs"] == []
    assert any(
        item["type"] == "dingtalk_candidate_not_applied"
        and item["field"] == "total_electricity_kwh"
        and item["reason"] == "missing_trace_id"
        for item in bundle["conflicts"]
    )


def test_dingtalk_structured_none_value_does_not_clear_missing_field(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {},
            "sources": {},
            "missing_fields": ["total_output_daily"],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            source_user_id=None,
            recognized_text="今日总产量待确认",
            confirmation_status="confirmed",
            payload={
                "business_date": "2026-06-19",
                "include_in_daily_sample": True,
                "evidence_kind": "fact",
                "fact_updates": {
                    "total_output_daily": {
                        "value": None,
                        "unit": "吨",
                    }
                },
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert "total_output_daily" not in bundle["facts"]
    assert bundle["missing_fields"] == ["total_output_daily"]
    assert bundle["missing"] == ["total_output_daily"]
    assert bundle["status"] == "blocked"
    assert bundle["dingtalk_refs"] == []
    closure_field = _fact_closure_field(bundle, "total_output_daily")
    assert closure_field["status"] == "missing"


def test_dingtalk_structured_list_field_key_target_date_applies_with_trace(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {},
            "sources": {},
            "missing_fields": ["total_output_daily"],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            source_user_id=None,
            recognized_text="今日总产量371吨",
            confirmation_status="confirmed",
            payload={
                "target_date": "2026-06-19",
                "include_in_daily_sample": True,
                "evidence_kind": "fact",
                "trace_id": "trace-structured",
                "parse_status": "text_captured",
                "fact_updates": [
                    {
                        "field": "total_output_daily",
                        "value": 371,
                        "unit": "吨",
                    }
                ],
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["facts"]["total_output_daily"]["value"] == 371
    assert bundle["facts"]["total_output_daily"]["source"] == "dingtalk_supplement"
    assert bundle["facts"]["total_output_daily"]["source_detail"]["trace_id"] == "trace-structured"
    assert bundle["facts"]["total_output_daily"]["source_ref"]["trace_id"] == "trace-structured"
    assert bundle["missing_fields"] == []
    assert bundle["status"] == "ready"
    closure_field = _fact_closure_field(bundle, "total_output_daily")
    assert closure_field["status"] == "confirmed"
    assert closure_field["source"] == "dingtalk_supplement"
    assert closure_field["trace_id"] == "trace-structured"


def test_dingtalk_daily_input_updates_canonical_and_template_alias(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    rendered_values: dict[str, Any] = {}

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"cold_roll_input_daily": 463},
            "sources": {"cold_roll_input_daily": "contract_projection"},
            "missing_fields": [],
            "conflicts": [],
        }

    def fake_render(payload):
        rendered_values.update(payload["values"])
        return "rendered"

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "render_template_daily_report",
        fake_render,
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            recognized_text="投料量：2050投料463吨 1850投料0吨 外加工62吨 中厚板0吨",
            confirmation_status="confirmed",
            payload={
                "business_date": "2026-07-11",
                "trace_id": "trace-plan-contract",
                "parse_status": "text_captured",
                "fact_updates": {
                    "daily_input_weight": {
                        "value": 525,
                        "unit": "吨",
                        "reason": "钉钉计划科合同消息确定性分项求和",
                        "source_ref": {
                            "parser": "plan_contract_message_v1",
                            "business_date": "2026-07-11",
                            "content_sha256": "a" * 64,
                        },
                    }
                },
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 7, 11),
        allow_output_skill_reference_adoption=False,
    )

    for field_name in ("daily_input_weight", "cold_roll_input_daily"):
        fact = bundle["facts"][field_name]
        assert fact["value"] == 525
        assert fact["source"] == "dingtalk_supplement"
        assert fact["source_ref"]["field_source_ref"]["content_sha256"] == "a" * 64
    assert rendered_values["daily_input_weight"] == 525
    assert rendered_values["cold_roll_input_daily"] == 525
    assert bundle["dingtalk_refs"] == [
        {
            "id": 1,
            "field_names": ["daily_input_weight", "cold_roll_input_daily"],
        }
    ]


def test_human_confirmed_dingtalk_confirm_result_stays_candidate_only(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {},
            "sources": {},
            "missing_fields": ["total_electricity_kwh"],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_file",
            source_user_id=None,
            file_uri="dingtalk://energy/2026-06-19.xlsx",
            recognized_text="6月19日全厂高压总用电量18420度",
            confirmation_status="human_confirmed",
            payload={
                "source": "dingtalk",
                "confirm_result": {
                    "business_date": "2026-06-19",
                    "trace_id": "trace-human-confirmed-energy",
                    "parse_status": "text_captured",
                    "fact_updates": {
                        "total_electricity_kwh": {
                            "value": 18420,
                            "unit": "度",
                            "reason": "人工确认钉钉能源表",
                        }
                    },
                },
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert "total_electricity_kwh" not in bundle["facts"]
    assert bundle["missing_fields"] == ["total_electricity_kwh"]
    assert bundle["dingtalk_refs"] == []
    assert bundle["conflicts"] == [
        {
            "field": "total_electricity_kwh",
            "type": "dingtalk_candidate_not_applied",
            "candidate_value": 18420,
            "reason": "confirmation_status_not_adoptable",
            "trace_id": "trace-human-confirmed-energy",
            "evidence_id": 1,
        }
    ]
    closure_field = _fact_closure_field(bundle, "total_electricity_kwh")
    assert closure_field["status"] == "missing"


def test_human_confirmed_dingtalk_daily_report_text_stays_candidate_only(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {},
            "sources": {},
            "missing_fields": [
                "total_output_daily",
                "finished_inbound_daily",
                "wip_total",
                "total_electricity_kwh",
                "daily_yield_rate",
            ],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    report_text = (
        "6月19日生产日报\n"
        "车间总产量日合计371吨。\n"
        "当天在制料1136吨。\n"
        "全厂高压总用电量18420度。\n"
        "入库成品日合计365.2吨。\n"
        "日成品率83.4%。"
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            source_user_id=None,
            recognized_text=report_text,
            confirmation_status="human_confirmed",
            payload={
                "source": "dingtalk",
                "trace_id": "trace-human-confirmed-report",
                "parse_status": "text_captured",
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["facts"] == {}
    assert bundle["dingtalk_refs"] == []
    assert bundle["missing_fields"] == [
        "total_output_daily",
        "finished_inbound_daily",
        "wip_total",
        "total_electricity_kwh",
        "daily_yield_rate",
    ]
    assert [item["reason"] for item in bundle["conflicts"]] == [
        "confirmation_status_not_adoptable",
        "confirmation_status_not_adoptable",
        "confirmation_status_not_adoptable",
        "confirmation_status_not_adoptable",
        "confirmation_status_not_adoptable",
    ]


def test_attachment_text_payload_applies_parsed_fields(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {},
            "sources": {},
            "missing_fields": ["total_output_daily", "total_electricity_kwh"],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="attachment",
            source_user_id=None,
            file_uri="dingtalk://media/daily-report-20260619",
            recognized_text="日报文件已上传",
            confirmation_status="confirmed",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-attachment-report",
                "parse_status": "text_captured",
                "file_name": "6月19日生产日报.xlsx",
                "attachment_text": (
                    "6月19日生产日报\n"
                    "车间总产量日合计371吨。\n"
                    "当天在制料1136吨。\n"
                    "全厂高压总用电量18420度。\n"
                    "入库成品日合计365.2吨。\n"
                    "日成品率83.4%。"
                ),
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["facts"]["total_output_daily"]["value"] == 371
    assert bundle["facts"]["total_electricity_kwh"]["value"] == 18420
    assert bundle["facts"]["total_output_daily"]["source_ref"]["source_key"] == "dingtalk_group_file"
    assert bundle["facts"]["total_output_daily"]["source_ref"]["file_uri"] == "dingtalk://media/daily-report-20260619"
    assert bundle["facts"]["total_output_daily"]["source_ref"]["trace_id"] == "trace-attachment-report"
    assert bundle["missing_fields"] == []


def test_dingtalk_daily_report_text_without_trace_stays_candidate_only(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"total_output_daily": 355},
            "sources": {"total_output_daily": "mes_packaging_output"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            source_user_id=None,
            recognized_text="6月19日车间总产量日合计371吨，当天在制料1136吨，全厂高压总用电量18420度。",
            confirmation_status="confirmed",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "parse_status": "text_captured",
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["facts"]["total_output_daily"]["value"] == 355
    assert bundle["dingtalk_refs"] == []
    assert any(
        item["type"] == "dingtalk_candidate_not_applied"
        and item["field"] == "total_output_daily"
        and item["reason"] == "missing_trace_id"
        for item in bundle["conflicts"]
    )


def test_dingtalk_text_without_text_captured_status_stays_candidate_only(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"total_output_daily": 355},
            "sources": {"total_output_daily": "mes_packaging_output"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            source_user_id=None,
            recognized_text="6月19日车间总产量日合计371吨，当天在制料1136吨。",
            confirmation_status="confirmed",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-text-unavailable",
                "parse_status": "text_unavailable",
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["facts"]["total_output_daily"]["value"] == 355
    assert bundle["dingtalk_refs"] == []
    assert any(
        item["type"] == "dingtalk_candidate_not_applied"
        and item["field"] == "total_output_daily"
        and item["reason"] == "parse_status_not_text_captured"
        for item in bundle["conflicts"]
    )


def test_machine_only_dingtalk_daily_report_text_is_not_applied(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {},
            "sources": {},
            "missing_fields": ["total_output_daily"],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            source_user_id=None,
            recognized_text="6月19日车间总产量日合计371吨，当天在制料1136吨，全厂高压总用电量18420度。",
            confirmation_status="machine_only",
            payload={"source": "dingtalk"},
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert "total_output_daily" not in bundle["facts"]
    assert bundle["missing_fields"] == ["total_output_daily"]
    assert bundle["dingtalk_refs"] == []


def test_specialist_sampled_dingtalk_daily_report_text_is_applied(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {},
            "sources": {},
            "missing_fields": ["total_output_daily"],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            source_user_id=None,
            recognized_text="6月19日车间总产量日合计371吨，当天在制料1136吨，全厂高压总用电量18420度。",
            confirmation_status="specialist_sampled",
            payload={
                "source": "dingtalk",
                "channel": "dingtalk_stream",
                "business_date": "2026-06-19",
                "trace_id": "stream-msg-001",
                "parse_status": "text_captured",
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["facts"]["total_output_daily"]["value"] == 371
    assert bundle["facts"]["total_output_daily"]["source"] == "dingtalk_supplement"
    assert bundle["facts"]["total_output_daily"]["source_ref"]["source_key"] == "dingtalk_group_content"
    assert bundle["facts"]["total_output_daily"]["source_ref"]["trace_id"] == "stream-msg-001"
    assert bundle["missing_fields"] == []
    assert bundle["dingtalk_refs"] == [{"id": 1, "field_names": ["total_output_daily", "wip_total", "total_electricity_kwh"]}]


def test_dingtalk_structured_date_mismatch_is_excluded_but_remains_auditable(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"total_output_daily": 355},
            "sources": {"total_output_daily": "mes_packaging_output"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            source_user_id=None,
            recognized_text="今日总产量371吨",
            confirmation_status="confirmed",
            payload={
                "business_date": "2026-06-18",
                "include_in_daily_sample": True,
                "evidence_kind": "fact",
                "trace_id": "trace-structured-date-mismatch",
                "parse_status": "text_captured",
                "fact_updates": {
                    "total_output_daily": {
                        "value": 371,
                        "unit": "吨",
                    }
                },
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["facts"]["total_output_daily"]["value"] == 355
    assert bundle["facts"]["total_output_daily"]["source"] == "mes_packaging_output"
    assert bundle["dingtalk_refs"] == []
    assert bundle["conflicts"] == []

    audit_items = daily_fact_bundle.query_dingtalk_evidence(
        db_session,
        business_date=date(2026, 6, 19),
        include_outside_business_context=True,
    )
    assert [item.trace_id for item in audit_items] == ["trace-structured-date-mismatch"]


def test_unstructured_dingtalk_evidence_with_matching_business_date_applies_to_fact_closure(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {
                "finished_inbound_daily": 365.2,
                "wip_total": 1136,
                "total_electricity_kwh": 18420,
                "daily_yield_rate": 98.4,
            },
            "sources": {
                "finished_inbound_daily": "finished_inbound_output",
                "wip_total": "mes_wip_distribution",
                "total_electricity_kwh": "owner_or_energy_summary",
                "daily_yield_rate": "computed",
            },
            "missing_fields": ["total_output_daily"],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            source_user_id=None,
            recognized_text="今日总产量371吨",
            confirmation_status="confirmed",
            payload={
                "business_date": "2026-06-19",
                "include_in_daily_sample": True,
                "evidence_kind": "fact",
                "trace_id": "trace-unstructured-output",
                "parse_status": "text_captured",
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    fact = bundle["facts"]["total_output_daily"]
    assert fact["value"] == 371
    assert fact["unit"] == "吨"
    assert fact["source"] == "dingtalk_supplement"
    assert fact["freshness"] == "supplemented"
    assert fact["evidence_status"] == "confirmed"
    assert fact["evidence_gaps"] == []
    assert bundle["missing_fields"] == []
    assert bundle["dingtalk_refs"] == [{"id": 1, "field_names": ["total_output_daily"]}]
    closure_field = _fact_closure_field(bundle, "total_output_daily")
    assert closure_field["status"] == "confirmed"
    assert closure_field["source"] == "dingtalk_supplement"
    assert closure_field["trace_id"] == "trace-unstructured-output"
    assert closure_field["business_window"] == (
        "2026-06-19T07:50:00+08:00/2026-06-20T07:50:00+08:00"
    )


def test_unstructured_dingtalk_today_without_payload_date_applies_to_current_bundle_day(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {
                "finished_inbound_daily": 365.2,
                "wip_total": 1136,
                "total_electricity_kwh": 18420,
                "daily_yield_rate": 98.4,
            },
            "sources": {
                "finished_inbound_daily": "finished_inbound_output",
                "wip_total": "mes_wip_distribution",
                "total_electricity_kwh": "owner_or_energy_summary",
                "daily_yield_rate": "computed",
            },
            "missing_fields": ["total_output_daily"],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            source_user_id=None,
            recognized_text="今日总产量371吨",
            confirmation_status="confirmed",
            created_at=datetime(2026, 6, 19, 9, 0),
            payload={
                "include_in_daily_sample": True,
                "evidence_kind": "fact",
                "trace_id": "trace-today-output",
                "workshop_name": "精整",
                "parse_status": "text_captured",
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    fact = bundle["facts"]["total_output_daily"]
    assert fact["value"] == 371
    assert fact["source"] == "dingtalk_supplement"
    assert fact["source_detail"]["business_date"] == "2026-06-19"
    assert bundle["missing_fields"] == []
    assert bundle["dingtalk_refs"] == [{"id": 1, "field_names": ["total_output_daily"]}]
    assert _fact_closure_field(bundle, "total_output_daily")["status"] == "confirmed"


def test_dingtalk_field_business_window_uses_billet_time_for_hot_roll() -> None:
    from app.services.report import daily_fact_bundle

    assert daily_fact_bundle._business_window_for_field("hot_roll_daily", date(2026, 6, 19)) == (
        "2026-06-19T10:00:00+08:00/2026-06-20T10:00:00+08:00"
    )


def test_dingtalk_fact_with_wrong_unit_remains_needs_evidence(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {},
            "sources": {},
            "missing_fields": ["total_output_daily"],
            "conflicts": [],
        },
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            recognized_text="6月19日车间总产量日合计371吨。",
            confirmation_status="confirmed",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-wrong-unit",
                "parse_status": "text_captured",
                "fact_updates": {
                    "total_output_daily": {
                        "value": 371,
                        "unit": "kg",
                    }
                },
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    fact = bundle["facts"]["total_output_daily"]
    assert fact["evidence_status"] == "needs_evidence"
    assert "unit_field_contract_mismatch" in fact["evidence_gaps"]
    assert _fact_closure_field(bundle, "total_output_daily")["status"] == "needs_evidence"


def test_dingtalk_fact_before_business_window_closes_remains_needs_evidence(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {},
            "sources": {},
            "missing_fields": ["total_output_daily"],
            "conflicts": [],
        },
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            recognized_text="6月19日车间总产量日合计371吨。",
            confirmation_status="confirmed",
            payload={
                "source": "dingtalk",
                "business_date": "2026-06-19",
                "trace_id": "trace-window-open",
                "parse_status": "text_captured",
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 6, 19),
        now=datetime(2026, 6, 20, 7, 49, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    fact = bundle["facts"]["total_output_daily"]
    assert fact["evidence_status"] == "needs_evidence"
    assert "business_window_not_closed" in fact["evidence_gaps"]
    assert _fact_closure_field(bundle, "total_output_daily")["status"] == "needs_evidence"


def test_unstructured_dingtalk_month_day_without_payload_date_applies_to_matching_bundle_day(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {
                "total_output_daily": 371,
                "finished_inbound_daily": 365.2,
                "wip_total": 1136,
                "daily_yield_rate": 98.4,
            },
            "sources": {
                "total_output_daily": "mes_packaging_output",
                "finished_inbound_daily": "finished_inbound_output",
                "wip_total": "mes_wip_distribution",
                "daily_yield_rate": "computed",
            },
            "missing_fields": ["total_electricity_kwh"],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            source_user_id=None,
            recognized_text="6月19日用电18420度",
            confirmation_status="confirmed",
            created_at=datetime(2026, 6, 18, 16, 0),
            payload={
                "include_in_daily_sample": True,
                "evidence_kind": "fact",
                "trace_id": "trace-month-day-energy",
                "parse_status": "text_captured",
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    fact = bundle["facts"]["total_electricity_kwh"]
    assert fact["value"] == 18420
    assert fact["source"] == "dingtalk_supplement"
    assert fact["source_detail"]["business_date"] == "2026-06-19"
    assert "total_electricity_kwh" not in bundle["missing_fields"]
    assert bundle["dingtalk_refs"] == [{"id": 1, "field_names": ["total_electricity_kwh"]}]
    assert _fact_closure_field(bundle, "total_electricity_kwh")["status"] == "confirmed"


def test_same_priority_dingtalk_candidate_does_not_override_existing_dingtalk_fact(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {},
            "sources": {},
            "missing_fields": ["total_output_daily"],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add_all(
        [
            MultimodalEvidence(
                evidence_type="dingtalk_text",
                recognized_text="6月19日总产量371吨",
                confirmation_status="confirmed",
                payload={
                    "business_date": "2026-06-19",
                    "include_in_daily_sample": True,
                    "evidence_kind": "fact",
                    "trace_id": "trace-first-output",
                    "parse_status": "text_captured",
                },
            ),
            MultimodalEvidence(
                evidence_type="dingtalk_text",
                recognized_text="6月19日总产量390吨",
                confirmation_status="confirmed",
                payload={
                    "business_date": "2026-06-19",
                    "include_in_daily_sample": True,
                    "evidence_kind": "fact",
                    "trace_id": "trace-second-output",
                    "parse_status": "text_captured",
                },
            ),
        ]
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["facts"]["total_output_daily"]["value"] == 371
    assert bundle["dingtalk_refs"] == [{"id": 1, "field_names": ["total_output_daily"]}]
    assert any(
        item["type"] == "dingtalk_candidate_not_applied"
        and item["field"] == "total_output_daily"
        and item["candidate_value"] == 390
        and item["reason"] == "same_priority_fact_exists"
        for item in bundle["conflicts"]
    )


def test_unstructured_dingtalk_today_from_other_business_day_is_excluded_but_remains_auditable(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"total_output_daily": 355},
            "sources": {"total_output_daily": "mes_packaging_output"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            source_user_id=None,
            recognized_text="今日总产量371吨",
            confirmation_status="confirmed",
            created_at=datetime(2026, 6, 18, 12, 0),
            payload={
                "include_in_daily_sample": True,
                "evidence_kind": "fact",
                "trace_id": "trace-old-today-output",
                "workshop_name": "精整",
                "parse_status": "text_captured",
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["facts"]["total_output_daily"]["value"] == 355
    assert bundle["facts"]["total_output_daily"]["source"] == "mes_packaging_output"
    assert bundle["dingtalk_refs"] == []
    assert bundle["conflicts"] == []

    audit_items = daily_fact_bundle.query_dingtalk_evidence(
        db_session,
        business_date=date(2026, 6, 19),
        include_outside_business_context=True,
    )
    assert [item.trace_id for item in audit_items] == ["trace-old-today-output"]


def test_unstructured_dingtalk_evidence_without_safe_business_date_is_excluded_but_remains_auditable(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"total_output_daily": 355},
            "sources": {"total_output_daily": "mes_packaging_output"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        MultimodalEvidence(
            evidence_type="dingtalk_text",
            source_user_id=None,
            recognized_text="成品入库 365.2 t",
            confirmation_status="confirmed",
            payload={
                "include_in_daily_sample": True,
                "evidence_kind": "fact",
                "trace_id": "trace-unapplied-output",
                "parse_status": "text_captured",
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["facts"]["total_output_daily"]["value"] == 355
    assert bundle["facts"]["total_output_daily"]["source"] == "mes_packaging_output"
    assert bundle["dingtalk_refs"] == []
    assert bundle["conflicts"] == []

    audit_items = daily_fact_bundle.query_dingtalk_evidence(
        db_session,
        business_date=date(2026, 6, 19),
        include_outside_business_context=True,
    )
    assert [item.trace_id for item in audit_items] == ["trace-unapplied-output"]


def test_dingtalk_supplement_overrides_mes_and_keeps_conflict(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        assert target_date == date(2026, 6, 19)
        return {
            "values": {"total_gas_m3": 50000},
            "sources": {"total_gas_m3": "mes_wms"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add(
        User(
            id=12,
            username="energy_owner",
            password_hash="hashed",
            name="energy_owner",
            role="admin",
        )
    )
    db_session.flush()
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
                "trace_id": "trace-gas-dingtalk",
                "parse_status": "text_captured",
                "fact_updates": {
                    "total_gas_m3": {
                        "value": 50578,
                        "unit": "m³",
                        "reason": "能源负责人钉钉补充",
                    }
                },
            },
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    fact = bundle["facts"]["total_gas_m3"]
    assert fact["value"] == 50578
    assert fact["source"] == "dingtalk_supplement"
    assert fact["source_type"] == "dingtalk_supplement"
    assert fact["priority"] == 100
    assert fact["confidence"] == 1.0
    assert fact["freshness"] == "supplemented"
    assert fact["adoption_reason"] == "能源负责人钉钉补充"
    assert fact["source_detail"] == {
        "source": "dingtalk_supplement",
        "evidence_id": 1,
        "source_user_id": 12,
        "file_uri": "dingtalk://gas/2026-06-19.xlsx",
        "evidence_type": "dingtalk_file",
        "source_key": "dingtalk_group_file",
        "recognized_text": "6月19日天然气共计50578m³",
        "business_date": "2026-06-19",
        "business_window": "2026-06-19T07:50:00+08:00/2026-06-20T07:50:00+08:00",
        "confirmation_status": "confirmed",
        "parse_status": "text_captured",
        "unit": "m³",
        "metric_contract_version": "2026-07-11",
        "trace_id": "trace-gas-dingtalk",
    }
    assert fact["source_ref"] == {
        "source": "dingtalk_supplement",
        "evidence_id": 1,
        "source_user_id": 12,
        "file_uri": "dingtalk://gas/2026-06-19.xlsx",
        "evidence_type": "dingtalk_file",
        "source_key": "dingtalk_group_file",
        "recognized_text": "6月19日天然气共计50578m³",
        "business_date": "2026-06-19",
        "business_window": "2026-06-19T07:50:00+08:00/2026-06-20T07:50:00+08:00",
        "confirmation_status": "confirmed",
        "parse_status": "text_captured",
        "unit": "m³",
        "metric_contract_version": "2026-07-11",
        "trace_id": "trace-gas-dingtalk",
    }
    assert bundle["sources"]["total_gas_m3"]["source"] == "dingtalk_supplement"
    assert bundle["dingtalk_refs"] == [{"id": 1, "field_names": ["total_gas_m3"]}]
    assert bundle["conflicts"][0] == {
        "field": "total_gas_m3",
        "type": "dingtalk_supplement",
        "previous_source": "mes_wms",
        "previous_value": 50000,
        "adopted_source": "dingtalk_supplement",
        "adopted_value": 50578,
        "reason": "能源负责人钉钉补充",
    }


def test_dingtalk_supplement_remains_primary_over_root_owner_correction(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        assert target_date == date(2026, 6, 19)
        return {
            "values": {"total_gas_m3": 50000},
            "sources": {"total_gas_m3": "mes_wms"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    db_session.add_all(
        [
            User(
                id=12,
                username="energy_owner",
                password_hash="hashed",
                name="energy_owner",
                role="admin",
            ),
            User(
                id=983,
                username="root_owner",
                password_hash="hashed",
                name="root_owner",
                role="admin",
            ),
        ]
    )
    db_session.flush()
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
                "trace_id": "trace-gas-dingtalk",
                "parse_status": "text_captured",
                "fact_updates": {
                    "total_gas_m3": {
                        "value": 50578,
                        "unit": "m³",
                        "reason": "能源负责人钉钉补充",
                    }
                },
            },
        )
    )
    db_session.add(
        DailyFactCorrection(
            business_date=date(2026, 6, 19),
            field_name="total_gas_m3",
            value_payload={"value": 50600},
            unit="m³",
            reason="root_owner 最终确认",
            actor_user_id=983,
            trace_id="trace-root-owner-gas",
        )
    )
    db_session.commit()

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    fact = bundle["facts"]["total_gas_m3"]
    assert fact["value"] == 50578
    assert fact["source"] == "dingtalk_supplement"
    assert fact["source_type"] == "dingtalk_supplement"
    assert fact["priority"] == 100
    assert bundle["dingtalk_refs"] == [{"id": 1, "field_names": ["total_gas_m3"]}]
    assert bundle["correction_refs"] == [
        {"id": 1, "field_name": "total_gas_m3", "trace_id": "trace-root-owner-gas"}
    ]
    assert any(item["type"] == "dingtalk_supplement" for item in bundle["conflicts"])
    assert next(
        item for item in bundle["conflicts"] if item["type"] == "root_owner_correction"
    ) == {
        "field": "total_gas_m3",
        "type": "root_owner_correction",
        "adopted_source": "dingtalk_supplement",
        "adopted_value": 50578,
        "candidate_source": "root_owner_correction",
        "candidate_value": 50600,
        "reason": "higher_priority_fact_retained",
    }


def test_build_daily_fact_bundle_reuses_existing_run_for_same_run_key(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"total_output_daily": 366},
            "sources": {"total_output_daily": "mes_packaging_output"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )

    daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 20), persist_run=True)
    daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 20), persist_run=True)

    runs = db_session.query(DailyFactBundleRun).all()
    snapshots = db_session.query(DailyFactBundleSnapshot).all()
    assert len(runs) == 1
    assert runs[0].business_date == date(2026, 6, 20)
    assert snapshots == []


def test_payload_hash_ignores_runtime_only_fact_closure() -> None:
    from app.services.report import daily_fact_bundle

    bundle = {
        "facts": {
            "total_output_daily": {
                "value": 366,
                "source": "mes_packaging_output",
                "source_type": "mes_packaging_output",
            }
        },
        "sources": {
            "total_output_daily": {"source": "mes_packaging_output"},
        },
        "conflicts": [],
        "correction_refs": [],
        "dingtalk_refs": [],
        "output_skill_alignment": {"status": "passed", "differences": []},
    }
    with_runtime_key = {
        **bundle,
        "fact_closure": {
            "status": "pass",
            "critical_fields": [],
        },
    }

    assert daily_fact_bundle._payload_hash(bundle) == daily_fact_bundle._payload_hash(
        with_runtime_key
    )


def test_daily_fact_bundle_persists_light_run_and_formal_snapshot(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        assert target_date == date(2026, 6, 19)
        return {
            "values": {"total_output_daily": 366},
            "sources": {"total_output_daily": "mes_packaging_output"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 6, 19),
        trace_id="trace-fact-bundle-persist",
        persist_run=True,
        snapshot_reason="formal_daily_report",
    )
    db_session.commit()

    run = db_session.query(DailyFactBundleRun).one()
    assert run.business_date == date(2026, 6, 19)
    assert run.trace_id == "trace-fact-bundle-persist"
    assert run.missing_count == 0
    assert run.conflict_count == 0
    assert run.confidence == 85
    assert run.source_status["sources"]["total_output_daily"]["source"] == "mes_packaging_output"

    snapshot = db_session.query(DailyFactBundleSnapshot).one()
    assert snapshot.snapshot_reason == "formal_daily_report"
    assert snapshot.facts == bundle["facts"]
    assert snapshot.sources == bundle["sources"]
    assert snapshot.adopted_values["total_output_daily"] == 366
    assert len(snapshot.payload_hash) == 64
    assert snapshot.trace_id == "trace-fact-bundle-persist"


def test_same_formal_snapshot_reason_creates_immutable_snapshots(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    values = iter((366, 367))

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"total_output_daily": next(values)},
            "sources": {"total_output_daily": "mes_packaging_output"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )

    daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 6, 19),
        trace_id="trace-formal-refresh",
        persist_run=True,
        snapshot_reason="formal_daily_report",
    )
    first_snapshot = db_session.query(DailyFactBundleSnapshot).one()
    first_snapshot_id = first_snapshot.id
    first_hash = first_snapshot.payload_hash
    daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 6, 19),
        trace_id="trace-formal-refresh",
        persist_run=True,
        snapshot_reason="formal_daily_report",
    )

    assert db_session.query(DailyFactBundleRun).count() == 1
    snapshots = db_session.query(DailyFactBundleSnapshot).order_by(DailyFactBundleSnapshot.id).all()
    assert len(snapshots) == 2
    assert snapshots[0].id == first_snapshot_id
    assert snapshots[0].adopted_values["total_output_daily"] == 366
    assert snapshots[0].payload_hash == first_hash
    assert snapshots[1].adopted_values["total_output_daily"] == 367
    assert snapshots[1].payload_hash != first_hash
    assert snapshots[0].snapshot_key is None
    assert snapshots[1].snapshot_key is None


def test_build_daily_fact_bundle_recovers_when_run_insert_hits_unique_race(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    business_date = date(2026, 6, 23)
    run_key = daily_fact_bundle._run_key(business_date=business_date, trace_id=None)
    race_triggered = False

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"total_output_daily": 366},
            "sources": {"total_output_daily": "mes_packaging_output"},
            "missing_fields": [],
            "conflicts": [],
        }

    class RaceContext:
        def __enter__(self) -> None:
            nonlocal race_triggered
            race_triggered = True
            db_session.execute(
                cast(Table, DailyFactBundleRun.__table__).insert().values(
                    run_key=run_key,
                    business_date=business_date,
                    status="ready",
                    source_status={},
                    missing_count=0,
                    conflict_count=0,
                )
            )
            raise IntegrityError("insert", {}, Exception("unique"))

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
            return False

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )
    monkeypatch.setattr(db_session, "begin_nested", lambda: RaceContext())

    daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=business_date, persist_run=True)

    runs = db_session.query(DailyFactBundleRun).all()
    assert race_triggered is True
    assert len(runs) == 1
    assert runs[0].run_key == run_key


def test_build_daily_fact_bundle_preserves_source_mapping_in_bundle_and_snapshot(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"total_output_daily": 366},
            "sources": {
                "total_output_daily": {
                    "source": "owner_daily",
                    "field": "total_output_daily",
                    "table": "x",
                    "token": "secret-token",
                },
            },
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 6, 21),
        persist_run=True,
        snapshot_reason="formal_daily_report",
    )

    assert bundle["facts"]["total_output_daily"]["source"] == "owner_daily"
    assert bundle["facts"]["total_output_daily"]["source_type"] == "owner_daily"
    assert bundle["facts"]["total_output_daily"]["source_detail"] == {
        "source": "owner_daily",
        "field": "total_output_daily",
        "table": "x",
    }
    assert bundle["sources"]["total_output_daily"] == {
        "source": "owner_daily",
        "field": "total_output_daily",
        "table": "x",
    }
    snapshot = db_session.query(DailyFactBundleSnapshot).one()
    assert snapshot.snapshot_reason == "formal_daily_report"
    assert snapshot.facts["total_output_daily"]["value"] == 366
    assert snapshot.sources["total_output_daily"] == {
        "source": "owner_daily",
        "field": "total_output_daily",
        "table": "x",
    }
    assert len(snapshot.payload_hash) == 64


def test_build_daily_fact_bundle_uses_template_projection_priority(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    def fake_template_facts(db, *, target_date, wip_date=None):
        return {
            "values": {"daily_contract_weight": 120},
            "sources": {"daily_contract_weight": "contract_projection"},
            "missing_fields": [],
            "conflicts": [],
        }

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        fake_template_facts,
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 22))

    assert bundle["facts"]["daily_contract_weight"]["priority"] == 60
    assert bundle["facts"]["daily_contract_weight"]["confidence"] == 0.65


def test_daily_fact_bundle_includes_output_skill_alignment(
    monkeypatch,
    tmp_path: Path,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    template_facts = {
        "values": {
            "report_date": date(2026, 6, 19),
            "total_output_daily": 366,
            "outsourced_daily": 0,
            "total_output_delta": 11,
            "total_output_month": 5971,
            "outsourced_month": 270,
        },
        "sources": {
            "report_date": "computed",
            "total_output_daily": "mes_packaging_output",
            "outsourced_daily": "mes_packaging_output",
            "total_output_delta": "computed",
            "total_output_month": "mes_packaging_output",
            "outsourced_month": "mes_packaging_output",
        },
        "missing_fields": [],
        "conflicts": [],
    }
    expected = daily_fact_bundle.template_daily_report.render_template_daily_report(template_facts)
    report_path = tmp_path / "2026-6-19_日报正文.txt"
    report_path.write_text(expected, encoding="utf-8")
    parsed_fields = set(parse_output_skill_daily_report(expected))
    report_path.with_suffix(".na.json").write_text(
        json.dumps(
            {
                "not_applicable": [
                    field_name
                    for field_name in normative_daily_report_fields()
                    if field_name not in parsed_fields
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: template_facts,
    )
    monkeypatch.setenv("OUTPUT_SKILL_ROOT", str(tmp_path))

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    assert bundle["output_skill_alignment"]["status"] == "passed"
    assert bundle["output_skill_alignment"]["file_name"] == "2026-6-19_日报正文.txt"
    assert bundle["output_skill_alignment"]["field_match_rate"] == 100.0
    assert bundle["gap_plan"]["status"] == "ready"


def test_daily_fact_bundle_real_source_gate_requires_closed_reference_contract(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {"report_date": target_date},
            "sources": {"report_date": "computed"},
            "missing_fields": [],
            "conflicts": [],
        },
    )
    monkeypatch.setattr(
        daily_fact_bundle,
        "build_output_skill_alignment",
        lambda *_args, **_kwargs: {
            "status": "blocked",
            "reference_absent_fields": ["total_output_daily"],
        },
    )
    monkeypatch.setattr(
        daily_fact_bundle,
        "build_daily_report_fact_closure",
        lambda _bundle: {"status": "pass"},
    )

    bundle = daily_fact_bundle.build_daily_fact_bundle(
        db_session,
        business_date=date(2026, 6, 19),
        allow_output_skill_reference_adoption=False,
    )

    assert bundle["output_skill_alignment"]["status"] == "blocked"
    assert bundle["fact_closure"]["status"] == "pass"
    assert bundle["real_source_gate_passed"] is False


def test_daily_fact_bundle_output_skill_adoption_stays_blocked_as_reference_only(
    monkeypatch,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle
    from app.services.report.template_daily_report import REQUIRED_FIELDS

    fixture_dir = Path(__file__).parent / "fixtures" / "output_skill_daily_reports"

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: {
            "values": {},
            "sources": {},
            "missing_fields": list(REQUIRED_FIELDS),
            "conflicts": [],
        },
    )
    monkeypatch.setenv("OUTPUT_SKILL_ROOT", str(fixture_dir))
    monkeypatch.setenv("OUTPUT_SKILL_REFERENCE_MODE", "adopt")

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 16))
    parsed_reference = parse_output_skill_daily_report(
        (fixture_dir / "2026-6-16_日报正文.txt").read_text(encoding="utf-8")
    )
    reference_fields = [
        *[field for field in REQUIRED_FIELDS if field in parsed_reference],
        *[field for field in parsed_reference if field not in REQUIRED_FIELDS],
    ]

    assert bundle["output_skill_alignment"]["status"] == "passed"
    assert bundle["output_skill_alignment"]["field_match_rate"] == 100.0
    assert bundle["reference_only"] is True
    assert bundle["real_source_gate_passed"] is False
    assert bundle["missing_fields"] == []
    assert bundle["fact_closure"]["status"] == "blocked"
    assert bundle["fact_closure"]["reference_only"] is True
    assert _fact_closure_field(bundle, "total_output_daily")["status"] == "needs_evidence"
    assert bundle["facts"]["total_output_daily"]["value"] == 328
    assert bundle["facts"]["total_output_daily"]["source_type"] == "official_daily_report"
    assert bundle["facts"]["total_output_daily"]["source_detail"] == {
        "source": "official_daily_report",
        "source_type": "official_daily_report",
        "reference_kind": "output_skill_daily_report",
        "file_name": "2026-6-16_日报正文.txt",
        "business_date": "2026-06-16",
    }
    assert bundle["output_skill_refs"] == [
        {
            "file_name": "2026-6-16_日报正文.txt",
            "field_count": len(reference_fields),
            "field_names": reference_fields,
        }
    ]


def test_daily_fact_bundle_includes_gap_plan_for_output_skill_differences(
    monkeypatch,
    tmp_path: Path,
    db_session: Session,
) -> None:
    from app.services.report import daily_fact_bundle

    template_facts = {
        "values": {
            "report_date": date(2026, 6, 19),
            "total_output_daily": 384,
            "outsourced_daily": 0,
            "total_output_delta": 0,
            "total_output_month": 6000,
            "outsourced_month": 270,
        },
        "sources": {
            "report_date": "computed",
            "total_output_daily": "mes_packaging_output",
            "outsourced_daily": "mes_packaging_output",
            "total_output_delta": "computed",
            "total_output_month": "mes_packaging_output",
            "outsourced_month": "mes_packaging_output",
        },
        "missing_fields": ["total_electricity_kwh"],
        "conflicts": [],
    }
    expected_facts = {
        **template_facts,
        "values": {
            **template_facts["values"],
            "total_output_daily": 360,
        },
    }
    expected = daily_fact_bundle.template_daily_report.render_template_daily_report(expected_facts)
    (tmp_path / "2026-6-19_日报正文.txt").write_text(expected, encoding="utf-8")

    monkeypatch.setattr(
        daily_fact_bundle.template_daily_report,
        "build_template_daily_report_facts",
        lambda db, *, target_date, wip_date=None: template_facts,
    )
    monkeypatch.setenv("OUTPUT_SKILL_ROOT", str(tmp_path))

    bundle = daily_fact_bundle.build_daily_fact_bundle(db_session, business_date=date(2026, 6, 19))

    fields = {item["field"]: item for item in bundle["gap_plan"]["items"]}
    assert bundle["gap_plan"]["status"] == "needs_action"
    assert fields["total_electricity_kwh"]["source_lane"] == "dingtalk_or_scan_fill_energy"
    assert fields["total_output_daily"]["source_lane"] == "dingtalk_or_final_daily_report"
    assert fields["total_output_daily"]["current_source"] == "mes_packaging_output"


def test_refresh_bundle_metadata_syncs_fact_overlays() -> None:
    from app.services.report import daily_fact_bundle

    bundle = {
        "status": "partial",
        "facts": {
            "total_output_daily": {
                "value": 400,
                "unit": "吨",
                "source": "root_owner_correction",
                "source_type": "root_owner_correction",
                "priority": 100,
                "confidence": 1.0,
                "freshness": "confirmed",
                "adoption_reason": "root_owner 确认",
                "source_detail": {
                    "source": "root_owner_correction",
                    "correction_id": 7,
                    "token": "secret-token",
                },
            },
        },
        "missing_fields": [],
        "missing": ["stale_missing"],
        "conflicts": [],
    }

    refreshed = daily_fact_bundle._refresh_bundle_metadata(bundle)

    assert refreshed["sources"]["total_output_daily"] == {
        "source": "root_owner_correction",
        "correction_id": 7,
    }
    assert refreshed["freshness"]["total_output_daily"] == "confirmed"
    assert refreshed["confidence"] == 1.0
    assert refreshed["missing_fields"] == []
    assert refreshed["missing"] == []
    assert refreshed["status"] == "ready"

    refreshed["missing_fields"] = ["total_gas_m3"]
    daily_fact_bundle._refresh_bundle_metadata(refreshed)

    assert refreshed["missing"] == ["total_gas_m3"]
    assert refreshed["status"] == "blocked"


def _assert_daily_fact_bundle_schema(
    inspector: sa.Inspector,
    *,
    expect_snapshot_key: bool,
) -> None:
    table_names = set(inspector.get_table_names())
    assert "daily_fact_bundle_runs" in table_names
    assert "daily_fact_bundle_snapshots" in table_names
    assert "daily_fact_corrections" in table_names

    run_indexes = inspector.get_indexes("daily_fact_bundle_runs")
    snapshot_indexes = inspector.get_indexes("daily_fact_bundle_snapshots")
    correction_indexes = inspector.get_indexes("daily_fact_corrections")
    snapshot_columns = {column["name"]: column for column in inspector.get_columns("daily_fact_bundle_snapshots")}
    assert any("run_key" in index["column_names"] and bool(index.get("unique")) for index in run_indexes)
    assert any("business_date" in index["column_names"] for index in run_indexes)
    assert any("run_id" in index["column_names"] for index in snapshot_indexes)
    assert any("payload_hash" in index["column_names"] for index in snapshot_indexes)
    if expect_snapshot_key:
        assert snapshot_columns["snapshot_key"]["nullable"] is True
        assert any(
            index["column_names"] == ["snapshot_key"] and bool(index.get("unique"))
            for index in snapshot_indexes
        )
    else:
        assert "snapshot_key" not in snapshot_columns
    assert any("field_name" in index["column_names"] for index in correction_indexes)


def _load_daily_fact_bundle_migration():
    migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0050_daily_fact_bundle.py"
    spec = importlib.util.spec_from_file_location("daily_fact_bundle_migration_0050", migration_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_snapshot_key_migration():
    migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0053_daily_fact_snapshot_key.py"
    spec = importlib.util.spec_from_file_location("daily_fact_snapshot_key_migration_0053", migration_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
