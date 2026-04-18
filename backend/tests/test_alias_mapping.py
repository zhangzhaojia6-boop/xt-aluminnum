from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def test_alias_crud_endpoints(monkeypatch) -> None:
    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(id=10, username='admin', password_hash='x', name='Admin', role='admin', is_active=True)

    def fake_list(db, *, entity_type=None, source_type=None, is_active=None):
        return [
            SimpleNamespace(
                id=1,
                entity_type='workshop',
                canonical_code='W1',
                alias_code='WK-01',
                alias_name='熔铸',
                source_type='mes_export',
                is_active=True,
            )
        ]

    def fake_create(db, *, payload, operator):
        assert payload['canonical_code'] == 'W1'
        return SimpleNamespace(
            id=2,
            entity_type=payload['entity_type'],
            canonical_code=payload['canonical_code'],
            alias_code=payload.get('alias_code'),
            alias_name=payload.get('alias_name'),
            source_type=payload.get('source_type'),
            is_active=True,
        )

    def fake_update(db, *, alias_id, payload, operator):
        assert alias_id == 2
        return SimpleNamespace(
            id=2,
            entity_type=payload.get('entity_type', 'workshop'),
            canonical_code=payload.get('canonical_code', 'W1'),
            alias_code=payload.get('alias_code', 'WK-01'),
            alias_name=payload.get('alias_name', '熔铸'),
            source_type=payload.get('source_type', 'mes_export'),
            is_active=payload.get('is_active', True),
        )

    def fake_delete(db, *, alias_id, operator):
        assert alias_id == 2
        return None

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.master.master_service.list_aliases', fake_list)
    monkeypatch.setattr('app.routers.master.master_service.create_alias', fake_create)
    monkeypatch.setattr('app.routers.master.master_service.update_alias', fake_update)
    monkeypatch.setattr('app.routers.master.master_service.delete_alias', fake_delete)

    client = TestClient(app)
    response = client.get('/api/v1/master/aliases')
    assert response.status_code == 200
    assert response.json()['total'] == 1
    assert response.json()['items'][0]['canonical_code'] == 'W1'

    create = client.post(
        '/api/v1/master/aliases',
        json={'entity_type': 'workshop', 'canonical_code': 'W1', 'alias_code': 'WK-01', 'alias_name': '熔铸'},
    )
    assert create.status_code == 201
    assert create.json()['id'] == 2

    update = client.put('/api/v1/master/aliases/2', json={'alias_name': '熔铸车间'})
    assert update.status_code == 200
    assert update.json()['alias_name'] == '熔铸车间'

    delete = client.delete('/api/v1/master/aliases/2')
    assert delete.status_code == 200

    app.dependency_overrides.clear()
