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
from app.models.mes import MesCoilSnapshot
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


def test_mobile_coil_entry_rejects_snapshot_without_lock_token(tmp_path) -> None:
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

    assert response.status_code == 409
    assert response.json()['detail'] == 'locked_field_tampered'


def test_mobile_coil_entry_rejects_registered_coil_tamper_without_lock_token(tmp_path) -> None:
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

    assert response.status_code == 409
    assert response.json()['detail'] == 'locked_field_tampered'


def test_mobile_coil_entry_rejects_tokenless_submit_when_mes_snapshot_table_missing(tmp_path) -> None:
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

    assert response.status_code == 409
    assert response.json()['detail'] == 'locked_field_tampered'


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


def test_mobile_coil_entry_accepts_scan_lookup_token_with_submission_fields(tmp_path) -> None:
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
                'locked_fields_token': lookup_payload['lock_token'],
                'locked_fields_snapshot': {
                    'tracking_card_no': 'TRACK-LOOKUP-1',
                    'alloy_grade': '6061',
                    'input_spec': '1.2×1200',
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()['tracking_card_no'] == 'TRACK-LOOKUP-1'


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


def test_mobile_coil_entry_rejects_old_fields_from_tracking_card_lookup(tmp_path) -> None:
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
                'locked_fields_token': lookup_payload['lock_token'],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()['detail'] == 'locked_field_tampered'


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
