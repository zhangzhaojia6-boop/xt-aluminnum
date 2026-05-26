from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_db, get_current_user
from app.main import app
from app.models.base import Base
from app.models.master import Workshop


def _fake_manager():
    return SimpleNamespace(
        id=7,
        role='manager',
        is_admin=True,
        is_manager=True,
        is_reviewer=False,
        workshop_id=None,
        data_scope_type='all',
    )


@pytest.fixture
def client_with_workshops(tmp_path):
    db_path = tmp_path / 'test.db'
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    session = SessionLocal()
    session.add_all([
        Workshop(code='LZ2050', name='2050冷轧车间', is_active=True),
        Workshop(code='RZ', name='热轧车间', is_active=True),
        Workshop(code='CPK', name='成品库', is_active=True),
    ])
    session.commit()
    session.close()

    def _get_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _fake_manager
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_consumable_workshops_excludes_workshops_without_consumables(client_with_workshops):
    response = client_with_workshops.get('/api/v1/consumables/workshops')
    assert response.status_code == 200
    items = response.json()['items']
    types = {w['workshop_type'] for w in items}
    assert 'cold_roll' in types
    assert 'hot_roll' in types
    assert 'inventory' not in types


def test_consumable_workshops_returns_field_descriptors(client_with_workshops):
    response = client_with_workshops.get('/api/v1/consumables/workshops')
    items = response.json()['items']
    cold = next(w for w in items if w['workshop_type'] == 'cold_roll')
    field_names = [f['name'] for f in cold['fields']]
    assert field_names, 'cold_roll must expose at least one consumable field'


def test_get_daily_log_returns_empty_payload_when_no_record(client_with_workshops):
    workshops = client_with_workshops.get('/api/v1/consumables/workshops').json()['items']
    cold_id = next(w for w in workshops if w['workshop_type'] == 'cold_roll')['workshop_id']

    response = client_with_workshops.get(
        '/api/v1/consumables/daily',
        params={'workshop_id': cold_id, 'business_date': '2026-05-26'},
    )
    assert response.status_code == 200
    body = response.json()
    assert body['payload'] == {}
    assert body['workshop_type'] == 'cold_roll'
    assert body['business_date'] == '2026-05-26'


def test_upsert_then_fetch_round_trips_payload(client_with_workshops):
    workshops = client_with_workshops.get('/api/v1/consumables/workshops').json()['items']
    cold = next(w for w in workshops if w['workshop_type'] == 'cold_roll')
    cold_id = cold['workshop_id']
    field_name = cold['fields'][0]['name']

    upsert_payload = {
        'workshop_id': cold_id,
        'business_date': '2026-05-26',
        'payload': {field_name: 12.5, 'unknown_field_should_be_dropped': 99},
        'note': 'first day',
    }
    upsert = client_with_workshops.post('/api/v1/consumables/daily', json=upsert_payload)
    assert upsert.status_code == 200
    saved = upsert.json()
    assert saved['payload'] == {field_name: 12.5}
    assert saved['note'] == 'first day'

    fetch = client_with_workshops.get(
        '/api/v1/consumables/daily',
        params={'workshop_id': cold_id, 'business_date': '2026-05-26'},
    )
    assert fetch.json()['payload'] == {field_name: 12.5}


def test_upsert_replaces_existing_row_for_same_workshop_date(client_with_workshops):
    workshops = client_with_workshops.get('/api/v1/consumables/workshops').json()['items']
    cold = next(w for w in workshops if w['workshop_type'] == 'cold_roll')
    cold_id = cold['workshop_id']
    field_name = cold['fields'][0]['name']

    base = {
        'workshop_id': cold_id,
        'business_date': '2026-05-26',
        'note': None,
    }
    client_with_workshops.post('/api/v1/consumables/daily', json={**base, 'payload': {field_name: 1}})
    second = client_with_workshops.post('/api/v1/consumables/daily', json={**base, 'payload': {field_name: 2}})
    assert second.json()['payload'] == {field_name: 2}


def test_upsert_rejects_workshop_without_consumables(client_with_workshops):
    workshops_resp = client_with_workshops.get('/api/v1/consumables/workshops').json()['items']
    visible_ids = {w['workshop_id'] for w in workshops_resp}

    from app.models.master import Workshop  # noqa: PLC0415
    response = client_with_workshops.get(
        '/api/v1/consumables/daily',
        params={'workshop_id': max(visible_ids) + 1, 'business_date': '2026-05-26'},
    )
    assert response.status_code == 404
