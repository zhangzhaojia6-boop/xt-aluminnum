from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Equipment, Workshop
from app.models.mes import MesCoilSnapshot, MesWorkshopProcessRecord
from app.models.production import WorkOrder, WorkOrderEntry
from app.services import mes_fill_gap_service


BUSINESS_DATE = date(2026, 5, 6)


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mes-fill-gap.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Equipment.__table__,
            MesCoilSnapshot.__table__,
            MesWorkshopProcessRecord.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _seed_master(db) -> None:
    db.add_all(
        [
            Workshop(id=1, code='LZ2050', name='2050冷轧车间', workshop_type='cold_rolling', sort_order=1, is_active=True),
            Workshop(id=2, code='JZ', name='精整车间', workshop_type='finishing', sort_order=2, is_active=True),
            Equipment(id=11, code='LZ2050-1', name='2050-1#轧机', workshop_id=1, equipment_type='cold_mill', is_active=True),
            Equipment(id=21, code='JZ-1', name='精整1#线', workshop_id=2, equipment_type='finishing', is_active=True),
        ]
    )


def _add_snapshot(db, *, tracking_card_no: str, batch_no: str, workshop_name: str = '2050冷轧车间') -> None:
    db.add(
        MesCoilSnapshot(
            coil_id=f'MES-{tracking_card_no}',
            tracking_card_no=tracking_card_no,
            batch_no=batch_no,
            alloy_grade='5052',
            spec_display='1.0×1200',
            current_workshop=workshop_name,
            current_process='冷轧',
        )
    )


def _add_process(
    db,
    *,
    source_id: str,
    batch_no: str,
    output_weight_kg: float = 960,
    workshop_name: str = '2050冷轧车间',
    process_name: str = '冷轧',
    device_name: str = '2050-1#轧机',
) -> None:
    db.add(
        MesWorkshopProcessRecord(
            source_id=source_id,
            source_path='mvc',
            batch_no=batch_no,
            workshop_name=workshop_name,
            process_name=process_name,
            device_name=device_name,
            input_weight_kg=1000,
            output_weight_kg=output_weight_kg,
            business_date=BUSINESS_DATE,
            end_time=datetime(2026, 5, 6, 11, 30),
        )
    )


def _add_local_entry(
    db,
    *,
    entry_id: int,
    tracking_card_no: str,
    output_weight: float = 960,
    workshop_id: int = 1,
    machine_id: int | None = 11,
) -> None:
    work_order = WorkOrder(
        id=entry_id,
        tracking_card_no=tracking_card_no,
        process_route_code='mobile',
        overall_status='created',
    )
    db.add(work_order)
    db.flush()
    db.add(
        WorkOrderEntry(
            id=entry_id,
            work_order_id=work_order.id,
            workshop_id=workshop_id,
            machine_id=machine_id,
            business_date=BUSINESS_DATE,
            input_weight=1000,
            output_weight=output_weight,
            entry_status='submitted',
            entry_type='mobile_coil',
        )
    )


