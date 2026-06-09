from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Equipment, Workshop
from app.models.mes import MesCoilSnapshot, MesWorkshopProcessRecord
from app.services import scan_lookup_service


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'scan-lookup.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[Workshop.__table__, Equipment.__table__, MesCoilSnapshot.__table__, MesWorkshopProcessRecord.__table__],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _session_factory_without_mes(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'scan-lookup-without-mes.db'}", future=True)
    Base.metadata.create_all(engine, tables=[Workshop.__table__, Equipment.__table__])
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _seed_workshop(db) -> Workshop:
    workshop = Workshop(code='ZR2', name='铸二车间', workshop_type='casting', sort_order=1, is_active=True)
    db.add(workshop)
    db.flush()
    return workshop


def test_scan_lookup_hits_mes_coil_qr_first(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES-QR-1',
                tracking_card_no='TRACK-QR-1',
                qr_code='XT-20260503-001',
                batch_no='BATCH-001',
                alloy_grade='6061',
                spec_thickness=1.2,
                spec_width=1200,
                spec_display='1.2×1200',
                contract_no='HT-001',
                current_workshop='冷轧车间',
                current_process='冷轧',
                next_workshop='退火车间',
                next_process='退火',
                material_weight=1580,
            )
        )
        db.commit()

    with session_factory() as db:
        payload = scan_lookup_service.lookup_qr(db, qr='XT-20260503-001')

    assert payload['source'] == 'coil_snapshot'
    assert payload['header_fields']['tracking_card_no'] == 'TRACK-QR-1'
    assert payload['header_fields']['batch_no'] == 'BATCH-001'
    assert payload['header_fields']['alloy_grade'] == '6061'
    assert payload['header_fields']['spec_thickness'] == 1.2
    assert payload['header_fields']['spec_width'] == 1200.0
    assert payload['header_fields']['spec_display'] == '1.2×1200'
    assert payload['header_fields']['contract_no'] == 'HT-001'
    assert payload['header_fields']['current_workshop'] == '冷轧车间'
    assert payload['header_fields']['current_process'] == '冷轧'
    assert payload['header_fields']['next_workshop'] == '退火车间'
    assert payload['header_fields']['next_process'] == '退火'
    assert payload['header_fields']['material_weight'] == 1580.0
    assert payload['lock_keys'] == []
    assert payload['lock_token'] is None


def test_scan_lookup_enriches_header_fields_from_latest_mes_process(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES-PROC-QR-1',
                tracking_card_no='TRACK-PROC-1',
                qr_code='QR-PROC-1',
                batch_no='BATCH-PROC-1',
                alloy_grade='6061',
                material_state='H24',
                spec_display='1.2×1200',
            )
        )
        db.add(
            MesWorkshopProcessRecord(
                source_id='PROC-LOOKUP-1',
                source_path='mvc',
                batch_no='BATCH-PROC-1',
                workshop_name='冷轧车间',
                process_name='精轧',
                device_name='2#轧机',
                input_weight_kg=1000,
                output_weight_kg=960,
                end_time=datetime(2026, 5, 3, 8, 20, tzinfo=timezone.utc),
                source_payload={
                    'BeginSpecification': '1.0×1200',
                    'EndSpecification': '0.8×1200',
                    'BeginDatetime': '2026-05-03T07:40:00+00:00',
                    'EndDatetime': '2026-05-03T08:20:00+00:00',
                },
            )
        )
        db.commit()

    with session_factory() as db:
        payload = scan_lookup_service.lookup_qr(db, qr='QR-PROC-1')

    assert payload['source'] == 'coil_snapshot'
    assert payload['header_fields']['tracking_card_no'] == 'TRACK-PROC-1'
    assert payload['header_fields']['input_spec'] == '1.0×1200'
    assert payload['header_fields']['output_spec'] == '0.8×1200'
    assert payload['header_fields']['input_weight'] == 1000.0
    assert payload['header_fields']['output_weight'] == 960.0
    assert payload['header_fields']['on_machine_time'] == '15:40'
    assert payload['header_fields']['off_machine_time'] == '16:20'
    assert payload['header_fields']['material_state'] == 'H24'
    assert payload['lock_keys'] == []
    assert payload['lock_token'] is None


