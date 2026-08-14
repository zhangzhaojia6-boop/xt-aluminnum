from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_db
from app.core.permissions import get_current_mobile_user
from app.database import Base
from app.main import app
from app.models.master import Equipment, Workshop
from app.models.mes import MesCoilSnapshot, MesWorkshopProcessRecord
from app.models.production import ShiftProductionData, WorkOrder, WorkOrderEntry
from app.models.shift import ShiftConfig
from app.models.system import User
from app.services import scan_lookup_service
from app.services.locked_fields_service import sign_locked_fields


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mobile-locked-fields.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Equipment.__table__,
            ShiftConfig.__table__,
            User.__table__,
            MesCoilSnapshot.__table__,
            MesWorkshopProcessRecord.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            ShiftProductionData.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _session_factory_without_mes_snapshot(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mobile-locked-fields-no-mes.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Equipment.__table__,
            ShiftConfig.__table__,
            User.__table__,
            WorkOrder.__table__,
            WorkOrderEntry.__table__,
            ShiftProductionData.__table__,
        ],
    )
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


def _client_with_db(session_factory):
    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def fake_mobile_user() -> User:
        return User(
            id=1,
            username='operator',
            password_hash='x',
            name='主操',
            role='machine_operator',
            workshop_id=1,
            data_scope_type='self_workshop',
            is_mobile_user=True,
            is_reviewer=False,
            is_manager=False,
            is_active=True,
        )

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_mobile_user] = fake_mobile_user
    return TestClient(app)


def _seed_reference_data(session_factory) -> None:
    with session_factory() as db:
        workshop = Workshop(code='ZR2', name='铸二车间', workshop_type='casting', sort_order=1, is_active=True)
        db.add(workshop)
        db.flush()
        db.add(
            ShiftConfig(
                code='D',
                name='白班',
                shift_type='day',
                start_time=time(8, 0),
                end_time=time(20, 0),
                workshop_id=workshop.id,
                is_active=True,
            )
        )
        db.commit()