def test_mes_fill_gap_marks_missing_local_entry(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_master(db)
        _add_snapshot(db, tracking_card_no='TRACK-MISSING', batch_no='BATCH-MISSING')
        _add_process(db, source_id='PROC-MISSING', batch_no='BATCH-MISSING')
        db.commit()

    with session_factory() as db:
        payload = mes_fill_gap_service.build_mes_fill_gaps(db, business_date=BUSINESS_DATE)

    assert payload['summary']['status_counts']['missing_local_entry'] == 1
    assert payload['items'][0]['status'] == 'missing_local_entry'
    assert payload['items'][0]['tracking_card_no'] == 'TRACK-MISSING'
    assert payload['items'][0]['local_entry_id'] is None
    assert payload['items'][0]['shift_name'] == '长白班'
    assert payload['items'][0]['shift_window'] == '07:30-15:30'
    assert payload['items'][0]['mes_end_time'] == '2026-05-06T11:30:00'


def test_mes_fill_gap_matches_split_batch_to_base_snapshot(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_master(db)
        _add_snapshot(db, tracking_card_no='TRACK-SPLIT', batch_no='BATCH-SPLIT')
        _add_process(db, source_id='PROC-SPLIT', batch_no='BATCH-SPLIT-2')
        db.commit()

    with session_factory() as db:
        payload = mes_fill_gap_service.build_mes_fill_gaps(db, business_date=BUSINESS_DATE)

    assert payload['items'][0]['status'] == 'missing_local_entry'
    assert payload['items'][0]['tracking_card_no'] == 'TRACK-SPLIT'


def test_mes_fill_gap_marks_unmapped_mes_batch(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_master(db)
        _add_process(db, source_id='PROC-UNMAPPED', batch_no='BATCH-UNMAPPED')
        db.commit()

    with session_factory() as db:
        payload = mes_fill_gap_service.build_mes_fill_gaps(db, business_date=BUSINESS_DATE)

    assert payload['items'][0]['status'] == 'mes_batch_unmapped'
    assert payload['items'][0]['batch_no'] == 'BATCH-UNMAPPED'
    assert payload['items'][0]['tracking_card_no'] is None


def test_mes_fill_gap_marks_local_entry_without_machine(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_master(db)
        _add_snapshot(db, tracking_card_no='TRACK-NO-MACHINE', batch_no='BATCH-NO-MACHINE')
        _add_process(db, source_id='PROC-NO-MACHINE', batch_no='BATCH-NO-MACHINE')
        _add_local_entry(db, entry_id=301, tracking_card_no='TRACK-NO-MACHINE', machine_id=None)
        db.commit()

    with session_factory() as db:
        payload = mes_fill_gap_service.build_mes_fill_gaps(db, business_date=BUSINESS_DATE)

    assert payload['items'][0]['status'] == 'local_entry_unassigned'
    assert payload['items'][0]['local_entry_id'] == 301
    assert payload['items'][0]['local_machine_name'] is None


def test_mes_fill_gap_marks_weight_mismatch_over_one_kg(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_master(db)
        _add_snapshot(db, tracking_card_no='TRACK-WEIGHT', batch_no='BATCH-WEIGHT')
        _add_process(db, source_id='PROC-WEIGHT', batch_no='BATCH-WEIGHT', output_weight_kg=960)
        _add_local_entry(db, entry_id=401, tracking_card_no='TRACK-WEIGHT', output_weight=958)
        db.commit()

    with session_factory() as db:
        payload = mes_fill_gap_service.build_mes_fill_gaps(db, business_date=BUSINESS_DATE)

    assert payload['items'][0]['status'] == 'weight_mismatch'
    assert payload['items'][0]['mes_output_weight'] == 960.0
    assert payload['items'][0]['local_output_weight'] == 958.0


def test_mes_fill_gap_marks_matched_within_one_kg(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_master(db)
        _add_snapshot(db, tracking_card_no='TRACK-MATCHED', batch_no='BATCH-MATCHED')
        _add_process(db, source_id='PROC-MATCHED', batch_no='BATCH-MATCHED', output_weight_kg=960)
        _add_local_entry(db, entry_id=501, tracking_card_no='TRACK-MATCHED', output_weight=959.5)
        db.commit()

    with session_factory() as db:
        payload = mes_fill_gap_service.build_mes_fill_gaps(db, business_date=BUSINESS_DATE)

    assert payload['items'][0]['status'] == 'matched'
    assert payload['summary']['status_counts']['matched'] == 1


def test_mes_fill_gap_filters_to_workshop_scope(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_master(db)
        _add_snapshot(db, tracking_card_no='TRACK-2050', batch_no='BATCH-2050', workshop_name='2050冷轧车间')
        _add_process(db, source_id='PROC-2050', batch_no='BATCH-2050', workshop_name='2050冷轧车间')
        _add_snapshot(db, tracking_card_no='TRACK-JZ', batch_no='BATCH-JZ', workshop_name='精整车间')
        _add_process(db, source_id='PROC-JZ', batch_no='BATCH-JZ', workshop_name='精整车间', device_name='精整1#线')
        db.commit()

    with session_factory() as db:
        payload = mes_fill_gap_service.build_mes_fill_gaps(db, business_date=BUSINESS_DATE, workshop_id=2)

    assert payload['total'] == 1
    assert payload['items'][0]['workshop_id'] == 2
    assert payload['items'][0]['workshop_name'] == '精整车间'
