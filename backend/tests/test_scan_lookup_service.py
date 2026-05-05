from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.master import Equipment, Workshop
from app.models.mes import MesCoilSnapshot
from app.services import scan_lookup_service
from app.services.locked_fields_service import verify_locked_fields_token


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'scan-lookup.db'}", future=True)
    Base.metadata.create_all(engine, tables=[Workshop.__table__, Equipment.__table__, MesCoilSnapshot.__table__])
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
    assert payload['lock_keys'] == ['tracking_card_no', 'alloy_grade', 'input_spec']
    locked_fields = verify_locked_fields_token(payload['lock_token'])
    assert locked_fields == {
        'tracking_card_no': 'TRACK-QR-1',
        'alloy_grade': '6061',
        'input_spec': '1.2×1200',
    }


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
    locked_fields = verify_locked_fields_token(payload['lock_token'])
    assert locked_fields == {
        'tracking_card_no': 'TRACK-SAME',
        'alloy_grade': '5052',
        'input_spec': '2.0×1200',
    }


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

    assert snapshot == {
        'tracking_card_no': 'TRACK-LOCK-SAME',
        'alloy_grade': '7075',
        'input_spec': '2.0×1200',
    }


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


def test_scan_lookup_raises_not_found_when_qr_unknown(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db, pytest.raises(scan_lookup_service.ScanLookupNotFound):
        scan_lookup_service.lookup_qr(db, qr='missing')
