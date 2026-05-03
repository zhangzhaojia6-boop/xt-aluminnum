from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_current_user, get_db
from app.database import Base
from app.main import app
from app.models.rule_config import RuleConfig
from app.models.system import User
from app.services import rule_config_service


def build_sessionmaker(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rule-config-router.db'}", future=True)
    Base.metadata.create_all(engine, tables=[RuleConfig.__table__])
    return sessionmaker(bind=engine, future=True)


def _admin_user() -> User:
    return User(id=1, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)


def _manager_user() -> User:
    return User(id=2, username='manager', password_hash='x', name='Manager', role='manager', is_active=True)


def test_admin_can_list_upsert_and_update_rule_configs(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)
    rule_config_service.invalidate_cache()

    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = _admin_user
    client = TestClient(app)
    try:
        initial = client.get('/api/v1/rule-configs', params={'scope_type': 'workshop', 'scope_key': 'LZ01'})
        assert initial.status_code == 200
        assert any(item['key'] == 'MAX_SINGLE_SHIFT_WEIGHT' and item['source'] == 'fallback' for item in initial.json())

        created = client.post(
            '/api/v1/rule-configs',
            json={
                'scope_type': 'workshop',
                'scope_key': 'LZ01',
                'key': 'MAX_SINGLE_SHIFT_WEIGHT',
                'value': 55,
            },
        )
        assert created.status_code == 201
        created_payload = created.json()
        assert created_payload['value'] == 55
        assert created_payload['source'] == 'override'

        updated = client.put(f"/api/v1/rule-configs/{created_payload['id']}", json={'value': 54})
        assert updated.status_code == 200
        assert updated.json()['value'] == 54

        listed = client.get('/api/v1/rule-configs', params={'scope_type': 'workshop', 'scope_key': 'LZ01'})
    finally:
        app.dependency_overrides.clear()

    assert listed.status_code == 200
    max_weight = next(item for item in listed.json() if item['key'] == 'MAX_SINGLE_SHIFT_WEIGHT')
    assert max_weight['value'] == 54
    assert max_weight['source'] == 'override'


def test_rule_config_write_requires_admin(tmp_path) -> None:
    session_factory = build_sessionmaker(tmp_path)

    def fake_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = _manager_user
    client = TestClient(app)
    try:
        response = client.post(
            '/api/v1/rule-configs',
            json={
                'scope_type': 'factory',
                'scope_key': None,
                'key': 'MAX_SINGLE_SHIFT_WEIGHT',
                'value': 55,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
