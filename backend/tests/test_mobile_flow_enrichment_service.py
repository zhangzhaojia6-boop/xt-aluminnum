from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Equipment, Workshop
from app.models.mes import MesCoilSnapshot
from app.models.production import ShiftProductionData, WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services.mobile_report.flow_enrichment import enrich_mobile_coil_flow_context


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mobile-flow-enrichment.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Equipment.__table__,
            ShiftConfig.__table__,
            User.__table__,
            MesCoilSnapshot.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            ShiftProductionData.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _add_mobile_entry(db, *, tracking_card_no: str, status: str = 'submitted', extra_payload: dict | None = None) -> WorkOrderEntry:
    work_order = WorkOrder(
        tracking_card_no=tracking_card_no,
        alloy_grade='5052',
        process_route_code='mobile',
        overall_status='created',
    )
    db.add(work_order)
    db.flush()
    entry = WorkOrderEntry(
        work_order_id=work_order.id,
        workshop_id=1,
        machine_id=12,
        shift_id=5,
        business_date=date(2026, 5, 12),
        input_weight=9300,
        output_weight=9000,
        extra_payload=extra_payload,
        entry_type='mobile_coil',
        entry_status=status,
    )
    db.add(entry)
    db.flush()
    return entry


def _add_mes_snapshot(db) -> None:
    db.add(
        MesCoilSnapshot(
            coil_id='fallback:26RA03782:R3-9216-2',
            tracking_card_no='26RA03782',
            material_code='R3-9216-2',
            batch_no='26RA03782',
            alloy_grade='5052',
            spec_display='3.175×1524×3048',
            current_workshop='2050车间',
            current_process='冷轧',
            next_workshop='新厂在线车间',
            next_process='北线退火',
            updated_from_mes_at=datetime(2026, 5, 12, 9, tzinfo=timezone.utc),
        )
    )


def test_flow_context_enrichment_dry_run_reports_candidates_without_mutating(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        entry = _add_mobile_entry(db, tracking_card_no='R3-9216-2', extra_payload={'operator_note': 'keep'})
        _add_mes_snapshot(db)
        db.commit()
        entry_id = entry.id

    with session_factory() as db:
        result = enrich_mobile_coil_flow_context(db, business_date=date(2026, 5, 12), apply=False)

    assert result['scanned_count'] == 1
    assert result['candidate_count'] == 1
    assert result['updated_count'] == 0
    assert result['samples'][0]['entry_id'] == entry_id
    assert result['samples'][0]['flow']['next_process'] == '北线退火'

    with session_factory() as db:
        entry = db.get(WorkOrderEntry, entry_id)
        assert entry.extra_payload == {'operator_note': 'keep'}


def test_flow_context_enrichment_applies_only_missing_flow_context(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        target = _add_mobile_entry(db, tracking_card_no='R3-9216-2', extra_payload={'operator_note': 'keep'})
        existing = _add_mobile_entry(
            db,
            tracking_card_no='FLOW-EXISTS',
            extra_payload={'flow': {'next_process': '人工确认'}, 'operator_note': 'preserve'},
        )
        draft = _add_mobile_entry(db, tracking_card_no='R3-9216-DRAFT', status='draft', extra_payload={})
        _add_mes_snapshot(db)
        db.commit()
        target_id = target.id
        existing_id = existing.id
        draft_id = draft.id

    with session_factory() as db:
        result = enrich_mobile_coil_flow_context(db, business_date=date(2026, 5, 12), apply=True)

    assert result['scanned_count'] == 2
    assert result['candidate_count'] == 1
    assert result['updated_count'] == 1
    assert result['skipped_existing_flow_count'] == 1

    with session_factory() as db:
        target = db.get(WorkOrderEntry, target_id)
        assert target.entry_status == 'submitted'
        assert float(target.input_weight) == 9300
        assert float(target.output_weight) == 9000
        assert target.machine_id == 12
        assert target.extra_payload['operator_note'] == 'keep'
        assert target.extra_payload['flow']['current_workshop'] == '2050车间'
        assert target.extra_payload['flow']['next_process'] == '北线退火'
        assert target.extra_payload['mes_reference']['tracking_card_no'] == '26RA03782'

        existing = db.get(WorkOrderEntry, existing_id)
        assert existing.extra_payload == {'flow': {'next_process': '人工确认'}, 'operator_note': 'preserve'}

        draft = db.get(WorkOrderEntry, draft_id)
        assert draft.extra_payload == {}