def test_mobile_coil_entry_accepts_snapshot_without_lock_token(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    client = _client_with_db(session_factory)
    try:
        response = client.post(
            '/api/v1/mobile/coil-entry',
            json={
                'tracking_card_no': 'TRACK-LOCK-1',
                'alloy_grade': '6061',
                'input_spec': '1.2×1200',
                'input_weight': 1000,
                'output_weight': 960,
                'business_date': '2026-05-03',
                'shift_id': 1,
                'locked_fields_snapshot': {
                    'tracking_card_no': 'TRACK-LOCK-1',
                    'alloy_grade': '6061',
                    'input_spec': '1.2×1200',
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


def test_mobile_coil_entry_reuses_existing_row_after_response_is_lost(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    payload = {
        'tracking_card_no': 'TRACK-RETRY-1',
        'alloy_grade': '6061',
        'input_spec': '1.2×1200',
        'input_weight': 1000,
        'output_weight': 960,
        'business_date': '2026-05-03',
        'shift_id': 1,
    }
    client = _client_with_db(session_factory)
    try:
        first = client.post('/api/v1/mobile/coil-entry', json=payload)
        second = client.post('/api/v1/mobile/coil-entry', json=payload)
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()['id'] == first.json()['id']
    with session_factory() as db:
        rows = db.query(WorkOrderEntry).filter(WorkOrderEntry.entry_type == 'mobile_coil').all()
    assert len(rows) == 1


def test_mobile_coil_entry_rejects_changed_payload_for_existing_row(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    payload = {
        'tracking_card_no': 'TRACK-RETRY-2',
        'alloy_grade': '6061',
        'input_spec': '1.2×1200',
        'input_weight': 1000,
        'output_weight': 960,
        'business_date': '2026-05-03',
        'shift_id': 1,
    }
    client = _client_with_db(session_factory)
    try:
        first = client.post('/api/v1/mobile/coil-entry', json=payload)
        changed = client.post('/api/v1/mobile/coil-entry', json={**payload, 'output_weight': 950})
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert changed.status_code == 409
    assert changed.json()['detail'] == 'coil_entry_already_submitted'


def test_mobile_coil_entry_accepts_manual_entry_even_if_mes_has_different_values(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    with session_factory() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES-LOCK-REGISTERED',
                tracking_card_no='TRACK-REGISTERED-1',
                qr_code='QR-REGISTERED-1',
                alloy_grade='6061',
                spec_display='1.2×1200',
            )
        )
        db.commit()

    client = _client_with_db(session_factory)
    try:
        response = client.post(
            '/api/v1/mobile/coil-entry',
            json={
                'tracking_card_no': 'TRACK-REGISTERED-1',
                'alloy_grade': '7075',
                'input_spec': '1.2×1200',
                'input_weight': 1000,
                'output_weight': 960,
                'business_date': '2026-05-03',
                'shift_id': 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


def test_mobile_coil_entry_accepts_tokenless_submit_when_mes_snapshot_table_missing(tmp_path) -> None:
    session_factory = _session_factory_without_mes_snapshot(tmp_path)
    _seed_reference_data(session_factory)
    client = _client_with_db(session_factory)
    try:
        response = client.post(
            '/api/v1/mobile/coil-entry',
            json={
                'tracking_card_no': 'TRACK-NO-MES-TABLE',
                'alloy_grade': '6061',
                'input_spec': '1.2×1200',
                'input_weight': 1000,
                'output_weight': 960,
                'business_date': '2026-05-03',
                'shift_id': 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


def test_mobile_coil_entry_accepts_matching_locked_fields(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    locked_snapshot = {
        'tracking_card_no': 'TRACK-LOCK-2',
        'alloy_grade': '6061',
        'input_spec': '1.2×1200',
    }
    client = _client_with_db(session_factory)
    try:
        response = client.post(
            '/api/v1/mobile/coil-entry',
            json={
                'tracking_card_no': 'TRACK-LOCK-2',
                'alloy_grade': '6061',
                'input_spec': '1.2×1200',
                'input_weight': 1000,
                'output_weight': 960,
                'business_date': '2026-05-03',
                'shift_id': 1,
                'locked_fields_token': sign_locked_fields(locked_snapshot),
                'locked_fields_snapshot': locked_snapshot,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()['tracking_card_no'] == 'TRACK-LOCK-2'


def test_mobile_coil_entry_accepts_missing_output_weight(tmp_path) -> None:
    """output_weight 改为可选后，允许不填"""
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    client = _client_with_db(session_factory)
    try:
        response = client.post(
            '/api/v1/mobile/coil-entry',
            json={
                'tracking_card_no': 'TRACK-MISSING-OUTPUT',
                'alloy_grade': '1060',
                'input_spec': '1.2×1200',
                'input_weight': 1000,
                'business_date': '2026-05-03',
                'shift_id': 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert 'id' in data or 'work_order_id' in data
    with session_factory() as db:
        entries = db.query(WorkOrderEntry).all()
        assert len(entries) == 1
        entry = entries[0]
        assert entry.input_weight == 1000
        assert entry.output_weight is None


def test_mobile_coil_entry_maps_unit_output_alias(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    client = _client_with_db(session_factory)
    try:
        response = client.post(
            '/api/v1/mobile/coil-entry',
            json={
                'tracking_card_no': 'TRACK-UNIT-OUTPUT',
                'alloy_grade': '1060',
                'input_spec': '1.2×1200',
                'input_weight': 1000,
                'unit_output': 960,
                'material_state': 'H24',
                'spool_weight': 10,
                'extra_payload': {
                    'ingot_spec': '6×1600',
                    'cast_speed': 720,
                    'skin_weight': 12,
                    'trim_weight': 4,
                },
                'business_date': '2026-05-03',
                'shift_id': 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    with session_factory() as db:
        entry = db.query(WorkOrderEntry).one()
        assert entry.output_weight == 960
        assert entry.material_state == 'H24'
        assert entry.spool_weight == 10
        assert entry.extra_payload['ingot_spec'] == '6×1600'
        assert entry.extra_payload['cast_speed'] == 720
        assert entry.extra_payload['skin_weight'] == 12
        assert entry.extra_payload['trim_weight'] == 4


def test_mobile_coil_entry_accepts_output_weight_above_input_weight(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    client = _client_with_db(session_factory)
    try:
        response = client.post(
            '/api/v1/mobile/coil-entry',
            json={
                'tracking_card_no': 'TRACK-BAD-WEIGHT',
                'alloy_grade': '1060',
                'input_spec': '1.2×1200',
                'input_weight': 1000,
                'output_weight': 1200,
                'business_date': '2026-05-03',
                'shift_id': 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


def test_mobile_coil_entry_accepts_equivalent_locked_spec_and_alloy_values(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    locked_snapshot = {
        'tracking_card_no': 'TRACK-LOCK-EQUIV',
        'alloy_grade': '1060.0',
        'input_spec': '1.2×1200',
    }
    client = _client_with_db(session_factory)
    try:
        response = client.post(
            '/api/v1/mobile/coil-entry',
            json={
                'tracking_card_no': 'TRACK-LOCK-EQUIV',
                'alloy_grade': '1060',
                'input_spec': '1.20×1200×C',
                'input_weight': 1000,
                'output_weight': 960,
                'business_date': '2026-05-03',
                'shift_id': 1,
                'locked_fields_token': sign_locked_fields(locked_snapshot),
                'locked_fields_snapshot': locked_snapshot,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()['tracking_card_no'] == 'TRACK-LOCK-EQUIV'


def test_mobile_coil_entry_accepts_scan_lookup_without_lock_token(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    with session_factory() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES-LOCK-LOOKUP',
                tracking_card_no='TRACK-LOOKUP-1',
                qr_code='QR-LOOKUP-1',
                alloy_grade='6061',
                spec_display='1.2×1200',
                current_workshop='冷轧车间',
                current_process='冷轧',
                next_workshop='退火车间',
                next_process='退火',
            )
        )
        db.commit()

    with session_factory() as db:
        lookup_payload = scan_lookup_service.lookup_qr(db, qr='QR-LOOKUP-1')

    assert lookup_payload['lock_keys'] == []
    assert lookup_payload['lock_token'] is None

    client = _client_with_db(session_factory)
    try:
        response = client.post(
            '/api/v1/mobile/coil-entry',
            json={
                'tracking_card_no': 'TRACK-LOOKUP-1',
                'alloy_grade': '6061',
                'input_spec': '1.2×1200',
                'input_weight': 1000,
                'output_weight': 960,
                'business_date': '2026-05-03',
                'shift_id': 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()['tracking_card_no'] == 'TRACK-LOOKUP-1'


def test_mobile_coil_entry_accepts_edited_mes_process_output_weight(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    with session_factory() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES-LOCK-PROC',
                tracking_card_no='TRACK-PROC-LOCK',
                qr_code='QR-PROC-LOCK',
                batch_no='BATCH-PROC-LOCK',
                alloy_grade='6061',
                spec_display='1.2×1200',
            )
        )
        db.add(
            MesWorkshopProcessRecord(
                source_id='PROC-LOCK-1',
                source_path='mvc',
                batch_no='BATCH-PROC-LOCK',
                input_weight_kg=1000,
                output_weight_kg=960,
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
        lookup_payload = scan_lookup_service.lookup_qr(db, qr='QR-PROC-LOCK')

    assert lookup_payload['lock_keys'] == []
    assert lookup_payload['lock_token'] is None

    client = _client_with_db(session_factory)
    try:
        response = client.post(
            '/api/v1/mobile/coil-entry',
            json={
                'tracking_card_no': 'TRACK-PROC-LOCK',
                'alloy_grade': '6061',
                'input_spec': '1.0×1200',
                'output_spec': '0.8×1200',
                'input_weight': 1000,
                'output_weight': 950,
                'business_date': '2026-05-03',
                'shift_id': 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()['output_weight'] == 950.0


def test_mobile_coil_entry_enriches_flow_from_mes_material_code_match(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    with session_factory() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES-MATERIAL-FLOW',
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

    client = _client_with_db(session_factory)
    try:
        response = client.post(
            '/api/v1/mobile/coil-entry',
            json={
                'tracking_card_no': 'R3-9216-2',
                'alloy_grade': '5052',
                'input_spec': '3.175×1524×3048',
                'input_weight': 9780,
                'output_weight': 9300,
                'business_date': '2026-05-03',
                'shift_id': 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['tracking_card_no'] == 'R3-9216-2'
    assert payload['previous_process'] is None
    assert payload['next_process'] == '北线退火'
    assert payload['extra_payload']['flow'] == {
        'current_workshop': '2050车间',
        'current_process': '冷轧',
        'next_workshop': '新厂在线车间',
        'next_process': '北线退火',
        'flow_source': 'mes_projection',
    }
    assert payload['extra_payload']['mes_reference'] == {
        'tracking_card_no': '26RA03782',
        'material_code': 'R3-9216-2',
        'batch_no': '26RA03782',
        'coil_id': 'MES-MATERIAL-FLOW',
    }


def test_mobile_coil_entry_accepts_user_edited_fields_from_tracking_card_lookup(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    with session_factory() as db:
        db.add_all(
            [
                MesCoilSnapshot(
                    coil_id='MES-LOOKUP-OLD',
                    tracking_card_no='TRACK-LOOKUP-SAME',
                    qr_code='QR-LOOKUP-OLD',
                    alloy_grade='6061',
                    spec_display='1.0×1000',
                    updated_from_mes_at=datetime(2026, 5, 3, 8, tzinfo=timezone.utc),
                ),
                MesCoilSnapshot(
                    coil_id='MES-LOOKUP-NEW',
                    tracking_card_no='TRACK-LOOKUP-SAME',
                    qr_code='QR-LOOKUP-NEW',
                    alloy_grade='7075',
                    spec_display='2.0×1200',
                    updated_from_mes_at=datetime(2026, 5, 3, 9, tzinfo=timezone.utc),
                ),
            ]
        )
        db.commit()

    with session_factory() as db:
        lookup_payload = scan_lookup_service.lookup_qr(db, qr='TRACK-LOOKUP-SAME')

    assert lookup_payload['lock_keys'] == []
    assert lookup_payload['lock_token'] is None

    client = _client_with_db(session_factory)
    try:
        response = client.post(
            '/api/v1/mobile/coil-entry',
            json={
                'tracking_card_no': 'TRACK-LOOKUP-SAME',
                'alloy_grade': '6061',
                'input_spec': '1.0×1000',
                'input_weight': 1000,
                'output_weight': 960,
                'business_date': '2026-05-03',
                'shift_id': 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()['alloy_grade'] == '6061'


def test_mobile_coil_entry_rejects_missing_locked_flow_fields(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    locked_snapshot = {
        'tracking_card_no': 'TRACK-LOCK-3',
        'current_process': '冷轧',
        'next_process': '退火',
    }
    client = _client_with_db(session_factory)
    try:
        response = client.post(
            '/api/v1/mobile/coil-entry',
            json={
                'tracking_card_no': 'TRACK-LOCK-3',
                'alloy_grade': '6061',
                'input_spec': '1.2×1200',
                'input_weight': 1000,
                'output_weight': 960,
                'business_date': '2026-05-03',
                'shift_id': 1,
                'locked_fields_token': sign_locked_fields(locked_snapshot),
                'locked_fields_snapshot': locked_snapshot,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()['detail'] == 'locked_field_tampered'


def test_mobile_coil_entry_rejects_invalid_lock_token(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    _seed_reference_data(session_factory)
    client = _client_with_db(session_factory)
    try:
        response = client.post(
            '/api/v1/mobile/coil-entry',
            json={
                'tracking_card_no': 'TRACK-LOCK-4',
                'alloy_grade': '6061',
                'input_spec': '1.2×1200',
                'input_weight': 1000,
                'output_weight': 960,
                'business_date': '2026-05-03',
                'shift_id': 1,
                'locked_fields_token': 'invalid.token',
                'locked_fields_snapshot': {
                    'tracking_card_no': 'TRACK-LOCK-4',
                    'alloy_grade': '6061',
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()['detail'] == 'locked_field_tampered'
