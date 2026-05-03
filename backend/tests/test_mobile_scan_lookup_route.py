from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_db
from app.core.permissions import get_current_mobile_user
from app.database import Base
from app.main import app
from app.models.master import Equipment, Workshop
from app.models.mes import MesCoilSnapshot
from app.models.system import User
from app.services.locked_fields_service import verify_locked_fields_token


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mobile-scan-lookup.db'}", future=True)
    Base.metadata.create_all(engine, tables=[Workshop.__table__, Equipment.__table__, MesCoilSnapshot.__table__, User.__table__])
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
    locked_fields = verify_locked_fields_token(payload['lock_token'])
    assert locked_fields['tracking_card_no'] == 'TRACK-ROUTE-1'
    assert locked_fields['current_process'] == '冷轧'


def test_mobile_scan_lookup_route_returns_readable_404(tmp_path) -> None:
    session_factory = _session_factory(tmp_path)
    client = _client_with_db(session_factory)
    try:
        response = client.get('/api/v1/mobile/scan-lookup', params={'qr': 'missing'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()['detail'] == 'qr_not_found'