def test_scan_lookup_uses_latest_mes_coil_qr_snapshot(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add_all(
            [
                MesCoilSnapshot(
                    coil_id='MES-QR-OLD',
                    tracking_card_no='TRACK-QR-SAME',
                    qr_code='QR-SAME',
                    batch_no='OLD',
                    alloy_grade='3003',
                    spec_display='1.0×1000',
                    updated_from_mes_at=datetime(2026, 5, 3, 8, tzinfo=timezone.utc),
                ),
                MesCoilSnapshot(
                    coil_id='MES-QR-NEW',
                    tracking_card_no='TRACK-QR-SAME',
                    qr_code='QR-SAME',
                    batch_no='NEW',
                    alloy_grade='5052',
                    spec_display='2.0×1200',
                    updated_from_mes_at=datetime(2026, 5, 3, 9, tzinfo=timezone.utc),
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        payload = scan_lookup_service.lookup_qr(db, qr='QR-SAME')

    assert payload['source'] == 'coil_snapshot'
    assert payload['header_fields']['batch_no'] == 'NEW'
    assert payload['header_fields']['alloy_grade'] == '5052'
    assert payload['lock_keys'] == []
    assert payload['lock_token'] is None


def test_scan_lookup_hits_tracking_card_latest_snapshot_when_qr_misses(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add_all(
            [
                MesCoilSnapshot(
                    coil_id='MES-TC-1',
                    tracking_card_no='TRACK-SAME',
                    qr_code='QR-A',
                    batch_no='FIRST',
                    alloy_grade='3003',
                    spec_display='1.0×1000',
                    updated_from_mes_at=datetime(2026, 5, 3, 8, tzinfo=timezone.utc),
                ),
                MesCoilSnapshot(
                    coil_id='MES-TC-2',
                    tracking_card_no='TRACK-SAME',
                    qr_code='QR-B',
                    batch_no='SECOND',
                    alloy_grade='5052',
                    spec_display='2.0×1200',
                    updated_from_mes_at=datetime(2026, 5, 3, 9, tzinfo=timezone.utc),
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        payload = scan_lookup_service.lookup_qr(db, qr='TRACK-SAME')

    assert payload['source'] == 'tracking_card'
    assert payload['header_fields']['batch_no'] == 'SECOND'
    assert payload['header_fields']['alloy_grade'] == '5052'
    assert payload['lock_keys'] == []
    assert payload['lock_token'] is None


def test_scan_lookup_hits_material_code_when_tracking_card_differs(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES-MATERIAL-1',
                tracking_card_no='26RA03782',
                material_code='R3-9216-2',
                batch_no='26RA03782',
                alloy_grade='5052',
                spec_display='3.175×1524×3048',
                current_workshop='2050车间',
                current_process='冷轧',
                next_workshop='新厂在线车间',
                next_process='北线退火',
                updated_from_mes_at=datetime(2026, 5, 10, 9, tzinfo=timezone.utc),
            )
        )
        db.commit()

    with session_factory() as db:
        payload = scan_lookup_service.lookup_qr(db, qr='R3-9216-2')

    assert payload['source'] == 'coil_identifier'
    assert payload['header_fields']['tracking_card_no'] == 'R3-9216-2'
    assert payload['header_fields']['material_code'] == 'R3-9216-2'
    assert payload['header_fields']['batch_no'] == '26RA03782'
    assert payload['header_fields']['current_workshop'] == '2050车间'
    assert payload['header_fields']['current_process'] == '冷轧'
    assert payload['header_fields']['next_process'] == '北线退火'


def test_scan_lookup_matches_tracking_card_separator_variants(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES-TC-VARIANT',
                tracking_card_no='S-2-054-1',
                batch_no='BATCH-VARIANT',
                alloy_grade='3003',
                spec_display='1.0×1200',
                updated_from_mes_at=datetime(2026, 5, 3, 9, tzinfo=timezone.utc),
            )
        )
        db.commit()

    with session_factory() as db:
        payload = scan_lookup_service.lookup_qr(db, qr='S一2一054一1')
        locked_snapshot = scan_lookup_service.submission_locked_snapshot_for_tracking_card(
            db,
            tracking_card_no='S一2一054一1',
        )

    assert payload['source'] == 'tracking_card'
    assert payload['header_fields']['tracking_card_no'] == 'S-2-054-1'
    assert payload['header_fields']['batch_no'] == 'BATCH-VARIANT'
    assert locked_snapshot == {}


def test_submission_locked_snapshot_uses_latest_mes_snapshot(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add_all(
            [
                MesCoilSnapshot(
                    coil_id='MES-LOCK-OLD',
                    tracking_card_no='TRACK-LOCK-SAME',
                    alloy_grade='6061',
                    spec_display='1.0×1000',
                    updated_from_mes_at=datetime(2026, 5, 3, 8, tzinfo=timezone.utc),
                ),
                MesCoilSnapshot(
                    coil_id='MES-LOCK-NEW',
                    tracking_card_no='TRACK-LOCK-SAME',
                    alloy_grade='7075',
                    spec_display='2.0×1200',
                    updated_from_mes_at=datetime(2026, 5, 3, 9, tzinfo=timezone.utc),
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        snapshot = scan_lookup_service.submission_locked_snapshot_for_tracking_card(
            db,
            tracking_card_no='TRACK-LOCK-SAME',
        )

    assert snapshot == {}


def test_scan_lookup_hits_equipment_qr(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        workshop = _seed_workshop(db)
        db.add(
            Equipment(
                code='ZD-1',
                name='1#机',
                workshop_id=workshop.id,
                equipment_type='ingot_caster',
                operational_status='running',
                shift_mode='three',
                qr_code='XT-ZD-1',
                is_active=True,
            )
        )
        db.commit()

    with session_factory() as db:
        payload = scan_lookup_service.lookup_qr(db, qr='XT-ZD-1')

    assert payload['source'] == 'machine_identity'
    assert payload['header_fields'] == {
        'equipment_code': 'ZD-1',
        'equipment_name': '1#机',
        'workshop_id': 1,
    }
    assert payload['lock_keys'] == []
    assert payload['lock_token'] is None


def test_scan_lookup_hits_equipment_qr_when_mes_table_missing(tmp_path) -> None:
    session_factory = _session_factory_without_mes(tmp_path)
    with session_factory() as db:
        workshop = _seed_workshop(db)
        db.add(
            Equipment(
                code='ZD-NO-MES',
                name='无快照表机台',
                workshop_id=workshop.id,
                equipment_type='ingot_caster',
                operational_status='running',
                shift_mode='three',
                qr_code='XT-NO-MES',
                is_active=True,
            )
        )
        db.commit()

    with session_factory() as db:
        payload = scan_lookup_service.lookup_qr(db, qr='XT-NO-MES')

    assert payload['source'] == 'machine_identity'
    assert payload['header_fields'] == {
        'equipment_code': 'ZD-NO-MES',
        'equipment_name': '无快照表机台',
        'workshop_id': 1,
    }


def test_scan_lookup_raises_not_found_when_qr_unknown(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db, pytest.raises(scan_lookup_service.ScanLookupNotFound):
        scan_lookup_service.lookup_qr(db, qr='missing')


def _seed_workshop_with_machines(db, *, workshop_code: str, workshop_name: str, machines: list[dict]):
    workshop = Workshop(code=workshop_code, name=workshop_name, workshop_type='cold_rolling', sort_order=1, is_active=True)
    db.add(workshop)
    db.flush()
    seeded = []
    for spec in machines:
        equipment = Equipment(
            code=spec['code'],
            name=spec['name'],
            workshop_id=workshop.id,
            equipment_type=spec['equipment_type'],
            operational_status='running',
            shift_mode='three',
            is_active=True,
        )
        db.add(equipment)
        seeded.append(equipment)
    db.flush()
    return workshop, seeded


def test_scan_lookup_binds_machine_when_workshop_process_unique(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _, machines = _seed_workshop_with_machines(
            db,
            workshop_code='2050',
            workshop_name='2050车间',
            machines=[{'code': 'LZ2050-1', 'name': '2050冷轧机', 'equipment_type': 'cold_mill'}],
        )
        db.add(
            MesCoilSnapshot(
                coil_id='MES-BIND-1',
                tracking_card_no='TRACK-BIND-1',
                material_code='R3-2050-A',
                qr_code='QR-BIND-1',
                alloy_grade='5052',
                spec_display='3.175×1524',
                current_workshop='2050车间',
                current_process='冷轧',
                next_workshop='新厂在线车间',
                next_process='北线退火',
            )
        )
        db.commit()
        machine_id = machines[0].id

    with session_factory() as db:
        payload = scan_lookup_service.lookup_qr(db, qr='QR-BIND-1')

    assert payload['source'] == 'coil_snapshot'
    assert payload['machine_line_id'] == machine_id
    assert payload['machine_line_code'] == 'LZ2050-1'
    assert payload['machine_line_name'] == '2050冷轧机'
    assert payload['machine_binding_source'] == 'route_inferred'


def test_scan_lookup_keeps_machine_unresolved_when_multiple_candidates(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _seed_workshop_with_machines(
            db,
            workshop_code='JZ',
            workshop_name='精整车间',
            machines=[
                {'code': 'SLIT-1', 'name': '1#纵剪', 'equipment_type': 'slitter'},
                {'code': 'SLIT-2', 'name': '2#纵剪', 'equipment_type': 'slitter'},
            ],
        )
        db.add(
            MesCoilSnapshot(
                coil_id='MES-MULTI-1',
                tracking_card_no='TRACK-MULTI-1',
                qr_code='QR-MULTI-1',
                alloy_grade='3003',
                spec_display='1.0×1000',
                current_workshop='精整车间',
                current_process='纵剪',
            )
        )
        db.commit()

    with session_factory() as db:
        payload = scan_lookup_service.lookup_qr(db, qr='QR-MULTI-1')

    assert payload['source'] == 'coil_snapshot'
    assert payload['machine_line_id'] is None
    assert payload['machine_line_code'] is None
    assert payload['machine_line_name'] is None
    assert payload['machine_binding_source'] == 'unresolved'


def test_scan_lookup_uses_direct_machine_code_when_present(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        _, machines = _seed_workshop_with_machines(
            db,
            workshop_code='2050',
            workshop_name='2050车间',
            machines=[
                {'code': 'LZ2050-1', 'name': '1#冷轧', 'equipment_type': 'cold_mill'},
                {'code': 'LZ2050-2', 'name': '2#冷轧', 'equipment_type': 'cold_mill'},
            ],
        )
        db.add(
            MesCoilSnapshot(
                coil_id='MES-DIRECT-1',
                tracking_card_no='TRACK-DIRECT-1',
                qr_code='QR-DIRECT-1',
                machine_code='LZ2050-2',
                alloy_grade='5052',
                spec_display='2.0×1200',
                current_workshop='2050车间',
                current_process='冷轧',
            )
        )
        db.commit()
        target_id = machines[1].id

    with session_factory() as db:
        payload = scan_lookup_service.lookup_qr(db, qr='QR-DIRECT-1')

    assert payload['machine_line_id'] == target_id
    assert payload['machine_line_code'] == 'LZ2050-2'
    assert payload['machine_binding_source'] == 'direct_machine_code'


def test_scan_lookup_returns_unresolved_when_workshop_unknown(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES-UNK-1',
                tracking_card_no='TRACK-UNK-1',
                qr_code='QR-UNK-1',
                alloy_grade='5052',
                spec_display='2.0×1200',
                current_workshop='未知车间',
                current_process='冷轧',
            )
        )
        db.commit()

    with session_factory() as db:
        payload = scan_lookup_service.lookup_qr(db, qr='QR-UNK-1')

    assert payload['machine_line_id'] is None
    assert payload['machine_binding_source'] == 'unresolved'


def test_scan_lookup_machine_binding_omitted_for_machine_identity_qr(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        workshop = _seed_workshop(db)
        db.add(
            Equipment(
                code='ZD-MID',
                name='机台直扫',
                workshop_id=workshop.id,
                equipment_type='ingot_caster',
                operational_status='running',
                shift_mode='three',
                qr_code='XT-ZD-MID',
                is_active=True,
            )
        )
        db.commit()

    with session_factory() as db:
        payload = scan_lookup_service.lookup_qr(db, qr='XT-ZD-MID')

    assert payload['source'] == 'machine_identity'
    assert 'machine_line_id' not in payload
    assert 'machine_binding_source' not in payload
