from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_db
from app.core.permissions import get_current_mobile_user
from app.database import Base
from app.main import app
from app.models.master import Equipment, Workshop
from app.models.mes import MesCoilSnapshot, MesWorkshopProcessRecord
from app.models.system import User


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mobile-scan-lookup.db'}", future=True)
    Base.metadata.create_all(
        engine,
        tables=[
            Workshop.__table__,
            Equipment.__table__,
            MesCoilSnapshot.__table__,
            MesWorkshopProcessRecord.__table__,
            User.__table__,
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


def test_mobile_scan_lookup_route_returns_header_fields(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES-ROUTE-1',
                tracking_card_no='TRACK-ROUTE-1',
                qr_code='QR-ROUTE-1',
                batch_no='BATCH-ROUTE-1',
                alloy_grade='6061',
                spec_display='1.2×1200',
                current_process='冷轧',
                next_process='退火',
            )
        )
        db.commit()

    client = _client_with_db(session_factory)
    try:
        response = client.get('/api/v1/mobile/scan-lookup', params={'qr': 'QR-ROUTE-1'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['source'] == 'coil_snapshot'
    assert payload['header_fields']['tracking_card_no'] == 'TRACK-ROUTE-1'
    assert payload['header_fields']['input_spec'] == '1.2×1200'
    assert payload['lock_keys'] == []
    assert payload['lock_token'] is None


def test_mobile_scan_lookup_route_returns_mes_process_fields(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    with session_factory() as db:
        db.add(
            MesCoilSnapshot(
                coil_id='MES-ROUTE-PROC',
                tracking_card_no='TRACK-ROUTE-PROC',
                qr_code='QR-ROUTE-PROC',
                batch_no='BATCH-ROUTE-PROC',
                alloy_grade='6061',
                spec_display='1.2×1200',
            )
        )
        db.add(
            MesWorkshopProcessRecord(
                source_id='PROC-ROUTE-1',
                source_path='mvc',
                batch_no='BATCH-ROUTE-PROC',
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

    client = _client_with_db(session_factory)
    try:
        response = client.get('/api/v1/mobile/scan-lookup', params={'qr': 'QR-ROUTE-PROC'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload['header_fields']['input_spec'] == '1.0×1200'
    assert payload['header_fields']['output_spec'] == '0.8×1200'
    assert payload['header_fields']['input_weight'] == 1000.0
    assert payload['header_fields']['output_weight'] == 960.0
    assert payload['header_fields']['on_machine_time'] == '15:40'
    assert payload['header_fields']['off_machine_time'] == '16:20'
    assert payload['lock_keys'] == []
    assert payload['lock_token'] is None


def test_mobile_scan_lookup_route_returns_readable_404(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client_with_db(session_factory)
    try:
        response = client.get('/api/v1/mobile/scan-lookup', params={'qr': 'missing'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()['detail'] == 'qr_not_found'
